"""Credential and sandbox checks C1, C4, C7, C8 (spec 025, K10).

- `check_credentials` (C1, HIGH) — every path of `credentials.json` must be
  denied twice: to the file tools by a Read deny rule, and to the commands
  the agent runs by a sandbox that really runs. One finding per path, whether
  or not the path exists on this machine.
- `check_sandbox` (C4, HIGH) — the sandbox is on, can run, fails closed and
  is not weakened.
- `check_read_outside` (C7, MED) — reads outside the working directories are
  blocked, on a Claude Code version that knows the key.
- `check_network_domains` (C8, MED) — a sandbox that is on has a network
  domain list.

Every check takes keyword arguments only and ignores the ones it does not
read, so a caller can pass one context to all of them. Each yields
`verdict.Finding` objects, passes included. The arguments are:

- `effective_of` — callable, settings key → `effective.Effective`
- `env` — `environment.Environment` (platform, Claude Code version)
- `probe` — `probe.ProbeResult`
- `credentials` — `refdata.load_credentials()`
- `keys` — `refdata.load_keys()`
- `home` — the absolute home directory
- `sources` — the `layers.Source` list (only for `sandbox.filesystem.allowRead`,
  which has no entry in `keys.json`)

A deny is credited only in a spelling `credentials.json` lists for the path;
no glob is evaluated here. A rule that names the path in any other spelling
is reported as present but unverified. `Read(.env*)`, with no slash, is
listed and credited: a bare file name follows gitignore semantics and matches
at any depth under the current directory.

Nothing here looks at the disk, and nothing credits a file that was not
read: where an unread or malformed file could change the answer, the layer is
UNKNOWN.
"""

from __future__ import annotations

import re

import probe as probe_module
import verdict

HIGH, MED = "HIGH", "MED"
PERMISSIONS, SANDBOX = "permissions", "sandbox"

DENY = "permissions.deny"
BLOCK_READS = "permissions.blockReadsOutsideWorkingDirectories"
ENABLED = "sandbox.enabled"
FAIL_IF_UNAVAILABLE = "sandbox.failIfUnavailable"
ALLOW_UNSANDBOXED = "sandbox.allowUnsandboxedCommands"
WEAKER_NESTED = "sandbox.enableWeakerNestedSandbox"
DENY_READ = "sandbox.filesystem.denyRead"
ALLOWED_DOMAINS = "sandbox.network.allowedDomains"

# Fix texts of this group, keyed by template id. `render.fix_text` takes them
# through its `templates` argument; the registry merges them into the table.
FIX_TEMPLATES = {
    "settings-unread": (
        "A settings file could not be read. Repair it, then run the audit again."
    ),
    "c1-add-read-deny": (
        "Add a Read deny rule for the credential path '{credential}' to permissions.deny "
        "in your user settings."
    ),
    "c1-use-listed-spelling": (
        "A deny for the credential path '{credential}' exists, but not in a spelling the "
        "audit can verify. Add the listed Read deny rule to your user settings."
    ),
    "c1-sandbox": (
        "File tools cannot read the credential path '{credential}', but commands still "
        "can. Turn the sandbox on and make it fail closed (check C4)."
    ),
    "c4-enable-sandbox": "Set sandbox.enabled to true in your user settings.",
    "c4-install-dependencies": (
        "Install the sandbox dependencies, then run the audit again: "
        + probe_module.INSTALL_HINT + "."
    ),
    "c4-cannot-run": (
        "The trial run of the sandbox failed, so the sandbox cannot run here. "
        "Run /sandbox in Claude Code to see why."
    ),
    "c4-confirm-sandbox": (
        "The trial run could not decide whether the sandbox can run here. "
        "Run /sandbox in Claude Code and check that it shows the sandbox active."
    ),
    "c4-remove-weaker-nested-sandbox": (
        "Remove sandbox.enableWeakerNestedSandbox: it weakens the sandbox."
    ),
    "c4-fail-closed": (
        "Set sandbox.failIfUnavailable to true and sandbox.allowUnsandboxedCommands to "
        "false, after /sandbox shows the sandbox active."
    ),
    "c7-block-reads-outside": (
        "Set permissions.blockReadsOutsideWorkingDirectories to true in your user settings."
    ),
    "c7-upgrade": (
        "Blocking reads outside the working directories needs Claude Code {min_version} "
        "or newer. Update Claude Code, then set the key."
    ),
    "c8-allowed-domains": (
        "List the domains sandboxed commands may reach in sandbox.network.allowedDomains."
    ),
}

_SETTINGS_SCOPES = ("managed", "managed-dropin", "user", "project", "local")
_READ_PREFIX = "Read("
_NEGATION = "!"
# Sandbox path wildcards are `*`, `?` and `**` (settings reference, "Where
# wildcards work in sandbox paths"). Brackets, braces and parentheses are
# literal directory names ("Directory names with brackets, braces, or
# parentheses"), so they are not metacharacters here.
_GLOB = re.compile(r"[*?]")
_ANCHORED_PREFIXES = ("~/", "//")  # a `!` carve-out cannot reach these


# --- C1 ----------------------------------------------------------------------


def check_credentials(*, env, probe, credentials, home, effective_of, sources=(), **_unused):
    """C1: one finding per credential path. Reads `permissions.deny`,
    `sandbox.filesystem.denyRead`, `sandbox.enabled`,
    `sandbox.allowUnsandboxedCommands`, the probe result, the platform and
    the `allowRead` lists of `sources`."""
    home_text = str(home)
    deny = effective_of(DENY)
    deny_read = effective_of(DENY_READ)
    lists_certain = deny.certain and deny_read.certain
    running = _sandbox_running(probe, effective_of)
    allow_read = _allow_read_paths(sources, home_text)
    listed_anywhere = {
        rule for credential in credentials
        for rule in credential.read_rule_spellings_for(home_text)
    }

    for credential in credentials:
        rules = _read_denies(credential, deny, home_text, listed_anywhere)
        sandbox_entries = _sandbox_denies(credential, deny_read, home_text)
        permissions = _layer_state(rules, deny.certain)
        sandbox, sandbox_reason = _credential_sandbox_state(
            credential, rules + sandbox_entries, lists_certain, running,
            env.platform, _reopened(credential, allow_read, home_text),
        )
        states = {PERMISSIONS: permissions, SANDBOX: sandbox}
        status = verdict.status(states)
        reason, template = _credential_reason(status, permissions)
        named = (rules + sandbox_entries)[:1]
        yield verdict.finding(
            "C1", HIGH, status,
            SANDBOX if permissions == "EFFECTIVE" and sandbox != "EFFECTIVE" else PERMISSIONS,
            evidence_key=credential.id,
            scope=named[0]["scope"] if named else "",
            file=named[0]["file"] if named else "",
            evidence={
                "credential": credential.id,
                "path": credential.path,
                "reason": reason,
                "states": states,
                "rules": rules,
                "sandbox_entries": sandbox_entries,
                "sandbox_reason": sandbox_reason,
            },
            fix=_credential_fix(template, credential.id),
        )


def _credential_fix(template, credential_id):
    if template is None:
        return None
    if template == "settings-unread":  # takes no parameter
        return _fix(template)
    return _fix(template, credential=credential_id)


def _credential_reason(status, permissions):
    """The wording of the result and the fix that goes with it."""
    if status == "PASS":
        return None, None
    if status == "FAIL":
        return "no deny rule", "c1-add-read-deny"
    if permissions == "PRESENT-INERT":
        return "present, equivalence unverified", "c1-use-listed-spelling"
    if permissions == "UNKNOWN":
        return "settings file not read", "settings-unread"
    if permissions == "ABSENT":
        return "file tools can still read", "c1-add-read-deny"
    return "commands can still read", "c1-sandbox"


def _layer_state(matches, certain):
    """State of one layer from the entries that name the path."""
    if any(match["verified"] for match in matches):
        return "EFFECTIVE"  # a deny list is a union: no other file takes an entry away
    if matches:
        return "PRESENT-INERT"
    return "ABSENT" if certain else "UNKNOWN"


def _credential_sandbox_state(credential, matches, lists_certain, running, platform, reopened):
    """`(state, reason)` of the sandbox half for one path. A Read deny rule
    also feeds the sandbox, so `matches` holds both kinds of entry."""
    covered = _layer_state(matches, lists_certain)
    if covered in ("ABSENT", "UNKNOWN"):
        return covered, "no-sandbox-deny" if covered == "ABSENT" else "settings-unread"
    running_state, running_reason = running
    if running_state != "EFFECTIVE":
        return running_state, running_reason
    if covered == "PRESENT-INERT":
        return "PRESENT-INERT", "equivalence-unverified"
    if platform == "linux" and not credential.linux_enforceable:
        return "PRESENT-INERT", "not-linux-enforceable"
    if platform not in ("linux", "darwin"):
        return "UNKNOWN", "platform-unsupported"
    if reopened:
        return "PRESENT-INERT", "allow-read-reopens"
    return "EFFECTIVE", None


def _sandbox_running(probe, effective_of):
    """`(state, reason)`: does a sandbox contain the commands the agent runs."""
    enabled = effective_of(ENABLED)
    if not enabled.certain:
        return "UNKNOWN", "settings-unread"
    if enabled.value is not True:
        return "ABSENT", "sandbox-off"
    if probe.result == "fail":
        return "PRESENT-INERT", "sandbox-cannot-run"
    if probe.result != "pass":
        return "UNKNOWN", "probe-inconclusive"
    unsandboxed = effective_of(ALLOW_UNSANDBOXED)
    if not unsandboxed.certain:
        return "UNKNOWN", "settings-unread"
    if unsandboxed.value is not False:
        return "PRESENT-INERT", "unsandboxed-commands-allowed"
    return "EFFECTIVE", None


def _read_denies(credential, deny, home, listed_anywhere):
    """Read deny rules that name the path: `verified` for a listed spelling
    that no later `!` rule of the same file carves into."""
    listed = set(credential.read_rule_spellings_for(home))
    matches = []
    for source, rules in deny.contributions:
        for index, rule in enumerate(rules):
            body = _read_body(rule)
            if body is None or body.startswith(_NEGATION):
                continue
            if rule in listed:
                verified = body.startswith(_ANCHORED_PREFIXES) or not _negated_after(rules, index)
            elif rule not in listed_anywhere and _names(credential, body):
                verified = False
            else:
                continue
            matches.append(_match("rule", rule, source, verified))
    return matches


def _sandbox_denies(credential, deny_read, home):
    """`denyRead` entries that name the path, in a listed spelling or not."""
    listed = set(credential.sandbox_spellings_for(home))
    matches = []
    for source, entries in deny_read.contributions:
        for entry in entries:
            if isinstance(entry, str) and (entry in listed or _names(credential, entry)):
                matches.append(_match("entry", entry, source, entry in listed))
    return matches


def _match(kind, text, source, verified):
    return {kind: text, "scope": source.scope, "file": source.path, "verified": verified}


def _read_body(rule):
    """`Read(x)` → `x`; None for anything else."""
    if not isinstance(rule, str) or not rule.startswith(_READ_PREFIX) or not rule.endswith(")"):
        return None
    return rule[len(_READ_PREFIX):-1]


def _negated_after(rules, index):
    return any((_read_body(later) or "").startswith(_NEGATION) for later in rules[index + 1:])


def _names(credential, text):
    """Whether `text` holds the path's own segments in a row (`.config/gh`).
    A path that ends in `*` (`.env*`) is named by any segment with its prefix."""
    tail = credential.path
    for anchor in ("~/", "**/"):
        if tail.startswith(anchor):
            tail = tail[len(anchor):]
    by_prefix = tail.endswith("*")
    wanted = tail.rstrip("*").split("/")
    segments = [segment for segment in text.split("/") if segment]
    for start in range(len(segments) - len(wanted) + 1):
        window = segments[start:start + len(wanted)]
        last_fits = window[-1].startswith(wanted[-1]) if by_prefix else window[-1] == wanted[-1]
        if window[:-1] == wanted[:-1] and last_fits:
            return True
    return False


def _allow_read_paths(sources, home):
    """Absolute `sandbox.filesystem.allowRead` entries of the readable
    settings files. Relative entries resolve below a project or `~/.claude`
    and are left out."""
    paths = []
    for source in sources:
        if source.scope not in _SETTINGS_SCOPES or source.status != "ok":
            continue
        entries = _member(_member(_member(source.data, "sandbox"), "filesystem"), "allowRead")
        for entry in entries if isinstance(entries, list) else ():
            path = _absolute(entry, home)
            if path is not None:
                paths.append(path)
    return paths


def _member(node, name):
    return node.get(name) if isinstance(node, dict) else None


def _absolute(entry, home):
    """A sandbox path as an absolute path without trailing slash, or None."""
    if not isinstance(entry, str):
        return None
    if entry == "~" or entry.startswith("~/"):
        entry = home + entry[1:]
    if not entry.startswith("/"):
        return None
    return "/" + entry.strip("/")


def _reopened(credential, allow_read, home):
    """Whether an `allowRead` entry lies at or under the path, or is a glob
    that could match it. An allow of a wider directory does not reopen a
    deny: the narrower rule applies."""
    if not credential.path.startswith("~/"):
        return False
    base = _absolute(credential.path, home)
    for path in allow_read:
        if path == base or path.startswith(base + "/"):
            return True
        if _GLOB.search(path) and _glob_reopens(path, base):
            return True
    return False


def _glob_reopens(path, base):
    """Whether an `allowRead` glob could be a narrower rule than the denied
    `base`. A glob that is only a wildcard below an ancestor directory
    (`~/**`, `~/*`, `/**`) is wider, so the deny holds. A glob whose literal
    prefix ends inside the credential's own name (`~/.s*`) cannot be shown
    wider, and so is conservatively treated as reopening it."""
    match = _GLOB.search(path)
    prefix, rest = path[:match.start()], path[match.start() + 1:]
    if not base.startswith(prefix):
        return False
    wider = prefix.endswith("/") and match.group() == "*" and rest.strip("*") == ""
    return not wider


# --- C4 ----------------------------------------------------------------------


def check_sandbox(*, probe, effective_of, **_unused):
    """C4: one finding. Reads `sandbox.enabled`, `failIfUnavailable`,
    `allowUnsandboxedCommands`, `enableWeakerNestedSandbox` and the probe."""
    enabled = effective_of(ENABLED)
    fail_closed = effective_of(FAIL_IF_UNAVAILABLE)
    unsandboxed = effective_of(ALLOW_UNSANDBOXED)
    weaker = effective_of(WEAKER_NESTED)

    if not enabled.certain:
        enabled_state, enabled_gap = "UNKNOWN", "settings-unread"
    elif enabled.value is True:
        enabled_state, enabled_gap = "EFFECTIVE", None
    else:
        enabled_state, enabled_gap = "ABSENT", "sandbox-off"
    parts = [
        ("enabled", enabled_state, enabled_gap),
        ("probe", *_PROBE_STATES.get(probe.result, _PROBE_STATES["inconclusive"])),
        ("enableWeakerNestedSandbox",
         *_key_state(weaker, False, "PRESENT-INERT", "weaker-nested-sandbox")),
        ("failIfUnavailable", *_key_state(fail_closed, True, "ABSENT", "fail-if-unavailable-off")),
        ("allowUnsandboxedCommands",
         *_key_state(unsandboxed, False, "ABSENT", "unsandboxed-commands-allowed")),
    ]
    gaps = [gap for _name, _state, gap in parts if gap is not None]
    # A sandbox that is off, or not known to be on, is not made better by
    # the rest: only an enabled sandbox is rated on its other parts.
    rated = parts if enabled_state == "EFFECTIVE" else parts[:1]
    states = {name: state for name, state, _gap in rated}

    probe_evidence = {
        "result": probe.result, "reason": probe.reason, "missing": list(probe.missing),
    }
    if probe.missing:
        probe_evidence["install_hint"] = probe_module.INSTALL_HINT
    template = _sandbox_fix(enabled_state, probe, gaps)
    yield verdict.finding(
        "C4", HIGH, verdict.status(states), SANDBOX,
        evidence_key="sandbox",
        scope=enabled.winner.scope if enabled.winner else "",
        file=enabled.winner.path if enabled.winner else "",
        evidence={
            "reason": gaps[0] if gaps else None,
            "gaps": gaps,
            "states": states,
            "effective": {
                item.key: item.value for item in (enabled, fail_closed, unsandboxed, weaker)
            },
            "set_in": [
                {"scope": source.scope, "file": source.path, "value": value}
                for source, value in enabled.contributions
            ],
            "overridden_by": [
                {"key": item.key, **entry}
                for item in (enabled, fail_closed, unsandboxed, weaker)
                for entry in _overridden_by(item)
            ],
            "probe": probe_evidence,
        },
        fix=None if template is None else _fix(template),
    )


_PROBE_STATES = {
    "pass": ("EFFECTIVE", None),
    "fail": ("PRESENT-INERT", "sandbox-cannot-run"),
    "inconclusive": ("UNKNOWN", "probe-inconclusive"),
}


def _key_state(item, wanted, otherwise, gap):
    """`(state, gap)` of a boolean key that must be `wanted`."""
    if not item.certain:
        return "UNKNOWN", "settings-unread"
    if item.value is wanted:
        return "EFFECTIVE", None
    return otherwise, gap


def _sandbox_fix(enabled_state, probe, gaps):
    """The first step that helps; `gaps` lists everything that is open."""
    if not gaps:
        return None
    if enabled_state == "UNKNOWN":
        return "settings-unread"
    if probe.result == "fail":
        return "c4-install-dependencies" if probe.missing else "c4-cannot-run"
    if probe.result != "pass":
        return "c4-confirm-sandbox"
    if enabled_state == "ABSENT":
        return "c4-enable-sandbox"
    if "weaker-nested-sandbox" in gaps:
        return "c4-remove-weaker-nested-sandbox"
    return "c4-fail-closed"


# --- C7 ----------------------------------------------------------------------


def check_read_outside(*, env, keys, effective_of, **_unused):
    """C7: one finding. Reads `permissions.blockReadsOutsideWorkingDirectories`,
    its minimum version from `keys` and the Claude Code version."""
    minimum = keys.rules[BLOCK_READS].min
    version = env.claude_version
    item = effective_of(BLOCK_READS)

    upgrade = _fix("c7-upgrade", min_version=minimum)
    if version is not None and _is_older(version, minimum):
        state, reason, fix = "UNKNOWN", "version-unsupported", upgrade
    elif item.value is True and version is None:
        state, reason, fix = "UNKNOWN", "version-unknown", upgrade
    elif item.value is True:
        # The strict value holds from any file, whatever an unread one says.
        state, reason, fix = "EFFECTIVE", None, None
    elif not item.certain:
        state, reason, fix = "UNKNOWN", "settings-unread", _fix("settings-unread")
    else:
        state, reason, fix = "ABSENT", "not-enabled", _fix("c7-block-reads-outside")

    yield verdict.finding(
        "C7", MED, verdict.status({PERMISSIONS: state}), PERMISSIONS,
        evidence_key=BLOCK_READS,
        scope=item.winner.scope if item.winner else "",
        file=item.winner.path if item.winner else "",
        evidence={
            "reason": reason,
            "states": {PERMISSIONS: state},
            "effective": {BLOCK_READS: item.value},
            "overridden_by": _overridden_by(item),
            "min_version": minimum,
            "claude_version": None if version is None else str(version),
        },
        fix=fix,
    )


def _is_older(version, minimum):
    wanted = tuple(int(part) for part in minimum.split("."))
    return (version.major, version.minor, version.patch) < wanted


# --- C8 ----------------------------------------------------------------------


def check_network_domains(*, effective_of, **_unused):
    """C8: one finding while the sandbox is on, none otherwise. Reads
    `sandbox.enabled` and `sandbox.network.allowedDomains`. A list that is set
    counts even when it is empty: nothing is pre-approved then."""
    # An uncertain `sandbox.enabled` also stays silent here: C4 reports that
    # case as UNKNOWN, so the question is not lost.
    if effective_of(ENABLED).value is not True:
        return
    domains = effective_of(ALLOWED_DOMAINS)
    if domains.contributions:
        state, reason, fix = "EFFECTIVE", None, None
    elif not domains.certain:
        state, reason, fix = "UNKNOWN", "settings-unread", _fix("settings-unread")
    else:
        state, reason, fix = "ABSENT", "no-allowed-domains", _fix("c8-allowed-domains")
    first = domains.contributions[0][0] if domains.contributions else None
    yield verdict.finding(
        "C8", MED, verdict.status({SANDBOX: state}), SANDBOX,
        evidence_key=ALLOWED_DOMAINS,
        scope=first.scope if first else "",
        file=first.path if first else "",
        evidence={
            "reason": reason,
            "states": {SANDBOX: state},
            "domains": len(domains.value),
        },
        fix=fix,
    )


def _overridden_by(item):
    """The lower files whose value the winner overrode: `{scope, file, value}`
    each, for the report to name next to the winning file."""
    return [
        {"scope": source.scope, "file": source.path, "value": value}
        for source, value in item.shadowed_by
    ]


def _fix(template, **params):
    return {"template": template, "params": params}
