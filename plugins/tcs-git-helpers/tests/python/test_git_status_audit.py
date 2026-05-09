"""
test_git_status_audit.py — pytest suite for scripts/git_status_audit.py

TDD cycle: these tests are written RED first; they import from
scripts/git_status_audit.py which does not exist yet, so they will
fail with ImportError until the implementation is in place.

Test numbering matches the spec T3.1 requirement list:
  1. test_brief_mode_outputs_one_line_format
  2. test_brief_mode_warning_marker_on_protected_branch
  3. test_cleanup_mode_lists_stale_branches_with_pr_numbers
  4. test_cleanup_excludes_worktree_branches
  5. test_json_mode_outputs_valid_json_matching_schema
  6. test_overrides_mode_reads_jsonl_prints_last_n
  7. test_overrides_missing_file_exits_zero_with_message
  8. test_cache_write_produces_tsv_and_json_atomically
  9. test_batched_gh_pr_list_single_call_not_per_branch
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Dynamic import of git_status_audit (not installed; loaded by path)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
_MODULE_PATH = _SCRIPTS_DIR / "git_status_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("git_status_audit", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gsa():
    """Loaded git_status_audit module."""
    return _load_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_hash(repo_path: str) -> str:
    return hashlib.sha1(repo_path.encode()).hexdigest()[:12]


def _write_stale_cache(
    cache_dir: Path,
    repo_path: str,
    default_branch: str,
    entries: list[dict],
    updated_iso: str = "2026-05-09T14:23:11Z",
) -> None:
    """Write TSV + JSON stale cache for the given repo_path into cache_dir."""
    rh = _repo_hash(repo_path)
    tsv = cache_dir / f"{rh}-stale-cache.tsv"
    jsn = cache_dir / f"{rh}-stale-cache.json"

    lines = [
        "# tcs-git-helpers stale cache v1",
        f"# updated_iso={updated_iso}",
        f"# repo_path={repo_path}",
        f"# default_branch={default_branch}",
    ]
    for e in entries:
        lines.append(f"{e['name']}\t{e['pr_number']}\t{e['merged_at']}")
    tsv.write_text("\n".join(lines) + "\n")

    data = {
        "version": 1,
        "updated_iso": updated_iso,
        "repo_path": repo_path,
        "default_branch": default_branch,
        "stale_branches": list(entries),
    }
    jsn.write_text(json.dumps(data, indent=2))


STALE_ENTRIES = [
    {"name": "feat/old-thing", "pr_number": 38, "merged_at": "2026-04-12T10:00:00Z"},
    {"name": "fix/another-thing", "pr_number": 40, "merged_at": "2026-04-15T09:00:00Z"},
]

# ---------------------------------------------------------------------------
# Helper: make a synthetic git repo for worktree tests
# ---------------------------------------------------------------------------

def _make_git_repo(path: Path, branch: str = "feat/main-branch") -> None:
    """Create a minimal git repo at path on the given branch."""
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(["git", "init", "-b", branch, str(path)], check=True,
                   capture_output=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.invalid"],
                   check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True,
                   capture_output=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "commit.gpgsign", "false"],
                   check=True, capture_output=True, env=env)
    (path / "README.md").write_text("hello\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True,
                   capture_output=True, env=env)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True,
                   capture_output=True, env=env)


# ---------------------------------------------------------------------------
# Subprocess result factory
# ---------------------------------------------------------------------------

def _git_result(stdout: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = ""
    return m


def _gh_result(entries: list[dict] | None = None, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = json.dumps(entries or [])
    m.stderr = ""
    return m


# ===========================================================================
# Test 1: --brief outputs one-line format matching SDD wireframe
# ===========================================================================

class TestBriefMode:
    def test_brief_mode_outputs_one_line_format(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        --brief must emit exactly one line matching:
          [tcs-git-helpers] <branch> • <state> • <ahead/behind> • <stale-count>
        """
        repo_path = "/fake/repo/path"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        call_log: list[tuple] = []

        def fake_run(cmd, **kwargs):
            call_log.append(cmd)
            if cmd[0] == "git":
                if "rev-parse" in cmd and "--show-toplevel" in cmd:
                    return _git_result(repo_path)
                if "symbolic-ref" in cmd:
                    return _git_result("feat/my-feature")
                if "status" in cmd and "--porcelain" in cmd:
                    return _git_result("")
                if "rev-list" in cmd:
                    return _git_result("2\n0")
                # for-each-ref local branches
                if "for-each-ref" in cmd:
                    return _git_result("feat/old-thing\nfix/another-thing\nmain")
                if "worktree" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        lines: list[str] = []

        def fake_print(s: str = "", **_kw):
            lines.append(s)

        monkeypatch.setattr("builtins.print", fake_print)

        gsa.cmd_brief(cache_dir=cache_dir, repo_path=repo_path)

        assert len(lines) == 1, f"Expected exactly 1 line, got: {lines}"
        pattern = r"^\[tcs-git-helpers\] .+ • .+ • .+"
        assert re.match(pattern, lines[0]), (
            f"Brief line did not match wireframe pattern.\nGot: {lines[0]!r}"
        )

    def test_brief_mode_warning_marker_on_protected_branch(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When on main/master, the brief line must be prefixed with '⚠ '.
        """
        repo_path = "/fake/repo/path"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "rev-parse" in cmd and "--show-toplevel" in cmd:
                    return _git_result(repo_path)
                if "symbolic-ref" in cmd:
                    return _git_result("main")
                if "status" in cmd and "--porcelain" in cmd:
                    return _git_result("")
                if "rev-list" in cmd:
                    return _git_result("0\n0")
                if "for-each-ref" in cmd:
                    return _git_result("main")
                if "worktree" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: lines.append(s))

        gsa.cmd_brief(cache_dir=cache_dir, repo_path=repo_path)

        assert len(lines) == 1
        assert lines[0].startswith("⚠ "), (
            f"Expected '⚠ ' prefix for protected branch, got: {lines[0]!r}"
        )


# ===========================================================================
# Test 3: --cleanup lists stale branches with PR numbers
# ===========================================================================

class TestCleanupMode:
    def test_cleanup_mode_lists_stale_branches_with_pr_numbers(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        --cleanup must list stale branch names and PR numbers.
        """
        repo_path = "/fake/repo/path"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "rev-parse" in cmd and "--show-toplevel" in cmd:
                    return _git_result(repo_path)
                if "symbolic-ref" in cmd:
                    return _git_result("feat/current")
                # worktree list --porcelain
                if "worktree" in cmd and "list" in cmd:
                    return _git_result("worktree /fake/repo/path\nHEAD abc123\nbranch refs/heads/feat/current\n")
                # for-each-ref: local branches include stale ones
                if "for-each-ref" in cmd:
                    return _git_result(
                        "feat/old-thing\nfix/another-thing\nfeat/current\nmain"
                    )
            if cmd[0] == "gh":
                return _gh_result(
                    [
                        {"headRefName": "feat/old-thing", "number": 38, "mergedAt": "2026-04-12T10:00:00Z"},
                        {"headRefName": "fix/another-thing", "number": 40, "mergedAt": "2026-04-15T09:00:00Z"},
                    ]
                )
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)

        combined = "\n".join(output_lines)
        assert "feat/old-thing" in combined, f"Expected feat/old-thing in output:\n{combined}"
        assert "PR #38" in combined, f"Expected 'PR #38' in output:\n{combined}"
        assert "fix/another-thing" in combined
        assert "PR #40" in combined

    def test_cleanup_excludes_worktree_branches(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        A branch currently checked out in a worktree must NOT appear in cleanup candidates.
        PRD M6 AC3.
        """
        repo_path = "/fake/repo/path"
        worktree_path = "/fake/worktree/feat-old-thing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        worktree_porcelain = (
            f"worktree {repo_path}\n"
            "HEAD abc123\n"
            "branch refs/heads/feat/current\n"
            "\n"
            f"worktree {worktree_path}\n"
            "HEAD def456\n"
            "branch refs/heads/feat/old-thing\n"
        )

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "rev-parse" in cmd and "--show-toplevel" in cmd:
                    return _git_result(repo_path)
                if "symbolic-ref" in cmd:
                    return _git_result("feat/current")
                if "worktree" in cmd and "list" in cmd:
                    return _git_result(worktree_porcelain)
                if "for-each-ref" in cmd:
                    return _git_result(
                        "feat/old-thing\nfix/another-thing\nfeat/current\nmain"
                    )
            if cmd[0] == "gh":
                return _gh_result(
                    [
                        {"headRefName": "feat/old-thing", "number": 38, "mergedAt": "2026-04-12T10:00:00Z"},
                        {"headRefName": "fix/another-thing", "number": 40, "mergedAt": "2026-04-15T09:00:00Z"},
                    ]
                )
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)

        combined = "\n".join(output_lines)
        # feat/old-thing is in a worktree → must NOT appear
        assert "feat/old-thing" not in combined, (
            f"feat/old-thing is checked out in worktree and must be excluded.\nOutput:\n{combined}"
        )
        # fix/another-thing is NOT in a worktree → must appear
        assert "fix/another-thing" in combined, (
            f"fix/another-thing should be listed.\nOutput:\n{combined}"
        )


# ===========================================================================
# Test 5: --json outputs valid JSON matching schema
# ===========================================================================

class TestJsonMode:
    def test_json_mode_outputs_valid_json_matching_schema(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        --json must output a valid JSON object with the required schema fields.
        """
        repo_path = "/fake/repo/path"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "rev-parse" in cmd and "--show-toplevel" in cmd:
                    return _git_result(repo_path)
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_json(cache_dir=cache_dir, repo_path=repo_path)

        combined = "\n".join(output_lines)
        data = json.loads(combined)

        # Top-level keys
        assert data["version"] == 1
        assert "updated_iso" in data
        assert "repo_path" in data
        assert "default_branch" in data
        assert "stale_branches" in data
        assert isinstance(data["stale_branches"], list)

        # Per-entry schema
        for entry in data["stale_branches"]:
            assert "name" in entry
            assert "pr_number" in entry
            assert "merged_at" in entry

        # Verify data round-trips correctly
        assert len(data["stale_branches"]) == len(STALE_ENTRIES)
        assert data["stale_branches"][0]["name"] == "feat/old-thing"
        assert data["stale_branches"][0]["pr_number"] == 38


# ===========================================================================
# Test 6 & 7: --overrides mode
# ===========================================================================

class TestOverridesMode:
    def _make_overrides_jsonl(self, audit_dir: Path, repo_path: str, extra_repo: str) -> None:
        """
        Write 5 events for repo_path and 2 for extra_repo.
        """
        events = []
        for i in range(5):
            events.append({
                "ts": f"2026-05-0{i+1}T10:00:00Z",
                "repo": repo_path,
                "branch": f"feat/branch-{i}",
                "hook": "block-bad-git-ops",
                "env_var": "CLAUDE_ALLOW_RESET_HARD",
                "master": False,
                "command": f"git reset --hard HEAD~{i}",
                "pattern": "git reset --hard",
                "tool_input_truncated": False,
            })
        for j in range(2):
            events.append({
                "ts": f"2026-05-0{j+6}T10:00:00Z",
                "repo": extra_repo,
                "branch": "main",
                "hook": "block-bad-git-ops",
                "env_var": "CLAUDE_ALLOW_FORCE_PUSH",
                "master": False,
                "command": "git push --force",
                "pattern": "git push --force",
                "tool_input_truncated": False,
            })
        jsonl_path = audit_dir / "overrides.jsonl"
        jsonl_path.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    def test_overrides_mode_reads_jsonl_prints_last_n(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        --overrides --limit 3 must print exactly 3 (the last 3 for the current repo),
        in chronological order.
        """
        repo_path = "/fake/repo/my-repo"
        extra_repo = "/fake/repo/other-repo"
        plugin_data = tmp_path / "plugin_data"
        audit_dir = plugin_data / "audit"
        audit_dir.mkdir(parents=True)

        self._make_overrides_jsonl(audit_dir, repo_path, extra_repo)

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git" and "rev-parse" in cmd and "--show-toplevel" in cmd:
                return _git_result(repo_path)
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_overrides(repo_path=repo_path, limit=3, plugin_data_dir=plugin_data)

        # Filter to non-empty output lines
        non_empty = [l for l in output_lines if l.strip()]

        # Must include a header/summary line + at most 3 event lines
        # Count event lines: lines referencing the branch names of the last 3
        event_count = sum(
            1 for l in non_empty
            if any(f"feat/branch-{i}" in l for i in range(2, 5))
        )
        assert event_count == 3, (
            f"Expected 3 event lines for last-3 events, got {event_count}.\n"
            f"Output: {output_lines}"
        )

        # Must NOT include events from extra_repo
        combined = "\n".join(non_empty)
        assert extra_repo not in combined, (
            f"Events from other repo leaked into output:\n{combined}"
        )

    def test_overrides_missing_file_exits_zero_with_message(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When overrides.jsonl is missing, output 'no overrides recorded yet' and exit 0.
        """
        repo_path = "/fake/repo/my-repo"
        plugin_data = tmp_path / "plugin_data_missing"
        plugin_data.mkdir()
        (plugin_data / "audit").mkdir()
        # No overrides.jsonl created

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(plugin_data))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git" and "rev-parse" in cmd and "--show-toplevel" in cmd:
                return _git_result(repo_path)
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        # Must not raise SystemExit with non-zero code
        try:
            gsa.cmd_overrides(repo_path=repo_path, limit=20, plugin_data_dir=plugin_data)
        except SystemExit as e:
            pytest.fail(f"cmd_overrides raised SystemExit({e.code}) on missing file")

        combined = "\n".join(output_lines)
        assert "no overrides recorded yet" in combined.lower(), (
            f"Expected 'no overrides recorded yet' in output, got:\n{combined}"
        )


# ===========================================================================
# Test 8: cache write produces TSV and JSON atomically
# ===========================================================================

class TestCacheWrite:
    def test_cache_write_produces_tsv_and_json_atomically(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        write_stale_cache() must produce both .tsv and .json files.
        Both must contain the same logical data, and the TSV must be
        parseable by bash's head/grep pattern.
        """
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        repo_path = "/fake/atomic/repo"
        default_branch = "main"
        updated_iso = "2026-05-09T14:23:11Z"
        entries = [
            {"name": "feat/test-branch", "pr_number": 99, "merged_at": "2026-05-01T00:00:00Z"},
        ]

        gsa.write_stale_cache(
            cache_dir=cache_dir,
            repo_path=repo_path,
            default_branch=default_branch,
            updated_iso=updated_iso,
            entries=entries,
        )

        rh = hashlib.sha1(repo_path.encode()).hexdigest()[:12]
        tsv_path = cache_dir / f"{rh}-stale-cache.tsv"
        json_path = cache_dir / f"{rh}-stale-cache.json"

        assert tsv_path.exists(), "TSV cache file must exist"
        assert json_path.exists(), "JSON cache file must exist"

        # TSV structure
        tsv_content = tsv_path.read_text()
        assert "# tcs-git-helpers stale cache v1" in tsv_content
        assert f"# updated_iso={updated_iso}" in tsv_content
        assert f"# repo_path={repo_path}" in tsv_content
        assert f"# default_branch={default_branch}" in tsv_content
        assert "feat/test-branch\t99\t2026-05-01T00:00:00Z" in tsv_content

        # JSON structure
        data = json.loads(json_path.read_text())
        assert data["version"] == 1
        assert data["updated_iso"] == updated_iso
        assert data["repo_path"] == repo_path
        assert data["default_branch"] == default_branch
        assert len(data["stale_branches"]) == 1
        assert data["stale_branches"][0]["name"] == "feat/test-branch"
        assert data["stale_branches"][0]["pr_number"] == 99
        assert data["stale_branches"][0]["merged_at"] == "2026-05-01T00:00:00Z"

        # No .tmp files remain (atomic mv cleaned up)
        assert not (cache_dir / f"{rh}-stale-cache.tsv.tmp").exists()
        assert not (cache_dir / f"{rh}-stale-cache.json.tmp").exists()


# ===========================================================================
# Test 9: batched gh pr list — single call, not per-branch
# ===========================================================================

class TestBatchedGhCall:
    def test_batched_gh_pr_list_single_call_not_per_branch(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        refresh_stale_cache() (or the internal gh-call function) must make
        exactly ONE gh invocation matching 'pr list --state merged --limit 100',
        regardless of how many local branches exist.
        """
        repo_path = "/fake/repo/batched"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        default_branch = "main"

        # 10 local branches to verify no per-branch loop
        local_branches = [f"feat/branch-{i:02d}" for i in range(10)]

        gh_calls: list[list[str]] = []
        git_calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                gh_calls.append(list(cmd))
                return _gh_result(
                    [
                        {
                            "headRefName": "feat/branch-03",
                            "number": 53,
                            "mergedAt": "2026-04-10T00:00:00Z",
                        }
                    ]
                )
            if cmd[0] == "git":
                git_calls.append(list(cmd))
                if "rev-parse" in cmd and "--show-toplevel" in cmd:
                    return _git_result(repo_path)
                if "symbolic-ref" in cmd and "refs/remotes/origin/HEAD" in cmd:
                    return _git_result(f"refs/remotes/origin/{default_branch}")
                if "for-each-ref" in cmd:
                    return _git_result("\n".join(local_branches))
                if "worktree" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        gsa.refresh_stale_cache(
            cache_dir=cache_dir,
            repo_path=repo_path,
            default_branch=default_branch,
        )

        # Exactly one gh call
        assert len(gh_calls) == 1, (
            f"Expected exactly 1 gh call, got {len(gh_calls)}:\n{gh_calls}"
        )

        # That call must be the batched form
        gh_cmd_str = " ".join(gh_calls[0])
        assert "pr" in gh_cmd_str and "list" in gh_cmd_str, (
            f"gh call must be 'pr list', got: {gh_cmd_str}"
        )
        assert "--state" in gh_cmd_str and "merged" in gh_cmd_str, (
            f"gh call must use --state merged, got: {gh_cmd_str}"
        )
        assert "--limit" in gh_cmd_str, f"gh call must use --limit, got: {gh_cmd_str}"
