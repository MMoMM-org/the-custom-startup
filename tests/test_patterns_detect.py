"""T2.1 (spec-020): the fixture corpus measured against the not-yet-built detector.

Why this exists: the PRD's top risk is that detection rules are authored and graded
by the same party. This file is written against `detect.py` before that module
exists, so every one of the fixtures in `tests/fixtures/patterns-detection/`
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
import pathlib
import sys
from types import ModuleType

import pytest

from patterns_detection_corpus_lib import EXPECTED_CASE_COUNT, REPO_ROOT, discover_fixtures, load_expected

LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"


def _load_detect() -> ModuleType:
    """Imports `detect` at call time, not at module import time, so its absence
    (until T2.2) fails the individual test that calls this, not collection of the
    whole file.

    **Mutation-testing this module: do not point `PYTHONPATH` at a mutated copy.**
    The `sys.path.insert(0, ...)` below puts `LIB_DIR` ahead of everything
    `PYTHONPATH` contributes, so a harness that copies `detect.py` elsewhere,
    mutates it and sets `PYTHONPATH` loads the **unmutated** module and reports
    the mutant as survived. A false SURVIVED is invisible -- it looks exactly
    like a well-behaved test suite. Found 2026-10-04 by a reviewer who hit it.
    Load a mutated copy with `importlib.util.spec_from_file_location` against its
    real path instead, and copy to a scratch directory rather than mutating the
    working tree -- a file here may belong to an agent that is still editing it,
    which was the other half of the same day's lesson."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("detect")


def _fixture_ids() -> list[str]:
    return [f.name for f in discover_fixtures()]


def test_corpus_is_not_empty_here_either() -> None:
    """Standalone and non-parametrized, mirroring `test_patterns_detection_corpus.py
    ::test_corpus_has_exactly_the_expected_number_of_cases` -- this file parametrizes over the same
    corpus but has no count guard of its own, so a vanished or emptied corpus must
    fail THIS assertion when this file is run alone, not skip quietly at exit 0."""
    fixtures = discover_fixtures()
    names = sorted(f.name for f in fixtures)
    assert len(fixtures) == EXPECTED_CASE_COUNT, (
        f"expected exactly {EXPECTED_CASE_COUNT} fixtures, found {len(fixtures)}: {names}"
    )


# Deliberately duplicated from detect.py's own `SKIP_DIRS`, not imported --
# the same reasoning `EXPECTED_MANIFEST_NAMES` below gives for its own
# duplication: if this were `frozenset(detect.SKIP_DIRS)` instead, a future
# NARROWING of `SKIP_DIRS` (accidentally dropping `.claude`, say) would
# narrow this check right along with it, so the detector could start citing
# evidence from inside `.claude` again and this invariant would agree with
# it by construction. Kept independent, it still catches that.
#
# The opposite drift -- `SKIP_DIRS` WIDENED without updating this literal --
# is exactly what happened here: `.git` and `.claude` were added to
# `detect.py:83` (spec-020 T2.6 follow-up, 2026-10-04) while this stayed at
# four, so a proposal citing a path inside either would have gone
# unasserted. `test_excluded_segments_matches_skip_dirs` below catches that
# direction instead, asserting equality explicitly rather than by sharing
# the value -- so the next addition to either side fails loudly here,
# naming exactly which literal is behind.
EXCLUDED_SEGMENTS = frozenset({"node_modules", ".venv", "venv", "vendor", ".git", ".claude"})


def test_excluded_segments_matches_skip_dirs() -> None:
    """The two drift risks the comment above describes are different
    directions of the same mistake; this test is the standing guard against
    the second one (`SKIP_DIRS` widened, this file not updated to match),
    which is the one that just happened. It does not protect against the
    first (a narrowing) -- that is `EXCLUDED_SEGMENTS` staying independent,
    not this test, and is why this asserts equality rather than replacing
    the literal with a derived one."""
    detect = _load_detect()
    assert EXCLUDED_SEGMENTS == frozenset(detect.SKIP_DIRS), (
        f"tests/test_patterns_detect.py's EXCLUDED_SEGMENTS {sorted(EXCLUDED_SEGMENTS)} "
        f"no longer matches detect.py's SKIP_DIRS {sorted(detect.SKIP_DIRS)} -- "
        "update EXCLUDED_SEGMENTS (and its evidence invariants) to match"
    )


def _evidence_problems(entry: dict, repo_dir) -> list[str]:
    """The three `evidence` invariants, per SDD/Data model: fixture expectation.

    `evidence` is asserted as an invariant rather than declared per fixture:
    exact paths would add a key the corpus's exact-shape guard rejects and pin every
    fixture to incidental strings. Nothing asserted `evidence` at all until this
    was added -- a detector emitting `evidence: ""` satisfied every fixture while
    failing T2.2's first success criterion, which is PRD/F2 1st.

    Dependency evidence is formatted `"packages/server/package.json: dependencies.foo"`,
    so the path is everything before the first ": ".
    """
    ev = entry.get("evidence", "")
    problems: list[str] = []
    if not isinstance(ev, str) or not ev.strip():
        return ["%s: evidence is empty" % entry.get("pattern")]

    path_part = ev.split(": ", 1)[0]
    if not (pathlib.Path(repo_dir) / path_part).exists():
        problems.append("%s: evidence path does not exist in repo/: %r"
                        % (entry.get("pattern"), path_part))
    hit = EXCLUDED_SEGMENTS.intersection(pathlib.PurePath(path_part).parts)
    if hit:
        problems.append("%s: evidence cites an excluded directory (%s): %r"
                        % (entry.get("pattern"), ",".join(sorted(hit)), path_part))
    return problems


GATE_NAMES = ("q1_backend", "q2_architecture", "q3_test_quality")


def _gate_evidence_problems(report: dict, repo_dir) -> list[str]:
    """The two `gate_evidence` invariants, per SDD/Interface Specifications
    (Data model: detection report; the `gate_evidence` clauses under Data
    model: fixture expectation). No `expected.json` declares `gate_evidence`
    -- the exact-key shape guard in `test_patterns_detection_corpus.py` would
    reject one -- so this is asserted universally rather than per fixture,
    the same treatment `evidence` already gets above:

    1. every gate reported **open** has a non-empty `gate_evidence` entry,
       and each path it cites resolves inside `repo_dir` and avoids the
       excluded directories (same path-part rule as `_evidence_problems`:
       everything before the first `": "`);
    2. every gate reported **closed** carries no entry -- a gate cannot be
       justified by evidence it did not act on.

    Without this, T2.3 could emit `{}` for every fixture (as the T2.2
    placeholder effectively did) and still satisfy every comparison in
    `test_detector_matches_expected`, since `expected.json` has no
    `gate_evidence` key for that function to compare against."""
    problems: list[str] = []
    gates = report.get("gates", {})
    gate_evidence = report.get("gate_evidence", {})
    for name in GATE_NAMES:
        entries = gate_evidence.get(name)
        if gates.get(name):
            if not entries:
                problems.append("%s: open gate has no gate_evidence entry" % name)
                continue
            for entry in entries:
                if not isinstance(entry, str) or not entry.strip():
                    problems.append("%s: gate_evidence entry is empty" % name)
                    continue
                path_part = entry.split(": ", 1)[0]
                if not (pathlib.Path(repo_dir) / path_part).exists():
                    problems.append("%s: gate_evidence path does not exist in repo/: %r"
                                    % (name, path_part))
                hit = EXCLUDED_SEGMENTS.intersection(pathlib.PurePath(path_part).parts)
                if hit:
                    problems.append("%s: gate_evidence cites an excluded directory (%s): %r"
                                    % (name, ",".join(sorted(hit)), path_part))
        elif entries:
            problems.append("%s: closed gate carries gate_evidence: %r" % (name, entries))
    return problems


# Deliberately duplicated from detect.py's own `DEPENDENCY_MANIFEST_NAMES`,
# not imported: this is the one constant where importing it would defeat the
# whole point of the invariant below. If `detect.py`'s set is ever narrowed
# back to the original three names, this hardcoded copy must NOT move with
# it -- that is what makes the completeness check below able to fail at all,
# rather than silently re-deriving "whatever detect.py currently walks" and
# always agreeing with it by construction.
EXPECTED_MANIFEST_NAMES = frozenset({"package.json", "pyproject.toml", "go.mod", "requirements.txt", "setup.py"})


def _expected_manifests_walked(repo_dir) -> list[str]:
    """Every file under `repo_dir` whose basename is a dependency-manifest
    name, computed independently of `detect.py` by walking the fixture tree
    directly, excluding any path with a segment in `EXCLUDED_SEGMENTS`.
    `manifests_walked` exists so that a missing signal is explicable
    (SDD/Detection rules), and that job is satisfied exactly by this set --
    every such manifest that exists and was not excluded, named relative to
    `repo_dir`."""
    root = pathlib.Path(repo_dir)
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in EXPECTED_MANIFEST_NAMES:
            continue
        rel = path.relative_to(root)
        if EXCLUDED_SEGMENTS.intersection(rel.parts):
            continue
        found.append(rel.as_posix())
    return sorted(found)


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

    # manifests_walked completeness invariant: not per-fixture data (no
    # expected.json mentions it), asserted universally instead, against a
    # set of names this file owns independently of detect.py.
    assert report["manifests_walked"] == _expected_manifests_walked(fixture.repo_dir), fixture.name

    # The three `evidence` invariants. Accumulated so every bad entry reports,
    # not just the first.
    evidence_problems: list[str] = []
    for entry in list(report["auto"]) + list(report["baseline"]):
        evidence_problems.extend(_evidence_problems(entry, fixture.repo_dir))
    assert not evidence_problems, (
        "%s: evidence invariants violated:\n  %s"
        % (fixture.name, "\n  ".join(evidence_problems))
    )

    non_surfaced = [entry["pattern"] for entry in report["baseline"] if entry.get("surface") is not False]
    assert not non_surfaced, f"{fixture.name}: baseline entries not surface:false: {non_surfaced}"

    # The two `gate_evidence` invariants -- not per-case data, asserted
    # universally the same way the `evidence` invariants above are.
    gate_evidence_problems = _gate_evidence_problems(report, fixture.repo_dir)
    assert not gate_evidence_problems, (
        "%s: gate_evidence invariants violated:\n  %s"
        % (fixture.name, "\n  ".join(gate_evidence_problems))
    )

    # schema and repo complete the sweep over every report field (SDD/Data
    # model: fixture expectation, "repo and schema complete the sweep").
    assert report["schema"] == 1, fixture.name
    assert report["repo"] == str(fixture.repo_dir), fixture.name


class _FakeDetectModule(ModuleType):
    """A stand-in for the real `detect` module that returns one fixed report
    regardless of `repo_dir` -- used only to mutation-test the evidence
    invariants above, never to replace the real detector in the parametrized
    comparison."""

    def __init__(self, report: dict) -> None:
        super().__init__("fake_detect_for_mutation_test")
        self._report = report

    def detect(self, repo_dir) -> dict:
        return self._report


def _honest_report(tmp_path: pathlib.Path) -> dict:
    """A report over one real file, used as the mutation baseline that must
    NOT trip any invariant below."""
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    return {"auto": [{"pattern": "typescript-strict", "evidence": "tsconfig.json"}], "baseline": []}


def _evidence_problems_via_fake_detector(monkeypatch, tmp_path, report: dict) -> list[str]:
    """Feeds `report` to `_evidence_problems` via a monkeypatched fake detector,
    reproducing the loop `test_detector_matches_expected` runs.

    It does NOT prove that loop is still wired into the real test: this helper
    re-implements it rather than calling it, so commenting the assertion out of
    `test_detector_matches_expected` leaves all four mutants below green --
    measured on 2026-10-03, `4 passed`. `test_the_evidence_and_surface_assertions_are_wired_into_the_real_test`
    is what covers the wiring; these four cover the invariants themselves.
    `[ref: SDD/Data model: fixture expectation]`"""
    monkeypatch.setattr(sys.modules[__name__], "_load_detect", lambda: _FakeDetectModule(report))
    detect = _load_detect()
    produced = detect.detect(tmp_path)
    problems: list[str] = []
    for entry in list(produced["auto"]) + list(produced["baseline"]):
        problems.extend(_evidence_problems(entry, tmp_path))
    return problems


def test_evidence_invariant_accepts_an_honest_entry(tmp_path, monkeypatch) -> None:
    """The baseline fed to every mutant below must itself pass, or the
    mutants prove nothing."""
    problems = _evidence_problems_via_fake_detector(monkeypatch, tmp_path, _honest_report(tmp_path))
    assert problems == []


def test_evidence_invariant_catches_empty_evidence(tmp_path, monkeypatch) -> None:
    """Invariant 1: a non-empty `evidence` string."""
    report = _honest_report(tmp_path)
    report["auto"][0]["evidence"] = ""
    problems = _evidence_problems_via_fake_detector(monkeypatch, tmp_path, report)
    assert problems and "evidence is empty" in problems[0]


def test_evidence_invariant_catches_a_missing_path(tmp_path, monkeypatch) -> None:
    """Invariant 2: the path part resolves to a file that exists inside the
    repo."""
    report = _honest_report(tmp_path)
    report["auto"][0]["evidence"] = "does-not-exist.json"
    problems = _evidence_problems_via_fake_detector(monkeypatch, tmp_path, report)
    assert problems and "does not exist" in problems[0]


def test_evidence_invariant_catches_an_excluded_directory(tmp_path, monkeypatch) -> None:
    """Invariant 3: the path is not under an excluded directory -- trap 5
    reintroduced, caught even though the file genuinely exists there."""
    decoy_dir = tmp_path / "vendor" / "x"
    decoy_dir.mkdir(parents=True)
    (decoy_dir / "tsconfig.json").write_text("{}", encoding="utf-8")
    report = _honest_report(tmp_path)
    report["auto"][0]["evidence"] = "vendor/x/tsconfig.json"
    problems = _evidence_problems_via_fake_detector(monkeypatch, tmp_path, report)
    assert problems and "excluded directory" in problems[0]


def test_gate_evidence_invariant_accepts_an_honest_entry(tmp_path) -> None:
    """The baseline fed to every mutant below must itself pass, or the
    mutants prove nothing -- mirroring `test_evidence_invariant_accepts_an_honest_entry`."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    report = {
        "gates": {"q1_backend": True, "q2_architecture": False, "q3_test_quality": False},
        "gate_evidence": {"q1_backend": ["package.json: dependencies.express"]},
    }
    assert _gate_evidence_problems(report, tmp_path) == []


def test_gate_evidence_invariant_catches_an_open_gate_with_no_evidence(tmp_path) -> None:
    """Invariant 1: every gate reported open has a non-empty `gate_evidence`
    entry. Without this, T2.3 emitting `{}` for every gate -- the T2.2
    placeholder's shape -- would satisfy the fixture comparison and go
    undetected."""
    report = {
        "gates": {"q1_backend": True, "q2_architecture": False, "q3_test_quality": False},
        "gate_evidence": {},
    }
    problems = _gate_evidence_problems(report, tmp_path)
    assert problems and "no gate_evidence entry" in problems[0]


def test_gate_evidence_invariant_catches_a_closed_gate_carrying_evidence(tmp_path) -> None:
    """Invariant 2: a closed gate carries no `gate_evidence` entry -- a gate
    cannot be justified by evidence it did not act on."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    report = {
        "gates": {"q1_backend": False, "q2_architecture": False, "q3_test_quality": False},
        "gate_evidence": {"q1_backend": ["package.json: dependencies.express"]},
    }
    problems = _gate_evidence_problems(report, tmp_path)
    assert problems and "closed gate carries gate_evidence" in problems[0]


def test_gate_evidence_invariant_catches_a_missing_path(tmp_path) -> None:
    """Same path-resolution rule `_evidence_problems` applies, reused here."""
    report = {
        "gates": {"q1_backend": True, "q2_architecture": False, "q3_test_quality": False},
        "gate_evidence": {"q1_backend": ["does-not-exist.json: dependencies.express"]},
    }
    problems = _gate_evidence_problems(report, tmp_path)
    assert problems and "does not exist" in problems[0]


def test_gate_evidence_invariant_catches_an_excluded_directory(tmp_path) -> None:
    """A `gate_evidence` path under an excluded directory is caught even
    though the file genuinely exists there -- trap 5's lesson, reapplied."""
    decoy_dir = tmp_path / "vendor" / "x"
    decoy_dir.mkdir(parents=True)
    (decoy_dir / "package.json").write_text("{}", encoding="utf-8")
    report = {
        "gates": {"q1_backend": True, "q2_architecture": False, "q3_test_quality": False},
        "gate_evidence": {"q1_backend": ["vendor/x/package.json: dependencies.express"]},
    }
    problems = _gate_evidence_problems(report, tmp_path)
    assert problems and "excluded directory" in problems[0]


def test_the_evidence_and_surface_assertions_are_wired_into_the_real_test(monkeypatch) -> None:
    """The four mutation tests above exercise `_evidence_problems` but re-implement
    the loop that calls it, so they stay green if that loop is deleted from
    `test_detector_matches_expected` -- measured: `4 passed` with the assertion
    commented out. This test closes that hole by driving the real parametrized
    function and requiring it to reject a report that is correct in every respect
    except the invariants, for `evidence` and for `surface` alike.

    Both are checked here because both are assertions living inside that one
    function, and a regression that removes either is invisible to every other test
    in this file.
    """
    fixture = next(f for f in discover_fixtures() if f.name == "auto-testing-baseline")
    expected = load_expected(fixture)

    def report_with(evidence: str, surface: bool) -> dict:
        return {
            "schema": 1,
            "repo": str(fixture.repo_dir),
            "auto": [{"pattern": p, "evidence": evidence} for p in expected["auto"]],
            "baseline": [{"pattern": p, "evidence": evidence, "surface": surface}
                         for p in expected["baseline"]],
            "gates": expected["gates"],
            # One honest entry per open gate -- this fixture's q3_test_quality
            # is True, so an "everything correct" control needs a non-empty
            # entry there too, or the gate_evidence invariant added alongside
            # this control (below) would reject its own control case.
            "gate_evidence": {name: [evidence] for name, is_open in expected["gates"].items() if is_open},
            "unrecognised_stack": expected["unrecognised_stack"],
            # Not `[]`: this fixture genuinely has a `requirements.txt`, and
            # the manifests_walked completeness invariant (added after this
            # control was first written) now holds the "everything correct"
            # control to that too -- reusing the same independent
            # computation the invariant itself checks against.
            "manifests_walked": _expected_manifests_walked(fixture.repo_dir),
        }

    honest = "requirements.txt"

    # Control: everything correct, including both invariants -- must not raise.
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(report_with(honest, False)))
    test_detector_matches_expected(fixture)

    # `evidence` violated and nothing else -- the real test must reject it.
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(report_with("", False)))
    with pytest.raises(AssertionError, match="evidence"):
        test_detector_matches_expected(fixture)

    # `surface` violated and nothing else -- trap 1 reintroduced.
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(report_with(honest, True)))
    with pytest.raises(AssertionError, match="surface"):
        test_detector_matches_expected(fixture)


def test_the_gate_evidence_schema_and_repo_assertions_are_wired_into_the_real_test(monkeypatch) -> None:
    """Mirrors the test above, for T2.3's three additions: `gate_evidence`
    (both directions), `schema`, and `repo`. The dedicated unit tests above
    (`test_gate_evidence_invariant_catches_*`) exercise `_gate_evidence_problems`
    directly but re-implement the call rather than making it, so they would stay
    green if the `assert not gate_evidence_problems` line were deleted from
    `test_detector_matches_expected` -- measured by temporarily commenting that
    line (and the `schema`/`repo` asserts) out and re-running this file: those
    five unit tests still pass, proving they alone cannot catch the regression.
    This test closes that hole the same way the `evidence`/`surface` wiring test
    above does: by driving the real parametrized function.

    Uses `gate-q1-node-runtime-dependency` rather than `auto-testing-baseline`
    because it has two open gates (q1, q2) and one closed (q3), exercising both
    invariant directions in one fixture."""
    fixture = next(f for f in discover_fixtures() if f.name == "gate-q1-node-runtime-dependency")
    expected = load_expected(fixture)
    dep_evidence = "package.json: dependencies.express"

    def base_report(**overrides) -> dict:
        report = {
            "schema": 1,
            "repo": str(fixture.repo_dir),
            "auto": [{"pattern": p, "evidence": dep_evidence} for p in expected["auto"]],
            "baseline": [{"pattern": p, "evidence": dep_evidence, "surface": False}
                         for p in expected["baseline"]],
            "gates": dict(expected["gates"]),
            "gate_evidence": {name: [dep_evidence] for name, is_open in expected["gates"].items() if is_open},
            "unrecognised_stack": expected["unrecognised_stack"],
            "manifests_walked": _expected_manifests_walked(fixture.repo_dir),
        }
        report.update(overrides)
        return report

    # Control: everything correct, including all three invariants -- must not raise.
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(base_report()))
    test_detector_matches_expected(fixture)

    # gate_evidence invariant 1: an open gate (q1_backend) loses its entry.
    missing_q1 = base_report()
    del missing_q1["gate_evidence"]["q1_backend"]
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(missing_q1))
    with pytest.raises(AssertionError, match="gate_evidence"):
        test_detector_matches_expected(fixture)

    # gate_evidence invariant 2: a closed gate (q3_test_quality) gains an entry
    # it did not act on.
    unjustified_q3 = base_report()
    unjustified_q3["gate_evidence"]["q3_test_quality"] = [dep_evidence]
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(unjustified_q3))
    with pytest.raises(AssertionError, match="gate_evidence"):
        test_detector_matches_expected(fixture)

    # `schema` violated and nothing else.
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(base_report(schema=2)))
    with pytest.raises(AssertionError):
        test_detector_matches_expected(fixture)

    # `repo` violated and nothing else.
    monkeypatch.setattr(sys.modules[__name__], "_load_detect",
                        lambda: _FakeDetectModule(base_report(repo="/not/the/fixture/repo")))
    with pytest.raises(AssertionError):
        test_detector_matches_expected(fixture)


def test_q1_backend_gate_evidence_excludes_an_indirect_go_require(tmp_path) -> None:
    """Drives the real detector (not a fake) against a constructed `go.mod`
    with one direct and one indirect server-framework require, and asserts
    exact equality against a **hand-typed literal** -- completeness AND
    exclusivity on a tree not drawn from the corpus, so this cannot be
    satisfied by the corpus's one such case alone
    `[ref: SDD/Interface Specifications, "gate-q1-go-direct-require"]`.

    The literal is the point, not an accident of convenience. An earlier
    version of this test compared against a helper that re-parsed `go.mod`
    in the test file, which imported nothing from `detect.py` but
    re-implemented its module regex and its `"// indirect"` substring check
    -- two copies of one piece of logic agree wherever that logic is wrong,
    so the comparison proved call-site wiring and nothing about correctness.
    The helper was removed; this docstring claimed to compare against it
    until 2026-10-04, after it was gone."""
    (tmp_path / "go.mod").write_text(
        "module example.com/sample\n\ngo 1.22\n\n"
        "require (\n"
        "\tgithub.com/gin-gonic/gin v1.9.1\n"
        "\tgithub.com/labstack/echo/v4 v4.11.1 // indirect\n"
        ")\n",
        encoding="utf-8",
    )
    detect = _load_detect()
    report = detect.detect(tmp_path)
    assert report["gate_evidence"]["q1_backend"] == ["go.mod: require.github.com/gin-gonic/gin"]


def test_q2_architecture_triad_evidence_lists_every_matching_directory(tmp_path) -> None:
    """Completeness for the triad signal, the same property the test above
    pins for Go: two directories named `ports` are two contributing signals,
    and citing only the first found would under-report
    `[ref: SDD/Interface Specifications, "lists EVERY signal that
    contributed"]`. Drives the real detector, not a fake."""
    (tmp_path / "a" / "ports").mkdir(parents=True)
    (tmp_path / "b" / "ports").mkdir(parents=True)
    (tmp_path / "adapters").mkdir()
    (tmp_path / "domain").mkdir()
    detect = _load_detect()
    report = detect.detect(tmp_path)
    q2_evidence = set(report["gate_evidence"]["q2_architecture"])
    assert {"a/ports/", "b/ports/"} <= q2_evidence, q2_evidence


def test_pre_311_interpreter_is_refused_loudly(tmp_path, monkeypatch) -> None:
    """ADR-2's 3.11 floor: on an interpreter without `tomllib`, `detect()`
    must refuse with an actionable `RuntimeError` naming the required
    version -- never degrade to a weaker parser, which is exactly the
    failure mode of the regex fallback that used to live in `detect.py` and
    silently produced a false `mcp-server` proposal.

    A test asserting only "no false positive" would pass against that
    silently-degraded parser too, since its output was individually
    defensible-looking; the refusal itself is the property worth asserting.
    Simulated by monkeypatching the real `detect` module's `tomllib`
    attribute to `None` rather than reimporting under a different
    interpreter -- `_require_tomllib` is checked at call time inside
    `detect()` for exactly this reason, not at import time."""
    detect = _load_detect()
    monkeypatch.setattr(detect, "tomllib", None)
    with pytest.raises(RuntimeError, match="3.11"):
        detect.detect(tmp_path)


def test_a_current_interpreter_is_not_refused(tmp_path) -> None:
    """Control for the test above: on this repo's own floor (`tomllib`
    present), `detect()` must not raise."""
    detect = _load_detect()
    detect.detect(tmp_path)


def test_q2_evidence_unions_q1_and_a_content_signal(tmp_path) -> None:
    """The combined case no fixture can reach: `q1_backend` open AND a weak
    content signal present at the same time. `q2_architecture`'s evidence must
    list BOTH, because an entry lists every signal that contributed
    `[ref: SDD/Interface Specifications, "lists EVERY signal that
    contributed"]`.

    Unreachable through the corpus by construction, which is why it is here:
    `gates` carries booleans, so a fixture cannot distinguish "q2 opened" from
    "q2 opened for both reasons", and the exact-key guard forbids any
    `expected.json` from declaring `gate_evidence`. Every corpus case that
    opens q2 does so for exactly one reason.

    Asserted against hand-typed literals rather than anything re-derived from
    `detect.py`'s own logic.
    """
    (tmp_path / "package.json").write_text(
        '{"name": "s", "version": "1.0.0", "dependencies": {"express": "^4.18.0"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "event_store").mkdir(parents=True)
    (tmp_path / "src" / "event_store" / "schema.sql").write_text("-- events\n", encoding="utf-8")

    detect = _load_detect()
    report = detect.detect(tmp_path)

    assert report["gates"]["q1_backend"] is True
    assert report["gates"]["q2_architecture"] is True
    assert report["gate_evidence"]["q2_architecture"] == [
        "package.json: dependencies.express",
        "src/event_store/",
    ]


# The four-manifest table, row by row, against the real detector
# `[ref: SDD/Interface Specifications/Detection rules, "Which declaration counts
# as `dependencies` outside `package.json`"]`. Three of these six rows are
# covered by no fixture at all, and three are satisfied only by OMISSION -- the
# dependency readers simply never parse a development table. Correct today and
# fragile tomorrow: adding `[project.optional-dependencies]` support to the
# stack-fact reader for a perfectly good reason would silently open gates on
# development-only declarations, and before this test nothing would have failed.
# Trees are hand-written here rather than added to the corpus: a gate's boolean
# is all these need, which `detect()` already reports, and six more fixtures to
# assert six booleans would be a poor trade.
GATE_DEPENDENCY_SOURCE_CASES = [
    ("optional_dependencies_do_not_open_q1", False, {
        "pyproject.toml": '[project]\nname = "s"\ndependencies = []\n\n'
                          '[project.optional-dependencies]\ndev = ["fastapi"]\n',
        "app.py": "x = 1\n",
    }),
    ("poetry_dev_group_does_not_open_q1", False, {
        "pyproject.toml": '[tool.poetry]\nname = "s"\n\n'
                          '[tool.poetry.group.dev.dependencies]\nfastapi = "^0.104"\n',
        "app.py": "x = 1\n",
    }),
    ("extras_require_does_not_open_q1", False, {
        "setup.py": "from setuptools import setup\n"
                    "setup(name='s', install_requires=[], extras_require={'dev': ['fastapi']})\n",
        "app.py": "x = 1\n",
    }),
    ("project_dependencies_open_q1", True, {
        "pyproject.toml": '[project]\nname = "s"\ndependencies = ["fastapi"]\n',
        "app.py": "x = 1\n",
    }),
    ("install_requires_opens_q1", True, {
        "setup.py": "from setuptools import setup\nsetup(name='s', install_requires=['flask'])\n",
        "app.py": "x = 1\n",
    }),
    ("poetry_dependencies_open_q1", True, {
        "pyproject.toml": '[tool.poetry]\nname = "s"\n\n'
                          '[tool.poetry.dependencies]\ndjango = "^5.0"\n',
        "app.py": "x = 1\n",
    }),
]


@pytest.mark.parametrize(
    "case_id,expect_open,files",
    GATE_DEPENDENCY_SOURCE_CASES,
    ids=[c[0] for c in GATE_DEPENDENCY_SOURCE_CASES],
)
def test_q1_reads_runtime_declarations_and_not_development_ones(
    case_id, expect_open, files, tmp_path
) -> None:
    """Each case is one row of the four-manifest table, with the three
    development-table rows paired against three runtime-table controls. The
    controls are what make the negatives mean anything: a detector that reads no
    Python manifest at all would pass the three negatives and fail all three
    positives, which is the failure this pairing is here to tell apart."""
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    detect = _load_detect()
    report = detect.detect(tmp_path)
    assert report["gates"]["q1_backend"] is expect_open, (
        "%s: gate_evidence was %r" % (case_id, report["gate_evidence"].get("q1_backend"))
    )


def test_q3_evidence_is_one_signal_per_ecosystem_across_all_ecosystems(tmp_path) -> None:
    """q3's evidence is deliberately NOT complete within an ecosystem, and this
    pins both halves so neither can drift
    `[ref: SDD/Interface Specifications, "Where completeness binds, and where one
    signal is a complete explanation"]`.

    Completeness binds only where an entry's contents are the only observable
    that can discriminate a rule -- q1's Go direct/indirect split, the triad's
    repeated directories, and q2's union. q3 excludes nothing, so there is no
    wrong match for its contents to rule out, and one config file completely
    answers "is there a test framework here".

    This behaviour was undocumented and its docstring claimed the opposite until
    2026-10-04, so it is pinned in both directions: a change making it complete
    within an ecosystem fails here just as loudly as one dropping an ecosystem.
    """
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "tox.ini").write_text("[tox]\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module example.com/s\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "a_test.go").write_text("package a\n", encoding="utf-8")
    (tmp_path / "b_test.go").write_text("package a\n", encoding="utf-8")

    detect = _load_detect()
    report = detect.detect(tmp_path)

    assert report["gates"]["q3_test_quality"] is True
    # Python contributes pytest.ini and not tox.ini; Go contributes a_test.go
    # and not b_test.go; both ecosystems are present.
    assert report["gate_evidence"]["q3_test_quality"] == ["a_test.go", "pytest.ini"]


def test_q1_evidence_omits_an_excluded_declaration_while_the_gate_still_opens(tmp_path) -> None:
    """The mixed case the boolean cannot see: a development-only framework
    beside a runtime one. q1 opens either way, so only the evidence CONTENTS
    distinguish a detector that correctly ignored `express` in
    `devDependencies` from one that credited it
    `[ref: SDD/Interface Specifications, "Where completeness binds, and where
    one signal is a complete explanation"]`.

    Found 2026-10-04 by probing whether the scoped completeness rule had missed
    a place, after that rule was written naming three. It had: q1's
    development-and-transitive exclusion is content-discriminated for EVERY
    ecosystem, and Go's `// indirect` split -- which the rule did name -- is one
    instance of it rather than a separate case. `gate-q1-node-runtime-dependency`
    and the paired dependency-source test both assert only the boolean, which a
    detector crediting the devDependency would still satisfy here.

    Both halves asserted together: `fastapi` present, `express` absent, against
    hand-typed literals.
    """
    (tmp_path / "package.json").write_text(
        '{"name": "s", "version": "1.0.0", "devDependencies": {"express": "^4.18.0"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi==0.104.0\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

    detect = _load_detect()
    report = detect.detect(tmp_path)

    assert report["gates"]["q1_backend"] is True
    assert report["gate_evidence"]["q1_backend"] == ["requirements.txt: requirements.fastapi"]


def test_q1_evidence_lists_every_runtime_framework_not_only_the_first(tmp_path) -> None:
    """The completeness half of the same rule, which nothing asserted either:
    two server frameworks declared as runtime dependencies are two contributing
    signals, and citing one would under-report exactly as crediting only the
    first-matched `go.mod` require would. Two in ONE manifest, so this cannot be
    satisfied by a per-manifest loop that returns on its first hit.
    """
    (tmp_path / "package.json").write_text(
        '{"name": "s", "version": "1.0.0", '
        '"dependencies": {"express": "^4.18.0", "koa": "^2.14.0"}}\n',
        encoding="utf-8",
    )

    detect = _load_detect()
    report = detect.detect(tmp_path)

    assert report["gate_evidence"]["q1_backend"] == [
        "package.json: dependencies.express",
        "package.json: dependencies.koa",
    ]
