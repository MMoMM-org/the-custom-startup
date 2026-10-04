"""T2.1 (spec-020): corpus-integrity tests for the patterns-detection fixture corpus.

Why this exists: the PRD's top risk is that detection rules get authored and graded
by the same party (SDD/Phase 2 context), so T2.1 writes the fixtures from the written
rules -- SDD/Detection rules: the eight stack facts and the three gates, and SDD/The
seven traps, numbered -- before any detector exists. This file is the loader half of
that gate: it proves the corpus itself is well-formed (right count, every case shaped
correctly, every pattern name real) independently of whether `detect.py` has been
written yet. It must stay green with or without `detect.py` present -- the detector
comparison itself lives in `test_patterns_detect.py`, which does import `detect` and
is expected to fail collection until T2.2.

Three guards are mandatory here (task text step 2), each measured on 2026-10-03
against this repo's pytest, each defending a specific way a fixture-corpus test goes
quietly green over nothing:

  1. corpus size is asserted in `test_corpus_has_exactly_the_expected_number_of_cases`, standalone and
     non-parametrized. A bare `for` loop over an empty glob reports `1 passed` (the
     body never runs); `@pytest.mark.parametrize` over the same empty glob reports
     `1 skipped` at exit 0 ("got empty parameter set") -- a green suite of zero
     cases. Asserting `len(fixtures) == EXPECTED_CASE_COUNT` directly, never only as a parametrize
     source, is the only shape that fails loudly when the corpus is short or empty.
  2. `repo/` and `expected.json` existence is checked per fixture, in
     `test_every_fixture_has_repo_and_expected_json`, BEFORE either is read -- a
     missing file reports as a missing file, not as a JSON parse error or a
     silently-empty-repo false pass.
  3. every validation failure across every fixture is accumulated and asserted once
     at the end (`test_every_expected_json_parses_and_has_the_declared_shape` and
     `test_every_pattern_named_in_any_fixture_is_one_of_the_21`), so eight bad
     pattern names are reported as eight, not as the first one with the rest hidden
     behind it.
"""

from __future__ import annotations

import json

from patterns_detection_corpus_lib import (
    CATALOGUE_DIR,
    CORPUS_DIR,
    EXPECTED_CASE_COUNT,
    catalogue_pattern_names,
    discover_fixtures,
    load_expected,
)

EXPECTED_SHAPE_KEYS = {"why", "auto", "baseline", "gates", "must_not_propose", "unrecognised_stack"}
EXPECTED_GATE_KEYS = {"q1_backend", "q2_architecture", "q3_test_quality"}


def test_corpus_directory_exists() -> None:
    assert CORPUS_DIR.is_dir(), f"{CORPUS_DIR} does not exist -- no fixtures were written"


def test_corpus_has_exactly_the_expected_number_of_cases() -> None:
    """Guard 1 -- standalone and non-parametrized. Never `>=`, and never only as a
    parametrize source: an empty or short corpus must fail THIS assertion, not skip
    quietly or pass with an unexercised loop body."""
    fixtures = discover_fixtures()
    names = sorted(f.name for f in fixtures)
    assert len(fixtures) == EXPECTED_CASE_COUNT, (
        f"expected exactly {EXPECTED_CASE_COUNT} fixtures, found {len(fixtures)}: {names}"
    )


def test_catalogue_has_pattern_names_to_validate_against() -> None:
    """The 21 names must be readable from the catalogue, or every other test in this
    file that validates a fixture's pattern names against it is vacuously trivial."""
    names = catalogue_pattern_names()
    assert len(names) == 21, (
        f"expected 21 pattern directories under {CATALOGUE_DIR}, found {len(names)}: {sorted(names)}"
    )


def test_every_fixture_has_repo_and_expected_json() -> None:
    """Guard 2 -- existence checked before either path is validated, and every
    missing path across every fixture is reported, not just the first."""
    fixtures = discover_fixtures()
    assert fixtures, "no fixtures discovered -- see test_corpus_has_exactly_the_expected_number_of_cases"

    missing: list[str] = []
    for fixture in fixtures:
        if not fixture.repo_dir.is_dir():
            missing.append(f"{fixture.name}: missing repo/")
        if not fixture.expected_path.is_file():
            missing.append(f"{fixture.name}: missing expected.json")

    assert not missing, "fixtures missing required paths:\n" + "\n".join(missing)


def test_every_expected_json_parses_and_has_the_declared_shape() -> None:
    """Every `expected.json` parses as JSON and declares exactly the fixture-expectation
    keys (SDD/Data model: fixture expectation) -- no more, no fewer -- and `gates`
    declares exactly the three gate keys. Guard 3: every failure across every fixture
    is collected and asserted once."""
    fixtures = discover_fixtures()
    assert fixtures, "no fixtures discovered -- see test_corpus_has_exactly_the_expected_number_of_cases"

    failures: list[str] = []
    for fixture in fixtures:
        try:
            expected = load_expected(fixture)
        except json.JSONDecodeError as exc:
            failures.append(f"{fixture.name}: expected.json does not parse as JSON ({exc})")
            continue

        if not isinstance(expected, dict):
            failures.append(f"{fixture.name}: expected.json is not a JSON object")
            continue

        keys = set(expected)
        if keys != EXPECTED_SHAPE_KEYS:
            failures.append(
                f"{fixture.name}: expected.json keys {sorted(keys)} != {sorted(EXPECTED_SHAPE_KEYS)}"
            )
            continue

        gate_keys = set(expected.get("gates", {}))
        if gate_keys != EXPECTED_GATE_KEYS:
            failures.append(f"{fixture.name}: gates keys {sorted(gate_keys)} != {sorted(EXPECTED_GATE_KEYS)}")

    assert not failures, "expected.json shape violations:\n" + "\n".join(failures)


def test_every_pattern_named_in_any_fixture_is_one_of_the_21() -> None:
    """Every pattern name appearing in any fixture's `auto`, `baseline` or
    `must_not_propose` list must be one of the names read from the catalogue -- not
    hardcoded here, and not a typo. Guard 3: a typo must fail loudly -- every bad
    name across every fixture is reported together, not just the first."""
    valid_names = catalogue_pattern_names()
    assert valid_names, "no pattern names available -- see test_catalogue_has_pattern_names_to_validate_against"

    fixtures = discover_fixtures()
    assert fixtures, "no fixtures discovered -- see test_corpus_has_exactly_the_expected_number_of_cases"

    failures: list[str] = []
    for fixture in fixtures:
        expected = load_expected(fixture)
        for field in ("auto", "baseline", "must_not_propose"):
            for name in expected.get(field, []):
                if name not in valid_names:
                    failures.append(f"{fixture.name}: {field!r} names unknown pattern {name!r}")

    assert not failures, "fixtures reference unknown pattern names:\n" + "\n".join(failures)


def test_auto_and_baseline_are_disjoint_per_fixture() -> None:
    """Each of the 21 is decided exactly once, by a file signal or by one question,
    never both (PRD business rule) -- no fixture should declare the same name in
    both `auto` and `baseline`."""
    fixtures = discover_fixtures()
    assert fixtures, "no fixtures discovered -- see test_corpus_has_exactly_the_expected_number_of_cases"

    failures: list[str] = []
    for fixture in fixtures:
        expected = load_expected(fixture)
        overlap = set(expected.get("auto", [])) & set(expected.get("baseline", []))
        if overlap:
            failures.append(f"{fixture.name}: pattern(s) in both auto and baseline: {sorted(overlap)}")

    assert not failures, "fixtures with overlapping auto/baseline:\n" + "\n".join(failures)


def test_must_not_propose_is_disjoint_from_auto_per_fixture() -> None:
    """`must_not_propose` is deliberately redundant against `auto` (SDD/Data model:
    fixture expectation) -- a name listed as defended against must not also appear
    in the same fixture's own `auto` list, which would be self-contradictory."""
    fixtures = discover_fixtures()
    assert fixtures, "no fixtures discovered -- see test_corpus_has_exactly_the_expected_number_of_cases"

    failures: list[str] = []
    for fixture in fixtures:
        expected = load_expected(fixture)
        overlap = set(expected.get("auto", [])) & set(expected.get("must_not_propose", []))
        if overlap:
            failures.append(f"{fixture.name}: pattern(s) in both auto and must_not_propose: {sorted(overlap)}")

    assert not failures, "fixtures with self-contradictory must_not_propose:\n" + "\n".join(failures)


def test_unrecognised_stack_equals_auto_is_empty() -> None:
    """`unrecognised_stack` is computed from `auto` alone (SDD/Data model: detection
    report, ADR-5): it is true IFF `auto` is empty, with no legitimate inverse. A
    hand-rolled architecture can open q2 with no stack fact firing (`auto: []`) and
    that case still reports `unrecognised_stack: true` -- `trap-06-hand-rolled-
    architecture`'s own `why` says so verbatim. "q2 can open with no stack fact" is
    true; "therefore the flag may be false" is exactly the gate-opened-means-
    recognised conflation ADR-5 forbids. Both directions are asserted, not one."""
    fixtures = discover_fixtures()
    assert fixtures, "no fixtures discovered -- see test_corpus_has_exactly_the_expected_number_of_cases"

    failures: list[str] = []
    for fixture in fixtures:
        expected = load_expected(fixture)
        auto_is_empty = not expected.get("auto")
        unrecognised = expected.get("unrecognised_stack")
        if unrecognised is not auto_is_empty:
            failures.append(
                f"{fixture.name}: auto empty={auto_is_empty} but unrecognised_stack={unrecognised!r}"
            )

    assert not failures, "fixtures where unrecognised_stack does not equal (auto is empty):\n" + "\n".join(
        failures
    )


def test_each_trap_fixture_names_its_trap_number_and_defends_something() -> None:
    """Task text step 3: each of the seven trap fixtures names its trap in `why` and
    lists `must_not_propose`."""
    fixtures = {f.name: f for f in discover_fixtures()}
    trap_names = [name for name in fixtures if name.startswith("trap-")]
    assert len(trap_names) == 7, f"expected 7 trap fixtures, found {len(trap_names)}: {sorted(trap_names)}"

    failures: list[str] = []
    for name in sorted(trap_names):
        expected = load_expected(fixtures[name])
        trap_number = name.split("-")[1]
        if f"trap {int(trap_number)}" not in expected.get("why", ""):
            failures.append(f"{name}: why does not name its trap number ({trap_number})")
        if not expected.get("must_not_propose"):
            failures.append(f"{name}: must_not_propose is empty")

    assert not failures, "trap fixtures missing required content:\n" + "\n".join(failures)
