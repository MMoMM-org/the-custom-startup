"""implement-direct must dispatch and escalate by the model ladder, by reference.

Why this exists: the skill is Markdown applied by an agent. The ladder
(`xdd/reference/model-ladder.md`) is the single source for rungs, the starting
table, the cap, consent and the fable-failure rule; the skill links it and must
not restate it. Assertions slice steps 3b and 3c so each checks its own step.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "implement-direct" / "SKILL.md"
LADDER = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd" / "reference" / "model-ladder.md"
LINK = "../xdd/reference/model-ladder.md"


def _step(heading: str) -> str:
    text = SKILL.read_text()
    m = re.search(rf"^#### {re.escape(heading)}.*?(?=^#{{1,4}} )", text, re.S | re.M)
    assert m, heading
    return m.group(0)


def test_linked_ladder_exists():
    assert (SKILL.parent / LINK).resolve() == LADDER
    assert LADDER.is_file()


def test_3b_links_ladder_and_reads_model_tier():
    s = _step("3b")
    assert LINK in s
    assert "model_tier" in s
    assert "Direct column" in s


def test_3b_dispatch_details():
    s = _step("3b")
    assert "alias" in s
    assert "no `model` parameter" in s
    assert "effort: max" in s
    assert "served" in s.lower()
    assert "[model:" not in s.replace("no `[model:]` tag", "")


def test_3b_does_not_restate_the_mapping_table():
    s = _step("3b")
    assert "| `routine`" not in s
    assert not re.search(r"routine\s*(→|->|=)\s*sonnet", s)
    assert not re.search(r"frontier\s*(→|->|=)\s*fable", s)


def _escalation_paragraph() -> str:
    m = re.search(r"^\*\*Complexity escalation\*\*.*?(?=\n\s*\n|\Z)", _step("3c"), re.S | re.M)
    assert m
    return m.group(0)


def test_3c_complexity_escalates_one_rung_by_reference():
    s = _step("3c")
    assert "stronger model" not in s
    p = _escalation_paragraph()
    assert LINK in p
    for phrase in ("one rung up", "consent and nobody-to-ask rules", "fable-failure rule"):
        assert phrase in p
    assert "the cap" in p.lower()


def test_3c_logs_through_xdd_meta():
    p = _escalation_paragraph()
    assert "Skill(tcs-workflow:xdd-meta)" in p
    assert "Log Decision" in p
    assert "in the ladder's row formats" in p
    for what in ("escalation", "consent", "substitution"):
        assert what in p.lower()


def test_3b_logs_substitution_through_xdd_meta():
    s = _step("3b")
    assert "Skill(tcs-workflow:xdd-meta)" in s
    assert "Log Decision" in s
    assert "substitution" in s.lower()


def test_step_1_names_model_tier_and_absent_rule():
    text = SKILL.read_text()
    m = re.search(r"^### 1\. .*?(?=^### )", text, re.S | re.M)
    assert m
    s = m.group(0)
    assert "model_tier" in s
    assert "--read" in s
    assert "absent" in s
    assert "empty" in s


def test_3c_has_no_review_failure_trigger():
    s = _step("3c")
    assert "FAIL" not in s
    assert "twice" not in s.lower()
    assert "two in a row" not in s.lower()


def test_3c_other_blocked_reasons_keep_handling():
    s = _step("3c")
    for kept in ("more context", "split it", "escalate to the user"):
        assert kept in s


def test_skill_does_not_restate_ladder_content():
    text = SKILL.read_text()
    assert "2.5×" not in text
    assert "Fable costs" not in text
    assert not re.search(r"haiku\W+sonnet\W+opus", text)


def test_3b_routes_a_failed_fable_dispatch_to_the_fable_failure_rule():
    # Walkthrough finding (spec 022 T4.2): the rule was named only in the
    # complexity-escalation paragraph of 3c, but a planned fable dispatch fails at 3b.
    s = _step("3b")
    assert "Fable Failure" in s
