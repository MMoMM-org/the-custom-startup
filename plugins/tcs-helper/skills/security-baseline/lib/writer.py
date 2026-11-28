"""The settings writer (spec 025, K14, ADR-3).

The only code in the skill that writes a settings file. It accepts three
targets, all computed here: the user `settings.json`, the project
`settings.json` and the local `settings.local.json`. Any other path is
refused before the file system is touched, and a target that resolves into a
managed root is refused as well.

A write keeps a verified private backup, goes through a temp file in the
target's own directory and one `os.replace`, and is read back afterwards; a
result that does not match the planned object is undone. No path leads to an
in-place write. The caller holds the state lock and passes the backup
directory; this module knows nothing else about where state lives.

Paths are resolved and vetted once. From then on the target's directory is
held open and every step (read, temp file, rename, re-read, restore, sync)
names the file relative to that descriptor, so a directory swapped for a link
after the check cannot redirect the write. Just before the rename the path is
walked again and must still lead to the directory held open.

`Result.error` is a code from `MESSAGES`. Messages are fixed texts: no file
content and no path ever enters one.
"""

from __future__ import annotations

import contextlib
import datetime
import errno
import hashlib
import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from typing import Optional

try:
    import fcntl
except ImportError:  # Windows: plan and apply never run there
    fcntl = None

import jsonio
import layers

SCOPES = ("user", "project", "local")
MANAGED_ROOTS = tuple(layers.SYSTEM_ROOTS.values())
DEFAULT_FORMAT = jsonio.Format(2, "\n", True)
KEEP_NEWEST = 10
KEEP_DAYS = 30

MESSAGES = {
    "not-a-target": "not a settings file this tool writes",
    "managed": "managed settings are never written",
    "outside-project": "the settings path resolves outside the project",
    "symlink": "the settings file is a symbolic link this tool does not follow",
    "not-regular": "the target is not a regular file",
    "foreign-owner": "the target belongs to another user",
    "placeholder": "remove the placeholder (`claude doctor` lists them)",
    "too-large": "the target is too large to be a settings file",
    "no-directory": "the directory that should hold the settings file is missing",
    "invalid-content": "the planned content is not a JSON object",
    "changed": "the file changed after it was reviewed; nothing was written",
    "read-failed": "the target could not be read; nothing was written",
    "backup-failed": "no verified backup could be made; nothing was written",
    "sandbox-denied": "run apply outside the sandbox",
    "write-failed": "the new file could not be written; the original is intact",
    "replace-failed": "the file could not be replaced; the original is intact",
    "verify-failed": "the written file did not match the plan; the original was restored",
    "restore-failed": "the written file did not match the plan and could not be restored; "
                      "restore it from the backup",
}

_REFUSALS = frozenset({
    "not-a-target", "managed", "outside-project", "symlink", "not-regular",
    "foreign-owner", "placeholder", "too-large", "no-directory",
})
_SANDBOX_ERRNOS = (errno.EPERM, errno.EROFS)
_TIMESTAMP = "%Y%m%dT%H%M%SZ"
_BACKUP_NAME = re.compile(r"^(\d{8}T\d{6}Z)-(user|project|local)-[0-9a-f]{8}\.json\Z")
_NEW_FILE = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
_READ_ONLY = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
_MOVED_ERRNOS = (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EMLINK)
_READ_CHUNK = 65536


@dataclass(frozen=True)
class Target:
    """One file the writer accepts. `root` is the directory a project or
    local file must stay inside; None for the user file."""

    scope: str
    path: str
    root: Optional[str]


@dataclass(frozen=True)
class Result:
    """Outcome for one target. `backup` is set once a backup is verified,
    also when the write then failed."""

    scope: str
    path: str
    real_path: Optional[str]
    written: bool
    backup: Optional[str]
    verified: bool
    restored: bool
    refused: bool
    error: Optional[str]
    message: Optional[str]


class _Stop(Exception):
    """Ends a write with an error code from `MESSAGES`."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _Place:
    """Where a target really is. `real` is the file read and replaced,
    `directory` holds it and the temp file, `root` is the resolved directory
    a project or local file must stay inside (None for the user file) and
    `missing_directory_mode` is set when `directory` has to be created."""

    real: str
    directory: str
    root: Optional[str]
    missing_directory_mode: Optional[int]


@dataclass
class _Held:
    """The descriptors one write works through. `fd` is the target's
    directory, None until it exists; `parent_fd` is set instead when that
    directory has to be created. `name` is the target's name inside `fd`."""

    place: _Place
    name: str
    fd: Optional[int] = None
    parent_fd: Optional[int] = None


@dataclass
class _Progress:
    real_path: Optional[str] = None
    backup: Optional[str] = None
    written: bool = False
    restored: bool = False


def allowed_targets(home, config_dir, project_dir, repo_root):
    """Return `{scope: Target}` for the three files that may be written.

    `config_dir` is the value of `CLAUDE_CONFIG_DIR` or None. The local file
    lives at the repository root, else in the project directory.
    """
    user_dir = config_dir or os.path.join(home, ".claude")
    local_root = repo_root or project_dir
    return {
        "user": Target("user", _absolute(user_dir, "settings.json"), None),
        "project": Target(
            "project",
            _absolute(project_dir, ".claude", "settings.json"),
            os.path.abspath(project_dir),
        ),
        "local": Target(
            "local",
            _absolute(local_root, ".claude", "settings.local.json"),
            os.path.abspath(local_root),
        ),
    }


def refusal(scope, path, *, targets, managed_roots=None):
    """Return the code for why `path` cannot be written, None when it can.

    Read-only and opens no file: the planner uses it to mark a target
    refused. `write_target` repeats every test.
    """
    try:
        _place(_accepted(scope, path, targets), _roots(managed_roots))
    except _Stop as stop:
        return stop.code
    return None


def write_target(target_plan, expected_obj, fmt, *, targets, backup_dir,
                 managed_roots=None, now=None):
    """Replace one settings file with `expected_obj`, laid out as `fmt`.

    `target_plan` supplies `scope`, `path` and `pre_sha256` (the SHA-256 of
    the file the plan was made from, None for a missing file). `targets` is
    the result of `allowed_targets`; `backup_dir` is the private directory
    for backups. `fmt` None means the default layout, for a new file.
    """
    scope = getattr(target_plan, "scope", None)
    path = getattr(target_plan, "path", None)
    progress = _Progress()
    try:
        target = _accepted(scope, path, targets)
        _apply(
            target,
            _serialise(expected_obj, fmt),
            expected_obj,
            getattr(target_plan, "pre_sha256", None),
            backup_dir,
            _roots(managed_roots),
            now or datetime.datetime.now(datetime.timezone.utc),
            progress,
        )
    except _Stop as stop:
        return _result(scope, path, progress, stop.code)
    return _result(scope, path, progress, None)


def prune_backups(scope, backup_dir, now=None):
    """Delete this scope's old backups and return the removed names.

    A backup goes only when it is both outside the newest `KEEP_NEWEST` and
    older than `KEEP_DAYS`, so the newest always stays. Names that are not
    this module's backup names, and anything that is not a regular file, are
    left alone.
    """
    if scope not in SCOPES:
        raise ValueError("unknown scope")
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = (now - datetime.timedelta(days=KEEP_DAYS)).strftime(_TIMESTAMP)
    try:
        names = os.listdir(backup_dir)
    except OSError:
        return []
    mine = sorted((name for name in names if _backup_scope(name) == scope), reverse=True)
    removed = []
    for name in mine[KEEP_NEWEST:]:
        if _backup_stamp(name) >= cutoff:
            continue
        path = os.path.join(backup_dir, name)
        try:
            if not stat.S_ISREG(os.lstat(path).st_mode):
                continue
            os.unlink(path)
        except OSError:
            continue
        removed.append(name)
    return removed


def _before_restat(_real_path):
    """Test seam: runs after the temp file is complete, before the target is
    read again. Not reachable from any argument."""


def _apply(target, new_bytes, expected_obj, pre_sha256, backup_dir, managed_roots, now, progress):
    place = _place(target, managed_roots)
    progress.real_path = place.real
    with _hold(place) as held:
        original = _read(held)
        _require_reviewed(original, pre_sha256)
        if original is None:
            mode = _new_file_mode(target.scope)
        else:
            mode = stat.S_IMODE(original[1].st_mode)
            progress.backup = _backup(original[0], target.scope, backup_dir, now)
        made_directory = _make_directory(held)
        try:
            _replace_and_verify(held, new_bytes, expected_obj, original, mode, progress)
        finally:
            if made_directory and not progress.written:
                _quietly(os.rmdir, os.path.basename(place.directory), dir_fd=held.parent_fd)
    try:
        prune_backups(target.scope, backup_dir, now)
    except OSError:
        pass


def _replace_and_verify(held, new_bytes, expected_obj, original, mode, progress):
    fingerprint = _fingerprint(original)

    def still_as_read():
        _before_restat(held.place.real)
        _require_in_place(held)
        if _fingerprint(_read(held)) != fingerprint:
            raise _Stop("changed")

    def replaced():
        # Set here, not after the call returns: an interrupt between the
        # rename and the verification must not leave a new file unrecorded.
        progress.written = True

    written = _atomic_replace(held, new_bytes, mode, still_as_read, replaced)
    if _matches(held, expected_obj):
        return
    progress.restored = _restore(held, original, mode, written)
    progress.written = not progress.restored
    raise _Stop("verify-failed" if progress.restored else "restore-failed")


def _accepted(scope, path, targets):
    """The `Target` for `scope` when `path` is exactly its computed path."""
    if not isinstance(scope, str) or not isinstance(path, str) or scope not in SCOPES:
        raise _Stop("not-a-target")
    target = targets.get(scope)
    if target is None or os.path.abspath(path) != target.path:
        raise _Stop("not-a-target")
    return target


def _place(target, managed_roots):
    """Resolve a target and apply the symlink, containment and file-type
    rules using `lstat` and path resolution only."""
    place = _user_place(target) if target.root is None else _repo_place(target)
    for root in managed_roots:
        if _within(place.real, os.path.realpath(root)):
            raise _Stop("managed")
    try:
        _vet(os.lstat(place.real))
    except FileNotFoundError:
        pass
    except OSError:
        raise _Stop("not-regular") from None
    return place


def _user_place(target):
    """Follow links to the real file and write beside it, so a link into a
    dotfiles checkout stays a link."""
    real = os.path.realpath(target.path)
    if os.path.lexists(target.path) and not os.path.exists(real):
        raise _Stop("symlink")  # dangling: there is no regular file to follow to
    directory = os.path.dirname(real)
    if os.path.isdir(directory):
        return _Place(real, directory, None, None)
    config_dir = os.path.dirname(target.path)
    if os.path.lexists(config_dir) or not os.path.isdir(os.path.dirname(directory)):
        raise _Stop("no-directory")
    return _Place(real, directory, None, 0o700)


def _repo_place(target):
    """A project or local file: its `.claude` must resolve inside the root,
    and the file itself is never followed."""
    root = os.path.realpath(target.root)
    if not os.path.isdir(root):
        raise _Stop("no-directory")
    claude_dir = os.path.dirname(target.path)
    directory = os.path.realpath(claude_dir)
    if not _within(directory, root):
        raise _Stop("outside-project")
    real = os.path.join(directory, os.path.basename(target.path))
    if os.path.isdir(directory):
        return _Place(real, directory, root, None)
    if os.path.lexists(claude_dir):
        raise _Stop("no-directory")  # a dangling link or a file named .claude
    return _Place(real, directory, root, 0o777)


@contextlib.contextmanager
def _hold(place):
    """Open the target's directory, or its parent when the directory is still
    to be created, and keep it open for the whole write."""
    held = _Held(place, os.path.basename(place.real))
    try:
        if place.missing_directory_mode is None:
            held.fd = _open_resolved(place.directory, place.root)
        else:
            held.parent_fd = _open_resolved(os.path.dirname(place.directory), place.root)
        yield held
    finally:
        for fd in (held.fd, held.parent_fd):
            if fd is not None:
                _quietly(os.close, fd)


def _open_resolved(directory, root):
    """Open `directory`, a path `_place` resolved, without following a link
    that has appeared in it since.

    Below `root` (project and local) every component is opened in turn with
    `O_NOFOLLOW`, relative to the one before, so the descriptor cannot be
    outside the root whatever is swapped meanwhile. Without a root (user)
    the path belongs to the user, not to a cloned repository: it is opened
    with `O_NOFOLLOW` and then checked against a fresh resolution.
    """
    try:
        if root is None:
            return _open_verified(directory)
        return _descend(_open_verified(root), os.path.relpath(directory, root))
    except OSError as exc:
        raise _Stop("changed" if exc.errno in _MOVED_ERRNOS else "read-failed") from None


def _open_verified(directory):
    """Open a resolved path; it must still resolve to itself and be the
    directory that was opened. `O_NOFOLLOW` alone covers the last component
    only."""
    fd = os.open(directory, _DIRECTORY)
    try:
        still_resolved = os.path.realpath(directory) == directory
        if not still_resolved or not os.path.samestat(os.fstat(fd), os.lstat(directory)):
            raise _Stop("changed")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _descend(fd, relative):
    """Walk `relative` down from the open directory `fd`, which this call
    closes, and return the last directory opened."""
    for part in relative.split(os.sep):
        if part == os.curdir:
            continue
        try:
            if part == os.pardir:
                raise _Stop("outside-project")
            below = os.open(part, _DIRECTORY, dir_fd=fd)
        finally:
            os.close(fd)
        fd = below
    return fd


def _require_in_place(held):
    """The path must still lead to the directory held open. A directory that
    was moved away, or replaced by a link, since it was opened would
    otherwise be written to under a path that now means something else."""
    fd = _open_resolved(held.place.directory, held.place.root)
    try:
        same = os.path.samestat(os.fstat(fd), os.fstat(held.fd))
    except OSError:
        same = False
    finally:
        os.close(fd)
    if not same:
        raise _Stop("changed")


def _vet(status):
    """Refuse what must not be replaced: links, non-files, foreign files and
    the empty read-only placeholders a killed sandbox leaves behind."""
    if stat.S_ISLNK(status.st_mode):
        raise _Stop("symlink")
    if not stat.S_ISREG(status.st_mode):
        raise _Stop("not-regular")
    if status.st_uid != os.geteuid():
        raise _Stop("foreign-owner")
    if status.st_size == 0 and not status.st_mode & 0o222:
        raise _Stop("placeholder")
    if status.st_size > jsonio.MAX_BYTES:
        raise _Stop("too-large")


def _read(held):
    """Return `(bytes, stat)` for the target, None when it does not exist."""
    if held.fd is None:
        return None
    try:
        fd = os.open(held.name, _READ_ONLY, dir_fd=held.fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise _Stop("symlink") from None
        raise _Stop("read-failed") from None
    try:
        status = os.fstat(fd)
        _vet(status)
        raw = _read_up_to(fd, jsonio.MAX_BYTES + 1)
    except OSError:
        raise _Stop("read-failed") from None
    finally:
        os.close(fd)
    if len(raw) > jsonio.MAX_BYTES:
        raise _Stop("too-large")
    return raw, status


def _require_reviewed(original, pre_sha256):
    """The file must still be the one the plan was computed from.

    A missing target is reviewed only as ``pre_sha256 is None``; any hash,
    including that of empty content, means the plan saw a file that is gone.
    """
    if original is None:
        if pre_sha256 is not None:
            raise _Stop("changed")
    elif pre_sha256 != _sha256(original[0]):
        raise _Stop("changed")


def _fingerprint(original):
    if original is None:
        return None
    raw, status = original
    return (
        _sha256(raw), status.st_dev, status.st_ino, status.st_size,
        status.st_mtime_ns, status.st_mode, status.st_uid,
    )


def _serialise(expected_obj, fmt):
    if not isinstance(expected_obj, dict):
        raise _Stop("invalid-content")
    try:
        return jsonio.dumps(expected_obj, fmt or DEFAULT_FORMAT)
    except (TypeError, ValueError, RecursionError):
        raise _Stop("invalid-content") from None


def _backup(raw, scope, backup_dir, now):
    """Write `raw` to a new private backup and return its path once it has
    been read back equal. An equal backup of the same second is reused."""
    name = f"{now.strftime(_TIMESTAMP)}-{scope}-{_sha256(raw)[:8]}.json"
    try:
        directory = _private_directory(backup_dir)
    except OSError as exc:
        raise _Stop(_code_for(exc, "backup-failed")) from None
    try:
        _write_backup(directory, name, raw)
    finally:
        os.close(directory)
    return os.path.join(backup_dir, name)


def _private_directory(path):
    """Open the backup directory itself, never a link to one, creating it
    0700 when it is missing. One that others can enter is tightened to 0700;
    one that belongs to another user is refused."""
    try:
        fd = os.open(path, _DIRECTORY)
    except FileNotFoundError:
        os.mkdir(path, 0o700)
        fd = os.open(path, _DIRECTORY)
    try:
        status = os.fstat(fd)
        if status.st_uid != os.geteuid():
            raise _Stop("backup-failed")
        if stat.S_IMODE(status.st_mode) & 0o077:
            os.fchmod(fd, 0o700)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _write_backup(directory, name, raw):
    created = False
    try:
        try:
            fd = os.open(name, _NEW_FILE, 0o600, dir_fd=directory)
        except FileExistsError:
            pass
        else:
            created = True
            try:
                # Not a privacy guard: a umask only clears bits, so the open
                # mode never yields more than 0600. This puts back owner bits
                # a strict umask (0277) removed, so the copy is exactly 0600.
                os.fchmod(fd, 0o600)
                _write_all(fd, raw)
                _fsync(fd)
            finally:
                os.close(fd)
        if not _is_private_copy(directory, name, raw):
            raise _Stop("backup-failed")
    except OSError as exc:
        if created:
            _quietly(os.unlink, name, dir_fd=directory)
        raise _Stop(_code_for(exc, "backup-failed")) from None
    except BaseException:
        if created:
            _quietly(os.unlink, name, dir_fd=directory)
        raise


def _is_private_copy(directory, name, raw):
    fd = os.open(name, _READ_ONLY, dir_fd=directory)
    try:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode) or stat.S_IMODE(status.st_mode) & 0o077:
            return False
        if status.st_uid != os.geteuid():
            return False
        return _read_up_to(fd, len(raw) + 1) == raw
    finally:
        os.close(fd)


def _make_directory(held):
    """Create the one missing directory level inside its open parent and
    open it without following a link; True when it was created."""
    if held.fd is not None:
        return False
    name = os.path.basename(held.place.directory)
    try:
        os.mkdir(name, held.place.missing_directory_mode, dir_fd=held.parent_fd)
    except FileExistsError:
        raise _Stop("changed") from None  # something appeared since `_place` looked
    except OSError as exc:
        raise _Stop(_code_for(exc, "write-failed")) from None
    try:
        held.fd = os.open(name, _DIRECTORY, dir_fd=held.parent_fd)
    except OSError:
        _quietly(os.rmdir, name, dir_fd=held.parent_fd)
        raise _Stop("changed") from None
    return True


def _atomic_replace(held, data, mode, before_replace, replaced):
    """Write `data` to a temp file beside the target and rename it over the
    target; `replaced` runs as soon as the rename has happened. The temp file
    never outlives this call, whatever ends it. Returns the fingerprint of
    the file now in place."""
    name = f".{held.name}.{secrets.token_hex(8)}.tmp"
    pending = False
    try:
        try:
            fd = os.open(name, _NEW_FILE, 0o600, dir_fd=held.fd)
            pending = True
            try:
                os.fchmod(fd, mode)
                _write_all(fd, data)
                _fsync(fd)
                written = _fingerprint((data, os.fstat(fd)))
            finally:
                os.close(fd)
        except OSError as exc:
            raise _Stop(_code_for(exc, "write-failed")) from None
        before_replace()
        try:
            os.replace(name, held.name, src_dir_fd=held.fd, dst_dir_fd=held.fd)
        except OSError as exc:
            raise _Stop(_code_for(exc, "replace-failed")) from None
        replaced()
        pending = False
    finally:
        if pending:
            _quietly(os.unlink, name, dir_fd=held.fd)
    _fsync_directory(held.fd)
    return written


def _matches(held, expected_obj):
    """True when the file reads back, strictly, as the planned object with
    every key in the planned order."""
    try:
        reread = _read(held)
    except _Stop:
        return False
    if reread is None:
        return False
    status, data, _fmt, _reason = _parse_strict(reread[0])
    return status == "ok" and _ordered(data) == _ordered(expected_obj)


def _parse_strict(raw):
    """jsonio's strict parse, applied to bytes read through the directory
    descriptor, so the target is not opened by name again."""
    return jsonio.parse(raw)


def _ordered(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)


def _restore(held, original, mode, written):
    """Put back what was there before, through the same atomic path. The
    bytes are the ones the backup was verified against. A file that is no
    longer the one this write put there (`written` is its fingerprint) was
    changed by someone else and is left alone."""
    try:
        if _fingerprint(_read(held)) != written:
            return False
        if original is None:
            os.unlink(held.name, dir_fd=held.fd)
        else:
            _atomic_replace(held, original[0], mode, _nothing, _nothing)
    except (OSError, _Stop):
        return False
    return True


def _nothing():
    pass


def _new_file_mode(scope):
    if scope == "project":
        return 0o644 & ~_umask()
    return 0o600


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def _fsync(fd):
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        try:
            fcntl.fcntl(fd, full)
            return
        except OSError:
            pass
    os.fsync(fd)


def _fsync_directory(fd):
    """Best effort: the rename already happened, and some file systems
    refuse to sync a directory."""
    try:
        _fsync(fd)
    except OSError:
        pass


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def _read_up_to(fd, limit):
    chunks = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(fd, min(_READ_CHUNK, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _code_for(exc, fallback):
    """EPERM and EROFS are read as "the sandbox denied this". That is a
    heuristic: an immutable file (`chattr +i`, `chflags uchg`), a sticky
    directory or a read-only mount gives the same errno outside a sandbox."""
    return "sandbox-denied" if exc.errno in _SANDBOX_ERRNOS else fallback


def _result(scope, path, progress, code):
    return Result(
        scope=scope if isinstance(scope, str) else "",
        path=path if isinstance(path, str) else "",
        real_path=progress.real_path,
        written=progress.written,
        backup=progress.backup,
        verified=code is None,
        restored=progress.restored,
        refused=code in _REFUSALS,
        error=code,
        message=None if code is None else MESSAGES[code],
    )


def _roots(managed_roots):
    return MANAGED_ROOTS if managed_roots is None else tuple(managed_roots)


def _absolute(*parts):
    return os.path.abspath(os.path.join(*parts))


def _within(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _backup_scope(name):
    match = _BACKUP_NAME.match(name)
    return match.group(2) if match else None


def _backup_stamp(name):
    return _BACKUP_NAME.match(name).group(1)


def _quietly(action, *args, **kwargs):
    try:
        action(*args, **kwargs)
    except OSError:
        pass
