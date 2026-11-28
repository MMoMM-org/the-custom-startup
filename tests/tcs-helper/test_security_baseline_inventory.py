"""Plugin inventory of the security-baseline skill (spec 025, T2.4, K7, ADR-9).

`scan(home, repo_root)` walks the plugin trees and the two `.claude/skills`
directories. Every test builds its own home and repository under `tmp_path`;
the real `$HOME` and the real plugin cache are never read.
"""

from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import threading

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"
REAL_TEMPLATE = (
    REPO_ROOT / "plugins" / "tcs-git-helpers" / "templates" / "claude-settings" / "sandbox-git.json"
)
TEMPLATE_REL = pathlib.Path("templates") / "claude-settings" / "sandbox-git.json"
_ABSENT = object()


def _load(name, filename):
    """Register before executing: dataclasses resolves string annotations
    through `sys.modules` while the class body runs (Python 3.11)."""
    spec = importlib.util.spec_from_file_location(name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def inventory():
    """`inventory.py` imports `jsonio` by its bare name, the way it resolves
    once `cli.py` has put the lib directory on `sys.path`. The alias exists
    only while the module body runs."""
    jsonio = _load("sb_inventory_jsonio", "jsonio.py")
    previous = sys.modules.get("jsonio", _ABSENT)
    sys.modules["jsonio"] = jsonio
    try:
        return _load("sb_inventory", "inventory.py")
    finally:
        if previous is _ABSENT:
            del sys.modules["jsonio"]
        else:
            sys.modules["jsonio"] = previous


class World:
    """A throwaway home and repository."""

    def __init__(self, tmp_path):
        self.home = tmp_path / "home"
        self.repo = tmp_path / "repo"
        self.plugins = self.home / ".claude" / "plugins"
        self.plugins.mkdir(parents=True)
        self.repo.mkdir()

    def skill(self, skills_dir, dirname, name=None, text=None):
        skill_dir = skills_dir / dirname
        skill_dir.mkdir(parents=True, exist_ok=True)
        if text is None:
            text = "---\nname: %s\ndescription: x\n---\n\nbody\n" % (name or dirname)
        (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
        return skill_dir / "SKILL.md"

    def cache_plugin(self, plugin, version="1.0.0", marketplace="mp"):
        root = self.plugins / "cache" / marketplace / plugin / version
        root.mkdir(parents=True, exist_ok=True)
        return root

    def marketplace_plugin(self, plugin, segment="plugins", marketplace="mp"):
        root = self.plugins / "marketplaces" / marketplace / segment / plugin
        root.mkdir(parents=True, exist_ok=True)
        return root

    def install(self, entries):
        """Write installed_plugins.json; `entries` maps plugin key -> installPath."""
        doc = {
            "version": 2,
            "plugins": {
                key: [{"scope": "user", "installPath": str(path)}] for key, path in entries.items()
            },
        }
        write_json(self.plugins / "installed_plugins.json", doc)

    def template(self, version, excluded, marketplace="mp"):
        """A template in the cache layout, which has a version directory."""
        path = self.plugins / "cache" / marketplace / "tcs-git-helpers" / version / TEMPLATE_REL
        write_template(path, excluded)
        return path

    def marketplace_template(self, excluded, marketplace="mp"):
        """A template in the marketplace layout, which has no version directory."""
        path = self.plugins / "marketplaces" / marketplace / "plugins" / "tcs-git-helpers" / TEMPLATE_REL
        write_template(path, excluded)
        return path

    def repo_template(self, excluded):
        """The path a cloned repository can ship; `scan` must never read it."""
        path = self.repo / "plugins" / "tcs-git-helpers" / TEMPLATE_REL
        write_template(path, excluded)
        return path


def write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_template(path, excluded):
    write_json(
        path,
        {
            "sandbox": {
                "excludedCommands": list(excluded),
                "filesystem": {"denyWrite": ["./.githooks"]},
            },
            "permissions": {"ask": ["Bash(git remote add *)"]},
        },
    )


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def names(inv, namespace=None):
    return sorted(s.name for s in inv.skills if namespace is None or s.namespace == namespace)


def reasons(inv):
    return [s.reason for s in inv.skipped]


@pytest.fixture
def opened(monkeypatch):
    """Every path handed to `os.open` while the test runs. Both `inventory`
    and `jsonio` open files through it and through nothing else."""
    paths = []
    real_open = os.open

    def recording_open(path, *args, **kwargs):
        paths.append(os.fspath(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", recording_open)
    return paths


def opened_below(opened, root):
    return [path for path in opened if pathlib.Path(path).is_relative_to(root)]


# --- skills ---------------------------------------------------------------


def test_empty_home_and_repo_give_an_empty_inventory(inventory, world):
    inv = inventory.scan(world.home, world.repo)

    assert inv.skills == ()
    assert inv.plugin_mcp == ()
    assert inv.git_template is None
    assert inv.skipped == ()


def test_plugin_skills_are_found_in_cache_and_marketplaces(inventory, world):
    world.skill(world.cache_plugin("alpha", "1.2.0") / "skills", "one")
    world.skill(world.marketplace_plugin("beta") / "skills", "two")
    world.skill(world.marketplace_plugin("gamma", segment="external_plugins") / "skills", "three")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv, "plugin") == ["one", "three", "two"]
    assert {s.name: s.plugin for s in inv.skills} == {"one": "alpha", "two": "beta", "three": "gamma"}


def test_skill_name_is_the_frontmatter_name_not_the_directory(inventory, world):
    world.skill(world.cache_plugin("hookify") / "skills", "writing-rules", name="writing-hookify-rules")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["writing-hookify-rules"]


def test_quoted_name_and_trailing_comment_are_read_as_yaml_would(inventory, world):
    skills = world.home / ".claude" / "skills"
    world.skill(skills, "a", text='---\nname: "quoted-one"\n---\n')
    world.skill(skills, "b", text="---\nname: 'quoted-two'\n---\n")
    world.skill(skills, "c", text="---\nname: plain-one # a comment\n---\n")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["plain-one", "quoted-one", "quoted-two"]


def test_repo_and_user_skills_are_found(inventory, world):
    world.skill(world.repo / ".claude" / "skills", "repo-skill")
    world.skill(world.home / ".claude" / "skills", "user-skill")
    world.skill(world.home / ".claude" / "skills" / "synced" / "0af3", "deep-skill")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv, "repo") == ["repo-skill"]
    assert names(inv, "user") == ["deep-skill", "user-skill"]
    assert all(s.plugin is None for s in inv.skills)


def test_skill_names_hold_bare_and_plugin_qualified_spellings(inventory, world):
    world.skill(world.cache_plugin("alpha") / "skills", "one")
    world.skill(world.home / ".claude" / "skills", "mine")

    inv = inventory.scan(world.home, world.repo)

    assert inv.skill_names == frozenset({"one", "alpha:one", "mine"})


def test_versions_of_one_plugin_are_unioned(inventory, world):
    world.skill(world.cache_plugin("alpha", "1.0.0") / "skills", "old-skill")
    world.skill(world.cache_plugin("alpha", "2.0.0") / "skills", "new-skill")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["new-skill", "old-skill"]


def test_symlink_loop_is_survived_and_each_skill_reported_once(inventory, world):
    skills = world.home / ".claude" / "skills"
    world.skill(skills, "looped")
    os.symlink(skills, skills / "looped" / "back")
    os.symlink(skills / "looped", skills / "alias")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["looped"]
    assert len(inv.skills) == 1
    # Without the identity dedup the walk only ends where the kernel refuses
    # to resolve the chain any further, and that refusal is reported.
    assert inv.skipped == ()


def test_symlinked_skill_directory_is_followed(inventory, world):
    real = world.home / "elsewhere"
    world.skill(real, "linked")
    skills = world.home / ".claude" / "skills"
    skills.mkdir(parents=True)
    os.symlink(real / "linked", skills / "linked")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv, "user") == ["linked"]


def test_dot_prefixed_directories_are_skipped(inventory, world):
    world.skill(world.home / ".claude" / "skills" / ".hidden", "inside-hidden")
    world.skill(world.home / ".claude" / "skills" / "ok" / ".git", "inside-git")
    world.skill(world.plugins / "cache" / "mp" / ".staging" / "1.0.0" / "skills", "staged")
    world.skill(world.plugins / "cache" / "mp" / "alpha" / ".tmp" / "skills", "half-installed")
    world.skill(world.home / ".claude" / "skills", "visible")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["visible"]
    assert inv.skipped == ()


def test_directory_whose_identity_cannot_be_read_is_reported_and_siblings_listed(
    inventory, world, monkeypatch
):
    skills = world.home / ".claude" / "skills"
    world.skill(skills, "a-first")
    world.skill(skills, "broken")
    world.skill(skills, "z-last")
    broken = str(skills / "broken")
    real_identity = inventory._identity

    def identity(path):
        if os.fspath(path) == broken:
            raise OSError(errno.EACCES, "denied", broken)
        return real_identity(path)

    monkeypatch.setattr(inventory, "_identity", identity)

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["a-first", "z-last"]
    assert [(s.path, s.reason) for s in inv.skipped] == [(broken, "unreadable-directory")]


def test_directory_that_cannot_be_listed_is_reported_and_siblings_listed(inventory, world, monkeypatch):
    skills = world.home / ".claude" / "skills"
    world.skill(skills, "a-first")
    world.skill(skills / "locked", "inside")
    world.skill(skills, "z-last")
    locked = str(skills / "locked")
    real_scandir = os.scandir

    def scandir(path="."):
        if os.fspath(path) == locked:
            raise PermissionError(errno.EACCES, "denied", locked)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["a-first", "z-last"]
    assert [(s.path, s.reason) for s in inv.skipped] == [(locked, "unreadable-directory")]


def test_plugin_directory_name_with_a_trailing_newline_is_not_a_plugin_name(inventory, world):
    world.skill(world.cache_plugin("alpha\n") / "skills", "one")

    inv = inventory.scan(world.home, world.repo)

    assert [(s.name, s.plugin) for s in inv.skills] == [("one", None)]
    assert inv.skill_names == frozenset({"one"})


@pytest.mark.parametrize(
    "raw",
    ["../../etc/passwd", "a/b", "/abs", "..", "has space", "x" * 65, "-leading", "nul\\x00", "a:b"],
)
def test_untrusted_frontmatter_name_is_skipped_never_listed(inventory, world, raw):
    path = world.skill(world.repo / ".claude" / "skills", "evil", text="---\nname: %s\n---\n" % raw)

    inv = inventory.scan(world.home, world.repo)

    assert inv.skills == ()
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(path), "invalid-skill-name")]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("no frontmatter here\n", "no-frontmatter"),
        ("---\nname: never-closed\n", "no-frontmatter"),
        ("---\ndescription: x\n---\n", "no-skill-name"),
        ("---\nname: one\nname: two\n---\n", "duplicate-skill-name"),
        ("---\nname:\n---\n", "invalid-skill-name"),
        ("---\nname: >-\n  folded\n---\n", "invalid-skill-name"),
    ],
)
def test_unusable_skill_file_is_skipped_with_a_fixed_reason(inventory, world, text, reason):
    world.skill(world.home / ".claude" / "skills", "broken", text=text)
    world.skill(world.home / ".claude" / "skills", "fine")

    inv = inventory.scan(world.home, world.repo)

    assert names(inv) == ["fine"]
    assert reasons(inv) == [reason]


def test_name_in_the_body_is_not_the_frontmatter_name(inventory, world):
    world.skill(
        world.home / ".claude" / "skills",
        "real",
        text="---\nname: real\n---\n\nname: body-name\n",
    )

    assert names(inventory.scan(world.home, world.repo)) == ["real"]


def test_skill_file_that_is_a_fifo_does_not_block_the_scan(inventory, world):
    skill_dir = world.repo / ".claude" / "skills" / "pipe"
    skill_dir.mkdir(parents=True)
    os.mkfifo(skill_dir / "SKILL.md")

    inv = inventory.scan(world.home, world.repo)

    assert inv.skills == ()
    assert reasons(inv) == ["unreadable-skill-file"]


def test_walk_stops_at_the_directory_limit_and_says_so(inventory, world, monkeypatch):
    skills = world.repo / ".claude" / "skills"
    for i in range(6):
        world.skill(skills, "s%d" % i)
    monkeypatch.setattr(inventory, "MAX_DIRS_PER_ROOT", 3)

    inv = inventory.scan(world.home, world.repo)

    # The root is directory one; `s0` and `s1` are two and three.
    assert names(inv) == ["s0", "s1"]
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(skills), "walk-limit")]


def test_repo_root_none_scans_only_the_home(inventory, world):
    world.skill(world.home / ".claude" / "skills", "mine")
    world.repo_template(["gh *"])

    inv = inventory.scan(world.home, None)

    assert names(inv) == ["mine"]
    assert inv.git_template is None


# --- plugin MCP servers ---------------------------------------------------


def test_plugin_mcp_servers_come_from_mcp_json(inventory, world):
    root = world.cache_plugin("alpha")
    write_json(root / ".mcp.json", {"mcpServers": {"wrapped": {"command": "x"}}})
    other = world.cache_plugin("beta")
    write_json(other / ".mcp.json", {"flat": {"command": "y"}})
    world.install({"alpha@mp": root, "beta@mp": other})

    inv = inventory.scan(world.home, world.repo)

    assert [(s.name, s.plugin, s.path) for s in inv.plugin_mcp] == [
        ("wrapped", "alpha@mp", str(root / ".mcp.json")),
        ("flat", "beta@mp", str(other / ".mcp.json")),
    ]


def test_plugin_mcp_servers_come_from_plugin_json_mcp_servers(inventory, world):
    root = world.cache_plugin("alpha")
    manifest = root / ".claude-plugin" / "plugin.json"
    write_json(manifest, {"name": "alpha", "mcpServers": {"inline": {"type": "http", "url": "https://x.test"}}})
    world.install({"alpha@mp": root})

    inv = inventory.scan(world.home, world.repo)

    assert [(s.name, s.plugin, s.path) for s in inv.plugin_mcp] == [("inline", "alpha@mp", str(manifest))]


def test_plugin_json_mcp_servers_may_name_a_file_inside_the_plugin(inventory, world):
    root = world.cache_plugin("alpha")
    write_json(root / ".claude-plugin" / "plugin.json", {"mcpServers": ["./cfg/a.json", {"inline": {}}]})
    write_json(root / "cfg" / "a.json", {"mcpServers": {"from-file": {}}})
    world.install({"alpha@mp": root})

    inv = inventory.scan(world.home, world.repo)

    assert [s.name for s in inv.plugin_mcp] == ["from-file", "inline"]
    assert inv.plugin_mcp[0].path == str(root / "cfg" / "a.json")


def test_plugin_json_mcp_file_outside_the_plugin_is_rejected(inventory, world):
    root = world.cache_plugin("alpha")
    outside = world.home / "outside.json"
    write_json(outside, {"mcpServers": {"smuggled": {}}})
    write_json(root / ".claude-plugin" / "plugin.json", {"mcpServers": "../../../../../../outside.json"})
    world.install({"alpha@mp": root})

    inv = inventory.scan(world.home, world.repo)

    assert inv.plugin_mcp == ()
    assert reasons(inv) == ["mcp-path-outside-plugin"]


def test_mcp_config_values_are_not_kept(inventory, world):
    root = world.cache_plugin("alpha")
    write_json(root / ".mcp.json", {"mcpServers": {"s": {"env": {"TOKEN": "value-not-kept"}}}})
    world.install({"alpha@mp": root})

    inv = inventory.scan(world.home, world.repo)

    assert "value-not-kept" not in repr(inv)


def test_install_path_outside_the_plugins_directory_is_rejected(inventory, world):
    outside = world.home / "rogue"
    write_json(outside / ".mcp.json", {"mcpServers": {"rogue": {}}})
    world.install({"rogue@mp": outside})

    inv = inventory.scan(world.home, world.repo)

    assert inv.plugin_mcp == ()
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(outside), "install-path-outside-plugins")]


def test_install_path_escaping_through_a_symlink_or_dotdot_is_rejected(inventory, world):
    outside = world.home / "rogue"
    write_json(outside / ".mcp.json", {"mcpServers": {"rogue": {}}})
    link = world.plugins / "cache" / "mp" / "linked"
    link.parent.mkdir(parents=True)
    os.symlink(outside, link)
    dotdot = str(world.plugins) + "/cache/../../../rogue"
    world.install({"a@mp": link, "b@mp": dotdot, "c@mp": "relative/path", "d@mp": world.plugins})

    inv = inventory.scan(world.home, world.repo)

    assert inv.plugin_mcp == ()
    assert reasons(inv) == ["install-path-outside-plugins"] * 4


def test_install_path_that_is_a_file_is_rejected(inventory, world):
    not_a_dir = world.plugins / "cache" / "mp" / "alpha" / "1.0.0"
    not_a_dir.parent.mkdir(parents=True)
    not_a_dir.write_text("{}", encoding="utf-8")
    good = world.cache_plugin("beta")
    write_json(good / ".mcp.json", {"mcpServers": {"ok": {}}})
    world.install({"alpha@mp": not_a_dir, "beta@mp": good})

    inv = inventory.scan(world.home, world.repo)

    assert [s.name for s in inv.plugin_mcp] == ["ok"]
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(not_a_dir), "install-path-not-a-directory")]


def test_install_path_that_does_not_exist_contributes_nothing(inventory, world):
    world.install({"gone@mp": world.plugins / "cache" / "mp" / "gone" / "1.0.0"})

    inv = inventory.scan(world.home, world.repo)

    assert inv.plugin_mcp == ()
    assert inv.skipped == ()


def test_install_path_that_is_not_a_string_is_rejected(inventory, world):
    write_json(
        world.plugins / "installed_plugins.json",
        {"version": 2, "plugins": {"a@mp": [{"installPath": 7}], "b@mp": "nonsense"}},
    )

    inv = inventory.scan(world.home, world.repo)

    assert inv.plugin_mcp == ()
    assert reasons(inv) == ["install-path-outside-plugins"] * 2


def test_unreadable_installed_plugins_file_is_reported(inventory, world):
    path = world.plugins / "installed_plugins.json"
    path.write_text("{not json", encoding="utf-8")

    inv = inventory.scan(world.home, world.repo)

    assert [(s.path, s.reason) for s in inv.skipped] == [(str(path), "invalid-json")]


def test_unreadable_plugin_mcp_file_is_reported_and_the_rest_still_read(inventory, world):
    bad = world.cache_plugin("alpha")
    (bad / ".mcp.json").write_text('{"a": 1, "a": 2}', encoding="utf-8")
    good = world.cache_plugin("beta")
    write_json(good / ".mcp.json", {"mcpServers": {"ok": {}}})
    world.install({"alpha@mp": bad, "beta@mp": good})

    inv = inventory.scan(world.home, world.repo)

    assert [s.name for s in inv.plugin_mcp] == ["ok"]
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(bad / ".mcp.json"), "duplicate-key")]


def test_plugin_without_mcp_files_contributes_nothing(inventory, world):
    world.install({"alpha@mp": world.cache_plugin("alpha")})

    inv = inventory.scan(world.home, world.repo)

    assert inv.plugin_mcp == ()
    assert inv.skipped == ()


# --- git-helpers template (ADR-9) ------------------------------------------


def test_template_is_the_newest_by_version_order_not_lexical(inventory, world):
    world.template("2.2.43", ["old *"])
    world.template("2.3.0", ["lexical-winner *"])
    newest = world.template("2.10.0", ["gh *", "git push *"])

    template = inventory.scan(world.home, world.repo).git_template

    assert template.version == "2.10.0"
    assert template.path == str(newest)
    assert template.origin == "cache"
    assert template.excluded_commands == ("gh *", "git push *")
    assert template.deny_write == ("./.githooks",)
    assert template.ask == ("Bash(git remote add *)",)


def test_marketplace_only_install_is_found(inventory, world):
    path = world.marketplace_template(["marketplace *"])

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template.path == str(path)
    assert inv.git_template.origin == "marketplace"
    assert inv.git_template.version is None
    assert inv.git_template.excluded_commands == ("marketplace *",)
    assert inv.git_template.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert inv.skipped == ()


def test_any_versioned_cache_copy_beats_the_marketplace_copy(inventory, world):
    world.marketplace_template(["marketplace *"])
    cached = world.template("0.0.1", ["cache *"])

    template = inventory.scan(world.home, world.repo).git_template

    assert template.path == str(cached)
    assert template.origin == "cache"
    assert template.excluded_commands == ("cache *",)


def test_marketplace_copy_beats_a_cache_directory_that_is_not_a_version(inventory, world):
    world.template("main", ["branch *"])
    world.marketplace_template(["marketplace *"])

    assert inventory.scan(world.home, world.repo).git_template.origin == "marketplace"


def test_version_directory_below_marketplaces_is_not_a_layout(inventory, world):
    path = world.plugins / "marketplaces" / "mp" / "tcs-git-helpers" / "9.9.9" / TEMPLATE_REL
    write_template(path, ["wrong-layout *"])

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template is None
    assert inv.skipped == ()


def test_template_with_a_non_version_directory_ranks_below_every_version(inventory, world):
    world.template("main", ["branch *"])
    world.template("0.0.1", ["versioned *"])

    assert inventory.scan(world.home, world.repo).git_template.version == "0.0.1"


def test_same_version_in_two_marketplaces_goes_to_the_lower_path(inventory, world, monkeypatch):
    world.template("1.0.0", ["zz *"], marketplace="zz")
    lower = world.template("1.0.0", ["aa *"], marketplace="aa")
    real_glob = pathlib.Path.glob

    def highest_path_first(self, pattern):
        """Directory order is the file system's choice; fix it to the order
        the tie-break has to undo."""
        return sorted(real_glob(self, pattern), reverse=True)

    monkeypatch.setattr(pathlib.Path, "glob", highest_path_first)

    template = inventory.scan(world.home, world.repo).git_template

    assert template.path == str(lower)
    assert template.excluded_commands == ("aa *",)


def test_longer_version_beats_its_shorter_prefix_whatever_the_path(inventory, world):
    world.template("1.0", ["short *"], marketplace="aa")
    longer = world.template("1.0.0", ["long *"], marketplace="zz")

    template = inventory.scan(world.home, world.repo).git_template

    assert template.version == "1.0.0"
    assert template.path == str(longer)


def test_version_directory_with_a_trailing_newline_is_not_a_version(inventory, world):
    world.template("9.9.9\n", ["newline *"])
    versioned = world.template("0.0.1", ["versioned *"])

    template = inventory.scan(world.home, world.repo).git_template

    assert template.version == "0.0.1"
    assert template.path == str(versioned)


def test_template_swapped_for_a_fifo_before_the_digest_is_none(inventory, world, monkeypatch):
    path = world.template("1.0.0", ["gh *"])
    real_read_json = inventory.jsonio.read_json

    def read_then_swap(target, follow_symlink):
        result = real_read_json(target, follow_symlink)
        if os.path.realpath(target) == os.path.realpath(path):
            os.unlink(path)
            os.mkfifo(path)
        return result

    def release_a_blocked_reader():
        try:
            os.close(os.open(path, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass  # nobody is blocked on the FIFO

    monkeypatch.setattr(inventory.jsonio, "read_json", read_then_swap)
    # A blocking open would hang the test run; this turns it into a failure.
    watchdog = threading.Timer(2.0, release_a_blocked_reader)
    watchdog.start()
    try:
        inv = inventory.scan(world.home, world.repo)
    finally:
        watchdog.cancel()
        watchdog.join()

    assert inv.git_template is None
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(path), "io-error")]


def test_repo_shipping_the_template_path_without_an_install_gives_none(inventory, world, opened):
    shipped = world.repo_template(["curl *"])

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template is None
    assert inv.skipped == ()
    assert opened_below(opened, shipped.parent) == []


def test_repo_shipping_the_template_path_never_replaces_the_installed_one(inventory, world, opened):
    shipped = world.repo_template(["curl *"])
    installed = world.template("0.1.0", ["installed *"])

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template.path == str(installed)
    assert inv.git_template.origin == "cache"
    assert inv.git_template.excluded_commands == ("installed *",)
    assert str(installed) in opened
    assert opened_below(opened, shipped.parent) == []


def test_template_sha256_is_the_digest_of_the_file_bytes(inventory, world):
    path = world.template("2.10.0", ["gh *"])

    template = inventory.scan(world.home, world.repo).git_template

    assert template.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_absent_template_is_none(inventory, world):
    world.skill(world.cache_plugin("tcs-git-helpers", "2.10.0") / "skills", "git-setup")

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template is None
    assert inv.skipped == ()


def test_unreadable_newest_template_is_none_never_an_older_one(inventory, world):
    world.template("2.3.0", ["older *"])
    newest = world.template("2.10.0", [])
    newest.write_text("{broken", encoding="utf-8")
    world.marketplace_template(["marketplace *"])
    world.repo_template(["repo *"])

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template is None
    assert [(s.path, s.reason) for s in inv.skipped] == [(str(newest), "invalid-json")]


def test_template_symlinked_out_of_the_plugins_directory_is_rejected(inventory, world):
    outside = world.home / "fake.json"
    write_template(outside, ["curl *"])
    link = world.plugins / "cache" / "mp" / "tcs-git-helpers" / "9.0.0" / TEMPLATE_REL
    link.parent.mkdir(parents=True)
    os.symlink(outside, link)

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template is None
    assert reasons(inv) == ["template-outside-plugins"]


def test_marketplace_symlinked_out_of_the_plugins_directory_is_rejected(inventory, world):
    outside = world.home / "local-marketplace"
    write_template(outside / "plugins" / "tcs-git-helpers" / TEMPLATE_REL, ["curl *"])
    link = world.plugins / "marketplaces" / "mp"
    link.parent.mkdir(parents=True)
    os.symlink(outside, link)

    inv = inventory.scan(world.home, world.repo)

    assert inv.git_template is None
    assert [(s.path, s.reason) for s in inv.skipped] == [
        (str(link / "plugins" / "tcs-git-helpers" / TEMPLATE_REL), "template-outside-plugins")
    ]


def test_template_entries_that_are_not_strings_are_dropped(inventory, world):
    path = world.template("1.0.0", [])
    write_json(path, {"sandbox": {"excludedCommands": ["gh *", 7, None, ["x"]]}, "permissions": "nope"})

    template = inventory.scan(world.home, world.repo).git_template

    assert template.excluded_commands == ("gh *",)
    assert template.deny_write == ()
    assert template.ask == ()


def test_real_template_shape_is_understood(inventory, world):
    target = world.plugins / "cache" / "mp" / "tcs-git-helpers" / "2.6.2" / TEMPLATE_REL
    target.parent.mkdir(parents=True)
    target.write_bytes(REAL_TEMPLATE.read_bytes())
    expected = json.loads(REAL_TEMPLATE.read_text(encoding="utf-8"))

    template = inventory.scan(world.home, world.repo).git_template

    assert list(template.excluded_commands) == expected["sandbox"]["excludedCommands"]
    assert list(template.deny_write) == expected["sandbox"]["filesystem"]["denyWrite"]
    assert list(template.ask) == expected["permissions"]["ask"]


# --- read-only ------------------------------------------------------------


def _digest(root):
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            entries.append((path, st.st_mode, st.st_size, st.st_mtime_ns))
    return sorted(entries)


def test_scan_writes_nothing(inventory, world, tmp_path):
    world.skill(world.cache_plugin("alpha") / "skills", "one")
    world.template("2.10.0", ["gh *"])
    root = world.cache_plugin("beta")
    write_json(root / ".mcp.json", {"mcpServers": {"s": {}}})
    world.install({"beta@mp": root})
    before = _digest(tmp_path)

    inventory.scan(world.home, world.repo)

    assert _digest(tmp_path) == before
