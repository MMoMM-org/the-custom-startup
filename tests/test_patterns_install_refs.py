"""T5.3a (spec-020): installed patterns name each other as `tcs-<name>`.

After 2.0 the address `tcs-patterns:<name>` resolves to nothing -- the 21
are no longer plugin skills, and an installed pattern is the repository
skill `tcs-<name>` (ADR-1). The installer therefore rewrites every
catalogue-pattern marker in the files it copies, and `_catalogue_as_installed`
applies the same rewrite, so `update`'s and `remove`'s diffs see it as
upstream text rather than as a local edit
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/solution.md,
ADR-1, "Amended 2026-10-07"]`.

Every expectation below is hand-typed. None is derived by calling the
rewrite function, because a check computed with the logic under test is
blind to everything that logic does.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"
REAL_CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"
TEST_BUNDLE = "0.0.0-test"


def _load_install() -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("install")


# --- fixture -----------------------------------------------------------------

ALPHA_SKILL = (
    "---\n"
    "name: alpha\n"
    "description: fixture; pairs with tcs-patterns:beta\n"
    "---\n"
    "\n"
    "See `tcs-patterns:beta` and `tcs-patterns:alpha` itself.\n"
    "Run `tcs-patterns:patterns-setup`, or read one with `tcs-patterns:pattern alpha`.\n"
    "Not a pattern: `tcs-patterns:foo`, nor `tcs-patterns:beta-extra`.\n"
    "Line the user will edit.\n"
)

ALPHA_SKILL_INSTALLED = (
    "---\n"
    "name: tcs-alpha\n"
    "description: fixture; pairs with tcs-beta\n"
    "---\n"
    "\n"
    "See `tcs-beta` and `tcs-alpha` itself.\n"
    "Run `tcs-patterns:patterns-setup`, or read one with `tcs-patterns:pattern alpha`.\n"
    "Not a pattern: `tcs-patterns:foo`, nor `tcs-patterns:beta-extra`.\n"
    "Line the user will edit.\n"
)

# CRLF on purpose: the rewrite must touch the marker and nothing else.
ALPHA_REFERENCE = b"# Notes\r\nAlso `tcs-patterns:beta` `reference/x.md`.\r\n"
ALPHA_REFERENCE_INSTALLED = b"# Notes\r\nAlso `tcs-beta` `reference/x.md`.\r\n"

# Not UTF-8: copied byte-for-byte even though it carries the marker bytes.
ALPHA_BLOB = b"\xff\xfe tcs-patterns:beta \x80"

USER_EDIT_FROM = "Line the user will edit.\n"
USER_EDIT_TO = "Line the user DID edit.\n"


def _catalogue(root: Path, *, extra_dirs: tuple[str, ...] = ()) -> Path:
    catalogue = root / "catalogue"
    alpha = catalogue / "alpha"
    (alpha / "reference").mkdir(parents=True)
    (alpha / "VERSION").write_text("1\n", encoding="utf-8")
    (alpha / "SKILL.md").write_bytes(ALPHA_SKILL.encode("utf-8"))
    (alpha / "reference" / "notes.md").write_bytes(ALPHA_REFERENCE)
    (alpha / "reference" / "blob.bin").write_bytes(ALPHA_BLOB)
    for name in ("beta", *extra_dirs):
        d = catalogue / name
        d.mkdir()
        (d / "VERSION").write_text("1\n", encoding="utf-8")
        (d / "SKILL.md").write_bytes(f"---\nname: {name}\ndescription: x\n---\n\nBody.\n".encode("utf-8"))
    return catalogue


def _installed(repo: Path, name: str = "alpha") -> Path:
    return repo / ".claude" / "skills" / f"tcs-{name}"


def _install_alpha(tmp_path: Path, **catalogue_kwargs) -> tuple[ModuleType, Path, Path]:
    install = _load_install()
    catalogue = _catalogue(tmp_path, **catalogue_kwargs)
    repo = tmp_path / "repo"
    report = install.install(repo, ["alpha"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)
    assert "alpha" in report.installed, report.failed
    return install, catalogue, repo


def _change_lines(diff: str) -> list[str]:
    """Every `-`/`+` line of a unified diff, headers excluded."""
    return [
        line
        for line in diff.splitlines()
        if line[:1] in "-+" and not line.startswith(("--- ", "+++ "))
    ]


# --- install -----------------------------------------------------------------


def test_installed_skill_md_names_catalogue_patterns_as_tcs_name(tmp_path: Path) -> None:
    _, _, repo = _install_alpha(tmp_path)
    assert (_installed(repo) / "SKILL.md").read_bytes() == ALPHA_SKILL_INSTALLED.encode("utf-8")


def test_installed_reference_file_is_rewritten_and_keeps_its_line_endings(tmp_path: Path) -> None:
    _, _, repo = _install_alpha(tmp_path)
    assert (_installed(repo) / "reference" / "notes.md").read_bytes() == ALPHA_REFERENCE_INSTALLED


def test_non_utf8_file_is_copied_unchanged(tmp_path: Path) -> None:
    _, _, repo = _install_alpha(tmp_path)
    assert (_installed(repo) / "reference" / "blob.bin").read_bytes() == ALPHA_BLOB


def test_plugin_skill_names_stay_plugin_addresses_even_beside_a_same_named_catalogue_dir(tmp_path: Path) -> None:
    """`patterns-setup` and `pattern` are still plugin skills, so their
    markers resolve as written. Excluded by name -- a catalogue directory
    that happened to carry either name must not redirect them to a
    `tcs-<name>` skill."""
    _, _, repo = _install_alpha(tmp_path, extra_dirs=("patterns-setup", "pattern"))
    text = (_installed(repo) / "SKILL.md").read_text(encoding="utf-8")
    assert "Run `tcs-patterns:patterns-setup`, or read one with `tcs-patterns:pattern alpha`.\n" in text
    assert "tcs-patterns-setup" not in text


def test_manifest_hash_is_of_the_rewritten_skill_md(tmp_path: Path) -> None:
    install, _, repo = _install_alpha(tmp_path)
    expected = hashlib.sha256(ALPHA_SKILL_INSTALLED.encode("utf-8")).hexdigest()
    entry = importlib.import_module("manifest").read(repo).patterns["alpha"]
    assert entry.sha256 == expected


def test_real_ddd_install_leaves_no_catalogue_marker(tmp_path: Path) -> None:
    install = _load_install()
    repo = tmp_path / "repo"
    report = install.install(repo, ["ddd"], catalogue_dir=REAL_CATALOGUE_DIR, bundle=TEST_BUNDLE)
    assert "ddd" in report.installed, report.failed
    dest = _installed(repo, "ddd")

    leftover = []
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        leftover += re.findall(r"tcs-patterns:([A-Za-z0-9_-]+)", path.read_text(encoding="utf-8"))
    assert set(leftover) <= {"patterns-setup", "pattern"}, leftover

    skill = (dest / "SKILL.md").read_text(encoding="utf-8")
    for expected in ("**Active skill: tcs-ddd**", "`tcs-event-sourcing`", "`tcs-event-driven`"):
        assert expected in skill, expected
    assert "`tcs-hexagonal`" in (dest / "reference" / "testing-by-layer.md").read_text(encoding="utf-8")


# --- update ------------------------------------------------------------------


def test_update_on_an_unedited_current_install_reports_current(tmp_path: Path) -> None:
    install, catalogue, repo = _install_alpha(tmp_path)
    calls: list[str] = []

    def decide(name: str, diff: str) -> bool:
        calls.append(name)
        return False

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert list(report.current) == ["alpha"]
    assert report.declined == {} and report.refreshed == {} and report.failed == {}
    assert calls == []


def test_update_after_a_version_bump_refreshes_an_unedited_install_without_asking(tmp_path: Path) -> None:
    install, catalogue, repo = _install_alpha(tmp_path)
    (catalogue / "alpha" / "VERSION").write_text("2\n", encoding="utf-8")
    calls: list[str] = []

    def decide(name: str, diff: str) -> bool:
        calls.append(name)
        return False

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert calls == []
    assert report.declined == {} and report.failed == {}
    assert report.refreshed["alpha"][1:3] == ("1", "2")
    assert (_installed(repo) / "SKILL.md").read_bytes() == ALPHA_SKILL_INSTALLED.encode("utf-8")
    assert (_installed(repo) / "reference" / "notes.md").read_bytes() == ALPHA_REFERENCE_INSTALLED


def _edit_installed(repo: Path) -> None:
    skill_md = _installed(repo) / "SKILL.md"
    edited = ALPHA_SKILL_INSTALLED.replace(USER_EDIT_FROM, USER_EDIT_TO)
    assert edited != ALPHA_SKILL_INSTALLED
    skill_md.write_bytes(edited.encode("utf-8"))


def test_update_diff_of_a_local_edit_shows_only_the_edit(tmp_path: Path) -> None:
    install, catalogue, repo = _install_alpha(tmp_path)
    _edit_installed(repo)
    seen: list[str] = []

    def decide(name: str, diff: str) -> bool:
        seen.append(diff)
        return False

    report = install.update(repo, catalogue_dir=catalogue, bundle=TEST_BUNDLE, decide=decide)

    assert len(seen) == 1
    _, diff = report.declined["alpha"]
    assert diff == seen[0]
    assert _change_lines(diff) == ["-Line the user DID edit.", "+Line the user will edit."]


def test_remove_diff_of_a_local_edit_shows_only_the_edit(tmp_path: Path) -> None:
    install, catalogue, repo = _install_alpha(tmp_path)
    _edit_installed(repo)

    report = install.remove(repo, ["alpha"], catalogue_dir=catalogue, bundle=TEST_BUNDLE)

    _, diff = report.refused["alpha"]
    assert _change_lines(diff) == ["-Line the user DID edit.", "+Line the user will edit."]
    assert _installed(repo).is_dir()
