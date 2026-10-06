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

**A second mutation pass (2026-10-05, after the first 10 tests were green)
found seven more coverage gaps**, none a behaviour bug -- the real code
handles all seven correctly, nothing here was missing or extra. Two
(`test_write_creates_its_temp_file_beside_the_manifest`,
`test_write_replaces_the_destination_with_os_replace`) assert a MECHANISM
call rather than an outcome, and say why in their own docstrings: the
requirement they pin (same-filesystem temp file, atomic `os.replace`) is
untestable through `tmp_path` by construction, because pytest's `tmp_path`
and the manifest's destination always share one filesystem, so the
cross-device failure the SDD cites can never actually occur inside a test
regardless of which call the implementation makes. The other five
(`test_read_rejects_every_malformed_manifest_shape`,
`test_write_cleans_up_its_temp_file_when_the_replace_fails`,
`test_with_pattern_does_not_mutate_the_original_manifest`,
`test_with_pattern_rejects_an_invalid_pattern_name`,
`test_read_treats_a_directory_at_the_manifest_path_as_absent`) are ordinary
outcome assertions that simply had no test yet.
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


def test_serialized_file_matches_hand_typed_format(tmp_path: Path) -> None:
    """Independent of `_serialize`/`_serialize_pattern` by construction --
    the expected text below is typed out literally, not assembled from any
    helper this module shares with the code under test. A reference built
    from a shared helper would reproduce the same blindness as
    `test_upsert_leaves_other_entries_byte_identical`: both the before- and
    after- side of that test are produced by the SAME serialiser, so a
    deterministic reformatting (key order inside a table, header spacing)
    passes it regardless of whether the bytes are what was actually
    intended. This test pins the intra-table key order, the header comment,
    and where `bundle` sits, against a literal nothing here can echo back
    by construction."""
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
    expected = (
        "# Written by /tcs-patterns:patterns-setup. Reviewed and committed like any other file.\n"
        'bundle = "2.0.0"\n'
        "\n"
        "[patterns.ddd]\n"
        'version = "3"\n'
        'installed_as = "tcs-ddd"\n'
        f'sha256 = "{_sha("ddd-3")}"\n'
        "\n"
        "[patterns.hexagonal]\n"
        'version = "2"\n'
        'installed_as = "tcs-hexagonal"\n'
        f'sha256 = "{_sha("hexagonal-2")}"\n'
    )

    assert path.read_text(encoding="utf-8") == expected


def test_patterns_are_written_in_sorted_order_regardless_of_insert_order(tmp_path: Path) -> None:
    """Pins `sorted()` in `_serialize` specifically: inserts in reverse-ish
    (observability, hexagonal, ddd) and asserts the file comes out
    alphabetical (ddd, hexagonal, observability) against a hand-typed
    literal -- the same kind of implementation-independent reference as
    `test_serialized_file_matches_hand_typed_format`, chosen here to make a
    dropped `sorted()` call fail even though the byte-identical test above
    cannot see it (a dropped `sorted()` reorders both the before- and
    after-file identically, by insertion order, so `before_block in
    after_bytes` still holds)."""
    manifest = _load_manifest()
    manifest.upsert(
        tmp_path,
        "observability",
        version="1",
        installed_as="tcs-observability",
        sha256=_sha("observability-1"),
        bundle="2.0.0",
    )
    manifest.upsert(
        tmp_path,
        "hexagonal",
        version="2",
        installed_as="tcs-hexagonal",
        sha256=_sha("hexagonal-2"),
        bundle="2.0.0",
    )
    manifest.upsert(
        tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
    )

    path = _manifest_path(tmp_path, manifest)
    expected = (
        "# Written by /tcs-patterns:patterns-setup. Reviewed and committed like any other file.\n"
        'bundle = "2.0.0"\n'
        "\n"
        "[patterns.ddd]\n"
        'version = "3"\n'
        'installed_as = "tcs-ddd"\n'
        f'sha256 = "{_sha("ddd-3")}"\n'
        "\n"
        "[patterns.hexagonal]\n"
        'version = "2"\n'
        'installed_as = "tcs-hexagonal"\n'
        f'sha256 = "{_sha("hexagonal-2")}"\n'
        "\n"
        "[patterns.observability]\n"
        'version = "1"\n'
        'installed_as = "tcs-observability"\n'
        f'sha256 = "{_sha("observability-1")}"\n'
    )

    assert path.read_text(encoding="utf-8") == expected


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


def test_non_utf8_manifest_raises_unparseable(tmp_path: Path) -> None:
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe\x00")

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


# A `bundle` value containing a quote and a newline. Representable literally
# in the hand-written TOML this module produces, `_require_representable`
# would let it through unescaped and the resulting file would both parse
# (as a spurious top-level `malicious` key) and later fail `read()`'s
# unknown-top-level-key check -- "write succeeds, every later read raises"
# is the hazard this guard exists to prevent (measured against a build with
# the guard disabled: the write succeeds and the record is effectively
# lost on the next read).
_UNSAFE_BUNDLE = '2.0.0"\nmalicious = "yes'


def test_unsafe_bundle_value_raises_and_writes_nothing(tmp_path: Path) -> None:
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)

    with pytest.raises(ValueError):
        manifest.upsert(
            tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle=_UNSAFE_BUNDLE
        )

    # No manifest existed before this call, and none must exist after it --
    # a half-written or malformed file left behind would be exactly as bad
    # as the spurious-key hazard this guard exists to prevent.
    assert not path.is_file()


def test_unsafe_bundle_value_raises_without_overwriting_existing_manifest(tmp_path: Path) -> None:
    manifest = _load_manifest()
    manifest.upsert(
        tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
    )
    path = _manifest_path(tmp_path, manifest)
    before_bytes = path.read_bytes()

    with pytest.raises(ValueError):
        manifest.upsert(
            tmp_path,
            "hexagonal",
            version="2",
            installed_as="tcs-hexagonal",
            sha256=_sha("hexagonal-2"),
            bundle=_UNSAFE_BUNDLE,
        )

    assert path.read_bytes() == before_bytes


def test_write_creates_its_temp_file_beside_the_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts the MECHANISM (`tempfile.mkstemp`'s `dir=` kwarg), not an
    outcome, because the outcome `write()` exists to prevent -- `os.replace`
    raising `Cross-device link` -- cannot be reproduced through `tmp_path`:
    pytest's `tmp_path` and the manifest's own destination always sit on
    one filesystem, so a mutant that drops `dir=` entirely (falling back to
    `$TMPDIR`) still lands the temp file on the SAME filesystem here and the
    write still succeeds. The SDD measured the real-world failure
    (`/Volumes/Moon` vs. `$TMPDIR`, different `st_dev`) as the reason this
    requirement exists; this test cannot reproduce that measurement, only
    confirm `write()` still asks for the right directory. Do not
    "simplify" this into an outcome assertion -- there is no outcome here
    that distinguishes right from wrong.
    """
    manifest = _load_manifest()
    calls: list[dict] = []
    real_mkstemp = manifest.tempfile.mkstemp

    def recording_mkstemp(*args, **kwargs):
        calls.append(kwargs)
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(manifest.tempfile, "mkstemp", recording_mkstemp)

    manifest.upsert(
        tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
    )

    assert calls, "tempfile.mkstemp was never called"
    expected_dir = str(_manifest_path(tmp_path, manifest).parent)
    assert calls[-1].get("dir") == expected_dir


def test_write_replaces_the_destination_with_os_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same reasoning as `test_write_creates_its_temp_file_beside_the_manifest`
    above: asserts that `write()` calls `os.replace` (atomic on one
    filesystem) rather than, say, `shutil.move` (which silently degrades to
    copy-then-delete across filesystems) -- a mechanism check, because
    `tmp_path` cannot put the temp file and the destination on different
    filesystems, so both implementations produce an identical, correct
    outcome here."""
    manifest = _load_manifest()
    calls: list[tuple] = []
    real_replace = manifest.os.replace

    def recording_replace(src, dst):
        calls.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr(manifest.os, "replace", recording_replace)

    manifest.upsert(
        tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
    )

    assert calls, "os.replace was never called"
    src, dst = calls[-1]
    expected_path = _manifest_path(tmp_path, manifest)
    assert Path(dst) == expected_path
    assert Path(src).parent == expected_path.parent


# Eight malformed manifest shapes, each missing exactly one requirement
# `read()` enforces. Parametrized over one `pytest.raises` rather than eight
# near-identical test functions -- the point of each case is which single
# clause of the schema it violates, not a separately named test.
_MALFORMED_MANIFESTS = {
    "unknown_top_level_key": (
        'bundle = "2.0.0"\n'
        'extra = "nope"\n'
    ),
    "bundle_missing": (
        "[patterns.ddd]\n"
        'version = "3"\n'
        'installed_as = "tcs-ddd"\n'
        f'sha256 = "{_sha("ddd-3")}"\n'
    ),
    "bundle_non_string": ("bundle = 123\n"),
    "patterns_not_a_table": (
        'bundle = "2.0.0"\n'
        'patterns = "nope"\n'
    ),
    "pattern_unknown_key": (
        'bundle = "2.0.0"\n'
        "\n"
        "[patterns.ddd]\n"
        'version = "3"\n'
        'installed_as = "tcs-ddd"\n'
        f'sha256 = "{_sha("ddd-3")}"\n'
        'extra = "nope"\n'
    ),
    "pattern_missing_field": (
        'bundle = "2.0.0"\n'
        "\n"
        "[patterns.ddd]\n"
        'version = "3"\n'
        'installed_as = "tcs-ddd"\n'
        # sha256 deliberately absent
    ),
    "pattern_wrong_typed_field": (
        'bundle = "2.0.0"\n'
        "\n"
        "[patterns.ddd]\n"
        "version = 3\n"  # not a string
        'installed_as = "tcs-ddd"\n'
        f'sha256 = "{_sha("ddd-3")}"\n'
    ),
    "pattern_invalid_name": (
        'bundle = "2.0.0"\n'
        "\n"
        '[patterns."BadName"]\n'  # uppercase: _NAME_RE rejects it
        'version = "3"\n'
        'installed_as = "tcs-ddd"\n'
        f'sha256 = "{_sha("ddd-3")}"\n'
    ),
}


@pytest.mark.parametrize("toml_text", _MALFORMED_MANIFESTS.values(), ids=_MALFORMED_MANIFESTS.keys())
def test_read_rejects_every_malformed_manifest_shape(tmp_path: Path, toml_text: str) -> None:
    """Each case is syntactically valid TOML violating exactly one of
    `read()`'s schema checks -- `test_unparseable_manifest_raises` only
    drives the `tomllib.TOMLDecodeError` branch; deleting any one of
    `read()`'s other guard clauses left the suite green until this test
    existed."""
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)
    path.parent.mkdir(parents=True)
    path.write_text(toml_text, encoding="utf-8")

    with pytest.raises(manifest.ManifestUnparseableError):
        manifest.read(tmp_path)


def test_write_cleans_up_its_temp_file_when_the_replace_fails(tmp_path: Path) -> None:
    """Makes the manifest's own path a pre-existing DIRECTORY, so `os.replace`
    fails with `IsADirectoryError` (measured) rather than succeeding --
    `read()` treats a directory there as absent (see
    `test_read_treats_a_directory_at_the_manifest_path_as_absent`), so
    `upsert` proceeds all the way to `write()`'s `os.replace` call before
    hitting the failure. Asserts both that the exception propagates AND that
    no `.{MANIFEST_FILENAME}.*.tmp` file is left behind in `.claude/skills/`
    -- deleting `write()`'s `except BaseException: os.unlink(...); raise`
    block leaves the exception propagating correctly while silently
    littering a temp file, which only the second assertion catches."""
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)
    path.parent.mkdir(parents=True)
    path.mkdir()  # the manifest "file" is actually a directory

    with pytest.raises(OSError):
        manifest.upsert(
            tmp_path, "ddd", version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"), bundle="2.0.0"
        )

    leftover = list(path.parent.glob(f".{manifest.MANIFEST_FILENAME}.*.tmp"))
    assert leftover == [], f"temp file(s) left behind: {leftover}"


def test_with_pattern_does_not_mutate_the_original_manifest() -> None:
    """`with_pattern`'s own docstring claims it never mutates `self`; nothing
    checked that claim until now. `upsert` depends on it: it calls
    `with_pattern` on `current` and then only writes the result, never
    `current` itself, so an implementation that mutated `current.patterns`
    in place would still (coincidentally) produce a correct file today --
    but would silently break the moment any caller inspects the pre-upsert
    `Manifest` after calling `with_pattern` on it, which is exactly the
    guarantee the docstring promises."""
    manifest = _load_manifest()
    original = manifest.Manifest(bundle="2.0.0", patterns={})
    entry = manifest.PatternEntry(version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"))

    updated = original.with_pattern("ddd", entry, bundle="2.0.0")

    assert "ddd" not in original.patterns
    assert "ddd" in updated.patterns


def test_with_pattern_rejects_an_invalid_pattern_name() -> None:
    manifest = _load_manifest()
    original = manifest.Manifest(bundle="2.0.0", patterns={})
    entry = manifest.PatternEntry(version="3", installed_as="tcs-ddd", sha256=_sha("ddd-3"))

    with pytest.raises(ValueError):
        original.with_pattern("Not A Valid Name!", entry, bundle="2.0.0")


def test_read_treats_a_directory_at_the_manifest_path_as_absent(tmp_path: Path) -> None:
    """Pins `path.is_file()` specifically over `path.exists()`: the latter
    is also `True` for a directory, which would then reach `read_text()`
    and raise `IsADirectoryError` -- a third outcome this module's two-state
    contract (absent vs. unparseable) has no room for."""
    manifest = _load_manifest()
    path = _manifest_path(tmp_path, manifest)
    path.parent.mkdir(parents=True)
    path.mkdir()  # a directory, not a file, at the manifest's own path

    result = manifest.read(tmp_path)

    assert result.bundle is None
    assert result.patterns == {}
