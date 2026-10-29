"""The xdd-plan `[model: tier]` task tag must be documented wherever tasks are described.

Why this exists: spec 022 (ADR-4) lets a `[model:]` tag on a plan task override
the spec's model tier for that one task. An implementer or orchestrator only
honours the tag if the plan's own documents name it: the metadata table the
task-structure reference gives, the Task interface in the skill, and the
Metadata Reference in the manifest template. Each test slices to its own
section so a mention elsewhere in the file cannot satisfy it.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
XDD_PLAN_DIR = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd-plan"
TASK_STRUCTURE = XDD_PLAN_DIR / "reference" / "task-structure.md"
SKILL = XDD_PLAN_DIR / "SKILL.md"
TEMPLATE = XDD_PLAN_DIR / "template.md"

MODEL_TAG = "[model: routine|hard|frontier]"


def _section(text, start_marker, end_marker=None):
    """Return the text from start_marker up to (not including) end_marker."""
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start + len(start_marker))
    return text[start:end]


def test_task_structure_metadata_lists_model_tag():
    text = TASK_STRUCTURE.read_text(encoding="utf-8")
    table = _section(text, "| Metadata | Description |", "\n---")
    rows = [line for line in table.splitlines() if line.startswith("| `[model:")]

    assert len(rows) == 1, "the Metadata table needs exactly one [model:] row"
    row = rows[0]
    assert MODEL_TAG in row
    assert "override" in row.lower()
    assert "spec" in row.lower()


def test_xdd_plan_task_interface_has_model():
    text = SKILL.read_text(encoding="utf-8")
    interface = _section(text, "Task {", "}")

    assert (
        "  model?: routine | hard | frontier   // overrides the spec's model tier for this task"
        in interface
    )


def test_plan_template_metadata_reference_lists_model_tag():
    text = TEMPLATE.read_text(encoding="utf-8")
    reference = _section(text, "## Metadata Reference", "### Success Criteria")

    assert (
        "- `[model: routine|hard|frontier]` - Overrides the spec's model tier for this task"
        in reference
    )
