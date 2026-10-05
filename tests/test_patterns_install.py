"""T3.1 (spec-020): the manifest store (component C6).

Six assertions, three of them sharpened at this task's TDD gate on
2026-10-05 because as first written they were satisfiable by an
implementation that does not do the thing `[ref: docs/XDD/specs/
020-tcs-patterns-selective-install/plan/phase-3.md#T3.1]`:

- `test_upsert_leaves_other_entries_byte_identical` (F6's second criterion)
  asserts a pre-existing pattern's exact table block survives a later
  `upsert` byte-for-byte, **and** that the parsed entry still equals the old
  one -- a structure comparison alone would pass against a re-serialiser
  that reorders keys or respaces the file, and a byte comparison alone would
  not catch a block that survived verbatim but was shadowed by a duplicate
  table.
- `test_unparseable_manifest_is_never_overwritten` captures the file's bytes
  before the call, runs the upsert inside `pytest.raises`, and asserts the
  bytes are unchanged after -- "assert it raises" alone is vacuous here,
  because the raise is the only observable and an implementation that
  catches the error internally and writes anyway would look identical.
- `test_currency_determinable_without_installed_pattern_files` deletes (by
  never creating) the installed pattern's own directory and asserts
  currency is still determinable (AC-17, PRD/F6 3rd) -- deliberately not by
  mocking `open()`, which would couple the test to the implementation's I/O
  calls rather than to the behaviour AC-17 actually requires.

The module under test (`manifest.py`) is imported at RUNTIME via
`_load_manifest()`, not at module level -- same reason `test_patterns_detect.py`
does this for `detect.py`: a module-level `ImportError` would abort
collection of this whole file rather than failing only the tests that need
the module.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"


def _load_manifest() -> ModuleType:
    """See `test_patterns_detect.py::_load_detect` for why this import
    happens here rather than at module level, and why `sys.path` (not
    `PYTHONPATH`) is how a mutated copy must be loaded when
    mutation-testing this file."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("manifest")


def _sha(seed: str) -> str:
    """A deterministic, valid-shaped 64-character hex digest for test data --
    real `sha256`, not a hand-typed string, so nothing here has to count
    hex characters by eye."""
    return hashlib.sha256(seed.encode()).hexdigest()


def _manifest_path(repo_dir: Path, manifest: ModuleType) -> Path:
    return repo_dir.joinpath(*manifest.MANIFEST_DIR, manifest.MANIFEST_FILENAME)


def _entry_block(path: Path, name: str) -> str:
    """The exact on-disk text of `[patterns.<name>]`'s table -- the header
    line plus its three `key = value` lines, nothing else. Used to assert a
    pattern's block survives an `upsert` byte-for-byte without comparing
    parsed structures (assertion b): a structure comparison would pass
    against a re-serialiser that reorders keys or respaces the file, which
    is exactly the implementation this assertion must catch."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"\[patterns\.{re.escape(name)}\]\n(?:.*\n){{3}}", text)
    assert match, f"no [patterns.{name}] block found in {path}"
    return match.group(0)


def test_round_trips_without_loss(tmp_path: Path) -> None:
    manifest = _load_manifest()
    written = manifest.upsert(
        tmp_path,
        "ddd",
        version="3",
        installed_as="tcs-ddd",
        sha256=_sha("ddd-3"),
        bundle="2.0.0",
    )

    reread = manifest.read(tmp_path)

    assert reread == written
    assert reread.bundle == "2.0.0"
    assert reread.patterns["ddd"] == manifest.PatternEntry(
        version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3")
    )


def test_upsert_leaves_other_entries_byte_identical(tmp_path: Path) -> None:
    manifest = _load_manifest()
    manifest.upsert(
        tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
    )
    manifest.upsert(
        tmp_path,
        "hexagonal",
        version="2",
        installed_as="tcs-hexagonal",
        sha256=_sha("hexagonal-2"),
        bundle="2.0.0",
    )

    path = _manifest_path(tmp_path, manifest)
    before_block = _entry_block(path, "ddd")
    before_entry = manifest.read(tmp_path).patterns["ddd"]

    manifest.upsert(
        tmp_path,
        "observability",
        version="1",
        installed_as="tcs-observability",
        sha256=_sha("observability-1"),
        bundle="2.0.0",
    )

    after_bytes = path.read_text(encoding="utf-8")
    # Not a comparison of parsed structures (SDD/tasking: `tomllib` cannot
    # write, so `upsert` regenerates the whole file rather than patching
    # it, and a structure comparison passes against a re-serialiser that
    # reorders keys or respaces the file).
    assert before_block in after_bytes

    # And the block surviving verbatim is not enough on its own -- it could
    # have survived while being shadowed by a duplicate table further down
    # the file. The parsed entry must still equal the old one too.
    after_entry = manifest.read(tmp_path).patterns["ddd"]
    assert after_entry == before_entry


def test_absent_manifest_reads_as_empty(tmp_path: Path) -> None:
    manifest = _load_manifest()

    result = manifest.read(tmp_path)

    assert result.bundle is None
    assert result.patterns == {}


def test_unparseable_manifest_raises(tmp_path: Path) -> None:
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)
    path.parent.mkdir(parents=True)
    path.write_text("this is not valid toml [[[\n= nope\n", encoding="utf-8")

    with pytest.raises(manifest.ManifestUnparseableError):
        manifest.read(tmp_path)


def test_unparseable_manifest_is_never_overwritten(tmp_path: Path) -> None:
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"this is not valid toml [[[\n= nope\n")
    before_bytes = path.read_bytes()

    # "Assert it raises" alone is vacuous here -- the raise is the only
    # observable, so an implementation that catches the error internally
    # and writes anyway would look identical to one that refuses. The bytes
    # check below is the assertion that actually distinguishes them.
    with pytest.raises(manifest.ManifestUnparseableError):
        manifest.upsert(
            tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
        )

    assert path.read_bytes() == before_bytes


def test_currency_determinable_without_installed_pattern_files(tmp_path: Path) -> None:
    manifest = _load_manifest()
    written = manifest.upsert(
        tmp_path,
        "ddd",
        version="3",
        installed_as="tcs-ddd",
        sha256=_sha("ddd-3"),
        bundle="2.0.0",
    )

    # AC-17 / PRD F6 3rd: no installed pattern directory exists at all --
    # not even created, let alone deleted after the fact. A function that
    # reads the installed pattern's own files cannot pass this, because
    # there is nothing there to read.
    installed_dir = tmp_path / ".claude" / "skills" / "tcs-ddd"
    assert not installed_dir.exists()

    entry = written.patterns["ddd"]
    assert manifest.is_current(entry, catalogue_version="4") is False
    assert manifest.is_current(entry, catalogue_version="3") is True
