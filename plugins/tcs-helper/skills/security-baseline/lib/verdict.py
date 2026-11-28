"""How a check's result is expressed (spec 025, K11, ADR-4).

A check (K10) states, per protection layer it requires, whether the
protection is EFFECTIVE, PRESENT-INERT, ABSENT or UNKNOWN. This module turns
those states into a status, and a run's raw findings into the blocks of the
audit report:

- `status` — the status table. Only "every layer EFFECTIVE" passes.
- `finding` / `Finding` — one result with a stable id.
- `run_check` — a check that raises is reported as UNKNOWN, never skipped.
- `finalise` — drops passes, splits off accepted exceptions and INFO
  findings, sorts, counts, and words the verdict line and coverage block.

A finding's severity is the check's base severity and is never changed here:
PARTIAL and UNKNOWN count at full severity. A finding can be accepted only for
a check in `ACCEPTABLE_CHECKS`, whatever the rules passed in say, so the
container exposure checks (C2x, C6x) always stay findings.

The verdict line never says more than "no gaps in the audited layers" and
always names what was not audited. A settings or MCP file that exists but
could not be read makes its scope unaudited.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from dataclasses import dataclass

STATES = ("EFFECTIVE", "PRESENT-INERT", "ABSENT", "UNKNOWN")
STATUSES = ("FAIL", "UNKNOWN", "PARTIAL", "PASS")
SEVERITIES = ("HIGH", "MED", "LOW", "INFO")
LAYERS = ("permissions", "sandbox", "webfetch", "mcp", "environment")

ACCEPTABLE_CHECKS = frozenset({"C2", "C9"})
CONTAINER_PROFILE = "container"
TEMPLATE_MATCH = "template_match"  # C9 evidence: the entry is exactly in the git-helpers template

CHECK_ERROR = "check-error"
NO_AUTO_FIX = "no-auto-fix"

UNAUDITED = (
    "settings-flag",
    "remote-managed",
    "mdm",
    "hooks",
    "env-overrides",
    "plugin-settings",
)
VERDICT_LINE_LIMIT = 160
NO_GAPS = "no gaps in the audited layers"

_GAP_SEVERITIES = ("HIGH", "MED", "LOW")
_QUALIFYING_STATUSES = ("PARTIAL", "UNKNOWN")
_READ_WITH_CERTAINTY = ("ok", "absent")
_UNAUDITED_LABELS = {
    "remote-managed": "remote",
    "mdm": "MDM",
    "hooks": "hooks",
    "env-overrides": "env overrides",
    "plugin-settings": "plugin settings",
}
_NUMBERED_CHECK_RE = re.compile(r"C([0-9]+)(.*)")


@dataclass(frozen=True)
class Finding:
    """One result of one check. `evidence` holds data from files and is
    escaped when the report is rendered; `fix` names a template, never text."""

    id: str  # check + "-" + 8 hex of the evidence key
    check: str  # C1..C10, C2x, C6x, CR
    severity: str
    status: str
    layer: str
    scope: str
    file: str
    evidence: dict
    fix: dict  # {"template": id, "params": {...}}
    accepted: bool = False
    accepted_reason: str | None = None

    def __post_init__(self):
        for name, allowed in (("severity", SEVERITIES), ("status", STATUSES), ("layer", LAYERS)):
            value = getattr(self, name)
            if value not in allowed:
                raise ValueError(f"finding {name} must be one of {list(allowed)}, got {value!r}")


def status(states):
    """Status of a check from its `{layer: state}` mapping (ADR-4)."""
    seen = set(states.values())
    if not seen:
        raise ValueError("a check needs at least one required layer")
    if not seen <= set(STATES):
        raise ValueError(f"layer states must be among {list(STATES)}")
    if seen == {"EFFECTIVE"}:
        return "PASS"
    if seen == {"ABSENT"}:
        return "FAIL"
    if "UNKNOWN" in seen and "EFFECTIVE" not in seen:
        return "UNKNOWN"
    return "PARTIAL"


def finding_id(check, evidence_key):
    """Stable id: the same check and evidence key give the same id on every run."""
    digest = hashlib.sha256(evidence_key.encode("utf-8", "surrogatepass")).hexdigest()
    return f"{check}-{digest[:8]}"


def finding(check, severity, status, layer, *, evidence_key, scope="", file="",
            evidence=None, fix=None):
    """Build a Finding. `evidence_key` is the text that tells this finding
    apart within its check (a scope plus a rule, a credential id) and only
    feeds the id; `severity` is the check's base severity."""
    return Finding(
        id=finding_id(check, evidence_key),
        check=check,
        severity=severity,
        status=status,
        layer=layer,
        scope=scope,
        file=file,
        evidence={} if evidence is None else evidence,
        fix={"template": NO_AUTO_FIX, "params": {}} if fix is None else fix,
    )


def run_check(check, severity, layer, run):
    """Call `run()` and return its findings as a list.

    If it raises, or yields something that is not a Finding, the findings made
    so far are kept and one UNKNOWN finding with reason `check-error` is added
    at the check's base severity. Only the exception's class name is kept: its
    message may quote file content.
    """
    found = []
    try:
        for item in run():
            if not isinstance(item, Finding):
                raise TypeError("a check must yield Finding objects")
            found.append(item)
    except Exception as exc:  # noqa: BLE001 - a failing check must never be skipped
        found.append(finding(
            check, severity, "UNKNOWN", layer,
            evidence_key=CHECK_ERROR,
            evidence={"reason": CHECK_ERROR, "error": type(exc).__name__},
        ))
    return found


def profile_exceptions(profile, check, evidence):
    """The accepted exceptions of ADR-4: a reason, or None for a finding.

    - C2 (bypass not disabled) in the container profile.
    - C9 entries the check marked as exactly in the git-helpers template
      (`evidence["template_match"] is True`).
    """
    if check == "C2" and profile == CONTAINER_PROFILE:
        return "container-profile"
    if check == "C9" and evidence.get(TEMPLATE_MATCH) is True:
        return "git-helpers-template"
    return None


def finalise(findings, profile, accepted_rules, *, sources=(), settings_flag="unknown"):
    """Turn raw findings into `(findings, accepted, info, summary, coverage)`.

    `accepted_rules(profile, check, evidence)` returns a reason to accept a
    finding or None (`profile_exceptions` is the shipped set). `sources` are
    the `layers.Source` objects of the run and `settings_flag` the
    environment's `--settings` observation; both only feed the coverage block
    and the verdict line.
    """
    gaps, accepted, info = [], [], []
    for item in findings:
        if item.status == "PASS":
            continue
        if item.severity == "INFO":
            info.append(item)
            continue
        reason = _accepted_reason(item, profile, accepted_rules)
        if reason is None:
            gaps.append(item)
        else:
            accepted.append(dataclasses.replace(item, accepted=True, accepted_reason=reason))
    for block in (gaps, accepted, info):
        block.sort(key=_report_order)

    unread = _unread_scopes(sources)
    coverage = {
        "audited": _distinct(s.scope for s in sources if s.scope not in unread),
        "unaudited": [*unread, *UNAUDITED],
    }
    counts = {severity: _count(gaps, "severity", severity) for severity in _GAP_SEVERITIES}
    counts["INFO"] = len(info)
    counts.update({name: _count(gaps, "status", name) for name in _QUALIFYING_STATUSES})
    counts["ACCEPTED"] = len(accepted)
    counts["unaudited"] = len(coverage["unaudited"])
    summary = {
        "counts": counts,
        "verdict_line": _verdict_line(counts, _unaudited_labels(unread, settings_flag)),
    }
    return gaps, accepted, info, summary, coverage


def _accepted_reason(item, profile, accepted_rules):
    if item.check not in ACCEPTABLE_CHECKS:
        return None
    return accepted_rules(profile, item.check, item.evidence)


def _report_order(item):
    """HIGH before MED before LOW, then C1, C2, C2x, ... C10, CR, then id."""
    numbered = _NUMBERED_CHECK_RE.fullmatch(item.check)
    check = (0, int(numbered[1]), numbered[2]) if numbered else (1, 0, item.check)
    return SEVERITIES.index(item.severity), check, item.id


def _count(items, field, value):
    return sum(1 for item in items if getattr(item, field) == value)


def _distinct(names):
    return list(dict.fromkeys(names))


def _unread_scopes(sources):
    """`{scope: status}` of scopes with a file that exists but was not read."""
    unread = {}
    for source in sources:
        if source.status not in _READ_WITH_CERTAINTY:
            unread.setdefault(source.scope, source.status)
    return unread


def _unaudited_labels(unread, settings_flag):
    seen = "present" if settings_flag == "present" else "may exist"
    labels = [f"{scope} ({why})" for scope, why in unread.items()]
    labels.append(f"--settings ({seen})")
    labels.extend(_UNAUDITED_LABELS[name] for name in UNAUDITED if name in _UNAUDITED_LABELS)
    return labels


def _verdict_line(counts, unaudited):
    """One line of at most `VERDICT_LINE_LIMIT` characters."""
    gaps = [f"{counts[name]} {name}" for name in _GAP_SEVERITIES if counts[name]]
    if gaps:
        qualifiers = [f"{counts[name]} {name}" for name in _QUALIFYING_STATUSES if counts[name]]
        qualified = f" ({', '.join(qualifiers)})" if qualifiers else ""
        head = f"{', '.join(gaps)}{qualified} in audited layers"
    else:
        head = NO_GAPS
    head += "; not audited: "
    for shown in range(len(unaudited), -1, -1):
        hidden = len(unaudited) - shown
        tail = unaudited[:shown] + ([f"+{hidden} more"] if hidden else [])
        line = head + ", ".join(tail)
        if len(line) <= VERDICT_LINE_LIMIT:
            return line
    return line[:VERDICT_LINE_LIMIT]
