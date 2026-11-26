#!/usr/bin/env python3
"""scripts/observability/denials.py -- spec-024: denials from session transcripts.

Claude Code records no event for a hook deny, a settings deny rule or a
rejected permission prompt. The only trace is the session transcript: an
error tool result whose text is the deny message. This module reads that
text and turns it into counts a person can review.

Classification -- `classify(text, tool)`: an ordered table of known message
openings, first match wins (SDD ADR-4). Hook owners are the TCS hook messages
mapped to `<plugin>/<hook>`, three known non-TCS openings as `external: ...`
(ADR-8). After the table:

  - text carrying Claude Code's `PreToolUse:<Tool> hook error: ` prefix is a
    hook deny whose owner is unknown -- kept as "hook deny, unattributed"
    (`hook=None`), so wording drift shows as a rising unattributed count
    instead of silently vanishing;
  - any other text is an ordinary tool error and not a denial (`None`).

Locating -- `locate_transcripts(repo_root, homes)` finds the candidate files
per home (ADR-3). Which repository a result belongs to is decided later, per
line, from its `cwd` -- locating by project-dir prefix also picks up sibling
repositories (`app` vs `app-old`).

Scanning -- `scan_file(path, period)` reads one file and returns its deduped
error tool results in the period (ADR-5), its skipped-line count, and the
earliest timestamp on any line (`oldest_ts`). A cheap text prefilter decides
which lines are JSON-parsed at all.

Privacy (CON-2): a returned `Denial` holds only fixed labels from the table
and identifiers parsed out of the message (rule names, classifier reason
category). Rule explanations, commands, paths and free reason text are never
copied out of the message.

Module contract: standard library only (CON-1) and nothing local to this
repository (CON-4); no wall clock and no real home directory -- callers pass
every path and time explicitly (CON-5).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

HOOK_DENY = "hook deny"

_HOOK_ERROR_PREFIX = re.compile(r"^PreToolUse:[^\s:]+ hook error: ")
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
    _row("sandbox: network", r"CONNECT tunnel failed, response 403", None, "low"),
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


# ---------------------------------------------------------------------------
# Locating transcripts (ADR-3) and scanning one file (ADR-5).
# ---------------------------------------------------------------------------

# Claude Code writes compact JSON (`"is_error":true`); the optional spaces keep
# a re-serialised file from slipping past. An escaped `\"is_error\"` inside a
# message string does not match, because its closing quote follows a backslash.
_IS_ERROR = re.compile(r'"is_error"\s*:\s*true')
# The same escaping argument keeps a quoted timestamp inside message text from
# matching. The first match is the line's own: Claude Code writes nested
# objects that carry a timestamp after the top-level field.
_TIMESTAMP = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')
_TOOL_USE = '"tool_use"'


@dataclass(frozen=True)
class Period:
    """The reporting window, both ends inclusive, timezone-aware (UTC)."""

    start: datetime
    end: datetime

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts <= self.end


@dataclass(frozen=True)
class LocateResult:
    """Candidate transcript files, every projects dir searched, and those absent."""

    files: tuple[Path, ...]
    searched: tuple[Path, ...]
    missing: tuple[Path, ...]


@dataclass(frozen=True)
class ErrorResult:
    """One deduped error tool result. `text` stays in memory for `classify` only (CON-2)."""

    file: Path
    tool_use_id: str
    tool: str | None
    text: str
    ts: datetime
    cwd: str
    session_id: str
    version: str
    sidechain: bool


@dataclass(frozen=True)
class ScanResult:
    """One file's error results in period, its skipped-line count, and whether it was readable.

    `oldest_ts` is the earliest valid timestamp on any line, in period or not;
    `None` when no line carries one or the file is unreadable.
    """

    path: Path
    results: tuple[ErrorResult, ...]
    skipped_lines: int
    unreadable: bool = False
    oldest_ts: datetime | None = None

    @property
    def versions(self) -> frozenset[str]:
        return frozenset(r.version for r in self.results if r.version)


def _encode(path: Path) -> str:
    """Mirror Claude Code's project-dir naming: every non-alphanumeric character becomes "-"."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _project_dirs(projects: Path, prefix: str) -> list[Path]:
    """Dirs under `projects` whose name starts with `prefix`, case-insensitive; [] if unlistable."""
    try:
        entries = sorted(projects.iterdir())
    except OSError:
        return []
    return [d for d in entries if d.is_dir() and d.name.casefold().startswith(prefix)]


def _transcripts_in(project: Path) -> list[Path]:
    """Main session files and subagent files of one project dir."""
    candidates = sorted(project.glob("*.jsonl")) + sorted(project.glob("*/subagents/*.jsonl"))
    return [path for path in candidates if path.is_file()]


def locate_transcripts(repo_root: Path, homes: Sequence[Path]) -> LocateResult:
    """Find transcript files for `repo_root` under each home's `.claude/projects` (ADR-3)."""
    prefix = _encode(repo_root).casefold()
    searched: list[Path] = []
    files: list[Path] = []
    for home in homes:
        projects = home / ".claude" / "projects"
        if projects in searched:
            continue
        searched.append(projects)
        for project in _project_dirs(projects, prefix):
            files.extend(_transcripts_in(project))
    missing = tuple(p for p in searched if not p.is_dir())
    return LocateResult(files=tuple(files), searched=tuple(searched), missing=missing)


class _BadShape(ValueError):
    """An error line whose envelope or tool result is not the shape this module reads."""


def _parse_ts(value: object) -> datetime:
    if not isinstance(value, str):
        raise _BadShape("timestamp")
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _BadShape("timestamp") from exc
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _content_items(line: dict) -> list:
    message = line.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        raise _BadShape("message.content")
    return content


def _result_text(content: object) -> str:
    """A tool result's text: a string, or the joined `text` parts of a list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part["text"] for part in content
                         if isinstance(part, dict) and part.get("type") == "text"
                         and isinstance(part.get("text"), str))
    raise _BadShape("tool_result.content")


def _error_items(line: dict) -> list[tuple[str, str]]:
    """`(tool_use_id, text)` of each `is_error: true` tool result on one user line."""
    pairs = []
    for item in _content_items(line):
        if not (isinstance(item, dict) and item.get("type") == "tool_result" and item.get("is_error") is True):
            continue
        tool_use_id = item.get("tool_use_id")
        if not isinstance(tool_use_id, str) or not tool_use_id:
            raise _BadShape("tool_use_id")
        pairs.append((tool_use_id, _result_text(item.get("content"))))
    return pairs


def _tool_uses(line: dict) -> Iterable[tuple[str, str]]:
    """`(id, name)` of each `tool_use` on an assistant line; wrong shapes yield nothing."""
    message = line.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    for item in content if isinstance(content, list) else ():
        if isinstance(item, dict) and item.get("type") == "tool_use":
            if isinstance(item.get("id"), str) and isinstance(item.get("name"), str):
                yield item["id"], item["name"]


def _text_field(line: dict, key: str) -> str:
    value = line.get(key)
    return value if isinstance(value, str) else ""


@dataclass
class _FileScan:
    """Mutable state while one file is read; `results` still lack tool names."""

    path: Path
    period: Period
    subagent_file: bool
    seen_ids: set[str] = field(default_factory=set)
    tool_names: dict[str, str] = field(default_factory=dict)
    results: list[ErrorResult] = field(default_factory=list)
    skipped: int = 0
    oldest_ts: datetime | None = None

    def add_line(self, raw: str) -> None:
        line = raw.strip()
        if not line:
            return
        if not (line.startswith("{") and line.endswith("}")):
            self.skipped += 1  # not JSON, or a partial write
            return
        self._note_timestamp(line)
        is_error = _IS_ERROR.search(line) is not None
        if not (is_error or _TOOL_USE in line):
            return  # cheap prefilter: nothing this module reads
        try:
            entry = json.loads(line)
        except (ValueError, RecursionError):  # RecursionError: pathologically nested
            self.skipped += 1
            return
        if isinstance(entry, dict):
            self._add_entry(entry, is_error)
        elif is_error:
            self.skipped += 1

    def _note_timestamp(self, line: str) -> None:
        """Track the earliest valid timestamp without parsing the line; bad values are ignored."""
        match = _TIMESTAMP.search(line)
        if match is None:
            return
        try:
            ts = _parse_ts(match.group(1))
        except _BadShape:
            return
        if self.oldest_ts is None or ts < self.oldest_ts:
            self.oldest_ts = ts

    def _add_entry(self, entry: dict, is_error: bool) -> None:
        kind = entry.get("type")
        if kind == "assistant":
            self.tool_names.update(_tool_uses(entry))
        elif kind == "user" and is_error:
            try:
                self._add_errors(entry)
            except _BadShape:
                self.skipped += 1

    def _add_errors(self, entry: dict) -> None:
        pairs = _error_items(entry)
        if not pairs:
            return
        ts = _parse_ts(entry.get("timestamp"))
        for tool_use_id, text in pairs:
            if tool_use_id in self.seen_ids:
                continue
            self.seen_ids.add(tool_use_id)
            if self.period.contains(ts):
                self.results.append(self._error_result(entry, tool_use_id, text, ts))

    def _error_result(self, entry: dict, tool_use_id: str, text: str, ts: datetime) -> ErrorResult:
        return ErrorResult(
            file=self.path, tool_use_id=tool_use_id, tool=None, text=text, ts=ts,
            cwd=_text_field(entry, "cwd"), session_id=_text_field(entry, "sessionId"),
            version=_text_field(entry, "version"),
            sidechain=self.subagent_file or entry.get("isSidechain") is True,
        )

    def finish(self) -> ScanResult:
        """Attach tool names: a `tool_use` may come after its result (compaction)."""
        named = tuple(replace(r, tool=self.tool_names.get(r.tool_use_id)) for r in self.results)
        return ScanResult(path=self.path, results=named, skipped_lines=self.skipped,
                          oldest_ts=self.oldest_ts)


def scan_file(path: Path, period: Period) -> ScanResult:
    """Read one transcript; return its deduped error tool results in `period` (ADR-5).

    Only `type == "user"` lines count (an `api-request-blob` line copies the
    same result); a result counts once per `tool_use_id`. A file that cannot
    be read is reported as `unreadable`, never raised.
    """
    state = _FileScan(path=path, period=period, subagent_file=path.parent.name == "subagents")
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                state.add_line(raw)
    except OSError:
        return ScanResult(path=path, results=(), skipped_lines=0, unreadable=True)
    return state.finish()
