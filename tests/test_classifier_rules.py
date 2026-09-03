"""The complexity classifier's rules must produce the tiers spec 017's SDD traces.

Why this exists: the classifier is agent-applied logic living in Markdown
(`xdd/reference/classifier.md`), so a test cannot execute the skill. What a test
*can* do is pin the two things that actually break.

1. **The rules produce wrong answers.** This module carries an independent
   reference implementation of the ordered rules and asserts it against the four
   real specs the SDD traces, plus the documented edge cases. Duplication is the
   point: if the rules and the traced expectations disagree, one of them is
   wrong, and the plan's Deviation Protocol says fix the rules.

2. **The document and the rules drift apart.** The reference implementation
   would happily stay correct while someone edits `classifier.md` into something
   else. The lockstep tests at the bottom assert the document still states these
   rules, still marks Factory reserved, and still documents override handling.

What is deliberately *not* covered: extracting the five signals from a spec's
prose. Counting "distinct user-facing capabilities" is judgement, not parsing.
The SDD asserts the signal values for the traced specs; this module asserts the
rules map those values to the right tier.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = (
    REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd" / "reference" / "classifier.md"
)

DIRECT = "Direct"
INCREMENTAL = "Incremental"

# Change types that are Direct-shaped *on their own terms*. Breadth still vetoes
# them (rule 1), which is why this set is consulted second and not first.
SMALL_CHANGE_TYPES = frozenset({"fix", "refactor", "doc"})


def classify(change_type, feature_count, ac_count, component_count, parallel_markers):
    """Reference implementation of the ordered rules in classifier.md.

    Top to bottom, first match wins. Rule 1 before rule 2 is the whole design:
    breadth vetoes Direct whatever the change type, which is the edge case
    upstream had to patch in as a footnote and which is a rule here.
    """
    if component_count >= 2 or feature_count >= 2 or parallel_markers:
        return INCREMENTAL
    if change_type in SMALL_CHANGE_TYPES or ac_count <= 2:
        return DIRECT
    return INCREMENTAL


# The four specs traced in SDD/Implementation Examples, with the signal values
# that section asserts for each.
TRACED = [
    ("015 no-verify sibling-flag false positive", "fix", 1, 2, 1, False, DIRECT),
    ("014 tcs-git-helpers rules fix", "fix", 1, 4, 1, False, DIRECT),
    ("012 hook runtime contract", "feature", 2, 12, 3, False, INCREMENTAL),
    ("017 this spec", "feature", 5, 24, 6, False, INCREMENTAL),
]


@pytest.mark.parametrize(
    "name,change_type,features,acs,components,parallel,expected",
    TRACED,
    ids=[row[0] for row in TRACED],
)
def test_traced_specs_classify_as_the_sdd_documents(
    name, change_type, features, acs, components, parallel, expected
):
    assert classify(change_type, features, acs, components, parallel) == expected


def test_a_stub_spec_classifies_direct():
    """No evidence of breadth exists yet, so recommend the cheap path.

    The user may override upward; the classifier's job is a recommendation, not
    a verdict.
    """
    assert classify("feature", 0, 0, 0, False) == DIRECT


def test_breadth_vetoes_direct_regardless_of_change_type():
    """A doc change touching four components is not Direct.

    This is SDD edge case 2 and PRD edge-case Scenario 2 — the ordering of rule
    1 before rule 2 is what implements it.
    """
    assert classify("doc", 1, 1, 4, False) == INCREMENTAL
    assert classify("refactor", 1, 1, 3, False) == INCREMENTAL
    assert classify("fix", 1, 1, 2, False) == INCREMENTAL


def test_a_single_component_fix_stays_direct():
    """The counterpart to the veto: breadth of one does not escalate."""
    assert classify("fix", 1, 9, 1, False) == DIRECT


def test_many_criteria_on_one_component_do_not_escalate_beyond_incremental():
    """PRD edge case 3: criteria count alone never drives the tier up.

    A long list of acceptance criteria against a single component is still one
    component's worth of work.
    """
    assert classify("feature", 1, 40, 1, False) == INCREMENTAL


def test_parallel_markers_alone_force_incremental():
    assert classify("fix", 1, 1, 1, True) == INCREMENTAL


def test_unparseable_signal_degrades_conservatively():
    """SDD edge case 3 / PRD AC Edge Case 2.

    An undeterminable component count is treated as 0 rather than blocking. A
    spec thin enough to lack a Building Block View is Direct-shaped anyway.
    """
    assert classify("fix", 1, 1, 0, False) == DIRECT


def test_classification_is_deterministic():
    signals = ("feature", 1, 3, 1, False)
    results = {classify(*signals) for _ in range(25)}
    assert len(results) == 1


def test_every_signal_combination_yields_a_known_tier():
    """The rules are total — there is no input that falls off the end."""
    for change_type in ("feature", "fix", "refactor", "doc", "something-else"):
        for features in range(0, 4):
            for acs in range(0, 6):
                for components in range(0, 4):
                    for parallel in (True, False):
                        assert classify(change_type, features, acs, components, parallel) in (
                            DIRECT,
                            INCREMENTAL,
                        )


# --- Lockstep: the document must still state these rules ---


def _classifier_text():
    assert CLASSIFIER.exists(), f"{CLASSIFIER} does not exist"
    return CLASSIFIER.read_text(encoding="utf-8")


def test_classifier_reference_documents_all_five_signals():
    text = _classifier_text()
    for signal in (
        "change_type",
        "feature_count",
        "ac_count",
        "component_count",
        "parallel_markers",
    ):
        assert signal in text, f"classifier.md does not document {signal}"


def test_classifier_reference_states_the_ordered_rules():
    text = _classifier_text()
    assert "first match wins" in text.lower()
    # rule 1's veto, in the form the reference implementation encodes
    assert "component_count >= 2" in text
    assert "feature_count >= 2" in text
    assert "parallel_markers" in text
    # rule 2's small-change escape
    assert "ac_count <= 2" in text


def test_classifier_reference_marks_factory_reserved_and_unbuilt():
    """ADR-3. A classifier that could recommend Factory would route work to a
    loop that does not exist."""
    text = _classifier_text()
    lowered = text.lower()
    assert "factory" in lowered
    assert "reserved" in lowered
    assert "not implemented" in lowered or "unbuilt" in lowered


def test_classifier_reference_requires_rationale_and_override_logging():
    text = _classifier_text().lower()
    assert "rationale" in text
    assert "override" in text
    assert "decisions log" in text or "decision log" in text


def test_classifier_reference_never_claims_to_apply_the_tier_itself():
    """PRD business rule 2: recommendation, never application."""
    text = _classifier_text().lower()
    assert "recommend" in text
    assert "never" in text and "apply" in text


# --- Lockstep: xdd must actually wire the classifier in ---

XDD_SKILL = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd" / "SKILL.md"


def _xdd_text():
    return XDD_SKILL.read_text(encoding="utf-8")


def _step_six():
    """The Decompose step, isolated from the rest of the workflow."""
    text = _xdd_text()
    start = text.index("### 6. Decompose")
    return text[start : text.index("### 7.", start)]


def test_xdd_reads_the_classifier_reference():
    assert "reference/classifier.md" in _step_six()


def test_xdd_lists_the_classifier_in_reference_materials():
    """Progressive disclosure only works if the file is discoverable."""
    text = _xdd_text()
    materials = text[text.index("## Reference Materials") : text.index("## Workflow")]
    assert "classifier.md" in materials


def test_xdd_surfaces_the_signals_before_asking():
    step = _step_six()
    for signal in ("change_type", "feature_count", "ac_count", "component_count", "parallel_markers"):
        assert signal in step, f"step 6 does not name {signal}"
    assert "Surface" in step


def test_xdd_offers_both_tiers_and_never_pre_applies():
    step = _step_six()
    assert "**Direct**" in step and "**Incremental**" in step
    assert "may override freely" in step


def test_xdd_direct_branch_writes_no_decomposition_artifact():
    step = _step_six()
    assert "Direct      => write no decomposition artifact" in step


def test_xdd_incremental_branch_still_invokes_xdd_plan():
    """The heavyweight path must be untouched — this feature makes small work
    possible, never big work cheaper."""
    assert "Skill(tcs-workflow:xdd-plan)" in _step_six()


def test_xdd_records_the_tier_in_both_places():
    step = _step_six()
    assert "Status table" in step
    assert "Decisions Log" in step


def test_xdd_adds_no_question_beyond_the_tier_confirmation():
    """CON-8: classification costs zero extra conversation turns.

    Step 6 asks twice — the tier, and the existing finalize/revisit gate that
    every phase step already had. A third question would mean the classifier
    started interrogating the user.
    """
    assert _step_six().count("AskUserQuestion") <= 1
    assert "Ask** the user to choose" in _step_six()


def test_xdd_forbids_recommending_the_unbuilt_tier():
    text = _xdd_text()
    assert "Recommend or record `Factory`" in text


def test_xdd_never_classifies_from_the_raw_request():
    text = _xdd_text()
    assert "never from the raw request" in text
