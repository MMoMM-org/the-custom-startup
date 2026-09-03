"""Behavioural coverage for scripts/ci/check-changelog-version-sync.sh.

The script guards against the state a dropped auto-bump leaves behind: a
CHANGELOG documenting a version the manifest never carried (issue #93). Each
case here builds a throwaway plugin directory and runs the real script against
it, so the assertions are about what the script *does*, not what it contains.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check-changelog-version-sync.sh"


def _make_plugin(root, name, manifest_version, changelog_heading):
    """Create a plugin directory. changelog_heading=None omits the CHANGELOG."""
    plugin = root / name
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": manifest_version}, indent=2) + "\n"
    )
    if changelog_heading is not None:
        (plugin / "CHANGELOG.md").write_text(
            f"# Changelog\n\n{changelog_heading}\n\n### Fixed\n\n- something\n"
        )
    return plugin


def _run(*args):
    return subprocess.run(
        ["bash", str(SCRIPT), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_script_is_executable():
    assert SCRIPT.exists(), f"{SCRIPT} is missing"


def test_matching_versions_pass(tmp_path):
    p = _make_plugin(tmp_path, "demo", "1.2.3", "## [1.2.3] - 2026-01-01")
    r = _run("--allow-ahead", "0", p)
    assert r.returncode == 0, r.stderr


def test_changelog_behind_manifest_passes(tmp_path):
    """Not every change earns an entry — behind is the normal steady state."""
    p = _make_plugin(tmp_path, "demo", "1.2.9", "## [1.2.3] - 2026-01-01")
    r = _run("--allow-ahead", "0", p)
    assert r.returncode == 0, r.stderr


def test_changelog_one_ahead_fails_on_main(tmp_path):
    """The exact 2026-08-31 bug: CHANGELOG 4.3.1 against plugin.json 4.3.0."""
    p = _make_plugin(tmp_path, "demo", "4.3.0", "## [4.3.1] - 2026-08-31")
    r = _run("--allow-ahead", "0", p)
    assert r.returncode == 1
    assert "CHANGELOG documents 4.3.1 but plugin.json carries 4.3.0" in r.stderr


def test_changelog_one_ahead_is_tolerated_on_a_pull_request(tmp_path):
    """Mid-PR the entry names the version the merge is about to produce."""
    p = _make_plugin(tmp_path, "demo", "4.3.0", "## [4.3.1] - 2026-08-31")
    r = _run("--allow-ahead", "1", p)
    assert r.returncode == 0, r.stderr


def test_changelog_two_ahead_fails_even_on_a_pull_request(tmp_path):
    """A patch bump cannot close a two-version gap, so this never becomes true."""
    p = _make_plugin(tmp_path, "demo", "4.3.0", "## [4.3.2] - 2026-08-31")
    r = _run("--allow-ahead", "1", p)
    assert r.returncode == 1
    assert "4.3.2" in r.stderr


def test_minor_version_ahead_is_never_tolerated(tmp_path):
    """The auto-bump only ever moves the patch component."""
    p = _make_plugin(tmp_path, "demo", "4.3.0", "## [4.4.0] - 2026-08-31")
    r = _run("--allow-ahead", "1", p)
    assert r.returncode == 1


def test_plugin_without_a_changelog_fails(tmp_path):
    """Every plugin needs one.

    The tcs-patterns bump in #114/#115 went unnoticed partly because this check
    had nothing to compare for that plugin — it had no CHANGELOG, so the missing
    version was invisible to the guard built to catch missing versions.
    """
    p = _make_plugin(tmp_path, "no-changelog", "1.0.0", None)
    comparable = _make_plugin(tmp_path, "demo", "1.0.0", "## [1.0.0] - 2026-01-01")
    r = _run("--allow-ahead", "0", p, comparable)
    assert r.returncode == 1
    assert "no CHANGELOG.md" in r.stderr


def test_a_directory_without_a_manifest_is_not_a_plugin(tmp_path):
    """A scaffold or stray directory must not be reported as a missing CHANGELOG."""
    (tmp_path / "not-a-plugin").mkdir()
    comparable = _make_plugin(tmp_path, "demo", "1.0.0", "## [1.0.0] - 2026-01-01")
    r = _run("--allow-ahead", "0", tmp_path / "not-a-plugin", comparable)
    assert r.returncode == 0, r.stderr


def test_every_plugin_in_this_repo_has_a_changelog():
    """The requirement, asserted against the real plugins."""
    plugins = [d for d in sorted((REPO_ROOT / "plugins").iterdir())
               if (d / ".claude-plugin" / "plugin.json").exists()]
    assert plugins, "found no plugins — the glob is wrong, not the repo"
    missing = [d.name for d in plugins if not (d / "CHANGELOG.md").exists()]
    assert not missing, f"plugins without a CHANGELOG: {missing}"


def test_unreleased_heading_is_skipped(tmp_path):
    p = _make_plugin(tmp_path, "demo", "1.0.0", "## [Unreleased]")
    comparable = _make_plugin(tmp_path, "other", "1.0.0", "## [1.0.0] - 2026-01-01")
    r = _run("--allow-ahead", "0", p, comparable)
    assert r.returncode == 0, r.stderr


def test_comparing_nothing_is_a_failure_not_an_all_clear(tmp_path):
    """Guard the guard: a broken glob must not read as success."""
    _make_plugin(tmp_path, "no-changelog", "1.0.0", None)
    r = _run("--allow-ahead", "0", tmp_path / "no-changelog")
    assert r.returncode == 1
    assert "compared nothing" in r.stderr


def test_repository_is_currently_consistent():
    """The real check against the real plugins.

    --allow-ahead 1, not 0: this runs on pull requests, where a CHANGELOG entry
    legitimately names the version the merge is about to produce. The strict
    --allow-ahead 0 form belongs in the auto-bump workflow, which runs on main
    after the bump has happened.
    """
    r = _run("--allow-ahead", "1")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("bad", ["", "x", "-1"])
def test_invalid_allow_ahead_is_a_usage_error(bad):
    r = _run("--allow-ahead", bad)
    assert r.returncode == 2
