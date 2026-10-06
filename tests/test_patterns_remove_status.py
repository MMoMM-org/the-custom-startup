"""T5.1a (spec-020): `install.remove()` and the read-only `status.status()`.

Contracts `[ref: SDD/Interface Specifications/Process contract: the CLI the
skill drives (C3's seam), "remove" and "status"]`.

**The verdict table is hand-typed.** `status()` and `patterns_drift.py` now
share `status.drift_verdict`, so asserting one against the other would agree
with itself whatever the rule said. Each row's expected state and reporter
line are typed here, from the contract's prose, and asserted against BOTH
implementations -- a wrong shared rule fails both.

Library modules are imported inside each test, never at module level, so a
missing module fails only the tests that need it (the loader convention of
`test_patterns_installer.py`).
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugins" / "tcs-patterns"
LIB_DIR = PLUGIN_DIR / "skills" / "patterns-setup" / "lib"
REPORTER = PLUGIN_DIR / "scripts" / "patterns_drift.py"

BUNDLE = "1.0.0"

_ROOT_IGNORES_PERMISSIONS = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores file permissions, so a mode-000 fixture cannot fail to read",
)


def _load_lib(name: str) -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module(name)


def _catalogue_pattern(root: Path, name: str, version: str = "1") -> None:
    d = root / name
    (d / "reference").mkdir(parents=True, exist_ok=True)
    (d / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: fixture\n---\n\nBody for {name}.\n", encoding="utf-8"
    )
    (d / "reference" / "notes.md").write_text(f"Reference for {name}.\n", encoding="utf-8")


def _setup(tmp_path: Path, names: list[str], version: str = "1") -> tuple[Path, Path]:
    """A catalogue holding `names` at `version`, and a repo that installed them."""
    cat = tmp_path / "catalogue"
    for n in names:
        _catalogue_pattern(cat, n, version)
    repo = tmp_path / "repo"
    repo.mkdir()
    report = _load_lib("install").install(repo, list(names), catalogue_dir=cat, bundle=BUNDLE)
    assert not report.failed, report.failed
    return repo, cat


def _skills(repo: Path) -> Path:
    return repo / ".claude" / "skills"


def _manifest_bytes(repo: Path) -> bytes:
    return _load_lib("manifest")._manifest_path(repo).read_bytes()


def _digest(root: Path) -> str:
    """Every entry under `root`: its relative path, its kind, and its bytes
    or link target. Symlinks are recorded, never followed."""
    h = hashlib.sha256()
    if not root.exists():
        return "absent"
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted([*dirnames, *filenames]):
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                h.update(f"L {rel} -> {os.readlink(p)}\n".encode())
            elif p.is_dir():
                h.update(f"D {rel}\n".encode())
            else:
                h.update(f"F {rel}\n".encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def _reporter_stdout(repo: Path, cat: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(REPORTER), str(repo), "--catalogue", str(cat)],
        capture_output=True,
        text=True,
        cwd=repo.parent,
    )
    assert r.returncode == 0
    return r.stdout


# =============================================================================
# status(): the verdict table, against status() AND the reporter
# =============================================================================

_ABSENT = object()  # the catalogue pattern has no VERSION file
_DELETED = object()  # the catalogue pattern directory is gone

# (row id, installed version, catalogue VERSION state,
#  expected state, expected catalogue_version, expected reporter stdout line)
# Typed by hand from the drift reporter's contract: behind is DRIFT, ahead is
# UNKNOWN, versions compare as integers, and an absent, non-numeric or empty
# VERSION -- or a deleted pattern -- is UNKNOWN. Never computed.
VERDICT_TABLE = [
    ("behind", "1", "2", "DRIFT", "2", "DRIFT:ddd:1:2"),
    ("behind-across-a-digit", "9", "10", "DRIFT", "10", "DRIFT:ddd:9:10"),
    ("equal", "1", "1", "OK", "1", "OK"),
    ("ahead", "3", "2", "UNKNOWN", "2", "UNKNOWN:ddd:3"),
    ("ahead-across-a-digit", "10", "9", "UNKNOWN", "9", "UNKNOWN:ddd:10"),
    ("leading-zero-is-equal", "1", "01", "OK", "01", "OK"),
    ("version-absent", "1", _ABSENT, "UNKNOWN", None, "UNKNOWN:ddd:1"),
    ("non-numeric", "1", "v2-beta", "UNKNOWN", None, "UNKNOWN:ddd:1"),
    ("empty", "1", "", "UNKNOWN", None, "UNKNOWN:ddd:1"),
    ("pattern-directory-deleted", "1", _DELETED, "UNKNOWN", None, "UNKNOWN:ddd:1"),
]


@pytest.mark.parametrize(
    "installed, catalogue, state, catalogue_version, line",
    [row[1:] for row in VERDICT_TABLE],
    ids=[row[0] for row in VERDICT_TABLE],
)
def test_status_and_the_reporter_both_match_the_hand_typed_verdict(
    tmp_path, installed, catalogue, state, catalogue_version, line
):
    repo, cat = _setup(tmp_path, ["ddd"], version=installed)
    if catalogue is _DELETED:
        shutil.rmtree(cat / "ddd")
    elif catalogue is _ABSENT:
        (cat / "ddd" / "VERSION").unlink()
    else:
        (cat / "ddd" / "VERSION").write_text(f"{catalogue}\n", encoding="utf-8")

    entry = _load_lib("status").status(repo, catalogue_dir=cat).patterns["ddd"]
    # One comparison, so a failure shows the status() side AND the reporter side.
    assert {
        "status.state": entry.state,
        "status.catalogue_version": entry.catalogue_version,
        "status.installed_version": entry.installed_version,
        "reporter stdout": _reporter_stdout(repo, cat),
    } == {
        "status.state": state,
        "status.catalogue_version": catalogue_version,
        "status.installed_version": installed,
        "reporter stdout": line + "\n",
    }


# =============================================================================
# status(): the manifest's four states
# =============================================================================


def test_status_reports_a_present_manifest_and_each_pattern_field(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert report.manifest_state == "present"
    assert report.manifest_error is None
    assert report.bundle == BUNDLE
    assert sorted(report.patterns) == ["ddd", "hexagonal"]
    ddd = report.patterns["ddd"]
    assert ddd.installed_as == "tcs-ddd"
    assert ddd.directory_present is True
    assert ddd.diverged is False
    assert report.unlisted == ()
    assert report.debris == ()


def test_status_absent_manifest_lists_every_tcs_directory_as_unlisted(tmp_path):
    repo = tmp_path / "repo"
    (_skills(repo) / "tcs-mine").mkdir(parents=True)
    (_skills(repo) / "other").mkdir()
    report = _load_lib("status").status(repo, catalogue_dir=tmp_path / "catalogue")
    assert report.manifest_state == "absent"
    assert report.manifest_error is None
    assert report.bundle is None
    assert report.patterns == {}
    assert report.unlisted == ("tcs-mine",)


def test_status_reports_an_unparseable_manifest_verbatim(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    manifest = _load_lib("manifest")
    manifest._manifest_path(repo).write_text("this is = = not toml [", encoding="utf-8")
    with pytest.raises(manifest.ManifestUnparseableError) as raised:
        manifest.read(repo)

    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert report.manifest_state == "unparseable"
    assert report.manifest_error == str(raised.value)
    assert report.bundle is None
    assert report.patterns == {}
    assert report.unlisted == ("tcs-ddd",)


@_ROOT_IGNORES_PERMISSIONS
def test_status_reports_an_unreadable_manifest_verbatim(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    path = _load_lib("manifest")._manifest_path(repo)
    path.chmod(0)
    try:
        with pytest.raises(OSError) as raised:
            path.read_text(encoding="utf-8")
        report = _load_lib("status").status(repo, catalogue_dir=cat)
    finally:
        path.chmod(0o644)
    assert report.manifest_state == "unreadable"
    assert report.manifest_error == str(raised.value)
    assert report.patterns == {}
    assert report.unlisted == ("tcs-ddd",)


def test_status_names_a_tcs_directory_the_manifest_does_not(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    (_skills(repo) / "tcs-handmade").mkdir()
    (_skills(repo) / "tcs-handmade" / "SKILL.md").write_text("mine\n", encoding="utf-8")
    (_skills(repo) / "tcs-a-file").write_text("not a directory\n", encoding="utf-8")
    (_skills(repo) / "someone-else").mkdir()
    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert report.unlisted == ("tcs-handmade",)


def test_status_diverged_is_true_false_or_none(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "functional", "hexagonal"])
    (_skills(repo) / "tcs-ddd" / "SKILL.md").write_text("edited\n", encoding="utf-8")
    (_skills(repo) / "tcs-hexagonal" / "SKILL.md").unlink()
    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert report.patterns["ddd"].diverged is True
    assert report.patterns["functional"].diverged is False
    assert report.patterns["hexagonal"].diverged is None
    assert report.patterns["hexagonal"].directory_present is True


def test_status_directory_absent_is_reported_with_diverged_none(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    shutil.rmtree(_skills(repo) / "tcs-ddd")
    status = _load_lib("status").status(repo, catalogue_dir=cat).patterns["ddd"]
    assert status.directory_present is False
    assert status.diverged is None


# =============================================================================
# status(): debris, classified, with the resolution the skill renders
# =============================================================================


def _debris(report) -> dict[str, tuple[str, str]]:
    return {d.name: (d.kind, d.resolution) for d in report.debris}


def test_status_classifies_every_debris_kind_with_its_resolution(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    skills = _skills(repo)
    (skills / ".tcs-ddd.tmp").mkdir()
    (skills / ".tcs-ddd.removing").mkdir()
    (skills / ".tcs-ddd.replaced").mkdir()  # tcs-ddd/ present
    (skills / ".tcs-hexagonal.replaced").mkdir()  # tcs-hexagonal/ absent
    (skills / "..tcs-patterns-manifest.x7f2q.tmp").write_text("partial", encoding="utf-8")
    (skills / ".tcs-ddd.bak").mkdir()
    (skills / ".unrelated").mkdir()

    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert _debris(report) == {
        ".tcs-ddd.tmp": ("install-tmp", "safe to delete; the next `install` of ddd deletes it itself"),
        ".tcs-ddd.removing": ("removing", "safe to delete"),
        ".tcs-ddd.replaced": (
            "replaced",
            "safe to delete; a refresh or a successful `remove ddd` also deletes it",
        ),
        ".tcs-hexagonal.replaced": (
            "replaced",
            "this is your copy of hexagonal; move it back to tcs-hexagonal/",
        ),
        "..tcs-patterns-manifest.x7f2q.tmp": (
            "manifest-tmp",
            "safe to delete; a manifest write was interrupted before its rename, "
            "and the manifest itself is intact",
        ),
        ".tcs-ddd.bak": ("unknown", "not a name this tool writes; left alone"),
    }
    assert ".tcs-patterns-manifest" not in _debris(report)
    assert [d.name for d in report.debris] == sorted(_debris(report))


def test_status_tells_a_listed_pattern_with_its_directory_absent_to_finish_the_remove(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    os.rename(_skills(repo) / "tcs-ddd", _skills(repo) / ".tcs-ddd.removing")
    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert _debris(report) == {".tcs-ddd.removing": ("removing", "run `remove ddd` to finish")}
    assert report.patterns["ddd"].directory_present is False


def test_status_calls_an_unlisted_removing_entry_safe_to_delete(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    (_skills(repo) / ".tcs-hexagonal.removing").mkdir()
    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert _debris(report) == {".tcs-hexagonal.removing": ("removing", "safe to delete")}


# =============================================================================
# status() writes nothing
# =============================================================================


def test_status_writes_nothing(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    skills = _skills(repo)
    (skills / "tcs-ddd" / "SKILL.md").write_text("edited\n", encoding="utf-8")
    shutil.rmtree(skills / "tcs-hexagonal")
    (skills / ".tcs-hexagonal.removing").mkdir()
    (skills / ".tcs-ddd.replaced").mkdir()
    (skills / "tcs-unlisted").mkdir()
    (skills / "..tcs-patterns-manifest.abc.tmp").write_text("x", encoding="utf-8")
    before_repo, before_cat = _digest(repo), _digest(cat)

    _load_lib("status").status(repo, catalogue_dir=cat)

    assert _digest(repo) == before_repo
    assert _digest(cat) == before_cat


_STATUS_SIBLINGS_ALLOWED = {"manifest", "paths"}
_MANIFEST_ATTRS_ALLOWED = {
    "read",
    "_manifest_path",
    "ManifestUnparseableError",
    "MANIFEST_FILENAME",
    "Manifest",
    "PatternEntry",
}


def _allowlist_violations(source: str, siblings: set[str]) -> list[str]:
    """Every way `source` steps outside status.py's allowlist: a sibling import
    other than `manifest`/`paths`, any alias or `from` form of a sibling, any
    relative import, and any `manifest.<attr>` (or bare `manifest` use) not on
    the read-only list. Fails on anything not allowed, rather than looking
    for named writers."""
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in siblings:
                    continue
                if top not in _STATUS_SIBLINGS_ALLOWED or alias.name != top:
                    violations.append(f"import {alias.name}")
                if alias.asname is not None:
                    violations.append(f"import {alias.name} as {alias.asname}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                violations.append(f"relative import from {'.' * node.level}{node.module or ''}")
            elif (node.module or "").split(".")[0] in siblings:
                violations.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Name) and node.id == "manifest":
            parent = parents.get(node)
            if not (isinstance(parent, ast.Attribute) and parent.value is node):
                violations.append(f"bare use of `manifest` at line {node.lineno}")
            elif parent.attr not in _MANIFEST_ATTRS_ALLOWED:
                violations.append(f"manifest.{parent.attr} at line {node.lineno}")
    return violations


def test_status_module_imports_and_uses_only_the_read_only_allowlist():
    siblings = {p.stem for p in LIB_DIR.glob("*.py")} - {"status"}
    assert {"manifest", "paths", "install"} <= siblings  # the check knows the real siblings
    source = (LIB_DIR / "status.py").read_text(encoding="utf-8")
    assert _allowlist_violations(source, siblings) == []
    # And the check can fail: each of these is a violation it must report.
    for bad in (
        "import install\n",
        "import manifest as m\n",
        "from manifest import read\n",
        "from . import manifest\n",
        "import manifest\nmanifest.write(None, None)\n",
        "import manifest\nwriter = manifest\n",
    ):
        assert _allowlist_violations(bad, siblings), bad


# =============================================================================
# remove(): the six rules, one test per rule
# =============================================================================


def _remove(repo: Path, names, force=frozenset()):
    return _load_lib("install").remove(repo, names, bundle=BUNDLE, force=frozenset(force))


def _assert_refused_and_untouched(repo: Path, report, name: str, before_skills: str, before_manifest: bytes):
    assert name in report.refused, report
    assert name not in report.removed
    assert name not in report.failed
    assert _digest(_skills(repo)) == before_skills
    assert _manifest_bytes(repo) == before_manifest


def test_remove_rule1_never_deletes_a_tcs_directory_the_manifest_does_not_list(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd"])
    mine = _skills(repo) / "tcs-foo"
    (mine / "reference").mkdir(parents=True)
    (mine / "SKILL.md").write_text("---\nname: tcs-foo\n---\nmine\n", encoding="utf-8")
    (mine / "reference" / "x.md").write_text("x\n", encoding="utf-8")
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    report = _remove(repo, ["foo"])

    _assert_refused_and_untouched(repo, report, "foo", before_skills, before_manifest)
    assert "not recorded in the manifest" in report.refused["foo"]
    assert report.committed is False


def test_remove_rule2_refuses_an_entry_whose_installed_as_names_another_pattern(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd", "hexagonal"])
    manifest = _load_lib("manifest")
    m = manifest.read(repo)
    hexagonal = m.patterns["hexagonal"]
    pointed = manifest.PatternEntry(version="1", installed_as="tcs-hexagonal", sha256=hexagonal.sha256)
    manifest.write(m.with_pattern("ddd", pointed, bundle=BUNDLE), repo)
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    report = _remove(repo, ["ddd"])

    _assert_refused_and_untouched(repo, report, "ddd", before_skills, before_manifest)
    assert "tcs-hexagonal" in report.refused["ddd"]


def test_remove_rule3_refuses_when_a_stash_is_the_only_copy_and_names_it(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd"])
    stash = _skills(repo) / ".tcs-ddd.replaced"
    os.rename(_skills(repo) / "tcs-ddd", stash)
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    report = _remove(repo, ["ddd"])

    _assert_refused_and_untouched(repo, report, "ddd", before_skills, before_manifest)
    assert str(stash) in report.refused["ddd"]


def test_remove_deletes_a_stash_beside_a_present_directory_with_it(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd"])
    stash = _skills(repo) / ".tcs-ddd.replaced"
    shutil.copytree(_skills(repo) / "tcs-ddd", stash)

    report = _remove(repo, ["ddd"])

    assert report.removed == {"ddd": ("tcs-ddd", "1", True)}
    assert not stash.exists()
    assert not (_skills(repo) / "tcs-ddd").exists()


def test_remove_step1_clears_a_stale_removing_beside_a_present_directory(tmp_path):
    """Step 1 deletes this verb's own debris from an earlier run first; without
    it, the move-aside would rename onto an existing directory and fail."""
    repo, cat = _setup(tmp_path, ["ddd"])
    stale = _skills(repo) / ".tcs-ddd.removing"
    (stale / "reference").mkdir(parents=True)
    (stale / "reference" / "old.md").write_text("old\n", encoding="utf-8")

    report = _remove(repo, ["ddd"])

    assert report.removed == {"ddd": ("tcs-ddd", "1", True)}
    assert not stale.exists()
    assert _load_lib("status").status(repo, catalogue_dir=cat).debris == ()


@pytest.mark.parametrize("shape", ["symlink", "file"])
def test_remove_rule4_refuses_a_symlink_or_a_file_where_the_directory_should_be(tmp_path, shape):
    repo, _cat = _setup(tmp_path, ["ddd"])
    dest = _skills(repo) / "tcs-ddd"
    elsewhere = tmp_path / "elsewhere"
    shutil.move(str(dest), str(elsewhere))
    if shape == "symlink":
        dest.symlink_to(elsewhere, target_is_directory=True)
    else:
        dest.write_text("not a directory\n", encoding="utf-8")
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)
    before_elsewhere = _digest(elsewhere)

    report = _remove(repo, ["ddd"])

    _assert_refused_and_untouched(repo, report, "ddd", before_skills, before_manifest)
    assert _digest(elsewhere) == before_elsewhere


def test_remove_rule5_refuses_an_edited_skill_md_without_force_and_removes_it_with(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd"])
    (_skills(repo) / "tcs-ddd" / "SKILL.md").write_text("my edits\n", encoding="utf-8")
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    refused = _remove(repo, ["ddd"])
    _assert_refused_and_untouched(repo, refused, "ddd", before_skills, before_manifest)
    assert "--force ddd" in refused.refused["ddd"]

    forced = _remove(repo, ["ddd"], force={"ddd"})
    assert forced.removed == {"ddd": ("tcs-ddd", "1", True)}
    assert not (_skills(repo) / "tcs-ddd").exists()
    assert _load_lib("manifest").read(repo).patterns == {}


def test_remove_rule5_counts_an_absent_skill_md_as_diverged(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd"])
    (_skills(repo) / "tcs-ddd" / "SKILL.md").unlink()
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)
    _assert_refused_and_untouched(repo, _remove(repo, ["ddd"]), "ddd", before_skills, before_manifest)


def test_remove_rule5_hashes_only_skill_md_so_a_reference_edit_is_removed_unasked(tmp_path):
    """ADR-4's stated limit, pinned so nobody "fixes" it by accident."""
    repo, _cat = _setup(tmp_path, ["ddd"])
    (_skills(repo) / "tcs-ddd" / "reference" / "notes.md").write_text("my edits\n", encoding="utf-8")
    report = _remove(repo, ["ddd"])
    assert report.removed == {"ddd": ("tcs-ddd", "1", True)}
    assert not (_skills(repo) / "tcs-ddd").exists()


def test_remove_rule6_removes_directory_and_entry_and_leaves_no_debris(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    report = _remove(repo, ["ddd"])
    assert report.removed == {"ddd": ("tcs-ddd", "1", True)}
    assert report.refused == {} and report.failed == {}
    assert report.committed is False
    assert not (_skills(repo) / "tcs-ddd").exists()
    assert sorted(_load_lib("manifest").read(repo).patterns) == ["hexagonal"]
    status = _load_lib("status").status(repo, catalogue_dir=cat)
    assert status.debris == ()
    assert status.unlisted == ()


def test_remove_forces_only_the_pattern_named_in_force(tmp_path):
    """Kills a blanket-flag `force`: two diverged, one named."""
    repo, _cat = _setup(tmp_path, ["ddd", "hexagonal"])
    for name in ("ddd", "hexagonal"):
        (_skills(repo) / f"tcs-{name}" / "SKILL.md").write_text("edited\n", encoding="utf-8")
    hexagonal_before = _digest(_skills(repo) / "tcs-hexagonal")

    report = _remove(repo, ["ddd", "hexagonal"], force={"ddd"})

    assert sorted(report.removed) == ["ddd"]
    assert sorted(report.refused) == ["hexagonal"]
    assert _digest(_skills(repo) / "tcs-hexagonal") == hexagonal_before
    assert sorted(_load_lib("manifest").read(repo).patterns) == ["hexagonal"]


def test_remove_leaves_another_patterns_manifest_block_byte_identical(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd", "hexagonal"])
    block = _load_lib("manifest")._serialize_pattern(
        "hexagonal", _load_lib("manifest").read(repo).patterns["hexagonal"]
    ).encode()
    assert block in _manifest_bytes(repo)
    _remove(repo, ["ddd"])
    assert block in _manifest_bytes(repo)
    assert b"[patterns.ddd]" not in _manifest_bytes(repo)


def test_removing_the_last_pattern_leaves_a_zero_pattern_manifest_the_reporter_calls_ok(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    report = _remove(repo, ["ddd"])
    assert sorted(report.removed) == ["ddd"]
    m = _load_lib("manifest").read(repo)
    assert m.patterns == {}
    assert m.bundle == BUNDLE
    assert _reporter_stdout(repo, cat) == "OK\n"


def test_remove_propagates_an_unparseable_manifest_before_touching_anything(tmp_path):
    repo, _cat = _setup(tmp_path, ["ddd"])
    manifest = _load_lib("manifest")
    manifest._manifest_path(repo).write_text("broken = = [", encoding="utf-8")
    before = _digest(_skills(repo))
    with pytest.raises(manifest.ManifestUnparseableError):
        _remove(repo, ["ddd"])
    assert _digest(_skills(repo)) == before


# =============================================================================
# remove(): faults, and the order of the five steps
# =============================================================================


def test_a_step2_oserror_after_a_partial_stash_delete_fails_and_goes_no_further(tmp_path, monkeypatch):
    repo, _cat = _setup(tmp_path, ["ddd"])
    stash = _skills(repo) / ".tcs-ddd.replaced"
    shutil.copytree(_skills(repo) / "tcs-ddd", stash)
    before_dir, before_manifest = _digest(_skills(repo) / "tcs-ddd"), _manifest_bytes(repo)
    real_rmtree = shutil.rmtree

    def partial_rmtree(path, *args, **kwargs):
        if Path(path) == stash:
            (stash / "SKILL.md").unlink()  # part of the stash is gone...
            raise OSError("injected: stash delete failed part-way")  # ...then it fails
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", partial_rmtree)
    report = _remove(repo, ["ddd"])
    monkeypatch.undo()

    assert "injected: stash delete failed part-way" in report.failed["ddd"]
    assert report.removed == {}
    assert _digest(_skills(repo) / "tcs-ddd") == before_dir
    assert _manifest_bytes(repo) == before_manifest
    assert not (_skills(repo) / ".tcs-ddd.removing").exists()  # step 3 never ran


class _Killed(BaseException):
    """A hard stop: not an `Exception`, so nothing in `remove()` handles it."""


def test_interrupted_right_after_the_move_aside_leaves_no_replaced_debris(tmp_path, monkeypatch):
    """A stash is present at the start. Step 2 must have deleted it before the
    move-aside, so a kill right after step 3 leaves nothing status calls
    `replaced` -- which, with the directory absent, would read as "your copy"."""
    repo, cat = _setup(tmp_path, ["ddd"])
    shutil.copytree(_skills(repo) / "tcs-ddd", _skills(repo) / ".tcs-ddd.replaced")
    real_rename = os.rename

    def rename_then_die(src, dst, *args, **kwargs):
        real_rename(src, dst, *args, **kwargs)
        raise _Killed

    monkeypatch.setattr(os, "rename", rename_then_die)
    with pytest.raises(_Killed):
        _remove(repo, ["ddd"])
    monkeypatch.undo()

    debris = _load_lib("status").status(repo, catalogue_dir=cat).debris
    assert [d.kind for d in debris if d.kind == "replaced"] == []
    assert [(d.name, d.kind) for d in debris] == [(".tcs-ddd.removing", "removing")]


def test_a_manifest_drop_fault_puts_the_directory_back_byte_identical(tmp_path, monkeypatch):
    repo, _cat = _setup(tmp_path, ["ddd"])
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    def boom(*_a, **_k):
        raise OSError("injected: manifest write failed")

    monkeypatch.setattr(_load_lib("manifest"), "drop", boom)
    report = _remove(repo, ["ddd"])
    monkeypatch.undo()

    assert "injected: manifest write failed" in report.failed["ddd"]
    assert report.removed == {}
    assert _digest(_skills(repo)) == before_skills
    assert _manifest_bytes(repo) == before_manifest


def test_a_failed_rename_back_after_a_drop_fault_is_reported_and_leaves_the_removing_directory(
    tmp_path, monkeypatch
):
    """Step 4 fails AND the directory cannot be put back: both errors reach the
    report, and `.removing` -- the user's only copy -- is left for `status`."""
    repo, cat = _setup(tmp_path, ["ddd"])
    skills = _skills(repo)
    dest, removing = skills / "tcs-ddd", skills / ".tcs-ddd.removing"
    before_dir, before_manifest = _digest(dest), _manifest_bytes(repo)
    real_rename = os.rename
    fired: list[str] = []

    def drop_boom(*_a, **_k):
        fired.append("drop")
        raise OSError("drop-boom")

    def rename_unless_back_to_dest(src, dst, *args, **kwargs):
        if Path(dst) == dest:
            fired.append("back")
            raise OSError("back-boom")
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(_load_lib("manifest"), "drop", drop_boom)
    monkeypatch.setattr(os, "rename", rename_unless_back_to_dest)
    report = _remove(repo, ["ddd"])
    monkeypatch.undo()

    assert fired == ["drop", "back"]
    assert "drop-boom" in report.failed["ddd"]
    assert "back to" in report.failed["ddd"]
    assert "back-boom" in report.failed["ddd"]
    assert report.removed == {}
    assert _digest(removing) == before_dir
    assert not dest.exists()
    assert _manifest_bytes(repo) == before_manifest
    debris = _debris(_load_lib("status").status(repo, catalogue_dir=cat))
    assert debris == {".tcs-ddd.removing": ("removing", "run `remove ddd` to finish")}


def test_a_step1_failure_on_a_stale_removing_fails_and_goes_no_further(tmp_path, monkeypatch):
    repo, _cat = _setup(tmp_path, ["ddd"])
    skills = _skills(repo)
    dest, stale = skills / "tcs-ddd", skills / ".tcs-ddd.removing"
    (stale / "reference").mkdir(parents=True)
    (stale / "reference" / "old.md").write_text("old\n", encoding="utf-8")
    before_dir, before_stale = _digest(dest), _digest(stale)
    before_manifest = _manifest_bytes(repo)
    real_rmtree, real_rename = shutil.rmtree, os.rename
    fired: list[str] = []
    renames: list[tuple] = []

    def rmtree_unless_stale(path, *args, **kwargs):
        if Path(path) == stale:
            fired.append("rmtree")
            if kwargs.get("ignore_errors"):  # as the real rmtree: the error is swallowed
                return None
            raise OSError("step1-boom")
        return real_rmtree(path, *args, **kwargs)

    def spy_rename(*args, **kwargs):
        renames.append(args)
        return real_rename(*args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", rmtree_unless_stale)
    monkeypatch.setattr(os, "rename", spy_rename)
    report = _remove(repo, ["ddd"])
    monkeypatch.undo()

    assert fired == ["rmtree"]
    assert "step1-boom" in report.failed["ddd"]
    assert report.removed == {}
    assert _digest(dest) == before_dir
    assert _digest(stale) == before_stale
    assert _manifest_bytes(repo) == before_manifest
    assert renames == []


def test_a_move_aside_rename_fault_leaves_the_manifest_and_directory_intact(tmp_path, monkeypatch):
    """Only this test can see a manifest written BEFORE the rename."""
    repo, _cat = _setup(tmp_path, ["ddd"])
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    def refuse(*_a, **_k):
        raise OSError("injected: rename refused")

    monkeypatch.setattr(os, "rename", refuse)
    report = _remove(repo, ["ddd"])
    monkeypatch.undo()

    assert "injected: rename refused" in report.failed["ddd"]
    assert _manifest_bytes(repo) == before_manifest
    assert _digest(_skills(repo)) == before_skills


def test_on_the_resume_path_a_manifest_drop_fault_renames_nothing_back(tmp_path, monkeypatch):
    """Entry listed, directory absent, `.removing` present. Spies on os.rename
    AND os.replace see zero calls after the fault, so a rename-back hidden
    inside an OSError handler is still caught."""
    repo, _cat = _setup(tmp_path, ["ddd"])
    os.rename(_skills(repo) / "tcs-ddd", _skills(repo) / ".tcs-ddd.removing")
    before_manifest = _manifest_bytes(repo)

    faulted = False
    calls_after_fault: list[tuple[str, tuple]] = []
    real_rename, real_replace = os.rename, os.replace

    def spy_rename(*args, **kwargs):
        if faulted:
            calls_after_fault.append(("rename", args))
        return real_rename(*args, **kwargs)

    def spy_replace(*args, **kwargs):
        if faulted:
            calls_after_fault.append(("replace", args))
        return real_replace(*args, **kwargs)

    def boom(*_a, **_k):
        nonlocal faulted
        faulted = True
        raise OSError("injected: drop failed on resume")

    monkeypatch.setattr(os, "rename", spy_rename)
    monkeypatch.setattr(os, "replace", spy_replace)
    monkeypatch.setattr(_load_lib("manifest"), "drop", boom)
    report = _remove(repo, ["ddd"])
    monkeypatch.undo()

    assert faulted
    assert calls_after_fault == []
    assert "injected: drop failed on resume" in report.failed["ddd"]
    assert _manifest_bytes(repo) == before_manifest
    assert not (_skills(repo) / "tcs-ddd").exists()


# =============================================================================
# remove(): interrupted states, built by hand
# =============================================================================


def test_state_a_listed_entry_absent_directory_and_removing_is_finished_by_a_rerun(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    os.rename(_skills(repo) / "tcs-ddd", _skills(repo) / ".tcs-ddd.removing")

    report = _remove(repo, ["ddd"])

    assert report.removed == {"ddd": ("tcs-ddd", "1", False)}
    assert _load_lib("manifest").read(repo).patterns == {}
    assert not (_skills(repo) / ".tcs-ddd.removing").exists()
    assert _load_lib("status").status(repo, catalogue_dir=cat).debris == ()


def _after_step4(repo: Path) -> None:
    """The state an interruption between steps 4 and 5 leaves."""
    os.rename(_skills(repo) / "tcs-ddd", _skills(repo) / ".tcs-ddd.removing")
    _load_lib("manifest").drop(repo, "ddd", bundle=BUNDLE)


def test_state_b_removing_alone_is_refused_by_rule1_and_reported_as_safe_debris(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    _after_step4(repo)
    before_skills, before_manifest = _digest(_skills(repo)), _manifest_bytes(repo)

    report = _remove(repo, ["ddd"])

    _assert_refused_and_untouched(repo, report, "ddd", before_skills, before_manifest)
    assert "not recorded in the manifest" in report.refused["ddd"]
    debris = _load_lib("status").status(repo, catalogue_dir=cat).debris
    assert [(d.name, d.kind, d.resolution) for d in debris] == [
        (".tcs-ddd.removing", "removing", "safe to delete")
    ]


def test_state_c_removing_left_behind_then_install_is_safe_debris_not_a_remove(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    _after_step4(repo)
    assert not _load_lib("install").install(repo, ["ddd"], catalogue_dir=cat, bundle=BUNDLE).failed

    report = _load_lib("status").status(repo, catalogue_dir=cat)
    assert report.patterns["ddd"].directory_present is True
    [debris] = report.debris
    assert (debris.name, debris.kind, debris.resolution) == (".tcs-ddd.removing", "removing", "safe to delete")
    assert "remove" not in debris.resolution
