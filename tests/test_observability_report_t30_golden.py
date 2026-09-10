"""spec-019 T3.0 -- pin `report.py`'s `--events <path>` rendering path against
a golden fixture captured from commit eb9b529, BEFORE spec-019 Phase 3
(spec-019 T3.1, T3.3, T3.4) starts rewriting the reader.

Why this file exists, not just a regeneration script: SDD-AC-24 requires
`--events`'s behaviour to stay unchanged from spec-018 across spec-019 Phase
3. `tests/fixtures/observability/t30_golden/regenerate.py` -- run standalone
-- rebuilds the synthetic input tree and diffs it against
`golden_report.txt`; this test wires the exact same check into the default
`pytest` run (`pytest.ini`'s `addopts = -m "not perf"` runs it unmarked, no
extra flag needed), so a later spec-019 task cannot silently drift the
`--events` path without a red test -- see the fixture directory's own
docstring for the full rationale, the "confirmed"-branch limitation (R4),
and the R6 git-filtering trade-off.

This is deliberately a SEPARATE file from tests/test_observability_report.py
rather than one more test appended there: that file's own tests build their
fixtures ad hoc per test (SDD-AC-13/-14/-15/-17/-18's unit coverage); this
one test's entire job is comparing the CURRENT reader's output against a
frozen byte-for-byte snapshot from a named commit, which is a different kind
of assertion warranting a name and a place of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "observability" / "t30_golden"
sys.path.insert(0, str(GOLDEN_DIR))

import regenerate  # noqa: E402  (sys.path must be extended first)


def test_t30_golden_fixture_reproduces_byte_identically():
    """Two independent (build tree -> run report.py CLI) passes must agree
    with each other AND with the committed golden_report.txt -- byte
    identical reproduction is necessary (spec-019 T3.0 team-lead brief, R5)
    but this alone does not prove coverage breadth; see the fixture
    directory's own regenerate.py docstring for how each report section was
    deliberately exercised.
    """
    golden = (GOLDEN_DIR / "golden_report.txt").read_text(encoding="utf-8")

    first = regenerate.build_and_capture()
    second = regenerate.build_and_capture()

    assert first == second, "two independent captures diverged -- the fixture is not deterministic"
    assert first == golden, (
        "report.py's --events rendering path no longer matches the golden fixture captured "
        "from commit eb9b529 (SDD-AC-24). If this is an INTENTIONAL spec-019 Phase 3 change to "
        "the reader, this failure is doing its job -- do not regenerate this fixture to silence "
        "it; the whole point is that it stays frozen against the pre-change behaviour."
    )
