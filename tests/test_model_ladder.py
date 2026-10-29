"""The model ladder reference must state the ladder, escalation and consent rules.

Why this exists: the ladder is agent-applied logic living in Markdown
(`xdd/reference/model-ladder.md`), so a test cannot execute it. Two things can
break, and this module pins both, as test_classifier_rules.py does for the
classifier.

1. **The rules give wrong answers.** An independent reference implementation of
   the escalation function is asserted against the traced cases in the solution
   design. If the rules and the traces disagree, one of them is wrong.

2. **The document drifts from the rules.** Lockstep tests slice the file by `##`
   heading, so each assertion checks its own section and cannot be satisfied by
   a literal that happens to appear elsewhere.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LADDER = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd" / "reference" / "model-ladder.md"

COST_SENTENCE = (
    "Fable costs about 2.5× Opus per token and can bill usage credits "
    "instead of your plan's limits."
)

RUNGS = ["haiku", "sonnet", "opus", "opus@max", "fable"]


# --- Reference implementation of the escalation function ---


class Task:
    def __init__(self, rung, planned=False):
        self.rung = rung
        self.planned = planned
        self.failures = 0
        self.fable_consent = False
        self.log = []


class Run:
    def __init__(self, can_ask=True, consent=True):
        self.can_ask = can_ask
        self.consent = consent
        self.fable_unavailable = False


CONTINUE = "continue"
BLOCKED = "BLOCKED"


def escalate(task, run):
    """Returns CONTINUE (re-dispatch at task.rung) or BLOCKED."""
    task.failures = 0
    if task.rung == "fable" or (task.rung == "opus@max" and run.fable_unavailable):
        return BLOCKED
    nxt = RUNGS[RUNGS.index(task.rung) + 1]
    if nxt != "fable":
        task.log.append(f"escalation {task.rung} -> {nxt}")
        task.rung = nxt
        return CONTINUE
    if not run.can_ask:
        task.log.append("fable not reached: no one to ask")
        return BLOCKED
    if run.consent:
        task.rung = "fable"
        task.fable_consent = True
        task.log.append("consent")
        task.log.append("escalation opus@max -> fable")
        return CONTINUE
    task.log.append("declined")
    return BLOCKED


def on_blocked(task, run, reason):
    if reason == "complexity":
        return escalate(task, run)
    return CONTINUE  # today's handling, no escalation


def on_review(task, run, passed):
    if passed:
        task.failures = 0
        return CONTINUE
    task.failures += 1
    if task.failures == 2:
        return escalate(task, run)
    return CONTINUE


def on_fable_failure(task, run):
    run.fable_unavailable = True
    if task.planned:
        task.rung = "opus@max"
        task.log.append("substitution fable -> opus@max")
        return CONTINUE
    task.log.append("substitution refused")
    return BLOCKED


def test_two_fails_in_a_row_escalate_one_rung_and_reset_the_count():
    task, run = Task("sonnet"), Run()
    assert on_review(task, run, False) == CONTINUE
    assert task.rung == "sonnet" and task.failures == 1
    assert on_review(task, run, False) == CONTINUE
    assert task.rung == "opus" and task.failures == 0


def test_fail_pass_fail_does_not_escalate():
    task, run = Task("sonnet"), Run()
    on_review(task, run, False)
    on_review(task, run, True)
    on_review(task, run, False)
    assert task.rung == "sonnet" and task.failures == 1


def test_complexity_blocked_escalates_but_other_reasons_do_not():
    for reason in ("missing context", "too large", "wrong plan"):
        task, run = Task("opus"), Run()
        on_blocked(task, run, reason)
        assert task.rung == "opus"
    task, run = Task("opus"), Run()
    on_blocked(task, run, "complexity")
    assert task.rung == "opus@max"


def test_complexity_blocked_at_opus_max_asks_when_someone_can_be_asked():
    task, run = Task("opus@max"), Run(can_ask=True, consent=True)
    assert on_blocked(task, run, "complexity") == CONTINUE
    assert task.rung == "fable" and task.fable_consent


def test_complexity_blocked_at_opus_max_is_blocked_when_nobody_can_be_asked():
    task, run = Task("opus@max"), Run(can_ask=False)
    assert on_blocked(task, run, "complexity") == BLOCKED
    assert task.rung == "opus@max"
    assert "fable not reached: no one to ask" in task.log


def test_declined_consent_is_blocked_at_opus_max():
    task, run = Task("opus@max"), Run(can_ask=True, consent=False)
    assert on_blocked(task, run, "complexity") == BLOCKED
    assert task.rung == "opus@max"


def test_fable_failure_on_a_planned_task_continues_at_opus_max():
    task, run = Task("fable", planned=True), Run()
    assert on_fable_failure(task, run) == CONTINUE
    assert task.rung == "opus@max" and run.fable_unavailable


def test_fable_failure_on_an_escalated_task_is_blocked():
    task, run = Task("fable", planned=False), Run()
    assert on_fable_failure(task, run) == BLOCKED
    assert run.fable_unavailable


def test_two_fails_at_fable_are_blocked():
    task, run = Task("fable"), Run()
    on_review(task, run, False)
    assert on_review(task, run, False) == BLOCKED


def test_fable_is_capped_at_opus_max_once_unavailable():
    task, run = Task("opus@max"), Run()
    run.fable_unavailable = True
    assert on_blocked(task, run, "complexity") == BLOCKED


def test_escalation_moves_exactly_one_rung_at_a_time():
    task, run = Task("haiku"), Run(can_ask=False)
    seen = [task.rung]
    while escalate(task, run) == CONTINUE:
        seen.append(task.rung)
    assert seen == ["haiku", "sonnet", "opus", "opus@max"]


# --- Lockstep: the document must still state these rules ---


def _text():
    assert LADDER.exists(), f"{LADDER} does not exist"
    return LADDER.read_text(encoding="utf-8")


def _section(name):
    text = _text()
    match = re.search(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"model-ladder.md has no '## {name}' section"
    return match.group(1)


def test_ladder_lists_the_five_rungs_in_order():
    body = _section("Ladder")
    rows = re.findall(r"^\| `([a-z@]+)` \|", body, re.M)
    assert rows == RUNGS


def test_ladder_uses_aliases_only_and_no_full_model_id():
    text = _text()
    assert not re.search(r"claude-[a-z]+-\d", text), "a full model ID appears"
    assert "aliases only" in _section("Ladder").lower()


def test_opus_max_is_opus_with_max_effort_and_minimum_version():
    body = _section("Ladder")
    assert "`opus@max` is not a model" in body
    assert "`effort: max`" in body
    assert "2.1.292" in body


def test_effort_unsupported_falls_back_to_opus_and_is_logged():
    body = _section("Ladder")
    assert "re-dispatch at `opus` without effort" in body
    assert "effort unsupported" in body


def test_effort_environment_override_is_noted():
    assert "CLAUDE_CODE_EFFORT_LEVEL" in _section("Ladder")


def test_starting_rungs_for_both_decomposition_tiers():
    body = _section("Starting Rung")
    rows = {
        m.group(1): (m.group(2), m.group(3))
        for m in re.finditer(r"^\| (absent[^|]*|`\w+`) \| ([^|]+) \| ([^|]+) \|$", body, re.M)
    }
    assert rows["`routine`"] == ("step 4b as today", "`sonnet`")
    assert rows["`hard`"] == ("`opus`", "`opus`")
    assert rows["`frontier`"] == ("`fable`", "`fable`")
    absent = next(v for k, v in rows.items() if k.startswith("absent"))
    assert absent[0].strip() == "step 4b as today"
    assert "no `model` parameter" in absent[1]
    assert "first escalation goes to `opus`" in absent[1]


def test_task_tag_overrides_spec_tier_and_unknown_tag_falls_back():
    body = _section("Starting Rung")
    assert "`[model: …]` tag" in body
    assert "unknown tag value falls back to the spec tier" in body


def test_frontier_tag_in_a_non_frontier_spec_is_consented_or_runs_at_hard():
    body = _section("Starting Rung")
    assert "needs consent first" in body
    assert "counts as planned" in body
    assert "run at the `hard` rung" in body


def test_escalation_names_exactly_two_triggers():
    body = _section("Escalation")
    assert "Exactly two triggers" in body
    assert "**BLOCKED** for reason **complexity**" in body
    assert "twice in a row at the same rung" in body
    assert len(re.findall(r"^\d\. ", body.split("```")[0], re.M)) == 2


def test_three_non_escalating_blocked_reasons_are_named():
    body = _section("Escalation")
    for reason in ("missing context", "task too large", "wrong plan"):
        assert reason in body


def test_escalation_resets_count_and_moves_one_rung():
    body = _section("Escalation")
    assert "One rung at a time" in body
    assert "T.failures_at_rung = 0" in body
    assert "starts again at 0" in body


def test_escalation_caps_at_the_highest_reachable_rung():
    body = _section("Escalation")
    assert "The cap" in body
    assert "report **BLOCKED** to the user instead of retrying" in body
    assert "no question is asked for any rung below `fable`" in body.lower()


def test_consent_precedes_every_fable_dispatch_not_covered_by_a_confirmed_tier():
    body = _section("Consent")
    assert "Every dispatch to `fable` needs a person's consent" in body
    assert "except a planned task in a spec whose `frontier` tier the user confirmed" in body
    assert "frontier` task tag in a spec whose tier is not `frontier`" in body


def test_declined_consent_outcome_depends_on_the_trigger():
    body = _section("Consent")
    line = next(l for l in body.splitlines() if "Answer no:" in l)
    assert "stay at the capped rung" not in line
    assert "An escalation is reported BLOCKED at `opus@max`" in line
    assert "a `frontier` tag runs at the `hard` rung" in line


def test_nobody_can_be_asked_is_defined():
    body = _section("Consent")
    assert "`YOLO=true`" in body
    assert "no answer or an error" in body
    assert "BLOCKED at `opus@max`" in body
    assert "runs at the `hard` rung" in body


def test_fable_failure_rules():
    body = _section("Fable Failure")
    assert "dismissed or unanswered" in body
    assert "off for the rest of the run" in body
    assert "**planned** task" in body and "`opus@max`" in body and "continue" in body
    assert "**escalated** task" in body and "report BLOCKED" in body


def test_served_model_check_reads_only_message_model():
    body = _section("Served Model")
    assert "`output_file`" in body
    assert "select(.type == \"assistant\") | .message.model" in body
    assert "only" in body.lower()
    assert "never against a hard-coded full model ID" in body
    assert "naming the served model" in body
    assert "served by another model is a fable failure" in body


def test_cost_sentence_appears_exactly_once_in_the_file():
    assert _text().count(COST_SENTENCE) == 1
    assert COST_SENTENCE in _section("Cost Sentence")


def test_cost_sentence_states_ratio_and_billing_route_not_prices():
    body = _section("Cost Sentence")
    assert "never prices" in body
    assert "$" not in _text()


def test_decisions_log_rows_have_the_four_formats():
    body = _section("Decisions Log")
    for fragment in (
        "| <date> | Model escalation: T2.1 opus → opus@max | Trigger: second review FAIL |",
        "| <date> | Fable consent: T2.1 | Asked at escalation; user agreed |",
        "| <date> | Model substitution: T2.1 | Requested fable, ran opus@max: dispatch error <reason> |",
        "| <date> | Model substitution: T2.1 | Requested fable, served <model> (message.model) |",
    ):
        assert fragment in body
    assert "xdd-meta step 4" in body


def test_instruction_text_carries_no_spec_or_issue_provenance():
    text = _text()
    assert not re.search(r"\bADR-\d|\bAC-\d|#\d{2,}|spec \d{3}", text)
