"""T1.2 (spec-020): every pattern directory in the catalogue carries a VERSION file.

Why this exists: SDD/Interface Specifications "Data model: catalogue entry (C1)" requires
`templates/patterns/<name>/VERSION` -- one line, a bare integer, maintainer-set (ADR-3).
ADR-3's rationale for making this per-directory rather than a central table is that "a
pattern added later is covered by the rule that already exists" with no registration step.
Iterating a closed name list here would reintroduce exactly the registration step ADR-3 was
reasoned to avoid, so every assertion below enumerates `templates/patterns/` at run time --
a 22nd directory with no `VERSION` must fail this suite, not wait for a constant to be
updated.

This is a separate module from `test_tcs_patterns_catalogue_relocation.py` on purpose: that
file's own docstring scopes itself to the one-time relocation and explicitly disclaims
`VERSION` as out of scope (it even anticipates this file's effect on its tracked-file count,
80 -> 101). The catalogue entry's file-shape contract (SDD C1) outlives the relocation --
Phase 4's CI gate and Phase 5's new patterns both depend on it holding long after the
relocation commit is history -- so it gets its own file rather than growing the relocation
test's scope.

The consuming half of plan step 2 ("a pattern without one is reported as unknown rather than
drifted") is Phase 4's drift reporter, not this file. This file only asserts the file-shape
half: presence, line count, and integer parsing, each as a distinct failure mode."""

from __future__ import annotations

from pathlib import Path

import pytest
from visible_dirs import visible_dir_names, visible_dirs

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"


def _pattern_dirs() -> list[Path]:
    """Every directory directly under the catalogue, read from the filesystem at run time --
    never a fixed name list (Requirement 1: a pattern added later with no VERSION must fail
    here, not be silently skipped because it is absent from some constant)."""
    assert CATALOGUE_DIR.is_dir(), f"{CATALOGUE_DIR} does not exist -- has the catalogue moved?"
    return visible_dirs(CATALOGUE_DIR)


def test_every_pattern_directory_has_a_version_file() -> None:
    """Presence only. Line-count and parsing are separate tests below -- each failure mode
    gets its own assertion so a failure here always means "absent", never "malformed"."""
    dirs = _pattern_dirs()
    assert dirs, "no pattern directories found under the catalogue"
    missing = sorted(d.name for d in dirs if not (d / "VERSION").is_file())
    assert not missing, f"pattern(s) missing a VERSION file: {missing}"


def test_every_version_file_holds_exactly_one_line() -> None:
    """`1\\n2\\n` is a distinct violation from a bad value -- asserted separately from
    integer-parsing below so a failure says which rule broke."""
    for pattern_dir in _pattern_dirs():
        version_file = pattern_dir / "VERSION"
        if not version_file.is_file():
            continue  # reported by test_every_pattern_directory_has_a_version_file
        lines = version_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1, f"{pattern_dir.name}'s VERSION has {len(lines)} lines, expected exactly 1: {lines!r}"


def test_every_version_file_parses_as_a_positive_integer() -> None:
    """Separate from the line-count check: a single-line file can still fail to parse
    (e.g. `abc`) or parse to a non-positive value (`0`, `-1`) -- each its own failure mode."""
    for pattern_dir in _pattern_dirs():
        version_file = pattern_dir / "VERSION"
        if not version_file.is_file():
            continue  # reported by test_every_pattern_directory_has_a_version_file
        lines = version_file.read_text(encoding="utf-8").splitlines()
        if len(lines) != 1:
            continue  # reported by test_every_version_file_holds_exactly_one_line
        raw = lines[0].strip()
        try:
            value = int(raw)
        except ValueError:
            pytest.fail(f"{pattern_dir.name}'s VERSION does not parse as an integer: {raw!r}")
        assert value > 0, f"{pattern_dir.name}'s VERSION is not a positive integer: {value}"
