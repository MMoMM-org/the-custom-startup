"""Settings and MCP sources at their known paths (spec 025, K6).

`discover` reads every settings layer and MCP file Claude Code would load
for one project and returns one `Source` per file, each carrying the status
`jsonio` gave it. A file that could not be read with certainty is named with
that status instead of being skipped, so its protections are never credited.

`mcp_servers` and `mcp_approvals` only reshape what `discover` returned.
Everything here is read-only, and every value taken from a file is
untrusted: callers escape it before showing it.
"""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from typing import Any, Optional

import jsonio

SYSTEM_ROOTS = {
    "darwin": "/Library/Application Support/ClaudeCode",
    "linux": "/etc/claude-code",
}

SETTINGS_SCOPES = ("managed", "managed-dropin", "user", "project", "local")

APPROVAL_KEYS = (
    "enableAllProjectMcpServers",
    "enabledMcpjsonServers",
    "disabledMcpjsonServers",
)

_DROPIN_DIR = "managed-settings.d"


@dataclass(frozen=True)
class Source:
    """One settings or MCP file. `data` and `format` are set only for `ok`;
    `real_path` is None only for `absent`."""

    scope: str  # managed|managed-dropin|user|project|local|claude-json|mcp-json|managed-mcp
    path: str
    real_path: Optional[str]
    status: str  # absent|ok|unreadable|ambiguous|too-large|not-regular|denied
    reason: Optional[str]
    data: Optional[dict]
    format: Optional[jsonio.Format]


@dataclass(frozen=True)
class McpServer:
    """One configured server. `config` is the raw entry, None when the entry
    is not an object."""

    name: str
    origin: str  # project|user|local|managed|plugin
    scope: str  # scope of the file that declares it
    path: str
    config: Optional[dict]
    plugin: Optional[str] = None  # installed_plugins key, plugin servers only


@dataclass(frozen=True)
class McpApproval:
    """One approval key as written in one file. `observed_only` marks
    `~/.claude.json` state, which is reported but never planned against."""

    key: str
    value: Any
    scope: str
    path: str
    observed_only: bool


def default_system_root(platform):
    """The directory holding managed files, None where there is none to read."""
    return SYSTEM_ROOTS.get(platform)


def project_keys(project_dir, repo_root):
    """The paths under which `~/.claude.json` may file this project."""
    keys = []
    for directory in (project_dir, repo_root):
        if directory:
            keys.extend((os.path.abspath(directory), os.path.realpath(directory)))
    return tuple(dict.fromkeys(keys))


def discover(project_dir, repo_root, home, config_dir, system_root):
    """Return a `Source` for every settings and MCP file of this project.

    `config_dir` is the value of `CLAUDE_CONFIG_DIR`, or None when it is not
    set: it relocates both `~/.claude` and `~/.claude.json`. `system_root` is
    the managed directory (`default_system_root`), or None to skip it.
    Order: managed, its drop-ins, user, project, local (repo-root file first,
    then a legacy start-directory file if one exists), `.claude.json`,
    `.mcp.json`, managed MCP.
    """
    sources = []
    if system_root:
        sources.append(_read("managed", os.path.join(system_root, "managed-settings.json"), True))
        sources.extend(_dropins(os.path.join(system_root, _DROPIN_DIR)))
    user_dir = config_dir or os.path.join(home, ".claude")
    sources.append(_read("user", os.path.join(user_dir, "settings.json"), True))
    sources.append(_read("project", os.path.join(project_dir, ".claude", "settings.json"), False))
    sources.extend(_local(project_dir, repo_root))
    claude_json_dir = config_dir or home
    sources.append(_read("claude-json", os.path.join(claude_json_dir, ".claude.json"), True))
    sources.append(_read("mcp-json", os.path.join(project_dir, ".mcp.json"), False))
    if system_root:
        sources.append(_read("managed-mcp", os.path.join(system_root, "managed-mcp.json"), True))
    return sources


def mcp_servers(sources, plugin_servers, project_paths):
    """List every configured server with the file that declares it.

    `plugin_servers` come from the plugin inventory: mappings or objects with
    `name` and `path`, plus optional `plugin` and `config` (the inventory
    drops config values, so plugin servers usually have none); an item
    without a string `name` and `path` is skipped. `project_paths`
    (`project_keys`) select the local-scope entries of `~/.claude.json`;
    other projects are never listed.
    A name declared in two places is listed twice.
    """
    servers = []
    for source in sources:
        if source.status != "ok":
            continue
        if source.scope == "mcp-json":
            servers.extend(_servers_in(source.data, "project", source))
        elif source.scope == "managed-mcp":
            servers.extend(_servers_in(source.data, "managed", source))
        elif source.scope == "claude-json":
            servers.extend(_servers_in(source.data, "user", source))
            for entry in _project_entries(source, project_paths):
                servers.extend(_servers_in(entry, "local", source))
    for item in plugin_servers:
        name = _field(item, "name")
        path = _field(item, "path")
        if not isinstance(name, str) or not isinstance(path, str):
            continue
        config = _field(item, "config")
        plugin = _field(item, "plugin")
        servers.append(McpServer(
            name=name,
            origin="plugin",
            scope="plugin",
            path=path,
            config=config if isinstance(config, dict) else None,
            plugin=plugin if isinstance(plugin, str) else None,
        ))
    return servers


def mcp_approvals(sources, project_paths):
    """List the `.mcp.json` approval keys each readable file sets.

    Settings layers count; the per-project entries of `~/.claude.json` are
    returned as observed-only. Which entry takes effect is not decided here.
    """
    approvals = []
    for source in sources:
        if source.status != "ok":
            continue
        if source.scope in SETTINGS_SCOPES:
            approvals.extend(_approvals_in(source.data, source, False))
        elif source.scope == "claude-json":
            for entry in _project_entries(source, project_paths):
                approvals.extend(_approvals_in(entry, source, True))
    return approvals


def _read(scope, path, follow_symlink):
    status, data, fmt, reason = jsonio.read_json(path, follow_symlink)
    return _source(scope, path, status, reason, data, fmt)


def _source(scope, path, status, reason, data=None, fmt=None):
    real_path = None if status == "absent" else os.path.realpath(path)
    return Source(scope, path, real_path, status, reason, data, fmt)


def _dropins(directory):
    """Drop-ins in the order Claude Code merges them: `*.json` by name,
    hidden files skipped. A directory that cannot be listed is one source."""
    try:
        names = os.listdir(directory)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return []
        if exc.errno in (errno.EACCES, errno.EPERM):
            return [_source("managed-dropin", directory, "denied", "permission-denied")]
        if exc.errno == errno.ENOTDIR:
            return [_source("managed-dropin", directory, "not-regular", "not-regular")]
        return [_source("managed-dropin", directory, "unreadable", "io-error")]
    wanted = sorted(n for n in names if n.endswith(".json") and not n.startswith("."))
    return [_read("managed-dropin", os.path.join(directory, name), True) for name in wanted]


def _local(project_dir, repo_root):
    """The repo-root local file (written since 2.1.211), then the older
    start-directory file, which Claude Code still reads when it exists."""
    start = os.path.join(project_dir, ".claude", "settings.local.json")
    if not repo_root or os.path.realpath(repo_root) == os.path.realpath(project_dir):
        return [_read("local", start, False)]
    current = _read("local", os.path.join(repo_root, ".claude", "settings.local.json"), False)
    legacy = _read("local", start, False)
    return [current] if legacy.status == "absent" else [current, legacy]


def _servers_in(container, origin, source):
    table = container.get("mcpServers")
    if not isinstance(table, dict):
        return []
    return [
        McpServer(name, origin, source.scope, source.path,
                  config if isinstance(config, dict) else None)
        for name, config in table.items()
    ]


def _project_entries(source, project_paths):
    projects = source.data.get("projects")
    if not isinstance(projects, dict):
        return []
    entries = (projects.get(path) for path in dict.fromkeys(project_paths))
    return [entry for entry in entries if isinstance(entry, dict)]


def _approvals_in(container, source, observed_only):
    return [
        McpApproval(key, container[key], source.scope, source.path, observed_only)
        for key in APPROVAL_KEYS
        if key in container
    ]


def _field(item, name):
    """A field of a mapping or an object; None when absent."""
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)
