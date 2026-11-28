"""Settings and MCP source discovery of the security-baseline skill
(spec 025, T2.3, K6).

Every test builds its own world under ``tmp_path``: a home, a repository
with a nested start directory and a system directory standing in for
``/etc/claude-code``. Nothing reads the real ``$HOME`` or ``/etc``, and a
digest of the whole world proves discovery writes nothing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"


def _load(name, filename):
    """Load a lib module under ``name``, registered before execution because
    dataclasses resolves string annotations through ``sys.modules``."""
    spec = importlib.util.spec_from_file_location(name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def layers():
    """``layers`` imports ``jsonio`` by its bare name, the way it resolves
    once cli.py has put the lib directory on ``sys.path``."""
    previous = sys.modules.get("jsonio")
    _load("jsonio", "jsonio.py")
    try:
        yield _load("sb_layers", "layers.py")
    finally:
        sys.modules.pop("sb_layers", None)
        if previous is None:
            sys.modules.pop("jsonio", None)
        else:
            sys.modules["jsonio"] = previous


@dataclasses.dataclass
class World:
    root: pathlib.Path
    home: pathlib.Path
    repo: pathlib.Path
    start: pathlib.Path
    system: pathlib.Path

    def discover(self, layers, **overrides):
        args = {
            "project_dir": str(self.start),
            "repo_root": str(self.repo),
            "home": str(self.home),
            "config_dir": None,
            "system_root": str(self.system),
        }
        args.update(overrides)
        return layers.discover(**args)


@pytest.fixture
def world(tmp_path, monkeypatch):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    start = repo / "packages" / "app"
    system = tmp_path / "system"
    for directory in (home, start, system):
        directory.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return World(tmp_path, home, repo, start, system)


def _write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _digest(root):
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs) + sorted(files):
            path = os.path.join(current, name)
            info = os.lstat(path)
            digest.update(f"{path}|{info.st_mode}|{info.st_mtime_ns}|{info.st_size}\n".encode())
            if os.path.isfile(path) and not os.path.islink(path) and os.access(path, os.R_OK):
                with open(path, "rb") as handle:
                    digest.update(handle.read())
    return digest.hexdigest()


def _by_scope(sources, scope):
    return [source for source in sources if source.scope == scope]


def _one(sources, scope):
    found = _by_scope(sources, scope)
    assert len(found) == 1, [(s.scope, s.path) for s in sources]
    return found[0]


needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root reads through file modes",
)


# --- managed -----------------------------------------------------------------


def test_managed_settings_found_under_injected_system_root(layers, world):
    path = _write_json(world.system / "managed-settings.json", {"model": "opus"})

    managed = _one(world.discover(layers), "managed")

    assert managed.path == str(path)
    assert managed.status == "ok"
    assert managed.data == {"model": "opus"}


def test_managed_dropins_alphabetical_hidden_and_non_json_skipped(layers, world):
    dropins = world.system / "managed-settings.d"
    _write_json(dropins / "20-security.json", {"n": 20})
    _write_json(dropins / "10-telemetry.json", {"n": 10})
    _write_json(dropins / "15-middle.json", {"n": 15})
    _write_json(dropins / ".hidden.json", {"n": -1})
    (dropins / "README.txt").write_text("not json\n", encoding="utf-8")
    (dropins / "30-backup.json.bak").write_text("{}\n", encoding="utf-8")

    found = _by_scope(world.discover(layers), "managed-dropin")

    assert [os.path.basename(s.path) for s in found] == [
        "10-telemetry.json",
        "15-middle.json",
        "20-security.json",
    ]
    assert [s.data["n"] for s in found] == [10, 15, 20]


def test_managed_file_precedes_its_dropins(layers, world):
    _write_json(world.system / "managed-settings.json", {})
    _write_json(world.system / "managed-settings.d" / "10-a.json", {})

    scopes = [s.scope for s in world.discover(layers)]

    assert scopes.index("managed") < scopes.index("managed-dropin")


def test_absent_managed_file_is_reported_absent_without_dropins(layers, world):
    sources = world.discover(layers)

    assert _one(sources, "managed").status == "absent"
    assert _by_scope(sources, "managed-dropin") == []


def test_no_system_root_yields_no_managed_sources(layers, world):
    sources = world.discover(layers, system_root=None)

    scopes = {s.scope for s in sources}
    assert not scopes & {"managed", "managed-dropin", "managed-mcp"}


def test_default_system_root_per_platform(layers):
    assert layers.default_system_root("linux") == "/etc/claude-code"
    assert layers.default_system_root("darwin") == "/Library/Application Support/ClaudeCode"
    assert layers.default_system_root("other") is None


# --- user --------------------------------------------------------------------


def test_user_settings_default_to_home_dot_claude(layers, world):
    path = _write_json(world.home / ".claude" / "settings.json", {"a": 1})

    user = _one(world.discover(layers), "user")

    assert (user.path, user.status, user.data) == (str(path), "ok", {"a": 1})


def test_user_settings_follow_claude_config_dir(layers, world, monkeypatch):
    _write_json(world.home / ".claude" / "settings.json", {"where": "home"})
    config = world.root / "config"
    path = _write_json(config / "settings.json", {"where": "config-dir"})
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))

    user = _one(world.discover(layers, config_dir=os.environ["CLAUDE_CONFIG_DIR"]), "user")

    assert (user.path, user.data) == (str(path), {"where": "config-dir"})


def test_empty_config_dir_falls_back_to_home(layers, world):
    path = _write_json(world.home / ".claude" / "settings.json", {})

    assert _one(world.discover(layers, config_dir=""), "user").path == str(path)


def test_user_settings_symlink_is_followed_and_real_path_recorded(layers, world):
    real = _write_json(world.root / "dotfiles" / "settings.json", {"linked": True})
    link = world.home / ".claude" / "settings.json"
    link.parent.mkdir()
    link.symlink_to(real)

    user = _one(world.discover(layers), "user")

    assert user.status == "ok"
    assert user.path == str(link)
    assert user.real_path == os.path.realpath(real)


# --- project and local -------------------------------------------------------


def test_project_settings_at_project_dir(layers, world):
    path = _write_json(world.start / ".claude" / "settings.json", {"p": 1})
    _write_json(world.repo / ".claude" / "settings.json", {"p": "repo-root"})

    project = _one(world.discover(layers), "project")

    assert (project.path, project.data) == (str(path), {"p": 1})


def test_project_settings_symlink_is_not_followed(layers, world):
    outside = _write_json(world.root / "outside.json", {"allow": "everything"})
    link = world.start / ".claude" / "settings.json"
    link.parent.mkdir()
    link.symlink_to(outside)

    project = _one(world.discover(layers), "project")

    assert (project.status, project.reason, project.data) == ("not-regular", "symlink", None)


def test_local_settings_at_repo_root(layers, world):
    path = _write_json(world.repo / ".claude" / "settings.local.json", {"l": "root"})

    local = _one(world.discover(layers), "local")

    assert (local.path, local.status, local.data) == (str(path), "ok", {"l": "root"})


def test_legacy_local_in_start_directory_read_after_repo_root_one(layers, world):
    root_file = _write_json(world.repo / ".claude" / "settings.local.json", {"l": "root"})
    legacy = _write_json(world.start / ".claude" / "settings.local.json", {"l": "legacy"})

    local = _by_scope(world.discover(layers), "local")

    assert [s.path for s in local] == [str(root_file), str(legacy)]
    assert [s.data["l"] for s in local] == ["root", "legacy"]


def test_absent_legacy_local_is_not_listed(layers, world):
    local = _by_scope(world.discover(layers), "local")

    assert [s.path for s in local] == [str(world.repo / ".claude" / "settings.local.json")]
    assert local[0].status == "absent"


def test_local_listed_once_when_start_directory_is_repo_root(layers, world):
    path = _write_json(world.repo / ".claude" / "settings.local.json", {})

    sources = world.discover(layers, project_dir=str(world.repo) + os.sep)

    assert [s.path for s in _by_scope(sources, "local")] == [str(path)]


def test_local_falls_back_to_project_dir_outside_a_repository(layers, world):
    path = _write_json(world.start / ".claude" / "settings.local.json", {})

    sources = world.discover(layers, repo_root=None)

    assert [s.path for s in _by_scope(sources, "local")] == [str(path)]


# --- statuses ----------------------------------------------------------------


@needs_unprivileged
def test_eacces_on_managed_file_is_denied(layers, world):
    path = _write_json(world.system / "managed-settings.json", {"x": 1})
    path.chmod(0)
    try:
        managed = _one(world.discover(layers), "managed")
    finally:
        path.chmod(0o600)

    assert (managed.status, managed.reason, managed.data) == ("denied", "permission-denied", None)


@needs_unprivileged
def test_eacces_on_dropin_directory_is_one_denied_source(layers, world):
    dropins = world.system / "managed-settings.d"
    _write_json(dropins / "10-a.json", {})
    dropins.chmod(0)
    try:
        found = _by_scope(world.discover(layers), "managed-dropin")
    finally:
        dropins.chmod(0o700)

    assert [(s.path, s.status, s.reason) for s in found] == [
        (str(dropins), "denied", "permission-denied")
    ]


@needs_unprivileged
def test_eacces_on_one_dropin_leaves_the_others_read(layers, world):
    dropins = world.system / "managed-settings.d"
    locked = _write_json(dropins / "10-a.json", {})
    _write_json(dropins / "20-b.json", {"b": 1})
    locked.chmod(0)
    try:
        found = _by_scope(world.discover(layers), "managed-dropin")
    finally:
        locked.chmod(0o600)

    assert [s.status for s in found] == ["denied", "ok"]


def test_dropin_path_that_is_a_file_is_not_regular(layers, world):
    (world.system / "managed-settings.d").write_text("{}\n", encoding="utf-8")

    found = _by_scope(world.discover(layers), "managed-dropin")

    assert [(s.status, s.reason) for s in found] == [("not-regular", "not-regular")]


def test_each_source_carries_the_jsonio_status(layers, world):
    (world.system / "managed-settings.json").write_text("{not json", encoding="utf-8")
    user = world.home / ".claude" / "settings.json"
    user.parent.mkdir()
    user.write_text('{"a": 1, "a": 2}\n', encoding="utf-8")
    (world.start / ".claude" / "settings.json").mkdir(parents=True)
    local = world.repo / ".claude" / "settings.local.json"
    local.parent.mkdir()
    local.write_bytes(b'{"pad": "' + b"x" * (1024 * 1024) + b'"}')
    _write_json(world.start / ".mcp.json", {"mcpServers": {}})

    sources = world.discover(layers)
    seen = {s.scope: (s.status, s.reason) for s in sources}

    assert seen["managed"] == ("unreadable", "invalid-json")
    assert seen["user"] == ("ambiguous", "duplicate-key")
    assert seen["project"] == ("not-regular", "not-regular")
    assert seen["local"] == ("too-large", "too-large")
    assert seen["mcp-json"] == ("ok", None)
    assert seen["claude-json"] == ("absent", None)


def test_only_ok_sources_carry_data_format_and_absent_ones_no_real_path(layers, world):
    _write_json(world.home / ".claude" / "settings.json", {"a": 1})
    (world.system / "managed-settings.json").write_text("[]\n", encoding="utf-8")

    for source in world.discover(layers):
        if source.status == "ok":
            assert isinstance(source.data, dict)
            assert source.format is not None
            assert source.reason is None
        else:
            assert source.data is None
            assert source.format is None
        if source.status == "absent":
            assert source.real_path is None
        else:
            assert source.real_path == os.path.realpath(source.path)


def test_ok_source_keeps_the_format_for_a_faithful_rewrite(layers, world):
    path = world.home / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_bytes(b'{\r\n    "a": 1\r\n}\r\n')

    fmt = _one(world.discover(layers), "user").format

    assert (fmt.indent, fmt.newline, fmt.trailing_newline) == (4, "\r\n", True)


def test_sources_are_listed_in_a_stable_scope_order(layers, world):
    _write_json(world.system / "managed-settings.d" / "10-a.json", {})
    _write_json(world.start / ".claude" / "settings.local.json", {})

    scopes = [s.scope for s in world.discover(layers)]

    assert scopes == [
        "managed",
        "managed-dropin",
        "user",
        "project",
        "local",
        "local",
        "claude-json",
        "mcp-json",
        "managed-mcp",
    ]


# --- MCP sources -------------------------------------------------------------


def test_claude_json_sits_in_home_by_default(layers, world):
    path = _write_json(world.home / ".claude.json", {"mcpServers": {}})
    _write_json(world.home / ".claude" / ".claude.json", {"wrong": True})

    source = _one(world.discover(layers), "claude-json")

    assert (source.path, source.data) == (str(path), {"mcpServers": {}})


def test_claude_json_moves_into_claude_config_dir(layers, world):
    _write_json(world.home / ".claude.json", {"where": "home"})
    config = world.root / "config"
    path = _write_json(config / ".claude.json", {"where": "config-dir"})

    source = _one(world.discover(layers, config_dir=str(config)), "claude-json")

    assert (source.path, source.data) == (str(path), {"where": "config-dir"})


def test_mcp_json_read_from_project_dir_and_managed_mcp_from_system_root(layers, world):
    project = _write_json(world.start / ".mcp.json", {"mcpServers": {"a": {}}})
    managed = _write_json(world.system / "managed-mcp.json", {"mcpServers": {"m": {}}})

    sources = world.discover(layers)

    assert _one(sources, "mcp-json").path == str(project)
    assert _one(sources, "managed-mcp").path == str(managed)
    assert _one(sources, "managed-mcp").status == "ok"


def _mcp_world(world):
    """One server per origin, named after it."""
    start, repo = str(world.start), str(world.repo)
    _write_json(
        world.start / ".mcp.json",
        {"mcpServers": {"from-project": {"command": "npx", "args": ["-y", "srv"]}}},
    )
    _write_json(
        world.home / ".claude.json",
        {
            "mcpServers": {"from-user": {"type": "http", "url": "https://mcp.example.test/"}},
            "projects": {
                start: {
                    "mcpServers": {"from-local": {"command": "local-srv"}},
                    "enabledMcpjsonServers": ["from-project"],
                    "disabledMcpjsonServers": ["rejected-in-state"],
                },
                repo: {"mcpServers": {"from-local-root": {"command": "root-srv"}}},
                "/somewhere/else": {
                    "mcpServers": {"other-project": {"command": "nope"}},
                    "enabledMcpjsonServers": ["other-project"],
                },
            },
        },
    )
    _write_json(
        world.system / "managed-mcp.json",
        {"mcpServers": {"from-managed": {"command": "/opt/corp/srv"}}},
    )


def test_servers_listed_from_every_origin_with_their_source(layers, world):
    _mcp_world(world)
    sources = world.discover(layers)
    plugin = {"name": "from-plugin", "path": "/p/demo/.mcp.json", "config": {"command": "plug"}}
    keys = layers.project_keys(str(world.start), str(world.repo))

    servers = layers.mcp_servers(sources, [plugin], keys)

    listed = {s.name: (s.origin, s.scope, s.path) for s in servers}
    claude_json = str(world.home / ".claude.json")
    assert listed == {
        "from-project": ("project", "mcp-json", str(world.start / ".mcp.json")),
        "from-user": ("user", "claude-json", claude_json),
        "from-local": ("local", "claude-json", claude_json),
        "from-local-root": ("local", "claude-json", claude_json),
        "from-managed": ("managed", "managed-mcp", str(world.system / "managed-mcp.json")),
        "from-plugin": ("plugin", "plugin", "/p/demo/.mcp.json"),
    }
    assert {s.name: s.config for s in servers}["from-project"] == {
        "command": "npx",
        "args": ["-y", "srv"],
    }


def test_local_scope_servers_of_other_projects_are_not_listed(layers, world):
    _mcp_world(world)
    sources = world.discover(layers)

    names = {s.name for s in layers.mcp_servers(sources, [], [str(world.start)])}

    assert "other-project" not in names
    assert "from-local-root" not in names
    assert "from-local" in names


def test_plugin_servers_accept_objects_as_well_as_mappings(layers, world):
    @dataclasses.dataclass
    class PluginServer:
        name: str
        path: str
        config: dict

    servers = layers.mcp_servers([], [PluginServer("obj", "/p/plugin.json", {"command": "x"})], [])

    assert [(s.name, s.origin, s.path, s.config) for s in servers] == [
        ("obj", "plugin", "/p/plugin.json", {"command": "x"})
    ]


def test_same_name_in_two_origins_is_listed_twice(layers, world):
    _write_json(world.start / ".mcp.json", {"mcpServers": {"dup": {"command": "a"}}})
    _write_json(world.home / ".claude.json", {"mcpServers": {"dup": {"command": "b"}}})

    servers = layers.mcp_servers(world.discover(layers), [], [])

    assert sorted((s.name, s.origin) for s in servers) == [("dup", "project"), ("dup", "user")]


def test_unreadable_mcp_source_lists_no_servers_but_keeps_its_status(layers, world):
    (world.start / ".mcp.json").write_text('{"mcpServers": {"a": {}}', encoding="utf-8")
    sources = world.discover(layers)

    assert layers.mcp_servers(sources, [], []) == []
    assert _one(sources, "mcp-json").status == "unreadable"


def test_malformed_server_tables_and_entries_do_not_raise(layers, world):
    _write_json(world.start / ".mcp.json", {"mcpServers": {"odd": "not-an-object", "ok": {}}})
    _write_json(
        world.home / ".claude.json",
        {"mcpServers": ["nope"], "projects": {str(world.start): "nope"}},
    )
    sources = world.discover(layers)

    servers = layers.mcp_servers(sources, [], [str(world.start)])

    assert [(s.name, s.config) for s in servers] == [("odd", None), ("ok", {})]


def test_approval_keys_read_from_every_settings_layer(layers, world):
    _write_json(world.system / "managed-settings.json", {"disabledMcpjsonServers": ["bad"]})
    _write_json(world.system / "managed-settings.d" / "10-a.json", {"model": "opus"})
    _write_json(world.home / ".claude" / "settings.json", {"enabledMcpjsonServers": ["memory"]})
    _write_json(world.start / ".claude" / "settings.json", {"enableAllProjectMcpServers": True})
    _write_json(
        world.repo / ".claude" / "settings.local.json",
        {"enabledMcpjsonServers": ["github"], "permissions": {"allow": []}},
    )
    sources = world.discover(layers)

    approvals = layers.mcp_approvals(sources, [])

    assert [(a.scope, a.key, a.value, a.observed_only) for a in approvals] == [
        ("managed", "disabledMcpjsonServers", ["bad"], False),
        ("user", "enabledMcpjsonServers", ["memory"], False),
        ("project", "enableAllProjectMcpServers", True, False),
        ("local", "enabledMcpjsonServers", ["github"], False),
    ]
    assert approvals[2].path == str(world.start / ".claude" / "settings.json")


def test_claude_json_per_project_approvals_are_observed_only(layers, world):
    _mcp_world(world)
    sources = world.discover(layers)

    approvals = layers.mcp_approvals(sources, layers.project_keys(str(world.start), None))

    assert [(a.scope, a.key, a.value, a.observed_only) for a in approvals] == [
        ("claude-json", "enabledMcpjsonServers", ["from-project"], True),
        ("claude-json", "disabledMcpjsonServers", ["rejected-in-state"], True),
    ]


def test_approval_keys_are_not_taken_from_mcp_files(layers, world):
    _write_json(
        world.start / ".mcp.json",
        {"mcpServers": {}, "enableAllProjectMcpServers": True},
    )
    _write_json(world.system / "managed-mcp.json", {"enabledMcpjsonServers": ["x"]})
    _write_json(world.home / ".claude.json", {"enableAllProjectMcpServers": True})

    assert layers.mcp_approvals(world.discover(layers), [str(world.start)]) == []


def test_project_keys_are_absolute_deduplicated_and_include_the_real_path(layers, world):
    link = world.root / "link-to-repo"
    link.symlink_to(world.repo)

    keys = layers.project_keys(str(link), str(world.repo))

    assert keys == (str(link), os.path.realpath(world.repo))
    assert layers.project_keys(str(world.repo), None) == tuple(
        dict.fromkeys([str(world.repo), os.path.realpath(world.repo)])
    )
    assert layers.project_keys(None, None) == ()


# --- read-only ---------------------------------------------------------------


def test_discovery_and_listing_write_nothing(layers, world):
    _mcp_world(world)
    _write_json(world.system / "managed-settings.json", {"a": 1})
    _write_json(world.system / "managed-settings.d" / "10-a.json", {})
    _write_json(world.home / ".claude" / "settings.json", {})
    _write_json(world.start / ".claude" / "settings.json", {})
    _write_json(world.repo / ".claude" / "settings.local.json", {})
    (world.start / ".claude" / "settings.local.json").write_text("{broken", encoding="utf-8")
    before = _digest(world.root)

    sources = world.discover(layers)
    keys = layers.project_keys(str(world.start), str(world.repo))
    layers.mcp_servers(sources, [], keys)
    layers.mcp_approvals(sources, keys)

    assert _digest(world.root) == before


def test_importing_layers_reads_and_writes_nothing(layers, world, monkeypatch):
    def _refuse(*_args, **_kwargs):
        raise AssertionError("I/O at import")

    monkeypatch.setattr(os, "open", _refuse)
    monkeypatch.setattr(os, "listdir", _refuse)
    monkeypatch.setattr(os, "scandir", _refuse)
    spec = importlib.util.spec_from_file_location("sb_layers_import_probe", LIB_DIR / "layers.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with open(LIB_DIR / "layers.py", encoding="utf-8") as handle:
            source = handle.read()
        exec(compile(source, str(LIB_DIR / "layers.py"), "exec"), module.__dict__)
    finally:
        sys.modules.pop(spec.name, None)


@pytest.fixture
def inventory(layers):
    """The real producer of plugin servers. The `layers` fixture keeps
    `jsonio` registered under its bare name, which `inventory` needs."""
    module = _load("sb_layers_inventory", "inventory.py")
    try:
        yield module
    finally:
        sys.modules.pop("sb_layers_inventory", None)


def test_real_inventory_plugin_server_is_listed_without_config(layers, inventory):
    item = inventory.PluginMcpServer("srv", "demo@market", "/p/demo/.mcp.json")

    servers = layers.mcp_servers([], [item], [])

    assert [(s.name, s.origin, s.scope, s.path, s.plugin, s.config) for s in servers] == [
        ("srv", "plugin", "plugin", "/p/demo/.mcp.json", "demo@market", None)
    ]


def test_plugin_server_mapping_without_config_has_none(layers):
    servers = layers.mcp_servers([], [{"name": "m", "path": "/p/.mcp.json", "plugin": "x@y"}], [])

    assert [(s.name, s.plugin, s.config) for s in servers] == [("m", "x@y", None)]


def test_non_plugin_servers_have_no_plugin(layers, world):
    _write_json(world.start / ".mcp.json", {"mcpServers": {"p": {"command": "a"}}})

    servers = layers.mcp_servers(world.discover(layers), [], [])

    assert [s.plugin for s in servers] == [None]


@pytest.mark.parametrize(
    "item",
    [
        {"path": "/p/.mcp.json"},
        {"name": "n"},
        {"name": 3, "path": "/p/.mcp.json"},
        {"name": "n", "path": None},
        {},
        object(),
    ],
)
def test_plugin_server_missing_name_or_path_is_skipped(layers, item):
    good = {"name": "ok", "path": "/p/.mcp.json"}

    servers = layers.mcp_servers([], [item, good], [])

    assert [s.name for s in servers] == ["ok"]
