"""implement-incremental must dispatch and escalate by the model ladder.

Why this exists: the loop is Markdown an agent applies, so a test cannot run it.
These assertions slice SKILL.md by `####` step heading and pin what each step
must say, so an edit that drops a rule, restates the ladder (a second source of
truth) or revives the stale YOLO reference fails here. The ladder itself is
pinned in test_model_ladder.py.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "implement-incremental" / "SKILL.md"
LADDER_LINK = "../xdd/reference/model-ladder.md"
COST_FRAGMENT = "2.5×"


def _text():
    return SKILL.read_text(encoding="utf-8")


def _step(letter):
    match = re.search(
        rf"^#### 4{letter}\. .*?(?=^#### 4|^---$)", _text(), re.MULTILINE | re.DOTALL
    )
    assert match, f"step 4{letter} not found"
    return match.group(0)


def _yolo():
    match = re.search(r"^YOLO mode.*?(?=^### )", _text(), re.MULTILINE | re.DOTALL)
    assert match, "YOLO block not found"
    return match.group(0)


def test_4b_links_the_ladder_and_reads_tier_and_tag():
    step = _step("b")
    assert LADDER_LINK in step
    assert "`[model:" in step
    assert "model_tier" in step
    assert "Starting Rung" in step


def test_4b_keeps_todays_selection_for_routine_and_absent():
    step = _step("b")
    assert "routine" in step and "absent" in step
    for rule in ("- **haiku** —", "- **sonnet** —", "- **opus** —"):
        assert rule in step
    assert "`[parallel: true]` → haiku unless integration" in step


def test_4b_passes_alias_effort_and_runs_served_model_check():
    step = _step("b")
    assert "alias" in step
    assert "effort: max" in step
    assert "Served Model" in step


def test_4b_defines_confirmation_as_none_and_asks_fable_consent_first():
    step = _step("b")
    assert re.search(r"no (model )?confirmation", step)
    assert "Consent" in step and "before" in step


def test_4b_logs_via_xdd_meta_log_decision():
    step = _step("b")
    assert "xdd-meta" in step
    assert "Log Decision" in step
    assert "Decisions Log" in step


def test_4e_escalates_on_complexity_only():
    step = _step("e")
    assert re.search(r"Complexity problem → escalate per the ladder \(one rung\)", step)
    assert "re-dispatch with upgraded model" not in step
    for other in (
        "Context problem → provide context, re-dispatch with same model",
        "Task too large → break into sub-tasks",
        "Plan is wrong → escalate to user",
    ):
        assert other in step
    assert step.count("per the ladder") == 1


def test_4f_holds_the_full_counter_rule():
    step = _step("f")
    fail_line = next(l for l in step.splitlines() if "❌ FAIL" in l)
    assert "across 4f and 4g" in fail_line
    assert "a PASS resets it" in fail_line
    assert "second in a row" in fail_line
    assert "escalate per the ladder" in fail_line
    assert "the count resets" in fail_line
    assert "highest reachable rung" in fail_line
    assert "BLOCKED" in fail_line
    assert "no further retry" in fail_line
    assert "repeat until PASS" not in step


def test_4g_points_to_4f_instead_of_restating_the_rule():
    step = _step("g")
    fail_line = next(l for l in step.splitlines() if "❌ FAIL" in l)
    assert "as in 4f" in fail_line
    assert "across 4f and 4g" in fail_line
    assert "repeat until PASS" not in step
    assert "BLOCKED" not in fail_line


def test_4f_still_precedes_4g_and_4c_is_untouched():
    text = _text()
    assert text.index("#### 4f.") < text.index("#### 4g.")
    assert "**Spec compliance review (4f) must pass before code quality review (4g) begins.**" in text
    c = _step("c")
    assert "Dispatch `tdd-guardian` agent (haiku)" in c


def test_fable_failure_and_nobody_to_ask_are_delegated_to_the_ladder():
    step = _step("b")
    assert "Fable Failure" in step
    assert "opus@max" in step
    assert "YOLO" in _yolo()
    assert "nobody can be asked" in _yolo()
    assert "Consent" in _yolo()


def test_yolo_drops_the_stale_model_selection_confirmation():
    text = _text()
    assert "model selection confirmation" not in text
    assert "4b (model" not in text


def test_skill_does_not_restate_the_ladder():
    text = _text()
    assert COST_FRAGMENT not in text
    assert "usage credits" not in text
    assert not re.search(r"haiku\W+sonnet\W+opus\W+opus@max\W+fable", text)
    assert not re.search(r"opus@max\W+(→|->|then)\W+fable", text)
