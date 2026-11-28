"""Settings writer of the security-baseline skill (spec 025, T4.3, K14, ADR-3).

Every test builds its own home, project and state directory under
``tmp_path``; nothing reads or writes the real home or a system path. The
managed roots and the backup directory are injected, and faults (a changed
file, a denied write, an interrupt) are produced by patching one ``os`` call
or the writer's re-stat hook.
"""

from __future__ import annotations

import builtins
import contextlib
import datetime
import errno
import hashlib
import importlib.util
import inspect
import json
import os
import pathlib
import re
import stat
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_SIBLINGS = ("jsonio", "layers")
NOW = datetime.datetime(2026, 11, 28, 12, 0, 0, tzinfo=datetime.timezone.utc)
STAMP = "20261128T120000Z"
BACKUP_NAME = re.compile(r"^\d{8}T\d{6}Z-(user|project|local)-[0-9a-f]{8}\.json$")

ORIGINAL = b'{\n  "model": "opus",\n  "permissions": {\n    "deny": []\n  }\n}\n'
EXPECTED = {"model": "opus", "permissions": {"deny": ["Read(~/.ssh/**)"]}}


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def writer():
    previous = {name: sys.modules.get(name) for name in BARE_SIBLINGS}
    for name in BARE_SIBLINGS:
        _load(name, name + ".py")
    try:
        yield _load("sb_writer", "writer.py")
    finally:
        sys.modules.pop("sb_writer", None)
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.fixture
def world(tmp_path, writer, monkeypatch):
    """A home, a project that is its own repo root, a backup directory and a
    stand-in managed root. ``$TMPDIR`` points at an empty directory that must
    stay empty."""
    base = pathlib.Path(os.path.realpath(tmp_path))
    home = base / "home"
    project = base / "repo"
    backups = base / "state" / "backups"
    managed = base / "managed"
    tmpdir = base / "tmpdir"
    for directory in (home / ".claude", project / ".claude", backups, managed, tmpdir):
        directory.mkdir(parents=True)
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    return types.SimpleNamespace(
        base=base,
        home=home,
        project=project,
        backups=backups,
        managed=managed,
        tmpdir=tmpdir,
        targets=writer.allowed_targets(str(home), None, str(project), str(project)),
    )


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _plan(world, scope, original=ORIGINAL):
    """A TargetPlan stand-in for `scope`; writes `original` to the target
    first unless it is None (target missing)."""
    path = pathlib.Path(world.targets[scope].path)
    if original is not None:
        path.write_bytes(original)
    return types.SimpleNamespace(
        scope=scope,
        path=str(path),
        pre_sha256=None if original is None else _sha(original),
    )


def _write(writer, world, plan, expected=None, fmt="detect", **overrides):
    if fmt == "detect":
        fmt = writer.jsonio.Format(2, "\n", True)
    arguments = {
        "targets": world.targets,
        "backup_dir": str(world.backups),
        "managed_roots": (str(world.managed),),
        "now": NOW,
    }
    arguments.update(overrides)
    return writer.write_target(plan, EXPECTED if expected is None else expected, fmt, **arguments)


def _leftovers(directory):
    """Names in `directory` that are neither settings files nor directories."""
    return sorted(
        entry.name for entry in pathlib.Path(directory).iterdir()
        if entry.name not in ("settings.json", "settings.local.json") and not entry.is_dir()
    )


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _fd_path(fd):
    """The path of an open directory, as the kernel reports it."""
    if sys.platform == "darwin":
        import fcntl
        return fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024).rstrip(b"\0").decode()
    return os.readlink(f"/proc/self/fd/{fd}")


def _opened_path(path, dir_fd):
    """The full path an `os.open` call names, also when it is relative to a
    directory descriptor."""
    path = os.fspath(path)
    return path if dir_fd is None else os.path.join(_fd_path(dir_fd), path)


@contextlib.contextmanager
def _spy_opens(monkeypatch):
    """Record every `os.open` and builtin `open` made inside the block."""
    calls = []
    real_os_open = os.open
    real_open = builtins.open

    def os_open(path, flags, mode=0o777, *, dir_fd=None):
        calls.append((_opened_path(path, dir_fd), flags))
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    def plain_open(file, *args, **kwargs):
        calls.append((file, "builtin"))
        return real_open(file, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", os_open)
        patch.setattr(builtins, "open", plain_open)
        yield calls


def _creating(calls):
    return [(path, flags) for path, flags in calls
            if flags != "builtin" and flags & os.O_CREAT]


def _fail_open_of(monkeypatch, wanted, code):
    """Make `os.open` fail with `code` for creating opens whose path matches."""
    real_os_open = os.open

    def os_open(path, flags, mode=0o777, *, dir_fd=None):
        if flags & os.O_CREAT and wanted(_opened_path(path, dir_fd)):
            raise OSError(code, os.strerror(code))
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", os_open)


class TestAllowedTargets:
    def test_three_targets_at_the_computed_paths(self, writer, world):
        targets = world.targets

        assert sorted(targets) == ["local", "project", "user"]
        assert targets["user"].path == str(world.home / ".claude" / "settings.json")
        assert targets["project"].path == str(world.project / ".claude" / "settings.json")
        assert targets["local"].path == str(world.project / ".claude" / "settings.local.json")

    def test_config_dir_relocates_the_user_file(self, writer, world):
        config = world.base / "cfg"

        targets = writer.allowed_targets(str(world.home), str(config), str(world.project), None)

        assert targets["user"].path == str(config / "settings.json")

    def test_local_file_lives_at_the_repo_root(self, writer, world):
        start = world.project / "packages" / "app"

        targets = writer.allowed_targets(str(world.home), None, str(start), str(world.project))

        assert targets["local"].path == str(world.project / ".claude" / "settings.local.json")
        assert targets["project"].path == str(start / ".claude" / "settings.json")

    def test_local_file_falls_back_to_the_project_dir(self, writer, world):
        targets = writer.allowed_targets(str(world.home), None, str(world.project), None)

        assert targets["local"].path == str(world.project / ".claude" / "settings.local.json")


class TestTargetAllowlist:
    @pytest.mark.parametrize("scope, path", [
        ("user", "/etc/claude-code/managed-settings.json"),
        ("user", "/etc/claude-code/managed-settings.d/10-org.json"),
        ("user", "/Library/Application Support/ClaudeCode/managed-settings.json"),
        ("managed", "/etc/claude-code/managed-settings.json"),
        ("managed-dropin", "/etc/claude-code/managed-settings.d/10-org.json"),
        ("project", "{base}/elsewhere/settings.json"),
        ("local", "{home}/.ssh/config"),
        ("project", "{home}/.claude/settings.json"),
        ("user", "{project}/.claude/settings.json"),
        ("user", "{home}/.claude.json"),
        ("user", None),
        (None, "{home}/.claude/settings.json"),
    ])
    def test_anything_but_a_computed_target_is_refused_before_any_open(
        self, writer, world, monkeypatch, scope, path
    ):
        if path is not None:
            path = path.format(base=world.base, home=world.home, project=world.project)
        plan = types.SimpleNamespace(scope=scope, path=path, pre_sha256=None)
        touched = []
        real_lstat = os.lstat

        def lstat(target, *args, **kwargs):
            touched.append(target)
            return real_lstat(target, *args, **kwargs)

        with _spy_opens(monkeypatch) as calls:
            monkeypatch.setattr(os, "lstat", lstat)
            result = _write(writer, world, plan)
            monkeypatch.setattr(os, "lstat", real_lstat)

        assert result.refused is True
        assert result.error == "not-a-target"
        assert result.written is False
        assert calls == []
        assert touched == []
        assert list(world.backups.iterdir()) == []

    def test_user_file_resolving_into_a_managed_root_is_refused(self, writer, world):
        managed_file = world.managed / "managed-settings.json"
        managed_file.write_bytes(ORIGINAL)
        link = world.home / ".claude" / "settings.json"
        link.symlink_to(managed_file)
        plan = types.SimpleNamespace(
            scope="user", path=str(link), pre_sha256=_sha(ORIGINAL))

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "managed")
        assert managed_file.read_bytes() == ORIGINAL
        assert _leftovers(world.managed) == ["managed-settings.json"]

    def test_default_managed_roots_are_the_system_roots(self, writer):
        assert set(writer.MANAGED_ROOTS) == set(writer.layers.SYSTEM_ROOTS.values())

    def test_refusal_reports_the_same_reason_without_opening(self, writer, world, monkeypatch):
        outside = world.base / "outside"
        outside.mkdir()
        (world.project / ".claude").rmdir()
        (world.project / ".claude").symlink_to(outside)
        (world.home / ".claude" / "settings.json").write_bytes(ORIGINAL)

        with _spy_opens(monkeypatch) as calls:
            reasons = {
                scope: writer.refusal(
                    scope, world.targets[scope].path,
                    targets=world.targets, managed_roots=(str(world.managed),))
                for scope in ("user", "project", "local")
            }
            stray = writer.refusal(
                "user", "/etc/claude-code/managed-settings.json",
                targets=world.targets, managed_roots=(str(world.managed),))

        assert reasons == {"user": None, "project": "outside-project", "local": "outside-project"}
        assert stray == "not-a-target"
        assert calls == []


class TestSymlinkPolicy:
    def test_project_claude_dir_symlinked_outside_the_project_is_refused(self, writer, world):
        outside = world.base / "outside"
        outside.mkdir()
        victim = outside / "settings.json"
        victim.write_bytes(ORIGINAL)
        (world.project / ".claude").rmdir()
        (world.project / ".claude").symlink_to(outside)
        plan = types.SimpleNamespace(
            scope="project", path=world.targets["project"].path, pre_sha256=_sha(ORIGINAL))

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "outside-project")
        assert victim.read_bytes() == ORIGINAL
        assert _leftovers(outside) == []

    def test_local_file_symlinked_to_an_ssh_config_is_refused(self, writer, world):
        ssh = world.home / ".ssh"
        ssh.mkdir()
        victim = ssh / "config"
        victim.write_bytes(b"Host *\n")
        link = world.project / ".claude" / "settings.local.json"
        link.symlink_to(victim)
        plan = types.SimpleNamespace(
            scope="local", path=str(link), pre_sha256=_sha(b"Host *\n"))

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "symlink")
        assert victim.read_bytes() == b"Host *\n"
        assert link.is_symlink()
        assert _leftovers(ssh) == ["config"]

    def test_project_file_symlinked_inside_the_project_is_refused_too(self, writer, world):
        inner = world.project / "package.json"
        inner.write_bytes(ORIGINAL)
        link = world.project / ".claude" / "settings.json"
        link.symlink_to(inner)
        plan = types.SimpleNamespace(
            scope="project", path=str(link), pre_sha256=_sha(ORIGINAL))

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "symlink")
        assert inner.read_bytes() == ORIGINAL

    def test_claude_dir_symlinked_inside_the_project_is_written(self, writer, world):
        inner = world.project / "config" / "claude"
        inner.mkdir(parents=True)
        (world.project / ".claude").rmdir()
        (world.project / ".claude").symlink_to(inner)
        plan = _plan(world, "project")

        result = _write(writer, world, plan)

        assert result.written is True
        assert result.real_path == str(inner / "settings.json")
        assert json.loads((inner / "settings.json").read_bytes()) == EXPECTED

    def test_user_symlink_into_dotfiles_is_followed_and_kept(self, writer, world, monkeypatch):
        dotfiles = world.home / "dotfiles" / "claude"
        dotfiles.mkdir(parents=True)
        real = dotfiles / "settings.json"
        real.write_bytes(ORIGINAL)
        link = world.home / ".claude" / "settings.json"
        link.symlink_to(real)
        plan = types.SimpleNamespace(scope="user", path=str(link), pre_sha256=_sha(ORIGINAL))

        with _spy_opens(monkeypatch) as calls:
            result = _write(writer, world, plan)

        assert result.written is True and result.verified is True
        assert link.is_symlink()
        assert os.readlink(link) == str(real)
        assert not real.is_symlink()
        assert json.loads(real.read_bytes()) == EXPECTED
        assert result.path == str(link)
        assert result.real_path == str(real)
        temp_dirs = {os.path.dirname(path) for path, _ in _creating(calls)
                     if not path.startswith(str(world.backups))}
        assert temp_dirs == {str(dotfiles)}
        assert _leftovers(world.home / ".claude") == []

    def test_dangling_user_symlink_is_refused(self, writer, world):
        link = world.home / ".claude" / "settings.json"
        link.symlink_to(world.home / "dotfiles" / "missing.json")
        plan = types.SimpleNamespace(scope="user", path=str(link), pre_sha256=None)

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "symlink")
        assert not (world.home / "dotfiles").exists()

    def test_target_owned_by_another_user_is_refused(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        owner = os.stat(plan.path).st_uid
        monkeypatch.setattr(os, "geteuid", lambda: owner + 1)

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "foreign-owner")
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
    def test_fifo_target_is_refused_without_blocking(self, writer, world):
        path = world.targets["local"].path
        os.mkfifo(path)
        plan = types.SimpleNamespace(scope="local", path=path, pre_sha256=None)

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "not-regular")
        assert stat.S_ISFIFO(os.lstat(path).st_mode)

    def test_directory_target_is_refused(self, writer, world):
        path = world.targets["project"].path
        os.mkdir(path)
        plan = types.SimpleNamespace(scope="project", path=path, pre_sha256=None)

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "not-regular")

    def test_empty_read_only_placeholder_is_refused_with_the_doctor_hint(self, writer, world):
        plan = _plan(world, "local", original=b"")
        os.chmod(plan.path, 0o444)

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "placeholder")
        assert "claude doctor" in result.message
        assert "placeholder" in result.message
        assert pathlib.Path(plan.path).read_bytes() == b""
        assert _mode(plan.path) == 0o444


class TestBackup:
    def test_backup_is_private_named_and_equal_to_the_original(self, writer, world):
        plan = _plan(world, "user")

        result = _write(writer, world, plan)

        backup = pathlib.Path(result.backup)
        assert backup.parent == world.backups
        assert backup.name == f"{STAMP}-user-{_sha(ORIGINAL)[:8]}.json"
        assert BACKUP_NAME.match(backup.name)
        assert _mode(backup) == 0o600
        assert backup.read_bytes() == ORIGINAL

    def test_backup_is_private_under_a_permissive_umask(self, writer, world):
        plan = _plan(world, "project")
        previous = os.umask(0)
        try:
            result = _write(writer, world, plan)
        finally:
            os.umask(previous)

        assert _mode(result.backup) == 0o600

    def test_backup_is_created_exclusively_without_following_links(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "user")

        with _spy_opens(monkeypatch) as calls:
            _write(writer, world, plan)

        created = [flags for path, flags in _creating(calls)
                   if path.startswith(str(world.backups))]
        assert len(created) == 1
        assert created[0] & os.O_EXCL and created[0] & os.O_NOFOLLOW

    def test_backup_that_does_not_read_back_equal_stops_the_write(self, writer, world):
        plan = _plan(world, "user")
        squatter = world.backups / f"{STAMP}-user-{_sha(ORIGINAL)[:8]}.json"
        squatter.write_bytes(b'{"not": "the original"}\n')

        result = _write(writer, world, plan)

        assert result.error == "backup-failed"
        assert result.written is False and result.backup is None
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL
        assert _leftovers(world.home / ".claude") == []
        assert squatter.read_bytes() == b'{"not": "the original"}\n'

    def test_backup_directory_is_created_private_when_missing(self, writer, world):
        world.backups.rmdir()
        plan = _plan(world, "user")

        result = _write(writer, world, plan)

        assert result.written is True
        assert _mode(world.backups) == 0o700

    def test_missing_target_needs_no_backup(self, writer, world):
        plan = _plan(world, "local", original=None)

        result = _write(writer, world, plan)

        assert result.written is True
        assert result.backup is None
        assert list(world.backups.iterdir()) == []


def _backup_names(scope, days_old):
    names = []
    for index, days in enumerate(days_old):
        moment = NOW - datetime.timedelta(days=days)
        names.append(f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{scope}-{index:08x}.json")
    return names


def _seed(directory, names):
    for name in names:
        (directory / name).write_bytes(b"{}\n")


class TestRetention:
    def test_only_backups_beyond_the_newest_ten_and_older_than_thirty_days_go(
        self, writer, world
    ):
        names = _backup_names("user", range(40, 52))  # 12 backups, all older than 30 days
        _seed(world.backups, names)

        removed = writer.prune_backups("user", str(world.backups), now=NOW)

        assert sorted(removed) == sorted(names[10:])
        assert sorted(p.name for p in world.backups.iterdir()) == sorted(names[:10])

    def test_backups_younger_than_thirty_days_are_kept_beyond_ten(self, writer, world):
        names = _backup_names("user", range(1, 15))  # 14 backups, all within 30 days
        _seed(world.backups, names)

        removed = writer.prune_backups("user", str(world.backups), now=NOW)

        assert removed == []
        assert len(list(world.backups.iterdir())) == 14

    def test_age_and_count_must_both_be_exceeded(self, writer, world):
        recent = _backup_names("project", range(0, 11))  # 11 within 30 days
        old = _backup_names("project", (31, 400))
        _seed(world.backups, recent + old)

        removed = writer.prune_backups("project", str(world.backups), now=NOW)

        assert sorted(removed) == sorted(old)

    def test_the_newest_backup_is_never_pruned(self, writer, world):
        names = _backup_names("local", (900,))
        _seed(world.backups, names)

        assert writer.prune_backups("local", str(world.backups), now=NOW) == []
        assert (world.backups / names[0]).exists()

    def test_other_scopes_and_foreign_names_are_left_alone(self, writer, world):
        mine = _backup_names("user", range(40, 52))
        others = _backup_names("project", range(40, 52))
        foreign = [
            "notes.txt",
            "20200101T000000Z-user-zzzzzzzz.json",
            "20200101T000000Z-user-0000000a.json.bak",
            "x20200101T000000Z-user-0000000a.json",
            "20200101T000000Z-managed-0000000a.json",
            "20200101T000000Z-user-0000000c.json\n",
        ]
        _seed(world.backups, mine + others + foreign)
        directory = world.backups / "20190101T000000Z-user-0000000b.json"
        directory.mkdir()

        removed = writer.prune_backups("user", str(world.backups), now=NOW)

        remaining = {p.name for p in world.backups.iterdir()}
        assert len(removed) == 2
        assert set(others) <= remaining
        assert set(foreign) <= remaining
        assert directory.is_dir()

    def test_unknown_scope_is_rejected(self, writer, world):
        with pytest.raises(ValueError):
            writer.prune_backups("managed", str(world.backups), now=NOW)

    def test_missing_backup_directory_prunes_nothing(self, writer, world):
        assert writer.prune_backups("user", str(world.base / "absent"), now=NOW) == []

    def test_a_successful_write_prunes_its_scope(self, writer, world):
        old = _backup_names("user", range(40, 51))  # 11 old backups
        _seed(world.backups, old)
        plan = _plan(world, "user")

        result = _write(writer, world, plan)

        names = {p.name for p in world.backups.iterdir()}
        assert os.path.basename(result.backup) in names
        assert len(names) == 10
        assert old[-1] not in names and old[-2] not in names


class TestAtomicReplace:
    def test_written_file_holds_the_expected_object(self, writer, world):
        plan = _plan(world, "user")

        result = _write(writer, world, plan)

        assert result == writer.Result(
            scope="user",
            path=plan.path,
            real_path=plan.path,
            written=True,
            backup=result.backup,
            verified=True,
            restored=False,
            refused=False,
            error=None,
            message=None,
        )
        fmt = writer.jsonio.Format(2, "\n", True)
        assert pathlib.Path(plan.path).read_bytes() == writer.jsonio.dumps(EXPECTED, fmt)

    def test_original_layout_is_kept(self, writer, world):
        original = b'{\r\n    "model": "opus"\r\n}'
        plan = _plan(world, "project", original=original)
        fmt = writer.jsonio.Format(4, "\r\n", False)

        _write(writer, world, plan, expected={"model": "opus", "x": 1}, fmt=fmt)

        assert pathlib.Path(plan.path).read_bytes() == (
            b'{\r\n    "model": "opus",\r\n    "x": 1\r\n}')

    def test_temp_file_is_exclusive_in_the_target_directory_never_tmpdir(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "project")
        directory = os.path.dirname(plan.path)

        with _spy_opens(monkeypatch) as calls:
            result = _write(writer, world, plan)

        temps = [(path, flags) for path, flags in _creating(calls)
                 if not path.startswith(str(world.backups))]
        assert result.written is True
        assert len(temps) == 1
        path, flags = temps[0]
        assert os.path.dirname(path) == directory
        assert path != plan.path
        assert flags & os.O_EXCL and flags & os.O_NOFOLLOW
        assert list(world.tmpdir.iterdir()) == []
        assert _leftovers(directory) == []

    def test_target_itself_is_never_opened_for_writing(self, writer, world, monkeypatch):
        plan = _plan(world, "user")

        with _spy_opens(monkeypatch) as calls:
            _write(writer, world, plan)

        for path, flags in calls:
            if path == plan.path:
                assert flags != "builtin"
                assert flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC) == 0

    @pytest.mark.parametrize("mode", [0o640, 0o600, 0o664, 0o444])
    def test_original_mode_is_kept(self, writer, world, mode):
        plan = _plan(world, "project")
        os.chmod(plan.path, mode)

        result = _write(writer, world, plan)

        assert result.written is True
        assert _mode(plan.path) == mode

    @pytest.mark.parametrize("scope, umask, mode", [
        ("user", 0o022, 0o600),
        ("local", 0o000, 0o600),
        ("project", 0o022, 0o644),
        ("project", 0o027, 0o640),
        ("project", 0o077, 0o600),
    ])
    def test_new_file_mode_by_scope(self, writer, world, scope, umask, mode):
        plan = _plan(world, scope, original=None)
        previous = os.umask(umask)
        try:
            result = _write(writer, world, plan)
            active = os.umask(umask)
        finally:
            os.umask(previous)

        assert result.written is True
        assert _mode(plan.path) == mode
        assert active == umask

    def test_missing_target_is_created_with_only_the_approved_keys(self, writer, world):
        plan = _plan(world, "local", original=None)
        approved = {"permissions": {"deny": ["Read(~/.ssh/**)"]}}

        result = _write(writer, world, plan, expected=approved)

        assert result.written is True and result.verified is True
        assert json.loads(pathlib.Path(plan.path).read_bytes()) == approved
        assert _leftovers(world.project / ".claude") == []

    def test_missing_target_gets_the_default_layout_without_a_format(self, writer, world):
        plan = _plan(world, "local", original=None)

        _write(writer, world, plan, expected={"a": {"b": 1}}, fmt=None)

        assert pathlib.Path(plan.path).read_bytes() == b'{\n  "a": {\n    "b": 1\n  }\n}\n'

    def test_missing_user_directory_is_created_private(self, writer, world):
        (world.home / ".claude").rmdir()
        plan = _plan_missing(world, "user")
        previous = os.umask(0)
        try:
            result = _write(writer, world, plan)
        finally:
            os.umask(previous)

        assert result.written is True
        assert _mode(world.home / ".claude") == 0o700
        assert _mode(plan.path) == 0o600

    def test_missing_claude_directory_in_the_project_is_created(self, writer, world):
        (world.project / ".claude").rmdir()
        plan = _plan_missing(world, "project")

        result = _write(writer, world, plan)

        assert result.written is True
        assert (world.project / ".claude").is_dir()
        assert not (world.project / ".claude").is_symlink()

    @pytest.mark.parametrize("scope", ["project", "local"])
    def test_missing_project_directory_is_never_created(self, writer, world, scope):
        (world.project / ".claude").rmdir()
        world.project.rmdir()
        plan = _plan_missing(world, scope)

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "no-directory")
        assert not world.project.exists()

    def test_missing_home_is_never_created(self, writer, world):
        (world.home / ".claude").rmdir()
        world.home.rmdir()
        plan = _plan_missing(world, "user")

        result = _write(writer, world, plan)

        assert (result.refused, result.error) == (True, "no-directory")
        assert not world.home.exists()

    def test_created_directory_is_removed_when_the_write_fails(self, writer, world, monkeypatch):
        (world.project / ".claude").rmdir()
        plan = _plan_missing(world, "project")
        _fail_open_of(monkeypatch, lambda path: path.startswith(str(world.project)), errno.EROFS)

        result = _write(writer, world, plan)

        assert result.error == "sandbox-denied"
        assert not (world.project / ".claude").exists()

    @pytest.mark.parametrize("expected", [["not", "an", "object"], {"x": float("nan")}, None])
    def test_content_that_is_not_a_json_object_is_refused_untouched(
        self, writer, world, monkeypatch, expected
    ):
        plan = _plan(world, "user")

        with _spy_opens(monkeypatch) as calls:
            result = writer.write_target(
                plan, expected, writer.jsonio.Format(2, "\n", True),
                targets=world.targets, backup_dir=str(world.backups),
                managed_roots=(str(world.managed),), now=NOW)

        assert result.error == "invalid-content"
        assert result.written is False
        assert calls == []
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL


def _plan_missing(world, scope):
    return types.SimpleNamespace(scope=scope, path=world.targets[scope].path, pre_sha256=None)


class TestChangedTarget:
    def test_file_differing_from_the_plan_is_not_written(self, writer, world):
        plan = _plan(world, "user")
        pathlib.Path(plan.path).write_bytes(b'{"edited": "after the plan"}\n')

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False and result.backup is None
        assert pathlib.Path(plan.path).read_bytes() == b'{"edited": "after the plan"}\n'
        assert list(world.backups.iterdir()) == []

    def test_existing_file_with_a_plan_that_expected_none_is_not_written(self, writer, world):
        plan = _plan(world, "local")
        plan.pre_sha256 = None

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_missing_file_with_the_hash_of_empty_content_is_not_written(self, writer, world):
        plan = _plan_missing(world, "local")
        plan.pre_sha256 = _sha(b"")

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert not os.path.lexists(plan.path)

    def test_missing_file_with_a_plan_that_expected_one_is_not_written(self, writer, world):
        plan = _plan_missing(world, "local")
        plan.pre_sha256 = _sha(ORIGINAL)

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert not os.path.lexists(plan.path)

    def test_change_between_read_and_replace_aborts(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        intruder = b'{"written": "by someone else"}\n'
        seen = []

        def intrude(path):
            seen.append(path)
            pathlib.Path(path).write_bytes(intruder)

        monkeypatch.setattr(writer, "_before_restat", intrude)

        result = _write(writer, world, plan)

        assert seen == [plan.path]
        assert result.error == "changed"
        assert result.written is False and result.verified is False
        assert pathlib.Path(plan.path).read_bytes() == intruder
        assert _leftovers(world.home / ".claude") == []

    def test_same_bytes_in_a_replaced_file_still_abort(self, writer, world, monkeypatch):
        plan = _plan(world, "user")

        def swap(path):
            os.unlink(path)
            pathlib.Path(path + ".new").write_bytes(ORIGINAL)
            os.rename(path + ".new", path)

        monkeypatch.setattr(writer, "_before_restat", swap)

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_file_appearing_where_none_was_aborts(self, writer, world, monkeypatch):
        plan = _plan_missing(world, "local")
        intruder = b'{"appeared": true}\n'
        monkeypatch.setattr(
            writer, "_before_restat", lambda path: pathlib.Path(path).write_bytes(intruder))

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert pathlib.Path(plan.path).read_bytes() == intruder
        assert _leftovers(world.project / ".claude") == []

    def test_symlink_swapped_in_before_replace_aborts(self, writer, world, monkeypatch):
        plan = _plan(world, "local")
        victim = world.base / "victim"
        victim.write_bytes(ORIGINAL)

        def swap(path):
            os.unlink(path)
            os.symlink(victim, path)

        monkeypatch.setattr(writer, "_before_restat", swap)

        result = _write(writer, world, plan)

        assert result.written is False
        assert result.error == "symlink"
        assert victim.read_bytes() == ORIGINAL

    def test_the_hook_is_not_a_parameter(self, writer):
        parameters = inspect.signature(writer.write_target).parameters

        assert list(parameters) == [
            "target_plan", "expected_obj", "fmt", "targets", "backup_dir", "managed_roots", "now"]
        assert writer._before_restat("/nowhere") is None


class TestFailures:
    @pytest.mark.parametrize("code", [errno.EPERM, errno.EROFS])
    def test_denied_temp_file_says_run_outside_the_sandbox(
        self, writer, world, monkeypatch, code
    ):
        plan = _plan(world, "user")
        _fail_open_of(monkeypatch, lambda path: path.startswith(str(world.home)), code)

        result = _write(writer, world, plan)

        assert result.error == "sandbox-denied"
        assert result.message == "run apply outside the sandbox"
        assert result.written is False
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL
        assert _leftovers(world.home / ".claude") == []

    def test_denied_backup_says_run_outside_the_sandbox(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        _fail_open_of(monkeypatch, lambda path: path.startswith(str(world.backups)), errno.EROFS)

        result = _write(writer, world, plan)

        assert result.error == "sandbox-denied"
        assert result.backup is None
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL
        assert _leftovers(world.home / ".claude") == []

    def test_other_write_errors_are_reported_without_the_sandbox_hint(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "user")
        _fail_open_of(monkeypatch, lambda path: path.startswith(str(world.home)), errno.ENOSPC)

        result = _write(writer, world, plan)

        assert result.error == "write-failed"
        assert "sandbox" not in result.message
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    @pytest.mark.parametrize("code, error", [
        (errno.EXDEV, "replace-failed"),
        (errno.EBUSY, "replace-failed"),
        (errno.EPERM, "sandbox-denied"),
        (errno.EROFS, "sandbox-denied"),
    ])
    def test_failed_replace_is_an_error_never_an_in_place_write(
        self, writer, world, monkeypatch, code, error
    ):
        plan = _plan(world, "project")

        def replace(source, destination, **kwargs):
            raise OSError(code, os.strerror(code))

        monkeypatch.setattr(os, "replace", replace)
        with _spy_opens(monkeypatch) as calls:
            result = _write(writer, world, plan)

        assert result.error == error
        assert result.written is False and result.verified is False
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL
        assert _leftovers(world.project / ".claude") == []
        for path, flags in calls:
            if path == plan.path:
                assert flags != "builtin"
                assert flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC) == 0
        assert pathlib.Path(result.backup).read_bytes() == ORIGINAL

    def test_post_write_mismatch_restores_the_original(self, writer, world, monkeypatch):
        plan = _plan(world, "project")
        os.chmod(plan.path, 0o640)
        monkeypatch.setattr(
            writer, "_parse_strict",
            lambda raw: ("ok", {"something": "else"}, None, None))

        result = _write(writer, world, plan)

        assert result.error == "verify-failed"
        assert (result.written, result.verified, result.restored) == (False, False, True)
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL
        assert _mode(plan.path) == 0o640
        assert pathlib.Path(result.backup).read_bytes() == ORIGINAL
        assert _leftovers(world.project / ".claude") == []

    @pytest.mark.parametrize("reread", [
        ("unreadable", None, None, "invalid-json"),
        ("ok", {"permissions": {"deny": ["Read(~/.ssh/**)"]}, "model": "opus"}, None, None),
        ("absent", None, None, None),
    ])
    def test_unreadable_or_reordered_result_counts_as_a_mismatch(
        self, writer, world, monkeypatch, reread
    ):
        plan = _plan(world, "user")
        monkeypatch.setattr(writer, "_parse_strict", lambda raw: reread)

        result = _write(writer, world, plan)

        assert result.error == "verify-failed"
        assert result.restored is True
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_post_write_mismatch_on_a_new_file_removes_it(self, writer, world, monkeypatch):
        (world.project / ".claude").rmdir()
        plan = _plan_missing(world, "local")
        monkeypatch.setattr(
            writer, "_parse_strict", lambda raw: ("ok", {}, None, None))

        result = _write(writer, world, plan)

        assert result.error == "verify-failed"
        assert (result.written, result.restored, result.backup) == (False, True, None)
        assert not os.path.lexists(plan.path)
        assert not (world.project / ".claude").exists()

    def test_failed_restore_is_reported_with_the_backup(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        monkeypatch.setattr(
            writer, "_parse_strict", lambda raw: ("ok", {}, None, None))
        real_replace = os.replace
        replaced = []

        def replace(source, destination, **kwargs):
            if replaced:
                raise OSError(errno.EBUSY, "busy")
            replaced.append(destination)
            return real_replace(source, destination, **kwargs)

        monkeypatch.setattr(os, "replace", replace)

        result = _write(writer, world, plan)

        assert result.error == "restore-failed"
        assert (result.written, result.verified, result.restored) == (True, False, False)
        assert pathlib.Path(result.backup).read_bytes() == ORIGINAL
        assert _leftovers(world.home / ".claude") == []

    def test_interrupt_after_the_temp_write_leaves_the_original(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "user")
        directory = world.home / ".claude"
        seen = []

        def interrupt(path):
            seen.extend(_leftovers(directory))
            raise KeyboardInterrupt

        monkeypatch.setattr(writer, "_before_restat", interrupt)

        with pytest.raises(KeyboardInterrupt):
            _write(writer, world, plan)

        assert len(seen) == 1  # the temp file existed when the interrupt came
        assert _leftovers(directory) == []
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_interrupt_while_syncing_the_temp_file_removes_it(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "local")
        directory = world.project / ".claude"
        real_fsync = os.fsync
        synced = []

        def fsync(fd):
            synced.append(fd)
            if len(synced) == 2:  # the first sync is the backup's
                raise KeyboardInterrupt
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", fsync)
        monkeypatch.delattr(writer.fcntl, "F_FULLFSYNC", raising=False)

        with pytest.raises(KeyboardInterrupt):
            _write(writer, world, plan)

        assert _leftovers(directory) == []
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_messages_never_carry_file_content_or_paths(self, writer, world, monkeypatch):
        secret = b'{"env": {"TOKEN": "s3cr3t-value"}}\n'
        plan = _plan(world, "user", original=secret)
        monkeypatch.setattr(
            writer, "_parse_strict", lambda raw: ("ok", {}, None, None))

        result = _write(writer, world, plan, expected={"env": {"TOKEN": "s3cr3t-value"}})

        assert result.error == "verify-failed"
        assert result.message == writer.MESSAGES["verify-failed"]
        assert "s3cr3t" not in repr(result)
        for message in writer.MESSAGES.values():
            assert str(world.base) not in message


class TestDurability:
    def test_full_fsync_is_used_where_the_platform_has_it(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        full = []
        plain = []
        real_fsync = os.fsync
        monkeypatch.setattr(writer.fcntl, "F_FULLFSYNC", 51, raising=False)
        monkeypatch.setattr(
            writer.fcntl, "fcntl", lambda fd, command, *args: full.append(command) or 0)
        monkeypatch.setattr(os, "fsync", lambda fd: plain.append(fd) or real_fsync(fd))

        result = _write(writer, world, plan)

        assert result.written is True
        assert full and set(full) == {51}
        assert plain == []

    def test_plain_fsync_when_full_fsync_is_refused(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        plain = []
        real_fsync = os.fsync

        def refuse(fd, command, *args):
            raise OSError(errno.ENOTSUP, "not supported")

        monkeypatch.setattr(writer.fcntl, "F_FULLFSYNC", 51, raising=False)
        monkeypatch.setattr(writer.fcntl, "fcntl", refuse)
        monkeypatch.setattr(os, "fsync", lambda fd: plain.append(fd) or real_fsync(fd))

        result = _write(writer, world, plan)

        assert result.written is True
        assert plain

    def test_temp_file_and_directory_are_synced(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        kinds = []
        real_fsync = os.fsync

        def fsync(fd):
            mode = os.fstat(fd).st_mode
            kinds.append("dir" if stat.S_ISDIR(mode) else "file")
            return real_fsync(fd)

        monkeypatch.delattr(writer.fcntl, "F_FULLFSYNC", raising=False)
        monkeypatch.setattr(os, "fsync", fsync)

        result = _write(writer, world, plan)

        assert result.written is True
        assert kinds == ["file", "file", "dir"]  # backup, temp file, target directory

    def test_directory_sync_failure_does_not_undo_a_written_file(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "user")
        real_fsync = os.fsync

        def fsync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError(errno.EINVAL, "invalid")
            return real_fsync(fd)

        monkeypatch.delattr(writer.fcntl, "F_FULLFSYNC", raising=False)
        monkeypatch.setattr(os, "fsync", fsync)

        result = _write(writer, world, plan)

        assert result.written is True and result.verified is True


def _once_before(monkeypatch, writer, seam, action):
    """Run `action` once, just before the writer's `seam` function runs."""
    original = getattr(writer, seam)
    done = []

    def wrapped(*args, **kwargs):
        if not done:
            done.append(True)
            action()
        return original(*args, **kwargs)

    monkeypatch.setattr(writer, seam, wrapped)


def _swap_for_link(directory, moved, victim):
    """What a racing attacker does: move `directory` away and leave a link to
    `victim` under its name."""
    def swap():
        os.rename(directory, moved)
        os.symlink(victim, directory)
    return swap


class TestDirectoryRace:
    """A directory on the way to the target is replaced by a link after the
    path was resolved and vetted (the review's proof of concept)."""

    @pytest.fixture
    def victim(self, world):
        victim = world.base / "victim"
        victim.mkdir()
        return victim

    @pytest.mark.parametrize("scope", ["project", "local"])
    def test_claude_dir_swapped_before_a_new_file_is_created(
        self, writer, world, monkeypatch, victim, scope
    ):
        plan = _plan_missing(world, scope)
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, "_make_directory",
                     _swap_for_link(world.project / ".claude", moved, victim))

        result = _write(writer, world, plan)

        assert result.error in ("changed", "outside-project")
        assert (result.written, result.verified) == (False, False)
        assert list(victim.iterdir()) == []
        assert list(moved.iterdir()) == []

    @pytest.mark.parametrize("seam", ["_backup", "_make_directory"])
    def test_claude_dir_swapped_while_an_existing_file_is_replaced(
        self, writer, world, monkeypatch, victim, seam
    ):
        plan = _plan(world, "project")
        (victim / "settings.json").write_bytes(ORIGINAL)
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, seam,
                     _swap_for_link(world.project / ".claude", moved, victim))

        result = _write(writer, world, plan)

        assert result.error in ("changed", "outside-project")
        assert result.written is False
        assert sorted(p.name for p in victim.iterdir()) == ["settings.json"]
        assert (victim / "settings.json").read_bytes() == ORIGINAL
        assert (moved / "settings.json").read_bytes() == ORIGINAL
        assert _leftovers(moved) == []

    def test_link_planted_where_the_claude_dir_was_missing(
        self, writer, world, monkeypatch, victim
    ):
        claude_dir = world.project / ".claude"
        claude_dir.rmdir()
        plan = _plan_missing(world, "project")
        _once_before(monkeypatch, writer, "_make_directory",
                     lambda: os.symlink(victim, claude_dir))

        result = _write(writer, world, plan)

        assert result.error in ("changed", "outside-project")
        assert result.written is False
        assert list(victim.iterdir()) == []
        assert claude_dir.is_symlink()

    def test_directory_moved_away_without_a_link_is_not_written_either(
        self, writer, world, monkeypatch
    ):
        plan = _plan_missing(world, "local")
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, "_make_directory",
                     lambda: os.rename(world.project / ".claude", moved))

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list(moved.iterdir()) == []
        assert not (world.project / ".claude").exists()

    def test_user_scope_parent_swapped_before_a_new_file_is_created(
        self, writer, world, monkeypatch, victim
    ):
        config = world.base / "cfg" / "claude"
        config.mkdir(parents=True)
        (victim / "claude").mkdir()
        world.targets = writer.allowed_targets(
            str(world.home), str(config), str(world.project), str(world.project))
        plan = _plan_missing(world, "user")
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, "_make_directory",
                     _swap_for_link(world.base / "cfg", moved, victim))

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list((victim / "claude").iterdir()) == []
        assert list((moved / "claude").iterdir()) == []

    def test_user_scope_parent_swapped_before_the_directory_is_created(
        self, writer, world, monkeypatch, victim
    ):
        parent = world.base / "cfg"
        parent.mkdir()
        world.targets = writer.allowed_targets(
            str(world.home), str(parent / "claude"), str(world.project), str(world.project))
        plan = _plan_missing(world, "user")
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, "_make_directory",
                     _swap_for_link(parent, moved, victim))

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list(victim.iterdir()) == []
        assert list(moved.iterdir()) == []

    def test_claude_dir_swapped_before_it_is_opened(self, writer, world, monkeypatch, victim):
        plan = _plan_missing(world, "project")
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, "_hold",
                     _swap_for_link(world.project / ".claude", moved, victim))

        result = _write(writer, world, plan)

        assert result.error in ("changed", "outside-project")
        assert result.written is False
        assert list(victim.iterdir()) == []
        assert list(moved.iterdir()) == []

    def test_path_that_now_leads_to_another_directory_is_not_written(
        self, writer, world, monkeypatch
    ):
        plan = _plan_missing(world, "project")
        claude_dir = world.project / ".claude"
        moved = world.base / "moved"

        def replace_directory():
            os.rename(claude_dir, moved)
            claude_dir.mkdir()

        _once_before(monkeypatch, writer, "_make_directory", replace_directory)

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list(claude_dir.iterdir()) == []
        assert list(moved.iterdir()) == []

    def test_directory_appearing_where_the_claude_dir_was_missing_is_not_used(
        self, writer, world, monkeypatch
    ):
        claude_dir = world.project / ".claude"
        claude_dir.rmdir()
        plan = _plan_missing(world, "project")
        _once_before(monkeypatch, writer, "_make_directory", claude_dir.mkdir)

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list(claude_dir.iterdir()) == []

    def test_new_claude_dir_swapped_for_a_link_right_after_it_is_made(
        self, writer, world, monkeypatch, victim
    ):
        claude_dir = world.project / ".claude"
        claude_dir.rmdir()
        plan = _plan_missing(world, "project")
        real_mkdir = os.mkdir

        def mkdir(path, mode=0o777, *, dir_fd=None):
            real_mkdir(path, mode, dir_fd=dir_fd)
            if dir_fd is not None and os.fspath(path) == ".claude":
                claude_dir.rmdir()
                claude_dir.symlink_to(victim)

        monkeypatch.setattr(os, "mkdir", mkdir)
        with _spy_opens(monkeypatch) as calls:
            result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list(victim.iterdir()) == []
        assert [path for path, _ in _creating(calls)] == []

    def test_user_scope_parent_swapped_before_the_directory_is_opened(
        self, writer, world, monkeypatch, victim
    ):
        config = world.base / "cfg" / "claude"
        config.mkdir(parents=True)
        (victim / "claude").mkdir()
        world.targets = writer.allowed_targets(
            str(world.home), str(config), str(world.project), str(world.project))
        plan = _plan_missing(world, "user")
        moved = world.base / "moved"
        _once_before(monkeypatch, writer, "_hold",
                     _swap_for_link(world.base / "cfg", moved, victim))

        result = _write(writer, world, plan)

        assert result.error == "changed"
        assert result.written is False
        assert list((victim / "claude").iterdir()) == []
        assert list((moved / "claude").iterdir()) == []

    def test_user_directory_replaced_between_open_and_check_is_not_written(
        self, writer, world, monkeypatch
    ):
        plan = _plan_missing(world, "user")
        directory = world.home / ".claude"
        moved = world.base / "moved"
        armed = []
        _once_before(monkeypatch, writer, "_hold", lambda: armed.append(True))
        real_realpath = os.path.realpath

        def realpath(path, *args, **kwargs):
            if armed and os.fspath(path) == str(directory):
                armed.clear()
                os.rename(directory, moved)
                directory.mkdir()
            return real_realpath(path, *args, **kwargs)

        monkeypatch.setattr(os.path, "realpath", realpath)

        result = _write(writer, world, plan)

        assert armed == []
        assert result.error == "changed"
        assert result.written is False
        assert list(directory.iterdir()) == []
        assert list(moved.iterdir()) == []

    def test_every_step_after_resolution_goes_through_the_directory_descriptor(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "project")
        by_path = []
        real_os_open = os.open

        def os_open(path, flags, mode=0o777, *, dir_fd=None):
            if dir_fd is None and not flags & getattr(os, "O_DIRECTORY", 0):
                by_path.append(os.fspath(path))
            return real_os_open(path, flags, mode, dir_fd=dir_fd)

        renames = []
        real_replace = os.replace

        def replace(source, destination, *, src_dir_fd=None, dst_dir_fd=None):
            renames.append((source, destination, src_dir_fd is not None,
                            src_dir_fd == dst_dir_fd))
            return real_replace(
                source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

        monkeypatch.setattr(os, "open", os_open)
        monkeypatch.setattr(os, "replace", replace)

        result = _write(writer, world, plan)

        assert result.written is True and result.verified is True
        assert by_path == []
        assert len(renames) == 1
        source, destination, relative, same_directory = renames[0]
        assert (destination, relative, same_directory) == ("settings.json", True, True)
        assert os.sep not in source


class TestFingerprint:
    """The re-read before the replace compares the file's identity and
    metadata, not only its bytes."""

    def test_same_bytes_and_times_in_a_new_inode_abort(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        before = os.stat(plan.path)

        def swap(path):
            twin = path + ".twin"
            pathlib.Path(twin).write_bytes(ORIGINAL)
            os.chmod(twin, stat.S_IMODE(before.st_mode))
            os.utime(twin, ns=(before.st_atime_ns, before.st_mtime_ns))
            os.rename(twin, path)

        monkeypatch.setattr(writer, "_before_restat", swap)

        result = _write(writer, world, plan)

        after = os.stat(plan.path)
        assert (after.st_mtime_ns, after.st_size, after.st_mode, after.st_uid) == (
            before.st_mtime_ns, before.st_size, before.st_mode, before.st_uid)
        assert after.st_ino != before.st_ino
        assert result.error == "changed"
        assert result.written is False
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_new_modification_time_on_the_same_bytes_aborts(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        before = os.stat(plan.path)

        def touch(path):
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))

        monkeypatch.setattr(writer, "_before_restat", touch)

        result = _write(writer, world, plan)

        assert os.stat(plan.path).st_ino == before.st_ino
        assert result.error == "changed"
        assert result.written is False
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_new_mode_on_the_same_bytes_aborts(self, writer, world, monkeypatch):
        plan = _plan(world, "user")
        os.chmod(plan.path, 0o600)
        before = os.stat(plan.path)
        monkeypatch.setattr(writer, "_before_restat", lambda path: os.chmod(path, 0o640))

        result = _write(writer, world, plan)

        after = os.stat(plan.path)
        assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
        assert result.error == "changed"
        assert result.written is False
        assert _mode(plan.path) == 0o640


class TestAfterReplace:
    def test_interrupt_right_after_the_replace_is_recorded_as_written(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "user")
        progress = []
        real_apply = writer._apply

        def apply(*args):
            progress.append(args[-1])
            return real_apply(*args)

        def interrupt(*_args):
            raise KeyboardInterrupt

        monkeypatch.setattr(writer, "_apply", apply)
        monkeypatch.setattr(writer, "_fsync_directory", interrupt)

        with pytest.raises(KeyboardInterrupt):
            _write(writer, world, plan)

        assert json.loads(pathlib.Path(plan.path).read_bytes()) == EXPECTED
        assert progress[0].written is True
        assert progress[0].backup is not None
        assert _leftovers(world.home / ".claude") == []

    def test_restore_does_not_clobber_a_file_changed_after_the_write(
        self, writer, world, monkeypatch
    ):
        plan = _plan(world, "user")
        intruder = b'{"written": "by someone else"}\n'

        def mismatch(*_args):
            pathlib.Path(plan.path).write_bytes(intruder)
            return False

        monkeypatch.setattr(writer, "_matches", mismatch)

        result = _write(writer, world, plan)

        assert result.error == "restore-failed"
        assert (result.written, result.verified, result.restored) == (True, False, False)
        assert pathlib.Path(plan.path).read_bytes() == intruder
        assert pathlib.Path(result.backup).read_bytes() == ORIGINAL
        assert _leftovers(world.home / ".claude") == []

    def test_restore_does_not_remove_a_new_file_changed_after_the_write(
        self, writer, world, monkeypatch
    ):
        plan = _plan_missing(world, "local")
        intruder = b'{"written": "by someone else"}\n'

        def mismatch(*_args):
            pathlib.Path(plan.path).write_bytes(intruder)
            return False

        monkeypatch.setattr(writer, "_matches", mismatch)

        result = _write(writer, world, plan)

        assert result.error == "restore-failed"
        assert (result.written, result.restored, result.backup) == (True, False, None)
        assert pathlib.Path(plan.path).read_bytes() == intruder


class TestBackupDirectory:
    def test_backup_directory_that_is_a_link_is_refused(self, writer, world):
        elsewhere = world.base / "elsewhere"
        elsewhere.mkdir()
        world.backups.rmdir()
        world.backups.symlink_to(elsewhere)
        plan = _plan(world, "user")

        result = _write(writer, world, plan)

        assert result.error == "backup-failed"
        assert result.written is False and result.backup is None
        assert list(elsewhere.iterdir()) == []
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL
        assert _leftovers(world.home / ".claude") == []

    def test_backup_directory_open_to_others_is_tightened(self, writer, world):
        os.chmod(world.backups, 0o755)
        plan = _plan(world, "user")

        result = _write(writer, world, plan)

        assert result.written is True
        assert _mode(world.backups) == 0o700
        assert _mode(result.backup) == 0o600

    def test_backup_directory_of_another_user_is_refused(self, writer, world, monkeypatch):
        os.chmod(world.backups, 0o755)
        plan = _plan(world, "user")
        inode = os.stat(world.backups).st_ino
        real_fstat = os.fstat

        def fstat(fd):
            status = real_fstat(fd)
            if status.st_ino != inode:
                return status
            fields = list(status)
            fields[4] = status.st_uid + 1  # st_uid
            return os.stat_result(fields)

        monkeypatch.setattr(os, "fstat", fstat)

        result = _write(writer, world, plan)

        assert result.error == "backup-failed"
        assert result.written is False and result.backup is None
        assert list(world.backups.iterdir()) == []
        assert _mode(world.backups) == 0o755
        assert pathlib.Path(plan.path).read_bytes() == ORIGINAL

    def test_backup_stays_readable_by_its_owner_under_a_strict_umask(self, writer, world):
        plan = _plan(world, "user")
        previous = os.umask(0o277)
        try:
            result = _write(writer, world, plan)
        finally:
            os.umask(previous)

        assert result.written is True
        assert _mode(result.backup) == 0o600
