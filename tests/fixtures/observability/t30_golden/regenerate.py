#!/usr/bin/env python3
"""spec-019 T3.0 -- regenerate/verify the golden fixture for report.py's
`--events` rendering path, captured against commit eb9b529
(scripts/observability/report.py untouched since that commit -- see
docs/XDD/specs/019-observability-rollout-across-active-repos/plan/phase-3.md,
task "spec-019 T3.0").

Why this fixture exists: SDD-AC-24 requires `--events <path>`'s behaviour to
stay unchanged from spec-018 once spec-019 Phase 3 (spec-019 T3.1, T3.3, T3.4)
starts rewriting report.py's reader and rendering. A golden fixture captured
AFTER those changes would only prove the new code agrees with itself -- so
this was captured first, against the UNMODIFIED reader, and this script (and
golden_report.txt) must never be touched by any later spec-019 task; spec-019
T3.5 diffs its own output against `golden_report.txt` in this directory.

Binding ruling (spec-019 T3.0 team-lead brief, R4) -- the "confirmed"
recording-state branch can never be pinned here: `_render_recording_status`'s
fourth branch ("recording (confirmed by the last selfcheck round-trip)")
requires the newest record's `ts` to be within STALE_THRESHOLD_SECONDS (6h)
of wall-clock `now` AT REPORT TIME, and time only moves forward -- whatever
renders "confirmed" today renders "STALE" tomorrow. This fixture's
`kind: state` record deliberately exercises the STALE branch instead
(enabled="1", but every `ts` below is already dated 2026-09-06/07 relative to
the day this was captured, permanently in the past): STALE, like UNKNOWN and
NOT RECORDING, is stable forever once the newest `ts` is already old. Do NOT
"fix" a stale-looking fixture by moving its timestamps closer to now -- that
reintroduces exactly the rot this comment exists to prevent.

Binding ruling (R6) -- the synthetic repo root is built under a fresh
`tempfile.TemporaryDirectory()`, deliberately NOT committed as a literal
subtree of THIS repository, for two reasons found the hard way while
authoring this fixture:

  1. `walk_instruction_inventory` must report `git_filtered=False` (the
     "unfiltered -- git unavailable or repo_root is not a git repository"
     wording) deterministically. A first attempt committed the synthetic
     tree under this directory -- and because it is still a SUBDIRECTORY of
     this repository's own git worktree, `git check-ignore` happily answered
     against THIS repo's `.gitignore` instead of failing closed: the root
     `.gitignore`'s bare `.claude/` rule silently swallowed
     `.claude/rules/*.md` two levels down inside the fixture, corrupting the
     captured inventory count without touching report.py at all. Building
     under `tempfile.TemporaryDirectory()` (outside any git worktree, per
     `tempfile`'s platform default) is what actually makes `git
     check-ignore` fail with "not a git repository" and `git_filtered=False`
     render, deterministically, instead of just usually.
  2. It avoids committing dozens of tiny synthetic fixture files -- the
     builder function below is the input specification, committed as code;
     `python3 regenerate.py` (no flags) rebuilds byte-identical input from it
     every time, which is also how this satisfies "the input that produced
     it is committed."

Trade-off: this fixture does not pin the gitignore-filtered branch of the
instruction-inventory walk -- a different concern from what spec-019 T3.0
exists to lock down (SDD-AC-24 is about `--events` behaviour as a whole, not
about exercising every walk branch).

Usage:
    python3 regenerate.py            Rebuild input/ from scratch, capture
                                      report.py's stdout against it, and diff
                                      against the committed golden_report.txt
                                      (exit 1 on any mismatch). This is what
                                      spec-019 T3.5 -- and this fixture's own
                                      pytest test -- runs.
    python3 regenerate.py --write    Write golden_report.txt with the freshly
                                      captured output. Only works when the
                                      file does not exist yet (the one-time
                                      initial capture) -- refuses otherwise,
                                      structurally, not just by convention:
                                      see --force below.
    python3 regenerate.py --write --force
                                      OVERWRITE an existing golden_report.txt.
                                      Never run this to "fix" a mismatch -- a
                                      mismatch after spec-019 T3.1/T3.3/T3.4
                                      land means the reader's `--events`
                                      behaviour changed, which is exactly what
                                      SDD-AC-24 forbids. `--write` alone
                                      refusing when the file already exists is
                                      the structural guard against exactly
                                      that: the first task to hit a red test
                                      here and reach for `--write` gets
                                      stopped, in code, not just by a comment.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN_PATH = HERE / "golden_report.txt"
REPORT_PY = HERE.parents[3] / "scripts" / "observability" / "report.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_input(base: Path) -> None:
    """Deterministically build a fresh input tree under `base` (a directory
    that must not already exist as a git worktree -- see the module
    docstring's R6 ruling on why `base` is always a fresh
    `tempfile.TemporaryDirectory()`, never a path under this repository).

    Every section of build_load_report must render non-empty (spec-019 T3.0
    team-lead brief, R5), so each fixture element below is labelled with the
    report section and sub-case it exists to exercise.
    """
    repo = base / "repo"
    home = base / "home"
    home.mkdir(parents=True)  # walked but left empty -- no home-side inventory entry needed here

    # --- instruction inventory: 6 configured files, 4 loaded (one per layer
    # label: always / conditional / always+conditional / unknown), 2 never
    # loaded -- see the matching `kind: instruction` records below. ---------
    _write(
        repo / "CLAUDE.md",
        "# Fixture root CLAUDE.md\n\n"
        "Loaded under both an always-loaded and a conditional reason below "
        "(layer: always+conditional).\n",
    )
    _write(
        repo / "nested" / "CLAUDE.md",
        "# Fixture nested CLAUDE.md\n\n"
        "Never loaded -- one of the two \"Configured but never loaded\" entries.\n",
    )
    _write(
        repo / "docs" / "ai" / "memory" / "general.md",
        "# Fixture memory file\n\nLoaded once, conditionally (layer: conditional).\n",
    )
    _write(
        repo / "docs" / "ai" / "memory" / "context.md",
        "# Fixture memory file\n\n"
        "Never loaded -- the other \"Configured but never loaded\" entry.\n",
    )
    _write(
        repo / ".claude" / "rules" / "style.md",
        "# Fixture rule file\n\nLoaded once under an empty reason (layer: unknown).\n",
    )
    _write(
        repo / ".claude" / "rules" / "other.md",
        "# Fixture rule file\n\nLoaded once, always (layer: always).\n",
    )

    # --- skill/agent inventory: 4 discoverable entries (2 fire, 2 stay
    # unused), plus 1 nested SKILL.md the harness can never discover
    # (unreachable) -- see FiringCoverage/SkillAgentInventory in report.py. -
    _write(repo / "plugins" / "pluginA" / "skills" / "alpha" / "SKILL.md", "# alpha\n\nFires.\n")
    _write(
        repo / "plugins" / "pluginA" / "skills" / "beta" / "SKILL.md",
        "# beta\n\nNever fires -- stays in \"Never fired -- unused, not missing.\"\n",
    )
    _write(
        repo / "plugins" / "pluginA" / "skills" / "nested" / "inner" / "SKILL.md",
        "# inner\n\nTwo levels deep under skills/ -- unreachable, per SDD/The two "
        "inventories' third amendment; the harness only ever looks at "
        "skills/<name>/SKILL.md.\n",
    )
    _write(
        repo / "plugins" / "pluginA" / "agents" / "helper.md",
        "---\nname: helper\ndescription: fixture agent that fires\n---\nbody\n",
    )
    _write(
        repo / "plugins" / "pluginA" / "agents" / "unused-agent.md",
        "---\nname: unused-agent\ndescription: fixture agent that never fires\n---\nbody\n",
    )

    # --- the record itself. All `ts` values are dated 2026-09-06/07 --
    # already in the past relative to this fixture's capture day, and only
    # ever get further in the past -- see the STALE-branch note above. -----
    lines = [
        # kind: instruction -- CLAUDE.md, layer always+conditional; bytes
        # measurable (500) under an always-loaded reason.
        '{"ts":"2026-09-06T16:43:28Z","kind":"instruction","session":"s1","repo":"fixture-repo",'
        '"path":"CLAUDE.md","scope":"Project","reason":"session_start","bytes":"500"}',
        # kind: instruction -- CLAUDE.md again, conditional reason, `bytes`
        # ABSENT -- the byte-accounting "unmeasurable" case (R5).
        '{"ts":"2026-09-06T16:43:29Z","kind":"instruction","session":"s1","repo":"fixture-repo",'
        '"path":"CLAUDE.md","scope":"Project","reason":"path_glob_match"}',
        # kind: instruction -- general.md, pure conditional layer, bytes
        # measurable (200).
        '{"ts":"2026-09-06T16:43:30Z","kind":"instruction","session":"s1","repo":"fixture-repo",'
        '"path":"docs/ai/memory/general.md","scope":"Project","reason":"nested_traversal","bytes":"200"}',
        # kind: instruction -- style.md, empty reason (spec-018 T2.1's "unknown"),
        # bytes measurable (999) -- the "measurable value under an unknown
        # reason" case (R5), lands in unknown_reason_bytes.
        '{"ts":"2026-09-06T16:43:31Z","kind":"instruction","session":"s1","repo":"fixture-repo",'
        '"path":".claude/rules/style.md","scope":"Project","reason":"","bytes":"999"}',
        # kind: instruction -- other.md, pure always layer, bytes measurable (50).
        '{"ts":"2026-09-06T16:43:32Z","kind":"instruction","session":"s1","repo":"fixture-repo",'
        '"path":".claude/rules/other.md","scope":"Project","reason":"compact","bytes":"50"}',
        # kind: state -- enabled=1, but every ts in this log is already old
        # relative to any real wall clock at report time -> renders STALE,
        # never "confirmed" (see the module docstring's binding ruling).
        '{"ts":"2026-09-07T09:00:00Z","kind":"state","session":"s1","repo":"fixture-repo",'
        '"enabled":"1","detail":"0","note":"selfcheck probe (fixture)"}',
        # kind: skill -- fires plugins/pluginA/skills/alpha via its qualified name.
        '{"ts":"2026-09-07T09:05:00Z","kind":"skill","session":"s1","repo":"fixture-repo",'
        '"skill":"pluginA:alpha"}',
        # kind: agent -- fires plugins/pluginA/agents/helper.md via its
        # (unique) bare frontmatter name.
        '{"ts":"2026-09-07T09:06:00Z","kind":"agent","session":"s1","repo":"fixture-repo",'
        '"agent_type":"helper","agent_id":"1"}',
        # kind: agent -- names a built-in agent absent from this inventory
        # entirely -- the "unmatched_record_names" case (R5).
        '{"ts":"2026-09-07T09:07:00Z","kind":"agent","session":"s1","repo":"fixture-repo",'
        '"agent_type":"Explore","agent_id":"2"}',
        # kind: hook -- scope_note: single -- the one per-hook duration entry.
        '{"ts":"2026-09-07T09:08:00Z","kind":"hook","session":"s1","repo":"fixture-repo",'
        '"hook_event":"PreToolUse","matcher":"Skill","ms":"120","exit":"0","scope_note":"single"}',
        # kind: hook -- scope_note: batch -- excluded from per-hook durations,
        # counted in batch_count (ADR-7).
        '{"ts":"2026-09-07T09:09:00Z","kind":"hook","session":"s1","repo":"fixture-repo",'
        '"hook_event":"PreToolUse","matcher":"Skill","ms":"999","exit":"0","scope_note":"batch"}',
        # kind: hook -- no scope_note key at all -- counted in unscoped_count.
        '{"ts":"2026-09-07T09:10:00Z","kind":"hook","session":"s1","repo":"fixture-repo",'
        '"hook_event":"SessionStart","matcher":"","ms":"50","exit":"0"}',
        # Malformed line -- exercises read_events' unparseable-line count.
        '{"not valid json -- exercises the unparseable-line count (read_events)',
    ]
    _write(base / "events.jsonl", "\n".join(lines) + "\n")


def capture(base: Path) -> str:
    """Run the real CLI (report.py's own __main__/argparse path, not an
    imported function call) against `base`, mirroring
    tests/test_observability_report.py's `_run_report_cli` convention.
    """
    result = subprocess.run(
        [
            sys.executable, str(REPORT_PY),
            "--events", str(base / "events.jsonl"),
            "--repo-root", str(base / "repo"),
            "--home", str(base / "home"),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, f"report.py exited {result.returncode}: {result.stderr}"
    return result.stdout


def build_and_capture() -> str:
    """Build a fresh synthetic tree under a new temp directory and capture
    report.py's stdout against it -- the one entry point both `main()` below
    and the golden fixture's pytest test call, so there is exactly one code
    path that can ever produce "the captured output."
    """
    with tempfile.TemporaryDirectory(prefix="spec019-t30-golden-") as tmp:
        base = Path(tmp)
        build_input(base)
        return capture(base)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write golden_report.txt")
    parser.add_argument(
        "--force", action="store_true",
        help="required alongside --write when golden_report.txt already exists",
    )
    args = parser.parse_args()

    captured = build_and_capture()

    if args.write:
        if GOLDEN_PATH.is_file() and not args.force:
            print(
                f"REFUSING to overwrite {GOLDEN_PATH}: it already exists.\n"
                "This golden fixture is frozen against commit eb9b529 to prove SDD-AC-24 -- "
                "that report.py's --events output has not changed since spec-018. A mismatch "
                "here means report.py's --events output DID change; regenerating the golden to "
                "make a red test pass destroys the only evidence of that change.\n"
                "Run with no flags first to see the diff. If the change is genuinely intentional "
                "and reviewed, re-run with --write --force.",
                file=sys.stderr,
            )
            return 1
        if GOLDEN_PATH.is_file():
            print(f"WARNING: --force given -- overwriting existing {GOLDEN_PATH}", file=sys.stderr)
        _write(GOLDEN_PATH, captured)
        print(f"wrote {GOLDEN_PATH} ({len(captured)} bytes)")
        return 0

    if not GOLDEN_PATH.is_file():
        print(f"{GOLDEN_PATH} does not exist -- run with --write first", file=sys.stderr)
        return 1
    existing = GOLDEN_PATH.read_text(encoding="utf-8")
    if captured != existing:
        print("MISMATCH -- captured output no longer matches golden_report.txt", file=sys.stderr)
        return 1
    print("OK: reproduces byte-identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
