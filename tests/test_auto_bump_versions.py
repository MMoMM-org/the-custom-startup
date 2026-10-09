"""Behavioural coverage for scripts/ci/auto-bump-versions.sh.

The script patch-bumps a plugin once for every commit that touched it since
its version was last raised, so a run that never happened (#196) is caught up
by the next one. A major or minor release cannot be produced by a patch bump,
so it is requested in the plugin's own CHANGELOG: when the top heading names
exactly the next major (M+1.0.0) or the next minor (M.m+1.0) of the manifest's
version, the manifest is set to that version instead. Anything else falls back
to the patch bump.

Each case builds a throwaway git repository with one plugin and a marketplace,
commits changes, and runs the real script on the checked-out state. Expected
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
    return _make_repo(tmp_path, "1.4.4")


def _make_repo(tmp_path, base_version):
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
        json.dumps({"name": "demo", "version": base_version}, indent=2) + "\n"
    )
    (work / "plugins" / "demo" / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{base_version}] - 2026-09-04\n\n### Fixed\n\n- an older entry\n"
    )
    _git(work, env, "add", "-A")
    _git(work, env, "commit", "--quiet", "-m", "base")
    base = _git(work, env, "rev-parse", "HEAD")
    return {"work": work, "env": env, "base": base}


def _commit_change(repo, heading=None, manifest_version=None, changelog_bytes=None):
    """Touch the plugin; optionally rewrite the CHANGELOG and the manifest."""
    work, env = repo["work"], repo["env"]
    (work / "plugins" / "demo" / "notes.md").write_text("a change\n")
    if heading is not None:
        (work / "plugins" / "demo" / "CHANGELOG.md").write_text(_changelog(heading))
    if changelog_bytes is not None:
        (work / "plugins" / "demo" / "CHANGELOG.md").write_bytes(changelog_bytes)
    if manifest_version is not None:
        _manifest_path(work).write_text(
            json.dumps({"name": "demo", "version": manifest_version}, indent=2) + "\n"
        )
    _git(work, env, "add", "-A")
    _git(work, env, "commit", "--quiet", "-m", "change demo")
    return _git(work, env, "rev-parse", "HEAD")


def _run_bump(repo, *args):
    """Run the script the way CI does: on the checked-out state, no range."""
    return subprocess.run(
        ["bash", str(BUMP), *args],
        cwd=repo["work"], capture_output=True, text=True, env=repo["env"],
    )


def _bumped_to(repo, heading=None, manifest_version=None, changelog_bytes=None):
    _commit_change(repo, heading=heading, manifest_version=manifest_version,
                   changelog_bytes=changelog_bytes)
    r = _run_bump(repo)
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
    _commit_change(repo, heading="## [2.0.0] - 2026-10-06")
    r = _run_bump(repo)
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


# ---------------------------------------------------------------------------
# What counts as a release request: a canonical X.Y.Z closed by "]",
# whitespace or end of line — the same rule check-changelog-version-sync.sh
# applies, so the PR-side check and the merge never disagree.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("heading", [
    "## [2.0.0-rc1] - 2026-10-06",
    "## [1.5.0-beta.2] - 2026-10-06",
    "## [2.0.0+build.7] - 2026-10-06",
])
def test_a_pre_release_heading_requests_nothing(repo, heading):
    """2.0.0-rc1 must not ship as the final 2.0.0."""
    assert _bumped_to(repo, heading=heading) == "1.4.5"


@pytest.mark.parametrize("heading", [
    "## [2.00.0] - 2026-10-06",
    "## [01.5.0] - 2026-10-06",
    "## [1.05.0] - 2026-10-06",
])
def test_a_non_canonical_version_requests_nothing(repo, heading):
    assert _bumped_to(repo, heading=heading) == "1.4.5"


@pytest.mark.parametrize("raw", [
    b"# Changelog\r\n\r\n## [2.0.0] - 2026-10-06\r\n\r\n- breaking\r\n",
    b"# Changelog\r\n\r\n## 2.0.0\r\n\r\n- breaking\r\n",
])
def test_a_crlf_heading_is_read(repo, raw):
    assert _bumped_to(repo, changelog_bytes=raw) == "2.0.0"


def test_unreleased_above_a_next_major_heading_is_a_patch_bump(repo):
    """Only the top heading requests a release; Unreleased requests nothing."""
    raw = (b"# Changelog\n\n## [Unreleased]\n\n- pending\n\n"
           b"## [2.0.0] - 2026-10-06\n\n- breaking\n")
    assert _bumped_to(repo, changelog_bytes=raw) == "1.4.5"


@pytest.mark.parametrize("base, heading, expected", [
    ("1.9.3", "## [1.10.0] - 2026-10-06", "1.10.0"),   # minor past 9
    ("0.4.2", "## [1.0.0] - 2026-10-06", "1.0.0"),     # 0.x to the first major
    ("0.4.2", "## [0.5.0] - 2026-10-06", "0.5.0"),     # 0.x next minor
])
def test_next_release_from_other_bases(tmp_path, base, heading, expected):
    assert _bumped_to(_make_repo(tmp_path, base), heading=heading) == expected


# ---------------------------------------------------------------------------
# Catching up (#196): the bump is derived from the state of main, not from the
# push that triggered the run. GitHub delivered no push event for #187, no run
# happened, and a range-based bump never looked at that commit again.
# ---------------------------------------------------------------------------


def _commit(repo, message, write=None, remove=None):
    """Commit arbitrary file writes ({relpath: text}) and removals."""
    work, env = repo["work"], repo["env"]
    for rel, text in (write or {}).items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for rel in remove or ():
        _git(work, env, "rm", "-r", "--quiet", rel)
    _git(work, env, "add", "-A")
    _git(work, env, "commit", "--quiet", "-m", message)
    return _git(work, env, "rev-parse", "HEAD")


def _manifest_text(version, indent=2, name="demo"):
    return json.dumps({"name": name, "version": version}, indent=indent) + "\n"


def _bump_ok(repo, *args):
    r = _run_bump(repo, *args)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def _commit_the_bump(repo):
    return _commit(repo, "chore(release): auto-bump plugin versions [skip ci]")


def _demo(repo):
    return _version(_manifest_path(repo["work"]), "version")


DEMO_CHANGELOG = "plugins/demo/CHANGELOG.md"
DEMO_MANIFEST = "plugins/demo/.claude-plugin/plugin.json"
MARKETPLACE = ".claude-plugin/marketplace.json"


def test_a_lost_run_is_caught_up_by_the_next_run(repo):
    """#196: the run for the plugin commit never happened; a docs-only push follows."""
    _commit(repo, "fix demo", write={"plugins/demo/notes.md": "a fix\n"})
    _commit(repo, "docs only", write={"README.md": "docs\n"})
    _bump_ok(repo)
    assert _demo(repo) == "1.4.5"
    assert _marketplace(repo) == "1.0.1"


def test_two_lost_commits_replay_their_own_changelog_headings(repo):
    """Each lost commit gets the bump its own run would have made."""
    _commit(repo, "one", write={"plugins/demo/a.md": "a\n",
                                DEMO_CHANGELOG: _changelog("## [1.4.5] - 2026-10-08")})
    _commit(repo, "two", write={"plugins/demo/b.md": "b\n",
                                DEMO_CHANGELOG: _changelog("## [1.4.6] - 2026-10-09")})
    _bump_ok(repo)
    assert _demo(repo) == "1.4.6"
    r = subprocess.run(
        ["bash", str(SYNC), "--allow-ahead", "0", str(repo["work"] / "plugins" / "demo")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_lost_minor_request_followed_by_a_patch_replays_both(repo):
    _commit(repo, "feature", write={"plugins/demo/a.md": "a\n",
                                    DEMO_CHANGELOG: _changelog("## [1.5.0] - 2026-10-08")})
    _commit(repo, "fix", write={"plugins/demo/b.md": "b\n",
                                DEMO_CHANGELOG: _changelog("## [1.5.1] - 2026-10-09")})
    _bump_ok(repo)
    assert _demo(repo) == "1.5.1"


def test_a_second_run_after_the_bump_changes_nothing(repo):
    _commit(repo, "fix demo", write={"plugins/demo/notes.md": "a fix\n"})
    _bump_ok(repo)
    _commit_the_bump(repo)
    _bump_ok(repo)
    assert _git(repo["work"], repo["env"], "status", "--porcelain") == ""
    assert _demo(repo) == "1.4.5"


def test_a_reformatted_manifest_is_not_a_version_raise(repo):
    """The version line changes, the value does not: still owed for the fix."""
    _commit(repo, "fix demo", write={"plugins/demo/notes.md": "a fix\n"})
    _commit(repo, "reformat", write={DEMO_MANIFEST: _manifest_text("1.4.4", indent=4)})
    _bump_ok(repo)
    # Two commits touched the plugin since 1.4.4 was set: two patch bumps.
    assert _demo(repo) == "1.4.6"


def test_reverting_a_bump_never_reships_its_version(repo):
    _commit(repo, "fix demo", write={"plugins/demo/notes.md": "a fix\n"})
    _bump_ok(repo)
    bump = _commit_the_bump(repo)
    _git(repo["work"], repo["env"], "revert", "--no-edit", bump)
    assert _demo(repo) == "1.4.4"
    _bump_ok(repo)
    assert _demo(repo) == "1.4.6", "1.4.5 already shipped with other contents"


def test_a_hand_set_lower_version_is_not_a_raise(repo):
    _commit(repo, "downgrade", write={"plugins/demo/notes.md": "x\n",
                                      DEMO_MANIFEST: _manifest_text("1.4.2")})
    _bump_ok(repo)
    assert _demo(repo) == "1.4.5"


def test_a_change_and_its_revert_are_both_owed(repo):
    """main served the change under the old version, however briefly."""
    _commit(repo, "add", write={"plugins/demo/notes.md": "x\n"})
    _commit(repo, "revert", remove=["plugins/demo/notes.md"])
    _bump_ok(repo)
    assert _demo(repo) == "1.4.6"


def test_a_no_ff_merge_that_sets_the_version_is_not_bumped_again(repo):
    work, env = repo["work"], repo["env"]
    _git(work, env, "checkout", "--quiet", "-b", "feature")
    _commit(repo, "code", write={"plugins/demo/notes.md": "x\n"})
    _commit(repo, "hand bump", write={DEMO_MANIFEST: _manifest_text("1.4.9")})
    _git(work, env, "checkout", "--quiet", "main")
    _git(work, env, "merge", "--quiet", "--no-ff", "-m", "merge feature", "feature")
    _bump_ok(repo)
    assert _demo(repo) == "1.4.9"


def test_a_no_ff_merge_is_one_bump_however_many_commits_it_brings(repo):
    """One merge is one push is one run: its side-branch commits are not owed separately."""
    work, env = repo["work"], repo["env"]
    _git(work, env, "checkout", "--quiet", "-b", "feature")
    _commit(repo, "one", write={"plugins/demo/a.md": "a\n"})
    _commit(repo, "two", write={"plugins/demo/b.md": "b\n"})
    _git(work, env, "checkout", "--quiet", "main")
    _git(work, env, "merge", "--quiet", "--no-ff", "-m", "merge feature", "feature")
    _bump_ok(repo)
    assert _demo(repo) == "1.4.5"


def test_commits_after_a_hand_set_version_each_get_a_patch(repo):
    """Pinned: a rebase-merge loses the push boundary, so 1.5.0 then a fix ships 1.5.1."""
    _commit(repo, "hand bump", write={DEMO_MANIFEST: _manifest_text("1.5.0")})
    _commit(repo, "fix", write={"plugins/demo/notes.md": "x\n"})
    _bump_ok(repo)
    assert _demo(repo) == "1.5.1"


def test_a_hand_set_marketplace_still_gets_a_patch_for_a_plugin_bump(repo):
    """Pinned: harmless, and AGENTS.md forbids hand-setting versions anyway."""
    _commit(repo, "both", write={
        "plugins/demo/notes.md": "x\n",
        MARKETPLACE: json.dumps({"name": "test", "metadata": {"version": "1.1.0"}},
                                indent=2) + "\n",
    })
    _bump_ok(repo)
    assert _demo(repo) == "1.4.5"
    assert _marketplace(repo) == "1.1.1"


def test_the_marketplace_catches_up_on_a_lost_hand_bump(repo):
    _commit(repo, "hand bump", write={DEMO_MANIFEST: _manifest_text("1.4.9")})
    _commit(repo, "docs only", write={"README.md": "docs\n"})
    _bump_ok(repo)
    assert _demo(repo) == "1.4.9"
    assert _marketplace(repo) == "1.0.1"


def test_a_renamed_plugin_is_not_bumped_but_the_marketplace_is(repo):
    work, env = repo["work"], repo["env"]
    _git(work, env, "mv", "plugins/demo", "plugins/renamed")
    _git(work, env, "commit", "--quiet", "-m", "rename")
    _bump_ok(repo)
    renamed = work / "plugins" / "renamed" / ".claude-plugin" / "plugin.json"
    assert _version(renamed, "version") == "1.4.4"
    assert _marketplace(repo) == "1.0.1"


def test_a_deleted_plugin_does_not_break_the_run(repo):
    _commit(repo, "delete", remove=["plugins/demo"])
    _bump_ok(repo)
    assert _marketplace(repo) == "1.0.0"


def test_a_shallow_clone_is_refused(repo, tmp_path):
    _commit(repo, "fix demo", write={"plugins/demo/notes.md": "x\n"})
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1",
         f"file://{repo['work']}", str(shallow)],
        check=True, capture_output=True, env=repo["env"],
    )
    r = subprocess.run(["bash", str(BUMP)], cwd=shallow,
                       capture_output=True, text=True, env=repo["env"])
    assert r.returncode == 1
    assert "shallow" in r.stderr
    assert _version(shallow / DEMO_MANIFEST, "version") == "1.4.4"


def test_a_manifest_that_never_carried_a_version_is_an_error(repo):
    _commit(repo, "broken plugin", write={
        "plugins/broken/.claude-plugin/plugin.json": json.dumps({"name": "broken"}) + "\n",
    })
    r = _run_bump(repo)
    assert r.returncode == 1
    assert "plugins/broken" in r.stderr


def test_legacy_range_arguments_are_ignored(repo):
    """A run queued before this change calls the script with <base> <head>."""
    head = _commit(repo, "fix demo", write={"plugins/demo/notes.md": "x\n"})
    _commit(repo, "docs only", write={"README.md": "docs\n"})
    r = _bump_ok(repo, head, head)
    assert "ignored" in r.stderr
    assert _demo(repo) == "1.4.5"
