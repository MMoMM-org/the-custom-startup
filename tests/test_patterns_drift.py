"""T4.2 (spec-020): the patterns drift reporter (`patterns_drift.py`).

Contract `[ref: SDD/Interface Specifications/Process contract: drift reporter]`:
zero or more stdout lines, exit 0 always --

    OK | MISSING | DRIFT:<pattern>:<installed>:<catalogue> | UNKNOWN:<pattern>:<installed>

Drift is computed from each pattern's own manifest `version`, never from the
manifest's top-level `bundle` (decision 9) -- `test_refreshing_one_pattern_...`
pins that.
"""

from __future__ import annotations

import importlib
import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugins" / "tcs-patterns"
LIB_DIR = PLUGIN_DIR / "skills" / "patterns-setup" / "lib"
SCRIPT = PLUGIN_DIR / "scripts" / "patterns_drift.py"

BUNDLE = "1.0.0"


def _load_lib(name: str) -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module(name)


def _load_drift() -> ModuleType:
    spec = importlib.util.spec_from_file_location("patterns_drift_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _catalogue_pattern(root: Path, name: str, version: str | None = "1") -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    if version is not None:
        (d / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: fixture\n---\n\nBody for {name}.\n", encoding="utf-8"
    )


def _set_version(root: Path, name: str, version: str) -> None:
    (root / name / "VERSION").write_text(f"{version}\n", encoding="utf-8")


def _setup(tmp_path: Path, names: list[str], extra_catalogue: Sequence[str] = ()) -> tuple[Path, Path]:
    """A catalogue holding `names` + `extra_catalogue`, and a repo that installed `names`."""
    cat = tmp_path / "catalogue"
    for n in [*names, *extra_catalogue]:
        _catalogue_pattern(cat, n)
    repo = tmp_path / "repo"
    repo.mkdir()
    report = _load_lib("install").install(repo, list(names), catalogue_dir=cat, bundle=BUNDLE)
    assert not report.failed
    return repo, cat


def _lines(repo: Path, cat: Path) -> list[str]:
    return _load_drift().drift_lines(repo, catalogue_dir=cat)


def test_all_current_prints_exactly_ok(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    assert _lines(repo, cat) == ["OK"]


def test_two_behind_prints_two_drift_lines_naming_both_versions_and_no_ok(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal", "functional"])
    _set_version(cat, "ddd", "4")
    _set_version(cat, "hexagonal", "5")
    assert _lines(repo, cat) == ["DRIFT:ddd:1:4", "DRIFT:hexagonal:1:5"]


def test_no_manifest_prints_missing(tmp_path):
    cat = tmp_path / "catalogue"
    _catalogue_pattern(cat, "ddd")
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _lines(repo, cat) == ["MISSING"]


def test_nonexistent_repo_path_prints_missing(tmp_path):
    cat = tmp_path / "catalogue"
    _catalogue_pattern(cat, "ddd")
    assert _lines(tmp_path / "nowhere", cat) == ["MISSING"]


def test_unparseable_manifest_prints_missing(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    lib = _load_lib("manifest")
    lib._manifest_path(repo).write_text("this is = = not toml [", encoding="utf-8")
    assert _lines(repo, cat) == ["MISSING"]


def test_schema_invalid_manifest_prints_missing(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    lib = _load_lib("manifest")
    lib._manifest_path(repo).write_text('bundle = "1.0.0"\nsurprise = 1\n', encoding="utf-8")
    assert _lines(repo, cat) == ["MISSING"]


def test_catalogue_pattern_changed_but_not_installed_is_never_mentioned(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"], extra_catalogue=["go-idiomatic"])
    _set_version(cat, "go-idiomatic", "9")
    assert _lines(repo, cat) == ["OK"]


def test_uninstalled_pattern_changing_beside_a_drifted_one_stays_silent(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"], extra_catalogue=["go-idiomatic"])
    _set_version(cat, "ddd", "2")
    _set_version(cat, "go-idiomatic", "9")
    assert _lines(repo, cat) == ["DRIFT:ddd:1:2"]


def test_absent_catalogue_version_is_unknown_not_drift_and_suppresses_ok(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    (cat / "ddd" / "VERSION").unlink()
    assert _lines(repo, cat) == ["UNKNOWN:ddd:1"]


def test_non_numeric_catalogue_version_is_unknown(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    _set_version(cat, "ddd", "v2-beta")
    assert _lines(repo, cat) == ["UNKNOWN:ddd:1"]


def test_empty_catalogue_version_is_unknown(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    (cat / "ddd" / "VERSION").write_text("\n", encoding="utf-8")
    assert _lines(repo, cat) == ["UNKNOWN:ddd:1"]


def test_pattern_directory_gone_from_catalogue_is_unknown(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    shutil.rmtree(cat / "hexagonal")
    assert _lines(repo, cat) == ["UNKNOWN:hexagonal:1"]


def test_unknown_and_drift_coexist_sorted_by_pattern_name(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "functional", "hexagonal"])
    _set_version(cat, "hexagonal", "3")
    _set_version(cat, "functional", "x")
    _set_version(cat, "ddd", "2")
    assert _lines(repo, cat) == ["DRIFT:ddd:1:2", "UNKNOWN:functional:1", "DRIFT:hexagonal:1:3"]


def test_refreshing_one_pattern_advances_bundle_but_the_stale_one_still_drifts(tmp_path):
    """Decision 9: `bundle` records who last WROTE the manifest, not what every
    pattern came from. A reporter keyed on `bundle` answers OK here."""
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    install = _load_lib("install")
    manifest = _load_lib("manifest")

    _set_version(cat, "ddd", "2")
    report = install.update(repo, catalogue_dir=cat, bundle="2.0.0")
    assert not report.failed
    _set_version(cat, "hexagonal", "2")  # hexagonal now lags; ddd is current

    m = manifest.read(repo)
    assert m.bundle == "2.0.0"  # the bundle really advanced...
    assert m.patterns["ddd"].version == "2"
    assert m.patterns["hexagonal"].version == "1"  # ...while hexagonal kept its old version

    assert _lines(repo, cat) == ["DRIFT:hexagonal:1:2"]


def _run(repo: Path, cat: Path | None, cwd: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), str(repo)]
    if cat is not None:
        cmd += ["--catalogue", str(cat)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def test_cli_exits_zero_and_prints_the_lines_from_any_cwd(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd", "hexagonal"])
    _set_version(cat, "ddd", "2")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    r = _run(repo, cat, elsewhere)
    assert r.returncode == 0
    assert r.stdout == "DRIFT:ddd:1:2\n"


def test_cli_exit_zero_for_ok_missing_unknown_and_nonexistent_repo(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    ok = _run(repo, cat, tmp_path)
    assert (ok.returncode, ok.stdout) == (0, "OK\n")

    (cat / "ddd" / "VERSION").unlink()
    unk = _run(repo, cat, tmp_path)
    assert (unk.returncode, unk.stdout) == (0, "UNKNOWN:ddd:1\n")

    empty = tmp_path / "empty"
    empty.mkdir()
    miss = _run(empty, cat, tmp_path)
    assert (miss.returncode, miss.stdout) == (0, "MISSING\n")

    gone = _run(tmp_path / "nowhere", cat, tmp_path)
    assert (gone.returncode, gone.stdout) == (0, "MISSING\n")


def test_cli_exits_zero_even_without_a_repo_argument(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0


def test_cli_defaults_to_the_real_catalogue(tmp_path):
    """No --catalogue: the script resolves the shipped catalogue from its own __file__."""
    real = PLUGIN_DIR / "templates" / "patterns"
    repo = tmp_path / "repo"
    repo.mkdir()
    _load_lib("install").install(repo, ["ddd"], catalogue_dir=real, bundle=BUNDLE)
    r = _run(repo, None, tmp_path)
    assert (r.returncode, r.stdout) == (0, "OK\n")


def test_non_utf8_manifest_prints_missing(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    _load_lib("manifest")._manifest_path(repo).write_bytes(b"\xff\xfe\x00")
    assert _lines(repo, cat) == ["MISSING"]


def test_present_manifest_naming_no_patterns_prints_ok(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    _load_lib("manifest")._manifest_path(repo).write_text('bundle = "1.0.0"\n', encoding="utf-8")
    assert _lines(repo, cat) == ["OK"]


def test_main_swallows_any_exception_from_drift_lines(tmp_path, monkeypatch, capsys):
    mod = _load_drift()

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "drift_lines", boom)
    assert mod.main(["patterns_drift.py", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "boom" in captured.err


def test_cli_exits_zero_and_stays_silent_when_the_lib_is_unreachable(tmp_path):
    """A partial plugin copy (script without skills/patterns-setup/lib) must not traceback."""
    scripts = tmp_path / "plugin" / "scripts"
    scripts.mkdir(parents=True)
    copy = scripts / "patterns_drift.py"
    copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    r = subprocess.run([sys.executable, str(copy), str(repo)], capture_output=True, text=True, cwd=tmp_path)
    assert (r.returncode, r.stdout) == (0, "")
    assert r.stderr.strip() != ""


def test_cli_catalogue_flag_without_value_fails(tmp_path):
    repo, cat = _setup(tmp_path, ["ddd"])
    r = _run(repo, None, tmp_path)
    r.returncode == 0
    # Run with --catalogue flag but no value should fail
    cmd = [sys.executable, str(SCRIPT), str(repo), "--catalogue"]
    bad = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp_path)
    assert bad.returncode == 0
    assert bad.stdout == ""
    assert bad.stderr.strip() != ""
