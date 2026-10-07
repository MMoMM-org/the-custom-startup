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

Rename purity (PRD/F1 4th -- every file a 100%-similarity rename, not a delete+add pair that
would sever `git log --follow`) is NOT asserted below as a standing test. It was verified once,
at migration time, and cannot be re-asserted from a clean checkout: `git diff --name-status -M
HEAD` compares the working tree against HEAD, which is empty on any tree with nothing pending --
true the instant the move was made and uncommitted, false one commit later, and false forever
after on a fresh clone or in CI, since there is no state a committed tree can be in where a
pending rename exists to see. The branch this shipped on is squash-merged, so pinning the
assertion to a parent commit or SHA does not survive either. Verified directly instead, and
recorded here because the evidence does not survive as a runnable assertion:
commit 2a5f192 ("refactor(tcs-patterns): relocate 21 pattern skills to templates/patterns
catalogue") shows `git diff --name-status -M HEAD~1 HEAD` reporting all 80 moved files as
`R100`, and `git diff --cached --stat -M` at the time of that commit reported
"80 files changed, 0 insertions(+), 0 deletions(-)" -- zero content changed across every one of
them.

Migration evidence, not invariants (measured 2026-10-03, pre-move baseline immediately before
commit 2a5f192, vs. the post-move reading taken right after it): `report.py`'s inventory read 98
entries (80 skills, 18 agents), 21 of the 80 skills qualified `tcs-patterns:`; after the move it
read 77 entries (59 skills, 18 agents unchanged) and the catalogue held 80 tracked files (21
`SKILL.md` + their sibling reference/asset files). None of these absolute figures are asserted
below as standing invariants, because later tasks legitimately change them: T1.2 writes a
`VERSION` file into each of the 21 catalogue directories (80 tracked files becomes 101), and
Phase 5 adds two new skills -- `patterns-setup` and `pattern` -- under
`plugins/tcs-patterns/skills/` (skill_count, entries and the tcs-patterns-qualified set all grow
again, for names outside `PATTERN_NAMES`). The invariants that survive both are: the catalogue
holds exactly the 21 named directories with a parseable `SKILL.md` each, none of those 21 names
is reachable as a skill under any `plugins/*/skills/` path, and the inventory's unreachable list
stays empty.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "observability"))

import report  # noqa: E402  (sys.path must be extended first)
from visible_dirs import visible_dir_names, visible_dirs

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
    found = visible_dir_names(CATALOGUE_DIR)
    assert found == PATTERN_NAMES


def test_catalogue_holds_21_skill_md_each_tracked_by_git() -> None:
    """`report.py` globs `skills/*/SKILL.md` one level deep and cannot see a catalogue
    directory at all (SDD/Building Block View) -- so the only way to confirm the move landed
    intact is to assert directly against the tree, never through the report.

    Checks presence AND that git actually tracks each `SKILL.md` -- a filesystem walk alone
    could pass against an untracked stray copy. Does not assert a total tracked-file count:
    T1.2 adds a `VERSION` file to every one of these 21 directories, which would otherwise
    break this test for reasons unrelated to the relocation regressing."""
    skill_mds = sorted(CATALOGUE_DIR.glob("*/SKILL.md"))
    assert len(skill_mds) == 21
    assert {p.parent.name for p in skill_mds} == PATTERN_NAMES

    for name in sorted(PATTERN_NAMES):
        tracked_here = _tracked_files(CATALOGUE_DIR / name)
        assert any(f.endswith("SKILL.md") for f in tracked_here), f"{name}'s SKILL.md is not tracked by git"


def test_old_skills_location_has_no_pattern_left() -> None:
    """Every one of the 21 names must be gone from skills/ -- a name left behind there is a
    half-move, not a move."""
    remaining = visible_dir_names(OLD_SKILLS_DIR) if OLD_SKILLS_DIR.is_dir() else set()
    assert not (remaining & PATTERN_NAMES)


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


def test_no_pattern_skill_reachable_in_inventory() -> None:
    """None of the 21 moved names is reachable as a skill, by its fully-qualified
    `tcs-patterns:<name>` form, through `report.py`'s inventory walk.

    Scoped to `PATTERN_NAMES` rather than a blanket "no skill qualifies tcs-patterns:" check
    (follows `test_old_skills_location_has_no_pattern_left`'s shape) because Phase 5
    deliberately adds two new skills under `plugins/tcs-patterns/skills/` --
    `patterns-setup` and `pattern`, neither a pattern name -- which the inventory is meant to
    keep seeing."""
    inventory = report.walk_skill_agent_inventory(REPO_ROOT)
    pattern_qualified_names = {f"tcs-patterns:{name}" for name in PATTERN_NAMES}

    reachable_pattern_skills = {
        entry.qualified for entry in inventory.entries if entry.kind == "skill" and entry.qualified in pattern_qualified_names
    }
    assert reachable_pattern_skills == set()


def test_unreachable_list_stays_empty() -> None:
    """A regression guard, not evidence the move worked: this list was already empty before the
    move (verified 2026-10-03), so a hit here means something else broke -- not that the
    catalogue relocation succeeded. A criterion whose value is identical before and after cannot
    distinguish success from doing nothing (this task's plan, step 2)."""
    inventory = report.walk_skill_agent_inventory(REPO_ROOT)
    assert inventory.unreachable == ()
