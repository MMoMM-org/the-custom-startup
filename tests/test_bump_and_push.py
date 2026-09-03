"""Behavioural coverage for scripts/ci/bump-and-push.sh (issue #93).

The bug: two PRs merging seconds apart produced two concurrent auto-bump runs,
each checked out at its own commit. Whichever pushed second lost a
non-fast-forward, the job failed, and the bump was gone — no later run revisits
that push range, so the plugin shipped unbumped and consumers never saw it.

These tests build a real bare remote and run the real script against it. Every
simulated run gets its own clone, detached at its own SHA, because that is what
`actions/checkout` hands a CI run — and because two runs sharing one working
tree cannot reproduce the race at all: the second would already have the
first's bump in its HEAD. An earlier version of this file made exactly that
mistake and stayed green when the fix was removed.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "bump-and-push.sh"
BUMP_SCRIPT = REPO_ROOT / "scripts" / "ci" / "auto-bump-versions.sh"

HOOK_REJECT_FIRST = """#!/bin/sh
count=$(cat push-count 2>/dev/null || echo 0)
count=$((count + 1))
printf '%s' "$count" > push-count
if [ "$count" -le 1 ]; then
  echo "simulated race: rejecting first push" >&2
  exit 1
fi
exit 0
"""

HOOK_REJECT_ALWAYS = """#!/bin/sh
echo "always rejecting" >&2
exit 1
"""


def _env(home):
    """Isolate from the developer's global git config and from CI's."""
    env = dict(os.environ)
    env.update(
        HOME=str(home),
        GIT_CONFIG_GLOBAL=str(home / "gitconfig-absent"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return env


def _git(repo, *args, env=None, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=check, env=env,
    )


def _write_plugin(repo, name, version):
    d = repo / "plugins" / name / ".claude-plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}, indent=2) + "\n"
    )


@pytest.fixture
def world(tmp_path):
    """A bare remote plus a clone holding two plugins and the CI scripts."""
    env = _env(tmp_path)
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"

    subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", str(remote)],
                   check=True, env=env)
    subprocess.run(["git", "clone", "--quiet", str(remote), str(work)], check=True, env=env)
    _git(work, "config", "user.email", "test@example.com", env=env)
    _git(work, "config", "user.name", "Test", env=env)

    # The scripts under test, committed so every checkout of any SHA has them.
    (work / "scripts" / "ci").mkdir(parents=True)
    for src in (SCRIPT, BUMP_SCRIPT):
        (work / "scripts" / "ci" / src.name).write_bytes(src.read_bytes())

    (work / ".claude-plugin").mkdir()
    (work / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "test", "metadata": {"version": "1.0.0"}}, indent=2) + "\n"
    )
    _write_plugin(work, "demo", "1.0.0")
    _write_plugin(work, "other", "1.0.0")

    _git(work, "add", "-A", env=env)
    _git(work, "commit", "--quiet", "-m", "base", env=env)
    _git(work, "push", "--quiet", "origin", "main", env=env)

    return {
        "env": env,
        "remote": remote,
        "work": work,
        "base": _git(work, "rev-parse", "HEAD", env=env).stdout.strip(),
        "tmp": tmp_path,
        "n": [0],
    }


def _touch_plugin_and_commit(world, plugin, message):
    work, env = world["work"], world["env"]
    (work / "plugins" / plugin / "notes.md").write_text(message + "\n")
    _git(work, "add", "-A", env=env)
    _git(work, "commit", "--quiet", "-m", message, env=env)
    return _git(work, "rev-parse", "HEAD", env=env).stdout.strip()


def _fresh_checkout(world, sha):
    """A clone detached at `sha` — what actions/checkout hands each CI run."""
    world["n"][0] += 1
    dest = world["tmp"] / f"run{world['n'][0]}"
    env = world["env"]
    subprocess.run(["git", "clone", "--quiet", str(world["remote"]), str(dest)],
                   check=True, env=env)
    _git(dest, "config", "user.email", "test@example.com", env=env)
    _git(dest, "config", "user.name", "Test", env=env)
    _git(dest, "checkout", "--quiet", sha, env=env)
    return dest


def _run_bump(world, base, head, extra_env=None, at=None):
    env = dict(world["env"])
    env["MAX_ATTEMPTS"] = "4"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "scripts/ci/bump-and-push.sh", base, head],
        cwd=_fresh_checkout(world, at or head),
        capture_output=True, text=True, env=env,
    )


def _remote_json(world, path):
    out = subprocess.run(
        ["git", "-C", str(world["remote"]), "show", f"main:{path}"],
        capture_output=True, text=True, check=True, env=world["env"],
    ).stdout
    return json.loads(out)


def _remote_plugin_version(world, name):
    return _remote_json(world, f"plugins/{name}/.claude-plugin/plugin.json")["version"]


# ---------------------------------------------------------------------------


def test_happy_path_bumps_and_pushes(world):
    head = _touch_plugin_and_commit(world, "demo", "change demo")
    _git(world["work"], "push", "--quiet", "origin", "main", env=world["env"])

    r = _run_bump(world, world["base"], head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remote_plugin_version(world, "demo") == "1.0.1"
    assert _remote_json(world, ".claude-plugin/marketplace.json")["metadata"]["version"] == "1.0.1"


def test_nothing_to_bump_exits_clean(world):
    """A docs-only push must not create an empty release commit."""
    work, env = world["work"], world["env"]
    (work / "README.md").write_text("docs\n")
    _git(work, "add", "-A", env=env)
    _git(work, "commit", "--quiet", "-m", "docs only", env=env)
    head = _git(work, "rev-parse", "HEAD", env=env).stdout.strip()
    _git(work, "push", "--quiet", "origin", "main", env=env)

    before = _git(world["remote"], "rev-parse", "main", env=env).stdout.strip()
    r = _run_bump(world, world["base"], head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "No version bumps needed" in r.stdout
    assert _git(world["remote"], "rev-parse", "main", env=env).stdout.strip() == before


def test_the_race_no_longer_drops_a_bump(world):
    """The 2026-08-31 failure, reproduced.

    Two PRs land seconds apart. The run for the *second* wins the push and
    bumps `other`. The run for the first then has to bump `demo` on top of a
    main that has already moved — its checkout predates that move. Before the
    fix its push was rejected, the job failed, and demo's bump was lost.
    """
    work, env = world["work"], world["env"]

    head_first = _touch_plugin_and_commit(world, "demo", "PR one touches demo")
    head_second = _touch_plugin_and_commit(world, "other", "PR two touches other")
    _git(work, "push", "--quiet", "origin", "main", env=env)

    # The competing run gets there first and bumps `other`.
    winner = _run_bump(world, head_first, head_second)
    assert winner.returncode == 0, winner.stdout + winner.stderr
    assert _remote_plugin_version(world, "other") == "1.0.1"
    assert _remote_plugin_version(world, "demo") == "1.0.0"

    # Now the run whose bump used to be dropped. Its checkout is at head_first,
    # which the winner's release commit has already moved past.
    r = _run_bump(world, world["base"], head_first, at=head_first)
    assert r.returncode == 0, r.stdout + r.stderr

    assert _remote_plugin_version(world, "demo") == "1.0.1"
    assert _remote_plugin_version(world, "other") == "1.0.1", \
        "the competing run's bump must survive"


def test_retries_when_the_push_is_rejected(world):
    """Force a non-fast-forward on the first attempt and require recovery."""
    head = _touch_plugin_and_commit(world, "demo", "change demo")
    _git(world["work"], "push", "--quiet", "origin", "main", env=world["env"])

    # Armed only now, so it rejects the bump push rather than the setup push.
    hook = world["remote"] / "hooks" / "pre-receive"
    hook.write_text(HOOK_REJECT_FIRST)
    hook.chmod(0o755)

    r = _run_bump(world, world["base"], head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remote_plugin_version(world, "demo") == "1.0.1", \
        "exactly one bump — a retry must not double-increment"


def test_gives_up_loudly_when_every_push_is_rejected(world):
    """Never exit 0 on a bump that did not land."""
    head = _touch_plugin_and_commit(world, "demo", "change demo")
    _git(world["work"], "push", "--quiet", "origin", "main", env=world["env"])

    hook = world["remote"] / "hooks" / "pre-receive"
    hook.write_text(HOOK_REJECT_ALWAYS)
    hook.chmod(0o755)

    r = _run_bump(world, world["base"], head, extra_env={"MAX_ATTEMPTS": "2"})
    assert r.returncode == 1
    assert "could not push after 2 attempts" in r.stderr


def test_all_zero_base_sha_does_not_bump_every_plugin(world):
    """`github.event.before` is all-zeros on a first push.

    Diffing against the empty tree would mark every plugin as touched and bump
    the entire marketplace; the fallback keeps it to the single commit.
    """
    head = _touch_plugin_and_commit(world, "demo", "change demo")
    _git(world["work"], "push", "--quiet", "origin", "main", env=world["env"])

    r = _run_bump(world, "0" * 40, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "falling back" in r.stderr
    assert _remote_plugin_version(world, "demo") == "1.0.1"
    assert _remote_plugin_version(world, "other") == "1.0.0"


# ---------------------------------------------------------------------------
# Classification: touching a manifest is not the same as bumping it (#114/#115)
# ---------------------------------------------------------------------------


def _edit_manifest(world, plugin, **fields):
    """Change fields in a plugin manifest without touching its version."""
    path = world["work"] / "plugins" / plugin / ".claude-plugin" / "plugin.json"
    data = json.loads(path.read_text())
    data.update(fields)
    path.write_text(json.dumps(data, indent=2) + "\n")


def test_manifest_edited_without_a_version_change_still_bumps(world):
    """The defect that shipped two skills under one version.

    #114 and #115 both added keywords to plugins/tcs-patterns/plugin.json. The
    old rule — "this manifest is in the diff, so the author bumped it" — read
    that as deliberate and skipped the bump. Two skills went out under 1.4.0.
    """
    work, env = world["work"], world["env"]
    (work / "plugins" / "demo" / "notes.md").write_text("a new skill\n")
    _edit_manifest(world, "demo", keywords=["oauth", "oidc"])
    _git(work, "add", "-A", env=env)
    _git(work, "commit", "--quiet", "-m", "add skill and keywords", env=env)
    head = _git(work, "rev-parse", "HEAD", env=env).stdout.strip()
    _git(work, "push", "--quiet", "origin", "main", env=env)

    r = _run_bump(world, world["base"], head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remote_plugin_version(world, "demo") == "1.0.1", \
        "a manifest edit that leaves the version alone must not suppress the bump"


def test_a_real_version_change_is_not_bumped_again(world):
    """The behaviour the old rule was protecting — keep it."""
    work, env = world["work"], world["env"]
    (work / "plugins" / "demo" / "notes.md").write_text("a change\n")
    _edit_manifest(world, "demo", version="2.0.0")
    _git(work, "add", "-A", env=env)
    _git(work, "commit", "--quiet", "-m", "deliberate minor bump", env=env)
    head = _git(work, "rev-parse", "HEAD", env=env).stdout.strip()
    _git(work, "push", "--quiet", "origin", "main", env=env)

    r = _run_bump(world, world["base"], head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remote_plugin_version(world, "demo") == "2.0.0", \
        "an author's deliberate bump must survive untouched"


def test_marketplace_is_bumped_when_a_plugin_ships(world):
    """The marketplace follows a plugin bump even when its own file was edited."""
    work, env = world["work"], world["env"]
    (work / "plugins" / "demo" / "notes.md").write_text("a change\n")
    mk = work / ".claude-plugin" / "marketplace.json"
    data = json.loads(mk.read_text())
    data["description"] = "edited without touching metadata.version"
    mk.write_text(json.dumps(data, indent=2) + "\n")
    _git(work, "add", "-A", env=env)
    _git(work, "commit", "--quiet", "-m", "change plugin and marketplace prose", env=env)
    head = _git(work, "rev-parse", "HEAD", env=env).stdout.strip()
    _git(work, "push", "--quiet", "origin", "main", env=env)

    r = _run_bump(world, world["base"], head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remote_plugin_version(world, "demo") == "1.0.1"
    assert _remote_json(world, ".claude-plugin/marketplace.json")["metadata"]["version"] == "1.0.1"
