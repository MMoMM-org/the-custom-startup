"""Behavioural coverage for scripts/ci/auto-bump-versions.sh.

The script patch-bumps every plugin a push touched. A major or minor release
cannot be produced by a patch bump, so it is requested in the plugin's own
CHANGELOG: when the top heading names exactly the next major (M+1.0.0) or the
next minor (M.m+1.0) of the manifest's version, the manifest is set to that
version instead. Anything else falls back to the patch bump.

Each case builds a throwaway git repository with one plugin and a marketplace,
commits a change, and runs the real script over the commit range. Expected
versions are typed out by hand, never computed from the input.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUMP = REPO_ROOT / "scripts" / "ci" / "auto-bump-versions.sh"
SYNC = REPO_ROOT / "scripts" / "ci" / "check-changelog-version-sync.sh"


def _env(home):
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return env


def _git(repo, env, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=env,
    ).stdout.strip()


def _changelog(heading):
    return (
        "# Changelog\n\n"
        "All notable changes to `demo` are documented here.\n\n"
        f"{heading}\n\n### Changed\n\n- something\n\n"
        "## [1.4.4] - 2026-09-04\n\n### Fixed\n\n- an older entry\n"
    )


def _manifest_path(repo):
    return repo / "plugins" / "demo" / ".claude-plugin" / "plugin.json"


def _version(path, *keys):
    data = json.loads(path.read_text())
    for k in keys:
        data = data[k]
    return data


@pytest.fixture
def repo(tmp_path):
    """A repository at base: demo 1.4.4 with a CHANGELOG topped by 1.4.4."""
    env = _env(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _git(work, env, "init", "--quiet", "-b", "main")

    (work / ".claude-plugin").mkdir()
    (work / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "test", "metadata": {"version": "1.0.0"}}, indent=2) + "\n"
    )
    _manifest_path(work).parent.mkdir(parents=True)
    _manifest_path(work).write_text(
        json.dumps({"name": "demo", "version": "1.4.4"}, indent=2) + "\n"
    )
    (work / "plugins" / "demo" / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.4.4] - 2026-09-04\n\n### Fixed\n\n- an older entry\n"
    )
    _git(work, env, "add", "-A")
    _git(work, env, "commit", "--quiet", "-m", "base")
    base = _git(work, env, "rev-parse", "HEAD")
    return {"work": work, "env": env, "base": base}


def _commit_change(repo, heading=None, manifest_version=None):
    """Touch the plugin; optionally rewrite the CHANGELOG top and the manifest."""
    work, env = repo["work"], repo["env"]
    (work / "plugins" / "demo" / "notes.md").write_text("a change\n")
    if heading is not None:
        (work / "plugins" / "demo" / "CHANGELOG.md").write_text(_changelog(heading))
    if manifest_version is not None:
        _manifest_path(work).write_text(
            json.dumps({"name": "demo", "version": manifest_version}, indent=2) + "\n"
        )
    _git(work, env, "add", "-A")
    _git(work, env, "commit", "--quiet", "-m", "change demo")
    return _git(work, env, "rev-parse", "HEAD")


def _run_bump(repo, head):
    return subprocess.run(
        ["bash", str(BUMP), repo["base"], head],
        cwd=repo["work"], capture_output=True, text=True, env=repo["env"],
    )


def _bumped_to(repo, heading=None, manifest_version=None):
    head = _commit_change(repo, heading=heading, manifest_version=manifest_version)
    r = _run_bump(repo, head)
    assert r.returncode == 0, r.stdout + r.stderr
    return _version(_manifest_path(repo["work"]), "version")


def _marketplace(repo):
    return _version(repo["work"] / ".claude-plugin" / "marketplace.json",
                    "metadata", "version")


# ---------------------------------------------------------------------------
# A major or minor release requested through the CHANGELOG
# ---------------------------------------------------------------------------


def test_next_major_heading_sets_the_manifest_to_it(repo):
    assert _bumped_to(repo, heading="## [2.0.0] - 2026-10-06") == "2.0.0"


def test_next_minor_heading_sets_the_manifest_to_it(repo):
    assert _bumped_to(repo, heading="## [1.5.0] - 2026-10-06") == "1.5.0"


def test_a_requested_release_still_bumps_the_marketplace_by_a_patch(repo):
    _bumped_to(repo, heading="## [2.0.0] - 2026-10-06")
    assert _marketplace(repo) == "1.0.1"


def test_the_requested_release_is_reported(repo):
    head = _commit_change(repo, heading="## [2.0.0] - 2026-10-06")
    r = _run_bump(repo, head)
    assert "1.4.4 -> 2.0.0" in r.stdout


# ---------------------------------------------------------------------------
# Everything else is the patch bump, as before
# ---------------------------------------------------------------------------


def test_a_patch_ahead_heading_is_a_patch_bump(repo):
    assert _bumped_to(repo, heading="## [1.4.5] - 2026-10-06") == "1.4.5"


@pytest.mark.parametrize("heading", [
    "## [3.0.0] - 2026-10-06",   # skips a major
    "## [1.6.0] - 2026-10-06",   # skips a minor
    "## [2.1.0] - 2026-10-06",   # next major, but not its .0.0
    "## [2.0.1] - 2026-10-06",
    "## [1.5.1] - 2026-10-06",
])
def test_a_heading_that_is_not_exactly_the_next_major_or_minor_is_a_patch_bump(repo, heading):
    assert _bumped_to(repo, heading=heading) == "1.4.5"


def test_a_skipped_major_is_patch_bumped_and_the_sync_check_then_fails(repo):
    """Never ship 3.0.0 from 1.4.x silently — the PR-side check names the gap."""
    assert _bumped_to(repo, heading="## [3.0.0] - 2026-10-06") == "1.4.5"
    r = subprocess.run(
        ["bash", str(SYNC), "--allow-ahead", "1", str(repo["work"] / "plugins" / "demo")],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "CHANGELOG documents 3.0.0 but plugin.json carries 1.4.5" in r.stderr


def test_an_unreleased_heading_is_a_patch_bump(repo):
    assert _bumped_to(repo, heading="## [Unreleased]") == "1.4.5"


def test_an_unchanged_changelog_is_a_patch_bump(repo):
    assert _bumped_to(repo) == "1.4.5"


def test_a_heading_equal_to_the_manifest_is_a_patch_bump(repo):
    assert _bumped_to(repo, heading="## [1.4.4] - 2026-10-06") == "1.4.5"


def test_a_plugin_without_a_changelog_is_a_patch_bump(repo):
    (repo["work"] / "plugins" / "demo" / "CHANGELOG.md").unlink()
    assert _bumped_to(repo) == "1.4.5"


def test_a_manifest_version_changed_in_the_diff_is_left_untouched(repo):
    """The author's own version wins, even against a next-major heading."""
    assert _bumped_to(repo, heading="## [2.0.0] - 2026-10-06",
                      manifest_version="1.4.9") == "1.4.9"
