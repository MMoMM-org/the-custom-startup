#!/usr/bin/env python3
"""scripts/observability/report.py -- offline analysis over the observability record.

Spec 018 (observability of what loads and fires), phase 3, T3.1: turns the
JSONL record `logwrite.sh` and its adapters write into PRD F4's answers --
which instruction files loaded, how often, under which reasons, and which
configured files never did (SDD-AC-13).

ADR-6: this file is Python, pytest-covered, and runs offline -- nowhere near
the hook path, so the sub-millisecond budget (CON-7) does not apply here.
Every function below is pure over the paths and records it is handed: no
global state, no reliance on a real `$HOME` or a live session, so the whole
module is importable and unit-testable without one (tests/test_observability_report.py).

Three phase-2 findings this reader must respect (SDD/Application Data Models):

  1. `bytes` is written as a quoted string ("2048"), never a bare JSON number
     -- out of scope for T3.1 (byte accounting is T3.2), but a record
     carrying it must not be rejected.
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
        entries=sorted(_redact_path(p, repo_root) for p in kept),
        git_filtered=git_filtered,
    )


# ---------------------------------------------------------------------------
# Assembling the text report (SDD-AC-13 / PRD F4).
# ---------------------------------------------------------------------------


def build_load_report(
    stats: dict[str, InstructionFileStats],
    inventory: Sequence[str],
    unparseable: int = 0,
    git_filtered: bool = True,
) -> str:
    """Render the load report: per-file counts and reasons, and what never loaded.

    States which inventory was used, how many entries it found, and whether
    gitignore filtering was applied to the walk, so a surprising coverage
    figure can be traced to the denominator rather than assumed to be about
    usage (SDD/The two inventories, last line, and the second amendment,
    2026-09-07). `git_filtered=False` means the walk is unfiltered because
    git was unavailable or `repo_root` was not a repository.
    """
    lines: list[str] = []
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
    print(build_load_report(stats, inventory.entries, unparseable, inventory.git_filtered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
