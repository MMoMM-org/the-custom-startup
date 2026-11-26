#!/usr/bin/env python3
"""scripts/observability/denials.py -- spec-024: denials from session transcripts.

Claude Code records no event for a hook deny, a settings deny rule or a
rejected permission prompt. The only trace is the session transcript: an
error tool result whose text is the deny message. This module reads that
text and turns it into counts a person can review.

T1.2 -- `classify(text, tool)`: an ordered table of known message openings,
first match wins (SDD ADR-4). Hook owners are the TCS hook messages mapped to
`<plugin>/<hook>`, three known non-TCS openings as `external: ...` (ADR-8).
After the table:

  - text carrying Claude Code's `PreToolUse:<Tool> hook error: ` prefix is a
    hook deny whose owner is unknown -- kept as "hook deny, unattributed"
    (`hook=None`), so wording drift shows as a rising unattributed count
    instead of silently vanishing;
  - any other text is an ordinary tool error and not a denial (`None`).

Privacy (CON-2): a returned `Denial` holds only fixed labels from the table
and identifiers parsed out of the message (rule names, classifier reason
category). Rule explanations, commands, paths and free reason text are never
copied out of the message.

Module contract (ADR-1, CON-5): standard library only, nothing local to this
repository, no wall clock and no real home directory -- callers pass every
path and time explicitly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HOOK_DENY = "hook deny"

_HOOK_ERROR_PREFIX = re.compile(r"^PreToolUse:\w+ hook error: ")
_BAD_GIT_OPS_RULE = re.compile(r"^\s+- \[([A-Z_]+)\]", re.MULTILINE)
_CLASSIFIER_REASON = re.compile(r"Reason: \[([^\]]+)\]")

# Rejecting these is answering a question or declining a plan, not stopping an action.
_NOT_ACTION_TOOLS = frozenset({"AskUserQuestion", "ExitPlanMode"})


@dataclass(frozen=True)
class Denial:
    """One classified denial: fixed labels and identifiers only (CON-2)."""

    category: str
    hook: str | None
    rules: tuple[str, ...]
    reason_category: str | None
    confidence: str


@dataclass(frozen=True)
class Row:
    """One table entry; `rule_pattern` and `reason_pattern` extract identifiers."""

    category: str
    pattern: re.Pattern[str]
    hook: str | None
    confidence: str
    rule_pattern: re.Pattern[str] | None = None
    reason_pattern: re.Pattern[str] | None = None
    excluded_tools: frozenset[str] = field(default_factory=frozenset)


def _row(category: str, pattern: str, hook: str | None, confidence: str, **extra) -> Row:
    return Row(category, re.compile(pattern), hook, confidence, **extra)


# Order matters (SDD/Implementation Examples): hook-specific rows before generic
# ones; "prompt rejected" before the sandbox rows, because a rejected Bash call
# can carry EPERM-looking text; sandbox rows last, as their text is the least
# specific. The pre-edit `Refusing to ... on '...'.` row precedes the eslint
# row, whose `': ... detected` shape it does not match.
TABLE: tuple[Row, ...] = (
    _row(HOOK_DENY, r"^tcs-git-helpers DENIED: \d+ rule\(s\) matched",
         "tcs-git-helpers/block-bad-git-ops", "high", rule_pattern=_BAD_GIT_OPS_RULE),
    _row(HOOK_DENY, r"^Refusing to (Write|Edit|NotebookEdit) '[^']*' on '[^']*'\.",
         "tcs-git-helpers/pre-edit-branch-check", "high"),
    _row(HOOK_DENY, r"^Refusing to \w+ '[^']*': edits to git-internal paths",
         "tcs-git-helpers/protect-git-internals", "high"),
    _row(HOOK_DENY, r"^Cannot exit worktree:", "tcs-git-helpers/worktree-exit-guard", "high"),
    _row(HOOK_DENY, r"^Refusing to \w+ '[^']*': .* detected", "tcs-patterns/block-eslint-disable", "high"),
    _row(HOOK_DENY, r"^This reads a GitHub issue without its comments\.",
         "tcs-issues/require-issue-comments", "high"),
    _row(HOOK_DENY, r"^Dangerous flag detected", "external: dangerous flag", "medium"),
    _row(HOOK_DENY, r"^(rm -rf on critical directory blocked|Recursive force rm on a critical path blocked)",
         "external: critical rm", "medium"),
    _row("classifier block", r"denied by the Claude Code auto mode classifier\. Reason: \[[^\]]+\]",
         None, "high", reason_pattern=_CLASSIFIER_REASON),
    _row("classifier block", r"^Permission for this action has been denied\. Reason:",
         None, "high", reason_pattern=_CLASSIFIER_REASON),
    _row("safety check", r"^Permission for this command was denied by a built-in Claude Code safety check",
         None, "high"),
    _row("permission denied", r"^Permission to use \S+ has been denied", None, "medium"),
    _row("worktree isolation", r"^This (agent|session) is isolated in the worktree", None, "high"),
    _row("prompt rejected", r"^The user doesn't want to proceed with this tool use", None, "high",
         excluded_tools=_NOT_ACTION_TOOLS),
    _row("sandbox: filesystem", r"[Oo]peration not permitted|Read-only file system|could not lock config file",
         None, "low"),
    _row("sandbox: network", r"CONNECT tunnel failed, response 403", None, "medium"),
)


def _strip_prefix(text: str) -> tuple[str, bool]:
    """Remove a leading `PreToolUse:<Tool> hook error: `; report whether it was there."""
    match = _HOOK_ERROR_PREFIX.match(text)
    return (text[match.end():], True) if match else (text, False)


def _denial_from_row(row: Row, text: str) -> Denial:
    rules = tuple(row.rule_pattern.findall(text)) if row.rule_pattern else ()
    reason = row.reason_pattern.search(text) if row.reason_pattern else None
    return Denial(
        category=row.category,
        hook=row.hook,
        rules=rules,
        reason_category=reason.group(1) if reason else None,
        confidence=row.confidence,
    )


def classify(text: str, tool: str | None) -> Denial | None:
    """Map one error tool result's text (and its tool name) to a `Denial`, or `None`.

    `None` means "not a denial": an ordinary tool error, a rejected question or
    plan prompt, or input that is not text at all.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    body, prefixed = _strip_prefix(text)
    for row in TABLE:
        if row.pattern.search(body):
            return None if tool in row.excluded_tools else _denial_from_row(row, body)
    if prefixed:
        return Denial(category=HOOK_DENY, hook=None, rules=(), reason_category=None, confidence="high")
    return None
