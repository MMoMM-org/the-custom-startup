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
