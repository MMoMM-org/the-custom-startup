"""Every SKILL.md body must survive compaction whole (#274).

After a compaction Claude Code re-attaches each invoked skill, but keeps only
its first ~5,000 tokens. A longer skill silently loses its later steps: the
session goes on with step 1-6 and no trace of step 8.

Calibration: in a session that compacted mid-skill, rule-enforcer's rendered
body was cut after 19,778 characters, i.e. ~3.96 characters per token. The
budget below leaves ~2,800 characters of that for the "Base directory" header
and for `$ARGUMENTS`, which is substituted at every occurrence. Detail a late
step needs goes into `reference/`, read at that step.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BODY_BUDGET_BYTES = 17_000

SKILLS = sorted(
    [*ROOT.glob("plugins/*/skills/*/SKILL.md"),
     *ROOT.glob("plugins/tcs-patterns/templates/patterns/*/SKILL.md")]
)


def _body(text: str) -> str:
    """The part Claude Code renders: everything after the YAML frontmatter."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + len("\n---\n"):]
    return text


def test_the_globs_find_the_skills():
    assert len(SKILLS) > 50


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: str(p.relative_to(ROOT)))
def test_skill_body_fits_the_post_compaction_budget(skill):
    size = len(_body(skill.read_text()).encode())
    assert size <= BODY_BUDGET_BYTES, (
        f"{size} bytes > {BODY_BUDGET_BYTES}: move late-step detail into reference/ "
        "and read it at the step that needs it"
    )


def test_body_excludes_the_frontmatter():
    assert _body("---\nname: x\ndescription: y\n---\n## Persona\n") == "## Persona\n"
    assert _body("## No frontmatter\n") == "## No frontmatter\n"
