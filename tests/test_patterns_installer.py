"""T3.3 (spec-020): the installer (component C5).

`install(repo_dir, names, *, catalogue_dir) -> InstallReport` is the write
path: copy, frontmatter rename, hash, manifest upsert, report. It **assumes
every name it is given already cleared the collision guard (C4)** and never
imports `guard` -- that assumption is what this file tests, not the
partition itself (`test_patterns_guard.py` owns that) `[ref: docs/XDD/specs/
020-tcs-patterns-selective-install/plan/phase-3.md#T3.3]`.

Deliberately a SEPARATE file from `test_patterns_install.py`, which is T3.1's
manifest-store suite (C6) -- the name collision between "install" (this
component, C5) and "install" (that file's historical name, predating this
task) is confusing and settled; do not merge them.

This file is written against `install.py` before that module exists, so
every test below fails for want of the module rather than passing by
construction -- the RED half of T3.3's TDD gate. The import happens at
RUNTIME inside each loader function, not at module level, for the same
reason `test_patterns_guard.py` and `test_patterns_install.py` do this: a
module-level `ImportError` would abort collection of this whole file rather
than failing only the tests that need the module.

**Six clarifications this file is built against, all from `solution.md`'s
"Data model: the install plan and report (C5)" and T3.3's task text --
read there for the full reasoning, this is only the one-line form:**

1. `install()` takes names, never a `GuardReport` -- not exercised directly
   here; there is simply no `guard` import anywhere below.
2. "No change" on a second install means CONTENT, proven by a digest over
   the installed tree *and* the manifest -- never mtimes.
3. The manifest is upserted per pattern, after that pattern's directory
   lands, not per run.
4. Each pattern appears atomically: temp directory inside the destination,
   then `os.rename`.
5. `install()` reports; it never raises `pytest.raises(InstallError)`-style
   for a single bad pattern among others, and never prompts.
6. `catalogue_dir` defaults to this plugin's own `templates/patterns/`,
   derived from `install.py`'s own `__file__` -- tested once, against the
   REAL catalogue, by omitting the parameter entirely.

**`install()` is purely additive** (clarification g in the task text): the
three states of `<repo>/.claude/skills/tcs-<name>/` are absent (write),
present-and-current (leave alone, report `unchanged`), present-and-anything-
else (leave alone, report `failed` naming `update`) -- NONE of them deletes.
Every test that calls `install()` against a pre-existing installed pattern
below carries a digest proving nothing on disk changed, not only a
report-channel assertion -- a mutation that reports `failed` correctly while
still overwriting the file passes any test that checks only the report
`[ref: solution.md, "install() is purely additive"]`.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"
REAL_CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"


def _load_install() -> ModuleType:
    """See `test_patterns_guard.py::_load_guard` for why this import happens
    here rather than at module level, and why `sys.path` (not `PYTHONPATH`)
    is how a mutated copy must be loaded when mutation-testing this file."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("install")


def _load_manifest() -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("manifest")


# --- fixture builders --------------------------------------------------------


def _catalogue_pattern(
    catalogue_root: Path,
    name: str,
    *,
    version: str = "1",
    skill_bytes: bytes | None = None,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """Create `catalogue_root/name/` with a `VERSION` file and a `SKILL.md`.

    `skill_bytes` is written with `write_bytes`, never `write_text`, so a
    CRLF fixture's `\\r\\n` survives untouched -- `write_text`'s default
    universal-newlines mode would translate it on some platforms."""
    d = catalogue_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    if skill_bytes is None:
        skill_bytes = (
            f"---\nname: {name}\ndescription: fixture pattern for T3.3\n---\n\nBody for {name}.\n"
        ).encode("utf-8")
    (d / "SKILL.md").write_bytes(skill_bytes)
    for rel, content in (extra_files or {}).items():
        path = d / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return d


def _digest_tree(root: Path) -> str:
    """A single sha256 over every entry under `root`: path plus content.
    Same shape as `test_patterns_guard.py::_digest_tree` -- used here to
    prove `install()` changed nothing on disk, which is one step stronger
    than checking the report alone `[ref: solution.md, "install() is purely
    additive"]`."""
    if not root.exists():
        return "ABSENT"
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root)
        h.update(b"DIR:")
        h.update(Path(rel_dir).as_posix().encode())
        h.update(b"\n")
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = (Path(rel_dir) / name).as_posix()
            h.update(rel.encode())
            try:
                h.update(full.read_bytes())
            except OSError as e:
                h.update(f"UNREADABLE:{e}".encode())
    return h.hexdigest()


def _skills_root(repo: Path) -> Path:
    return repo / ".claude" / "skills"


# --- clarification 1 & the primary write path --------------------------------


def test_chosen_pattern_lands_with_tcs_prefix_and_full_subtree(tmp_path: Path) -> None:
    """Full subtree, not just `SKILL.md` -- a mutation copying only
    `SKILL.md` survives any test that merely checks the directory exists, so
    this fixture carries a `reference/*.md` file and asserts its BYTES
    match the catalogue's (clarification b)."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        "ddd",
        version="3",
        extra_files={"reference/bounded-contexts.md": "# Bounded contexts\n\nFixture content.\n"},
    )
    repo = tmp_path / "repo"

    report = install.install(repo, ["ddd"], catalogue_dir=catalogue)

    dest = _skills_root(repo) / "tcs-ddd"
    assert dest.is_dir()
    assert dest.joinpath("SKILL.md").read_text(encoding="utf-8").splitlines()[1] == "name: tcs-ddd"
    assert (dest / "reference" / "bounded-contexts.md").read_bytes() == (
        catalogue / "ddd" / "reference" / "bounded-contexts.md"
    ).read_bytes()
    assert "ddd" in report.installed
    assert report.failed == {}


def test_nothing_unchosen_is_written(tmp_path: Path) -> None:
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "alpha")
    _catalogue_pattern(catalogue, "beta")
    repo = tmp_path / "repo"

    report = install.install(repo, ["alpha"], catalogue_dir=catalogue)

    assert (_skills_root(repo) / "tcs-alpha").is_dir()
    assert not (_skills_root(repo) / "tcs-beta").exists()
    assert "beta" not in report.installed
    manifest = _load_manifest()
    assert "beta" not in manifest.read(repo).patterns


def test_manifest_records_version_installed_name_and_hash_for_each(tmp_path: Path) -> None:
    install = _load_install()
    manifest = _load_manifest()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="3")
    _catalogue_pattern(catalogue, "hexagonal", version="2")
    repo = tmp_path / "repo"

    report = install.install(repo, ["ddd", "hexagonal"], catalogue_dir=catalogue)

    after = manifest.read(repo)
    for name in ("ddd", "hexagonal"):
        installed_as, version, sha256 = report.installed[name]
        entry = after.patterns[name]
        assert entry.installed_as == installed_as == f"tcs-{name}"
        assert entry.version == version
        assert entry.sha256 == sha256
        # independently recomputed, never trusting the report's own number
        expected_hash = hashlib.sha256(
            (_skills_root(repo) / f"tcs-{name}" / "SKILL.md").read_bytes()
        ).hexdigest()
        assert entry.sha256 == expected_hash


def test_report_lists_writes_and_committed_is_false(tmp_path: Path) -> None:
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd")
    repo = tmp_path / "repo"

    report = install.install(repo, ["ddd"], catalogue_dir=catalogue)

    assert report.committed is False  # identity, not falsiness -- always False, never merely falsy
    assert set(report.installed) == {"ddd"}


# --- clarification c: the test computes the hash independently --------------


def test_sha256_in_report_matches_independently_computed_hash_of_installed_file(tmp_path: Path) -> None:
    """The fixture's catalogue `name:` necessarily differs from the installed
    `tcs-<name>`, so the two files' bytes differ -- a mutation hashing the
    CATALOGUE's original bytes is caught only because this test reads the
    INSTALLED file itself, independently, rather than calling anything in
    `install.py` to get its expectation."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "hexagonal", version="2")
    repo = tmp_path / "repo"

    report = install.install(repo, ["hexagonal"], catalogue_dir=catalogue)

    installed_skill_md = _skills_root(repo) / "tcs-hexagonal" / "SKILL.md"
    expected = hashlib.sha256(installed_skill_md.read_bytes()).hexdigest()
    _installed_as, _version, sha256 = report.installed["hexagonal"]
    assert sha256 == expected
    # and it must NOT equal the catalogue's own (pre-rename) bytes
    assert sha256 != hashlib.sha256((catalogue / "hexagonal" / "SKILL.md").read_bytes()).hexdigest()


# --- clarification a & d: a per-pattern fault never escapes install() -------


def test_malformed_name_fails_one_pattern_while_the_other_installs_in_one_call(tmp_path: Path) -> None:
    """A SINGLE `install()` call, good name first in `names`, so "earlier
    patterns stay" is exercised by order rather than assumed. Must NOT be
    wrapped in `pytest.raises` -- that would test the opposite of the
    contract and could not observe the other pattern installing
    (clarifications a and d)."""
    install = _load_install()
    manifest = _load_manifest()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "good")
    _catalogue_pattern(
        catalogue,
        "bad",
        skill_bytes=b"---\ndescription: no name key at all\n---\n\nBody.\n",
    )
    repo = tmp_path / "repo"

    report = install.install(repo, ["good", "bad"], catalogue_dir=catalogue)

    assert report.installed["good"][0] == "tcs-good"
    assert "bad" in report.failed and report.failed["bad"]
    assert (_skills_root(repo) / "tcs-good").is_dir()
    assert not (_skills_root(repo) / "tcs-bad").exists()
    assert not (_skills_root(repo) / ".tcs-bad.tmp").exists()
    assert "bad" not in manifest.read(repo).patterns


def test_missing_name_key_raises_rather_than_installing_unprefixed(tmp_path: Path) -> None:
    """Success criterion 2, in isolation: a `SKILL.md` with no frontmatter
    `name:` line must never be installed under any name at all -- not
    `tcs-bad`, not the bare catalogue name."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        "bad",
        skill_bytes=b"---\ndescription: no name key\n---\n\nBody.\n",
    )
    repo = tmp_path / "repo"

    report = install.install(repo, ["bad"], catalogue_dir=catalogue)

    assert "bad" in report.failed
    assert not (_skills_root(repo) / "tcs-bad").exists()
    assert not (_skills_root(repo) / "bad").exists()


# --- clarification 2: idempotency is content, never mtimes -----------------


def test_second_identical_install_is_a_noop_by_content_and_manifest_digest(tmp_path: Path) -> None:
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="3")
    repo = tmp_path / "repo"

    first = install.install(repo, ["ddd"], catalogue_dir=catalogue)
    assert "ddd" in first.installed

    digest_after_first = _digest_tree(_skills_root(repo))
    second = install.install(repo, ["ddd"], catalogue_dir=catalogue)
    digest_after_second = _digest_tree(_skills_root(repo))

    assert digest_after_first == digest_after_second
    assert "ddd" in second.unchanged
    assert "ddd" not in second.installed
    assert second.unchanged["ddd"] == first.installed["ddd"]


# --- clarification e: the one ACCEPT path the rewrite correction changed ---


def test_crlf_skill_md_installs_successfully(tmp_path: Path) -> None:
    """The corrected `rename_in_frontmatter` fixed a FALSE rejection: the old
    `startswith("---\\n")` refused a CRLF file. Every other frontmatter test
    in this suite covers a raise path; this is the one accept path the
    correction changed."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        "crlf-pattern",
        skill_bytes=b"---\r\nname: crlf-pattern\r\ndescription: CRLF fixture\r\n---\r\n\r\nBody.\r\n",
    )
    repo = tmp_path / "repo"

    report = install.install(repo, ["crlf-pattern"], catalogue_dir=catalogue)

    assert "crlf-pattern" in report.installed
    installed_text = (_skills_root(repo) / "tcs-crlf-pattern" / "SKILL.md").read_bytes()
    assert b"\r\nname: tcs-crlf-pattern\r\n" in installed_text
    assert installed_text.endswith(b"Body.\r\n")


# --- clarification 6 / f: the default catalogue_dir, against the REAL tree -


def test_default_catalogue_dir_resolves_to_the_real_templates_patterns_dir(tmp_path: Path) -> None:
    """Builds its expected path independently -- `REPO_ROOT / "plugins" /
    "tcs-patterns" / "templates" / "patterns"` -- rather than reading
    `install.py`'s own `parents[3]` expression back at it, which would make
    this a snapshot of the code under test (the failure that got past
    T3.1's gate). `catalogue_dir` is omitted entirely from the call."""
    install = _load_install()
    expected_catalogue_dir = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"
    assert expected_catalogue_dir.is_dir(), "the real catalogue must exist for this test to mean anything"
    expected_version = (expected_catalogue_dir / "ddd" / "VERSION").read_text(encoding="utf-8").strip()
    repo = tmp_path / "repo"

    report = install.install(repo, ["ddd"])  # no catalogue_dir -- must use the real one

    assert "ddd" in report.installed
    installed_as, version, sha256 = report.installed["ddd"]
    assert installed_as == "tcs-ddd"
    assert version == expected_version
    installed_skill_md = _skills_root(repo) / "tcs-ddd" / "SKILL.md"
    assert sha256 == hashlib.sha256(installed_skill_md.read_bytes()).hexdigest()
    assert report.committed is False


def test_all_21_catalogue_names_are_plain_scalars_for_the_rename(tmp_path: Path) -> None:
    """The precondition the installer's rename depends on is narrower than
    parseability (`test_all_21_frontmatter_blocks_still_parse_as_yaml`
    proves only that they parse, which a block scalar also does). Runs the
    REAL `rename_in_frontmatter` against all 21 real catalogue files and
    asserts none of them is refused -- the refusal is only harmless while
    this holds `[ref: solution.md, "A test must pin that all 21 catalogue
    name: values are plain scalars"]`."""
    install = _load_install()
    skill_mds = sorted(REAL_CATALOGUE_DIR.glob("*/SKILL.md"))
    assert len(skill_mds) == 21, "catalogue must hold all 21 patterns for this precondition to mean anything"

    for skill_md in skill_mds:
        text = skill_md.read_text(encoding="utf-8")
        patched = install.rename_in_frontmatter(text, "tcs-placeholder")
        assert "name: tcs-placeholder" in patched


# --- clarification g: purely additive -- absent / current / anything else -


def test_present_locally_edited_pattern_is_failed_and_untouched(tmp_path: Path) -> None:
    """Fixture 1 of 2 (clarification h): version matches the catalogue, but
    the installed `SKILL.md`'s hash does not match the manifest's recorded
    hash -- a local edit. Asserts the digest over the whole skills tree is
    IDENTICAL before and after the second call, not only the report
    channel -- the mutation this kills reports `failed` correctly while
    still overwriting the file on disk."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "edited", version="2")
    repo = tmp_path / "repo"
    first = install.install(repo, ["edited"], catalogue_dir=catalogue)
    assert "edited" in first.installed

    installed_path = _skills_root(repo) / "tcs-edited" / "SKILL.md"
    installed_path.write_bytes(installed_path.read_bytes() + b"\nLocally added paragraph.\n")

    digest_before = _digest_tree(_skills_root(repo))
    second = install.install(repo, ["edited"], catalogue_dir=catalogue)
    digest_after = _digest_tree(_skills_root(repo))

    assert digest_before == digest_after
    assert "update" in second.failed["edited"]
    assert "edited" not in second.installed
    assert "edited" not in second.unchanged


def test_present_stale_but_unedited_pattern_is_failed_and_untouched(tmp_path: Path) -> None:
    """Fixture 2 of 2 (clarification h): the installed file is byte-for-byte
    what was installed (hash matches the manifest), but the CATALOGUE's
    `VERSION` has since moved on -- stale, never locally edited. A mutation
    that treats "version stale but unedited" as eligible for a silent write
    survives fixture 1 above and is caught only by this one."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "stale", version="1")
    repo = tmp_path / "repo"
    first = install.install(repo, ["stale"], catalogue_dir=catalogue)
    assert "stale" in first.installed

    (catalogue / "stale" / "VERSION").write_text("2\n", encoding="utf-8")  # catalogue moves on; file untouched

    digest_before = _digest_tree(_skills_root(repo))
    second = install.install(repo, ["stale"], catalogue_dir=catalogue)
    digest_after = _digest_tree(_skills_root(repo))

    assert digest_before == digest_after
    assert "update" in second.failed["stale"]
    assert "stale" not in second.installed
    assert "stale" not in second.unchanged


# --- the installer's own leftover temp directory ----------------------------


def test_leftover_tmp_directory_from_a_crashed_run_is_cleaned(tmp_path: Path) -> None:
    """The ONE delete `install()` may perform: its own `.tcs-<name>.tmp/`
    debris from an earlier crashed attempt, never a user's installed
    pattern. Pre-seeding garbage under that exact name must not leak into
    the final `tcs-good/` directory."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "good")
    repo = tmp_path / "repo"
    leftover = _skills_root(repo) / ".tcs-good.tmp"
    leftover.mkdir(parents=True)
    (leftover / "garbage-from-a-crashed-run.txt").write_text("stale debris\n", encoding="utf-8")

    report = install.install(repo, ["good"], catalogue_dir=catalogue)

    assert "good" in report.installed
    dest = _skills_root(repo) / "tcs-good"
    assert not (dest / "garbage-from-a-crashed-run.txt").exists()
    assert not leftover.exists()
    assert dest.joinpath("SKILL.md").read_text(encoding="utf-8").splitlines()[1] == "name: tcs-good"


# --- clarification i: directory-then-manifest order, a narrow monkeypatch -


def test_directory_lands_even_when_the_manifest_upsert_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every OTHER failure path in this file fails during the frontmatter
    rewrite, which happens BEFORE the final `os.rename` -- so neither the
    directory nor the manifest entry is ever written and the order between
    them is invisible. A mutation calling `manifest.upsert()` before the
    rename would pass every other test here. Monkeypatches `manifest.upsert`
    to fail for exactly one target name; the directory-write path still runs
    for real `[ref: plan/phase-3.md T3.3, clarification i]`."""
    install = _load_install()
    manifest = _load_manifest()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "good")
    repo = tmp_path / "repo"

    real_upsert = manifest.upsert

    def _failing_upsert(repo_dir, name, **kwargs):
        if name == "good":
            raise RuntimeError("simulated manifest upsert failure")
        return real_upsert(repo_dir, name, **kwargs)

    monkeypatch.setattr(manifest, "upsert", _failing_upsert)

    report = install.install(repo, ["good"], catalogue_dir=catalogue)

    dest = _skills_root(repo) / "tcs-good"
    assert dest.is_dir()
    assert dest.joinpath("SKILL.md").read_text(encoding="utf-8").splitlines()[1] == "name: tcs-good"
    assert "good" not in manifest.read(repo).patterns
    assert "good" in report.failed


# --- rename_in_frontmatter, the three corrections, exercised directly ------


def test_rename_in_frontmatter_rejects_unterminated_block_as_install_error() -> None:
    install = _load_install()
    with pytest.raises(install.InstallError):
        install.rename_in_frontmatter("---\nname: ddd\nno closing delimiter at all\n", "tcs-ddd")


def test_rename_in_frontmatter_rejects_block_scalar_name() -> None:
    install = _load_install()
    with pytest.raises(install.InstallError):
        install.rename_in_frontmatter("---\nname: >-\n  ddd\n---\n\nBody.\n", "tcs-ddd")


def test_rename_in_frontmatter_leaves_body_byte_identical_including_name_shaped_line() -> None:
    """Nothing below the closing `---` may change, including a `name:`-
    shaped line in the BODY -- only the frontmatter's own `name:` line is
    touched."""
    install = _load_install()
    text = "---\nname: ddd\ndescription: x\n---\n\nBody mentions name: ddd again here.\n"
    patched = install.rename_in_frontmatter(text, "tcs-ddd")
    body = text.split("---", 2)[2]
    assert patched.endswith(body)
    assert "name: ddd again here" in patched
