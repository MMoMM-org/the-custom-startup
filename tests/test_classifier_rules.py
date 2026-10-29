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


def test_classifier_reference_defines_component_granularity():
    """#161. Without a granularity, two helper functions read as two
    components and rule 1's breadth veto fires on a one-unit change."""
    text = _classifier_text()
    assert "What counts as a component" in text
    assert "single function or helper is part of the component" in text
    assert "only outside the Building Block View" in text


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


# --- The Direct tier's plan/ row (spec-017 T4.2 walkthrough finding) ---
#
# The Documents table carries a `plan/` row for every spec. Nothing told the
# workflow what to put there when the tier is Direct, so it stayed at `pending`
# — a finished Direct spec reading as if a plan were still outstanding, which
# is exactly the "no plan by decision, not by omission" distinction xdd-meta
# draws in its Read Status step.


def test_classifier_reference_says_what_the_plan_row_reads_on_direct():
    text = _classifier_text()
    assert "Documents table" in text
    assert "skipped" in text


def test_xdd_direct_branch_marks_the_plan_row_skipped():
    step = _step_six()
    assert "`plan/` row `skipped`" in step


# --- Model tier: the second section of the classifier (spec 022, ADR-1/ADR-2) ---
#
# Same shape as the decomposition tests above: an independent reference
# implementation of the ordered rules asserted against the SDD's traced
# walkthroughs, then lockstep tests that the document still states the rules.
# The lockstep tests slice the "Model Tier" section by heading so they can never
# be satisfied by the decomposition section.

ROUTINE = "routine"
HARD = "hard"
FRONTIER = "frontier"


def model_tier(change_type, high_risks, novel_pattern, adr_count):
    """Reference implementation of the model-tier rules in classifier.md.

    Top to bottom, first match wins. Rule 1 first: a doc change is routine
    whatever its risks. Rule 2 before rule 3: the frontier test is the strict
    case of the hard test.
    """
    if change_type == "doc":
        return ROUTINE
    if novel_pattern and high_risks >= 2:
        return FRONTIER
    if novel_pattern or high_risks >= 1 or adr_count >= 3:
        return HARD
    return ROUTINE


# The situation strings are the Edge cases table's, verbatim; a lockstep test
# below parses the table and requires exactly these (situation, tier) pairs.
MODEL_TIER_TRACED = [
    ("Doc rewrite, one High risk, a new doc pattern", "doc", 1, True, 1, ROUTINE),
    ("Spec with 7 ADRs, no High risk, no new pattern", "feature", 0, False, 7, HARD),
    ("Novel pattern, two High risks", "feature", 2, True, 4, FRONTIER),
    ("Two High risks, no new pattern", "feature", 2, False, 0, HARD),
    ("Small fix, only Medium risks", "fix", 0, False, 0, ROUTINE),
    (
        "No Pattern Documentation section, one High risk",
        "feature",
        1,
        False,
        2,
        HARD,
    ),
]


@pytest.mark.parametrize(
    "name,change_type,high_risks,novel,adrs,expected",
    MODEL_TIER_TRACED,
    ids=[row[0] for row in MODEL_TIER_TRACED],
)
def test_model_tier_traced_specs_match_the_sdd(
    name, change_type, high_risks, novel, adrs, expected
):
    assert model_tier(change_type, high_risks, novel, adrs) == expected


def test_model_tier_novelty_alone_is_hard_not_frontier():
    assert model_tier("feature", 1, True, 0) == HARD
    assert model_tier("feature", 0, True, 0) == HARD


def test_model_tier_two_high_risks_without_novelty_are_hard():
    assert model_tier("feature", 2, False, 0) == HARD


def test_model_tier_adr_threshold_is_three():
    assert model_tier("feature", 0, False, 2) == ROUTINE
    assert model_tier("feature", 0, False, 3) == HARD


def _model_tier_section():
    text = _classifier_text()
    assert "\n## Model Tier\n" in text, "classifier.md has no '## Model Tier' section"
    start = text.index("\n## Model Tier\n") + 1
    nxt = text.find("\n## ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


def test_model_tier_section_documents_the_four_signals():
    section = _model_tier_section()
    for signal in ("change_type", "high_risks", "novel_pattern", "adr_count"):
        assert signal in section, f"Model Tier section does not document {signal}"
    assert "Risks and Mitigations" in section
    assert "Pattern Documentation" in section
    assert "Architecture Decisions" in section


def test_model_tier_section_states_the_ordered_rules():
    section = _model_tier_section()
    assert "first match wins" in section.lower()
    rules = [
        "1. routine   if change_type == doc",
        "2. frontier  if novel_pattern AND high_risks >= 2",
        "3. hard      if novel_pattern OR high_risks >= 1 OR adr_count >= 3",
        "4. routine   otherwise",
    ]
    assert "\n".join(rules) in section, "rule block is missing, reworded or reordered"


def _edge_case_rows():
    section = _model_tier_section()
    body = section.split("### Edge cases", 1)[1].split("\n### ", 1)[0]
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 3 and cells[1] in (
            ROUTINE,
            HARD,
            FRONTIER,
        ):
            rows.append((cells[0], cells[1]))
    return rows


def test_model_tier_edge_case_table_matches_the_traced_cases():
    expected = [(row[0], row[5]) for row in MODEL_TIER_TRACED]
    assert _edge_case_rows() == expected


def test_model_tier_section_lowers_undeterminable_signals():
    section = _model_tier_section()
    assert (
        "lower it: `high_risks = 0`, `novel_pattern = false`, `adr_count = 0`."
        in section
    )
    assert "Name each lowered signal in the rationale" in section
    assert "rationale" in section.lower()


def test_model_tier_section_logs_overrides_with_reason_or_none_given():
    section = _model_tier_section()
    assert "Model tier" in section
    assert "Status table" in section
    assert "Decisions Log" in section
    assert "override" in section.lower()
    assert "without one, log `no reason given`" in section
    assert "free-text" in section


def test_model_tier_section_recommends_and_never_applies():
    lowered = _model_tier_section().lower()
    assert "recommend" in lowered
    assert "never" in lowered and "apply" in lowered


def test_model_tier_section_links_the_ladder_without_copying_its_cost_sentence():
    section = _model_tier_section()
    assert "model-ladder.md" in section
    assert "2.5" not in section
    assert "usage credits" not in section


def test_model_tier_section_names_all_three_tiers_and_no_rung_names():
    section = _model_tier_section()
    for tier in ("routine", "hard", "frontier"):
        assert tier in section
    lowered = section.lower()
    for rung in ("opus", "sonnet", "haiku", "fable", "@max"):
        assert rung not in lowered, f"rung name {rung} belongs in model-ladder.md"


# --- Step 6 confirms both tiers in one round (spec 022, T3.2) ---
#
# The model tier rides on the existing "Ask the user to choose" bullet as a
# second question. The tool name stays out of step 6 beyond the one finalize
# gate, so the CON-8 count test above holds unchanged.


def test_xdd_extracts_the_model_tier_signals_without_asking():
    step = _step_six()
    for signal in ("high_risks", "novel_pattern", "adr_count"):
        assert signal in step, f"step 6 does not name {signal}"
    assert "ask the user nothing" in step


def test_xdd_asks_both_tiers_in_one_round_under_named_headers():
    step = _step_six()
    assert "**Ask** the user to choose" in step
    assert "in one question round with two questions" in step
    assert 'header "Decompose"' in step
    assert 'header "Model"' in step
    assert "routine | hard | frontier" in step


def test_xdd_undeterminable_signal_takes_the_classifier_fallback_not_a_cautious_value():
    step = _step_six()
    assert "takes the fallback value the classifier defines" in step
    assert "conservative" not in step


def test_xdd_frontier_option_takes_its_cost_sentence_from_the_ladder():
    step = _step_six()
    assert "reference/model-ladder.md" in step
    # The sentence is owned by model-ladder.md; restating it here would fork it.
    assert "2.5×" not in step
    assert "usage credits" not in step


def test_xdd_takes_the_override_reason_from_free_text():
    step = _step_six()
    assert "free-text" in step
    assert "no reason given" in step


def test_xdd_records_both_tiers_in_status_and_decisions_log():
    step = _step_six()
    assert "`Decomposition tier`" in step
    assert "`Model tier`" in step
    assert "a Decisions Log row per tier" in step


def test_xdd_state_and_interface_carry_the_model_tier():
    text = _xdd_text()
    head = text[: text.index("## Constraints")]
    assert "modelTier: Routine | Hard | Frontier" in head
    assert "model: {" in head
