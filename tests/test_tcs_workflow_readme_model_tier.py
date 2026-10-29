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


CHANGELOG = (ROOT / "plugins/tcs-workflow/CHANGELOG.md").read_text()


def _changelog_entry() -> str:
    match = re.search(r"^## \[4\.4\.16\][^\n]*\n(.*?)(?=^## \[)", CHANGELOG, re.S | re.M)
    assert match, "plugin CHANGELOG has no 4.4.16 entry"
    return match.group(1)


def _sentences(text: str):
    return re.split(r"(?<=[.!?])\s+", " ".join(text.split()))


def test_review_counter_is_attributed_to_implement_incremental_only():
    for text in (_section(), _changelog_entry()):
        counted = [s for s in _sentences(text) if "review" in s.lower() and "count" in s.lower()]
        assert counted, "no sentence says review failures are counted"
        for sentence in counted:
            assert "implement-incremental" in sentence
            assert "implement-direct" not in sentence


def test_no_review_loop_claim_names_implement_direct():
    for text in (_section(), _changelog_entry()):
        for sentence in _sentences(text):
            if "review loop" in sentence.lower():
                assert "implement-direct" not in sentence


def test_nobody_can_be_asked_is_scoped_to_escalation():
    section = _section()
    sentences = [s for s in _sentences(section) if "nobody can be asked" in s.lower()]
    assert sentences, "section does not mention nobody can be asked"
    for sentence in sentences:
        assert "escalat" in sentence.lower()
        assert "opus@max" not in sentence


def test_section_does_not_restate_escalation_mechanics():
    section = _section()
    assert "twice in a row" not in section
    assert "model-ladder.md#escalation" in section
    assert "model-ladder.md#consent" in section
