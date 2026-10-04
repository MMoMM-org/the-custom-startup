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
    whole file."""
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


EXCLUDED_SEGMENTS = frozenset({"node_modules", ".venv", "venv", "vendor"})


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
