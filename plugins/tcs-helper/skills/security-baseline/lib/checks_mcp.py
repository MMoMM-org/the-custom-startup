"""MCP, excluded-command, hygiene and clone-risk checks (spec 025, K10).

Five checks, each a generator of `verdict.Finding`:

- `check_mcp` (C6) — `enableAllProjectMcpServers` effective true is HIGH and
  lists the `.mcp.json` servers it approves; no `allowedMcpServers` in any
  file is MED with no automatic fix.
- `check_container_mcp` (C6x) — in the container profile with bypass active,
  `.mcp.json` servers start without an approval prompt; HIGH naming the ones
  no `disabledMcpjsonServers` entry rejects. Never accepted.
- `check_excluded_commands` (C9) — every `sandbox.excludedCommands` entry is
  MED. An entry that is exactly an entry of the installed tcs-git-helpers
  template carries `evidence["template_match"] is True`, which is what
  `verdict.finalise` accepts; every other entry carries False.
- `check_hygiene` (C10) — a `Skill(<name>)` allow rule naming no installed
  skill is LOW.
- `check_clone_risk` (CR) — one INFO finding per key and file for project or
  local settings that can run code or redirect Claude Code.

Every check takes keyword arguments only and ignores the ones it does not
read, so the registry can hand all checks the same context. Each docstring
names what the check reads.

A check that finds no gap yields nothing. A file that could not be read is
never credited: the finding it could have changed is reported UNKNOWN at the
check's base severity (ADR-4).

Everything taken from a file is untrusted (ADR-8). Evidence is rendered
here: strings go through `render.render_untrusted`, and the values of CR
findings through `render.redact` first, so `env` values and helper commands
never leave this module. Nothing here touches the filesystem: a skill name
is only compared with the names the inventory found, never joined to a
path, and one that breaks the name rule is shown only inside its escaped
rule.
"""

from __future__ import annotations

import re

import layers
import render
import verdict

ENABLE_ALL = "enableAllProjectMcpServers"
REJECTED_SERVERS = "disabledMcpjsonServers"
ALLOWLIST = "allowedMcpServers"
EXCLUDED_COMMANDS = "sandbox.excludedCommands"
ALLOW_RULES = "permissions.allow"
DEFAULT_MODE = "permissions.defaultMode"
BYPASS_MODE = "bypassPermissions"

CLONE_RISK_KEYS = ("hooks", "statusLine", "apiKeyHelper", "env", ENABLE_ALL)
CLONE_SCOPES = ("project", "local")
CONTAINER_PROFILE = "container"

# Fix texts of this group; the registry merges them into `render.FIX_TEMPLATES`.
FIX_TEMPLATES = {
    "mcp-approve-by-name": (
        "Replace enableAllProjectMcpServers with enabledMcpjsonServers naming the servers "
        "approved today."
    ),
    "mcp-reject-by-name": (
        "Reject each listed server by name in disabledMcpjsonServers, or remove it from "
        ".mcp.json."
    ),
    "remove-stale-allow-rule": "Remove this allow rule: no installed skill has that name.",
}

_MCP_JSON_SCOPE = "mcp-json"
_READ_WITH_CERTAINTY = ("ok", "absent")
_SKILL_RULE_RE = re.compile(r"Skill\((.*)\)", re.DOTALL)
_ARGUMENT_WILDCARD = ":*"
# A private copy of the inventory's name rule, optionally prefixed by a plugin name.
_SKILL_NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
_SKILL_NAME_RE = re.compile(rf"(?:{_SKILL_NAME}:)?{_SKILL_NAME}")


def check_mcp(*, sources, effective_of, **_unread):
    """C6. Reads `sources` (the `.mcp.json` file) and `effective_of` for
    `enableAllProjectMcpServers`, `disabledMcpjsonServers` and
    `allowedMcpServers`."""
    yield from _enable_all(sources, effective_of)
    yield from _allowlist(effective_of)


def check_container_mcp(*, sources, env, effective_of, **_unread):
    """C6x. Reads `env` (profile, bypass), `sources` (the `.mcp.json` file) and
    `effective_of` for `disabledMcpjsonServers` and `permissions.defaultMode`."""
    if env.profile != CONTAINER_PROFILE:
        return
    bypass = _bypass_active(env, effective_of)
    if bypass == "no":
        return
    names, mcp_json = project_servers(sources)
    rejections = effective_of(REJECTED_SERVERS)
    unrejected = _without_rejected(names, rejections)
    readable = mcp_json.status in _READ_WITH_CERTAINTY
    if readable and not unrejected:
        return
    proven = bypass == "yes" and readable and rejections.certain
    yield verdict.finding(
        "C6x", "HIGH", "FAIL" if proven else "UNKNOWN", "mcp",
        evidence_key=mcp_json.path,
        scope=mcp_json.scope,
        file=mcp_json.path,
        evidence={
            "servers": render.render_untrusted(unrejected),
            "mcp_json": mcp_json.status,
            "bypass_active": bypass,
            **_uncertainty(rejections),
        },
        fix={"template": "mcp-reject-by-name", "params": {}},
    )


def check_excluded_commands(*, inventory, effective_of, **_unread):
    """C9. Reads `effective_of` for `sandbox.excludedCommands` and
    `inventory.git_template`."""
    excluded = effective_of(EXCLUDED_COMMANDS)
    template = inventory.git_template
    about_template = {"template_found": template is not None}
    if template is not None:
        about_template["template_sha256"] = template.sha256
        about_template["template_origin"] = template.origin
    for source, entry in _entries(excluded):
        matches = (
            template is not None
            and isinstance(entry, str)
            and entry in template.excluded_commands
        )
        yield verdict.finding(
            "C9", "MED", "FAIL", "sandbox",
            evidence_key=_entry_key(source, entry),
            scope=source.scope,
            file=source.path,
            evidence={
                "entry": render.render_untrusted(entry),
                verdict.TEMPLATE_MATCH: matches,
                **about_template,
            },
        )
    if not excluded.certain:
        yield _unknown("C9", "MED", "sandbox", EXCLUDED_COMMANDS, excluded)


def check_hygiene(*, inventory, effective_of, **_unread):
    """C10. Reads `effective_of` for `permissions.allow`, and
    `inventory.skill_names` and `inventory.skipped`."""
    installed = inventory.skill_names
    complete = not inventory.skipped
    for source, rule in _entries(effective_of(ALLOW_RULES)):
        name = _skill_named_by(rule)
        if name is None:
            continue
        valid = _SKILL_NAME_RE.fullmatch(name) is not None
        if valid and name in installed:
            continue
        evidence = {"rule": render.render_untrusted(rule)}
        if valid:
            evidence["skill"] = name  # plain by the name rule; an invalid name stays in `rule`
        evidence["reason"] = "not-installed" if valid else "invalid-name"
        yield verdict.finding(
            "C10", "LOW", "FAIL" if complete or not valid else "UNKNOWN", "permissions",
            evidence_key=_entry_key(source, rule),
            scope=source.scope,
            file=source.path,
            evidence=evidence,
            fix={"template": "remove-stale-allow-rule", "params": {}},
        )


def check_clone_risk(*, sources, **_unread):
    """CR. Reads the project and local settings files among `sources`.

    A file that could not be read yields nothing here; it is named in the
    coverage block. A key is reported whatever its value, including
    `enableAllProjectMcpServers: false`.
    """
    for source in sources:
        if source.scope not in CLONE_SCOPES or source.status != "ok":
            continue
        for key in CLONE_RISK_KEYS:
            if key not in source.data:
                continue
            value = source.data[key]
            yield verdict.finding(
                "CR", "INFO", "FAIL", "mcp" if key == ENABLE_ALL else "environment",
                evidence_key="\0".join((key, source.scope, source.path)),
                scope=source.scope,
                file=source.path,
                evidence={
                    "key": key,
                    "value": render.render_untrusted(render.redact("/" + key, value)),
                },
            )


def project_servers(sources):
    """`(names, source)` for the project's `.mcp.json`: the server names as
    written in the file (untrusted), and the file's `layers.Source`. Names
    are empty unless the file was read."""
    mcp_json = next((s for s in sources if s.scope == _MCP_JSON_SCOPE), None)
    if mcp_json is None:
        mcp_json = layers.Source(
            scope=_MCP_JSON_SCOPE, path="", real_path=None, status="absent",
            reason=None, data=None, format=None,
        )
    servers = layers.mcp_servers([mcp_json], (), ())
    return tuple(server.name for server in servers), mcp_json


def approved_project_servers(sources, effective_of):
    """The `.mcp.json` server names `enableAllProjectMcpServers` approves:
    all of them but the ones `disabledMcpjsonServers` rejects. Raw names, for
    the planner; render them before showing."""
    names, _mcp_json = project_servers(sources)
    return _without_rejected(names, effective_of(REJECTED_SERVERS))


def _enable_all(sources, effective_of):
    enable_all = effective_of(ENABLE_ALL)
    if enable_all.value is not True:
        if not enable_all.certain:
            yield _unknown("C6", "HIGH", "mcp", ENABLE_ALL, enable_all)
        return
    _names, mcp_json = project_servers(sources)
    winner = enable_all.winner
    yield verdict.finding(
        "C6", "HIGH", "FAIL", "mcp",
        evidence_key=ENABLE_ALL,
        scope=winner.scope,
        file=winner.path,
        evidence={
            "key": ENABLE_ALL,
            "approved_servers": render.render_untrusted(approved_project_servers(sources, effective_of)),
            "mcp_json": mcp_json.status,
            **_uncertainty(enable_all),
        },
        fix={"template": "mcp-approve-by-name", "params": {}},
    )


def _allowlist(effective_of):
    allowlist = effective_of(ALLOWLIST)
    if allowlist.contributions:
        return
    if not allowlist.certain:
        yield _unknown("C6", "MED", "mcp", ALLOWLIST, allowlist)
        return
    yield verdict.finding(
        "C6", "MED", "FAIL", "mcp",
        evidence_key=ALLOWLIST,
        evidence={"key": ALLOWLIST},
    )


def _bypass_active(env, effective_of):
    """yes | no | unknown: the session flag, or bypass as the default mode of
    a file Claude Code honours it in."""
    default_mode = effective_of(DEFAULT_MODE)
    if env.bypass_active == "yes" or default_mode.value == BYPASS_MODE:
        return "yes"
    if env.bypass_active != "no" or not default_mode.certain:
        return "unknown"
    return "no"


def _without_rejected(names, rejections):
    rejected = {entry for entry in rejections.value if isinstance(entry, str)}
    return [name for name in names if name not in rejected]


def _entries(union):
    """`(source, entry)` for every entry of a list key, each distinct entry
    once per file, highest file first."""
    for source, entries in union.contributions:
        seen = set()
        for entry in entries:
            identity = (type(entry).__name__, repr(entry))
            if identity not in seen:
                seen.add(identity)
                yield source, entry


def _entry_key(source, entry):
    return "\0".join((source.scope, source.path, type(entry).__name__, repr(entry)))


def _skill_named_by(rule):
    """The one skill a `Skill(...)` rule names, or None when the rule is not
    a skill rule or covers a pattern of names."""
    if not isinstance(rule, str):
        return None
    match = _SKILL_RULE_RE.fullmatch(rule)
    words = match[1].split() if match else []
    if not words:
        return None
    name = words[0]
    if name.endswith(_ARGUMENT_WILDCARD):
        name = name[: -len(_ARGUMENT_WILDCARD)]
    if not name or "*" in name:
        return None
    return name


def _uncertainty(value):
    """Evidence naming the files that could have changed an effective value
    but were not read, or hold the key in a malformed shape."""
    evidence = {}
    if value.unknown:
        evidence["unread"] = list(dict.fromkeys(source.scope for source in value.unknown))
    if value.malformed:
        evidence["malformed"] = list(dict.fromkeys(source.scope for source, _ in value.malformed))
    return evidence


def _unknown(check, severity, layer, key, value):
    return verdict.finding(
        check, severity, "UNKNOWN", layer,
        evidence_key=key + "\0unknown",
        evidence={"key": key, **_uncertainty(value)},
    )
