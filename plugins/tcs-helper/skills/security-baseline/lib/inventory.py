"""Plugin inventory (spec 025, K7, ADR-9).

`scan(home, repo_root)` walks the plugin trees and reports three things:
the installed skills, the MCP servers plugins declare, and the
tcs-git-helpers settings template. It only reads, and never the real home
by itself: `home` is always a parameter.

Skills. A skill's name is its frontmatter `name:`, never its directory.
Roots are `<repo>/.claude/skills`, `<home>/.claude/skills` and
`<home>/.claude/plugins/{cache,marketplaces}/*/*/*/skills`, walked to any
depth with symlinks followed and a `(st_dev, st_ino)` dedup applied before
descending, so a symlink loop ends and a skill reached twice is listed
once. Dot-prefixed directories are not entered. The walk approach is copied
from tcs-patterns' `guard.py`; a plugin cannot import another plugin.

Everything read here is untrusted. A name that fails `_NAME_RE` is skipped
and reported, never listed and never joined into a path. A repository can
ship a FIFO as `SKILL.md` or a symlink to `/` as a skill directory, so
files are opened non-blocking and must be regular, and each root stops
after `MAX_DIRS_PER_ROOT` directories.

Plugin MCP servers come from `installed_plugins.json`: each `installPath`
must resolve to a directory strictly inside `<home>/.claude/plugins`, and
every file read below it must resolve inside that directory. Only server
names are kept; a server's configuration can hold credentials.

The git-helpers template comes from an installed copy only: the newest
`cache/<market>/tcs-git-helpers/<version>/` by version order, else
`marketplaces/<market>/plugins/tcs-git-helpers/`, which has no version
directory. The repository's own checkout is never read, not even when it is
this repository: a cloned repository could ship that path and have its own
excluded commands reported as accepted. An unreadable best copy yields no
template rather than a lower-ranked one: without a template every excluded
command is an ordinary finding, which is the safe direction.

Whatever could not be read is listed in `Inventory.skipped` with a reason
from a fixed vocabulary, never file content.

MCP server names, plugin keys and every path, the skipped ones included,
are kept as written in the files and on disk. They are untrusted text: a
caller must put them through `render_untrusted` or a `NameTable` before
showing them (CON-5).
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

import jsonio

MAX_DIRS_PER_ROOT = 20000
MAX_SKILL_BYTES = 64 * 1024

# Used with `fullmatch`: `$` would also match before a trailing newline.
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_VERSION_RE = re.compile(r"[0-9]{1,9}(\.[0-9]{1,9}){0,5}")
_NAME_LINE_RE = re.compile(r"^name:(.*)$")
_COMMENT_RE = re.compile(r"\s#")
_FRONTMATTER_DELIM = "---"
_SKILL_FILE = "SKILL.md"
_GIT_HELPERS = "tcs-git-helpers"
_TEMPLATE_PARTS = ("templates", "claude-settings", "sandbox-git.json")
_PLUGIN_TREES = ("cache", "marketplaces")
_RANK_VERSIONED, _RANK_MARKETPLACE, _RANK_UNVERSIONED = 2, 1, 0


@dataclass(frozen=True)
class Skill:
    """One installed skill. `plugin` is set only for namespace `plugin`."""

    name: str
    namespace: str  # repo | user | plugin
    plugin: str | None
    path: str

    @property
    def qualified_name(self) -> str:
        return f"{self.plugin}:{self.name}" if self.plugin else self.name


@dataclass(frozen=True)
class PluginMcpServer:
    """An MCP server a plugin declares. `plugin` is the installed_plugins
    key and `name` the server key, both as written in the files."""

    name: str
    plugin: str
    path: str


@dataclass(frozen=True)
class GitTemplate:
    """The tcs-git-helpers settings template. `origin` is the installed
    layout it came from; `version` is None for the marketplace layout,
    which has no version directory."""

    path: str
    origin: str  # cache | marketplace
    version: str | None
    sha256: str
    excluded_commands: tuple[str, ...]
    deny_write: tuple[str, ...]
    ask: tuple[str, ...]


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str


@dataclass(frozen=True)
class Inventory:
    skills: tuple[Skill, ...]
    plugin_mcp: tuple[PluginMcpServer, ...]
    git_template: GitTemplate | None
    skipped: tuple[Skipped, ...] = ()

    @property
    def skill_names(self) -> frozenset[str]:
        """Every spelling a `Skill(<name>)` rule can use for an installed
        skill: the bare name, and `plugin:name` for a plugin skill."""
        names = set()
        for skill in self.skills:
            names.add(skill.name)
            names.add(skill.qualified_name)
        return frozenset(names)


def scan(home, repo_root) -> Inventory:
    """Read the inventory below `home` and, when given, `repo_root`. The
    repository contributes skills only, never the git-helpers template."""
    home = Path(home)
    repo = Path(repo_root) if repo_root is not None else None
    plugins_dir = home / ".claude" / "plugins"
    skipped: list[Skipped] = []
    return Inventory(
        skills=tuple(_scan_skills(home, repo, plugins_dir, skipped)),
        plugin_mcp=tuple(_scan_plugin_mcp(plugins_dir, skipped)),
        git_template=_find_git_template(plugins_dir, skipped),
        skipped=tuple(skipped),
    )


# --- skills ---------------------------------------------------------------


def _scan_skills(home, repo, plugins_dir, skipped):
    roots = []
    if repo is not None:
        roots.append(("repo", None, repo / ".claude" / "skills"))
    roots.append(("user", None, home / ".claude" / "skills"))
    roots.extend(("plugin", plugin, root) for plugin, root in _plugin_skill_roots(plugins_dir))

    seen = set()
    for namespace, plugin, root in roots:
        for skill_md in _walk_skill_files(root, skipped):
            name, reason = _skill_name(skill_md)
            if reason is not None:
                skipped.append(Skipped(str(skill_md), reason))
                continue
            key = (namespace, plugin, name)
            if key in seen:
                continue
            seen.add(key)
            yield Skill(name, namespace, plugin, str(skill_md))


def _plugin_skill_roots(plugins_dir):
    """`(plugin, skills_dir)` pairs, cache then marketplaces, sorted. The
    plugin is the directory the layout names: `cache/<market>/<plugin>/
    <version>/skills` and `marketplaces/<market>/<segment>/<plugin>/skills`."""
    for tree in _PLUGIN_TREES:
        base = plugins_dir / tree
        for root in sorted(base.glob("*/*/*/skills")):
            if _has_hidden_part(root, base):
                continue
            owner = root.parent.parent if tree == "cache" else root.parent
            yield (owner.name if _NAME_RE.fullmatch(owner.name) else None), root


def _has_hidden_part(path, base):
    return any(part.startswith(".") for part in path.relative_to(base).parts)


def _walk_skill_files(root, skipped):
    """Yield every `SKILL.md` path below `root`; see the module docstring."""
    try:
        visited = {_identity(root)}
    except OSError:
        return  # a missing root is empty, not an error
    if not root.is_dir():
        return

    def unreadable(err):
        skipped.append(Skipped(err.filename or str(root), "unreadable-directory"))

    count = 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=unreadable, followlinks=True):
        count += 1
        if count > MAX_DIRS_PER_ROOT:
            skipped.append(Skipped(str(root), "walk-limit"))
            return
        kept = []
        for name in sorted(dirnames):
            if name.startswith("."):
                continue
            child = os.path.join(dirpath, name)
            try:
                key = _identity(child)
            except OSError:
                skipped.append(Skipped(child, "unreadable-directory"))
                continue
            if key in visited:
                continue
            visited.add(key)
            kept.append(name)
        dirnames[:] = kept
        if _SKILL_FILE in filenames:
            yield Path(dirpath) / _SKILL_FILE


def _identity(path):
    st = os.stat(path)
    return st.st_dev, st.st_ino


def _skill_name(skill_md):
    """Return `(name, None)` or `(None, reason)`."""
    text = _read_skill_head(skill_md)
    if text is None:
        return None, "unreadable-skill-file"
    block = _frontmatter_lines(text)
    if block is None:
        return None, "no-frontmatter"
    matches = [m for m in map(_NAME_LINE_RE.match, block) if m is not None]
    if not matches:
        return None, "no-skill-name"
    if len(matches) > 1:
        return None, "duplicate-skill-name"
    name = _plain_scalar(matches[0].group(1))
    if not _NAME_RE.fullmatch(name):
        return None, "invalid-skill-name"
    return name, None


def _read_skill_head(path):
    """The first `MAX_SKILL_BYTES` of a regular file, or None. Non-blocking,
    so a FIFO planted as `SKILL.md` cannot stall the scan."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags)
    except (OSError, ValueError):
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        raw = _read_up_to(fd, MAX_SKILL_BYTES)
    except OSError:
        return None
    finally:
        os.close(fd)
    return raw.decode("utf-8", errors="replace")


def _read_up_to(fd, limit):
    chunks = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(fd, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _frontmatter_lines(text):
    """The lines between the first two `---` lines, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIM:
            return lines[1:index]
    return None


def _plain_scalar(raw):
    """The value of a plain or simply quoted YAML scalar. Anything else
    (block scalar, tag, anchor, escapes) comes back in a form `_NAME_RE`
    rejects, so it is skipped instead of guessed."""
    text = raw.strip()
    if text[:1] in ("'", '"'):
        quote = text[0]
        end = text.find(quote, 1)
        trailer = text[end + 1 :].strip() if end > 0 else "unterminated"
        if trailer and not trailer.startswith("#"):
            return ""
        return text[1:end]
    comment = _COMMENT_RE.search(text)
    return (text[: comment.start()] if comment else text).rstrip()


# --- plugin MCP servers ---------------------------------------------------


def _scan_plugin_mcp(plugins_dir, skipped):
    registry = plugins_dir / "installed_plugins.json"
    status, data, _fmt, reason = jsonio.read_json(str(registry), True)
    if status == "absent":
        return
    if status != "ok":
        skipped.append(Skipped(str(registry), reason or status))
        return
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return
    plugins_real = os.path.realpath(plugins_dir)
    seen = set()
    for plugin, entries in plugins.items():
        for entry in entries if isinstance(entries, list) else [entries]:
            install_path = entry.get("installPath") if isinstance(entry, dict) else None
            root, reason = _contained_dir(install_path, plugins_real)
            if root is None:
                shown = install_path if isinstance(install_path, str) else str(registry)
                skipped.append(Skipped(shown, reason))
                continue
            for server in _plugin_servers(plugin, install_path, root, skipped):
                if server not in seen:
                    seen.add(server)
                    yield server


def _contained_dir(install_path, plugins_real):
    """Return `(real_path, None)` when `install_path` is absolute and
    resolves strictly inside the plugins directory, else `(None, reason)`.
    A path that exists has to be a directory; one that does not exist is a
    stale entry and reads as a plugin without files."""
    outside = None, "install-path-outside-plugins"
    if not isinstance(install_path, str) or "\x00" in install_path:
        return outside
    if not os.path.isabs(install_path):
        return outside
    real = os.path.realpath(install_path)
    if not _is_inside(real, plugins_real):
        return outside
    if os.path.exists(real) and not os.path.isdir(real):
        return None, "install-path-not-a-directory"
    return real, None


def _is_inside(real, root_real):
    return real != root_real and os.path.commonpath([real, root_real]) == root_real


def _plugin_servers(plugin, shown_root, root_real, skipped):
    """Servers of one plugin: its `.mcp.json`, then `mcpServers` of its
    `plugin.json`. `shown_root` is the path as recorded, for reporting."""
    data, shown = _read_plugin_file(".mcp.json", shown_root, root_real, skipped)
    if data is not None:
        yield from _servers_in(data, plugin, shown)
    manifest = os.path.join(".claude-plugin", "plugin.json")
    data, shown = _read_plugin_file(manifest, shown_root, root_real, skipped)
    if data is not None:
        yield from _declared_servers(data.get("mcpServers"), shown, plugin, shown_root, root_real, skipped)


def _declared_servers(value, shown, plugin, shown_root, root_real, skipped):
    """`mcpServers` of a plugin.json: an object, a file path, or a list of both."""
    if isinstance(value, dict):
        yield from _servers_in({"mcpServers": value}, plugin, shown)
    elif isinstance(value, str):
        data, file_shown = _read_plugin_file(value, shown_root, root_real, skipped)
        if data is not None:
            yield from _servers_in(data, plugin, file_shown)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, str)):
                yield from _declared_servers(item, shown, plugin, shown_root, root_real, skipped)


def _read_plugin_file(relative, shown_root, root_real, skipped):
    """Return `(data, shown_path)` for a JSON object inside the plugin, or
    `(None, shown_path)`. A path that resolves outside the plugin is
    rejected before anything is opened."""
    shown = os.path.normpath(os.path.join(shown_root, relative))
    real = None
    if "\x00" not in relative and not os.path.isabs(relative):
        real = os.path.realpath(os.path.join(root_real, relative))
    if real is None or not _is_inside(real, root_real):
        skipped.append(Skipped(shown, "mcp-path-outside-plugin"))
        return None, shown
    status, data, _fmt, reason = jsonio.read_json(real, False)
    if status == "ok":
        return data, shown
    if status != "absent":
        skipped.append(Skipped(shown, reason or status))
    return None, shown


def _servers_in(data, plugin, shown):
    """Server names of an `.mcp.json`-shaped object: under `mcpServers`, or
    the top-level keys of the flat form."""
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {name: value for name, value in data.items() if isinstance(value, dict)}
    for name in servers:
        yield PluginMcpServer(name, plugin, shown)


# --- git-helpers template (ADR-9) ------------------------------------------


def _find_git_template(plugins_dir, skipped):
    """The best installed template, or None. Only the best candidate is
    ever opened; a repository checkout is not a candidate."""
    candidates = _installed_templates(plugins_dir)
    if not candidates:
        return None
    origin, version, path = candidates[0]
    real = os.path.realpath(path)
    if not _is_inside(real, os.path.realpath(plugins_dir)):
        skipped.append(Skipped(str(path), "template-outside-plugins"))
        return None
    return _load_template(path, real, origin, version, skipped)


def _installed_templates(plugins_dir):
    """`(origin, version, path)` of every installed template, best first:
    cache copies by version, then the marketplace layout, then a cache
    directory that is not a dotted number. Ties go to the lower path."""
    found = []
    cache = plugins_dir / "cache"
    for path in cache.glob("/".join(("*", _GIT_HELPERS, "*") + _TEMPLATE_PARTS)):
        if _has_hidden_part(path, cache):
            continue
        version = path.relative_to(cache).parts[2]
        if _VERSION_RE.fullmatch(version):
            rank = (_RANK_VERSIONED, tuple(int(part) for part in version.split(".")))
        else:
            rank, version = (_RANK_UNVERSIONED, ()), None
        found.append((rank, str(path), "cache", version, path))
    marketplaces = plugins_dir / "marketplaces"
    for path in marketplaces.glob("/".join(("*", "plugins", _GIT_HELPERS) + _TEMPLATE_PARTS)):
        if not _has_hidden_part(path, marketplaces):
            found.append(((_RANK_MARKETPLACE, ()), str(path), "marketplace", None, path))
    found.sort(key=lambda item: item[1])
    found.sort(key=lambda item: item[0], reverse=True)
    return [(origin, version, path) for _rank, _text, origin, version, path in found]


def _load_template(path, read_path, origin, version, skipped):
    status, data, _fmt, reason = jsonio.read_json(read_path, False)
    if status == "absent":
        return None
    # The digest comes from a second read: jsonio's public interface returns
    # the parsed object but not the bytes it parsed. A file replaced between
    # the two reads would be recorded with the digest of the new bytes and
    # the entries of the old. Only someone who can already write inside
    # `~/.claude/plugins` can do that, and the digest is reported, not used
    # for a decision.
    digest = _sha256(read_path) if status == "ok" else None
    if digest is None:
        skipped.append(Skipped(str(path), reason or "io-error"))
        return None
    sandbox = _object(data.get("sandbox"))
    return GitTemplate(
        path=str(path),
        origin=origin,
        version=version,
        sha256=digest,
        excluded_commands=_strings(sandbox.get("excludedCommands")),
        deny_write=_strings(_object(sandbox.get("filesystem")).get("denyWrite")),
        ask=_strings(_object(data.get("permissions")).get("ask")),
    )


def _sha256(path):
    """The digest of a regular file, or None. Non-blocking for the reason
    given at `_read_skill_head`: the file can be replaced after it parsed."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags | getattr(os, "O_BINARY", 0))
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        raw = _read_up_to(fd, jsonio.MAX_BYTES + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    return hashlib.sha256(raw).hexdigest()


def _object(value):
    return value if isinstance(value, dict) else {}


def _strings(value):
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
