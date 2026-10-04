"""T2.5 (spec-020): the decided-exactly-once invariant.

Why this exists: F3's fourth acceptance criterion is "each of the 21 is
decided exactly once -- by a file signal or by one question, never both".
That is only a claim until something sums it
`[ref: SDD/Runtime View/Complex Logic]`.

**Four sets, not three.** A three-set partition (installed,
declined-by-question, excluded-by-stack-fact) covers the 21 in zero of the
26 fixtures, because a pattern behind a gate that stayed shut belongs to
none of the three -- nobody was asked, so it is neither installed nor
declined, and no stack fact excluded it. It is `not_reached`, the fourth
set `outcomes.decide()` returns
`[ref: SDD/Runtime View/Complex Logic, "There are four outcomes, not
three"]`.

The module under test (`outcomes.py`) is imported at **runtime**, inside
each test, not at module level -- same reason `test_patterns_detect.py`
does this for `detect.py`: a module-level `ImportError` would collect zero
cases and abort the rest of the suite's collection besides.
"""

from __future__ import annotations

import importlib
import itertools
import sys
from types import ModuleType

import pytest

from patterns_detection_corpus_lib import CATALOGUE_DIR, EXPECTED_CASE_COUNT, REPO_ROOT, discover_fixtures
from visible_dirs import visible_dir_names

LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"


def _load_outcomes() -> ModuleType:
    """See `test_patterns_detect.py::_load_detect` for why this import
    happens here rather than at module level, and why `sys.path` (not
    `PYTHONPATH`) is how a mutated copy must be loaded when
    mutation-testing this file."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("outcomes")


def _load_detect() -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("detect")


# Hand-typed against the SDD's gate table, independently of `outcomes.py`'s
# own `GATE_SETTLED_PATTERNS` -- the point of this check is that a table
# swapping two names between the gate-settled and stack-fact groups (e.g.
# `testing` moved under a gate, `mutation-testing` moved under stack facts)
# still unions to 21 and still leaves the groups disjoint, so a union-only
# check would pass it. Asserting the gate-settled group against this
# literal is what catches the swap
# `[ref: SDD/Interface Specifications/Detection rules: the eight stack facts
# and the three gates]`.
EXPECTED_GATE_SETTLED_PATTERNS = {
    "q1_backend": frozenset(
        {
            "api-design",
            "bff-entry-points",
            "secure-oauth-oidc",
            "observability",
            "twelve-factor",
            "node-service",
        }
    ),
    "q2_architecture": frozenset(
        {
            "ddd",
            "event-driven",
            "event-sourcing",
            "hexagonal",
            "functional",
        }
    ),
    "q3_test_quality": frozenset(
        {
            "mutation-testing",
            "test-design-reviewer",
        }
    ),
}

# The other eight, also hand-typed `[ref: SDD/Interface Specifications/
# Detection rules: the eight stack facts and the three gates]`.
EXPECTED_STACK_FACT_PATTERNS = frozenset(
    {
        "obsidian-plugin",
        "mcp-server",
        "typescript-strict",
        "go-idiomatic",
        "python-project",
        "react-testing",
        "frontend-testing",
        "testing",
    }
)


def test_corpus_is_not_empty_here_either() -> None:
    """Standalone and non-parametrized, mirroring the same guard in
    `test_patterns_detect.py` and `test_patterns_detection_corpus.py` -- this
    file parametrizes over the same corpus but has no count guard of its
    own, so a vanished or emptied corpus must fail THIS assertion when this
    file is run alone, not skip quietly at exit 0."""
    fixtures = discover_fixtures()
    names = sorted(f.name for f in fixtures)
    assert len(fixtures) == EXPECTED_CASE_COUNT, (
        f"expected exactly {EXPECTED_CASE_COUNT} fixtures, found {len(fixtures)}: {names}"
    )


def test_gate_settled_group_matches_the_hand_typed_literal() -> None:
    """Asserted against the literal above, never derived from the module
    under test -- a check that re-derives the code's own logic agrees with
    it wherever both are wrong."""
    outcomes = _load_outcomes()
    assert outcomes.GATE_SETTLED_PATTERNS == EXPECTED_GATE_SETTLED_PATTERNS


def test_stack_fact_group_matches_the_hand_typed_literal() -> None:
    outcomes = _load_outcomes()
    assert outcomes.STACK_FACT_PATTERNS == EXPECTED_STACK_FACT_PATTERNS


def test_the_two_groups_are_disjoint_and_union_to_the_21_catalogue_directories() -> None:
    """The union check alone cannot catch a swap between the two groups (see
    the two tests above for that); it still has to hold, since it is what
    ties the table to the real catalogue rather than to a stale count."""
    outcomes = _load_outcomes()
    gate_settled = frozenset().union(*outcomes.GATE_SETTLED_PATTERNS.values())
    stack_facts = outcomes.STACK_FACT_PATTERNS

    assert gate_settled & stack_facts == frozenset(), (
        f"patterns in both groups: {gate_settled & stack_facts}"
    )

    catalogue_names = visible_dir_names(CATALOGUE_DIR)
    assert gate_settled | stack_facts == catalogue_names, (
        f"union does not match catalogue directories: "
        f"missing={catalogue_names - (gate_settled | stack_facts)}, "
        f"extra={(gate_settled | stack_facts) - catalogue_names}"
    )
    assert len(gate_settled) == 13
    assert len(stack_facts) == 8


@pytest.mark.parametrize("fixture", discover_fixtures(), ids=lambda f: f.name)
def test_no_fixtures_auto_or_baseline_names_a_gate_settled_pattern(fixture) -> None:
    """Corpus-wide guard for the leak `decide()` now raises on: `auto` or
    `baseline` naming one of the 13 gate-settled patterns instead of one of
    the 8 stack facts.

    Why this is not already covered by the existing corpus comparisons in
    `test_patterns_detect.py`: those assert each fixture's `auto`/`baseline`
    against its *own* hand-written `expected.json`, and none of those 26
    expectations happens to contain a gate-settled name -- so the absence is
    enforced by coincidence of what the fixture authors wrote, not as an
    invariant. A new fixture whose author mistakenly listed `ddd` under
    `auto`, or a `detect()` regression that starts proposing one, would
    satisfy every per-fixture comparison and slip through. This test runs
    the real `detect()` against every real fixture `repo/` and checks the
    one thing those comparisons do not: that `auto ∪ baseline` never
    contains a name outside `STACK_FACT_PATTERNS`, regardless of what any
    `expected.json` says."""
    outcomes = _load_outcomes()
    detect = _load_detect()

    report = detect.detect(fixture.repo_dir)
    fired = {p["pattern"] for p in report["auto"]} | {p["pattern"] for p in report["baseline"]}

    leaked = fired - outcomes.STACK_FACT_PATTERNS
    assert not leaked, (
        f"{fixture.name}: auto/baseline named a gate-settled pattern, not a stack fact: {sorted(leaked)}"
    )


def test_decide_raises_when_auto_names_a_gate_settled_pattern() -> None:
    """The other half of the same guard, at the point `decide()` itself can
    be called with a bad report -- a hand-built one here, not a fixture, so
    this does not depend on `detect()` ever actually producing this shape.
    `decide()` must refuse rather than silently drop the leaked name from
    `installed`, which would otherwise leave the four sets summing to 21 and
    looking exactly like a clean partition."""
    outcomes = _load_outcomes()
    report = {
        "auto": [{"pattern": "ddd", "evidence": "constructed"}],
        "baseline": [],
        "gates": {"q1_backend": False, "q2_architecture": False, "q3_test_quality": False},
    }

    with pytest.raises(ValueError, match="ddd"):
        outcomes.decide(report, answers={})


def test_decide_raises_when_baseline_names_a_gate_settled_pattern() -> None:
    """Same guard, the `baseline` side -- `decide()`'s raise names which
    field the leak came from, so this and the test above must each name a
    different field in the message, not just the pattern."""
    outcomes = _load_outcomes()
    report = {
        "auto": [],
        "baseline": [{"pattern": "mutation-testing", "evidence": "constructed", "surface": False}],
        "gates": {"q1_backend": False, "q2_architecture": False, "q3_test_quality": False},
    }

    with pytest.raises(ValueError, match="baseline"):
        outcomes.decide(report, answers={})


def _powerset(items) -> list[frozenset[str]]:
    """Every subset of `items`, as frozensets -- each open gate is
    multiSelect, so any subset of its settled patterns (including none of
    them, and all of them) is an answer a user could actually give. Q1/Q2/Q3
    settle 6/5/2 patterns, so this yields 64/32/4 subsets respectively --
    small enough to enumerate exhaustively rather than sample
    `[ref: SDD/Runtime View/Complex Logic]`."""
    ordered = sorted(items)
    subsets = []
    for r in range(len(ordered) + 1):
        subsets.extend(frozenset(c) for c in itertools.combinations(ordered, r))
    return subsets


def _assert_decided_exactly_once(outcome, all_names: frozenset[str]) -> None:
    """The shared check: the four sets are pairwise disjoint and their union
    is exactly `all_names`. Shared between the exhaustive sweep below and the
    two seeded-failure tests, so both exercise the identical assertion that
    production code must satisfy."""
    groups = {
        "installed": outcome.installed,
        "declined_by_question": outcome.declined_by_question,
        "excluded_by_stack_fact": outcome.excluded_by_stack_fact,
        "not_reached": outcome.not_reached,
    }

    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str, str]] = []
    for label, members in groups.items():
        for name in members:
            if name in seen:
                duplicates.append((name, seen[name], label))
            else:
                seen[name] = label

    assert not duplicates, f"decided more than once: {duplicates}"

    missing = all_names - set(seen)
    assert not missing, f"decided zero times (not in any of the four sets): {sorted(missing)}"

    extra = set(seen) - all_names
    assert not extra, f"decided for a name outside the 21: {sorted(extra)}"


def _answer_combinations(report: dict, gate_settled_patterns: dict[str, frozenset[str]]):
    """Every combination of answers to `report`'s **open** gates, generated
    over the answer space rather than written per case
    `[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/
    phase-2.md#T2.5]`. A fixture with no gate open yields exactly one
    combination (the empty answer set); one open gate yields as many as that
    gate's power set; two yields the product."""
    open_gates = [g for g in gate_settled_patterns if report["gates"].get(g)]
    per_gate_subsets = [_powerset(gate_settled_patterns[g]) for g in open_gates]
    for combo in itertools.product(*per_gate_subsets):
        yield dict(zip(open_gates, combo))


@pytest.mark.parametrize("fixture", discover_fixtures(), ids=lambda f: f.name)
def test_every_answer_combination_decides_each_of_the_21_exactly_once(fixture) -> None:
    """The core invariant, F3's fourth acceptance criterion
    `[ref: PRD/F3 4th; SDD/AC-6]`: for every fixture and for every
    combination of answers to its open gates, all 21 pattern names are
    decided exactly once across the four outcome sets. Generated over the
    full answer space (not sampled) because the invariant must hold for
    every combination, and a sampled one that holds says nothing about the
    rest `[ref: SDD/Runtime View/Complex Logic]`."""
    outcomes = _load_outcomes()
    detect = _load_detect()

    report = detect.detect(fixture.repo_dir)

    combos = list(_answer_combinations(report, outcomes.GATE_SETTLED_PATTERNS))
    assert combos, f"{fixture.name}: no answer combinations generated at all"

    for answers in combos:
        outcome = outcomes.decide(report, answers)
        _assert_decided_exactly_once(outcome, outcomes.ALL_PATTERN_NAMES)


def test_not_reached_is_non_empty_for_a_fixture_where_no_gate_opens_all_three() -> None:
    """Measured 2026-10-04 against the real corpus: all 26 fixtures leave a
    non-empty fourth set under every answer combination, because none of
    them opens all three gates. `edge-bare-repository` closes all three, so
    its `not_reached` set is the full 13 -- picked because it needs no
    assumption about which gates a more elaborate fixture happens to open."""
    outcomes = _load_outcomes()
    detect = _load_detect()

    fixtures = {f.name: f for f in discover_fixtures()}
    fixture = fixtures["edge-bare-repository"]
    report = detect.detect(fixture.repo_dir)

    assert report["gates"] == {"q1_backend": False, "q2_architecture": False, "q3_test_quality": False}

    outcome = outcomes.decide(report, {})
    assert outcome.not_reached == frozenset().union(*outcomes.GATE_SETTLED_PATTERNS.values())
    assert len(outcome.not_reached) == 13


def test_not_reached_is_empty_for_a_constructed_report_with_every_gate_open() -> None:
    """No fixture in the corpus opens all three gates, so this case needs a
    constructed report rather than a fixture
    `[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/
    phase-2.md#T2.5]`. Neither `not_reached` empty nor `not_reached`
    non-empty should be true of this suite by accident -- the fixture test
    above covers non-empty, and this one covers empty."""
    outcomes = _load_outcomes()
    report = {
        "schema": 1,
        "repo": "/constructed/does-not-exist",
        "auto": [],
        "baseline": [],
        "gates": {"q1_backend": True, "q2_architecture": True, "q3_test_quality": True},
        "gate_evidence": {
            "q1_backend": ["constructed"],
            "q2_architecture": ["constructed"],
            "q3_test_quality": ["constructed"],
        },
        "manifests_walked": [],
        "unrecognised_stack": True,
    }

    outcome = outcomes.decide(report, answers={})
    assert outcome.not_reached == frozenset()
    _assert_decided_exactly_once(outcome, outcomes.ALL_PATTERN_NAMES)


def test_closed_gate_is_not_reached_even_if_answers_names_it() -> None:
    """A closed gate yields no question, so there is nothing to have
    answered -- an `answers` entry for a closed gate (a caller mistake, or a
    stale answer carried from a previous run) must not be allowed to move
    that gate's patterns out of `not_reached`
    `[ref: SDD/Runtime View/Complex Logic]`."""
    outcomes = _load_outcomes()
    report = {
        "auto": [],
        "baseline": [],
        "gates": {"q1_backend": False, "q2_architecture": False, "q3_test_quality": False},
    }
    one_q1_pattern = next(iter(outcomes.GATE_SETTLED_PATTERNS["q1_backend"]))

    outcome = outcomes.decide(report, answers={"q1_backend": {one_q1_pattern}})

    assert one_q1_pattern in outcome.not_reached
    assert one_q1_pattern not in outcome.installed
    assert outcome.not_reached == frozenset().union(*outcomes.GATE_SETTLED_PATTERNS.values())


def test_invariant_fails_on_a_seeded_double_assignment() -> None:
    """A pattern decided by two sets at once must fail the shared check --
    an invariant test that cannot fail is decoration
    `[ref: SDD/Quality Requirements]`. Built from a real fixture's real
    partition and then corrupted by one move, rather than from scratch, so
    the seed is realistic rather than a toy shape the check happens to
    recognise."""
    outcomes = _load_outcomes()
    detect = _load_detect()

    fixtures = {f.name: f for f in discover_fixtures()}
    fixture = fixtures["edge-bare-repository"]
    report = detect.detect(fixture.repo_dir)
    outcome = outcomes.decide(report, answers={})

    duplicated = next(iter(outcome.not_reached))
    corrupted = outcomes.Outcomes(
        installed=outcome.installed | {duplicated},  # now also claimed installed
        declined_by_question=outcome.declined_by_question,
        excluded_by_stack_fact=outcome.excluded_by_stack_fact,
        not_reached=outcome.not_reached,
    )

    with pytest.raises(AssertionError, match="decided more than once"):
        _assert_decided_exactly_once(corrupted, outcomes.ALL_PATTERN_NAMES)


def test_invariant_fails_on_a_seeded_omission() -> None:
    """A pattern assigned to none of the four sets must fail the shared
    check. This is the failure mode the three-set formulation had in every
    one of the 26 fixtures -- a check that only catches double-assignment
    would have passed the broken specification
    `[ref: SDD/AC-6]`. Built from a real fixture's real partition and then
    corrupted by dropping one member, for the same reason as the
    double-assignment test above."""
    outcomes = _load_outcomes()
    detect = _load_detect()

    fixtures = {f.name: f for f in discover_fixtures()}
    fixture = fixtures["edge-bare-repository"]
    report = detect.detect(fixture.repo_dir)
    outcome = outcomes.decide(report, answers={})

    omitted = next(iter(outcome.not_reached))
    corrupted = outcomes.Outcomes(
        installed=outcome.installed,
        declined_by_question=outcome.declined_by_question,
        excluded_by_stack_fact=outcome.excluded_by_stack_fact,
        not_reached=outcome.not_reached - {omitted},  # now decided nowhere
    )

    with pytest.raises(AssertionError, match="decided zero times"):
        _assert_decided_exactly_once(corrupted, outcomes.ALL_PATTERN_NAMES)
