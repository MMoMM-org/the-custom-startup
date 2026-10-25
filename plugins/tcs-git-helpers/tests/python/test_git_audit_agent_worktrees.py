"""--cleanup and the leftovers of `isolation: "worktree"` agents (#226).

A committing worktree agent leaves `.claude/worktrees/agent-<id>` checking out
its feature branch, plus a `worktree-agent-<id>` base branch. --cleanup used to
skip all three: it excludes branches checked out in a worktree, and the base
branch has no PR.

These tests use a real repository with real worktrees. Only the merged-PR
lookup (gh) and the drift gate are replaced.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).parent.parent.parent / "scripts" / "git_status_audit.py"


@pytest.fixture(scope="module")
def gsa():
    spec = importlib.util.spec_from_file_location("git_status_audit_wt", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout


def _branches(repo: Path) -> set[str]:
    return set(_git(repo, "for-each-ref", "refs/heads/", "--format=%(refname:short)").split())


def _merged(name: str, pr: int) -> dict:
    return {"name": name, "pr_number": pr, "merged_at": "2026-10-07T12:00:00Z"}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "t")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "t@example.invalid")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "a.txt").write_text("a\n")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _agent_worktree(repo: Path, agent_id: str, feature: str) -> Path:
    """Lay out what a committing worktree agent leaves behind."""
    path = repo / ".claude" / "worktrees" / f"agent-{agent_id}"
    _git(repo, "worktree", "add", "-q", "-b", f"worktree-agent-{agent_id}", str(path), "main")
    _git(path, "switch", "-q", "-c", feature)
    (path / f"{agent_id}.txt").write_text("work\n")
    _git(path, "add", f"{agent_id}.txt")
    _git(path, "commit", "-q", "-m", "agent work")
    return path


def _run_cleanup(gsa, monkeypatch, repo: Path, merged: list[dict], *, assume_yes: bool, capsys):
    monkeypatch.setattr(gsa, "_drift_gate", lambda *a, **k: None)
    monkeypatch.setattr(gsa, "_gh_available", lambda: True)
    monkeypatch.setattr(gsa, "_gh_authenticated", lambda: True)
    monkeypatch.setattr(gsa, "refresh_stale_cache", lambda **kw: list(merged))
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": pytest.fail("no prompt may run in these tests"),
    )
    gsa.cmd_cleanup(
        cache_dir=repo.parent / "cache",
        repo_path=str(repo),
        interactive=False,
        assume_yes=assume_yes,
    )
    return capsys.readouterr().out


def test_listing_names_the_worktree_its_branch_and_the_base_branch(gsa, repo, monkeypatch, capsys):
    wt = _agent_worktree(repo, "a1", "feat/x")

    out = _run_cleanup(gsa, monkeypatch, repo, [_merged("feat/x", 179)], assume_yes=False, capsys=capsys)

    assert "Agent worktrees of merged PRs (1):" in out, out
    assert ".claude/worktrees/agent-a1" in out
    assert "Stale-merged branches (1):" in out
    assert "feat/x" in out
    assert "Merged agent base branches (1):" in out
    assert "worktree-agent-a1" in out
    assert wt.is_dir(), "listing must not remove anything"
    assert {"feat/x", "worktree-agent-a1"} <= _branches(repo)


def test_yes_removes_the_worktree_then_both_branches(gsa, repo, monkeypatch, capsys):
    wt = _agent_worktree(repo, "a1", "feat/x")

    out = _run_cleanup(gsa, monkeypatch, repo, [_merged("feat/x", 179)], assume_yes=True, capsys=capsys)

    assert not wt.exists(), out
    assert _branches(repo) == {"main"}, out
    assert "Removed worktree .claude/worktrees/agent-a1" in out


def test_a_dirty_agent_worktree_is_reported_and_left_alone(gsa, repo, monkeypatch, capsys):
    wt = _agent_worktree(repo, "a1", "feat/x")
    (wt / "a.txt").write_text("unsaved\n")

    out = _run_cleanup(gsa, monkeypatch, repo, [_merged("feat/x", 179)], assume_yes=True, capsys=capsys)

    assert wt.is_dir()
    assert {"feat/x", "worktree-agent-a1"} <= _branches(repo), out
    assert "uncommitted changes" in out


def test_a_worktree_outside_claude_worktrees_stays_excluded(gsa, repo, monkeypatch, capsys):
    mine = repo.parent / "my-worktree"
    _git(repo, "worktree", "add", "-q", "-b", "feat/mine", str(mine), "main")

    out = _run_cleanup(gsa, monkeypatch, repo, [_merged("feat/mine", 12)], assume_yes=True, capsys=capsys)

    assert mine.is_dir()
    assert "feat/mine" in _branches(repo), out


def test_the_base_branch_of_an_agent_still_at_work_is_kept(gsa, repo, monkeypatch, capsys):
    wt = _agent_worktree(repo, "b2", "feat/open")

    out = _run_cleanup(gsa, monkeypatch, repo, [], assume_yes=True, capsys=capsys)

    assert wt.is_dir()
    assert {"feat/open", "worktree-agent-b2"} <= _branches(repo), out
    assert "worktree-agent-b2" not in out, "must not even be listed as a candidate"


def test_an_orphan_base_branch_is_deleted_only_when_merged(gsa, repo, monkeypatch, capsys):
    _git(repo, "branch", "worktree-agent-c3", "main")
    _git(repo, "switch", "-q", "-c", "worktree-agent-d4")
    (repo / "d.txt").write_text("unmerged\n")
    _git(repo, "add", "d.txt")
    _git(repo, "commit", "-q", "-m", "unmerged")
    _git(repo, "switch", "-q", "main")

    out = _run_cleanup(gsa, monkeypatch, repo, [], assume_yes=True, capsys=capsys)

    branches = _branches(repo)
    assert "worktree-agent-c3" not in branches, out
    assert "worktree-agent-d4" in branches, out
