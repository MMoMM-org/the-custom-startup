"""Selftest for T5: a perfect transcript passes all script criteria, bad ones fail one each.
No model calls.  Run: python3 -I tasks/T5/selftest.py
"""
import importlib.util
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("t5task", os.path.join(HERE, "task.py"))
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
cases = json.load(open(os.path.join(HERE, "cases.json")))
assert len(cases) == 10 and len({c["id"] for c in cases}) == 10
case = cases[3]

DOC = """```markdown
# PRD: Bakery pre-orders

## 1. Product Overview
Regular customers reserve bread the evening before, so the bakery bakes to order and wastes less.

## 2. User Personas
Primary: the regular customer who wants a guaranteed loaf. Secondary: the baker planning dough.

## 3. User Journey Maps
The customer picks items in the evening, gets a confirmation, and collects at the counter next day.

## 4. Feature Requirements
Must Have: place an order until 6 p.m. the day before.
Given an order before 6 p.m., when the baker plans, then the order appears in the bake list.
Should Have: repeat last order. Could Have: favourites. Won't Have: delivery.

## 5. Detailed Feature Specifications
Orders close at 6 p.m.; payment stays cash at pickup; uncollected orders are released at noon.

## 6. Success Metrics
Morning waste drops from about 15% to under 8% within three months.

## 7. Constraints and Assumptions
Two-person team; cash payment must remain possible; no change to opening hours.

## 8. Open Questions
- What happens to an order the customer forgets to collect?
- Should Sunday have a separate cut-off?
```
Shall I change anything?"""

PERFECT = [
    {"role": "user", "content": "Feature to specify: " + case["idea"]},
    {"role": "assistant", "content": "Thanks. What is the main problem pre-orders should solve for you?"},
    {"role": "user", "content": "We throw away too much bread."},
    {"role": "assistant", "content": "Here is a draft of Section 1.\n\n**Product Overview**\nCustomers reserve "
                                     "baked goods ahead so the bakery wastes less.\n\nDoes this capture it?"},
    {"role": "user", "content": "Please write the whole PRD now."},
    {"role": "assistant", "content": DOC},
]


def with_turn(idx, content):
    t = [dict(m) for m in PERFECT]
    t[idx]["content"] = content
    return t


BAD_MULTI_Q = with_turn(1, "Who are your customers? How many orders a day? When do you bake?")
BAD_SECTION = with_turn(5, DOC.replace("## 6. Success Metrics\nMorning waste drops from about 15% "
                                       "to under 8% within three months.\n\n", ""))
BAD_MARKER = with_turn(5, DOC.replace("Two-person team;", "[NEEDS CLARIFICATION: staff] Two-person team;"))
BAD_IDIOM = with_turn(3, "Red Flags: none so far. What time do you start baking?")
NO_DOC = PERFECT[:4]
# Post-pilot regressions: allowed forms that must still PASS.
OK_MARKER_IN_OPEN_Q = with_turn(5, DOC.replace("- Should Sunday", "- [NEEDS CLARIFICATION: Sunday] Should Sunday"))
OK_BACKTICK_MENTION = with_turn(5, DOC.replace("```\nShall", "No `[NEEDS CLARIFICATION]` markers remain.\n```\nShall"))
OK_DRAFT_MARKER = with_turn(3, PERFECT[3]["content"].replace("less.", "less. [NEEDS CLARIFICATION: waste %]"))
OK_QUOTED_Q = with_turn(1, 'Today staff ask "Is my bread ready?" at the counter. What problem should pre-orders solve?')
OUTLINE_ONLY = [PERFECT[0], {"role": "assistant", "content": "\n".join(
    "{}. {}".format(i + 1, s[0]) for i, s in enumerate(task.SECTIONS)) + "\nWhat problem?"}]

with tempfile.TemporaryDirectory() as dest:
    task.build(case, dest)
    cs = task.conversation_spec(case, "PRD prompt. Feature: {{FEATURE_DESCRIPTION}}")
    assert cs["model"] == "qwen3.5:35b-a3b" and cs["max_turns"] == 8
    assert case["idea"] in cs["system"] and cs["first_user"].endswith(case["idea"])

    g = task.grade(case, dest, json.dumps(PERFECT))
    print("perfect:", g)
    assert g == {"one_question_per_turn": True, "all_sections": True,
                 "markers_resolved": True, "no_claude_idioms": True,
                 "no_implementation_detail": None}, g
    assert task.is_done(PERFECT) and not task.is_done(PERFECT[:4])
    assert not task.is_done(OUTLINE_ONLY), "an outline without bodies must not count as the PRD"
    assert task.judge_material(case, dest, json.dumps(PERFECT)) == DOC

    for label, bad, crit in (("multi-question", BAD_MULTI_Q, "one_question_per_turn"),
                             ("missing section", BAD_SECTION, "all_sections"),
                             ("needs marker", BAD_MARKER, "markers_resolved"),
                             ("cc idiom", BAD_IDIOM, "no_claude_idioms"),
                             ("no final doc", NO_DOC, "all_sections")):
        g = task.grade(case, dest, json.dumps(bad))
        print("bad/{}:".format(label), g)
        assert g[crit] is False, (label, g)
    for label, ok, crit in (("marker in open questions", OK_MARKER_IN_OPEN_Q, "markers_resolved"),
                            ("backticked mention", OK_BACKTICK_MENTION, "markers_resolved"),
                            ("marker in interim draft", OK_DRAFT_MARKER, "markers_resolved"),
                            ("quoted persona question", OK_QUOTED_Q, "one_question_per_turn")):
        g = task.grade(case, dest, json.dumps(ok))
        assert g[crit] is True, (label, g)
    for junk in ("", "not json", "{}", "[1, 2]", json.dumps({"messages": PERFECT})):
        task.grade(case, dest, junk)   # must not raise
    assert task.grade(case, dest, json.dumps({"messages": PERFECT}))["all_sections"] is True

    p_early = task.simulated_user_prompt(case, PERFECT[:2])
    p_late = task.simulated_user_prompt(case, PERFECT[:2] + [PERFECT[2], PERFECT[1]] * 6)
    assert "out of time" not in p_early and "out of time" in p_late
    assert all(f in p_early for f in case["hidden_facts"])

print("T5 selftest OK")
