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

REPORT_PY = REPO_ROOT / "scripts" / "observability" / "report.py"
LOGWRITE_SH = REPO_ROOT / "plugins" / "tcs-helper" / "scripts" / "observability" / "logwrite.sh"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


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
) -> dict:
    record = {
        "ts": ts,
        "kind": "instruction",
        "session": session,
        "repo": "the-custom-startup",
        "path": path,
        "scope": "Project",
        "reason": reason,
    }
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
        ],
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    result = _run_report_cli(
        ["--events", str(events), "--repo-root", str(repo_root), "--home", str(home_dir)]
    )

    assert result.returncode == 0, result.stderr
    assert "docs/ai/memory/active.md: 2 load(s)" in result.stdout
    assert "session_start=2" in result.stdout
    assert "Configured but never loaded (0):" in result.stdout

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


# --- fired_names: the numerator, empty values counted as unknown -----------


def test_fired_names_collects_skill_and_agent_values():
    records = [_skill_record("tcs-patterns:observability"), _agent_record("Explore")]
    assert report.fired_names(records) == {"tcs-patterns:observability", "Explore"}


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
    coverage = report.firing_coverage(entries, {"tcs-team:the-tester:test-strategy"})
    assert coverage.fired == entries
    assert coverage.unused == []


def test_firing_coverage_record_with_bare_name_matches():
    entries = [report.InventoryEntry(qualified="tcs-team:the-tester:test-strategy", bare="test-strategy", kind="agent")]
    coverage = report.firing_coverage(entries, {"test-strategy"})
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
    coverage = report.firing_coverage([a, b], {"testing"})

    assert coverage.fired == []
    assert set(coverage.unused) == {a, b}
    assert "testing" in coverage.ambiguous_record_names


def test_firing_coverage_qualified_name_disambiguates_collision():
    """The same collision as above, but the record carries the qualified
    name -- exactly one of the two entries must be marked fired."""
    a = report.InventoryEntry(qualified="plugin-a:testing", bare="testing", kind="skill")
    b = report.InventoryEntry(qualified="plugin-b:testing", bare="testing", kind="skill")
    coverage = report.firing_coverage([a, b], {"plugin-a:testing"})

    assert coverage.fired == [a]
    assert coverage.unused == [b]


def test_firing_coverage_record_naming_absent_entry_is_reported_not_dropped():
    entries = [report.InventoryEntry(qualified="tcs-patterns:observability", bare="observability", kind="skill")]
    coverage = report.firing_coverage(entries, {"Explore"})

    assert coverage.unused == entries
    assert coverage.unmatched_record_names == ["Explore"]


def test_firing_coverage_is_a_fraction():
    entries = [
        report.InventoryEntry(qualified="a:x", bare="x", kind="skill"),
        report.InventoryEntry(qualified="a:y", bare="y", kind="skill"),
        report.InventoryEntry(qualified="a:z", bare="z", kind="skill"),
    ]
    coverage = report.firing_coverage(entries, {"a:x"})

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
    coverage = report.firing_coverage(inventory.entries, {"tcs-patterns:observability"})

    text = report.build_load_report({}, [], skill_agent_inventory=inventory, firing=coverage)

    assert "1/1" in text


def test_build_load_report_without_skill_agent_inventory_omits_section():
    """Pre-existing callers/tests that never pass skill_agent_inventory=/
    firing= must keep working unchanged -- same posture as byte_stats=/
    recording= in T3.2."""
    text = report.build_load_report({}, [])
    assert "never fired" not in text.lower()


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
