"""Shared fixture-corpus helpers for the patterns-detection test suite (spec-020 T2.1).

Not a test module itself -- its name deliberately falls outside pytest's `test_*.py`
discovery pattern, so the two files that use it (`test_patterns_detection_corpus.py`'s
integrity checks and `test_patterns_detect.py`'s comparison tests) share one glob/JSON
loading path instead of duplicating it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "patterns-detection"
CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"

# The single source of truth for the corpus size (task text step 2's mandatory
# guard). Both `test_patterns_detection_corpus.py` and `test_patterns_detect.py`
# assert against this constant -- each file must stay safe to run alone, so each
# needs its own standalone, non-parametrized count assertion, but there is still
# only one number to keep in sync with the fixture directory.
EXPECTED_CASE_COUNT = 18


@dataclass(frozen=True)
class Fixture:
    name: str
    path: Path

    @property
    def repo_dir(self) -> Path:
        return self.path / "repo"

    @property
    def expected_path(self) -> Path:
        return self.path / "expected.json"


def discover_fixtures() -> list[Fixture]:
    """Every immediate subdirectory of the corpus, sorted for stable test IDs.

    Deliberately not filtered by whether `repo/` or `expected.json` exist inside --
    a case directory missing either must still appear here, so the existence check
    (not a silently empty corpus) is what catches it."""
    if not CORPUS_DIR.is_dir():
        return []
    return sorted(
        (Fixture(name=p.name, path=p) for p in CORPUS_DIR.iterdir() if p.is_dir()),
        key=lambda f: f.name,
    )


def catalogue_pattern_names() -> set[str]:
    """The pattern names, read from the catalogue at test time -- never hardcoded,
    so a renamed or added pattern directory is picked up automatically."""
    if not CATALOGUE_DIR.is_dir():
        return set()
    return {p.name for p in CATALOGUE_DIR.iterdir() if p.is_dir()}


def load_expected(fixture: Fixture) -> dict:
    return json.loads(fixture.expected_path.read_text(encoding="utf-8"))
