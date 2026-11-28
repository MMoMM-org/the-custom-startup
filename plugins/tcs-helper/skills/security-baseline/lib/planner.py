"""Findings to proposed changes, per settings file (spec 025, K12, ADR-2, ADR-6).

`compute_plan` turns the findings of one audit run into a `Plan`: at most one
`TargetPlan` for each of the three files setup may write (user, project,
local), each with its changes, the object and hashes of what `apply` would
write, and a diff. `plan_id` is the identity of exactly that: `apply`
recomputes the plan from live files with the stored selection and refuses
when the id differs.

What is proposed (check catalogue, "setup proposes"):

- C1: one Read deny rule per credential path, user settings.
- C2: `permissions.disableBypassPermissionsMode`, user settings; never in the
  container profile.
- C4: `sandbox.enabled` after a passed probe; `failIfUnavailable` and
  `allowUnsandboxedCommands: false` only with `sandbox_confirmed` as well.
  `enableWeakerNestedSandbox` is never touched.
- C7: `permissions.blockReadsOutsideWorkingDirectories`, user settings, when
  the Claude Code version is known to support it.
- C3, C10: removal of the whole rule, in the file it is in, not selected.
- C6: `enableAllProjectMcpServers` removed where it is true, and the servers
  it approves today named in `enabledMcpjsonServers`. No allowlist.
- Everything else, managed settings, and any allow rule: nothing.

Selection: an addition is selected by default, a removal is not, and neither
is a change that would overwrite a value the file already holds
(`deliberate-difference`) nor any change whose own file is the project file.
`selection` (`{"select": [...], "deselect": [...]}`) overrides the default
per change id; `moves` (`{id: scope}`) puts an addition into another file.

A change id is `<scope>:<pointer>:<sha8 of the value>`, with the scope the
change has by default. It stays the same when the change is moved, so the id
the developer was shown is the id the next run takes.

Values are added or removed, never narrowed or rewritten: when the place a
change would go holds something of the wrong type, the change is not made.

Nothing here writes. `load_targets` reads the three files' bytes;
everything else works on what it is given.
"""

from __future__ import annotations

import copy
import dataclasses
import difflib
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

import checks_mcp
import effective
import jsonio
import refdata
import render

SCHEMA = 1
SCOPES = ("user", "project", "local")  # the order targets are listed and written in
DEFAULT_FORMAT = jsonio.Format(2, "\n", True)  # a new file; the writer uses the same

REASON_VERSION = "version"
REASON_PROBE = "probe"
REASON_CONFIRMATION = "confirmation"
REASON_MANAGED = "managed-only"
REASON_NO_AUTO_FIX = "no-auto-fix"

FLAG_DIFFERENCE = "deliberate-difference"
FLAG_MOVED = "moved"
FLAG_CONFIRMED = "requires-sandbox-confirmed"

CONSENT_NOTE = (
    "apply writes exactly what these diffs show: it recomputes the plan from the live files "
    "and writes nothing when anything differs. The plan is single-use and expires after 15 "
    "minutes. This does not prove that a human said yes: the model shares the shell."
)
CONSENT_NOTE_BYPASS = (
    CONSENT_NOTE
    + " Bypass mode is active or could not be ruled out, so no permission prompt guards apply."
)

DENY = "/permissions/deny"
ALLOW = "/permissions/allow"
DISABLE_BYPASS = "/permissions/disableBypassPermissionsMode"
BLOCK_READS = "/permissions/blockReadsOutsideWorkingDirectories"
SANDBOX_ENABLED = "/sandbox/enabled"
FAIL_IF_UNAVAILABLE = "/sandbox/failIfUnavailable"
ALLOW_UNSANDBOXED = "/sandbox/allowUnsandboxedCommands"
ENABLE_ALL = "/enableAllProjectMcpServers"
ENABLED_SERVERS = "/enabledMcpjsonServers"

LIST_POINTERS = (DENY, ALLOW, ENABLED_SERVERS)
SANDBOX_PREFIX = "/sandbox/"

_DISABLE_KEY = "permissions.disableBypassPermissionsMode"
_MODE_KEY = "permissions.defaultMode"
_BYPASS_MODE = "bypassPermissions"
_CONTAINER = "container"
_MANAGED_SCOPES = ("managed", "managed-dropin")
_MCP_JSON = "mcp-json"
_READ_WITH_CERTAINTY = ("ok", "absent")
_FAIL_CLOSED_GAPS = (
    ("fail-if-unavailable-off", FAIL_IF_UNAVAILABLE, True),
    ("unsandboxed-commands-allowed", ALLOW_UNSANDBOXED, False),
)
_CONTEXT_LINES = 3
_ESCAPE_CHUNK = 8  # eight characters never reach render's string limit, however escaped
_ABSENT = object()


class SelectionError(ValueError):
    """`selection` or `moves` cannot be used. `reason` is `unknown-id`,
    `conflict`, `bad-scope` or `not-movable`; `ids` are the change ids."""

    def __init__(self, reason: str, ids):
        super().__init__(reason)
        self.reason = reason
        self.ids = tuple(ids)


@dataclass(frozen=True)
class TargetFile:
    """One of the three files as it is now. `raw` is the bytes read, None
    for a missing file; `data` and `format` are set only for status `ok`."""

    scope: str
    path: str
    real_path: str
    status: str  # a `layers.Source` status, or `changed`
    reason: Optional[str]
    data: Optional[dict]
    format: Optional[jsonio.Format]
    raw: Optional[bytes]


@dataclass(frozen=True)
class Snapshot:
    """What one plan is computed from; read-only."""

    sources: tuple
    environment: Any  # environment.Environment
    probe: Any  # probe.ProbeResult
    keys: Any  # refdata.Keys
    credentials: tuple
    home: str
    targets: Mapping[str, TargetFile]


@dataclass(frozen=True)
class Change:
    id: str
    kind: str  # add | remove | set
    pointer: str
    value: Any  # the entry of a list, or the value of a key
    from_finding: str
    check: str
    default_selected: bool
    selected: bool
    flags: tuple = ()


@dataclass(frozen=True)
class TargetPlan:
    """One file and what would happen to it. `expected` is the object
    `apply` writes, laid out as `format` (None: `DEFAULT_FORMAT`); it is
    None when nothing is written. `pre_sha256` is None for a missing file."""

    scope: str
    path: str
    real_path: str
    pre_sha256: Optional[str]
    post_sha256: Optional[str]
    changes: tuple
    writable: str  # ok | refused
    refuse_reason: Optional[str]
    current: Optional[dict] = None
    expected: Optional[dict] = None
    format: Optional[jsonio.Format] = None
    reformatted: bool = False
    diff: str = ""

    @property
    def writes(self) -> bool:
        return self.expected is not None


@dataclass(frozen=True)
class Plan:
    plan_id: str
    plan_short: str
    targets: tuple
    not_proposed: tuple  # of {"finding_id", "reason"[, "min_version"]}
    self_allow_warning: bool
    consent_note: str


@dataclass(frozen=True)
class _Proposal:
    origin: str  # the scope the change has by default
    pointer: str
    value: Any
    remove: bool
    finding: Any
    selected: bool = True
    movable: bool = True
    flags: tuple = ()

    @property
    def id(self) -> str:
        return change_id(self.origin, self.pointer, self.value)


# =============================================================================
# Reading the targets
# =============================================================================


def read_raw(path, follow_symlink) -> Optional[bytes]:
    """The bytes of a regular file, None when it is missing or cannot be
    read. Opened the way `jsonio.read_json` opens it."""
    target = os.path.realpath(path) if follow_symlink else path
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(target, flags)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            if sum(map(len, chunks)) > jsonio.MAX_BYTES:
                return None
    except OSError:
        return None
    finally:
        os.close(fd)


def load_targets(sources, paths=None, read: Callable = read_raw) -> dict:
    """`{scope: TargetFile}` for the user, project and local settings files.

    `sources` come from `layers.discover`; the first file of a scope is the
    one written (for local: the repository-root file). `paths` (`{scope:
    path}`, from `writer.allowed_targets`) names the file the writer accepts;
    a scope whose discovered file is another one is not readable here.

    The bytes are read after the settings were parsed. When they no longer
    hold what was parsed, the target has status `changed`.
    """
    targets = {}
    for scope in SCOPES:
        source = next(
            (s for s in sources if s.scope == scope and _is_path(s.path, paths, scope)), None,
        )
        if source is None:
            path = paths[scope] if paths and scope in paths else ""
            targets[scope] = TargetFile(
                scope, path, os.path.realpath(path), "unreadable", "not-a-target", None, None, None,
            )
            continue
        raw = read(source.path, scope == "user")
        status, reason = source.status, source.reason
        if not _same_content(source, raw):
            status, reason = "changed", "changed-while-reading"
        ok = status == "ok"
        targets[scope] = TargetFile(
            scope, source.path, source.real_path or os.path.realpath(source.path),
            status, reason, source.data if ok else None, source.format if ok else None, raw,
        )
    return targets


def _is_path(path, paths, scope):
    return not paths or scope not in paths or os.path.abspath(path) == os.path.abspath(paths[scope])


def _same_content(source, raw):
    if source.status == "absent":
        return raw is None
    if source.status != "ok":
        return True
    if raw is None:
        return False
    try:
        return json.loads(raw.decode("utf-8")) == source.data
    except (ValueError, RecursionError):
        return False


# =============================================================================
# The plan
# =============================================================================


def compute_plan(snapshot, findings, selection, moves, sandbox_confirmed, tool_version,
                 refusal=None) -> Plan:
    """The whole plan for one run. `plan` and `apply` both call this; given
    the same files, selection, moves and flags it returns the same `plan_id`.

    `findings` are the `verdict.Finding` objects of `checks.run_all`, before
    rendering. `refusal(scope, path)` returns a code when the writer would
    refuse that file, else None.
    """
    targets, not_proposed = build(
        snapshot, findings, selection, moves, sandbox_confirmed, refusal=refusal,
    )
    identity = plan_id(snapshot, targets, sandbox_confirmed, tool_version)
    short = identity[:8]
    targets = tuple(
        dataclasses.replace(target, diff=render_diff(target, snapshot.environment, short))
        for target in targets
    )
    return Plan(
        plan_id=identity,
        plan_short=short,
        targets=targets,
        not_proposed=not_proposed,
        self_allow_warning=self_allow_warning(findings),
        consent_note=consent_note(snapshot),
    )


def build(snapshot, findings, selection, moves, sandbox_confirmed, refusal=None):
    """`(targets, not_proposed)`: the files with a change, in `SCOPES` order
    and without diffs, and one entry for every finding nothing is proposed
    for. Raises `SelectionError`."""
    effective_of = _effective_of(snapshot)
    proposals, reasons, handled = {}, [], set()
    for item in findings:
        if item.status == "PASS":
            continue
        handler = _HANDLERS.get(item.check)
        made, why = handler(item, snapshot, sandbox_confirmed, effective_of) if handler else ((), ())
        for proposal in made:
            if not _applies(proposal, snapshot.targets[proposal.origin]):
                continue
            handled.add(item.id)
            proposals.setdefault(proposal.id, proposal)
        for reason in why:
            reasons.append({"finding_id": item.id, **reason})
            handled.add(item.id)
        if item.id not in handled:
            reasons.append({"finding_id": item.id, "reason": REASON_NO_AUTO_FIX})

    select, deselect, moves = _checked_selection(proposals, selection, moves)
    misplaced = [
        i for i, scope in moves.items()
        if not _fits(proposals[i], snapshot.targets[scope].data or {})
    ]
    if misplaced:  # the other file holds something of the wrong type there
        raise SelectionError("not-movable", misplaced)
    targets = []
    for scope in SCOPES:
        placed = [p for p in proposals.values() if moves.get(p.id, p.origin) == scope]
        if placed:
            targets.append(_target_plan(snapshot.targets[scope], placed, select, deselect, refusal))
    return tuple(targets), tuple(_distinct(reasons))


def plan_id(snapshot, targets, sandbox_confirmed, tool_version) -> str:
    """sha256 over everything that decides what `apply` writes (ADR-2)."""
    env = snapshot.environment
    doc = {
        "tool": tool_version,
        "schema": SCHEMA,
        "profile": [env.profile, env.profile_source],
        "claude_version": str(env.claude_version),
        "probe": snapshot.probe.result,
        "sandbox_confirmed": sandbox_confirmed,
        "targets": [
            {
                "scope": target.scope,
                "real_path": target.real_path,
                "pre": target.pre_sha256,
                "post": target.post_sha256,
                "ops": [[c.kind, c.pointer, c.value] for c in target.changes if c.selected],
            }
            for target in sorted(targets, key=lambda target: target.scope)
        ],
    }
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def change_id(scope, pointer, value) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    return f"{scope}:{pointer}:{hashlib.sha256(text.encode('ascii')).hexdigest()[:8]}"


def holds_sandbox_keys(targets) -> bool:
    """Whether the plan writes a sandbox key: `apply` then runs the probe again."""
    return any(
        change.selected and change.pointer.startswith(SANDBOX_PREFIX)
        for target in targets if target.writes
        for change in target.changes
    )


def self_allow_warning(findings) -> bool:
    """Whether an allow rule lets `apply` run without a permission prompt:
    all of Bash, or any python command."""
    for item in findings:
        evidence = item.evidence
        if item.check != "C3" or evidence.get("tool") != "Bash" or evidence.get("shadowed"):
            continue
        kind = evidence.get("class")
        if kind == "whole-tool":
            return True
        if kind == "interpreter" and str(evidence.get("normalised", "")).startswith("python"):
            return True
    return False


def consent_note(snapshot) -> str:
    """The fixed consent note; the bypass variant unless bypass is ruled out."""
    mode = _effective_of(snapshot)(_MODE_KEY)
    ruled_out = (
        snapshot.environment.bypass_active == "no"
        and mode.certain
        and mode.value != _BYPASS_MODE
    )
    return CONSENT_NOTE if ruled_out else CONSENT_NOTE_BYPASS


def apply_changes(data, changes) -> dict:
    """A copy of `data` with the selected `changes` made. New keys go to the
    end; nothing else moves."""
    out = copy.deepcopy(data)
    for change in changes:
        if not change.selected:
            continue
        *parents, leaf = _segments(change.pointer)
        node = out
        for name in parents:
            node = node.setdefault(name, {})
        if change.pointer in LIST_POINTERS:
            entries = node.setdefault(leaf, [])
            if change.kind == "remove":
                node[leaf] = [entry for entry in entries if not _same(entry, change.value)]
            elif not any(_same(entry, change.value) for entry in entries):
                entries.append(change.value)
        elif change.kind == "remove":
            node.pop(leaf, None)
        else:
            node[leaf] = change.value
    return out


# =============================================================================
# Diffs
# =============================================================================


def render_diff(target, environment, plan_short) -> str:
    """The text shown for one target: a header line (`scope · real path ·
    profile (DETECTED|EXPLICIT) · plan <short>`), then a unified diff.

    The new side is the bytes `apply` writes, the old side the file in the
    same layout, both with secrets redacted (`render.redact`) and every line
    escaped and shortened like any file content (`render.render_untrusted`).
    A file that is not laid out the way it will be written is shown in the
    new layout on both sides, and the diff says so.
    """
    source = "EXPLICIT" if environment.profile_source == "explicit" else "DETECTED"
    lines = [
        f"{target.scope} · {_escaped(target.real_path)} · "
        f"{environment.profile} ({source}) · plan {plan_short}"
    ]
    if target.writable != "ok":
        lines.append(f"refused: {target.refuse_reason}; nothing is written to this file")
    elif not target.writes:
        lines.append("no change selected for this file; nothing is written to it")
    else:
        if target.current is None:
            lines.append("new file")
        if target.reformatted:
            lines.append(
                "layout: the file is rewritten in a regular layout; "
                "the diff shows the changes of content only"
            )
        fmt = target.format or DEFAULT_FORMAT
        old = [] if target.current is None else _shown_lines(target.current, fmt)
        new = _shown_lines(target.expected, fmt)
        label = target.scope
        lines.extend(
            render.render_untrusted(line)
            for line in difflib.unified_diff(
                old, new, "a/" + label, "b/" + label, lineterm="", n=_CONTEXT_LINES,
            )
        )
    return render.Untrusted("\n".join(lines))


def _shown_lines(data, fmt):
    return jsonio.dumps(render.redact("", data), fmt).decode("utf-8").splitlines()


def _escaped(text):
    """`text` escaped like any untrusted string, but whole: a path names a
    file only when all of it is there."""
    return "".join(
        render.render_untrusted(text[start:start + _ESCAPE_CHUNK])
        for start in range(0, len(text), _ESCAPE_CHUNK)
    )


# =============================================================================
# One target
# =============================================================================


def _target_plan(file, proposals, select, deselect, refusal):
    refuse_reason = None
    if file.status not in _READ_WITH_CERTAINTY:
        refuse_reason = file.reason or file.status
    elif refusal is not None:
        refuse_reason = refusal(file.scope, file.path)
    writable = refuse_reason is None
    data = file.data if file.status == "ok" else None

    changes = []
    for proposal in proposals:
        change = _change(proposal, file.scope, data or {})
        chosen = change.default_selected
        if change.id in select:
            chosen = True
        if change.id in deselect or not writable:
            chosen = False
        changes.append(dataclasses.replace(change, selected=chosen))

    pre = None if file.raw is None else hashlib.sha256(file.raw).hexdigest()
    expected, post = None, pre
    if writable and any(change.selected for change in changes):
        candidate = apply_changes(data or {}, changes)
        if data is None or candidate != data:
            expected = candidate
            new_bytes = jsonio.dumps(expected, file.format or DEFAULT_FORMAT)
            post = hashlib.sha256(new_bytes).hexdigest()
    return TargetPlan(
        scope=file.scope,
        path=file.path,
        real_path=file.real_path,
        pre_sha256=pre,
        post_sha256=post,
        changes=tuple(changes),
        writable="ok" if writable else "refused",
        refuse_reason=refuse_reason,
        current=data,
        expected=expected,
        format=file.format,
        reformatted=data is not None and jsonio.dumps(data, file.format) != file.raw,
    )


def _change(proposal, scope, data):
    """`proposal` as a change to the file of `scope` holding `data`."""
    flags = list(proposal.flags)
    if proposal.remove:
        kind = "remove"
    elif proposal.pointer in LIST_POINTERS:
        kind = "add"
    else:
        held = _lookup(data, proposal.pointer)
        differs = held is not _ABSENT and not _same(held, proposal.value)
        kind = "set" if differs else "add"
        if differs:
            flags.append(FLAG_DIFFERENCE)
    if scope != proposal.origin:
        flags.append(FLAG_MOVED)
    default = proposal.selected and FLAG_DIFFERENCE not in flags
    return Change(
        id=proposal.id,
        kind=kind,
        pointer=proposal.pointer,
        value=proposal.value,
        from_finding=proposal.finding.id,
        check=proposal.finding.check,
        default_selected=default,
        selected=default,
        flags=tuple(flags),
    )


def _applies(proposal, file):
    """Whether the change does something in its own file and can be made
    there without rewriting a value of the wrong type."""
    data = file.data if file.status == "ok" else {}
    if not _fits(proposal, data):
        return False
    held = _lookup(data, proposal.pointer)
    if proposal.pointer in LIST_POINTERS:
        present = held is not _ABSENT and any(_same(entry, proposal.value) for entry in held)
        return present if proposal.remove else not present
    if proposal.remove:
        return held is not _ABSENT
    return held is _ABSENT or not _same(held, proposal.value)


def _fits(proposal, data):
    *parents, _leaf = _segments(proposal.pointer)
    node = data
    for name in parents:
        if name not in node:
            return True
        node = node[name]
        if not isinstance(node, dict):
            return False
    held = _lookup(data, proposal.pointer)
    return held is _ABSENT or proposal.pointer not in LIST_POINTERS or isinstance(held, list)


def _checked_selection(proposals, selection, moves):
    select = tuple(selection.get("select", ()))
    deselect = tuple(selection.get("deselect", ()))
    unknown = [i for i in dict.fromkeys((*select, *deselect, *moves)) if i not in proposals]
    if unknown:
        raise SelectionError("unknown-id", unknown)
    both = [i for i in select if i in deselect]
    if both:
        raise SelectionError("conflict", both)
    bad = [i for i, scope in moves.items() if scope not in SCOPES]
    if bad:
        raise SelectionError("bad-scope", bad)
    fixed = [
        i for i, scope in moves.items()
        if scope != proposals[i].origin and not proposals[i].movable
    ]
    if fixed:
        raise SelectionError("not-movable", fixed)
    return frozenset(select), frozenset(deselect), dict(moves)


# =============================================================================
# What each check proposes
# =============================================================================


def _credentials(item, snapshot, _confirmed, _effective):
    """C1: the first listed Read deny rule of the path, unless a verified
    one is in place already (what is open then is the sandbox, C4)."""
    credential = next(
        (c for c in snapshot.credentials if c.id == item.evidence.get("credential")), None,
    )
    states = item.evidence.get("states")
    if credential is None or not isinstance(states, dict) or states.get("permissions") == "EFFECTIVE":
        return (), ()
    rule = credential.read_rule_spellings_for(snapshot.home)[0]
    return (_Proposal("user", DENY, rule, False, item),), ()


def _bypass(item, snapshot, _confirmed, _effective):
    """C2: the disable key, never in a container."""
    if item.evidence.get("key") != _DISABLE_KEY or snapshot.environment.profile == _CONTAINER:
        return (), ()
    return _key(DISABLE_BYPASS, "disable", item, snapshot)


def _sandbox(item, snapshot, confirmed, _effective):
    """C4: `enabled` after a passed probe, the fail-closed keys only when
    the developer also confirmed that the sandbox is active."""
    gaps = item.evidence.get("gaps")
    gaps = gaps if isinstance(gaps, list) else []
    wanted = [(SANDBOX_ENABLED, True, ())] if "sandbox-off" in gaps else []
    closing = [
        (pointer, value, (FLAG_CONFIRMED,))
        for gap, pointer, value in _FAIL_CLOSED_GAPS if gap in gaps
    ]
    if not wanted and not closing:
        return (), ()
    if snapshot.probe.result != "pass":
        return (), ({"reason": REASON_PROBE},)
    reasons = []
    if confirmed:
        wanted += closing
    elif closing:
        reasons.append({"reason": REASON_CONFIRMATION})
    proposals = []
    for pointer, value, flags in wanted:
        made, why = _key(pointer, value, item, snapshot, flags)
        proposals.extend(made)
        reasons.extend(why)
    return tuple(proposals), tuple(reasons)


def _read_outside(item, snapshot, _confirmed, _effective):
    """C7: the key, when the Claude Code version is known to have it."""
    return _key(BLOCK_READS, True, item, snapshot)


def _key(pointer, value, item, snapshot, flags=()):
    """A key of the user settings; not proposed when it needs a newer Claude
    Code than the one detected, or when the version is unknown."""
    rule = snapshot.keys.rules[".".join(_segments(pointer))]
    if rule.min is not None and not _at_least(snapshot.environment.claude_version, rule.min):
        return (), ({"reason": REASON_VERSION, "min_version": rule.min},)
    return (_Proposal("user", pointer, value, False, item, flags=tuple(flags)),), ()


def _broad_allow(item, snapshot, _confirmed, _effective):
    """C3: the whole rule out of the file it is in. A rule a deny or ask
    rule already covers is left alone."""
    rule = item.evidence.get("rule")
    if not isinstance(rule, str) or item.evidence.get("shadowed"):
        return (), ()
    return _removal(item, snapshot, rule)


def _stale_allow(item, snapshot, _confirmed, _effective):
    """C10: the rule out of the file it is in. The finding shows the rule
    rendered, so the rule is found again in the file; when two rules of the
    file render alike, none is proposed."""
    file = _own_target(item, snapshot)
    shown = item.evidence.get("rule")
    rules = _lookup(file.data, ALLOW) if file is not None and file.status == "ok" else _ABSENT
    if not isinstance(rules, list):
        return _removal(item, snapshot, None)
    matching = list(dict.fromkeys(
        rule for rule in rules
        if isinstance(rule, str) and render.render_untrusted(rule) == shown
    ))
    return _removal(item, snapshot, matching[0] if len(matching) == 1 else None)


def _removal(item, snapshot, rule):
    if item.scope in _MANAGED_SCOPES:
        return (), ({"reason": REASON_MANAGED},)
    if rule is None or _own_target(item, snapshot) is None:
        return (), ()
    return (_Proposal(item.scope, ALLOW, rule, True, item, selected=False, movable=False),), ()


def _mcp(item, snapshot, _confirmed, effective_of):
    """C6: `enableAllProjectMcpServers` out of every file that sets it, and
    the servers it approves today named instead. The missing allowlist gets
    nothing."""
    if item.evidence.get("key") != checks_mcp.ENABLE_ALL or item.status != "FAIL":
        return (), ()
    if item.scope in _MANAGED_SCOPES:
        return (), ({"reason": REASON_MANAGED},)
    mcp_json = next((s for s in snapshot.sources if s.scope == _MCP_JSON), None)
    if mcp_json is not None and mcp_json.status not in _READ_WITH_CERTAINTY:
        return (), ()  # the approved names are not known
    holders = [
        scope for scope in SCOPES
        if snapshot.targets[scope].status == "ok"
        and snapshot.targets[scope].data.get(checks_mcp.ENABLE_ALL) is True
    ]
    if not holders:
        return (), ()
    home = item.scope if _own_target(item, snapshot) is not None else holders[0]
    proposals = [
        _Proposal(scope, ENABLE_ALL, True, True, item, selected=scope != "project", movable=False)
        for scope in holders
    ]
    proposals += [
        _Proposal(home, ENABLED_SERVERS, name, False, item, selected=home != "project")
        for name in checks_mcp.approved_project_servers(snapshot.sources, effective_of)
        if isinstance(name, str)
    ]
    return tuple(proposals), ()


_HANDLERS = {
    "C1": _credentials,
    "C2": _bypass,
    "C3": _broad_allow,
    "C4": _sandbox,
    "C6": _mcp,
    "C7": _read_outside,
    "C10": _stale_allow,
}


def _own_target(item, snapshot):
    """The target the finding's file is, None when setup does not write it."""
    file = snapshot.targets.get(item.scope)
    if file is None or not item.file or os.path.abspath(item.file) != os.path.abspath(file.path):
        return None
    return file


# =============================================================================
# Small helpers
# =============================================================================


def _effective_of(snapshot):
    cache = {}

    def effective_of(key):
        if key not in cache:
            cache[key] = effective.effective(
                key, snapshot.sources, snapshot.keys.rules[key],
                snapshot.environment.claude_version,
            )
        return cache[key]

    return effective_of


def _at_least(version, minimum):
    if version is None:
        return False
    return (version.major, version.minor, version.patch) >= refdata.version_tuple(minimum)


def _segments(pointer):
    return pointer.split("/")[1:]


def _lookup(data, pointer):
    node = data
    for name in _segments(pointer):
        if not isinstance(node, dict) or name not in node:
            return _ABSENT
        node = node[name]
    return node


def _same(left, right):
    """Equal as JSON: `True` is not `1`."""
    return type(left) is type(right) and left == right


def _distinct(entries):
    seen, kept = set(), []
    for entry in entries:
        identity = json.dumps(entry, sort_keys=True, ensure_ascii=True)
        if identity not in seen:
            seen.add(identity)
            kept.append(entry)
    return kept
