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

---

**T3.4 added `update()`'s suite to this same file** (C5's second verb, below
the `=== T3.4 ===` banner). Still not `test_patterns_install.py`, which
remains T3.1's manifest store (C6), and still not `test_patterns_guard.py`,
which is C4.

**Why ADR-4's byte-identical guarantee and its `reference/` limit are not in
conflict -- they are different rows of the contract's three-state table**
`[ref: solution.md, "Data model: the update path (C5's second verb)",
decision 2; SDD/ADR-4, "Trade-offs accepted"]`. Read together without the
table they look like a contradiction ("nothing local is ever lost without
consent" against "a local `reference/` edit is replaced with no prompt"), and
the two fixtures below sit one in each row:

- The **byte-identical guarantee** is the **hash-differs** row. `decide`
  returned `False`, so the whole directory is left alone, `reference/`
  included -- proven by a digest, not by a report channel.
- **"Replaced without a prompt"** is the **version-behind, hash-matches**
  row. The refresh there is unconditional, and it overwrites the full
  directory, a locally edited `reference/` file included.

Both hold because **the hash never covered `reference/`**: a
`reference/`-only edit cannot put a pattern into the hash-differs row at
all, so it never reaches the row where consent is asked. The fixture making
that visible is version stale, `SKILL.md` hash **matching** the manifest, a
`reference/` file hand-edited -- then the refresh overwrites it.

And the limit on *detection* is not a limit on *replacement*: when `decide`
returns `True` the **whole subtree** is replaced, so the accept-path fixture
carries a `reference/` file too and asserts its bytes against the
catalogue's.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import re
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"
REAL_CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"

# Passed explicitly to every `install()` call in this file that is not
# itself testing the derived default -- mirrors T3.2b's `own_installed=
# frozenset()` through the guard's call sites. Without this, omitting
# `bundle` falls through to `_bundle_version()`, which reads a `plugin.json`
# relative to the MODULE's own `__file__` -- fine when `install.py` is
# loaded from its real location (as every test here does via
# `_load_install()`), but fatal when it is loaded from a relocated copy for
# mutation testing, since that copy's `__file__` resolves nowhere real. The
# two tests that must NOT pass this -- `test_default_catalogue_dir_resolves_
# to_the_real_templates_patterns_dir` and `test_bundle_defaults_to_the_
# installed_plugins_own_version` -- exist specifically to probe that real
# derivation and omit it on purpose.
TEST_BUNDLE = "0.0.0-test"


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


def _assert_uniform_line_endings(data: bytes, *, crlf: bool) -> None:
    """Every line terminator in `data` is `\\r\\n` (`crlf=True`) or a bare
    `\\n` (`crlf=False`) -- never a mix. Pins the fourth defect in
    `rename_in_frontmatter`'s corrected sample: `(?m)^name:.*$`'s `.`
    matches `\\r`, so the ONE line being rewritten silently lost its
    trailing `\\r` on a CRLF file -- a 5-line CRLF input came out as 4 CRLF
    lines and 1 bare LF line. `[^\\r\\n]*` fixes it
    `[ref: solution.md, "The rewrite preserves every line ending, including
    the one it rewrites"]`. A body-byte-identical assertion alone cannot
    see this: the rewritten line is in the frontmatter, not the body."""
    for i, byte in enumerate(data):
        if byte != 0x0A:  # '\n'
            continue
        preceded_by_cr = i > 0 and data[i - 1] == 0x0D
        assert preceded_by_cr == crlf, f"inconsistent line ending at byte {i} in {data!r}"


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

    report = install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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

    report = install.install(repo, ["alpha"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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

    report = install.install(repo, ["ddd", "hexagonal"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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

    report = install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    assert report.committed is False  # identity, not falsiness -- always False, never merely falsy
    assert set(report.installed) == {"ddd"}


# --- clarification 7: bundle is a parameter, with a derived default --------


def test_explicit_bundle_reaches_the_manifest(tmp_path: Path) -> None:
    """`bundle` is a parameter now (added after T3.3's first review round,
    `solution.md`'s point 7): the one input to `install()` that otherwise
    could not be driven by a test, since `catalogue_dir` and C4's
    `home_dir`/`own_installed` exist for exactly that reason. Passing an
    explicit value must reach the manifest's top-level `bundle` field
    verbatim -- a plugin.json-reading default a test cannot override would
    make this assertion impossible to write, and would break on every CI
    version bump besides."""
    install = _load_install()
    manifest = _load_manifest()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd")
    repo = tmp_path / "repo"

    install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle="9.9.9-test")

    assert manifest.read(repo).bundle == "9.9.9-test"


def test_bundle_defaults_to_the_installed_plugins_own_version(tmp_path: Path) -> None:
    """Omitting `bundle` must still produce a legal manifest -- the derived
    default (this plugin's own `plugin.json`) is kept as the fallback route,
    not replaced by the parameter `[ref: solution.md, point 7]`."""
    install = _load_install()
    manifest = _load_manifest()
    expected_bundle = json.loads(
        (REPO_ROOT / "plugins" / "tcs-patterns" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd")
    repo = tmp_path / "repo"

    install.install(repo, ["ddd"], catalogue_dir=catalogue)  # bundle omitted entirely

    assert manifest.read(repo).bundle == expected_bundle


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

    report = install.install(repo, ["hexagonal"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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

    report = install.install(repo, ["good", "bad"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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

    report = install.install(repo, ["bad"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    assert "bad" in report.failed
    assert not (_skills_root(repo) / "tcs-bad").exists()
    assert not (_skills_root(repo) / "bad").exists()


# --- clarification 2: idempotency is content, never mtimes -----------------


def test_second_identical_install_is_a_noop_by_content_and_manifest_digest(tmp_path: Path) -> None:
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="3")
    repo = tmp_path / "repo"

    first = install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    assert "ddd" in first.installed

    digest_after_first = _digest_tree(_skills_root(repo))
    second = install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    digest_after_second = _digest_tree(_skills_root(repo))

    assert digest_after_first == digest_after_second
    assert "ddd" in second.unchanged
    assert "ddd" not in second.installed
    assert second.unchanged["ddd"] == first.installed["ddd"]


# --- clarification e: the one ACCEPT path the rewrite correction changed ---


def test_crlf_skill_md_installs_successfully_and_stays_crlf_throughout(tmp_path: Path) -> None:
    """The corrected `rename_in_frontmatter` fixed a FALSE rejection: the old
    `startswith("---\\n")` refused a CRLF file. Every other frontmatter test
    in this suite covers a raise path; this is the one accept path the
    correction changed.

    **The contract is stronger than "the body is byte-identical".** A CRLF
    file must install as CRLF THROUGHOUT, including the one line that is
    intentionally rewritten -- `solution.md`'s correction names the weaker
    body-only assertion as insufficient, because it holds even when the
    rewritten line's own ending has changed `[ref: solution.md, "The
    rewrite preserves every line ending, including the one it rewrites"]`.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        "crlf-pattern",
        skill_bytes=b"---\r\nname: crlf-pattern\r\ndescription: CRLF fixture\r\n---\r\n\r\nBody.\r\n",
    )
    repo = tmp_path / "repo"

    report = install.install(repo, ["crlf-pattern"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    assert "crlf-pattern" in report.installed
    installed_text = (_skills_root(repo) / "tcs-crlf-pattern" / "SKILL.md").read_bytes()
    assert installed_text == (
        b"---\r\nname: tcs-crlf-pattern\r\ndescription: CRLF fixture\r\n---\r\n\r\nBody.\r\n"
    )
    _assert_uniform_line_endings(installed_text, crlf=True)


def test_lf_skill_md_installs_successfully_and_stays_lf_throughout(tmp_path: Path) -> None:
    """The other half of the same guarantee: an LF file installs as LF
    throughout, with no CRLF creeping in anywhere -- the two cases are
    symmetric, and a mutation that hard-codes `\\r\\n` into the replacement
    would pass the CRLF test above while failing this one."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        "lf-pattern",
        skill_bytes=b"---\nname: lf-pattern\ndescription: LF fixture\n---\n\nBody.\n",
    )
    repo = tmp_path / "repo"

    report = install.install(repo, ["lf-pattern"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    assert "lf-pattern" in report.installed
    installed_text = (_skills_root(repo) / "tcs-lf-pattern" / "SKILL.md").read_bytes()
    assert installed_text == b"---\nname: tcs-lf-pattern\ndescription: LF fixture\n---\n\nBody.\n"
    _assert_uniform_line_endings(installed_text, crlf=False)


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
    first = install.install(repo, ["edited"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    assert "edited" in first.installed

    installed_path = _skills_root(repo) / "tcs-edited" / "SKILL.md"
    installed_path.write_bytes(installed_path.read_bytes() + b"\nLocally added paragraph.\n")

    digest_before = _digest_tree(_skills_root(repo))
    second = install.install(repo, ["edited"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
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
    first = install.install(repo, ["stale"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    assert "stale" in first.installed

    (catalogue / "stale" / "VERSION").write_text("2\n", encoding="utf-8")  # catalogue moves on; file untouched

    digest_before = _digest_tree(_skills_root(repo))
    second = install.install(repo, ["stale"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
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

    report = install.install(repo, ["good"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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

    report = install.install(repo, ["good"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

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


# =============================================================================
# T3.4: `update()`, C5's second verb
# =============================================================================
#
# The three states, exactly as the contract's table defines them
# `[ref: solution.md, "Data model: the update path (C5's second verb)",
# decision 2]`. Every fixture below is built to sit in exactly one row:
#
#   manifest `version` vs catalogue `VERSION` | installed hash vs manifest `sha256`
#   ---------------------------------------- | -----------------------------------
#   equal                                    | equal   -> `current`, nothing done
#   BEHIND                                   | equal   -> refreshed, NO prompt
#   any                                      | DIFFERS -> decide(name, diff)
#
# `update()` takes no `names` argument at all -- the manifest is its only
# input about what to act on (F8's first criterion: no scan, no questions)
# `[ref: decision 1]`.


_DIVERGED_NAME = "api-design"

# The catalogue's own bytes for the divergence fixtures.
_DIVERGED_CATALOGUE_SKILL = (
    "---\n"
    "name: api-design\n"
    "description: fixture pattern for T3.4\n"
    "---\n"
    "\n"
    "Upstream body line, unedited.\n"
)

# The same file as it must appear once INSTALLED -- hand-written, with the
# `tcs-` prefix already applied, and deliberately NOT produced by calling
# `rename_in_frontmatter`, the helper `update()` itself uses to build the
# diff's `to` side. A shared bug in that helper would otherwise appear
# identically on both sides of the comparison and pass
# `[ref: phase-3.md#T3.4, "never by calling the same rename helper"]`.
_DIVERGED_CATALOGUE_AS_INSTALLED = (
    "---\n"
    "name: tcs-api-design\n"
    "description: fixture pattern for T3.4\n"
    "---\n"
    "\n"
    "Upstream body line, unedited.\n"
)

_UPSTREAM_LINE = "Upstream body line, unedited."
# The user's hand edit. Must NOT start with `name:`, or the `^[-+]name:`
# assertion below would be checking something other than what it is written
# for `[ref: phase-3.md#T3.4]`.
_USER_EDIT_LINE = "Locally adapted body line, mine."

_DIVERGED_INSTALLED_EDITED = _DIVERGED_CATALOGUE_AS_INSTALLED.replace(_UPSTREAM_LINE, _USER_EDIT_LINE)


def _manifest_bytes(repo: Path) -> bytes:
    """The manifest file's raw bytes, or a sentinel when absent. A literal
    byte comparison, not an "entry unchanged" paraphrase -- that is what
    catches a mutation reporting `declined` correctly and writing the
    manifest anyway `[ref: phase-3.md#T3.4]`."""
    manifest = _load_manifest()
    path = Path(repo).joinpath(*manifest.MANIFEST_DIR, manifest.MANIFEST_FILENAME)
    return path.read_bytes() if path.is_file() else b"ABSENT"


def _entry_fields(repo: Path, name: str) -> tuple[str, str, str]:
    entry = _load_manifest().read(repo).patterns[name]
    return (entry.version, entry.installed_as, entry.sha256)


def _assert_diff_properties(diff: str, *, where: str) -> None:
    """The four properties the contract pins about the divergence diff, and
    only those four.

    `n` (the context width) is explicitly NOT pinned and must not be
    asserted `[ref: solution.md, decision 4, "The context width n is NOT
    pinned"]`, which is why this asserts properties rather than comparing
    against a diff literal: measured, populating the labels changes two
    lines and `n=5` turns an 8-line diff into 10, so an exact-equality test
    fails against a *conforming* implementation.

    1. The user's edit appears as a DELETION -- sign-aware. A
       direction-reversed diff contains the edit text as an *addition*, so a
       sign-blind "the edit is in there somewhere" check passes it.
    2. The incoming catalogue text appears as an ADDITION -- the mirror of
       1, which is what makes the pair fail a reversal rather than only one.
    3. No `^[-+]name:` line -- a diff computed against the catalogue's
       PRE-rename bytes contains the user's edit too, just additionally
       polluted with a `name:` hunk, so 1 alone does not catch it.
    4. Both header labels populated, as decision 4 pins them. `difflib`
       defaults both to empty, so this fails a plain `unified_diff(a, b)`.
    """
    lines = diff.splitlines()
    assert f"-{_USER_EDIT_LINE}" in lines, f"{where}: the user's edit is not a deletion: {diff!r}"
    assert f"+{_UPSTREAM_LINE}" in lines, f"{where}: the catalogue text is not an addition: {diff!r}"
    polluted = [line for line in lines if re.match(r"^[-+]name:", line)]
    assert polluted == [], f"{where}: diff carries a pre-rename `name:` hunk: {polluted!r}"
    assert "--- installed" in lines, f"{where}: `fromfile` label not populated: {diff!r}"
    assert "+++ catalogue" in lines, f"{where}: `tofile` label not populated: {diff!r}"


def _diverged_fixture(tmp_path: Path, *, extra_files: dict[str, str] | None = None) -> tuple[Path, Path]:
    """Install `api-design`, then hand-edit ONE BODY LINE of the installed
    `SKILL.md` so its hash no longer matches the manifest -- the contract's
    third row, which always asks.

    The catalogue `VERSION` is left EQUAL to the manifest's on purpose, so
    the "any" in that row's first column is genuinely exercised rather than
    co-varying with staleness.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        _DIVERGED_NAME,
        version="1",
        skill_bytes=_DIVERGED_CATALOGUE_SKILL.encode("utf-8"),
        extra_files=extra_files,
    )
    repo = tmp_path / "repo"
    first = install.install(repo, [_DIVERGED_NAME], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    assert _DIVERGED_NAME in first.installed

    installed_skill_md = _skills_root(repo) / f"tcs-{_DIVERGED_NAME}" / "SKILL.md"
    # The hand-written literal must actually be what the installer writes,
    # or every diff assertion below is pinned against a file shape that
    # never occurs. Checked once, here, rather than assumed in four tests.
    assert installed_skill_md.read_bytes() == _DIVERGED_CATALOGUE_AS_INSTALLED.encode("utf-8")
    installed_skill_md.write_bytes(_DIVERGED_INSTALLED_EDITED.encode("utf-8"))
    return catalogue, repo


# --- decision 1: the manifest is the only selection input -------------------


def test_update_acts_on_every_manifest_pattern_and_has_no_names_parameter(tmp_path: Path) -> None:
    """F8's first criterion, both halves. There is no `names` parameter to
    pass a selection through (the signature half), and a catalogue pattern
    the manifest does not record is neither acted on nor written (the
    behavioural half) `[ref: PRD/F8 1st; solution.md, decision 1]`."""
    install = _load_install()
    sig = inspect.signature(install.update)
    assert "names" not in sig.parameters
    positional = [p for p in sig.parameters.values() if p.kind is not inspect.Parameter.KEYWORD_ONLY]
    assert positional == [sig.parameters["repo_dir"]]

    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="1")
    _catalogue_pattern(catalogue, "hexagonal", version="1")
    _catalogue_pattern(catalogue, "unselected", version="1")
    repo = tmp_path / "repo"
    first = install.install(repo, ["ddd", "hexagonal"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    assert sorted(first.installed) == ["ddd", "hexagonal"]
    (catalogue / "hexagonal" / "VERSION").write_text("2\n", encoding="utf-8")

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    assert "ddd" in report.current
    assert "hexagonal" in report.refreshed
    for channel in (report.refreshed, report.declined, report.current, report.failed):
        assert "unselected" not in channel
    assert not (_skills_root(repo) / "tcs-unselected").exists()


# --- the middle row: behind, hash matches -- refreshes without asking -------


def test_version_behind_with_matching_hash_refreshes_without_ever_calling_decide(tmp_path: Path) -> None:
    """The row worth stating explicitly: nothing local can be lost, so the
    refresh must not interrupt the user `[ref: solution.md, decision 2]`.

    `decide` RECORDS every invocation and returns `True`, so the only
    assertion that can fail here is the empty call list itself -- a mutation
    that asks is caught by `calls == []` rather than by a cascade of
    downstream failures. One pattern in the manifest, so there is no
    ambiguity about which pattern would have triggered the call
    `[ref: phase-3.md#T3.4]`.

    `version_before` is pinned as well as `version_after` -- without it a
    mutation swapping the two elements, or hardcoding the first, survives.
    """
    install = _load_install()
    manifest = _load_manifest()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "testing", version="1")
    repo = tmp_path / "repo"
    assert "testing" in install.install(repo, ["testing"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed

    version_before = manifest.read(repo).patterns["testing"].version
    assert version_before == "1"
    # Upstream moves on, in VERSION *and* in content. The INSTALLED file is
    # untouched, so its hash still matches the manifest.
    (catalogue / "testing" / "VERSION").write_text("2\n", encoding="utf-8")
    (catalogue / "testing" / "SKILL.md").write_bytes(
        b"---\nname: testing\ndescription: fixture pattern for T3.4\n---\n\nUpstream v2 body.\n"
    )

    calls: list[tuple[str, str]] = []

    def decide(name: str, diff: str) -> bool:
        calls.append((name, diff))
        return True

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert calls == []
    installed_as, got_before, got_after, sha256 = report.refreshed["testing"]
    assert installed_as == "tcs-testing"
    assert got_before == version_before
    # F8's third criterion applies to the no-prompt refresh too, not only
    # where `decide` returned True `[ref: PRD/F8 3rd; SDD/AC-17]`.
    assert got_after == (catalogue / "testing" / "VERSION").read_text(encoding="utf-8").strip()
    # Recomputed independently from the file on disk, mirroring
    # `test_sha256_in_report_matches_independently_computed_hash_of_installed_file`
    # -- never trusting a value `update()` produced.
    installed_skill_md = _skills_root(repo) / "tcs-testing" / "SKILL.md"
    assert sha256 == hashlib.sha256(installed_skill_md.read_bytes()).hexdigest()
    assert b"Upstream v2 body." in installed_skill_md.read_bytes()
    assert _entry_fields(repo, "testing") == ("2", "tcs-testing", sha256)
    assert report.committed is False


def test_version_behind_hash_matching_overwrites_a_locally_edited_reference_file(tmp_path: Path) -> None:
    """ADR-4's accepted limit, made visible rather than left to be
    discovered: the hash covers `SKILL.md` only, so a `reference/`-only edit
    cannot put a pattern into the hash-differs row at all -- it stays in the
    middle row, whose refresh is unconditional, and the local edit is
    replaced with no prompt `[ref: SDD/ADR-4, "Trade-offs accepted";
    solution.md, decision 6]`. Deliberate, and not a defect to fix here.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(
        catalogue,
        "observability",
        version="1",
        extra_files={"reference/guide.md": "# Upstream guide\n"},
    )
    repo = tmp_path / "repo"
    assert "observability" in install.install(
        repo, ["observability"], catalogue_dir=catalogue, bundle=TEST_BUNDLE
    ).installed

    # Catalogue version moves on; the installed SKILL.md is NOT touched, so
    # its hash still matches the manifest. Only the reference file is edited.
    (catalogue / "observability" / "VERSION").write_text("2\n", encoding="utf-8")
    local_ref = _skills_root(repo) / "tcs-observability" / "reference" / "guide.md"
    local_ref.write_bytes(b"# Local scribble, nothing upstream has.\n")

    calls: list[tuple[str, str]] = []

    def decide(name: str, diff: str) -> bool:
        calls.append((name, diff))
        return False

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert calls == []
    assert "observability" in report.refreshed
    assert local_ref.read_bytes() == (catalogue / "observability" / "reference" / "guide.md").read_bytes()


# --- the third row: hash differs -- always asks -----------------------------


def test_diverged_pattern_hands_decide_a_signed_and_labelled_diff(tmp_path: Path) -> None:
    """What `decide` RECEIVES. Asserted by the four properties the contract
    pins, never by equality against a diff literal -- see
    `_assert_diff_properties` for why each of the four exists and which
    mutation it kills."""
    install = _load_install()
    catalogue, repo = _diverged_fixture(tmp_path)

    calls: list[tuple[str, str]] = []

    def decide(name: str, diff: str) -> bool:
        calls.append((name, diff))
        return False

    install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert [name for name, _ in calls] == [_DIVERGED_NAME]
    _assert_diff_properties(calls[0][1], where="the diff passed into decide()")


def test_declined_report_carries_the_diff_with_the_same_four_properties(tmp_path: Path) -> None:
    """What the REPORT carries, asserted INDEPENDENTLY of what the callback
    received. `UpdateReport.declined[name][1]` is what a later advisory
    shows the user `[ref: SDD/Runtime View/Primary Flow, step 9]`, so a
    mutation computing the diff correctly for the callback and storing an
    empty string, a stale value or the pre-rename diff in the report is an
    externally visible bug.

    Deliberately NOT "the report equals what the callback received": that
    compares two values the code under test produces at two sites, so a
    compound mutation computing the *wrong* diff identically in both places
    is self-consistent and passes `[ref: phase-3.md#T3.4]`."""
    install = _load_install()
    manifest = _load_manifest()
    catalogue, repo = _diverged_fixture(tmp_path)
    version_before = manifest.read(repo).patterns[_DIVERGED_NAME].version

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=lambda name, diff: False)

    version, diff = report.declined[_DIVERGED_NAME]
    assert version == version_before
    _assert_diff_properties(diff, where="the diff stored in report.declined")


def test_declining_leaves_the_installed_file_and_the_manifest_byte_identical(tmp_path: Path) -> None:
    """ADR-4's guarantee on the decline path, proven by literal comparison
    twice over: a digest over the whole skills tree, and the manifest
    file's own bytes plus a field-by-field compare of its `PatternEntry`.
    The mutation this kills reports `declined` correctly and writes anyway
    `[ref: phase-3.md#T3.4]`."""
    install = _load_install()
    catalogue, repo = _diverged_fixture(tmp_path)
    entry_before = _entry_fields(repo, _DIVERGED_NAME)
    tree_before = _digest_tree(_skills_root(repo))
    manifest_before = _manifest_bytes(repo)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=lambda name, diff: False)

    assert _digest_tree(_skills_root(repo)) == tree_before
    assert _manifest_bytes(repo) == manifest_before
    assert _entry_fields(repo, _DIVERGED_NAME) == entry_before
    assert _DIVERGED_NAME in report.declined
    for channel in (report.refreshed, report.current, report.failed):
        assert _DIVERGED_NAME not in channel
    assert report.committed is False


def test_diverged_and_behind_still_asks_and_declining_writes_nothing(tmp_path: Path) -> None:
    """The third row's first column is "any", so a pattern that is BOTH
    behind and diverged still asks -- and declining must leave the manifest
    at its OLD version.

    This fixture exists because the version-equal decline fixture above
    cannot catch a mutation that reports `declined` correctly and upserts
    the manifest anyway: with the manifest `version` and the catalogue
    `VERSION` already equal, that erroneous write regenerates
    byte-identical content and every digest assertion passes. Measured
    against that exact mutant, which survives the two tests either side of
    this one `[ref: phase-3.md#T3.4, "Unchanged must be a literal
    comparison, twice over"]`."""
    install = _load_install()
    catalogue, repo = _diverged_fixture(tmp_path)
    (catalogue / _DIVERGED_NAME / "VERSION").write_text("2\n", encoding="utf-8")
    entry_before = _entry_fields(repo, _DIVERGED_NAME)
    assert entry_before[0] == "1"
    tree_before = _digest_tree(_skills_root(repo))
    manifest_before = _manifest_bytes(repo)
    calls: list[tuple[str, str]] = []

    def decide(name: str, diff: str) -> bool:
        calls.append((name, diff))
        return False

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert [name for name, _ in calls] == [_DIVERGED_NAME]
    version, diff = report.declined[_DIVERGED_NAME]
    assert version == "1"
    _assert_diff_properties(diff, where="the diff for a pattern both behind and diverged")
    assert _digest_tree(_skills_root(repo)) == tree_before
    assert _manifest_bytes(repo) == manifest_before
    assert _entry_fields(repo, _DIVERGED_NAME) == entry_before


def test_default_decide_declines_so_an_unanswered_prompt_destroys_nothing(tmp_path: Path) -> None:
    """`update()` called with NO callback argument at all -- not an explicit
    decliner. That is the only form that exercises the default, which is
    where "an unanswered prompt cannot destroy local work" lives now that it
    is held by this module rather than by C3's prose
    `[ref: SDD/ADR-4; solution.md, decision 3]`."""
    install = _load_install()
    catalogue, repo = _diverged_fixture(tmp_path)
    entry_before = _entry_fields(repo, _DIVERGED_NAME)
    tree_before = _digest_tree(_skills_root(repo))
    manifest_before = _manifest_bytes(repo)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    assert _digest_tree(_skills_root(repo)) == tree_before
    assert _manifest_bytes(repo) == manifest_before
    assert _entry_fields(repo, _DIVERGED_NAME) == entry_before
    assert _DIVERGED_NAME in report.declined
    assert _DIVERGED_NAME not in report.refreshed


def test_accepting_a_diverged_pattern_replaces_the_whole_subtree(tmp_path: Path) -> None:
    """The accept path replaces the FULL SUBTREE, `reference/` included.

    The limit on *detection* (the hash covers `SKILL.md` only, decision 6)
    is not a limit on *replacement*: an implementation that rewrites only
    `SKILL.md` on a hash difference passes every other test in this plan
    while leaving stale `reference/` content in place after the user
    accepted the diff. The local scribble below is what makes this
    assertion non-vacuous -- an uncopied `reference/` file whose bytes were
    never touched would match the catalogue's by accident
    `[ref: phase-3.md#T3.4]`. Mirror of
    `test_chosen_pattern_lands_with_tcs_prefix_and_full_subtree`.
    """
    install = _load_install()
    catalogue, repo = _diverged_fixture(tmp_path, extra_files={"reference/guide.md": "# Upstream guide\n"})
    dest = _skills_root(repo) / f"tcs-{_DIVERGED_NAME}"
    local_ref = dest / "reference" / "guide.md"
    local_ref.write_bytes(b"# Local scribble, nothing upstream has.\n")
    version_before = _entry_fields(repo, _DIVERGED_NAME)[0]

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=lambda name, diff: True)

    assert (dest / "SKILL.md").read_bytes() == _DIVERGED_CATALOGUE_AS_INSTALLED.encode("utf-8")
    assert local_ref.read_bytes() == (catalogue / _DIVERGED_NAME / "reference" / "guide.md").read_bytes()
    installed_as, got_before, got_after, sha256 = report.refreshed[_DIVERGED_NAME]
    assert installed_as == f"tcs-{_DIVERGED_NAME}"
    assert got_before == version_before
    assert got_after == (catalogue / _DIVERGED_NAME / "VERSION").read_text(encoding="utf-8").strip()
    assert sha256 == hashlib.sha256((dest / "SKILL.md").read_bytes()).hexdigest()
    assert _entry_fields(repo, _DIVERGED_NAME) == (got_after, installed_as, sha256)
    assert _DIVERGED_NAME not in report.declined
    assert report.committed is False


# --- the first row: nothing to do -------------------------------------------


def test_up_to_date_pattern_reports_current_and_asks_nothing(tmp_path: Path) -> None:
    """Version equal and hash equal: nothing is done, nothing is asked, and
    nothing on disk moves `[ref: solution.md, decision 2, first row]`."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="3")
    repo = tmp_path / "repo"
    assert "ddd" in install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed

    tree_before = _digest_tree(_skills_root(repo))
    manifest_before = _manifest_bytes(repo)
    calls: list[tuple[str, str]] = []

    def decide(name: str, diff: str) -> bool:
        calls.append((name, diff))
        return True

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert calls == []
    assert _digest_tree(_skills_root(repo)) == tree_before
    assert _manifest_bytes(repo) == manifest_before
    installed_as, version, sha256 = report.current["ddd"]
    assert (installed_as, version) == ("tcs-ddd", "3")
    assert sha256 == hashlib.sha256((_skills_root(repo) / "tcs-ddd" / "SKILL.md").read_bytes()).hexdigest()
    for channel in (report.refreshed, report.declined, report.failed):
        assert "ddd" not in channel


# --- the two `failed` rows, which are exact inverses of each other ----------


def test_manifest_entry_whose_directory_is_missing_is_failed_not_refreshed(tmp_path: Path) -> None:
    """Installed side ABSENT, catalogue side PRESENT `[ref: solution.md,
    decision 8]`. The record claims a pattern is installed and it is not,
    which is a different problem from being out of date -- reporting it
    tells the user which verb to reach for instead of papering over a
    manifest that lies. The exact inverse of the catalogue-removal fixture
    below; never both absent, or the two collapse into one case."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "functional", version="1")
    repo = tmp_path / "repo"
    assert "functional" in install.install(repo, ["functional"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed
    shutil.rmtree(_skills_root(repo) / "tcs-functional")
    manifest_before = _manifest_bytes(repo)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    # The reason must name THIS cause, not the catalogue-side one -- the two
    # rows are only distinguishable to a user by what they are told, and a
    # mutation dropping this check falls through to the SKILL.md read and
    # reports "no readable SKILL.md", which is a different diagnosis.
    assert "missing" in report.failed["functional"]
    assert "catalogue" not in report.failed["functional"]
    # Branch 1 of 2: with NO stash beside it, `install` is the right verb to
    # name, and the message says so. The stash branch below asserts the
    # inverse, because one fixture cannot distinguish them
    # `[ref: solution.md, decision 8, "Unless a .replaced stash"]`.
    assert "run install" in report.failed["functional"]
    for channel in (report.refreshed, report.declined, report.current):
        assert "functional" not in channel
    # Not resurrected: `update()` refreshes, it does not install.
    assert not (_skills_root(repo) / "tcs-functional").exists()
    assert _manifest_bytes(repo) == manifest_before


def test_missing_directory_beside_an_interrupted_refresh_stash_names_the_stash(tmp_path: Path) -> None:
    """Branch 2 of 2. When `dest` is absent AND
    `.<installed_as>.replaced` exists, the reason names the stash and must
    **not** tell the user to run install
    `[ref: solution.md, "Data model: the update path (C5's second verb)",
    decision 8, "Unless a .replaced stash"]`.

    `_replace_subtree` moves the current directory aside to that stash and
    deletes it only once the new one has landed, restoring it on any
    exception -- so the stash survives only a **hard kill** between the two
    renames. In that state the user's own copy, edits included, is the
    ONLY copy, and it sits in a dotted directory nothing names. Measured
    before this clause existed: `update()` said "run install to write it",
    said nothing about the stash, and left it in place -- and following that
    advice writes a fresh copy and orphans the user's work for good.

    `update()` still does not move it back: restoring a file the user has
    not asked about is what ADR-4 forbids this verb from doing, and the
    whole point of the stash mechanism is that nothing overwrites local
    work silently. Naming it turns a silent trap into a decision.

    The stash state is built by renaming `dest` aside rather than by
    simulating a kill -- the state is what matters, and a real SIGKILL
    between two renames is not something a test can place reliably.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "functional", version="1")
    repo = tmp_path / "repo"
    assert "functional" in install.install(repo, ["functional"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed

    dest = _skills_root(repo) / "tcs-functional"
    edited = dest / "SKILL.md"
    edited.write_bytes(edited.read_bytes() + b"\nThe user's own paragraph.\n")
    user_bytes = edited.read_bytes()
    stash = _skills_root(repo) / ".tcs-functional.replaced"
    dest.rename(stash)  # what a hard kill between the two renames leaves behind
    manifest_before = _manifest_bytes(repo)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    reason = report.failed["functional"]
    assert str(stash) in reason, reason
    assert "run install" not in reason, reason
    for channel in (report.refreshed, report.declined, report.current):
        assert "functional" not in channel
    # Not moved back, not deleted, and the user's edit still in it.
    assert (stash / "SKILL.md").read_bytes() == user_bytes
    assert not dest.exists()
    assert _manifest_bytes(repo) == manifest_before


def test_pattern_the_catalogue_no_longer_carries_is_failed_and_untouched(tmp_path: Path) -> None:
    """Installed side PRESENT with real content, catalogue side ABSENT
    `[ref: solution.md, decision 7]`. Both comparisons that define the three
    states presuppose the catalogue still has the pattern, so an upstream
    removal has no row -- it is `failed`, with nothing under `tcs-<name>/`
    touched: refreshing from a source that no longer exists is impossible,
    and deleting would destroy a working skill the user still has.

    The installed directory must EXIST with real content, or this collapses
    into the missing-directory case above and the digest assertion is
    vacuous `[ref: phase-3.md#T3.4]`."""
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "dropped", version="1", extra_files={"reference/guide.md": "# Upstream guide\n"})
    repo = tmp_path / "repo"
    assert "dropped" in install.install(repo, ["dropped"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed
    dest = _skills_root(repo) / "tcs-dropped"
    assert (dest / "reference" / "guide.md").read_bytes() == b"# Upstream guide\n"

    shutil.rmtree(catalogue / "dropped")  # upstream drops the pattern
    tree_before = _digest_tree(_skills_root(repo))
    manifest_before = _manifest_bytes(repo)
    calls: list[tuple[str, str]] = []

    def decide(name: str, diff: str) -> bool:
        calls.append((name, diff))
        return True

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert calls == []
    # Decision 7 pins the reason to name the absent catalogue entry. Without
    # it, a mutation checking the installed side FIRST reports the other
    # row's diagnosis and no channel assertion can tell the difference.
    assert "catalogue" in report.failed["dropped"]
    # The baseline half of the suppression pair below: with no stash and the
    # directory present, this clause is TRUE and must still be here.
    # Without this assertion nothing distinguishes "suppressed correctly in
    # the stash state" from "deleted everywhere"
    # `[ref: solution.md, decision 7, "And when a .replaced stash is ALSO
    # present"]`.
    assert "left exactly as it is" in report.failed["dropped"]
    for channel in (report.refreshed, report.declined, report.current):
        assert "dropped" not in channel
    assert _digest_tree(_skills_root(repo)) == tree_before
    assert _manifest_bytes(repo) == manifest_before
    assert (dest / "reference" / "guide.md").read_bytes() == b"# Upstream guide\n"


def test_both_sides_absent_reports_the_catalogue_reason_not_the_directory_one(tmp_path: Path) -> None:
    """A THIRD fixture, distinct from the inverse pair above: installed side
    absent AND catalogue side absent, with the manifest still recording the
    pattern. Reachable without anything exotic -- a user deletes
    `tcs-<name>/` by hand and a plugin update drops the pattern upstream.

    This is the one state where the ORDER of `_update_one`'s two early
    guards is observable, and the inverse pair never constructs it: each of
    those breaks exactly one side, so an installed-first implementation
    still reports the catalogue cause for the catalogue fixture. Measured --
    reordering the guards survives all 33 tests without this one.

    Both messages are true; only one is actionable. Catalogue-first says the
    pattern is gone upstream, so the manifest entry should be dropped.
    Installed-first says "run install to write it", which **cannot succeed**
    -- `install()` would fail on the same absent catalogue entry. So the
    catalogue check runs first, and that is a requirement rather than an
    accident `[ref: solution.md, "Data model: the update path (C5's second
    verb)", decision 7, "When both sides are absent"]`.

    Asserted on the reason's CONTENT. Both orderings put the name in
    `failed`, which is exactly why every channel assertion in this file
    passes under the reorder.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="1")
    repo = tmp_path / "repo"
    assert "ddd" in install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed
    shutil.rmtree(_skills_root(repo) / "tcs-ddd")  # the user deletes it by hand
    shutil.rmtree(catalogue / "ddd")  # and upstream drops the pattern
    manifest_before = _manifest_bytes(repo)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    reason = report.failed["ddd"]
    assert "catalogue" in reason, reason
    # The non-actionable advice decision 7's table rules out, named
    # literally: a reorder produces "run install to write it" here.
    assert "run install" not in reason, reason
    for channel in (report.refreshed, report.declined, report.current):
        assert "ddd" not in channel
    assert not (_skills_root(repo) / "tcs-ddd").exists()
    assert _manifest_bytes(repo) == manifest_before


def test_catalogue_absent_with_a_stash_names_it_and_drops_the_untouched_claim(tmp_path: Path) -> None:
    """The intersection of decisions 7 and 8, and the most severe of the
    three stash states. THREE independent failures co-occur: upstream
    dropped the pattern, a prior refresh was hard-killed, and the manifest
    still records it.

    Measured before this clause existed, the reason read "the catalogue no
    longer carries pattern 'ddd'; 'tcs-ddd' was left exactly as it is" --
    and **both halves are wrong**. `tcs-ddd` was not left as it is, it does
    not exist; and the stash goes unmentioned while holding the **only copy
    of the content anywhere** -- the user's edits AND the pattern itself,
    which the catalogue no longer has, so unlike decision 8's case
    `install` has no source to recreate it from.

    The precedence does not change and no guard is reordered: the catalogue
    cause stays the headline, because "the pattern is gone upstream, drop
    the manifest entry" remains the actionable fact. What changes is that
    the stash is named and the untouched claim is suppressed, because in
    this state it is false `[ref: solution.md, "Data model: the update path
    (C5's second verb)", decision 7, "And when a .replaced stash is ALSO
    present"]`.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="1")
    repo = tmp_path / "repo"
    assert "ddd" in install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed

    dest = _skills_root(repo) / "tcs-ddd"
    edited = dest / "SKILL.md"
    edited.write_bytes(edited.read_bytes() + b"\nThe user's own paragraph.\n")
    user_bytes = edited.read_bytes()
    stash = _skills_root(repo) / ".tcs-ddd.replaced"
    dest.rename(stash)  # a refresh hard-killed between its two renames
    shutil.rmtree(catalogue / "ddd")  # and upstream dropped the pattern
    manifest_before = _manifest_bytes(repo)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    reason = report.failed["ddd"]
    assert "catalogue" in reason, reason
    assert str(stash) in reason, reason
    # The third assertion, and the one a careless fix misses: the claim is
    # false here, so it must be gone.
    assert "left exactly as it is" not in reason, reason
    for channel in (report.refreshed, report.declined, report.current):
        assert "ddd" not in channel
    # Still the only copy, still untouched, still not moved back.
    assert (stash / "SKILL.md").read_bytes() == user_bytes
    assert not dest.exists()
    assert _manifest_bytes(repo) == manifest_before


def test_catalogue_absent_with_the_directory_PRESENT_keeps_the_untouched_claim(tmp_path: Path) -> None:
    """The fourth state, which pins the CONDITION rather than the message:
    catalogue absent, a stash present, but the installed directory still
    there. Not required by the task text -- added because gating the new
    clause on the directory being absent is the one judgment call in this
    change, and without this fixture a mutation dropping that gate survives.

    Here "left exactly as it is" is **true** -- `dest` exists and nothing
    touched it -- so suppressing it would make the message worse, and
    naming the stash would raise an alarm about debris that costs the user
    nothing: `dest` holds a working pattern `[ref: solution.md, decision 8,
    "Only the directory-ABSENT state needs this, because the other stash
    state heals itself"]`. The asymmetry is deliberate.
    """
    install = _load_install()
    catalogue = tmp_path / "catalogue"
    _catalogue_pattern(catalogue, "ddd", version="1")
    repo = tmp_path / "repo"
    assert "ddd" in install.install(repo, ["ddd"], catalogue_dir=catalogue, bundle=TEST_BUNDLE).installed

    dest = _skills_root(repo) / "tcs-ddd"
    stash = _skills_root(repo) / ".tcs-ddd.replaced"
    shutil.copytree(dest, stash)  # killed AFTER the new directory landed
    shutil.rmtree(catalogue / "ddd")
    tree_before = _digest_tree(_skills_root(repo))

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    reason = report.failed["ddd"]
    assert "catalogue" in reason, reason
    assert "left exactly as it is" in reason, reason
    assert str(stash) not in reason, reason
    assert _digest_tree(_skills_root(repo)) == tree_before


def test_a_refresh_dying_mid_copy_puts_the_users_directory_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_replace_subtree`'s restore-on-failure path, which nothing in this
    file reached before.

    Measured by the code-quality gate: **removing the restore entirely, or
    inverting its guard so it never fires, left all 37 tests green.** The
    path was correct, so a reader found nothing wrong -- what was missing
    was the tripwire. It is the path that puts the user's own directory back
    when a refresh dies mid-copy, which is the same work the stash clauses
    in decisions 7 and 8 exist to protect, so leaving it unheld is the
    defect class this spec documents: a promise held by nothing. If
    `_fresh_install`'s failure contract ever changes, the restore stops
    working and a green suite says nothing.

    Mirror of `test_directory_lands_even_when_the_manifest_upsert_fails`,
    which does the equivalent for `install()` -- and is exactly why that
    path had a tripwire and this one did not.

    `_fresh_install` raises `InstallError` specifically, not any exception:
    `_replace_subtree` restores and re-raises whatever it gets, but only
    `InstallError` is caught per pattern by `update()`, so anything else
    would escape rather than land in `failed`. That is also the real shape
    of this failure -- an unreadable catalogue pattern or a frontmatter the
    rewriter refuses.

    The third assertion is the point: a half-finished restore that copies
    the directory back and leaves the stash behind satisfies the first two
    and leaves the user with two copies and no way to tell which is live.
    """
    install = _load_install()
    catalogue, repo = _diverged_fixture(tmp_path, extra_files={"reference/guide.md": "# Upstream guide\n"})
    dest = _skills_root(repo) / f"tcs-{_DIVERGED_NAME}"
    stash = _skills_root(repo) / f".tcs-{_DIVERGED_NAME}.replaced"

    # The user's own state, captured before the attempt. The subtree digest
    # (not just SKILL.md) is what catches a restore that puts part of the
    # directory back.
    user_bytes = (dest / "SKILL.md").read_bytes()
    tree_before = _digest_tree(_skills_root(repo))
    manifest_before = _manifest_bytes(repo)

    def _dying_fresh_install(name, *, installed_as, dest, skills_root, catalogue_dir):
        raise install.InstallError("simulated mid-copy failure")

    monkeypatch.setattr(install, "_fresh_install", _dying_fresh_install)

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=lambda n, d: True)

    assert _DIVERGED_NAME in report.failed
    for channel in (report.refreshed, report.declined, report.current):
        assert _DIVERGED_NAME not in channel
    # 2: the directory is back, with the user's bytes untouched.
    assert dest.is_dir()
    assert (dest / "SKILL.md").read_bytes() == user_bytes
    # 3: MOVED back, not copied -- the stash is gone, so there is exactly
    # one copy and no ambiguity about which is live.
    assert not stash.exists()
    # and nothing else moved either, including `reference/`.
    assert _digest_tree(_skills_root(repo)) == tree_before
    assert _manifest_bytes(repo) == manifest_before
