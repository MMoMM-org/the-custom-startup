"""T2.1 (spec-020): the fixture corpus measured against the not-yet-built detector.

Why this exists: the PRD's top risk is that detection rules are authored and graded
by the same party. This file is written against `detect.py` before that module
exists, so every one of the 18 fixtures in `tests/fixtures/patterns-detection/`
fails for want of a detector rather than passing by construction -- the RED half of
T2.1's TDD gate. `detect.py` lands in T2.2 (SDD/Building Block View, C2 -- "pure,
fixture-callable"); until then this module fails to COLLECT at all, which is the
point: `import detect` below is deliberately module-level, not lazily caught inside
a test body, so `pytest tests/test_patterns_detect.py` reports `ERROR collecting` at
exit code 2 -- distinguishable from the ordinary exit-1 failure of a false
assertion, and from the exit-0 `1 skipped` a parametrize-over-an-empty-glob would
report if the corpus itself were broken instead.

Corpus-integrity (shape, count, pattern-name validity) is deliberately NOT
re-checked here -- `test_patterns_detection_corpus.py` owns that, does not import
`detect`, and keeps reporting pass/fail on the corpus itself even while this file
cannot collect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from patterns_detection_corpus_lib import REPO_ROOT, discover_fixtures, load_expected

LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"
sys.path.insert(0, str(LIB_DIR))

import detect  # noqa: E402  -- intentionally module-level and unguarded: `detect.py`
# does not exist until T2.2, so this import failing IS T2.1's verifiable RED state.


def _fixture_ids() -> list[str]:
    return [f.name for f in discover_fixtures()]


@pytest.mark.parametrize("fixture", discover_fixtures(), ids=_fixture_ids())
def test_detector_matches_expected(fixture) -> None:
    """The normalised report must equal the fixture's declared verdict exactly -- an
    unexpected extra proposal fails just as loudly as a missing one (SDD/Data model:
    fixture expectation)."""
    expected = load_expected(fixture)
    report = detect.detect(fixture.repo_dir)

    auto_names = {entry["pattern"] for entry in report["auto"]}
    baseline_names = {entry["pattern"] for entry in report["baseline"]}

    assert auto_names == set(expected["auto"]), fixture.name
    assert baseline_names == set(expected["baseline"]), fixture.name
    assert report["gates"] == expected["gates"], fixture.name
    assert report["unrecognised_stack"] == expected["unrecognised_stack"], fixture.name
    assert auto_names.isdisjoint(expected["must_not_propose"]), fixture.name
