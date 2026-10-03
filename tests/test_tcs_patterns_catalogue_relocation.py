"""T1.1 (spec-020): the 21 tcs-patterns skills move to templates/patterns/ as pure git-mv renames.

Why this exists: CON-2 (SDD/Constraints) forces tcs-patterns skills out of the plugin's
`skills/` directory entirely, because `skillOverrides` never reaches a plugin-sourced skill --
the resolver returns `"on"` before consulting it. `templates/patterns/` is a catalogue, not a
skills directory `report.py`'s inventory walk can see (it globs `plugins/*/skills/*/SKILL.md`
exactly one level deep, SDD/Building Block View) -- so moving the 21 pattern directories out
from under `skills/` is itself the mechanism that un-registers them from the shipped skill
listing. This file asserts that result directly against the real repository tree, not a
tmp_path fixture, because the thing under test IS the real tree's shape -- a tmp_path copy
would only prove the test fixture moved, not the repository.

T1.3, not this file, repairs the dangling `REFERENCES.md` citations (there is no such file in
this repository; nothing to move). T1.2's `VERSION` files and the frontmatter `name:` rewrite
(a later, install-time phase) are both out of scope here -- this task moves bytes and nothing
else; it must not change any file's content.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "observability"))

import report  # noqa: E402  (sys.path must be extended first)

PATTERNS_PLUGIN = REPO_ROOT / "plugins" / "tcs-patterns"
CATALOGUE_DIR = PATTERNS_PLUGIN / "templates" / "patterns"
OLD_SKILLS_DIR = PATTERNS_PLUGIN / "skills"

# The 21 pattern names, fixed at the pre-move baseline measured 2026-10-03
# (`ls plugins/tcs-patterns/skills/`). A name found in BOTH locations, or in
# NEITHER, is exactly the half-move failure this suite exists to catch.
PATTERN_NAMES = frozenset(
    {
        "api-design",
        "bff-entry-points",
        "ddd",
        "event-driven",
        "event-sourcing",
        "frontend-testing",
        "functional",
        "go-idiomatic",
        "hexagonal",
        "mcp-server",
        "mutation-testing",
        "node-service",
        "observability",
        "obsidian-plugin",
        "python-project",
        "react-testing",
        "secure-oauth-oidc",
        "test-design-reviewer",
        "testing",
        "twelve-factor",
        "typescript-strict",
    }
)


def _tracked_files(path: Path) -> list[str]:
    """Git's own view of what is tracked under `path` -- not a filesystem walk, so an
    accidentally-untracked stray file cannot inflate a passing count."""
    result = subprocess.run(
        ["git", "ls-files", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_catalogue_holds_exactly_the_21_pattern_directories() -> None:
    """templates/patterns/ exists and holds exactly the 21 moved directories -- no more, no fewer."""
    assert CATALOGUE_DIR.is_dir(), f"{CATALOGUE_DIR} does not exist yet -- the patterns have not moved"
    found = {p.name for p in CATALOGUE_DIR.iterdir() if p.is_dir()}
    assert found == PATTERN_NAMES


def test_catalogue_holds_21_skill_md_and_80_tracked_files_total() -> None:
    """`report.py` globs `skills/*/SKILL.md` one level deep and cannot see a catalogue
    directory at all (SDD/Building Block View) -- so the only way to confirm the move landed
    intact is to assert directly against the tree, never through the report."""
    skill_mds = sorted(CATALOGUE_DIR.glob("*/SKILL.md"))
    assert len(skill_mds) == 21
    assert {p.parent.name for p in skill_mds} == PATTERN_NAMES

    tracked = _tracked_files(CATALOGUE_DIR)
    assert len(tracked) == 80


def test_old_skills_location_has_no_pattern_left() -> None:
    """Every one of the 21 names must be gone from skills/ -- a name left behind there is a
    half-move, not a move."""
    remaining = {p.name for p in OLD_SKILLS_DIR.iterdir() if p.is_dir()} if OLD_SKILLS_DIR.is_dir() else set()
    assert not (remaining & PATTERN_NAMES)


def test_git_recognizes_all_80_files_as_pure_renames() -> None:
    """`git mv` must produce a 100%-similarity rename for every file -- not a delete+add pair,
    which would sever `git log --follow` (PRD/F1 4th)."""
    result = subprocess.run(
        ["git", "diff", "--name-status", "-M", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    pattern_renames = [
        line
        for line in result.stdout.splitlines()
        if line.startswith("R100\t")
        and "/tcs-patterns/skills/" in line
        and "/tcs-patterns/templates/patterns/" in line
    ]
    assert len(pattern_renames) == 80


def test_all_21_frontmatter_blocks_still_parse_as_yaml() -> None:
    """Not paranoia: ten skill descriptions in this repository once stopped parsing while
    `claude plugin validate` passed over all ten. Reads from `templates/patterns/` -- the NEW
    location -- deliberately: an assertion against the old `skills/` path would pass before the
    move too, making the RED step fake (tdd-guardian's gate on this task's plan)."""
    skill_mds = sorted(CATALOGUE_DIR.glob("*/SKILL.md"))
    assert len(skill_mds) == 21, "catalogue must hold all 21 SKILL.md files before frontmatter can be checked"

    for skill_md in skill_mds:
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill_md} has no opening frontmatter delimiter"
        end = text.index("\n---", 4)
        frontmatter = yaml.safe_load(text[4:end])
        assert isinstance(frontmatter, dict), f"{skill_md} frontmatter did not parse to a mapping"
        assert "name" in frontmatter


def test_inventory_drops_from_98_to_77_with_no_tcs_patterns_skill_left() -> None:
    """The pre-move baseline (measured 2026-10-03) is 98 entries (80 skills, 18 agents). After
    the move it must read 77 (59 skills, 18 agents) -- agents untouched, exactly 21 fewer
    skills, and none of the remaining skills still qualified `tcs-patterns:`."""
    inventory = report.walk_skill_agent_inventory(REPO_ROOT)
    assert inventory.skill_count == 59
    assert inventory.agent_count == 18
    assert len(inventory.entries) == 77

    tcs_patterns_skills = [
        entry.qualified for entry in inventory.entries if entry.kind == "skill" and entry.qualified.startswith("tcs-patterns:")
    ]
    assert tcs_patterns_skills == []


def test_unreachable_list_stays_empty() -> None:
    """A regression guard, not evidence the move worked: this list was already empty before the
    move (verified 2026-10-03), so a hit here means something else broke -- not that the
    catalogue relocation succeeded. A criterion whose value is identical before and after cannot
    distinguish success from doing nothing (this task's plan, step 2)."""
    inventory = report.walk_skill_agent_inventory(REPO_ROOT)
    assert inventory.unreachable == ()
