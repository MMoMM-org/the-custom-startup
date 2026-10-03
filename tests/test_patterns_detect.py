"""T2.1 (spec-020): the fixture corpus measured against the not-yet-built detector.

Why this exists: the PRD's top risk is that detection rules are authored and graded
by the same party. This file is written against `detect.py` before that module
exists, so every one of the 18 fixtures in `tests/fixtures/patterns-detection/`
fails for want of a detector rather than passing by construction -- the RED half of
T2.1's TDD gate. `detect.py` lands in T2.2 (SDD/Building Block View, C2 -- "pure,
fixture-callable").

The import of `detect` happens at RUNTIME, inside each test, not at module level.
T2.1's own success criterion is "18 fixtures collected, all failing for the right
reason" -- a module-level import would collect ZERO cases (an `ImportError` at
import time aborts collection for the whole file) and would abort the entire
`pytest -q` run besides, since one file's collection error stops the whole session
by default. A per-test import gives the actual required RED state instead:
`pytest tests/test_patterns_detect.py -q` reports 18 collected, 18 failed, exit 1 --
each one failing with `ModuleNotFoundError`/`ImportError` for want of a detector,
distinguishable from a false assertion only by its traceback, not by its exit code
or collected count. The earlier module-level version of this file (exit 2, 0
collected) was measured and reported, then corrected once it was checked against
this task's own success criterion.

Corpus-integrity (shape, pattern-name validity) is deliberately NOT re-checked
here -- `test_patterns_detection_corpus.py` owns that, does not import `detect`,
and keeps reporting pass/fail on the corpus itself regardless of whether the
detector exists. The corpus SIZE, however, is guarded again below, standalone and
non-parametrized: this file parametrizes over `discover_fixtures()` with no count
check of its own, so if the corpus directory ever vanished or emptied while this
file is run alone (`pytest tests/test_patterns_detect.py -q`, exactly the command
this module's own history cites), `@pytest.mark.parametrize` over an empty list
reports `1 skipped` at exit 0 -- the same "got empty parameter set" false-green
this suite's other guards exist to catch, just relocated to this file instead of
the corpus one. `test_corpus_is_not_empty_here_either` closes that.

This file also guards trap 1 directly: the report's `baseline` entries must carry
`surface: False` (SDD/Data model: detection report; SDD/The seven traps, numbered
-- trap 1 "changes a report field rather than suppressing a proposal"). Checking
only `entry["pattern"]` would let a detector that sets `surface: True` on
`testing` pass every fixture here while surfacing it to the user as a
recommendation -- trap 1, reintroduced, invisible to this corpus. The invariant
is asserted directly rather than added to `expected.json`: `surface` is false for
every baseline entry by definition, not per-case data, so encoding it in the
fixture would duplicate a constant and widen the exact-key shape guard in
`test_patterns_detection_corpus.py` for no reason.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest

from patterns_detection_corpus_lib import EXPECTED_CASE_COUNT, REPO_ROOT, discover_fixtures, load_expected

LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"


def _load_detect() -> ModuleType:
    """Imports `detect` at call time, not at module import time, so its absence
    (until T2.2) fails the individual test that calls this, not collection of the
    whole file."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("detect")


def _fixture_ids() -> list[str]:
    return [f.name for f in discover_fixtures()]


def test_corpus_is_not_empty_here_either() -> None:
    """Standalone and non-parametrized, mirroring `test_patterns_detection_corpus.py
    ::test_corpus_has_exactly_18_cases` -- this file parametrizes over the same
    corpus but has no count guard of its own, so a vanished or emptied corpus must
    fail THIS assertion when this file is run alone, not skip quietly at exit 0."""
    fixtures = discover_fixtures()
    names = sorted(f.name for f in fixtures)
    assert len(fixtures) == EXPECTED_CASE_COUNT, (
        f"expected exactly {EXPECTED_CASE_COUNT} fixtures, found {len(fixtures)}: {names}"
    )


@pytest.mark.parametrize("fixture", discover_fixtures(), ids=_fixture_ids())
def test_detector_matches_expected(fixture) -> None:
    """The normalised report must equal the fixture's declared verdict exactly -- an
    unexpected extra proposal fails just as loudly as a missing one (SDD/Data model:
    fixture expectation)."""
    detect = _load_detect()
    expected = load_expected(fixture)
    report = detect.detect(fixture.repo_dir)

    auto_names = {entry["pattern"] for entry in report["auto"]}
    baseline_names = {entry["pattern"] for entry in report["baseline"]}

    assert auto_names == set(expected["auto"]), fixture.name
    assert baseline_names == set(expected["baseline"]), fixture.name
    assert report["gates"] == expected["gates"], fixture.name
    assert report["unrecognised_stack"] == expected["unrecognised_stack"], fixture.name
    assert auto_names.isdisjoint(expected["must_not_propose"]), fixture.name

    non_surfaced = [entry["pattern"] for entry in report["baseline"] if entry.get("surface") is not False]
    assert not non_surfaced, f"{fixture.name}: baseline entries not surface:false: {non_surfaced}"
