"""`scripts/observability/report.py` must turn the JSONL record into PRD F4's answers.

Why this exists: `report.py` is the only place the raw record becomes an answer
to "what loaded, how often, and what never did" (SDD-AC-13, PRD F4). Two of
T2.1's phase-2 findings constrain every test here (see
docs/XDD/specs/018-observability-load-and-fire-log/plan/phase-3.md, Key
Decisions): an empty `reason` must be counted as unknown rather than folded
into a named reason's count -- the fabricated `session_start` default it
replaced would make a real anomaly permanently indistinguishable from a
genuine session-start load -- and the rotation chain (`.jsonl` plus
`.1`-`.3`) must be read as one logical record, oldest generation first,
without double-counting a line.

The module must be importable and unit-testable without a live session: every
test here builds its own fixture files under tmp_path rather than touching a
real $HOME or a real events.jsonl.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "observability"))

import report  # noqa: E402  (sys.path must be extended first)
import sources  # noqa: E402  (spec-019 T3.3: Source/HomeStatus fixtures for the per-source tests below)

REPORT_PY = REPO_ROOT / "scripts" / "observability" / "report.py"
LOGWRITE_SH = REPO_ROOT / "plugins" / "tcs-helper" / "scripts" / "observability" / "logwrite.sh"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _write_source_events(repo_root: Path, home: Path, records: list[dict]) -> None:
    """spec-019 T3.3: place a fixture events file at the exact path
    `report._resolve_events_path` resolves for `(repo_root, home)` -- the
    same real resolution `_build_source_report` uses per home, not a
    hand-picked location a test happens to read from."""
    path = report._resolve_events_path(None, repo_root, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(path, records)


def _init_git_repo(repo_root: Path) -> None:
    """A real git repo fixture for `git check-ignore` to run against.

    House rule (docs/ai/memory/active.md): a failed `git init` in a fixture
    can fall back to the parent `.git/` and leak commits onto this session's
    own branch. `repo_root` is created first so `git init` has somewhere of
    its own to put `.git`, `-C` is used instead of `cd`, and both config
    scopes are pointed at `os.devnull` so no real user/global git config
    (and no stray identity) leaks into the fixture.
    """
    repo_root.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    result = subprocess.run(
        ["git", "-C", str(repo_root), "init", "-q"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def _git_add(repo_root: Path, *relative_paths: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    result = subprocess.run(
        ["git", "-C", str(repo_root), "add", *relative_paths],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def _instruction(
    path: str,
    reason: str,
    session: str = "s1",
    bytes_value: str | bool | None = None,  # bool case is deliberate corruption for _parse_bytes guard test
    ts: str = "2026-09-06T16:43:28Z",
    repo: str | None = "the-custom-startup",  # spec-019 T3.1: pass "" or None to exercise the unknown bucket
) -> dict:
    record = {
        "ts": ts,
        "kind": "instruction",
        "session": session,
        "repo": repo,
        "path": path,
        "scope": "Project",
        "reason": reason,
    }
    if repo is None:
        del record["repo"]  # spec-019 T3.1: a truncated/hand-built record can lack the key entirely
    if bytes_value is not None:
        record["bytes"] = bytes_value
    return record


def _state(
    enabled: str,
    detail: str = "0",
    note: str = "selfcheck probe x",
    ts: str = "2026-09-06T16:43:28Z",
    session: str = "s1",
) -> dict:
    """A `kind: state` record, as `selfcheck.sh` writes it (T2.4).

    `enabled` and `detail` are the strings `"1"`/`"0"` -- the same generic
    quoting `_instruction`'s `bytes_value` goes through, and the truthiness
    trap this task's tests exist to catch (module docstring point 3 of the
    T3.2 task text).
    """
    return {
        "ts": ts,
        "kind": "state",
        "session": session,
        "repo": "the-custom-startup",
        "enabled": enabled,
        "detail": detail,
        "note": note,
    }


def _hook(
    hook_event: str = "PreToolUse",
    matcher: str = "Skill",
    ms: str | bool | None = "0.001",
    exit_value: str | bool | None = "0",
    scope_note: str | None = "single",
    session: str = "s1",
    ts: str = "2026-09-07T12:56:26Z",
) -> dict:
    """A `kind: hook` record, as `timed-wrapper.sh` writes it (T3.5).

    `ms` and `exit_value` default to the quoted-string shape the wrapper's
    generic writer actually produces (`"0.001"`, `"0"`) -- never bare JSON
    numbers -- the same convention `_instruction`'s `bytes_value` uses above.
    `scope_note` defaults to `"single"` (the only value the wrapper itself
    ever writes); tests exercising ADR-7's `batch`/absent cases override it
    explicitly, including passing `None` to omit the key entirely (a real
    pre-T3.5 or corrupted record would simply lack it).
    """
    record = {
        "ts": ts,
        "kind": "hook",
        "session": session,
        "repo": "the-custom-startup",
        "hook_event": hook_event,
        "matcher": matcher,
    }
    if ms is not None:
        record["ms"] = ms
    if exit_value is not None:
        record["exit"] = exit_value
    if scope_note is not None:
        record["scope_note"] = scope_note
    return record


# --- per-file load counts and reasons observed -----------------------------


def test_per_file_load_counts_and_reasons(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("docs/ai/memory/active.md", "session_start"),
            _instruction("docs/ai/memory/active.md", "session_start"),
            _instruction("docs/ai/memory/general.md", "path_glob_match"),
        ],
    )

    records, unparseable = report.read_events(events)
    assert unparseable == 0

    stats = report.instruction_stats(records)
    assert stats["docs/ai/memory/active.md"].load_count == 2
    assert stats["docs/ai/memory/active.md"].reason_counts == {"session_start": 2}
    assert stats["docs/ai/memory/general.md"].load_count == 1
    assert stats["docs/ai/memory/general.md"].reason_counts == {"path_glob_match": 1}


def test_non_instruction_kinds_are_ignored_not_fatal(tmp_path):
    events = tmp_path / "events.jsonl"
    lines = [
        {"ts": "2026-09-06T16:43:28Z", "kind": "hook", "session": "x", "repo": "notarepo"},
        _instruction("a.md", "session_start"),
        {"ts": "2026-09-06T16:43:29Z", "kind": "skill", "session": "x", "repo": "notarepo", "skill": "foo"},
        {"ts": "2026-09-06T16:43:30Z", "kind": "agent", "session": "x", "repo": "notarepo",
         "agent_type": "general-purpose", "agent_id": "1"},
        {"ts": "2026-09-06T16:43:31Z", "kind": "state", "session": "x", "repo": "notarepo",
         "enabled": True, "detail": False, "note": "check"},
    ]
    events.write_text("\n".join(json.dumps(r) for r in lines) + "\n", encoding="utf-8")

    records, unparseable = report.read_events(events)
    assert unparseable == 0
    stats = report.instruction_stats(records)
    assert set(stats.keys()) == {"a.md"}


# --- always-loaded vs conditionally loaded, including a file showing both --


def test_always_vs_conditional_classification(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("docs/ai/memory/active.md", "session_start"),
            _instruction("docs/ai/memory/general.md", "path_glob_match"),
            _instruction("docs/ai/memory/mixed.md", "session_start"),
            _instruction("docs/ai/memory/mixed.md", "path_glob_match"),
        ],
    )
    records, _ = report.read_events(events)
    stats = report.instruction_stats(records)

    assert stats["docs/ai/memory/active.md"].always_loaded is True
    assert stats["docs/ai/memory/active.md"].conditionally_loaded is False

    assert stats["docs/ai/memory/general.md"].always_loaded is False
    assert stats["docs/ai/memory/general.md"].conditionally_loaded is True

    # A file loaded both ways shows both -- neither flag suppresses the other.
    assert stats["docs/ai/memory/mixed.md"].always_loaded is True
    assert stats["docs/ai/memory/mixed.md"].conditionally_loaded is True


def test_compact_reason_also_counts_as_always_loaded(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(events, [_instruction("docs/ai/memory/active.md", "compact")])
    records, _ = report.read_events(events)
    stats = report.instruction_stats(records)
    assert stats["docs/ai/memory/active.md"].always_loaded is True


# --- an empty reason is unknown, never folded into a named reason's count --


def test_empty_reason_counted_as_unknown_never_folded(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("docs/ai/memory/active.md", "session_start"),
            _instruction("docs/ai/memory/active.md", ""),
            _instruction("docs/ai/memory/active.md", ""),
        ],
    )
    records, _ = report.read_events(events)
    stats = report.instruction_stats(records)
    entry = stats["docs/ai/memory/active.md"]

    assert entry.load_count == 3
    assert entry.reason_counts == {"session_start": 1}
    assert entry.unknown_count == 2
    assert "" not in entry.reason_counts
    # An unknown-only file is neither always-loaded nor conditionally loaded.
    only_unknown = report.instruction_stats(
        [_instruction("docs/ai/memory/only-unknown.md", "")]
    )["docs/ai/memory/only-unknown.md"]
    assert only_unknown.always_loaded is False
    assert only_unknown.conditionally_loaded is False


def test_missing_reason_key_also_counted_as_unknown(tmp_path):
    """A record missing `reason` entirely (not just empty) must not crash or fold in."""
    events = tmp_path / "events.jsonl"
    rec = _instruction("docs/ai/memory/active.md", "session_start")
    del rec["reason"]
    _write_jsonl(events, [rec])
    records, _ = report.read_events(events)
    stats = report.instruction_stats(records)
    entry = stats["docs/ai/memory/active.md"]
    assert entry.load_count == 1
    assert entry.unknown_count == 1
    assert entry.reason_counts == {}


def test_non_string_reason_is_counted_as_unknown_not_folded(tmp_path):
    """A malformed record (producer bug) with a non-string truthy `reason` must not
    become a non-string key in `reason_counts` -- it must fall through to unknown,
    the same as an empty or missing reason (module's stated defensive posture)."""
    entry = report.InstructionFileStats(path="a.md")
    entry.record(7)  # a truthy non-string, e.g. from a malformed producer
    assert entry.load_count == 1
    assert entry.unknown_count == 1
    assert entry.reason_counts == {}


# --- repo as a first-class dimension (spec-019 T3.1) ------------------------
#
# `instruction_stats` itself is NOT changed (see report.py's docstring on
# `instruction_stats_by_repo` for why: ~20 pre-existing tests above index its
# result by bare path string, and both `never_loaded()` and
# `build_load_report()` consume that exact shape). This baseline test pins
# down -- and documents -- the merge defect `instruction_stats` still has by
# design: a file of the same name in two repositories collapses into one
# entry. `instruction_stats_by_repo` below is the parallel function that
# fixes this without disturbing `instruction_stats`.


def test_instruction_stats_still_collapses_same_filename_across_repos(tmp_path):
    """Baseline/regression pin, not a bug to fix here: `instruction_stats`
    keys on bare path only, so two repos' records for the same filename
    still merge into one entry (SDD-AC-19's defect). `instruction_stats_by_repo`
    is the fix; this function is deliberately left alone (spec-019 T3.1 R1)."""
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("CLAUDE.md", "session_start", repo="repo-alpha"),
            _instruction("CLAUDE.md", "session_start", repo="repo-beta"),
        ],
    )
    records, _ = report.read_events(events)
    assert {r["repo"] for r in records} == {"repo-alpha", "repo-beta"}  # guard: fixture repos differ

    stats = report.instruction_stats(records)
    assert set(stats.keys()) == {"CLAUDE.md"}  # the two repos' records collapsed into one entry
    assert stats["CLAUDE.md"].load_count == 2  # ...and their loads were merged, not kept separate


def test_instruction_stats_by_repo_counts_same_filename_separately_per_repo(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("CLAUDE.md", "session_start", repo="repo-alpha"),
            _instruction("CLAUDE.md", "session_start", repo="repo-beta"),
            _instruction("CLAUDE.md", "session_start", repo="repo-beta"),
        ],
    )
    records, _ = report.read_events(events)
    assert {r["repo"] for r in records} == {"repo-alpha", "repo-beta"}  # guard: fixture repos differ

    by_repo = report.instruction_stats_by_repo(records)

    assert set(by_repo.keys()) == {"repo-alpha", "repo-beta"}
    assert by_repo["repo-alpha"]["CLAUDE.md"].load_count == 1
    assert by_repo["repo-beta"]["CLAUDE.md"].load_count == 2
    # each inner dict is exactly instruction_stats's own per-file shape
    assert isinstance(by_repo["repo-alpha"]["CLAUDE.md"], report.InstructionFileStats)


def test_instruction_stats_by_repo_per_repo_counts_sum_to_per_file_totals(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("CLAUDE.md", "session_start", repo="repo-alpha"),
            _instruction("CLAUDE.md", "session_start", repo="repo-alpha"),
            _instruction("CLAUDE.md", "path_glob_match", repo="repo-beta"),
            _instruction("other.md", "session_start", repo="repo-beta"),
        ],
    )
    records, _ = report.read_events(events)

    by_repo = report.instruction_stats_by_repo(records)
    merged = report.instruction_stats(records)  # the pre-existing, repo-blind totals

    for path, file_stats in merged.items():
        summed = sum(
            per_repo[path].load_count for per_repo in by_repo.values() if path in per_repo
        )
        assert summed == file_stats.load_count


def test_instruction_stats_by_repo_empty_repo_lands_in_unknown_bucket(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("CLAUDE.md", "session_start", repo=""),
            _instruction("CLAUDE.md", "session_start", repo="repo-alpha"),
        ],
    )
    records, _ = report.read_events(events)

    by_repo = report.instruction_stats_by_repo(records)

    assert None in by_repo  # keyed on Python None, never the string "unknown" (spec-019 T3.1 R2)
    assert by_repo[None]["CLAUDE.md"].load_count == 1
    assert by_repo["repo-alpha"]["CLAUDE.md"].load_count == 1  # did not join the empty-repo bucket


def test_instruction_stats_by_repo_missing_repo_key_also_lands_in_unknown_bucket(tmp_path):
    events = tmp_path / "events.jsonl"
    rec = _instruction("CLAUDE.md", "session_start", repo=None)
    assert "repo" not in rec  # guard: the key is genuinely absent, not merely falsy
    other = _instruction("CLAUDE.md", "session_start", repo="repo-alpha")
    _write_jsonl(events, [rec, other])
    records, _ = report.read_events(events)

    by_repo = report.instruction_stats_by_repo(records)

    assert None in by_repo
    assert by_repo[None]["CLAUDE.md"].load_count == 1
    assert by_repo["repo-alpha"]["CLAUDE.md"].load_count == 1  # did not join the absent-key bucket
    assert "unknown" not in by_repo  # never a string key (spec-019 T3.1 R2)


def test_instruction_stats_by_repo_missing_and_empty_repo_share_one_unknown_bucket(tmp_path):
    """A missing `repo` key and an empty-string `repo` are the same unification
    `InstructionFileStats.record()` already applies to `reason` (report.py:79-84)
    -- both land in the SAME unknown bucket, not two separate ones."""
    events = tmp_path / "events.jsonl"
    missing = _instruction("a.md", "session_start", repo=None)
    empty = _instruction("a.md", "session_start", repo="")
    _write_jsonl(events, [missing, empty])
    records, _ = report.read_events(events)

    by_repo = report.instruction_stats_by_repo(records)

    assert set(by_repo.keys()) == {None}
    assert by_repo[None]["a.md"].load_count == 2


# --- the rotated chain is one logical record, read once --------------------


def test_rotated_chain_read_as_one_logical_record_without_double_counting(tmp_path):
    base = tmp_path / "events.jsonl"
    _write_jsonl(tmp_path / "events.jsonl.3", [_instruction("a.md", "session_start")])
    _write_jsonl(tmp_path / "events.jsonl.2", [_instruction("b.md", "session_start")])
    _write_jsonl(tmp_path / "events.jsonl.1", [_instruction("c.md", "session_start")])
    _write_jsonl(base, [_instruction("d.md", "session_start")])

    records, unparseable = report.read_events(base)
    assert unparseable == 0

    stats = report.instruction_stats(records)
    assert set(stats.keys()) == {"a.md", "b.md", "c.md", "d.md"}
    for entry in stats.values():
        assert entry.load_count == 1  # no generation counted twice


def test_rotated_chain_skips_missing_generations(tmp_path):
    base = tmp_path / "events.jsonl"
    # Only .2 and the base exist -- .3 and .1 were never created (or already
    # aged out). A missing generation is skipped, not an error.
    _write_jsonl(tmp_path / "events.jsonl.2", [_instruction("only-two.md", "session_start")])
    _write_jsonl(base, [_instruction("only-base.md", "session_start")])

    records, unparseable = report.read_events(base)
    assert unparseable == 0
    stats = report.instruction_stats(records)
    assert set(stats.keys()) == {"only-two.md", "only-base.md"}


def test_rotation_chain_order_is_oldest_first(tmp_path):
    base = tmp_path / "events.jsonl"
    for suffix in (".3", ".2", ".1", ""):
        (tmp_path / f"events.jsonl{suffix}").write_text("{}\n", encoding="utf-8")

    chain = report.rotation_chain(base)
    assert [p.name for p in chain] == [
        "events.jsonl.3",
        "events.jsonl.2",
        "events.jsonl.1",
        "events.jsonl",
    ]


def test_rotation_chain_on_nonexistent_log_is_empty(tmp_path):
    assert report.rotation_chain(tmp_path / "events.jsonl") == []


# --- unparseable lines are counted, never fatal (CON-10) --------------------


def test_unparseable_line_is_counted_and_skipped_not_fatal(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(_instruction("a.md", "session_start")) + "\n"
        "{this is not json\n"
        + json.dumps(_instruction("b.md", "session_start")) + "\n",
        encoding="utf-8",
    )

    records, unparseable = report.read_events(events)
    assert unparseable == 1
    stats = report.instruction_stats(records)
    assert set(stats.keys()) == {"a.md", "b.md"}


def test_blank_lines_are_not_counted_as_unparseable(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(_instruction("a.md", "session_start")) + "\n\n\n",
        encoding="utf-8",
    )
    records, unparseable = report.read_events(events)
    assert unparseable == 0
    assert len(records) == 1


# --- never-loaded, named from the instruction inventory --------------------


def test_never_loaded_named_from_inventory(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(events, [_instruction("docs/ai/memory/active.md", "session_start")])
    records, _ = report.read_events(events)
    stats = report.instruction_stats(records)

    inventory = [
        "docs/ai/memory/active.md",
        "docs/ai/memory/general.md",
        "docs/ai/memory/context.md",
    ]
    assert report.never_loaded(inventory, stats) == [
        "docs/ai/memory/context.md",
        "docs/ai/memory/general.md",
    ]


def test_never_loaded_is_empty_when_everything_configured_loaded(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(events, [_instruction("a.md", "session_start")])
    records, _ = report.read_events(events)
    stats = report.instruction_stats(records)
    assert report.never_loaded(["a.md"], stats) == []


def test_walk_instruction_inventory_finds_configured_sources(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    (repo_root / "docs" / "ai" / "memory").mkdir(parents=True)
    (repo_root / ".claude" / "rules").mkdir(parents=True)
    (home_dir / ".claude" / "rules").mkdir(parents=True)
    (home_dir / "Kouzou" / "standards").mkdir(parents=True)

    (repo_root / "CLAUDE.md").write_text(
        "# root\n@docs/ai/memory/active.md\n@~/Kouzou/standards/general.md\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "ai" / "memory" / "active.md").write_text("active\n", encoding="utf-8")
    (repo_root / "docs" / "ai" / "memory" / "general.md").write_text("general\n", encoding="utf-8")
    (repo_root / ".claude" / "rules" / "local.md").write_text("local rule\n", encoding="utf-8")
    (home_dir / ".claude" / "rules" / "global.md").write_text("global rule\n", encoding="utf-8")
    (home_dir / ".claude" / "CLAUDE.md").write_text("home claude\n", encoding="utf-8")
    (home_dir / "Kouzou" / "standards" / "general.md").write_text("standards\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert "CLAUDE.md" in inventory  # the root file itself
    assert "docs/ai/memory/active.md" in inventory  # reached via the @-import
    assert "docs/ai/memory/general.md" in inventory  # reached via the memory-dir glob
    assert ".claude/rules/local.md" in inventory
    assert "global.md" in inventory  # outside repo_root -> basename only (R-3)
    assert "general.md" in inventory  # the transitively-imported standards file, basename only


def test_walk_instruction_inventory_transitive_import_is_reached(tmp_path):
    """@-imports resolve transitively, not just one hop deep."""
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    repo_root.mkdir(parents=True)
    (repo_root / "docs").mkdir()

    # @-imports resolve relative to the importing file's own directory,
    # matching Claude Code's own import semantics -- so level1.md (itself
    # under docs/) reaches its sibling with a bare "level2.md", not a
    # repo-root-relative path.
    (repo_root / "CLAUDE.md").write_text("@docs/level1.md\n", encoding="utf-8")
    (repo_root / "docs" / "level1.md").write_text("@level2.md\n", encoding="utf-8")
    (repo_root / "docs" / "level2.md").write_text("leaf\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries
    assert "docs/level1.md" in inventory
    assert "docs/level2.md" in inventory


def test_walk_instruction_inventory_missing_sources_do_not_crash(tmp_path):
    """A repo with none of the four sources present must still return an empty list."""
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    repo_root.mkdir()
    home_dir.mkdir()
    assert report.walk_instruction_inventory(repo_root, home_dir).entries == []


def test_walk_instruction_inventory_deduplicates_redacted_paths(tmp_path):
    """Paths redacting to the same string must appear only once in entries.

    _redact_path is many-to-one by design: paths outside the repo collapse to
    their basename (R-3), so ~/path/CLAUDE.md and repo_root/CLAUDE.md both
    redact to "CLAUDE.md". De-duplicating Path objects before redaction is
    insufficient -- the redaction itself must produce a set to remove duplicates.
    """
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    repo_root.mkdir(parents=True)
    (home_dir / ".claude" / "rules").mkdir(parents=True)

    # Create repo-root CLAUDE.md
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")

    # Create home-dir CLAUDE.md -- will redact to the same string
    (home_dir / ".claude" / "CLAUDE.md").write_text("# home\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir)

    # Both files exist but redact to "CLAUDE.md"
    assert "CLAUDE.md" in inventory.entries
    # The critical assertion: no duplicates in the entries list
    assert len(inventory.entries) == len(set(inventory.entries))
    # And "CLAUDE.md" should appear exactly once
    assert inventory.entries.count("CLAUDE.md") == 1


# --- nested CLAUDE.md files (SDD amendment, 2026-09-07, T3.1 review) --------
#
# A nested CLAUDE.md is one of the five verified `load_reason` values
# (`nested_traversal`). Before the amendment, a nested file could appear in
# the numerator (a real load record) but never in the denominator, so a
# nested file that never loaded was invisible to "configured but never
# loaded". The exclusion keeps a `tests/fixtures/` CLAUDE.md -- test data,
# not configuration -- from inflating the count.


def test_walk_instruction_inventory_finds_nested_claude_md(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    (repo_root / "docs").mkdir(parents=True)
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    (repo_root / "docs" / "CLAUDE.md").write_text("# docs\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert "docs/CLAUDE.md" in inventory


def test_walk_instruction_inventory_excludes_tests_fixtures_claude_md(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    fixtures_dir = repo_root / "plugins" / "example" / "tests" / "fixtures" / "sample-docs"
    fixtures_dir.mkdir(parents=True)
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    (fixtures_dir / "CLAUDE.md").write_text("# fixture\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert "plugins/example/tests/fixtures/sample-docs/CLAUDE.md" not in inventory


def test_walk_instruction_inventory_similarly_named_dir_is_not_wrongly_excluded(tmp_path):
    """`tests/fixtures` must be matched as path segments, not a substring.

    A directory legitimately named `tests-fixtures` (one segment, hyphenated)
    or `my-tests/fixtures-sample` (segments that merely contain the words)
    must not trip the exclusion -- only an exact `tests` segment immediately
    followed by an exact `fixtures` segment does.
    """
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").parent.mkdir(parents=True, exist_ok=True)
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")

    one_segment = repo_root / "tests-fixtures"
    one_segment.mkdir(parents=True)
    (one_segment / "CLAUDE.md").write_text("# one-segment\n", encoding="utf-8")

    two_segments = repo_root / "my-tests" / "fixtures-sample"
    two_segments.mkdir(parents=True)
    (two_segments / "CLAUDE.md").write_text("# two-segments\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert "tests-fixtures/CLAUDE.md" in inventory
    assert "my-tests/fixtures-sample/CLAUDE.md" in inventory


def test_walk_instruction_inventory_reaches_deeply_nested_claude_md(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    deep = repo_root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    (deep / "CLAUDE.md").write_text("# deep\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert "a/b/c/CLAUDE.md" in inventory


def test_walk_instruction_inventory_root_claude_md_not_double_counted(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    repo_root.mkdir()
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert inventory.count("CLAUDE.md") == 1


def test_walk_instruction_inventory_nested_entries_are_redacted(tmp_path):
    """Nested CLAUDE.md entries go through the same `_redact_path` as everything
    else, so they compare equal to what the bash writer puts in a record's
    `path` field -- a repo-relative posix path, not an absolute one."""
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    nested = repo_root / "docs" / "ai" / "CLAUDE.md"
    nested.parent.mkdir(parents=True)
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    nested.write_text("# nested\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir).entries

    assert "docs/ai/CLAUDE.md" in inventory
    assert not any(str(repo_root) in entry for entry in inventory)


# --- gitignore-aware filtering (SDD second amendment, 2026-09-07) ----------
#
# The walk had no `.gitignore` awareness, and widening it to nested files
# (above) made that visible: a gitignored local mount inside a real repo
# root can contain a full second checkout of the same repo, so the walk
# counted several real CLAUDE.md files a second time each -- duplicates of
# the very files the report is trying to reason about, corrupting the
# specific answer rather than merely padding a total. `walk_instruction_
# inventory` now asks `git check-ignore` at walk time and reports, via
# `InstructionInventory.git_filtered`, whether it could.


def test_walk_instruction_inventory_gitignored_nested_claude_md_is_excluded(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    _init_git_repo(repo_root)
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    mounted = repo_root / "mount" / "docs"
    mounted.mkdir(parents=True)
    (mounted / "CLAUDE.md").write_text("# second copy from a local mount\n", encoding="utf-8")
    (repo_root / ".gitignore").write_text("mount/\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir)

    assert "mount/docs/CLAUDE.md" not in inventory.entries
    assert inventory.git_filtered is True


def test_walk_instruction_inventory_tracked_nested_claude_md_is_included(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    _init_git_repo(repo_root)
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    (repo_root / "docs").mkdir()
    (repo_root / "docs" / "CLAUDE.md").write_text("# docs\n", encoding="utf-8")
    _git_add(repo_root, "CLAUDE.md", "docs/CLAUDE.md")

    inventory = report.walk_instruction_inventory(repo_root, home_dir)

    assert "docs/CLAUDE.md" in inventory.entries
    assert inventory.git_filtered is True


def test_walk_instruction_inventory_outside_repo_path_not_dropped_by_filter(tmp_path):
    """When partitioning candidates into inside-repo and outside-repo before
    calling git, the filter must never drop the outside-repo partition.

    Outside-repo paths (e.g., home_dir entries) sit outside the repository's
    working tree entirely -- they are out of scope for `git check-ignore`, not
    ignored by it. Asking git about an out-of-repo path can itself fail with
    a fatal "outside repository" error rather than a clean answer. The
    implementation must partition inside/outside BEFORE calling git to avoid
    that error entirely, and this test pins that the outside-repo partition
    is retained in the result.

    This test distinguishes the outside-repo file with a unique basename
    (`only-outside.md` vs `CLAUDE.md`) so its presence is directly observable,
    unlike a name collision where both redact to the same string.
    (SDD amendment: 'this is the subtlest part')
    """
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    _init_git_repo(repo_root)
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")

    # Outside-repo file with a unique basename
    (home_dir / ".claude" / "rules").mkdir(parents=True)
    (home_dir / ".claude" / "rules" / "only-outside.md").write_text("# home\n", encoding="utf-8")

    inventory = report.walk_instruction_inventory(repo_root, home_dir)

    # The outside-repo entry must be present with its distinct name
    assert "only-outside.md" in inventory.entries
    # Confirms the filter genuinely ran (otherwise fail-open would trivially pass)
    assert inventory.git_filtered is True
    # Confirm the inside-repo file is also found (exercises the partition)
    assert "CLAUDE.md" in inventory.entries


def test_walk_instruction_inventory_not_a_git_repo_is_unfiltered(tmp_path):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    repo_root.mkdir()
    home_dir.mkdir()
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    # Deliberately no `git init` -- repo_root is a plain directory.

    inventory = report.walk_instruction_inventory(repo_root, home_dir)

    assert "CLAUDE.md" in inventory.entries
    assert inventory.git_filtered is False


def test_walk_instruction_inventory_git_unavailable_fails_open(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    _init_git_repo(repo_root)
    (repo_root / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    ignored = repo_root / "mount"
    ignored.mkdir()
    (ignored / "CLAUDE.md").write_text("# would be ignored, if git ran\n", encoding="utf-8")
    (repo_root / ".gitignore").write_text("mount/\n", encoding="utf-8")

    def _raise_missing_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(report.subprocess, "run", _raise_missing_git)

    inventory = report.walk_instruction_inventory(repo_root, home_dir)

    # Fails open: everything is kept, including what a working filter would
    # have dropped -- an empty or partial inventory would be worse.
    assert "CLAUDE.md" in inventory.entries
    assert "mount/CLAUDE.md" in inventory.entries
    assert inventory.git_filtered is False


# --- byte accounting: always-loaded vs conditional, honestly (T3.2) -------
#
# SDD-AC-14, and the three typing traps in the T3.2 task text: `bytes` is a
# quoted string ("2048", never a bare 2048), it is ABSENT (never "0") when
# `logwrite.sh` could not stat the file, and it must never be silently
# folded into a total as if it were free.


def test_byte_accounting_separates_always_loaded_from_conditional():
    records = [
        _instruction("a.md", "session_start", bytes_value="1000"),
        _instruction("a.md", "compact", bytes_value="500"),
        _instruction("b.md", "path_glob_match", bytes_value="300"),
        _instruction("c.md", "include", bytes_value="200"),
    ]

    totals = report.byte_accounting(records)

    assert totals.always_loaded_bytes == 1500
    assert totals.conditional_bytes == 500
    assert totals.unmeasurable_count == 0


def test_byte_accounting_casts_quoted_string_bytes_to_int():
    # A naive `+=` over the raw string would concatenate ("2048" + "2048"),
    # not add -- this pins the cast, not just the total.
    records = [
        _instruction("a.md", "session_start", bytes_value="2048"),
        _instruction("a.md", "session_start", bytes_value="2048"),
    ]

    totals = report.byte_accounting(records)

    assert totals.always_loaded_bytes == 4096


def test_byte_accounting_excludes_unstatable_file_never_counts_as_zero():
    records = [
        _instruction("a.md", "session_start", bytes_value="1000"),
        _instruction("b.md", "session_start"),  # no `bytes` key: could not be stat'ed
    ]

    totals = report.byte_accounting(records)

    # b.md contributes nothing -- not a real zero, an absence -- so the
    # total must equal exactly a.md's measured cost, and the absence must
    # be surfaced, not dropped.
    assert totals.always_loaded_bytes == 1000
    assert totals.unmeasurable_count == 1


def test_byte_accounting_non_numeric_bytes_is_unmeasurable_not_zero_not_fatal():
    records = [_instruction("a.md", "session_start", bytes_value="not-a-number")]

    totals = report.byte_accounting(records)  # must not raise

    assert totals.always_loaded_bytes == 0
    assert totals.unmeasurable_count == 1


def test_byte_accounting_boolean_bytes_is_unmeasurable_not_a_measurement():
    # `int(True) == 1` and `int(False) == 0` both succeed in plain Python --
    # so a mis-serialized `"bytes": false` must not be recorded as a
    # measured zero (or a measured one). `bool` is a subtype of `int`, so
    # this only holds if the bool check runs before the `int()` cast.
    records = [_instruction("a.md", "session_start", bytes_value=False)]

    totals = report.byte_accounting(records)  # must not raise

    assert totals.always_loaded_bytes == 0
    assert totals.conditional_bytes == 0
    assert totals.unmeasurable_count == 1


def test_byte_accounting_unknown_reason_bytes_not_silently_dropped():
    records = [_instruction("a.md", "", bytes_value="42")]

    totals = report.byte_accounting(records)

    assert totals.always_loaded_bytes == 0
    assert totals.conditional_bytes == 0
    assert totals.unknown_reason_bytes == 42


def test_byte_accounting_ignores_non_instruction_kinds():
    records = [_state("1"), {"kind": "skill", "bytes": "999"}]

    totals = report.byte_accounting(records)

    assert totals.always_loaded_bytes == 0
    assert totals.conditional_bytes == 0
    assert totals.unmeasurable_count == 0


def test_byte_accounting_file_loaded_both_ways_attributes_each_event_by_its_own_reason():
    # A file can show up as BOTH always-loaded and conditional (loaded
    # eagerly, then re-triggered later by a glob match). Attribution is per
    # LOAD EVENT, not per file: each record's own reason decides its
    # bucket, so this is never a double-count, and never a dropped read.
    records = [
        _instruction("a.md", "session_start", bytes_value="100"),
        _instruction("a.md", "path_glob_match", bytes_value="100"),
    ]

    totals = report.byte_accounting(records)

    assert totals.always_loaded_bytes == 100
    assert totals.conditional_bytes == 100


# --- recording state honesty (SDD-AC-15) ------------------------------------
#
# `recording_status` takes an injected `now` rather than reading the wall
# clock, so every case here is deterministic (module docstring / T3.2 task
# text: "inject the clock").

_NOW = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)


def test_recording_status_no_records_at_all_is_unknown_not_off():
    status = report.recording_status([], _NOW)

    assert status.state_known is False
    assert status.enabled is None
    assert status.stale is False
    assert status.newest_ts is None


def test_recording_status_no_state_record_present_is_unknown():
    records = [_instruction("a.md", "session_start", ts="2026-09-07T11:00:00Z")]

    status = report.recording_status(records, _NOW)

    assert status.state_known is False
    assert status.enabled is None


def test_recording_status_enabled_string_zero_is_not_recording():
    # The truthiness trap: a Python `if "0":` is True. This must compare
    # against "1" explicitly, never rely on str truthiness.
    records = [_state("0", ts="2026-09-07T11:00:00Z")]

    status = report.recording_status(records, _NOW)

    assert status.state_known is True
    assert status.enabled is False


def test_recording_status_enabled_string_one_is_recording():
    records = [_state("1", ts="2026-09-07T11:00:00Z")]

    status = report.recording_status(records, _NOW)

    assert status.enabled is True


def test_recording_status_stale_when_newest_entry_predates_threshold():
    old_ts = "2026-09-06T00:00:00Z"  # 36h before _NOW
    records = [_state("1", ts=old_ts)]

    status = report.recording_status(records, _NOW)

    assert status.stale is True
    assert status.newest_ts == old_ts


def test_recording_status_not_stale_when_newest_entry_recent():
    recent_ts = "2026-09-07T11:55:00Z"  # 5 minutes before _NOW
    records = [_state("1", ts=recent_ts)]

    status = report.recording_status(records, _NOW)

    assert status.stale is False


def test_recording_status_not_stale_at_exactly_the_threshold():
    # Finding 4 (T3.2 code review): pin the `>` (not `>=`) semantics at
    # STALE_THRESHOLD_SECONDS exactly -- the pre-existing tests (36h and 5m)
    # are both far from the 6h line, so `>` and `>=` pass either one
    # equally. Exactly at the threshold must NOT be stale.
    assert report.STALE_THRESHOLD_SECONDS == 6 * 60 * 60
    boundary_ts = "2026-09-07T06:00:00Z"  # exactly 6h before _NOW
    records = [_state("1", ts=boundary_ts)]

    status = report.recording_status(records, _NOW)

    assert status.stale is False


def test_recording_status_stale_one_second_past_the_threshold():
    assert report.STALE_THRESHOLD_SECONDS == 6 * 60 * 60
    just_past_ts = "2026-09-07T05:59:59Z"  # 6h and 1s before _NOW
    records = [_state("1", ts=just_past_ts)]

    status = report.recording_status(records, _NOW)

    assert status.stale is True


def test_recording_status_newest_ts_is_max_across_all_records_not_last_in_list():
    records = [
        _instruction("a.md", "session_start", ts="2026-09-07T11:59:00Z"),
        _state("1", ts="2026-09-06T00:00:00Z"),  # written earlier, listed later
    ]

    status = report.recording_status(records, _NOW)

    assert status.newest_ts == "2026-09-07T11:59:00Z"
    assert status.stale is False


def test_recording_status_enabled_reflects_newest_state_record_by_ts_not_position():
    # Two `state` records, interleaved the way the SDD says concurrent
    # sessions' append-only writes can be: the list-LAST record carries the
    # EARLIER `ts`. The chronologically newer record (`enabled="1"`, listed
    # first) must win, not the positionally-last one (`enabled="0"`).
    records = [
        _state("1", ts="2026-09-07T11:00:00Z"),  # chronologically newer, listed first
        _state("0", ts="2026-09-06T00:00:00Z"),  # chronologically older, listed last
    ]

    status = report.recording_status(records, _NOW)

    assert status.enabled is True


def test_recording_status_enabled_ignores_state_record_with_unusable_ts():
    # A `state` record with a missing/malformed `ts` must not crash the
    # selection and must not win over a record with a valid, newer `ts`,
    # regardless of list position.
    records = [
        _state("0", ts="not-a-timestamp"),  # unusable ts, listed first
        _state("1", ts="2026-09-07T11:00:00Z"),  # usable, actually newest
    ]

    status = report.recording_status(records, _NOW)  # must not raise

    assert status.enabled is True


def test_recording_status_unparseable_ts_is_ignored_not_fatal():
    records = [_state("1", ts="not-a-timestamp")]

    status = report.recording_status(records, _NOW)  # must not raise

    assert status.newest_ts is None
    assert status.stale is False


def test_recording_status_fallback_to_last_on_all_unparseable_ts():
    # The fallback path (when NO state record has a usable ts) should select
    # the LAST state record encountered, not the first or a fixed one.
    # With multiple records all bearing unparseable ts, the fallback must
    # pick the last-listed one to correctly report the newest observable state.
    records = [
        _state("0", ts="not-a-date"),  # unparseable, listed first
        _state("0", ts=""),            # unparseable (empty), listed second
        _state("1", ts="invalid"),     # unparseable, listed last -- should win
    ]

    status = report.recording_status(records, _NOW)

    # The result must not crash and must select the last record (enabled="1")
    assert status.enabled is True
    assert status.newest_ts is None


# --- the report leads with recording state, never with a load figure ------
# (SDD-AC-15, Quality Requirements' Honesty row): an empty or stale record
# must report the recording state as the headline, not present emptiness or
# a stale figure as if it were a finding.


def test_build_load_report_states_byte_cost_always_vs_conditional():
    byte_stats = report.byte_accounting([
        _instruction("a.md", "session_start", bytes_value="1000"),
        _instruction("b.md", "path_glob_match", bytes_value="300"),
    ])

    text = report.build_load_report({}, [], byte_stats=byte_stats)

    # Finding 5 (T3.2 code review): assert the number is attached to its
    # own label, not merely present anywhere in the text -- a bare "1000"
    # / "300" check would still pass if `_render_byte_accounting` swapped
    # which figure it calls always-loaded vs. conditional.
    assert "always-loaded layer: 1000" in text
    assert "conditional loads: 300" in text


def test_build_load_report_states_unmeasurable_count():
    byte_stats = report.byte_accounting([_instruction("a.md", "session_start")])

    text = report.build_load_report({}, [], byte_stats=byte_stats)

    assert "1" in text
    assert "unmeasurable" in text.lower()


def test_build_load_report_empty_record_leads_with_recording_state_unknown():
    status = report.recording_status([], _NOW)

    text = report.build_load_report({}, [], recording=status)

    lines = [line for line in text.splitlines() if line.strip()]
    assert "recording" in lines[0].lower()
    assert "unknown" in lines[0].lower()


def test_build_load_report_states_not_recording_for_enabled_zero():
    status = report.recording_status([_state("0", ts="2026-09-07T11:00:00Z")], _NOW)

    text = report.build_load_report({}, [], recording=status)

    assert "not recording" in text.lower()


def test_build_load_report_states_recording_for_enabled_one():
    status = report.recording_status([_state("1", ts="2026-09-07T11:55:00Z")], _NOW)

    text = report.build_load_report({}, [], recording=status)

    lines = [line for line in text.splitlines() if line.strip()]
    assert "recording" in lines[0].lower()
    assert "not recording" not in lines[0].lower()


def test_build_load_report_states_stale():
    status = report.recording_status([_state("1", ts="2026-09-06T00:00:00Z")], _NOW)

    text = report.build_load_report({}, [], recording=status)

    assert "stale" in text.lower()


def test_build_load_report_unknown_state_when_no_state_record_present():
    records = [_instruction("a.md", "session_start")]
    status = report.recording_status(records, _NOW)

    text = report.build_load_report(
        report.instruction_stats(records), ["a.md"], recording=status
    )

    lines = [line for line in text.splitlines() if line.strip()]
    assert "unknown" in lines[0].lower()


def test_build_load_report_recording_state_line_precedes_loaded_files_line():
    status = report.recording_status([], _NOW)

    text = report.build_load_report({}, [], recording=status)
    lines = text.splitlines()

    recording_idx = next(i for i, line in enumerate(lines) if "recording" in line.lower())
    loaded_idx = next(
        i for i, line in enumerate(lines) if line.lower().startswith("loaded instruction files")
    )
    assert recording_idx < loaded_idx


# --- the assembled text report ---------------------------------------------


def test_build_load_report_mentions_counts_reasons_and_never_loaded(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [_instruction("a.md", "session_start"), _instruction("a.md", "")],
    )
    records, unparseable = report.read_events(events)
    stats = report.instruction_stats(records)

    text = report.build_load_report(stats, ["a.md", "b.md"], unparseable)

    assert "a.md" in text
    assert "session_start=1" in text
    assert "unknown=1" in text
    assert "b.md" in text  # named as configured-but-never-loaded
    assert "2" in text  # the inventory count is stated (SDD/The two inventories)


def test_build_load_report_states_unparseable_count():
    text = report.build_load_report({}, [], unparseable=3)
    assert "3" in text


# --- the report states which walk mode produced its denominator ------------
# (SDD/The two inventories, second amendment, 2026-09-07): a reader must be
# able to tell whether the count came from a gitignore-filtered walk or an
# unfiltered fallback, in both directions.


def test_build_load_report_states_gitignore_filtered_mode():
    text = report.build_load_report({}, ["a.md"], git_filtered=True)
    assert "gitignore" in text.lower()


def test_build_load_report_states_unfiltered_mode():
    text = report.build_load_report({}, ["a.md"], git_filtered=False)
    assert "unfiltered" in text.lower()


# --- CLI wiring (main / _resolve_events_path) -------------------------------
#
# Everything above drives the pure functions directly. Nothing calls
# report.main(...), so a wiring bug -- a wrong argument order into
# build_load_report, or a --data-dir override that resolves to a different
# shape than the writer's -- would ship undetected. This follows the
# subprocess-against-the-real-script pattern of tests/test_spec_tier.py
# (another stdlib-only Python CLI script in this repo) rather than
# tests/test_check_docs_sync.py's bash-script variant of the same idea: it
# exercises the actual `__main__` / argparse / sys.exit path a user hits from
# the command line, not just an imported function call.


def _run_report_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPORT_PY), *args],
        capture_output=True,
        text=True,
    )


def test_cli_end_to_end_prints_report_for_fixture_events(tmp_path):
    events = tmp_path / "events.jsonl"
    _write_jsonl(
        events,
        [
            _instruction("docs/ai/memory/active.md", "session_start", bytes_value="123"),
            _instruction("docs/ai/memory/active.md", "session_start", bytes_value="123"),
            _hook("PreToolUse", "Skill", ms="0.001", exit_value="0", scope_note="single"),
            _hook("PreToolUse", "Skill", ms="77.0", scope_note="batch"),
        ],
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    _make_nested_skill(repo_root, "tcs-team", "quality", "test-strategy")

    result = _run_report_cli(
        ["--events", str(events), "--repo-root", str(repo_root), "--home", str(home_dir)]
    )

    assert result.returncode == 0, result.stderr
    assert "docs/ai/memory/active.md: 2 load(s)" in result.stdout
    assert "session_start=2" in result.stdout
    assert "Configured but never loaded (0):" in result.stdout

    # T3.3 wiring: main() must pass the unreachable nested-skill data through
    # to build_load_report -- assert it actually reaches real stdout, same
    # posture as the Recording state/Byte cost assertions below.
    assert "unreachable" in result.stdout.lower()
    assert "plugins/tcs-team/skills/quality/test-strategy/SKILL.md" in result.stdout

    # Finding 3 (T3.2 code review): main() is the only real caller that
    # wires byte_stats=/recording= into build_load_report -- every other
    # test in this file calls build_load_report directly with hand-built
    # objects, bypassing main() entirely. Assert the actual CLI stdout
    # carries both honesty sections (with their computed values, not just
    # the section headers) so a future edit that drops or misorders those
    # keyword arguments fails here, rather than silently shipping the
    # "half a report" mode this task exists to prevent.
    assert "Recording state: UNKNOWN" in result.stdout
    assert "Byte cost -- always-loaded layer: 246 byte(s)" in result.stdout

    # T3.4 wiring: main() must pass hook_duration_stats(records) through to
    # build_load_report -- assert the single-scope duration reaches real
    # stdout, traceable to its hook_event/matcher, and that the batch-scoped
    # record's own figure (77.0) never appears as if it were a single hook's
    # own duration (ADR-7's misreading).
    assert "PreToolUse" in result.stdout
    assert "Skill" in result.stdout
    assert "0.001" in result.stdout
    assert "77.0" not in result.stdout
    assert "batch" in result.stdout.lower()


def test_cli_default_events_path_matches_writer_directory_shape(tmp_path):
    """No --events and no --data-dir: main() must resolve the events path the
    same way logwrite.sh's writer lays its directory out (ADR-1) -- checked
    here by placing the fixture at that exact resolved path and confirming
    the CLI actually reads it, not merely that the two resolvers agree in
    the abstract."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_dir = tmp_path / "home"
    events_dir = (
        home_dir / ".claude" / "plugins" / "data" / f"observability-{repo_root.name}" / "observability"
    )
    events_dir.mkdir(parents=True)
    _write_jsonl(events_dir / "events.jsonl", [_instruction("a.md", "session_start")])

    result = _run_report_cli(["--repo-root", str(repo_root), "--home", str(home_dir)])

    assert result.returncode == 0, result.stderr
    assert "a.md: 1 load(s)" in result.stdout


def test_cli_data_dir_override_is_honoured(tmp_path):
    """--data-dir must win over the default derivation -- the fixture is only
    reachable through the override, never through --home's default shape."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_dir = tmp_path / "home"  # left empty: must not be consulted
    home_dir.mkdir()
    data_dir = tmp_path / "custom-data"
    (data_dir / "observability").mkdir(parents=True)
    _write_jsonl(data_dir / "observability" / "events.jsonl", [_instruction("b.md", "compact")])

    result = _run_report_cli(
        ["--repo-root", str(repo_root), "--home", str(home_dir), "--data-dir", str(data_dir)]
    )

    assert result.returncode == 0, result.stderr
    assert "b.md: 1 load(s)" in result.stdout


def test_cli_missing_events_reports_none_found_and_exits_zero(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    missing_events = tmp_path / "nope.jsonl"

    result = _run_report_cli(
        ["--events", str(missing_events), "--repo-root", str(repo_root), "--home", str(home_dir)]
    )

    assert result.returncode == 0, result.stderr
    assert "No record found" in result.stdout


# --- the import-cycle guard (_collect_claude_md_imports / `seen`) ----------
#
# The reviewer hand-verified that a two-file @-import cycle and a self-import
# both terminate today. Nothing pinned that: a future edit that stops
# threading `seen` through the recursive call, or that adds to `found`
# before checking `seen`, would hang or blow the recursion limit against a
# real repo's CLAUDE.md hierarchy. These assert on the actual returned
# inventory (`found`), not merely that the call returned at all.


def test_collect_claude_md_imports_two_file_cycle_terminates(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("@b.md\n", encoding="utf-8")
    b.write_text("@a.md\n", encoding="utf-8")

    found: set[Path] = set()
    report._collect_claude_md_imports(a, tmp_path, found)

    assert found == {a.resolve(), b.resolve()}


def test_collect_claude_md_imports_self_import_terminates(tmp_path):
    a = tmp_path / "a.md"
    a.write_text("@a.md\n", encoding="utf-8")

    found: set[Path] = set()
    report._collect_claude_md_imports(a, tmp_path, found)

    assert found == {a.resolve()}


# --- redaction parity with logwrite.sh's _observability_redact_path --------
#
# report._redact_path (the reader) must produce the same string as
# _observability_redact_path in logwrite.sh (the writer) for the same path:
# the writer puts `path` into a record, this reader builds the inventory
# that record is matched against, and a divergence between the two makes a
# loaded file silently read as "never loaded" -- a wrong answer, not a
# missing one (CON-9). Same precedent as
# plugins/tcs-helper/tests/bats/observability-writer.bats's resolver-parity
# assertion and plugins/tcs-git-helpers/tests/bats/cache-path-parity.bats:
# both sides are actually executed, not restated as two copies of the same
# expected string. Kept in this file (not a new bats suite) because one side
# under test -- report._redact_path -- is a Python function this suite
# already imports; shelling out from here to bash mirrors the direction
# cache-path-parity.bats's print_resolved_path.py helper shells out from
# bats into python3, just reversed.


def _bash_redact_path(path: str, top: str) -> str:
    result = subprocess.run(
        ["bash", "-c", '. "$1"; _observability_redact_path "$2" "$3"',
         "_", str(LOGWRITE_SH), path, top],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _assert_redact_parity(path: Path, repo_root: Path) -> None:
    python_result = report._redact_path(path, repo_root)
    bash_result = _bash_redact_path(str(path), str(repo_root))
    assert python_result == bash_result, (
        f"reader/writer redaction diverge for {path!r} under {repo_root!r}: "
        f"python={python_result!r} bash={bash_result!r}"
    )


# --- the skill and agent inventory (T3.3, SDD/The two inventories, second
# table; PRD F8; SDD-AC-18) ---------------------------------------------------
#
# The namespace hazard this task exists to avoid: SDD/The two inventories
# says literally "agent name from frontmatter `name:`", but a real plugin
# agent is DISPATCHED under a qualified form, `<plugin>:<path under agents/,
# without extension, "/" -> ":">` (verified in this repo:
# plugins/tcs-team/agents/the-tester/test-strategy.md has frontmatter
# `name: test-strategy` but dispatches as `tcs-team:the-tester:test-strategy`).
# Every test below either pins that both forms are carried, or that the join
# accepts either without ever double-crediting an ambiguous bare name.


def _skill_record(skill: str, session: str = "s1", ts: str = "2026-09-06T16:43:28Z") -> dict:
    return {"ts": ts, "kind": "skill", "session": session, "repo": "the-custom-startup", "skill": skill}


def _agent_record(agent_type: str, session: str = "s1", ts: str = "2026-09-06T16:43:28Z") -> dict:
    return {
        "ts": ts, "kind": "agent", "session": session, "repo": "the-custom-startup",
        "agent_type": agent_type, "agent_id": "1",
    }


def _make_skill(repo_root: Path, plugin: str, name: str) -> Path:
    skill_dir = repo_root / "plugins" / plugin / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return skill_dir


def _make_agent(repo_root: Path, plugin: str, relative: str, frontmatter_name: str | None) -> Path:
    agent_path = repo_root / "plugins" / plugin / "agents" / relative
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    if frontmatter_name is None:
        agent_path.write_text("# no frontmatter here\n", encoding="utf-8")
    else:
        agent_path.write_text(f"---\nname: {frontmatter_name}\ndescription: x\n---\nbody\n", encoding="utf-8")
    return agent_path


# --- walk_skill_agent_inventory: building the inventory ---------------------


def test_walk_skill_agent_inventory_finds_skill_qualified_and_bare(tmp_path):
    _make_skill(tmp_path, "tcs-patterns", "observability")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    entry = next(e for e in inventory.entries if e.kind == "skill")
    assert entry.qualified == "tcs-patterns:observability"
    assert entry.bare == "observability"
    assert inventory.skill_count == 1
    assert inventory.agent_count == 0


def test_walk_skill_agent_inventory_skill_dir_without_skill_md_excluded(tmp_path):
    """A category directory that merely CONTAINS skill dirs (tcs-team's real
    layout: plugins/tcs-team/skills/the-tester/test-strategy/SKILL.md is two
    levels deep) must not itself be counted as a skill -- SDD/The two
    inventories' glob is one level (`skills/*/SKILL.md`), not recursive."""
    category_dir = tmp_path / "plugins" / "tcs-team" / "skills" / "quality"
    category_dir.mkdir(parents=True)
    (category_dir / "nested-skill").mkdir()
    (category_dir / "nested-skill" / "SKILL.md").write_text("nested\n", encoding="utf-8")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert inventory.skill_count == 0
    assert all(e.qualified != "tcs-team:quality" for e in inventory.entries)


def test_walk_skill_agent_inventory_agent_name_from_frontmatter_not_filename(tmp_path):
    _make_agent(tmp_path, "tcs-team", "leader.md", frontmatter_name="the-leader")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    entry = next(e for e in inventory.entries if e.kind == "agent")
    assert entry.bare == "the-leader"  # from frontmatter, not the "leader" filename
    assert entry.qualified == "tcs-team:leader"  # path-derived, disambiguating


def test_walk_skill_agent_inventory_nested_agent_qualified_name(tmp_path):
    """Mirrors the real repo: plugins/tcs-team/agents/the-tester/test-strategy.md
    has frontmatter `name: test-strategy` but dispatches qualified as
    `tcs-team:the-tester:test-strategy` -- the exact namespace hazard this
    task exists to close."""
    _make_agent(tmp_path, "tcs-team", "the-tester/test-strategy.md", frontmatter_name="test-strategy")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    entry = next(e for e in inventory.entries if e.kind == "agent")
    assert entry.bare == "test-strategy"
    assert entry.qualified == "tcs-team:the-tester:test-strategy"


def test_walk_skill_agent_inventory_deeply_nested_agent_is_found(tmp_path):
    """The `**` glob under agents/ must genuinely recurse two levels deep,
    mirroring the real
    plugins/tcs-team/agents/the-architect/reference/robustness-checklists.md."""
    _make_agent(
        tmp_path, "tcs-team", "the-architect/reference/robustness-checklists.md",
        frontmatter_name=None,
    )

    inventory = report.walk_skill_agent_inventory(tmp_path)

    entry = next(e for e in inventory.entries if e.kind == "agent")
    assert entry.qualified == "tcs-team:the-architect:reference:robustness-checklists"


def test_walk_skill_agent_inventory_missing_frontmatter_name_falls_back_to_filename(tmp_path):
    """A real file in this repo
    (plugins/tcs-team/agents/the-architect/reference/robustness-checklists.md)
    has no frontmatter at all. It must not crash the walk, and must still be
    included -- Claude Code's own harness lists it as a real dispatchable
    agent, deriving a name from its path when frontmatter supplies none."""
    _make_agent(tmp_path, "tcs-team", "reference/robustness-checklists.md", frontmatter_name=None)

    inventory = report.walk_skill_agent_inventory(tmp_path)

    entry = next(e for e in inventory.entries if e.kind == "agent")
    assert entry.bare == "robustness-checklists"  # falls back to the file stem
    assert entry.qualified == "tcs-team:reference:robustness-checklists"


def test_walk_skill_agent_inventory_local_claude_agents_dir(tmp_path):
    local_dir = tmp_path / ".claude" / "agents"
    local_dir.mkdir(parents=True)
    (local_dir / "helper.md").write_text("---\nname: helper\n---\nbody\n", encoding="utf-8")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    entry = next(e for e in inventory.entries if e.kind == "agent")
    assert entry.qualified == "helper"  # no plugin prefix -- repo-local
    assert entry.bare == "helper"


def test_walk_skill_agent_inventory_missing_local_agents_dir_does_not_crash(tmp_path):
    """`.claude/agents/` does not exist in this repo at all -- the real case
    this glob must handle without error."""
    tmp_path.mkdir(exist_ok=True)
    inventory = report.walk_skill_agent_inventory(tmp_path)
    assert inventory.entries == []


def test_walk_skill_agent_inventory_missing_plugins_dir_does_not_crash(tmp_path):
    inventory = report.walk_skill_agent_inventory(tmp_path)
    assert inventory.entries == []
    assert inventory.skill_count == 0
    assert inventory.agent_count == 0


def test_walk_skill_agent_inventory_states_skill_and_agent_counts(tmp_path):
    _make_skill(tmp_path, "tcs-patterns", "observability")
    _make_skill(tmp_path, "tcs-patterns", "testing")
    _make_agent(tmp_path, "tcs-team", "the-chief.md", frontmatter_name="the-chief")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert inventory.skill_count == 2
    assert inventory.agent_count == 1
    assert len(inventory.entries) == 3


# --- unreachable nested skills (SDD/The two inventories, third amendment,
# 2026-09-07 / T3.3): a SKILL.md nested deeper than one level under
# `skills/` cannot be discovered by the harness at all, so it must never be
# counted in the coverage denominator and never reported as "never fired" --
# but it must not be silently dropped either. -------------------------------


def _make_nested_skill(repo_root: Path, plugin: str, *segments: str) -> Path:
    """A SKILL.md nested `len(segments)` levels deep under `skills/` --
    e.g. `_make_nested_skill(root, "tcs-team", "quality", "test-strategy")`
    mirrors the real `plugins/tcs-team/skills/quality/test-strategy/SKILL.md`."""
    skill_dir = repo_root / "plugins" / plugin / "skills"
    for segment in segments:
        skill_dir = skill_dir / segment
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("nested\n", encoding="utf-8")
    return skill_dir / "SKILL.md"


def test_walk_skill_agent_inventory_two_levels_deep_is_unreachable(tmp_path):
    _make_nested_skill(tmp_path, "tcs-team", "quality", "test-strategy")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert len(inventory.unreachable) == 1
    assert "quality/test-strategy/SKILL.md" in inventory.unreachable[0]


def test_walk_skill_agent_inventory_unreachable_skill_not_in_entries(tmp_path):
    """It must not be in the coverage denominator -- i.e. never one of the
    entries `firing_coverage` joins against at all."""
    _make_nested_skill(tmp_path, "tcs-team", "quality", "test-strategy")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert inventory.skill_count == 0
    assert inventory.entries == []


def test_walk_skill_agent_inventory_unreachable_skill_does_not_change_denominator(tmp_path):
    """Requirement 1: the coverage fraction and its denominator are
    unchanged by an unreachable entry's presence -- assert the SAME
    denominator with and without the nested file."""
    _make_skill(tmp_path, "tcs-patterns", "observability")
    before = report.walk_skill_agent_inventory(tmp_path)
    before_coverage = report.firing_coverage(before.entries, set())

    _make_nested_skill(tmp_path, "tcs-team", "quality", "test-strategy")
    after = report.walk_skill_agent_inventory(tmp_path)
    after_coverage = report.firing_coverage(after.entries, set())

    assert after_coverage.denominator == before_coverage.denominator == 1
    assert len(after.unreachable) == 1


def test_walk_skill_agent_inventory_three_levels_deep_is_also_unreachable(tmp_path):
    """Don't hard-code exactly two levels -- three (or more) must also be
    caught."""
    _make_nested_skill(tmp_path, "tcs-team", "quality", "batch", "test-strategy")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert len(inventory.unreachable) == 1
    assert inventory.entries == []


def test_walk_skill_agent_inventory_one_level_deep_still_counted_normally(tmp_path):
    """The normal case must keep working: a one-level-deep SKILL.md is a
    real entry, not unreachable, alongside an unreachable nested one."""
    _make_skill(tmp_path, "tcs-patterns", "observability")
    _make_nested_skill(tmp_path, "tcs-team", "quality", "test-strategy")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert inventory.skill_count == 1
    assert len(inventory.unreachable) == 1
    entry = next(e for e in inventory.entries if e.kind == "skill")
    assert entry.qualified == "tcs-patterns:observability"


def test_walk_skill_agent_inventory_no_nested_skills_reports_zero_unreachable(tmp_path):
    _make_skill(tmp_path, "tcs-patterns", "observability")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert inventory.unreachable == ()


def test_walk_skill_agent_inventory_skill_md_directly_under_skills_dir_is_unreachable(tmp_path):
    """T3.3 code review, advisory finding A: a SKILL.md placed directly at
    `skills/SKILL.md` (one relative part, SHALLOWER than the discoverable
    `skills/<name>/SKILL.md` shape) is neither a normal entry nor a crash --
    it lands in `unreachable`, the same bucket as a too-deep nested one,
    because it likewise cannot be discovered by the harness."""
    _make_nested_skill(tmp_path, "tcs-team")

    inventory = report.walk_skill_agent_inventory(tmp_path)

    assert inventory.entries == []
    assert len(inventory.unreachable) == 1
    assert inventory.unreachable[0].endswith("skills/SKILL.md")


def test_build_load_report_unreachable_not_in_never_fired_list(tmp_path):
    """It must not appear in the 'never fired' / unused list at all --
    unreachable and unused are different findings with different fixes."""
    nested = _make_nested_skill(tmp_path, "tcs-team", "quality", "test-strategy")
    _make_skill(tmp_path, "tcs-patterns", "observability")

    inventory = report.walk_skill_agent_inventory(tmp_path)
    coverage = report.firing_coverage(inventory.entries, set())

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    # the unreachable path appears (named, not dropped) ...
    redacted = report._redact_path(nested, tmp_path)
    assert redacted in text
    # ... but never inside the "never fired" section as if it were unused
    never_fired_start = text.lower().index("never fired")
    unreachable_start = text.lower().index("unreachable")
    never_fired_section = text[never_fired_start:unreachable_start]
    assert redacted not in never_fired_section


def test_build_load_report_unreachable_section_names_them_as_unreachable_not_unused(tmp_path):
    _make_nested_skill(tmp_path, "tcs-team", "quality", "test-strategy")
    _make_skill(tmp_path, "tcs-patterns", "observability")

    inventory = report.walk_skill_agent_inventory(tmp_path)
    coverage = report.firing_coverage(inventory.entries, set())

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    assert "unreachable" in text.lower()
    assert "cannot" in text.lower()  # states they cannot be discovered/fire


def test_build_load_report_zero_unreachable_omits_awkward_empty_section(tmp_path):
    """No nested skills at all: no empty/awkward 'Unreachable (0):' section
    with nothing under it -- the section is omitted entirely."""
    _make_skill(tmp_path, "tcs-patterns", "observability")

    inventory = report.walk_skill_agent_inventory(tmp_path)
    coverage = report.firing_coverage(inventory.entries, set())

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    assert "unreachable" not in text.lower()


# --- fired_names: the numerator, empty values counted as unknown -----------


def test_fired_names_collects_skill_and_agent_values():
    records = [_skill_record("tcs-patterns:observability"), _agent_record("Explore")]
    assert report.fired_names(records) == {("skill", "tcs-patterns:observability"), ("agent", "Explore")}


def test_fired_names_empty_skill_value_counted_as_unknown_not_a_named_entry():
    records = [_skill_record("")]
    assert report.fired_names(records) == set()


def test_fired_names_empty_agent_type_value_counted_as_unknown_not_a_named_entry():
    records = [_agent_record("")]
    assert report.fired_names(records) == set()


def test_fired_names_ignores_non_skill_agent_kinds():
    records = [_instruction("a.md", "session_start"), _state("1")]
    assert report.fired_names(records) == set()


# --- firing_coverage: the join, and the ambiguity guard ---------------------


def test_firing_coverage_record_with_qualified_name_matches():
    entries = [report.InventoryEntry(qualified="tcs-team:the-tester:test-strategy", bare="test-strategy", kind="agent")]
    coverage = report.firing_coverage(entries, {("agent", "tcs-team:the-tester:test-strategy")})
    assert coverage.fired == entries
    assert coverage.unused == []


def test_firing_coverage_record_with_bare_name_matches():
    entries = [report.InventoryEntry(qualified="tcs-team:the-tester:test-strategy", bare="test-strategy", kind="agent")]
    coverage = report.firing_coverage(entries, {("agent", "test-strategy")})
    assert coverage.fired == entries
    assert coverage.unused == []


def test_firing_coverage_unused_entry_is_unused_not_missing():
    entries = [report.InventoryEntry(qualified="tcs-patterns:observability", bare="observability", kind="skill")]
    coverage = report.firing_coverage(entries, set())
    assert coverage.unused == entries
    assert coverage.fired == []


def test_firing_coverage_ambiguous_bare_name_collision_marks_neither_fired():
    """Two plugins each ship a same-named skill -- an ambiguous bare-name
    record must not mark BOTH (or either) as fired."""
    a = report.InventoryEntry(qualified="plugin-a:testing", bare="testing", kind="skill")
    b = report.InventoryEntry(qualified="plugin-b:testing", bare="testing", kind="skill")
    coverage = report.firing_coverage([a, b], {("skill", "testing")})

    assert coverage.fired == []
    assert set(coverage.unused) == {a, b}
    assert "testing [skill]" in coverage.ambiguous_record_names


def test_firing_coverage_qualified_name_disambiguates_collision():
    """The same collision as above, but the record carries the qualified
    name -- exactly one of the two entries must be marked fired."""
    a = report.InventoryEntry(qualified="plugin-a:testing", bare="testing", kind="skill")
    b = report.InventoryEntry(qualified="plugin-b:testing", bare="testing", kind="skill")
    coverage = report.firing_coverage([a, b], {("skill", "plugin-a:testing")})

    assert coverage.fired == [a]
    assert coverage.unused == [b]


def test_firing_coverage_cross_kind_bare_name_is_not_a_collision():
    """T3.3 code review, finding 1: a skill and an agent sharing a bare name
    is NOT the same hazard as two same-kind entries sharing one -- the
    record's own `kind` already says which one it means. A `kind: skill`
    record naming the shared bare name must credit the SKILL as fired, must
    NOT credit the agent, and must mark neither as ambiguous."""
    skill_entry = report.InventoryEntry(qualified="plugin-a:shared", bare="shared", kind="skill")
    agent_entry = report.InventoryEntry(qualified="plugin-b:shared", bare="shared", kind="agent")
    coverage = report.firing_coverage([skill_entry, agent_entry], {("skill", "shared")})

    assert coverage.fired == [skill_entry]
    assert coverage.unused == [agent_entry]
    assert coverage.ambiguous_record_names == []
    assert coverage.unmatched_record_names == []


def test_firing_coverage_record_naming_absent_entry_is_reported_not_dropped():
    entries = [report.InventoryEntry(qualified="tcs-patterns:observability", bare="observability", kind="skill")]
    coverage = report.firing_coverage(entries, {("agent", "Explore")})

    assert coverage.unused == entries
    assert coverage.unmatched_record_names == ["Explore [agent]"]


def test_firing_coverage_unmatched_records_of_different_kinds_render_as_two_lines():
    """T3.3 code review, finding 1 (reopened): a `kind: skill` record and a
    `kind: agent` record that share a bare name and BOTH fail to match any
    inventory entry are two distinct findings -- collapsing them to one bare
    name throws away exactly the `kind` information `fired_names` carries
    for this purpose (see its docstring). Assert on the RENDERED text, not
    just the NamedTuple fields -- a prior round's bug was a render-layer
    collapse that field-level assertions alone did not catch."""
    coverage = report.firing_coverage([], {("skill", "Explore"), ("agent", "Explore")})
    inventory = report.SkillAgentInventory(entries=[], skill_count=0, agent_count=0)

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    unmatched_start = text.lower().index("not found in this inventory at all")
    unmatched_section = text[unmatched_start:]
    rendered_lines = [line.strip() for line in unmatched_section.splitlines() if line.strip()]

    assert rendered_lines.count("Explore [skill]") == 1
    assert rendered_lines.count("Explore [agent]") == 1
    assert "('agent', 'Explore')" not in text
    assert "('skill', 'Explore')" not in text


def test_firing_coverage_ambiguous_records_of_different_kinds_render_as_two_lines():
    """Same collapse, other bucket: two ambiguous skill entries named `dup`
    and two ambiguous agent entries named `dup` must surface as two
    ambiguity findings, not one. Assert on the RENDERED text."""
    skill_a = report.InventoryEntry(qualified="plugin-a:dup", bare="dup", kind="skill")
    skill_b = report.InventoryEntry(qualified="plugin-b:dup", bare="dup", kind="skill")
    agent_a = report.InventoryEntry(qualified="plugin-a:dup", bare="dup", kind="agent")
    agent_b = report.InventoryEntry(qualified="plugin-b:dup", bare="dup", kind="agent")
    entries = [skill_a, skill_b, agent_a, agent_b]
    coverage = report.firing_coverage(entries, {("skill", "dup"), ("agent", "dup")})
    inventory = report.SkillAgentInventory(entries=entries, skill_count=2, agent_count=2)

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    ambiguous_start = text.lower().index("shared by two or more inventory entries")
    ambiguous_section = text[ambiguous_start:]
    rendered_lines = [line.strip() for line in ambiguous_section.splitlines() if line.strip()]

    assert rendered_lines.count("dup [skill]") == 1
    assert rendered_lines.count("dup [agent]") == 1
    assert "('agent', 'dup')" not in text
    assert "('skill', 'dup')" not in text


def test_firing_coverage_is_a_fraction():
    entries = [
        report.InventoryEntry(qualified="a:x", bare="x", kind="skill"),
        report.InventoryEntry(qualified="a:y", bare="y", kind="skill"),
        report.InventoryEntry(qualified="a:z", bare="z", kind="skill"),
    ]
    coverage = report.firing_coverage(entries, {("skill", "a:x")})

    assert coverage.numerator == 1
    assert coverage.denominator == 3


# --- the report renders the join: coverage, unused entries, and the
# inventory size (SDD-AC-18, PRD F8) -----------------------------------------


def test_build_load_report_states_skill_agent_inventory_size_and_coverage():
    inventory = report.SkillAgentInventory(
        entries=[report.InventoryEntry(qualified="a:x", bare="x", kind="skill")],
        skill_count=1,
        agent_count=0,
    )
    coverage = report.firing_coverage(inventory.entries, set())

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    assert "1 entries found" in text or "1 entrie" in text  # inventory size stated
    assert "0/1" in text  # coverage as a fraction


def test_build_load_report_never_fired_skill_reported_as_unused_not_missing():
    inventory = report.SkillAgentInventory(
        entries=[report.InventoryEntry(qualified="tcs-patterns:observability", bare="observability", kind="skill")],
        skill_count=1,
        agent_count=0,
    )
    coverage = report.firing_coverage(inventory.entries, set())

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    assert "tcs-patterns:observability" in text
    assert "unused" in text.lower()


def test_build_load_report_fired_skill_not_listed_as_unused():
    inventory = report.SkillAgentInventory(
        entries=[report.InventoryEntry(qualified="tcs-patterns:observability", bare="observability", kind="skill")],
        skill_count=1,
        agent_count=0,
    )
    coverage = report.firing_coverage(inventory.entries, {("skill", "tcs-patterns:observability")})

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    assert "1/1" in text


def test_build_load_report_without_skill_agent_inventory_omits_section():
    """Pre-existing callers/tests that never pass skill_agent_inventory=/
    firing= must keep working unchanged -- same posture as byte_stats=/
    recording= in spec-019 T3.2."""
    text = report.build_load_report({}, [])
    assert "never fired" not in text.lower()


def test_build_load_report_ambiguous_and_unmatched_render_under_correct_headings():
    """T3.3 code review, finding 2: `ambiguous_record_names` and
    `unmatched_record_names` render under two DIFFERENT headings. A
    mutation swapping which list is iterated under which heading would pass
    every other test in this file (they only assert on the `FiringCoverage`
    NamedTuple's fields, never on the rendered text) -- populate both lists
    at once, with distinguishable names, and pin each name to its own
    heading's section of the rendered text."""
    inventory = report.SkillAgentInventory(
        entries=[report.InventoryEntry(qualified="a:x", bare="x", kind="skill")],
        skill_count=1,
        agent_count=0,
    )
    coverage = report.FiringCoverage(
        fired=[],
        unused=inventory.entries,
        unmatched_record_names=["totally-unknown-name"],
        ambiguous_record_names=["shared-bare-name"],
    )

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)
    lowered = text.lower()

    ambiguous_heading_idx = lowered.index("shared by two or more inventory entries")
    unmatched_heading_idx = lowered.index("not found in this inventory at all")

    if ambiguous_heading_idx < unmatched_heading_idx:
        ambiguous_section = text[ambiguous_heading_idx:unmatched_heading_idx]
        unmatched_section = text[unmatched_heading_idx:]
    else:
        unmatched_section = text[unmatched_heading_idx:ambiguous_heading_idx]
        ambiguous_section = text[ambiguous_heading_idx:]

    assert "shared-bare-name" in ambiguous_section
    assert "totally-unknown-name" not in ambiguous_section
    assert "totally-unknown-name" in unmatched_section
    assert "shared-bare-name" not in unmatched_section


def test_redact_path_parity_nested_inside_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    nested = repo_root / "docs" / "ai" / "memory" / "active.md"
    _assert_redact_parity(nested, repo_root)
    assert report._redact_path(nested, repo_root) == "docs/ai/memory/active.md"


def test_redact_path_parity_repo_root_itself(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _assert_redact_parity(repo_root, repo_root)
    assert report._redact_path(repo_root, repo_root) == "."


def test_redact_path_parity_absolute_path_outside_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "home" / ".claude" / "CLAUDE.md"
    _assert_redact_parity(outside, repo_root)
    assert report._redact_path(outside, repo_root) == "CLAUDE.md"


# ---------------------------------------------------------------------------
# Hook durations: wrapper-sourced, single-invocation-scoped (T3.4, SDD-AC-17)
# ---------------------------------------------------------------------------
#
# `timed-wrapper.sh` (T3.5) is the only producer of `kind: hook` records, and
# it always writes `scope_note: single` -- it times exactly one invocation.
# `batch` remains in the enum only as a label for the HARNESS's own aggregate
# "Slow PreToolUse hooks" warning, never written by this design (solution.md,
# Integration Points). ADR-7's whole point: a record that does not carry
# `scope_note: single` must never be rendered as if it were one hook's own
# duration -- whether it says `batch` or says nothing about scope at all.
#
# `ms` and `exit` arrive as quoted strings ("0.001", "0"), never bare JSON
# numbers (confirmed against a real record produced by the shipped wrapper) --
# the same typing hazard `_parse_bytes` exists to catch for `bytes`, and this
# phase's `enabled="0"` bug for `exit`'s legitimate zero value.


def test_hook_duration_stats_single_scope_recorded_against_its_hook():
    records = [_hook("PreToolUse", "Skill", ms="12.5", exit_value="0", scope_note="single")]

    result = report.hook_duration_stats(records)

    assert result.installed is True
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.hook_event == "PreToolUse"
    assert entry.matcher == "Skill"
    assert entry.invocations == [report.HookInvocation(ms=12.5, exit=0)]


def test_hook_duration_stats_batch_scope_never_rendered_as_single():
    records = [_hook("PreToolUse", "Skill", ms="99.9", scope_note="batch")]

    result = report.hook_duration_stats(records)

    assert result.entries == []
    assert result.batch_count == 1


def test_hook_duration_stats_missing_scope_note_refused_as_single():
    records = [_hook("PreToolUse", "Skill", ms="5.0", scope_note=None)]

    result = report.hook_duration_stats(records)

    assert result.entries == []
    assert result.unscoped_count == 1


def test_hook_duration_stats_non_single_non_batch_scope_note_is_excluded_too():
    # Defensive: any value other than the two documented ones must still
    # never be folded into `entries` as if it meant "single".
    records = [_hook(scope_note="weird")]

    result = report.hook_duration_stats(records)

    assert result.entries == []
    assert result.unscoped_count == 1


def test_hook_duration_stats_no_hook_records_reports_not_installed():
    records = [_instruction("a.md", "session_start"), _state("1")]

    result = report.hook_duration_stats(records)

    assert result.installed is False
    assert result.entries == []
    assert result.batch_count == 0
    assert result.unscoped_count == 0


def test_hook_duration_stats_casts_quoted_string_ms_to_float():
    # A naive comparison against the raw string would never equal 0.001 --
    # this pins the cast, not just presence.
    records = [_hook(ms="0.001")]

    result = report.hook_duration_stats(records)

    assert result.entries[0].invocations[0].ms == 0.001
    assert isinstance(result.entries[0].invocations[0].ms, float)


def test_hook_duration_stats_non_numeric_ms_is_unmeasurable_not_zero():
    records = [_hook(ms="not-a-number")]

    result = report.hook_duration_stats(records)  # must not raise

    assert result.entries[0].invocations[0].ms is None


def test_hook_duration_stats_absent_ms_is_unmeasurable_not_zero():
    records = [_hook(ms=None)]

    result = report.hook_duration_stats(records)

    assert result.entries[0].invocations[0].ms is None


def test_hook_duration_stats_boolean_ms_is_rejected_not_coerced():
    # `float(True) == 1.0` / `float(False) == 0.0` both succeed silently in
    # plain Python -- a mis-serialized `"ms": false` must not become a
    # measured 0.0 (or 1.0).
    records = [_hook(ms=False)]

    result = report.hook_duration_stats(records)

    assert result.entries[0].invocations[0].ms is None


def test_hook_duration_stats_exit_zero_string_parsed_as_int_zero_not_falsy():
    records = [_hook(exit_value="0")]

    result = report.hook_duration_stats(records)

    invocation = result.entries[0].invocations[0]
    # Pin against the truthiness trap this phase already hit once
    # (`enabled="0"` read as True): a clean exit 0 must parse to the int
    # 0, distinguishable from "no exit code recorded" (`None`).
    assert invocation.exit == 0
    assert invocation.exit is not None


def test_hook_duration_stats_boolean_exit_is_rejected_not_coerced():
    records = [_hook(exit_value=True)]

    result = report.hook_duration_stats(records)

    assert result.entries[0].invocations[0].exit is None


def test_hook_duration_stats_non_numeric_exit_is_unmeasurable_not_fatal():
    records = [_hook(exit_value="not-a-number")]

    result = report.hook_duration_stats(records)  # must not raise

    assert result.entries[0].invocations[0].exit is None


def test_hook_duration_stats_multiple_hooks_kept_distinct():
    records = [
        _hook("PreToolUse", "Skill", ms="1.0"),
        _hook("PostToolUse", "Bash", ms="2.0"),
        _hook("PreToolUse", "Skill", ms="3.0"),
    ]

    result = report.hook_duration_stats(records)

    keyed = {(e.hook_event, e.matcher): e for e in result.entries}
    assert set(keyed) == {("PreToolUse", "Skill"), ("PostToolUse", "Bash")}
    assert len(keyed[("PreToolUse", "Skill")].invocations) == 2
    assert len(keyed[("PostToolUse", "Bash")].invocations) == 1


def test_hook_duration_stats_ignores_non_hook_kinds():
    records = [_instruction("a.md", "session_start"), _state("1"), {"kind": "skill", "skill": "x"}]

    result = report.hook_duration_stats(records)

    assert result.installed is False
    assert result.entries == []


# --- the report renders hook durations, honestly (SDD-AC-17) ---------------


def test_build_load_report_without_hooks_omits_hook_section():
    """Pre-existing callers/tests that never pass `hooks=` must keep working
    unchanged -- same posture as byte_stats=/recording=/skill_agent_inventory=
    above."""
    text = report.build_load_report({}, [])
    assert "hook" not in text.lower()


def test_build_load_report_no_hook_records_states_timing_not_installed():
    hooks = report.hook_duration_stats([_instruction("a.md", "session_start")])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "not installed" in text.lower()
    assert "0 hooks" not in text.lower()


def test_build_load_report_single_scope_hook_duration_traceable_to_hook_event_and_matcher():
    hooks = report.hook_duration_stats([_hook("PreToolUse", "Skill", ms="0.5", exit_value="0")])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "PreToolUse" in text
    assert "Skill" in text
    assert "0.5" in text


def test_build_load_report_renders_known_whole_millisecond_value_without_trailing_zero():
    # REGRESSION (1000x unit bug, #153): `timed-wrapper.sh` now converts
    # %3R seconds to integer milliseconds before writing `ms`, so a real
    # record for a ~500ms hook carries `"ms": "502"`, not `"ms": "0.502"`.
    # Assert the report renders that known value as "502 ms" -- proving
    # both that the magnitude survived (not 1000x off in either direction)
    # and that a whole-number ms value prints without a noisy ".0".
    hooks = report.hook_duration_stats([_hook("PreToolUse", "Skill", ms="502", exit_value="0")])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "502 ms" in text
    assert "502.0 ms" not in text


def test_build_load_report_empty_matcher_rendered_as_no_matcher_not_unknown():
    # An empty-string matcher is the correct, documented value for
    # `SubagentStart` (and `InstructionsLoaded`) -- it means "every load,
    # regardless of reason/subagent type" (observability README), not
    # "we don't know the matcher". Rendering it as "(unknown matcher)"
    # would tell the reader data is missing when it is not.
    hooks = report.hook_duration_stats(
        [_hook("SubagentStart", "", ms="10", exit_value="0")]
    )

    text = report.build_load_report({}, [], hooks=hooks)

    assert "SubagentStart / (no matcher)" in text
    assert "(unknown matcher)" not in text


def test_build_load_report_missing_matcher_still_rendered_as_unknown():
    # Contrast case: a matcher that is genuinely ABSENT (not an explicit
    # empty string) is a malformed/anomalous record, and stays "(unknown
    # matcher)" -- distinct from the legitimate empty-string case above.
    record = _hook("SubagentStart", "", ms="10", exit_value="0")
    del record["matcher"]
    hooks = report.hook_duration_stats([record])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "SubagentStart / (unknown matcher)" in text
    assert "(no matcher)" not in text


def test_build_load_report_batch_scope_never_shown_as_single_duration():
    hooks = report.hook_duration_stats([_hook(ms="999.0", scope_note="batch")])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "999.0" not in text


def test_build_load_report_batch_count_is_surfaced_not_silently_dropped():
    hooks = report.hook_duration_stats([_hook(scope_note="batch"), _hook(scope_note="batch")])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "batch" in text.lower()
    assert "2" in text


def test_build_load_report_missing_scope_note_never_shown_as_single_duration():
    hooks = report.hook_duration_stats([_hook(ms="42.0", scope_note=None)])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "42.0" not in text


def test_build_load_report_unscoped_count_is_surfaced_not_silently_dropped():
    hooks = report.hook_duration_stats([_hook(scope_note=None)])

    text = report.build_load_report({}, [], hooks=hooks)

    assert "1" in text
    assert "scope_note" in text.lower()


def test_build_load_report_hook_section_appears_after_no_hooks_call_too():
    # Symmetry check: the "not installed" branch and the populated branch
    # both go through the same optional-parameter posture.
    hooks_none = report.hook_duration_stats([])
    text = report.build_load_report({}, [], hooks=hooks_none)
    assert "not installed" in text.lower()


# ---------------------------------------------------------------------------
# Per-source rendering, and the honesty rules (spec-019 T3.3, ADR-7).
#
# ADR-7: merging several sources' records without introducing the `repo`
# dimension produces a plausible, wrong number -- recording status and byte
# accounting both collapse to a single winner across a merged stream, so one
# live source would report the whole set as fresh and hide a source that
# stopped recording months ago. `build_multi_source_report` (report.py) is
# what this section tests: one section per configured `sources.Source`,
# never pooled.
# ---------------------------------------------------------------------------


def test_recording_status_merged_across_sources_reports_only_the_freshest():
    """spec-019 T3.3 ruling (a): pins the COLLAPSE the per-source split
    exists to fix, against TODAY'S unmodified `recording_status` -- kept
    permanently, right beside the split test below, so the contrast between
    "merged" and "split" stays legible in the test suite itself.

    Source A's newest `kind: state` record is 5 minutes old (fresh); source
    B's is ~101 days old (stale). Concatenated into one flat list and run
    through `recording_status` exactly as a naive merge would, the result
    reports `stale=False` and `newest_ts` equal to A's -- the whole set
    reads as fresh, and B's staleness is invisible. This PASSES today, and
    that is the point: it demonstrates the defect, not a fix for it.
    """
    now = datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc)
    source_a_state = _state(enabled="1", ts="2026-09-10T08:00:00Z")
    source_b_state = _state(enabled="1", ts="2026-06-01T08:00:00Z")
    merged = [source_a_state, source_b_state]

    status = report.recording_status(merged, now)

    assert status.stale is False
    assert status.newest_ts == "2026-09-10T08:00:00Z"


def test_build_multi_source_report_splits_recording_status_per_source_and_names_the_stale_one(tmp_path):
    """spec-019 T3.3 ruling (a)/(b): the SPLIT half of the test above -- same
    fixture (source A fresh, source B ~101 days stale), through the new
    per-source path. Each source must report its OWN recording state: A
    fresh, B stale, and B's label present in the rendered output so a reader
    can tell which source went stale. Before the split is implemented this
    must fail on VALUES (the rendered text does not distinguish the two
    sources), never on a missing symbol.
    """
    now = datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc)

    root_a = tmp_path / "repo-a"
    root_a.mkdir()
    home_a = tmp_path / "home-a"
    home_a.mkdir()
    _write_source_events(root_a, home_a, [_state(enabled="1", ts="2026-09-10T08:00:00Z")])

    root_b = tmp_path / "repo-b"
    root_b.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()
    _write_source_events(root_b, home_b, [_state(enabled="1", ts="2026-06-01T08:00:00Z")])

    source_a = sources.Source(
        label="source-a", repo_root=root_a, homes=[sources.HomeStatus(home=home_a, state=sources.RECORDING)]
    )
    source_b = sources.Source(
        label="source-b", repo_root=root_b, homes=[sources.HomeStatus(home=home_b, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report([source_a, source_b], now)

    assert "=== source-a ===" in text
    assert "=== source-b ===" in text
    section_a, section_b = text.split("=== source-b ===")
    assert "Recording state: recording" in section_a
    assert "Recording state: STALE" in section_b
    assert "source-b" in text  # the stale source is named, not merely a status flag


def test_combine_inventories_unions_entries_and_ands_git_filtered():
    """spec-019 T3.3 ruling (i): `entries` unions (safe -- the walk already
    over-lists by design); `git_filtered` combines with AND, not OR --
    reporting the LESS confident state when two homes' walks disagree, since
    `or` would overclaim filtering the other home never achieved. Tested
    directly against hand-built `InstructionInventory` values rather than
    real `git check-ignore` runs, because the two homes of one source always
    share a `repo_root` and so agree in practice -- this is the one place
    the disagreement branch can be exercised deterministically.
    """
    a = report.InstructionInventory(entries=["a.md", "shared.md"], git_filtered=True)
    b = report.InstructionInventory(entries=["b.md", "shared.md"], git_filtered=False)

    combined = report._combine_inventories([a, b])

    assert combined.entries == ["a.md", "b.md", "shared.md"]
    assert combined.git_filtered is False


def test_build_multi_source_report_inventory_union_includes_file_present_in_only_one_home(tmp_path):
    """spec-019 T3.3 ruling (i)/SDD-AC-25: `walk_instruction_inventory` is
    called once per entry in `source.homes` and the results combined -- a
    file present in only ONE home must still appear in the denominator, or
    it shows up as neither loaded nor never-loaded and vanishes with nothing
    to say it was gone (the primary-home-rule failure the SDD warns about).
    """
    repo_root = tmp_path / "twohome-repo"
    (repo_root / "docs" / "ai" / "memory").mkdir(parents=True)
    (repo_root / "docs" / "ai" / "memory" / "only-in-repo.md").write_text("x", encoding="utf-8")

    home_container = tmp_path / "home-container"
    home_container.mkdir()
    home_host = tmp_path / "home-host"
    (home_host / ".claude" / "rules").mkdir(parents=True)
    (home_host / ".claude" / "rules" / "only-in-host-home.md").write_text("x", encoding="utf-8")

    source = sources.Source(
        label="twohome",
        repo_root=repo_root,
        homes=[
            sources.HomeStatus(home=home_container, state=sources.NOT_YET_RECORDING),
            sources.HomeStatus(home=home_host, state=sources.NOT_YET_RECORDING),
        ],
    )

    text, _ = report.build_multi_source_report([source], datetime(2026, 9, 10, tzinfo=timezone.utc))

    assert "2 configured file(s) found" in text
    assert "only-in-repo.md" in text
    assert "only-in-host-home.md" in text


def test_build_multi_source_report_never_loaded_is_per_source_not_pooled(tmp_path):
    """spec-019 T3.3, 'Also test': the never-loaded list is a per-source
    difference against that source's own inventory walk, never a pooled
    set. Source A has a configured-but-unloaded file; it must appear ONLY in
    A's section, never leaking into B's."""
    root_a = tmp_path / "repo-a"
    (root_a / "docs" / "ai" / "memory").mkdir(parents=True)
    (root_a / "docs" / "ai" / "memory" / "unused-in-a.md").write_text("x", encoding="utf-8")
    home_a = tmp_path / "home-a"
    home_a.mkdir()

    root_b = tmp_path / "repo-b"
    root_b.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()

    source_a = sources.Source(
        label="a", repo_root=root_a, homes=[sources.HomeStatus(home=home_a, state=sources.NOT_YET_RECORDING)]
    )
    source_b = sources.Source(
        label="b", repo_root=root_b, homes=[sources.HomeStatus(home=home_b, state=sources.NOT_YET_RECORDING)]
    )

    text, _ = report.build_multi_source_report([source_a, source_b], datetime(2026, 9, 10, tzinfo=timezone.utc))

    section_a, section_b = text.split("=== b ===")
    assert "unused-in-a.md" in section_a
    assert "unused-in-a.md" not in section_b


def test_build_multi_source_report_concatenates_homes_within_one_source_never_across_sources(tmp_path):
    """spec-019 T3.3 ruling (j): within a source, homes' streams
    CONCATENATE -- both of source A's homes' loads must appear in A's own
    section. Across sources, records never touch: a load recorded only in
    source A's home must never appear in source B's section, and vice
    versa."""
    root_a = tmp_path / "repo-a"
    root_a.mkdir()
    home_a1 = tmp_path / "home-a1"
    home_a1.mkdir()
    home_a2 = tmp_path / "home-a2"
    home_a2.mkdir()
    _write_source_events(root_a, home_a1, [_instruction("only-in-a1.md", "session_start", repo="repo-a")])
    _write_source_events(root_a, home_a2, [_instruction("only-in-a2.md", "compact", repo="repo-a")])

    root_b = tmp_path / "repo-b"
    root_b.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()
    _write_source_events(root_b, home_b, [_instruction("only-in-b.md", "session_start", repo="repo-b")])

    source_a = sources.Source(
        label="a",
        repo_root=root_a,
        homes=[
            sources.HomeStatus(home=home_a1, state=sources.RECORDING),
            sources.HomeStatus(home=home_a2, state=sources.RECORDING),
        ],
    )
    source_b = sources.Source(
        label="b", repo_root=root_b, homes=[sources.HomeStatus(home=home_b, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report([source_a, source_b], datetime(2026, 9, 10, tzinfo=timezone.utc))

    section_a, section_b = text.split("=== b ===")
    assert "only-in-a1.md" in section_a
    assert "only-in-a2.md" in section_a
    assert "only-in-b.md" not in section_a
    assert "only-in-b.md" in section_b
    assert "only-in-a1.md" not in section_b
    assert "only-in-a2.md" not in section_b


def test_build_multi_source_report_byte_accounting_is_per_source(tmp_path):
    """spec-019 T3.3, 'Also test': byte accounting is reported per source --
    source A's 100 bytes must not bleed into B's total (50), and vice
    versa."""
    root_a = tmp_path / "repo-a"
    root_a.mkdir()
    home_a = tmp_path / "home-a"
    home_a.mkdir()
    _write_source_events(
        root_a, home_a, [_instruction("a.md", "session_start", bytes_value="100", repo="repo-a")]
    )

    root_b = tmp_path / "repo-b"
    root_b.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()
    _write_source_events(
        root_b, home_b, [_instruction("b.md", "session_start", bytes_value="50", repo="repo-b")]
    )

    source_a = sources.Source(
        label="a", repo_root=root_a, homes=[sources.HomeStatus(home=home_a, state=sources.RECORDING)]
    )
    source_b = sources.Source(
        label="b", repo_root=root_b, homes=[sources.HomeStatus(home=home_b, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report([source_a, source_b], datetime(2026, 9, 10, tzinfo=timezone.utc))

    section_a, section_b = text.split("=== b ===")
    assert "Byte cost -- always-loaded layer: 100 byte(s)" in section_a
    assert "Byte cost -- always-loaded layer: 50 byte(s)" in section_b


def test_build_multi_source_report_looks_up_by_repo_root_basename_headed_by_label(tmp_path):
    """spec-019 T3.3 ruling (f): `instruction_stats_by_repo`'s outer key is
    the record's own `repo` field (frozen by `logwrite.sh` to `repo_root`'s
    basename), while `Source.label` is free text a human chose -- the two
    are not interchangeable. Without this test (which the plan lacked),
    looking a section up by label instead of basename -- or heading it with
    the basename instead of the label -- would both pass every other test in
    this file, since every other fixture happens to use the same string for
    both."""
    repo_root = tmp_path / "actual-basename"
    repo_root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    _write_source_events(
        repo_root, home, [_instruction("a.md", "session_start", repo="actual-basename")]
    )

    source = sources.Source(
        label="Human Label", repo_root=repo_root, homes=[sources.HomeStatus(home=home, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report([source], datetime(2026, 9, 10, tzinfo=timezone.utc))

    assert "=== Human Label ===" in text
    assert "a.md: 1 load(s)" in text


def test_build_multi_source_report_wires_hook_timing_in_but_leaves_firing_coverage_out(tmp_path):
    """spec-019 T3.4 ruling (q): retires
    `test_build_multi_source_report_leaves_skill_agent_and_hook_sections_out`
    (T3.3 ruling (k)) ON PURPOSE -- captured RED verbatim before this rewrite,
    in this task's report, per the T3.4 gate. Ruling (k) fixed `hooks=None`
    at `_build_source_report`'s call site as T3.3's clean insertion point for
    T3.4; ruling (q) is what completes that stub -- hook timing is per
    repository (ADR-7: only firing coverage unions), so it is wired into
    `_build_source_report` itself, the exact function this test inspects.
    Its firing-coverage half stays VALID but is now MISLEADING as a
    same-function assertion: the union renders in `main()` (ruling (n)),
    which `build_multi_source_report` never calls, so "absent from this
    function's output" proves nothing about whether the union exists --
    see `test_cli_multi_source_config_denominator_walked_from_shipping_repo_only`
    and the other T3.4 tests below for the union's own coverage."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    _write_source_events(repo_root, home, [_instruction("a.md", "session_start", repo="repo")])
    source = sources.Source(
        label="repo", repo_root=repo_root, homes=[sources.HomeStatus(home=home, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report([source], datetime(2026, 9, 10, tzinfo=timezone.utc))

    assert "hook timing" in text.lower()  # T3.4 ruling (q): now wired in, per source
    assert "skill and agent inventory" not in text.lower()  # still true -- rendered only in main()


# ---------------------------------------------------------------------------
# Per-home sub-lines within one source's section (spec-019 T3.2 ruling (a),
# implemented here in T3.3 since T3.2 could only deliver the per-home DATA --
# see ruling (a)'s own text: "the two streams merge exactly as `read_events`
# already merges a rotation chain, one level up -- and each home's own state
# is listed beneath it"). `HomeStatus.state` and `Source.verdict` were
# computed and tested in `test_observability_sources.py` since T3.2 but never
# read by `report.py` until now -- these tests pin that they are read.
# ---------------------------------------------------------------------------


def test_build_multi_source_report_renders_per_home_sublines_for_two_homes(tmp_path):
    """spec-019 T3.3 ruling (a): a two-home source renders one headline
    verdict -- "recording if ANY home is" (`sources.Source.verdict`) -- plus
    a sub-line PER home beneath it. The missing home's identifying text is
    the assertion that matters: the whole point of the ruling is that a
    second home that died cannot hide behind a healthy headline."""
    root = tmp_path / "repo-two-homes"
    root.mkdir()
    home_recording = tmp_path / "home-recording"
    home_recording.mkdir()
    _write_source_events(root, home_recording, [_state(enabled="1", ts="2026-09-10T08:12:00Z")])

    home_missing = tmp_path / "home-missing-does-not-exist"  # deliberately never created

    source = sources.Source(
        label="repo-two-homes",
        repo_root=root,
        homes=[
            sources.HomeStatus(home=home_recording, state=sources.RECORDING),
            sources.HomeStatus(home=home_missing, state=sources.MISSING),
        ],
    )

    text, _ = report.build_multi_source_report([source], datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc))

    assert "Recording state: recording" in text  # any home recording wins the headline
    assert str(home_recording) in text  # the healthy home is named
    assert str(home_missing) in text  # the dead home is named -- it cannot hide
    assert "missing" in text.lower()


def test_build_multi_source_report_dead_second_home_not_identical_to_healthy_single_home(tmp_path):
    """spec-019 T3.3 ruling (a): the ruling's own rejection criterion, made a
    direct comparison rather than two separate substring checks -- "a source
    whose second home died months ago would look identical to a healthy one"
    is exactly the collapse this must NOT reproduce. Same `repo_root`, same
    recording home, same records; the only difference between the two
    fixtures is whether a second, dead home is also configured."""
    now = datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc)
    root = tmp_path / "repo"
    root.mkdir()
    home_recording = tmp_path / "home-recording"
    home_recording.mkdir()
    _write_source_events(root, home_recording, [_state(enabled="1", ts="2026-09-10T08:12:00Z")])
    home_missing = tmp_path / "home-missing-does-not-exist"

    source_healthy = sources.Source(
        label="repo", repo_root=root, homes=[sources.HomeStatus(home=home_recording, state=sources.RECORDING)]
    )
    source_dying = sources.Source(
        label="repo",
        repo_root=root,
        homes=[
            sources.HomeStatus(home=home_recording, state=sources.RECORDING),
            sources.HomeStatus(home=home_missing, state=sources.MISSING),
        ],
    )

    text_healthy, _ = report.build_multi_source_report([source_healthy], now)
    text_dying, _ = report.build_multi_source_report([source_dying], now)

    assert text_healthy != text_dying


def test_build_multi_source_report_reads_home_status_state_not_just_records(tmp_path):
    """Guard against `HomeStatus.state` going write-only again (the defect
    this whole ruling responds to: computed and tested since T3.2, read by
    `report.py` nowhere until this task). Two sources are identical in every
    way -- same `repo_root`, same two homes, same on-disk records (home_b's
    stream is empty in both) -- and differ ONLY in `home_b`'s `HomeStatus.state`.
    If `_build_source_report` ever stops reading that field, nothing else
    in these fixtures differs and this test goes red."""
    now = datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc)
    root = tmp_path / "repo"
    root.mkdir()
    home_a = tmp_path / "home-a"
    home_a.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()
    _write_source_events(root, home_a, [_state(enabled="1", ts="2026-09-10T08:00:00Z")])
    # home_b's own record stream is never written in either variant below --
    # both fixtures see it as empty; only its HomeStatus.state differs.

    source_state_missing = sources.Source(
        label="repo",
        repo_root=root,
        homes=[
            sources.HomeStatus(home=home_a, state=sources.RECORDING),
            sources.HomeStatus(home=home_b, state=sources.MISSING),
        ],
    )
    source_state_not_yet = sources.Source(
        label="repo",
        repo_root=root,
        homes=[
            sources.HomeStatus(home=home_a, state=sources.RECORDING),
            sources.HomeStatus(home=home_b, state=sources.NOT_YET_RECORDING),
        ],
    )

    text_missing, _ = report.build_multi_source_report([source_state_missing], now)
    text_not_yet, _ = report.build_multi_source_report([source_state_not_yet], now)

    assert text_missing != text_not_yet


def test_build_multi_source_report_per_home_timestamp_is_that_homes_own_not_the_merged_one(tmp_path):
    """spec-019 T3.3 ruling (a): each RECORDING home's sub-line must show
    THAT home's own newest `ts`, computed from that home's own stream before
    the homes concatenate -- never the source's merged `newest_ts` borrowed
    from a fresher sibling. Two homes, both `recording`, at different
    timestamps: the older home's line must carry its own (older) timestamp
    and must NOT carry the fresher home's timestamp. `newest_ts(home_records)`
    changed to `newest_ts(records)` (the merged stream) makes this fail while
    leaving every other assertion in this file green -- the older home would
    silently advertise its sibling's fresher timestamp, exactly the
    dishonesty the sub-lines exist to prevent."""
    now = datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc)
    root = tmp_path / "repo"
    root.mkdir()
    home_fresh = tmp_path / "home-fresh"
    home_fresh.mkdir()
    home_older = tmp_path / "home-older"
    home_older.mkdir()
    _write_source_events(root, home_fresh, [_state(enabled="1", ts="2026-09-10T08:12:00Z")])
    _write_source_events(root, home_older, [_state(enabled="1", ts="2026-09-09T09:00:00Z")])

    source = sources.Source(
        label="repo",
        repo_root=root,
        homes=[
            sources.HomeStatus(home=home_fresh, state=sources.RECORDING),
            sources.HomeStatus(home=home_older, state=sources.RECORDING),
        ],
    )

    text, _ = report.build_multi_source_report([source], now)

    fresh_line = next(line for line in text.splitlines() if str(home_fresh) in line)
    older_line = next(line for line in text.splitlines() if str(home_older) in line)
    assert "2026-09-10T08:12:00Z" in fresh_line
    assert "2026-09-09T09:00:00Z" in older_line
    assert "2026-09-10T08:12:00Z" not in older_line  # never borrows the fresher sibling's ts


def test_build_multi_source_report_single_home_source_has_no_sublines(tmp_path):
    """spec-019 T3.3 ruling (a), scope decision: a source with exactly one
    home renders NO per-home sub-line. The headline already reports that
    one home's own state exactly -- no collapse has happened yet to hide
    anything -- so a sub-line would only restate the headline. Pins the
    choice against the pre-existing T3.3 tests, all of which use single-home
    sources and must keep rendering unchanged."""
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    _write_source_events(root, home, [_state(enabled="1", ts="2026-09-10T08:12:00Z")])
    source = sources.Source(
        label="repo", repo_root=root, homes=[sources.HomeStatus(home=home, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report([source], datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc))

    assert str(home) not in text


def test_cli_absent_config_and_empty_config_both_fall_back_to_single_record(tmp_path):
    """spec-019 T3.3 ruling (h): an absent config file and a config with
    zero `[[source]]` entries both fall back to the single-record path
    identically -- there is no third case. Same fixture placed at the
    default resolved events path in both trees; stdout must match exactly,
    and neither carries a `=== ... ===` per-source section header."""

    def _fixture(root: Path) -> tuple[Path, Path]:
        repo_root = root / "repo"
        repo_root.mkdir(parents=True)
        home_dir = root / "home"
        home_dir.mkdir()
        _write_source_events(repo_root, home_dir, [_instruction("a.md", "session_start", repo=repo_root.name)])
        return repo_root, home_dir

    no_config_root, no_config_home = _fixture(tmp_path / "no-config")
    result_no_config = _run_report_cli(["--repo-root", str(no_config_root), "--home", str(no_config_home)])

    empty_config_root, empty_config_home = _fixture(tmp_path / "empty-config")
    (empty_config_root / ".claude").mkdir(parents=True, exist_ok=True)
    (empty_config_root / ".claude" / "observability-sources.toml").write_text("", encoding="utf-8")
    result_empty_config = _run_report_cli(
        ["--repo-root", str(empty_config_root), "--home", str(empty_config_home)]
    )

    assert result_no_config.returncode == 0, result_no_config.stderr
    assert result_empty_config.returncode == 0, result_empty_config.stderr
    assert result_no_config.stdout == result_empty_config.stdout
    assert "a.md: 1 load(s)" in result_no_config.stdout
    assert "===" not in result_no_config.stdout


def test_cli_multi_source_config_renders_a_section_per_source(tmp_path):
    """spec-019 T3.3: main()'s config-driven branch, exercised end-to-end
    through the real CLI (not `build_multi_source_report` called directly)
    -- proves `main()` actually loads the config file and wires it through,
    the same wiring posture `test_cli_end_to_end_prints_report_for_fixture_events`
    already holds spec-019 T3.1/T3.2/T3.4 to."""
    repo_root = tmp_path / "repo"
    claude_dir = repo_root / ".claude"
    claude_dir.mkdir(parents=True)

    source_a_repo = tmp_path / "source-a-repo"
    source_a_repo.mkdir()
    source_a_home = tmp_path / "source-a-home"
    source_a_home.mkdir()
    _write_source_events(
        source_a_repo, source_a_home, [_instruction("a.md", "session_start", repo="source-a-repo")]
    )

    source_b_repo = tmp_path / "source-b-repo"
    source_b_repo.mkdir()
    source_b_home = tmp_path / "source-b-home"
    source_b_home.mkdir()
    _write_source_events(
        source_b_repo, source_b_home, [_instruction("b.md", "session_start", repo="source-b-repo")]
    )

    (claude_dir / "observability-sources.toml").write_text(
        f'[[source]]\nlabel = "Source A"\nrepo_root = "{source_a_repo}"\nhomes = ["{source_a_home}"]\n\n'
        f'[[source]]\nlabel = "Source B"\nrepo_root = "{source_b_repo}"\nhomes = ["{source_b_home}"]\n',
        encoding="utf-8",
    )

    result = _run_report_cli(["--repo-root", str(repo_root), "--home", str(tmp_path / "unused-home")])

    assert result.returncode == 0, result.stderr
    assert "=== Source A ===" in result.stdout
    assert "=== Source B ===" in result.stdout
    assert "a.md: 1 load(s)" in result.stdout
    assert "b.md: 1 load(s)" in result.stdout


# ---------------------------------------------------------------------------
# T3.4: the one union -- firing coverage across sources (ADR-8, rulings (l)-(q)).
# ---------------------------------------------------------------------------


def test_build_multi_source_report_union_and_per_source_firing_coverage(tmp_path):
    """spec-019 T3.4's own required test (rulings (m)/(p), ADR-8). Skill X
    fires only in source A, skill Y only in source B, skill Z in BOTH, skill
    W in neither -- deliberately NOT a fixture where both sources fire
    identical sets, which "cannot tell a union from an intersection, and
    cannot tell whether the second source was silently dropped" (T3.4 gate).

    The denominator (`inventory`) is walked from a THIRD root standing in for
    the shipping repository -- never from either source's own `repo_root` --
    matching how `main()` actually calls `walk_skill_agent_inventory` (ruling
    (l)). `union_fired_names`/`firing_coverage` are the same pure functions
    `main()` composes; this test exercises that composition directly rather
    than through the CLI, since the union renders in `main()` and
    `build_multi_source_report` never calls it (ruling (n))."""
    shipping_root = tmp_path / "shipping-repo"
    _make_skill(shipping_root, "plugin", "skill-x")
    _make_skill(shipping_root, "plugin", "skill-y")
    _make_skill(shipping_root, "plugin", "skill-z")
    _make_skill(shipping_root, "plugin", "skill-w")
    inventory = report.walk_skill_agent_inventory(shipping_root)

    root_a = tmp_path / "repo-a"
    root_a.mkdir()
    home_a = tmp_path / "home-a"
    home_a.mkdir()
    _write_source_events(
        root_a, home_a, [_skill_record("plugin:skill-x"), _skill_record("plugin:skill-z")]
    )

    root_b = tmp_path / "repo-b"
    root_b.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()
    _write_source_events(
        root_b, home_b, [_skill_record("plugin:skill-y"), _skill_record("plugin:skill-z")]
    )

    source_a = sources.Source(
        label="source-a", repo_root=root_a, homes=[sources.HomeStatus(home=home_a, state=sources.RECORDING)]
    )
    source_b = sources.Source(
        label="source-b", repo_root=root_b, homes=[sources.HomeStatus(home=home_b, state=sources.RECORDING)]
    )

    _, source_records = report.build_multi_source_report(
        [source_a, source_b], datetime(2026, 9, 10, tzinfo=timezone.utc)
    )
    fired_by_source = [(source.label, report.fired_names(records)) for source, records in source_records]

    union_fired = report.union_fired_names(fired for _, fired in fired_by_source)
    union_coverage = report.firing_coverage(inventory.entries, union_fired)
    union_qualified = {e.qualified for e in union_coverage.fired}

    # The union counts X, Y and Z as fired -- never W, which fired nowhere.
    assert union_qualified == {"plugin:skill-x", "plugin:skill-y", "plugin:skill-z"}

    # Source A's OWN credited-as-fired-here set is X and Z -- never Y, which
    # fired only in B. Source B's own set is Y and Z -- never X.
    fired_a = report.firing_coverage(inventory.entries, fired_by_source[0][1]).fired
    fired_b = report.firing_coverage(inventory.entries, fired_by_source[1][1]).fired
    assert {e.qualified for e in fired_a} == {"plugin:skill-x", "plugin:skill-z"}
    assert {e.qualified for e in fired_b} == {"plugin:skill-y", "plugin:skill-z"}

    # Ruling (p): the per-source DETAIL still names the divergence -- Y fired
    # in B but not A is exactly the gap the PRD's "fired in both places it
    # should" question exists to surface, so it appears in A's own detail
    # (never in A's credited-as-fired-here set, asserted above) and
    # symmetrically for X in B's.
    detail_text = "\n".join(report._render_per_source_firing_detail(inventory, fired_by_source))
    section_a, section_b = detail_text.split("  source-b:")
    assert "plugin:skill-y [skill]" in section_a
    assert "plugin:skill-x [skill]" not in section_a
    assert "plugin:skill-x [skill]" in section_b
    assert "plugin:skill-y [skill]" not in section_b


def test_build_multi_source_report_union_reports_unrecognised_name_not_dropped(tmp_path):
    """spec-019 T3.4 task text: "a record naming something outside the
    inventory is reported as unrecognised rather than dropped" -- exercised
    at the union, which is where unmatched/ambiguous names render (ruling
    (p): pooled on the union figure only, never attributed per source)."""
    shipping_root = tmp_path / "shipping-repo"
    _make_skill(shipping_root, "plugin", "skill-x")
    inventory = report.walk_skill_agent_inventory(shipping_root)

    root_a = tmp_path / "repo-a"
    root_a.mkdir()
    home_a = tmp_path / "home-a"
    home_a.mkdir()
    _write_source_events(root_a, home_a, [_agent_record("Explore")])

    source_a = sources.Source(
        label="source-a", repo_root=root_a, homes=[sources.HomeStatus(home=home_a, state=sources.RECORDING)]
    )

    _, source_records = report.build_multi_source_report(
        [source_a], datetime(2026, 9, 10, tzinfo=timezone.utc)
    )
    fired_by_source = [(source.label, report.fired_names(records)) for source, records in source_records]
    union_fired = report.union_fired_names(fired for _, fired in fired_by_source)
    union_coverage = report.firing_coverage(inventory.entries, union_fired)

    assert union_coverage.unmatched_record_names == ["Explore [agent]"]


def test_build_multi_source_report_hook_timing_installed_only_where_wrapper_was(tmp_path):
    """spec-019 T3.4 task text: hook timing's `installed` is per source, so a
    wrapper installed in one source does not present timing as available for
    the others (ruling (q): hook timing is wired into `_build_source_report`
    itself, never unioned -- ADR-7)."""
    root_a = tmp_path / "repo-a"
    root_a.mkdir()
    home_a = tmp_path / "home-a"
    home_a.mkdir()
    _write_source_events(root_a, home_a, [_hook()])

    root_b = tmp_path / "repo-b"
    root_b.mkdir()
    home_b = tmp_path / "home-b"
    home_b.mkdir()
    _write_source_events(root_b, home_b, [_instruction("b.md", "session_start", repo="repo-b")])

    source_a = sources.Source(
        label="a", repo_root=root_a, homes=[sources.HomeStatus(home=home_a, state=sources.RECORDING)]
    )
    source_b = sources.Source(
        label="b", repo_root=root_b, homes=[sources.HomeStatus(home=home_b, state=sources.RECORDING)]
    )

    text, _ = report.build_multi_source_report(
        [source_a, source_b], datetime(2026, 9, 10, tzinfo=timezone.utc)
    )

    section_a, section_b = text.split("=== b ===")
    assert "Hook durations" in section_a  # wrapper installed here: real durations render
    assert "NOT INSTALLED" in section_b  # no wrapper here: never borrows A's installed state


def test_cli_multi_source_config_denominator_walked_from_shipping_repo_only(tmp_path):
    """spec-019 T3.4 ruling (l): the denominator is walked ONCE, from
    `args.repo_root` -- the shipping repository -- never from any
    `Source.repo_root`, which are targets. A target's own `.claude/agents/`
    entry must therefore never enter the denominator. THIS repository has
    zero repo-local agents today (measured), so a real-repo fixture would
    prove nothing here -- ruling (l) requires a synthetic source root
    carrying one, exercised end-to-end through the real CLI so `main()`'s
    own wiring (not just the pure functions) is what is pinned."""
    shipping_root = tmp_path / "shipping"
    _make_skill(shipping_root, "plugin", "skill-x")
    claude_dir = shipping_root / ".claude"
    claude_dir.mkdir(parents=True)

    target_root = tmp_path / "target-with-local-agent"
    (target_root / ".claude" / "agents").mkdir(parents=True)
    (target_root / ".claude" / "agents" / "local-only.md").write_text(
        "---\nname: local-only\n---\nbody\n", encoding="utf-8"
    )
    target_home = tmp_path / "target-home"
    target_home.mkdir()

    (claude_dir / "observability-sources.toml").write_text(
        f'[[source]]\nlabel = "target"\nrepo_root = "{target_root}"\nhomes = ["{target_home}"]\n',
        encoding="utf-8",
    )

    result = _run_report_cli(["--repo-root", str(shipping_root), "--home", str(tmp_path / "unused-home")])

    assert result.returncode == 0, result.stderr
    assert "local-only" not in result.stdout
    assert "1 entries found (1 skill(s), 0 agent(s))" in result.stdout


def test_cli_multi_source_union_names_a_skill_that_fired_only_in_the_second_source(tmp_path):
    """spec-019 T3.4: `main()`'s union CALL SITE itself, exercised through
    the real CLI -- not `union_fired_names`/`firing_coverage` called
    directly, the way `test_build_multi_source_report_union_and_per_source_firing_coverage`
    does. That test proves the pure functions are correct; it does not prove
    `main()` actually feeds every source's records into them (verified by
    review: `main()`'s union line is uncovered by any test that inspects
    real CLI stdout). Same discipline as
    `test_cli_end_to_end_prints_report_for_fixture_events`, which exists for
    exactly this hazard on `build_load_report`'s own wiring.

    The shipping inventory holds exactly ONE skill, which fires only in the
    SECOND configured source -- so the union's own rendered "Coverage: X/Y
    fired." line is unambiguous evidence main() read past the first source,
    not just that a header string is present (a header-only assertion would
    survive a mutation that unions only `fired_by_source[:1]`)."""
    shipping_root = tmp_path / "shipping"
    _make_skill(shipping_root, "plugin", "skill-only-in-second")
    claude_dir = shipping_root / ".claude"
    claude_dir.mkdir(parents=True)

    source_a_repo = tmp_path / "source-a-repo"
    source_a_repo.mkdir()
    source_a_home = tmp_path / "source-a-home"
    source_a_home.mkdir()
    _write_source_events(
        source_a_repo, source_a_home, [_instruction("a.md", "session_start", repo="source-a-repo")]
    )

    source_b_repo = tmp_path / "source-b-repo"
    source_b_repo.mkdir()
    source_b_home = tmp_path / "source-b-home"
    source_b_home.mkdir()
    _write_source_events(source_b_repo, source_b_home, [_skill_record("plugin:skill-only-in-second")])

    (claude_dir / "observability-sources.toml").write_text(
        f'[[source]]\nlabel = "Source A"\nrepo_root = "{source_a_repo}"\nhomes = ["{source_a_home}"]\n\n'
        f'[[source]]\nlabel = "Source B"\nrepo_root = "{source_b_repo}"\nhomes = ["{source_b_home}"]\n',
        encoding="utf-8",
    )

    result = _run_report_cli(["--repo-root", str(shipping_root), "--home", str(tmp_path / "unused-home")])

    assert result.returncode == 0, result.stderr
    union_start = result.stdout.index("=== Firing coverage: union across all sources")
    union_text = result.stdout[union_start:]
    assert "Coverage: 1/1 fired." in union_text
    assert "Never fired -- unused, not missing (0):" in union_text
