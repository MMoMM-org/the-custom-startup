"""The tcs-workflow README documents model tiers and points at the ladder (#158)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "plugins/tcs-workflow/README.md").read_text()


def _section() -> str:
    match = re.search(r"^## Model Tiers\n(.*?)(?=^## )", README, re.S | re.M)
    assert match, "README has no '## Model Tiers' section"
    return match.group(1)


def test_section_names_the_three_tiers():
    section = _section()
    for tier in ("routine", "hard", "frontier"):
        assert f"`{tier}`" in section


def test_section_links_the_ladder_instead_of_copying_it():
    section = _section()
    assert "skills/xdd/reference/model-ladder.md" in section
    assert "2.5×" not in section
    assert "| `haiku` |" not in section


def test_section_states_the_requirements_and_overrides():
    section = _section()
    assert "2.1.292" in section
    assert "CLAUDE_CODE_EFFORT_LEVEL" in section


def test_section_states_consent_and_unverified_paths():
    section = _section()
    assert "consent" in section
    assert "usage credits" in section
    assert "#242" in section


def test_section_states_bounded_review_loop_and_served_model():
    section = _section().lower()
    assert "bounded" in section
    assert "subagent transcript" in section
    assert "served" in section
