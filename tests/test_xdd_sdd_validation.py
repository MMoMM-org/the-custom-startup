"""Lockstep: xdd-sdd's validation must catch new units the Building Block
View omits, because the xdd classifier counts components from the view
alone (#161, #223)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD_SKILL_DIR = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd-sdd"
CLASSIFIER = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd" / "reference" / "classifier.md"


def test_validation_checklist_requires_every_new_unit_in_the_view():
    text = (SDD_SKILL_DIR / "validation.md").read_text(encoding="utf-8")
    assert "No surface outside the Building Block View" in text


def test_validate_step_names_the_surface_check():
    text = (SDD_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    step = text[text.index("### 5. Validate Design") :]
    assert "Surface outside the view" in step


def test_the_granularity_the_checklist_cites_still_exists():
    """validation.md points at this heading; renaming it would leave the
    checklist citing nothing."""
    assert "What counts as a component" in CLASSIFIER.read_text(encoding="utf-8")
