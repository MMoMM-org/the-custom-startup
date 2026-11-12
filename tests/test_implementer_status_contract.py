"""The implementer brief must define every status the orchestrator branches on.

Why this exists (#250): both implement tiers branched on DONE / DONE_WITH_CONCERNS /
NEEDS_CONTEXT / BLOCKED, but neither brief asked the implementer to report one, so
the branch depended on the subagent guessing the vocabulary. Spec 023's T2
experiment measured NEEDS_CONTEXT coming back only when the brief defined it.
Each test slices the dispatch step (producer) and the status step (consumer) and
requires the consumer's status set to be a subset of the producer's.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "tcs-workflow" / "skills"
STATUS = re.compile(r"\b(DONE_WITH_CONCERNS|DONE|NEEDS_CONTEXT|BLOCKED)\b")

CASES = {
    "implement-incremental": ("4d", "4e"),
    "implement-direct": ("3b", "3c"),
}


def _step(skill: str, heading: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text()
    m = re.search(rf"^#### {re.escape(heading)}.*?(?=^#{{1,4}} )", text, re.S | re.M)
    assert m, f"{skill}: step {heading} not found"
    return m.group(0)


def _consumed(skill: str, heading: str) -> set[str]:
    block = re.search(r"```\n(.*?)```", _step(skill, heading), re.S)
    assert block, f"{skill}: step {heading} has no status block"
    return {line.split()[0] for line in block.group(1).splitlines() if STATUS.match(line)}


@pytest.mark.parametrize("skill", sorted(CASES))
def test_brief_defines_every_consumed_status(skill):
    brief, handling = CASES[skill]
    consumed = _consumed(skill, handling)
    assert consumed == {"DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"}
    defined = set(re.findall(r"^\s*- `([A-Z_]+)` — ", _step(skill, brief), re.M))
    assert consumed <= defined, f"{skill} {brief} lacks {sorted(consumed - defined)}"


@pytest.mark.parametrize("skill", sorted(CASES))
def test_brief_asks_for_a_status_line(skill):
    assert "`Status:`" in _step(skill, CASES[skill][0])


def test_incremental_states_the_history_rule_once():
    text = (SKILLS / "implement-incremental" / "SKILL.md").read_text()
    constraints = text.split("## Reference Materials")[0]
    assert len(re.findall(r"session history", constraints)) == 1


# #271: an environment failure is its own BLOCKED cause, a report without a
# status is never read as DONE, and "suite green" is a baseline comparison.

GATE = SKILLS / "xdd" / "reference" / "suite-gate.md"


@pytest.mark.parametrize("skill", sorted(CASES))
def test_blocked_names_the_environment_as_a_cause(skill):
    brief, handling = CASES[skill]
    blocked = re.search(r"^\s*- `BLOCKED` — .*$", _step(skill, brief), re.M)
    assert blocked and "environment" in blocked.group(0), f"{skill} {brief}"
    assert re.search(r"[Ee]nvironment problem →", _step(skill, handling)), f"{skill} {handling}"


@pytest.mark.parametrize("skill", sorted(CASES))
def test_environment_blocked_is_not_escalated(skill):
    step = _step(skill, CASES[skill][1])
    line = next(l for l in step.splitlines() if "nvironment problem →" in l)
    rest = step[step.index(line):]
    assert re.search(r"never escalate", rest, re.I), f"{skill}: environment branch may escalate"


@pytest.mark.parametrize("skill", sorted(CASES))
def test_a_report_without_a_status_is_needs_context(skill):
    block = re.search(r"```\n(.*?)```", _step(skill, CASES[skill][1]), re.S).group(1)
    row = next((l for l in block.splitlines() if l.startswith("no status")), None)
    assert row and "NEEDS_CONTEXT" in row, f"{skill}: no row for a missing status"
    assert "DONE" not in row.replace("NEEDS_CONTEXT", "").replace("never as DONE", "")


def test_suite_gate_compares_failure_sets_against_a_baseline():
    text = GATE.read_text()
    for needed in ("baseline", "set", "not a count", "command"):
        assert needed in text, f"suite-gate.md lacks {needed!r}"


@pytest.mark.parametrize("skill,steps", [
    ("implement-incremental", ("### 1. Initialize", "### 5. Validate Phase")),
    ("implement-direct", ("### 1. Initialize", "### 4. Validate")),
])
def test_both_tiers_record_a_baseline_and_gate_on_it(skill, steps):
    text = (SKILLS / skill / "SKILL.md").read_text()
    for heading in steps:
        start = text.index(heading)
        section = text[start:text.index("\n### ", start + 1)]
        assert "suite-gate.md" in section, f"{skill}: {heading} does not use the suite gate"
