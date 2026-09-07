#!/usr/bin/env python3
"""scripts/observability/report.py -- offline analysis over the observability record.

Spec 018 (observability of what loads and fires), phase 3. T3.1 turned the
JSONL record `logwrite.sh` and its adapters write into PRD F4's answers --
which instruction files loaded, how often, under which reasons, and which
configured files never did (SDD-AC-13). T3.2 adds this file's honesty
layer: the always-loaded layer's measured byte cost, separate from
conditional loads (SDD-AC-14), and reporting the recording state itself --
never a load figure -- when the record is empty, has no `kind: state`
probe, or is stale (SDD-AC-15).

ADR-6: this file is Python, pytest-covered, and runs offline -- nowhere near
the hook path, so the sub-millisecond budget (CON-7) does not apply here.
Every function below is pure over the paths and records it is handed: no
global state, no reliance on a real `$HOME` or a live session, so the whole
module is importable and unit-testable without one (tests/test_observability_report.py).

Three phase-2 findings this reader must respect (SDD/Application Data Models):

  1. `bytes` is written as a quoted string ("2048"), never a bare JSON number
     -- out of scope for T3.1, closed by T3.2's `_parse_bytes`/`byte_accounting`
     below, which cast on read (the SDD's chosen fix) and treat an absent
     or non-numeric `bytes` as unmeasurable, never as zero.
  2. `reason` can be an empty string. T2.1 deliberately removed a fabricated
     `session_start` default for a payload missing `load_reason`, because
     defaulting would make a real anomaly permanently indistinguishable from
     a genuine session-start load once it reaches this file. An empty (or
     absent) `reason` is therefore counted as UNKNOWN here, never folded
     into any named reason's count.
  3. A record with no usable `path` is never written upstream at all. This
     reader does not need to re-filter for that itself, but treats `path`
     as optional defensively rather than assuming every record it reads was
     necessarily well-formed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, NamedTuple, Sequence

# The five verified `load_reason` values (SDD/Application Data Models).
# `session_start` and `compact` are the always-loaded layer -- they cost on
# every session. The other three fire because something specific triggered
# them.
ALWAYS_LOADED_REASONS = frozenset({"session_start", "compact"})
CONDITIONAL_REASONS = frozenset({"nested_traversal", "include", "path_glob_match"})


@dataclass
class InstructionFileStats:
    """Per-file tally: how often it loaded, and under which reasons.

    `reason_counts` holds only named (non-empty) reasons -- an empty or
    missing `reason` increments `unknown_count` instead and is never folded
    in here (T2.1 finding, see module docstring point 2).
    """

    path: str
    load_count: int = 0
    reason_counts: dict[str, int] = field(default_factory=dict)
    unknown_count: int = 0

    def record(self, reason: str | None) -> None:
        self.load_count += 1
        if isinstance(reason, str) and reason:
            self.reason_counts[reason] = self.reason_counts.get(reason, 0) + 1
        else:
            self.unknown_count += 1

    @property
    def always_loaded(self) -> bool:
        """True if this file was observed loading at session_start or compact."""
        return bool(set(self.reason_counts) & ALWAYS_LOADED_REASONS)

    @property
    def conditionally_loaded(self) -> bool:
        """True if this file was observed loading for a triggered reason.

        Independent of `always_loaded` -- a file can be both (loaded eagerly
        AND also re-triggered by a glob match, say), and both flags are true
        at once in that case. Classification is on the reasons actually
        observed, never a single label that would hide one or the other.
        """
        return bool(set(self.reason_counts) & CONDITIONAL_REASONS)


# ---------------------------------------------------------------------------
# Reading the record: the rotation chain, as one logical file.
# ---------------------------------------------------------------------------


def rotation_chain(base_path: Path) -> list[Path]:
    """The generations of a rotated log, oldest first, skipping absent ones.

    SDD/Data Storage Changes: rotation runs `.jsonl -> .1 -> .2 -> .3`, with
    `.3` the oldest surviving generation and no `.4` ever created. Reading
    the chain "as one logical record without double-counting" means: `.3`,
    then `.2`, then `.1`, then the base file -- each read exactly once, in
    chronological order. A generation that does not exist is simply skipped,
    not an error.
    """
    ordered = [base_path.with_name(base_path.name + suffix) for suffix in (".3", ".2", ".1")]
    ordered.append(base_path)
    return [p for p in ordered if p.is_file()]


def read_events(base_path: Path) -> tuple[list[dict], int]:
    """Read every generation of the rotated log as one logical stream.

    Returns `(records, unparseable_line_count)`. CON-10 / the SDD's error
    handling: reads with `errors="replace"` and counts -- rather than
    raises on -- a line `json.loads` cannot parse. A silently-dropped line
    is exactly the failure mode this whole spec exists to prevent, so the
    count is returned rather than swallowed.
    """
    records: list[dict] = []
    unparseable = 0
    for path in rotation_chain(base_path):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                unparseable += 1
    return records, unparseable


# ---------------------------------------------------------------------------
# The load report: per-file counts and reasons.
# ---------------------------------------------------------------------------


def instruction_stats(records: Iterable[dict]) -> dict[str, InstructionFileStats]:
    """Group `kind: instruction` records by path, counting loads and reasons.

    Ignores every other `kind` (skill, agent, hook, state) without choking
    on it. A record with no usable `path` is defensively skipped rather
    than assumed impossible -- see module docstring point 3.
    """
    stats: dict[str, InstructionFileStats] = {}
    for rec in records:
        if rec.get("kind") != "instruction":
            continue
        path = rec.get("path")
        if not path:
            continue
        entry = stats.setdefault(path, InstructionFileStats(path=path))
        entry.record(rec.get("reason"))
    return stats


def never_loaded(inventory: Iterable[str], stats: dict[str, InstructionFileStats]) -> list[str]:
    """Configured instruction files with no load record at all, sorted.

    The denominator is the instruction inventory (SDD/The two inventories);
    the numerator is whatever the hook actually recorded. A hook supplies
    only the numerator, so "never loaded" is a set difference against a
    denominator this reader is handed, not something it can infer alone.
    """
    return sorted(set(inventory) - set(stats.keys()))


# ---------------------------------------------------------------------------
# Byte accounting: the always-loaded layer's cost, separate from conditional
# loads (T3.2, SDD-AC-14).
# ---------------------------------------------------------------------------


def _parse_bytes(value: object) -> int | None:
    """Cast a record's `bytes` field to `int`, or `None` when it cannot be.

    The SDD deliberately left `bytes` a quoted string in the record shape
    ("(b) `report.py` casts on read -- no change to this shape at all") --
    so this is the one place that cast happens. `None` covers both typing
    traps this task exists to catch: the key is ABSENT (T2.1: the file
    could not be stat'ed) and the key is PRESENT but not a valid integer (a
    producer bug). Both are "unmeasurable", never a silent zero -- callers
    must exclude a `None` from any total rather than adding it in.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ByteAccounting(NamedTuple):
    """The measured byte cost of the always-loaded layer, separate from
    conditional loads (SDD-AC-14), plus what could not be measured at all.

    Attribution is per LOAD EVENT (per record), not per file: each `kind:
    instruction` record's own `bytes` reading is counted toward exactly one
    of `always_loaded_bytes` / `conditional_bytes` / `unknown_reason_bytes`,
    chosen by THAT record's own `reason` -- never toward more than one
    bucket, and never dropped. A file that shows up as both always-loaded
    and conditional overall (loaded eagerly at session start, and also
    re-triggered later by a glob match -- `InstructionFileStats.always_loaded`
    and `.conditionally_loaded` can both be true for one path) is not a
    double-counting hazard under this rule: the ambiguity lives at the
    per-file summary level, but each individual load event still carries
    exactly one reason, so its own bytes land in exactly one bucket.

    `unknown_reason_bytes` exists so a record with an empty/missing/non-string
    `reason` (T2.1's "unknown" reason, module docstring point 2) still has
    its measurable bytes accounted for somewhere, rather than silently
    disappearing because they could not be classified into a layer.

    `unmeasurable_count` is the number of `kind: instruction` records whose
    `bytes` could not be cast to `int` at all (absent, or present but not
    numeric) -- see `_parse_bytes`. These contribute to NONE of the byte
    totals above; counting them as zero would be exactly the dishonesty
    SDD-AC-14/-15 exist to prevent.
    """

    always_loaded_bytes: int
    conditional_bytes: int
    unknown_reason_bytes: int
    unmeasurable_count: int


def byte_accounting(records: Iterable[dict]) -> ByteAccounting:
    """Sum `kind: instruction` records' `bytes` into the buckets above.

    Ignores every other `kind`, the same way `instruction_stats` does.
    """
    always_loaded_bytes = 0
    conditional_bytes = 0
    unknown_reason_bytes = 0
    unmeasurable_count = 0

    for rec in records:
        if rec.get("kind") != "instruction":
            continue
        size = _parse_bytes(rec.get("bytes"))
        if size is None:
            unmeasurable_count += 1
            continue
        reason = rec.get("reason")
        if isinstance(reason, str) and reason in ALWAYS_LOADED_REASONS:
            always_loaded_bytes += size
        elif isinstance(reason, str) and reason in CONDITIONAL_REASONS:
            conditional_bytes += size
        else:
            unknown_reason_bytes += size

    return ByteAccounting(
        always_loaded_bytes=always_loaded_bytes,
        conditional_bytes=conditional_bytes,
        unknown_reason_bytes=unknown_reason_bytes,
        unmeasurable_count=unmeasurable_count,
    )


# ---------------------------------------------------------------------------
# The honesty rule: report the recording state, not a load figure, when the
# record is empty or stale (T3.2, SDD-AC-15, Quality Requirements/Honesty).
# ---------------------------------------------------------------------------

# `ts` is UTC RFC3339 at second precision (e.g. "2026-09-06T16:43:28Z"),
# per the SDD's Application Data Models. `datetime.fromisoformat` before
# Python 3.11 rejects the trailing "Z", so this parses explicitly rather
# than assuming a runtime new enough to accept it.
_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# How old the newest record in the whole log may be before this report calls
# it stale relative to `now` -- SDD-AC-15's "a record whose newest entry is
# older than the current session." The SDD does not pin a value. Six hours
# is chosen as a deliberately generous upper bound on a single interactive
# session's length: long enough that a genuinely active session's own
# writes will always fall inside it, short enough that a log left over from
# a previous day is reliably caught. Stated here, and in the report output,
# rather than left as an unexplained magic number.
STALE_THRESHOLD_SECONDS = 6 * 60 * 60


def _parse_ts(value: object) -> datetime | None:
    """Parse a record's `ts` field, or `None` if it is missing or malformed.

    Malformed input must never crash the report -- an unparseable `ts` is
    simply excluded from `newest_ts`'s comparison, the same posture as an
    unmeasurable `bytes` value above.
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, _TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def newest_ts(records: Iterable[dict]) -> str | None:
    """The latest `ts` value across ALL records, regardless of `kind`, as
    the original string (not the parsed `datetime`) -- or `None` if no
    record carries a parseable one.

    Computed by explicit comparison rather than assumed from read order:
    `read_events` reads generations oldest-first and appends lines in
    file order, so records are USUALLY chronological, but "the newest
    entry" should not silently depend on that ordering holding for every
    caller of this function.
    """
    best: datetime | None = None
    best_raw: str | None = None
    for rec in records:
        parsed = _parse_ts(rec.get("ts"))
        if parsed is not None and (best is None or parsed > best):
            best = parsed
            best_raw = rec.get("ts")
    return best_raw


def latest_state_record(records: Sequence[dict]) -> dict | None:
    """The most recent `kind: state` record (selfcheck's probe), or `None`
    if the log carries none at all.

    "Most recent" by position: `read_events` returns records in
    chronological order (oldest generation first, lines in file order), so
    the last `kind: state` record encountered is the newest one.
    """
    for rec in reversed(records):
        if rec.get("kind") == "state":
            return rec
    return None


def _state_enabled(state: dict) -> bool:
    """Whether a `kind: state` record reports recording as on.

    `enabled` is the string `"1"` or `"0"` (`selfcheck.sh` writes
    `_enabled=0`/`_enabled=1` through the same generic quoting writer every
    field goes through) -- NOT a JSON bool despite the SDD's `bool` type
    annotation for it. A plain Python truthiness check (`if state["enabled"]`)
    would treat the string `"0"` as truthy and report recording as on when
    it is actually off -- the exact inversion SDD-AC-15 exists to prevent.
    Compared against `"1"` explicitly for that reason.
    """
    return state.get("enabled") == "1"


class RecordingStatus(NamedTuple):
    """What the report can honestly say about whether recording was on.

    Built by `recording_status`, a pure function of the records and an
    injected clock -- never wall time, so every case is deterministic and
    test fixtures never depend on when the test happens to run.
    """

    # Whether a `kind: state` record (selfcheck's probe) exists anywhere in
    # the log. False means the recording state is UNKNOWN -- not "off" and
    # not "on": nothing ever wrote the one record that could answer the
    # question, per the T3.2 task text ("do not assume it was on, and do
    # not assume it was off").
    state_known: bool
    # `None` when `state_known` is False; otherwise the last known value
    # from the newest `kind: state` record, decoded with `_state_enabled`.
    enabled: bool | None
    # The newest `ts` across every record in the log, regardless of kind,
    # or `None` if no record carries a parseable one (including an empty
    # log).
    newest_ts: str | None
    # True if `newest_ts` exists and is more than `STALE_THRESHOLD_SECONDS`
    # older than `now` -- i.e. the log's newest entry predates what this
    # report considers "the current session."
    stale: bool


def recording_status(records: Sequence[dict], now: datetime) -> RecordingStatus:
    """Assemble the honesty-rule verdict: is a `kind: state` record present,
    what did it last say, and is the whole log stale relative to `now`.

    `now` is an explicit parameter, never `datetime.now()` read inside this
    function -- see the module's purity note and the STALE_THRESHOLD_SECONDS
    comment above. The CLI entry point (`main`) is the only caller that ever
    supplies a real wall-clock value.
    """
    state = latest_state_record(records)
    latest = newest_ts(records)
    stale = False
    if latest is not None:
        parsed = _parse_ts(latest)
        if parsed is not None and (now - parsed).total_seconds() > STALE_THRESHOLD_SECONDS:
            stale = True
    return RecordingStatus(
        state_known=state is not None,
        enabled=_state_enabled(state) if state is not None else None,
        newest_ts=latest,
        stale=stale,
    )


# ---------------------------------------------------------------------------
# The instruction inventory: what *could* have loaded (SDD/The two inventories).
# ---------------------------------------------------------------------------

# An `@`-import token: `@` preceded by start-of-line or whitespace (so an
# email-shaped "user@host" mid-line is never mistaken for one), followed by
# a non-whitespace path.
#
# This also matches a non-import `@token` (a markdown table cell, a stray
# mention) that was never meant as an import. That is safe only because
# `_collect_claude_md_imports` below drops any candidate that does not
# resolve to a real file (`resolved.is_file()`), and the inventory this
# feeds is documented to over-list rather than under-list (SDD/The two
# inventories) -- a false-positive token simply never makes it into `found`.
_IMPORT_RE = re.compile(r"(?:^|(?<=\s))@(\S+)", re.MULTILINE)


def _redact_path(path: Path, repo_root: Path) -> str:
    """Repo-relative when inside the repo, else basename only (R-3).

    Mirrors `_observability_redact_path` in `logwrite.sh` so an inventory
    entry reads the same way a real record's `path` field would, and the
    two can be compared for equality.
    """
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _collect_claude_md_imports(
    start: Path,
    home_dir: Path,
    found: set[Path],
    seen: set[Path] | None = None,
) -> None:
    """Walk a CLAUDE.md and every `@`-import reachable from it, transitively."""
    if seen is None:
        seen = set()
    resolved = start.resolve()
    if resolved in seen or not resolved.is_file():
        return
    seen.add(resolved)
    found.add(resolved)

    text = resolved.read_text(encoding="utf-8", errors="replace")
    for token in _IMPORT_RE.findall(text):
        if token.startswith("~/"):
            candidate = home_dir / token[2:]
        elif token.startswith("/"):
            candidate = Path(token)
        else:
            candidate = resolved.parent / token
        _collect_claude_md_imports(candidate, home_dir, found, seen)


# Directories never descended into while walking the repo for nested
# CLAUDE.md files -- version control internals and dependency trees the
# loader itself never reads as instructions.
_WALK_SKIP_DIRS = frozenset({".git", "node_modules", ".venv"})


def _is_test_fixture_path(relative: Path) -> bool:
    """True if `relative`'s parts contain a `tests` segment immediately
    followed by a `fixtures` segment.

    SDD/The two inventories, exclusion: a CLAUDE.md under a `tests/fixtures/`
    path segment is test data, not configuration. Matched by path *segment*,
    not substring, so a directory named e.g. `tests-fixtures` or
    `my-tests/fixtures-sample` -- which merely contains the words -- is not
    wrongly excluded, at any depth.
    """
    parts = relative.parts
    return any(
        parts[i] == "tests" and parts[i + 1] == "fixtures" for i in range(len(parts) - 1)
    )


def _walk_nested_claude_md(repo_root: Path) -> set[Path]:
    """Every CLAUDE.md under `repo_root`, excluding the root file itself and
    any under a `tests/fixtures/` path segment (test data, not
    configuration).

    Amendment, 2026-09-07 (T3.1 review, SDD/The two inventories): the
    original inventory only walked the CLAUDE.md hierarchy from `repo_root`
    upward, missing nested subdirectory CLAUDE.md files entirely -- even
    though `nested_traversal` is a verified `load_reason`, so the record can
    demonstrably show one loading. A nested file that never loads was
    therefore invisible to "configured but never loaded" (PRD F4). This
    closes that gap with a plain filesystem walk, skipping `.git`,
    `node_modules`, and `.venv`.
    """
    found: set[Path] = set()
    root_resolved = repo_root.resolve()
    for candidate in repo_root.rglob("CLAUDE.md"):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved == root_resolved / "CLAUDE.md":
            continue
        try:
            relative = resolved.relative_to(root_resolved)
        except ValueError:
            continue
        if any(part in _WALK_SKIP_DIRS for part in relative.parts):
            continue
        if _is_test_fixture_path(relative):
            continue
        found.add(resolved)
    return found


class InstructionInventory(NamedTuple):
    """`walk_instruction_inventory`'s result: the redacted paths found, and
    whether gitignore filtering could actually be applied to the walk
    (SDD/The two inventories, second amendment, 2026-09-07).

    `git_filtered` is False only when git is unavailable or `repo_root` is
    not a git repository -- in which case `entries` is the walk unfiltered,
    never partial (fail open: silently under-reporting the denominator is
    worse than not filtering at all). `build_load_report` renders this so a
    reader can tell which mode produced a given count.
    """

    entries: list[str]
    git_filtered: bool


def _is_inside(path: Path, root_resolved: Path) -> bool:
    """True if `path` (already resolved) sits inside `root_resolved`.

    A path outside the repo (e.g. a `home_dir` entry) is not "ignored" by
    git -- it is simply out of `git check-ignore`'s scope, and asking git
    about it can produce a fatal "outside repository" error rather than a
    clean answer. Splitting on this BEFORE calling git is what lets that
    error never occur in the first place, rather than having to parse it.
    """
    try:
        path.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _git_ignored(paths: Sequence[Path], repo_root: Path) -> set[Path] | None:
    """Which of `paths` (already known to be inside `repo_root`) git ignores.

    One batched `git check-ignore --stdin -z` call rather than one per
    candidate. Exit codes, per `git-check-ignore(1)`: 0 = at least one path
    is ignored, 1 = none are -- both are normal, successful answers -- and
    128 = error (not a repository, or some other failure). Returns `None`
    for 128, for a missing `git` executable (`FileNotFoundError`), or for
    any other exec failure (`OSError`): this is the fail-open signal
    `walk_instruction_inventory` uses to keep every candidate rather than
    return an empty or partial inventory.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "check-ignore", "--stdin", "-z"],
            input="\0".join(str(p) for p in paths),
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode not in (0, 1):
        return None
    return {Path(p) for p in result.stdout.split("\0") if p}


def walk_instruction_inventory(repo_root: Path, home_dir: Path) -> InstructionInventory:
    """The instruction inventory: what could load, enumerated by filesystem walk.

    SDD/The two inventories -- a filesystem walk at report time, not a
    maintained manifest, because a manifest would drift and the walk is
    exactly the set the loader itself can reach:

      - the CLAUDE.md hierarchy from `repo_root` upward, plus every
        `@`-import reachable from it, resolved transitively
      - every nested CLAUDE.md within the repo, excluding any under a
        `tests/fixtures/` path segment (amendment, 2026-09-07, T3.1 review --
        see docs/XDD/specs/018-observability-load-and-fire-log/solution.md,
        "The two inventories")
      - docs/ai/memory/*.md
      - .claude/rules/**/*.md, in the repo and under `home_dir`
      - `home_dir`/.claude/CLAUDE.md

    A path git ignores is excluded (second amendment, 2026-09-07): it is not
    this repo's configuration, and counting it would corrupt the specific
    answer the report is trying to give -- not merely pad a total -- when,
    say, a gitignored local mount contains a second copy of a real
    CLAUDE.md. Determined with `git check-ignore` at walk time, over
    candidates inside `repo_root` only (see `_is_inside`); when git is
    absent or `repo_root` is not a repository the walk proceeds unfiltered,
    and `InstructionInventory.git_filtered` says so.

    Pure over the paths handed in: no reliance on a real `$HOME` or `cwd` --
    `repo_root` is passed explicitly as git's working directory (`-C`). A
    CLI entry point passes `Path.home()`; every test passes an explicit
    `tmp_path` fixture instead.
    """
    found: set[Path] = set()

    root_claude = repo_root / "CLAUDE.md"
    if root_claude.is_file():
        _collect_claude_md_imports(root_claude, home_dir, found)

    if repo_root.is_dir():
        found.update(_walk_nested_claude_md(repo_root))

    memory_dir = repo_root / "docs" / "ai" / "memory"
    if memory_dir.is_dir():
        found.update(p for p in memory_dir.glob("*.md") if p.is_file())

    repo_rules = repo_root / ".claude" / "rules"
    if repo_rules.is_dir():
        found.update(p for p in repo_rules.rglob("*.md") if p.is_file())

    home_rules = home_dir / ".claude" / "rules"
    if home_rules.is_dir():
        found.update(p for p in home_rules.rglob("*.md") if p.is_file())

    home_claude_md = home_dir / ".claude" / "CLAUDE.md"
    if home_claude_md.is_file():
        found.add(home_claude_md)

    found = {p.resolve() for p in found}
    root_resolved = repo_root.resolve()
    inside_repo = {p for p in found if _is_inside(p, root_resolved)}
    outside_repo = found - inside_repo

    ignored = _git_ignored(sorted(inside_repo), repo_root)
    if ignored is None:
        git_filtered = False
        kept = found
    else:
        git_filtered = True
        kept = (inside_repo - ignored) | outside_repo

    return InstructionInventory(
        # De-duplicate after redaction: _redact_path is many-to-one by design
        # (outside-repo paths collapse to basename), so distinct Path objects
        # can redact to the same string. De-duplicating Path objects upstream
        # is insufficient -- the set here removes the redacted duplicates.
        entries=sorted({_redact_path(p, repo_root) for p in kept}),
        git_filtered=git_filtered,
    )


# ---------------------------------------------------------------------------
# Assembling the text report (SDD-AC-13 / PRD F4).
# ---------------------------------------------------------------------------


def _render_recording_status(recording: RecordingStatus) -> list[str]:
    """The honesty-rule headline (SDD-AC-15): leads the report, always.

    Four distinguishable verdicts, per the T3.2 task text -- never
    collapsed into "0 files loaded" or a bare presence/absence check:
      - no `kind: state` record at all           -> unknown
      - a `kind: state` record says `enabled=0`  -> not recording
      - `enabled=1`, and the log is stale         -> was recording, but stale
      - `enabled=1`, and the log is current       -> recording
    """
    if not recording.state_known:
        line = (
            "Recording state: UNKNOWN -- no `kind: state` record (selfcheck's probe) "
            "was found in this log. This does not mean recording is off; it means "
            "nothing has confirmed either way. Run selfcheck.sh to check."
        )
    elif recording.enabled is False:
        line = "Recording state: NOT RECORDING (last `kind: state` record reported enabled=0)."
    elif recording.stale:
        line = (
            "Recording state: STALE -- the newest entry in this log "
            f"({recording.newest_ts}) is older than the "
            f"{STALE_THRESHOLD_SECONDS // 3600}-hour threshold this report uses for "
            "\"the current session,\" so the figures below describe a previous "
            "session, not this one."
        )
    else:
        line = "Recording state: recording (confirmed by the last selfcheck round-trip)."
        if recording.newest_ts:
            line += f" Newest entry: {recording.newest_ts}."
    return [line, ""]


def _render_byte_accounting(byte_stats: ByteAccounting) -> list[str]:
    """The always-loaded layer's measured byte cost, separate from
    conditional loads (SDD-AC-14), and how many records were unmeasurable.
    """
    lines = [
        "Byte cost -- always-loaded layer: "
        f"{byte_stats.always_loaded_bytes} byte(s); conditional loads: "
        f"{byte_stats.conditional_bytes} byte(s).",
    ]
    if byte_stats.unknown_reason_bytes:
        lines.append(
            f"  {byte_stats.unknown_reason_bytes} byte(s) recorded under an unknown "
            "load reason, counted separately (not folded into either total above)."
        )
    if byte_stats.unmeasurable_count:
        lines.append(
            f"  {byte_stats.unmeasurable_count} record(s) were unmeasurable (no usable "
            "`bytes` -- the file could not be stat'ed, or its size was not a valid "
            "number) and are excluded from every total above -- never counted as zero."
        )
    lines.append("")
    return lines


def build_load_report(
    stats: dict[str, InstructionFileStats],
    inventory: Sequence[str],
    unparseable: int = 0,
    git_filtered: bool = True,
    byte_stats: ByteAccounting | None = None,
    recording: RecordingStatus | None = None,
) -> str:
    """Render the load report: per-file counts and reasons, and what never loaded.

    States which inventory was used, how many entries it found, and whether
    gitignore filtering was applied to the walk, so a surprising coverage
    figure can be traced to the denominator rather than assumed to be about
    usage (SDD/The two inventories, last line, and the second amendment,
    2026-09-07). `git_filtered=False` means the walk is unfiltered because
    git was unavailable or `repo_root` was not a repository.

    `byte_stats` and `recording` are optional (T3.2, added after this
    function's original contract) so every pre-existing caller and test
    keeps working unchanged when it does not pass them. When `recording` IS
    given, its verdict is rendered FIRST, ahead of the inventory line and
    everything else -- the honesty rule (SDD-AC-15) is that an empty or
    stale record must lead with the recording state, never with a load
    figure presented as if it were a finding.
    """
    lines: list[str] = []

    if recording is not None:
        lines.extend(_render_recording_status(recording))

    mode = (
        "gitignore-filtered" if git_filtered
        else "unfiltered -- git unavailable or repo_root is not a git repository"
    )
    lines.append(
        f"Instruction inventory (filesystem walk, {mode}): "
        f"{len(inventory)} configured file(s) found."
    )
    if unparseable:
        lines.append(f"{unparseable} log line(s) could not be parsed and were skipped.")
    lines.append("")

    if byte_stats is not None:
        lines.extend(_render_byte_accounting(byte_stats))

    lines.append(f"Loaded instruction files ({len(stats)}):")
    for path in sorted(stats):
        entry = stats[path]
        reason_parts = [f"{r}={c}" for r, c in sorted(entry.reason_counts.items())]
        if entry.unknown_count:
            reason_parts.append(f"unknown={entry.unknown_count}")
        reasons = ", ".join(reason_parts) if reason_parts else "no reason recorded"
        if entry.always_loaded and entry.conditionally_loaded:
            layer = "always+conditional"
        elif entry.always_loaded:
            layer = "always"
        elif entry.conditionally_loaded:
            layer = "conditional"
        else:
            layer = "unknown"
        lines.append(f"  {path}: {entry.load_count} load(s) [{layer}] ({reasons})")

    missing = never_loaded(inventory, stats)
    lines.append("")
    lines.append(f"Configured but never loaded ({len(missing)}):")
    for path in missing:
        lines.append(f"  {path}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point.
# ---------------------------------------------------------------------------


def _resolve_events_path(data_dir_override: str | None, repo_root: Path, home_dir: Path) -> Path:
    """Mirror `_observability_data_dir` (logwrite.sh, ADR-1) for the CLI only.

    Not used by any test above -- those construct an events path directly,
    which is the point: the pure functions never need this resolution, only
    the CLI convenience wrapper does.
    """
    if data_dir_override:
        data_dir = Path(data_dir_override)
    else:
        data_dir = home_dir / ".claude" / "plugins" / "data" / f"observability-{repo_root.name}"
    return data_dir / "observability" / "events.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--events", type=Path, default=None,
        help="Path to events.jsonl (default: resolved the same way logwrite.sh does)",
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(),
        help="Repo root for path redaction and the instruction inventory walk",
    )
    parser.add_argument(
        "--home", type=Path, default=Path.home(),
        help="Home directory for the instruction inventory walk",
    )
    parser.add_argument(
        "--data-dir", default=None,
        help="Override for $CLAUDE_OBSERVABILITY_DATA-style data directory",
    )
    args = parser.parse_args(argv)

    events_path = args.events or _resolve_events_path(args.data_dir, args.repo_root, args.home)
    if not rotation_chain(events_path):
        print(f"No record found at {events_path} (or any of its rotated generations).")
        return 0

    records, unparseable = read_events(events_path)
    stats = instruction_stats(records)
    inventory = walk_instruction_inventory(args.repo_root, args.home)
    byte_stats = byte_accounting(records)
    # datetime.now() is the one place this module reads the wall clock --
    # every pure function above takes `now` as an explicit parameter instead
    # (see RecordingStatus / recording_status), so only this CLI wrapper is
    # untestable-by-construction, exactly like `Path.cwd()`/`Path.home()`
    # above.
    recording = recording_status(records, datetime.now(timezone.utc))
    print(
        build_load_report(
            stats,
            inventory.entries,
            unparseable,
            inventory.git_filtered,
            byte_stats=byte_stats,
            recording=recording,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
