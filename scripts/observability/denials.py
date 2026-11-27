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

Period and aggregation -- `period_from_args(weeks, since, now)` builds the
reporting window (ADR-7); `aggregate(scans, repo_root, period)` keeps the
results whose `cwd` lies in the repository (worktree suffix stripped, ADR-3),
classifies them and counts per category, hook rule, Monday week (UTC) and
main/subagent side, plus the ten most repeated denial kinds.

Overrides -- `read_overrides(repo_root, homes, period)` counts in-period
override consumptions from tcs-git-helpers' audit log per home (ADR-6): per
rule id, the master switch `CLAUDE_ALLOW_GIT_BAD_OPS` apart, ask-guard rows
skipped, a log reached through two homes read once. Only `ts`, `env_var` and
`hook` are read from a row. `with_overrides(summary, counts)` joins those
counts onto the summary and its block-bad-git-ops top rows.

Rendering -- `render(summary)` turns one source's summary into its section
lines (per category, hook and rule; per week; top repeated; overrides; what is
not observable; partial reads); `render_not_enabled(label)` is the one-line
section for a source without `denials = true` (F1 AC1). Both end with a
trailing "" line, like report.py's other renderers.

Entry point -- `build_section(repo_root, homes, period)`: locate -> scan ->
aggregate -> overrides -> render for one enabled source, or, with no
transcript in reach, a "no transcripts found" section naming every place
searched (F1 AC2). report.py calls only this and `render_not_enabled` (ADR-1).

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
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HOOK_DENY = "hook deny"

_HOOK_ERROR_PREFIX = re.compile(r"^PreToolUse:[^\s:]+ hook error: ")
_BAD_GIT_OPS_RULE = re.compile(r"^\s+- \[([A-Z_]+)\]", re.MULTILINE)
_CLASSIFIER_REASON = re.compile(r"Reason: \[([^\]]+)\]")

# Identifier shapes (CON-2). A free identifier -- rule id, classifier reason
# category ("Data Exfiltration"), tool name, session id, version -- is kept or
# printed only when it matches its shape in full; anything else (control
# characters, newlines, free text, overlong) becomes one fixed marker, never
# text. Anchored with \A and \Z, never ^ and $: `$` also matches before a
# trailing newline, so `^X$` lets "X\n" through `match` and `search`.
_SAFE_RULE = re.compile(r"\A[A-Z0-9_]{1,64}\Z")
_REASON_CATEGORY = re.compile(r"\A[A-Za-z][A-Za-z0-9 /&-]{0,47}\Z")
_SAFE_TOKEN = re.compile(r"\A[A-Za-z0-9._+-]{1,128}\Z")
_UNRECOGNISED = "(unrecognised)"


def _safe(value: str | None, shape: re.Pattern[str] = _SAFE_TOKEN) -> str:
    """`value` when it matches `shape` in full, else the fixed `(unrecognised)` marker."""
    return value if isinstance(value, str) and shape.fullmatch(value) else _UNRECOGNISED


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


def _reason_category(row: Row, text: str) -> str | None:
    reason = row.reason_pattern.search(text) if row.reason_pattern else None
    return None if reason is None else _safe(reason.group(1), _REASON_CATEGORY)


def _denial_from_row(row: Row, text: str) -> Denial:
    rules = tuple(row.rule_pattern.findall(text)) if row.rule_pattern else ()
    return Denial(
        category=row.category,
        hook=row.hook,
        rules=rules,
        reason_category=_reason_category(row, text),
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


# ---------------------------------------------------------------------------
# The period (ADR-7) and aggregation of one repository's denials.
# ---------------------------------------------------------------------------

DEFAULT_DAYS = 28
TOP_LIMIT = 10
# The Claude Code versions the classification table was checked against (CON-6).
CHECKED_VERSIONS = ((2, 1, 71), (2, 1, 332))
MAIN, SUBAGENT = "main", "subagent"

# ASCII digits only (`\d` also takes other scripts' digits), anchored like the
# identifier shapes. A version part is bounded so `int()` never meets its
# digit limit (CON-6: an odd version is "not checked", never a crash).
_DATE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_VERSION = re.compile(r"\A([0-9]{1,9})\.([0-9]{1,9})\.([0-9]{1,9})\Z")
# A worktree session's cwd is `<repo>/.claude/worktrees/<name>[/...]`; it counts for `<repo>`.
_WORKTREE = re.compile(r"/\.claude/worktrees/[^/]+(?:/.*)?$")
_WEEK = timedelta(weeks=1)


def week_start(ts: datetime) -> datetime:
    """Monday 00:00 UTC of the ISO week that holds `ts`."""
    day = ts.astimezone(timezone.utc).date()
    monday = day - timedelta(days=day.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)


def _weeks_start(weeks: object, now: datetime) -> datetime:
    if isinstance(weeks, bool) or not isinstance(weeks, int) or weeks < 1:
        raise ValueError(f"denials weeks must be a whole number of at least 1, got {weeks!r}")
    return week_start(now) - (weeks - 1) * _WEEK


def _since_start(since: object, now: datetime) -> datetime:
    expected = f"denials since must be a date in the form YYYY-MM-DD, got {since!r}"
    if not isinstance(since, str) or not _DATE.fullmatch(since):
        raise ValueError(expected)
    try:
        day = date.fromisoformat(since)
    except ValueError as exc:
        raise ValueError(expected) from exc
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    if start > now:
        raise ValueError(f"denials since {since} is after now ({now:%Y-%m-%d})")
    return start


def period_from_args(weeks: int | None, since: str | None, now: datetime) -> Period:
    """The reporting window ending at `now` (ADR-7); raises `ValueError` on bad options.

    Default: the last 28 days. `weeks=N`: from the Monday N-1 weeks before
    `now`'s week, so the period holds N calendar weeks, the last one partial.
    `since="YYYY-MM-DD"`: from that date, 00:00 UTC. Not both.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if weeks is not None and since is not None:
        raise ValueError("give denials weeks or denials since, not both")
    if weeks is not None:
        return Period(start=_weeks_start(weeks, now), end=now)
    if since is not None:
        return Period(start=_since_start(since, now), end=now)
    return Period(start=now - timedelta(days=DEFAULT_DAYS), end=now)


@dataclass(frozen=True)
class TopRow:
    """One repeated denial kind: labels, identifiers, counts and times only (CON-2).

    `overrides` stays `None` here; the override counts are joined in later.
    """

    category: str
    hook: str | None
    rule: str | None
    tool: str | None
    count: int
    overrides: int | None
    last_session_id: str
    last_ts: datetime


@dataclass(frozen=True)
class DenialsSummary:
    """Everything the section renders for one repository and period (CON-2: no transcript text).

    Counter keys: `by_category` (category, side), `by_rule` (hook, rule, side)
    with `rule=None` for a hook without rules and `hook=None` for an
    unattributed hook deny, `by_reason` (category, classifier reason category).
    `side` is "main" or "subagent". `by_week` holds every Monday of the
    period in order, empty weeks included; `partial_weeks` are the ones the
    period cuts. `low_confidence` names the low-confidence categories seen.
    """

    period: Period
    files_read: int
    unreadable: int
    skipped_lines: int
    oldest_ts: datetime | None
    versions_seen: set[str]
    unknown_versions: set[str]
    by_category: Counter
    by_rule: Counter
    by_reason: Counter
    by_week: dict[datetime, Counter]
    partial_weeks: frozenset[datetime]
    low_confidence: frozenset[str]
    top: list[TopRow]
    unattributed: int
    hook_denies: int
    overrides: OverrideCounts | None = None  # joined by `with_overrides`; None = not read


def _week_rows(period: Period) -> dict[datetime, Counter]:
    rows: dict[datetime, Counter] = {}
    monday = week_start(period.start)
    while monday <= period.end:
        rows[monday] = Counter()
        monday += _WEEK
    return rows


def _partial_weeks(period: Period) -> frozenset[datetime]:
    first, last = week_start(period.start), week_start(period.end)
    partial = set()
    if period.start > first:
        partial.add(first)
    if period.end < last + _WEEK - timedelta(microseconds=1):
        partial.add(last)
    return frozenset(partial)


def _in_repo(cwd: str, root: str) -> bool:
    """Whether a line's cwd, worktree suffix stripped and casefolded, is `root` or under it."""
    if not cwd:
        return False
    key = _WORKTREE.sub("", cwd.casefold()).rstrip("/")
    return key == root or key.startswith(root + "/")


def _version_unchecked(version: str) -> bool:
    match = _VERSION.fullmatch(version)
    if match is None:
        return True
    low, high = CHECKED_VERSIONS
    return not low <= tuple(int(part) for part in match.groups()) <= high


@dataclass
class _Tally:
    """Mutable counts while one repository's results are aggregated."""

    period: Period
    versions: set[str] = field(default_factory=set)
    by_category: Counter = field(default_factory=Counter)
    by_rule: Counter = field(default_factory=Counter)
    by_reason: Counter = field(default_factory=Counter)
    by_week: dict[datetime, Counter] = field(default_factory=dict)
    low_confidence: set[str] = field(default_factory=set)
    kinds: dict[tuple, list] = field(default_factory=dict)  # key -> [count, last_ts, last_session]
    unattributed: int = 0
    hook_denies: int = 0

    def __post_init__(self) -> None:
        self.by_week = _week_rows(self.period)

    def add(self, result: ErrorResult) -> None:
        if result.version:
            self.versions.add(result.version)
        denial = classify(result.text, result.tool)
        if denial is not None:
            self._add_denial(denial, result)

    def _add_denial(self, denial: Denial, result: ErrorResult) -> None:
        side = SUBAGENT if result.sidechain else MAIN
        self.by_category[(denial.category, side)] += 1
        self.by_week[week_start(result.ts)][denial.category] += 1
        if denial.confidence == "low":
            self.low_confidence.add(denial.category)
        if denial.reason_category is not None:
            self.by_reason[(denial.category, denial.reason_category)] += 1
        if denial.category == HOOK_DENY:
            self._add_hook_deny(denial, side)
        for rule in denial.rules or (None,):
            self._add_kind((denial.category, denial.hook, rule, result.tool), result)

    def _add_hook_deny(self, denial: Denial, side: str) -> None:
        self.hook_denies += 1
        self.unattributed += denial.hook is None
        for rule in denial.rules or (None,):
            self.by_rule[(denial.hook, rule, side)] += 1

    def _add_kind(self, key: tuple, result: ErrorResult) -> None:
        entry = self.kinds.setdefault(key, [0, result.ts, result.session_id])
        entry[0] += 1
        # Latest wins; on a timestamp tie the greater session id, so input order never matters.
        if (result.ts, result.session_id) > (entry[1], entry[2]):
            entry[1], entry[2] = result.ts, result.session_id

    def top(self) -> list[TopRow]:
        rows = [TopRow(category=key[0], hook=key[1], rule=key[2], tool=key[3], count=count,
                       overrides=None, last_session_id=session, last_ts=ts)
                for key, (count, ts, session) in self.kinds.items()]
        rows.sort(key=lambda row: repr((row.category, row.hook, row.rule, row.tool)))
        rows.sort(key=lambda row: (row.count, row.last_ts), reverse=True)
        return rows[:TOP_LIMIT]


def aggregate(scans: Iterable[ScanResult], repo_root: Path, period: Period) -> DenialsSummary:
    """Count one repository's denials in `period` from scanned files (SDD walkthrough 4-6).

    A result counts when its `cwd` is `repo_root` or under it, after a
    worktree suffix is stripped; both compared casefolded (ADR-3).
    """
    scans = list(scans)
    root = str(repo_root).rstrip("/").casefold()
    tally = _Tally(period)
    for scan in scans:
        for result in scan.results:
            if period.contains(result.ts) and _in_repo(result.cwd, root):
                tally.add(result)
    return _summary(scans, tally)


def _summary(scans: list[ScanResult], tally: _Tally) -> DenialsSummary:
    oldest = [scan.oldest_ts for scan in scans if scan.oldest_ts is not None]
    return DenialsSummary(
        period=tally.period,
        files_read=sum(not scan.unreadable for scan in scans),
        unreadable=sum(scan.unreadable for scan in scans),
        skipped_lines=sum(scan.skipped_lines for scan in scans),
        oldest_ts=min(oldest, default=None),
        versions_seen=set(tally.versions),
        unknown_versions={v for v in tally.versions if _version_unchecked(v)},
        by_category=tally.by_category, by_rule=tally.by_rule, by_reason=tally.by_reason,
        by_week=tally.by_week, partial_weeks=_partial_weeks(tally.period),
        low_confidence=frozenset(tally.low_confidence), top=tally.top(),
        unattributed=tally.unattributed, hook_denies=tally.hook_denies,
    )


# ---------------------------------------------------------------------------
# Override counts from tcs-git-helpers' audit log (ADR-6).
# ---------------------------------------------------------------------------

# lib/override.sh writes `CLAUDE_ALLOW_<RULE>` for a granular override and the
# master name for the blanket switch. ask-guard.sh writes `hook=ask-guard` rows
# for asks, which are not overrides; protect-git-internals.sh writes denies under
# a non-CLAUDE_ALLOW_ name. Only `ts`, `env_var` and `hook` are read (CON-2).
_ALLOW_PREFIX = "CLAUDE_ALLOW_"
_MASTER_SWITCH = "CLAUDE_ALLOW_GIT_BAD_OPS"
_ASK_GUARD_HOOK = "ask-guard"


@dataclass(frozen=True)
class OverrideCounts:
    """Override consumptions in the period: per rule, the master switch apart.

    `by_rule` holds rule ids only; `unrecognised` is how many distinct names
    after `CLAUDE_ALLOW_` were not one -- the names themselves stay in the
    reader (CON-2). `log_found` is False when no home holds a readable log
    ("no override log").
    """

    by_rule: Counter = field(default_factory=Counter)
    master: int = 0
    unrecognised: int = 0
    log_found: bool = False


def _override_log_path(repo_root: Path, home: Path) -> Path:
    data = home / ".claude" / "plugins" / "data" / f"tcs-git-helpers-{repo_root.name}"
    return data / "audit" / "overrides.jsonl"


def _override_switch(line: str, period: Period) -> str | None:
    """The `env_var` of one in-period override row, else None. The parsed row
    is dropped here, so no other field (`command` above all) leaves this function."""
    try:
        row = json.loads(line)
        if not isinstance(row, dict) or row.get("hook") == _ASK_GUARD_HOOK:
            return None
        env_var = row.get("env_var")
        ts = _parse_ts(row.get("ts"))
    except (ValueError, RecursionError):  # _BadShape is a ValueError; RecursionError: deep nesting
        return None
    if not isinstance(env_var, str) or not period.contains(ts):
        return None
    return env_var if env_var.startswith(_ALLOW_PREFIX) and env_var != _ALLOW_PREFIX else None


def _count_override_log(path: Path, period: Period) -> tuple[Counter, int]:
    """One log's in-period counts: per rule name as written, and the master switch. Raises OSError."""
    by_rule: Counter = Counter()
    master = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if _ALLOW_PREFIX not in line:
                continue
            switch = _override_switch(line, period)
            if switch == _MASTER_SWITCH:
                master += 1
            elif switch is not None:
                by_rule[switch[len(_ALLOW_PREFIX):]] += 1
    return by_rule, master


def read_overrides(repo_root: Path, homes: Sequence[Path], period: Period) -> OverrideCounts:
    """Count override consumptions per rule over every home's log for `repo_root`.

    A log reached through two homes (a symlink or bind mount) is read once;
    a missing or unreadable log is skipped, and malformed rows never raise.
    """
    by_rule: Counter = Counter()
    master, found, seen = 0, False, set()
    for home in homes:
        path = _override_log_path(repo_root, home)
        try:
            stat = path.stat()
            if (stat.st_dev, stat.st_ino) in seen:
                continue
            log_rules, log_master = _count_override_log(path, period)
        except OSError:
            continue
        seen.add((stat.st_dev, stat.st_ino))
        by_rule.update(log_rules)
        master += log_master
        found = True
    return _override_counts(by_rule, master, found)


def _override_counts(by_rule: Counter, master: int, found: bool) -> OverrideCounts:
    """Keep the names that are rule ids; of the others only how many distinct ones there were."""
    rules = Counter({rule: n for rule, n in by_rule.items() if _SAFE_RULE.fullmatch(rule)})
    return OverrideCounts(by_rule=rules, master=master, unrecognised=len(by_rule) - len(rules),
                          log_found=found)


# ---------------------------------------------------------------------------
# Rendering one source's section (SDD User Interface & UX, F3-F6).
#
# `render` reads only a `DenialsSummary` (CON-2). The override counts reach it
# on the summary itself: `with_overrides` stores the `OverrideCounts` (counts
# and rule ids, no log text) and fills `TopRow.overrides` for block-bad-git-ops
# rule rows. Every free-form identifier printed -- tool, session id, version,
# rule id, reason category -- goes through `_safe` with its identifier shape,
# so a value that is not an identifier prints as "(unrecognised)", not as text.
# ---------------------------------------------------------------------------

BAD_GIT_OPS_HOOK = "tcs-git-helpers/block-bad-git-ops"
NOT_OBSERVABLE = (
    'settings deny rules, a "no" to a hook\'s ask prompt as its own kind (it counts as prompt rejected), '
    "denials in sessions whose transcripts were removed, sandbox blocks that surface as no tool error "
    '(see README "Denials")'
)
_CATEGORY_ORDER = tuple(dict.fromkeys(row.category for row in TABLE))
_NO_COUNT = "–"
_DAY = timedelta(days=1)


def with_overrides(summary: DenialsSummary, counts: OverrideCounts) -> DenialsSummary:
    """`summary` with the audit-log counts joined (ADR-6), so `render` needs nothing else."""
    return replace(summary, overrides=counts, top=[_top_with_overrides(row, counts) for row in summary.top])


def _top_with_overrides(row: TopRow, counts: OverrideCounts) -> TopRow:
    if not (counts.log_found and row.hook == BAD_GIT_OPS_HOOK and row.rule is not None):
        return row
    return replace(row, overrides=counts.by_rule.get(row.rule, 0))


def _period_text(period: Period) -> str:
    days = -((period.start - period.end) // _DAY)  # whole days, rounded up
    start, end = period.start.astimezone(timezone.utc), period.end.astimezone(timezone.utc)
    return f"{start:%Y-%m-%d} .. {end:%Y-%m-%d}, {days} days"


def _categories(summary: DenialsSummary) -> list[str]:
    """Categories seen, in table order."""
    seen = {category for category, _side in summary.by_category}
    return [c for c in _CATEGORY_ORDER if c in seen] + sorted(seen.difference(_CATEGORY_ORDER))


def _split(main: int, subagent: int) -> str:
    return f"{main + subagent:>4}  (main {main}, subagent {subagent})"


def _override_text(summary: DenialsSummary, rule: str) -> str:
    counts = summary.overrides
    if counts is None or not counts.log_found:
        return f"overridden {_NO_COUNT}"
    return f"overridden {counts.by_rule.get(rule, 0)}"


def _category_line(summary: DenialsSummary, category: str) -> str:
    counts = summary.by_category
    line = f"  {category:<20}{_split(counts[(category, MAIN)], counts[(category, SUBAGENT)])}"
    reasons = sorted(((n, reason) for (cat, reason), n in summary.by_reason.items() if cat == category),
                     key=lambda pair: (-pair[0], pair[1]))
    if reasons:
        line += "  " + ", ".join(f"[{_safe(reason, _REASON_CATEGORY)}] {n}" for n, reason in reasons)
    return line + ("  low confidence" if category in summary.low_confidence else "")


def _rules_by_hook(summary: DenialsSummary) -> dict[str | None, dict[str | None, Counter]]:
    by_hook: dict[str | None, dict[str | None, Counter]] = {}
    for (hook, rule, side), n in summary.by_rule.items():
        by_hook.setdefault(hook, {}).setdefault(rule, Counter())[side] += n
    return by_hook


def _hook_lines(summary: DenialsSummary) -> list[str]:
    """Each hook under "hook deny": its rules below it, or one inline count; unattributed last."""
    by_hook = _rules_by_hook(summary)
    lines = []
    for hook in sorted(by_hook, key=lambda h: (h is None, h or "")):
        rules, label = by_hook[hook], hook or "unattributed"
        if set(rules) == {None}:
            lines.append(f"    {label:<40}{_split(rules[None][MAIN], rules[None][SUBAGENT])}")
            continue
        lines.append(f"    {label}")
        for rule in sorted(rules, key=lambda r: (r is None, -sum(rules[r].values()), r or "")):
            lines.append(_rule_line(summary, hook, rule, rules[rule]))
    return lines


def _rule_line(summary: DenialsSummary, hook: str | None, rule: str | None, sides: Counter) -> str:
    label = _safe(rule, _SAFE_RULE) if rule is not None else "(rule not named)"
    line = f"      {label:<30}{_split(sides[MAIN], sides[SUBAGENT])}"
    if hook == BAD_GIT_OPS_HOOK and rule is not None:
        line += f"   {_override_text(summary, rule)}"
    return line


def _category_lines(summary: DenialsSummary) -> list[str]:
    lines = []
    for category in _categories(summary):
        lines.append(_category_line(summary, category))
        if category == HOOK_DENY:
            lines.extend(_hook_lines(summary))
    return lines


def _week_lines(summary: DenialsSummary) -> list[str]:
    """One row per Monday of the period, empty weeks included (F3 AC3)."""
    categories = _categories(summary)
    widths = [max(len(c), 4) for c in categories]
    lines = ["  " + f"{'Weeks (Mon)':<22}" + "  ".join(f"{c:>{w}}" for c, w in zip(categories, widths))]
    for monday, counts in summary.by_week.items():
        label = f"{monday:%Y-%m-%d}" + (" (partial)" if monday in summary.partial_weeks else "")
        cells = "  ".join(f"{counts[c]:>{w}}" for c, w in zip(categories, widths))
        lines.append(f"    {label:<20}{cells}")
    return lines


def _top_line(rank: int, row: TopRow) -> str:
    parts = [f"{rank}.", row.category]
    if row.category == HOOK_DENY:
        parts.append(row.hook or "unattributed")
    if row.rule is not None:
        parts.append(_safe(row.rule, _SAFE_RULE))
    parts += [_safe(row.tool) if row.tool else "(tool unknown)", str(row.count)]
    if row.overrides is not None:
        parts.append(f"overridden {row.overrides}")
    elif row.hook == BAD_GIT_OPS_HOOK and row.rule is not None:
        parts.append(f"overridden {_NO_COUNT}")
    parts += ["last", _safe(row.last_session_id), f"{row.last_ts.astimezone(timezone.utc):%Y-%m-%d %H:%M}"]
    return "    " + "  ".join(parts)


def _top_lines(summary: DenialsSummary) -> list[str]:
    return ["  Top repeated"] + [_top_line(rank, row) for rank, row in enumerate(summary.top, start=1)]


def _overrides_line(summary: DenialsSummary) -> str:
    """The master switch, and overridden rules with no rule line above (asks among them)."""
    counts = summary.overrides
    if counts is None or not counts.log_found:
        return f"  Overrides: no override log found, so override counts show {_NO_COUNT}"
    listed = {rule for hook, rule, _side in summary.by_rule if hook == BAD_GIT_OPS_HOOK}
    others = sorted((_safe(rule, _SAFE_RULE), n)
                    for rule, n in counts.by_rule.items() if n and rule not in listed)
    shown = [f"{rule} {n}" for rule, n in others if rule != _UNRECOGNISED]
    unrecognised = counts.unrecognised + len(others) - len(shown)
    line = f"  Overrides: master switch CLAUDE_ALLOW_GIT_BAD_OPS (all rules) {counts.master}"
    if shown:
        line += "; rules without a deny above: " + ", ".join(shown)
    if unrecognised:
        line += f"; {unrecognised} unrecognised rule name(s)"
    return line


def _partial_line(summary: DenialsSummary) -> str:
    """What could not be read or checked (F5 AC2/AC3); never a bare silence."""
    versions = sorted({_safe(v) for v in summary.unknown_versions})
    unchecked = (", ".join(versions) + " (their denials may be unclassified)") if versions else "none"
    return (f"  Partial reads: lines skipped that could not be read: {summary.skipped_lines}; "
            f"unreadable files: {summary.unreadable}; versions not checked: {unchecked}")


def _render_empty(summary: DenialsSummary) -> list[str]:
    head = (f"Denials ({_period_text(summary.period)}): no denials found in {summary.files_read} "
            f"transcript(s). That is not proof none happened -- not observable: {NOT_OBSERVABLE}")
    return [head, _overrides_line(summary), _partial_line(summary), ""]


def render(summary: DenialsSummary) -> list[str]:
    """The section's lines for one source and period; the only input is `summary` (CON-2)."""
    if not summary.by_category:
        return _render_empty(summary)
    oldest = f"{summary.oldest_ts.astimezone(timezone.utc):%Y-%m-%d}" if summary.oldest_ts else "unknown"
    header = (f"Denials ({_period_text(summary.period)}; transcripts: {summary.files_read} file(s) read, "
              f"oldest {oldest})")
    return [header, *_category_lines(summary), *_week_lines(summary), *_top_lines(summary),
            _overrides_line(summary), f"  Not observable: {NOT_OBSERVABLE}", _partial_line(summary), ""]


def render_not_enabled(label: str) -> list[str]:
    """F1 AC1: the section is off for this source, and the one line that turns it on."""
    return [f'Denials: not enabled for source "{label}". Add "denials = true" to its [[source]] '
            "entry in .claude/observability-sources.toml.", ""]


def _render_no_transcripts(period: Period, located: LocateResult) -> list[str]:
    """F1 AC2: no file in reach -- say so and name every place searched."""
    lines = [f"Denials ({_period_text(period)}): no transcripts found for this repository."]
    lines += [f"  searched: {path}" + (" (missing)" if path in located.missing else "")
              for path in located.searched] or ["  no home directories given"]
    return lines + [""]


def build_section(repo_root: Path, homes: Sequence[Path], period: Period) -> list[str]:
    """One enabled source's section: locate -> scan -> classify -> overrides -> aggregate -> render."""
    located = locate_transcripts(repo_root, homes)
    if not located.files:
        return _render_no_transcripts(period, located)
    summary = aggregate((scan_file(path, period) for path in located.files), repo_root, period)
    return render(with_overrides(summary, read_overrides(repo_root, homes, period)))
