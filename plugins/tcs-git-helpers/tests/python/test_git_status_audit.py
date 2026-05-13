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
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

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
# Drift-check stub for tests that call cmd_cleanup but don't test drift logic
# ---------------------------------------------------------------------------

class _OKStatus:
    """Minimal status stub whose .value compares equal to "OK"."""
    value = "OK"


class _OKDriftResult:
    """Stub DriftResult that passes the drift gate in cmd_cleanup."""
    status = _OKStatus()
    installed_version = "h1"


def _ok_drift(*_args, **_kwargs) -> _OKDriftResult:
    """Drop-in replacement for check_hook_bundle that always returns OK."""
    return _OKDriftResult()

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
        brief_line = lines[0]
        assert brief_line.startswith("[tcs-git-helpers] "), (
            f"expected SDD prefix, got: {brief_line!r}"
        )
        assert brief_line.count(" • ") >= 3, (
            f"expected ≥4 segments (3 separators), got: {brief_line!r}"
        )
        parts = brief_line.split(" • ")
        assert re.search(r"\d+ stale-merged", parts[3]), (
            f"4th segment must contain stale-merged count, got: {parts[3]!r}"
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
        monkeypatch.setattr(gsa, "check_hook_bundle", _ok_drift)

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

        monkeypatch.setattr(gsa, "check_hook_bundle", _ok_drift)

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
        Drift gate is patched to OK so this test stays focused on the schema.
        """
        repo_path = "/fake/repo/path"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        # Patch drift check to OK so this test focuses on JSON schema, not drift
        monkeypatch.setattr(gsa, "check_hook_bundle", _ok_drift)

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
        non_empty = [line for line in output_lines if line.strip()]

        # Must include a header/summary line + at most 3 event lines
        # Count event lines: lines referencing the branch names of the last 3
        event_count = sum(
            1 for line in non_empty
            if any(f"feat/branch-{i}" in line for i in range(2, 5))
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


# ===========================================================================
# Tests for _fetch_merged_prs failure branches (fail-open contract)
# ===========================================================================

class TestFetchMergedPRsFailures:
    """Verify _fetch_merged_prs is fail-open under timeout, auth missing, and no GitHub remote."""

    def _make_gh_error_result(self, returncode: int, stderr: str) -> MagicMock:
        m = MagicMock()
        m.returncode = returncode
        m.stdout = ""
        m.stderr = stderr
        return m

    def test_fetch_returns_empty_on_timeout(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When subprocess.run raises TimeoutExpired, _fetch_merged_prs must return []
        and cmd_cleanup must exit 0 (fail-open).
        """
        repo_path = "/fake/repo/timeout"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                raise subprocess.TimeoutExpired(cmd=[], timeout=5)
            # git calls: succeed normally
            if "symbolic-ref" in cmd:
                return _git_result("feat/some-branch")
            if "for-each-ref" in cmd:
                return _git_result("feat/some-branch\nmain")
            if "worktree" in cmd:
                return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        result = gsa._fetch_merged_prs(repo_path)
        assert result == [], f"Expected [] on timeout, got {result!r}"

        # Also verify cmd_cleanup is fail-open (no SystemExit)
        _write_stale_cache(cache_dir, repo_path, "main", [])
        monkeypatch.setattr(gsa, "check_hook_bundle", _ok_drift)
        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))
        try:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)
        except SystemExit as exc:
            pytest.fail(f"cmd_cleanup raised SystemExit({exc.code}) on timeout — must be fail-open")

    def test_fetch_returns_empty_on_auth_missing(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When gh exits with returncode=4 (auth missing), _fetch_merged_prs must return []
        and cmd_cleanup must exit 0 (fail-open).
        """
        repo_path = "/fake/repo/auth-missing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                return self._make_gh_error_result(returncode=4, stderr="gh auth login")
            if "for-each-ref" in cmd:
                return _git_result("feat/some-branch\nmain")
            if "worktree" in cmd:
                return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        result = gsa._fetch_merged_prs(repo_path)
        assert result == [], f"Expected [] on auth missing (rc=4), got {result!r}"

        _write_stale_cache(cache_dir, repo_path, "main", [])
        monkeypatch.setattr(gsa, "check_hook_bundle", _ok_drift)
        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))
        try:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)
        except SystemExit as exc:
            pytest.fail(f"cmd_cleanup raised SystemExit({exc.code}) on auth missing — must be fail-open")

    def test_fetch_returns_empty_on_no_github_remote(
        self, gsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When gh reports 'no GitHub remote', _fetch_merged_prs must silently return []
        and cmd_cleanup must exit 0 (fail-open).
        """
        repo_path = "/fake/repo/no-remote"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                return self._make_gh_error_result(returncode=1, stderr="no GitHub remote")
            if "for-each-ref" in cmd:
                return _git_result("feat/some-branch\nmain")
            if "worktree" in cmd:
                return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        result = gsa._fetch_merged_prs(repo_path)
        assert result == [], f"Expected [] on no GitHub remote, got {result!r}"

        _write_stale_cache(cache_dir, repo_path, "main", [])
        monkeypatch.setattr(gsa, "check_hook_bundle", _ok_drift)
        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))
        try:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)
        except SystemExit as exc:
            pytest.fail(f"cmd_cleanup raised SystemExit({exc.code}) on no GitHub remote — must be fail-open")


# ===========================================================================
# Tests for T2.3: cmd_cleanup drift gate + live refresh
# ===========================================================================

class TestCleanupDriftGate:
    """
    Verify that cmd_cleanup performs drift check first, then refresh_stale_cache
    on OK, with correct error paths and fallback behavior.

    T2.3 spec: PRD/AC-F2.1 — --cleanup must reflect live git/gh reality.
    """

    def _setup_cache(self, cache_dir: Path, repo_path: str) -> None:
        """Seed a non-empty cache so fallback tests can verify it is used."""
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

    def _make_drift_result(self, dc_mod, status_name: str, installed: str | None):
        """Build a DriftResult using the drift_check module's types."""
        status = dc_mod.DriftStatus[status_name]
        return dc_mod.DriftResult(status=status, installed_version=installed)

    def _capture_print(self, monkeypatch, output_lines, stderr_lines):
        """
        Patch builtins.print to route file=sys.stderr calls to stderr_lines
        and all other calls to output_lines. Avoids the silent-capture issue
        where file=sys.stderr is swallowed into output_lines by a naive lambda.
        """
        import sys as _sys

        def _fake_print(*args, sep=" ", end="\n", file=None, flush=False):
            s = sep.join(str(a) for a in args)
            if file is _sys.stderr:
                stderr_lines.append(s)
            else:
                output_lines.append(s)

        monkeypatch.setattr("builtins.print", _fake_print)

    # ------------------------------------------------------------------
    # Helper: load drift_check module for building fixture objects
    # ------------------------------------------------------------------
    @pytest.fixture(scope="class")
    def dc(self):
        import sys
        _LIB_PATH = Path(__file__).parent.parent.parent / "scripts" / "lib" / "drift_check.py"
        spec = importlib.util.spec_from_file_location("drift_check_t23", _LIB_PATH)
        mod = importlib.util.module_from_spec(spec)
        # Register before exec so @dataclass can resolve forward-reference annotations
        # (Python 3.14 + from __future__ import annotations requires module in sys.modules)
        sys.modules["drift_check_t23"] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            del sys.modules["drift_check_t23"]
            raise
        return mod

    # ------------------------------------------------------------------
    # 1. MISSING — version file absent → exit 1, no gh call
    # ------------------------------------------------------------------
    def test_drift_missing_exits_1_no_gh_call(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When hook bundle version file is absent, cmd_cleanup must exit 1
        with a stderr message containing 'hooks not installed', and must NOT
        invoke any gh command.
        """
        repo_path = "/fake/repo/drift-missing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._setup_cache(cache_dir, repo_path)

        missing_result = self._make_drift_result(dc, "MISSING", None)
        gh_calls: list = []

        def fake_check_hook_bundle(rp, ver):
            return missing_result

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                gh_calls.append(cmd)
            return _git_result("")

        monkeypatch.setattr(gsa, "check_hook_bundle", fake_check_hook_bundle)
        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)

        assert exc_info.value.code == 1, (
            f"Expected exit 1 for MISSING drift, got {exc_info.value.code}"
        )
        combined_stderr = "\n".join(stderr_lines)
        assert "hooks not installed" in combined_stderr, (
            f"Expected 'hooks not installed' in stderr, got:\n{combined_stderr}"
        )
        assert gh_calls == [], (
            f"Expected no gh calls on MISSING drift, got: {gh_calls}"
        )

    # ------------------------------------------------------------------
    # 2. DRIFT — installed != expected → exit 1, both versions in stderr
    # ------------------------------------------------------------------
    def test_drift_version_mismatch_exits_1_no_gh_call(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When installed version != expected, cmd_cleanup must exit 1.
        stderr must contain both the installed and expected version strings,
        and a /tcs-git-helpers:git-setup suggestion.
        No gh call must be attempted.
        """
        repo_path = "/fake/repo/drift-version"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._setup_cache(cache_dir, repo_path)

        drift_result = self._make_drift_result(dc, "DRIFT", "h0")
        gh_calls: list = []

        def fake_check_hook_bundle(rp, ver):
            return drift_result

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                gh_calls.append(cmd)
            return _git_result("")

        monkeypatch.setattr(gsa, "check_hook_bundle", fake_check_hook_bundle)
        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)

        assert exc_info.value.code == 1, (
            f"Expected exit 1 for DRIFT, got {exc_info.value.code}"
        )
        combined_stderr = "\n".join(stderr_lines)
        assert "h0" in combined_stderr, (
            f"Expected installed version 'h0' in stderr:\n{combined_stderr}"
        )
        assert "h1" in combined_stderr, (
            f"Expected expected version 'h1' in stderr:\n{combined_stderr}"
        )
        assert "/tcs-git-helpers:git-setup" in combined_stderr, (
            f"Expected /tcs-git-helpers:git-setup suggestion in stderr:\n{combined_stderr}"
        )
        assert gh_calls == [], (
            f"Expected no gh calls on DRIFT, got: {gh_calls}"
        )

    # ------------------------------------------------------------------
    # 3. OK — refresh_stale_cache called exactly once before cache read
    # ------------------------------------------------------------------
    def test_ok_drift_calls_refresh_exactly_once(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When drift check returns OK and gh is available, refresh_stale_cache
        must be called exactly once before the cache read.
        """
        repo_path = "/fake/repo/drift-ok"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._setup_cache(cache_dir, repo_path)

        ok_result = self._make_drift_result(dc, "OK", "h1")
        refresh_calls: list = []

        def fake_check_hook_bundle(rp, ver):
            return ok_result

        def fake_refresh(*, cache_dir, repo_path, default_branch="main"):
            refresh_calls.append((cache_dir, repo_path))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "for-each-ref" in cmd:
                    return _git_result("feat/old-thing\nfix/another-thing\nmain")
                if "worktree" in cmd and "list" in cmd:
                    return _git_result("")
            # gh is "available": `gh --version` returns exit 0
            if cmd[0] == "gh" and "--version" in cmd:
                return _git_result("gh version 2.0.0")
            # gh is authenticated: `gh auth status` returns exit 0
            if cmd[0] == "gh" and "auth" in cmd and "status" in cmd:
                return _git_result("", returncode=0)
            return _git_result("")

        monkeypatch.setattr(gsa, "check_hook_bundle", fake_check_hook_bundle)
        monkeypatch.setattr(gsa, "refresh_stale_cache", fake_refresh)
        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)

        assert len(refresh_calls) == 1, (
            f"Expected refresh_stale_cache called once, got {len(refresh_calls)} calls"
        )

    # ------------------------------------------------------------------
    # 4. OK + gh unauthenticated → graceful fallback to existing cache
    # ------------------------------------------------------------------
    def test_ok_drift_gh_unauthenticated_falls_back_to_cache(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When drift=OK but gh is unauthenticated (rc=4 on the gh pr list call),
        refresh is attempted, fails gracefully, stderr explains, and the
        existing cache content is used (candidates are listed, not "none").
        """
        repo_path = "/fake/repo/drift-ok-auth"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._setup_cache(cache_dir, repo_path)

        ok_result = self._make_drift_result(dc, "OK", "h1")
        refresh_calls: list = []

        def fake_check_hook_bundle(rp, ver):
            return ok_result

        def fake_refresh(*, cache_dir, repo_path, default_branch="main"):
            refresh_calls.append((cache_dir, repo_path))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                if "--version" in cmd:
                    m = MagicMock()
                    m.returncode = 0
                    m.stdout = "gh version 2.0.0"
                    m.stderr = ""
                    return m
                if "auth" in cmd and "status" in cmd:
                    # gh auth status returns non-zero when unauthenticated
                    m = MagicMock()
                    m.returncode = 1
                    m.stdout = ""
                    m.stderr = "You are not logged in"
                    return m
                return _git_result("")
            if cmd[0] == "git":
                if "for-each-ref" in cmd:
                    return _git_result("feat/old-thing\nfix/another-thing\nmain")
                if "worktree" in cmd and "list" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr(gsa, "check_hook_bundle", fake_check_hook_bundle)
        monkeypatch.setattr(gsa, "refresh_stale_cache", fake_refresh)
        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        # Must not raise SystemExit
        try:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)
        except SystemExit as exc:
            pytest.fail(f"cmd_cleanup raised SystemExit({exc.code}) on unauthenticated gh — must be fail-open")

        # Preflight contract: refresh_stale_cache must NOT be called when gh is unauthenticated
        assert len(refresh_calls) == 0, (
            f"Expected preflight to gate refresh (not called), but got {len(refresh_calls)} calls"
        )

        combined_stderr = "\n".join(stderr_lines)
        assert "unauthenticated" in combined_stderr.lower() or "falling back" in combined_stderr.lower(), (
            f"Expected unauthenticated/fallback explanation in stderr:\n{combined_stderr}"
        )

        # Cache content must still be shown (not silent "none")
        combined_output = "\n".join(output_lines)
        assert "feat/old-thing" in combined_output or "fix/another-thing" in combined_output, (
            f"Expected cached candidates in output on fallback, got:\n{combined_output}"
        )

    # ------------------------------------------------------------------
    # 5. OK + gh not installed → graceful fallback to existing cache
    # ------------------------------------------------------------------
    def test_ok_drift_gh_not_installed_falls_back_to_cache(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        When drift=OK but gh is not installed (OSError on subprocess.run),
        refresh is skipped, stderr explains, and existing cache content is used.
        """
        repo_path = "/fake/repo/drift-ok-nogh"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._setup_cache(cache_dir, repo_path)

        ok_result = self._make_drift_result(dc, "OK", "h1")

        def fake_check_hook_bundle(rp, ver):
            return ok_result

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh":
                raise OSError("gh not found")
            if cmd[0] == "git":
                if "for-each-ref" in cmd:
                    return _git_result("feat/old-thing\nfix/another-thing\nmain")
                if "worktree" in cmd and "list" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr(gsa, "check_hook_bundle", fake_check_hook_bundle)
        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        try:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)
        except SystemExit as exc:
            pytest.fail(f"cmd_cleanup raised SystemExit({exc.code}) on gh-not-installed — must be fail-open")

        combined_stderr = "\n".join(stderr_lines)
        assert "gh" in combined_stderr.lower() or "not installed" in combined_stderr.lower() or "not found" in combined_stderr.lower(), (
            f"Expected gh-not-installed explanation in stderr:\n{combined_stderr}"
        )

        # Cache content must still be shown
        combined_output = "\n".join(output_lines)
        assert "feat/old-thing" in combined_output or "fix/another-thing" in combined_output, (
            f"Expected cached candidates in output on fallback, got:\n{combined_output}"
        )

    # ------------------------------------------------------------------
    # 6. Pre-existing interactive prompt + delete path preserved end-to-end
    # ------------------------------------------------------------------
    def test_ok_drift_interactive_prompt_preserved(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        With drift=OK and a non-empty cache, the interactive prompt + delete
        path must be preserved. When user answers 'y', git branch -d is called.
        """
        repo_path = "/fake/repo/drift-ok-interactive"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        self._setup_cache(cache_dir, repo_path)

        ok_result = self._make_drift_result(dc, "OK", "h1")
        git_delete_calls: list = []

        def fake_check_hook_bundle(rp, ver):
            return ok_result

        def fake_refresh(*, cache_dir, repo_path, default_branch="main"):
            # No-op: do not overwrite cache; candidates from pre-seeded cache
            pass

        def fake_run(cmd, **kwargs):
            if cmd[0] == "gh" and "--version" in cmd:
                m = MagicMock()
                m.returncode = 0
                m.stdout = "gh version 2.0.0"
                m.stderr = ""
                return m
            if cmd[0] == "gh" and "auth" in cmd and "status" in cmd:
                return _git_result("", returncode=0)
            if cmd[0] == "git":
                if "for-each-ref" in cmd:
                    return _git_result("feat/old-thing\nfix/another-thing\nmain")
                if "worktree" in cmd and "list" in cmd:
                    return _git_result("")
                if "branch" in cmd and "-d" in cmd:
                    git_delete_calls.append(cmd)
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr(gsa, "check_hook_bundle", fake_check_hook_bundle)
        monkeypatch.setattr(gsa, "refresh_stale_cache", fake_refresh)
        monkeypatch.setattr("subprocess.run", fake_run)

        # Simulate user answering 'y' to first branch, 'n' to second
        answers = iter(["y", "n"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=True)

        # git branch -d must have been called for the 'y' answer
        assert len(git_delete_calls) >= 1, (
            f"Expected at least one 'git branch -d' call, got: {git_delete_calls}"
        )


# ===========================================================================
# Tests for lazy drift_check loading (updated for T2.4)
# ===========================================================================

class TestLazyDriftCheckLoad:
    """
    Verify lazy drift_check loading behavior after T2.4 wiring.

    Post-T2.4 contract:
    - cmd_brief, cmd_json: NOW call _ensure_drift_check_loaded via _drift_gate.
      When drift_check.py is absent they exit(2) with a clear message.
    - cmd_overrides: still does NOT load drift_check — must succeed when absent.
    """

    def _make_module_with_broken_load(self, monkeypatch):
        """
        Return a freshly loaded gsa module with _load_drift_check patched to
        raise FileNotFoundError — simulating a missing drift_check.py.
        """
        import importlib
        import importlib.util

        spec = importlib.util.spec_from_file_location("git_status_audit_lazy", _MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Patch _load_drift_check on the freshly loaded module to always fail
        def broken_load():
            raise FileNotFoundError("drift_check.py not found (simulated)")

        monkeypatch.setattr(mod, "_load_drift_check", broken_load)
        # Reset lazy state so any _ensure_drift_check_loaded() call would attempt to load
        mod._drift_check_mod = None
        mod.check_hook_bundle = None
        mod.DriftStatus = None
        return mod

    def test_cmd_brief_exits_2_when_drift_check_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_brief calls _ensure_drift_check_loaded (via _drift_gate silent).
        When drift_check.py is absent the module must exit(2) with a clear
        error message — not silently succeed. This guards against accidental
        removal of the drift dependency.
        """
        mod = self._make_module_with_broken_load(monkeypatch)
        repo_path = "/fake/repo/lazy-brief"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        stderr_lines: list[str] = []

        import sys as _sys

        def _fake_print(*args, sep=" ", end="\n", file=None, flush=False):
            s = sep.join(str(a) for a in args)
            if file is _sys.stderr:
                stderr_lines.append(s)

        monkeypatch.setattr("builtins.print", _fake_print)
        monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: _git_result(""))

        with pytest.raises(SystemExit) as exc_info:
            mod.cmd_brief(cache_dir=cache_dir, repo_path=repo_path)

        assert exc_info.value.code == 2, (
            f"Expected exit(2) when drift_check.py is missing, got {exc_info.value.code}"
        )
        combined_stderr = "\n".join(stderr_lines)
        assert "drift_check.py" in combined_stderr or "Reinstall" in combined_stderr, (
            f"Expected clear error message, got: {combined_stderr!r}"
        )

    def test_cmd_json_exits_2_when_drift_check_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_json calls _ensure_drift_check_loaded (via _drift_gate non-silent).
        When drift_check.py is absent the module must exit(2).
        """
        mod = self._make_module_with_broken_load(monkeypatch)
        repo_path = "/fake/repo/lazy-json"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

        with pytest.raises(SystemExit) as exc_info:
            mod.cmd_json(cache_dir=cache_dir, repo_path=repo_path)

        assert exc_info.value.code == 2, (
            f"Expected exit(2) when drift_check.py is missing, got {exc_info.value.code}"
        )

    def test_cmd_overrides_succeeds_without_drift_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """cmd_overrides must complete normally when drift_check.py is absent."""
        mod = self._make_module_with_broken_load(monkeypatch)
        repo_path = "/fake/repo/lazy-overrides"
        plugin_data = tmp_path / "plugin_data"
        (plugin_data / "audit").mkdir(parents=True)
        # No overrides.jsonl — exercises the "no overrides recorded yet" path

        monkeypatch.setattr("builtins.print", lambda s="", **_: None)

        mod.cmd_overrides(repo_path=repo_path, limit=20, plugin_data_dir=plugin_data)


# ===========================================================================
# Tests for T2.4: _drift_gate wired into cmd_default, cmd_brief, cmd_json
# ===========================================================================

class TestDriftGateAllModes:
    """
    T2.4: Verify _drift_gate is correctly wired into cmd_default (non-silent),
    cmd_brief (silent/fall-open), cmd_json (non-silent), and that cmd_overrides
    remains completely isolated from drift checks.

    CON-5: cmd_brief falls open on drift (SessionStart must not block).
    """

    def _make_drift_result(self, dc_mod, status_name: str, installed: str | None):
        status = dc_mod.DriftStatus[status_name]
        return dc_mod.DriftResult(status=status, installed_version=installed)

    def _capture_print(self, monkeypatch, output_lines, stderr_lines):
        import sys as _sys

        def _fake_print(*args, sep=" ", end="\n", file=None, flush=False):
            s = sep.join(str(a) for a in args)
            if file is _sys.stderr:
                stderr_lines.append(s)
            else:
                output_lines.append(s)

        monkeypatch.setattr("builtins.print", _fake_print)

    @pytest.fixture(scope="class")
    def dc(self):
        import sys
        _LIB_PATH = Path(__file__).parent.parent.parent / "scripts" / "lib" / "drift_check.py"
        spec = importlib.util.spec_from_file_location("drift_check_t24", _LIB_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["drift_check_t24"] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            del sys.modules["drift_check_t24"]
            raise
        return mod

    # ------------------------------------------------------------------
    # cmd_default: MISSING → exit 1, message contains 'hooks not installed'
    # ------------------------------------------------------------------

    def test_cmd_default_missing_exits_1_with_message(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_default with MISSING drift must exit 1 with a stderr message
        containing 'hooks not installed'.
        """
        repo_path = "/fake/repo/default-missing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        missing_result = self._make_drift_result(dc, "MISSING", None)
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: missing_result)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_default(cache_dir=cache_dir, repo_path=repo_path)

        assert exc_info.value.code == 1
        combined_stderr = "\n".join(stderr_lines)
        assert "hooks not installed" in combined_stderr, (
            f"Expected 'hooks not installed' in stderr:\n{combined_stderr}"
        )

    def test_cmd_default_drift_exits_1_with_versions(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_default with DRIFT must exit 1; stderr contains installed version,
        expected version, and /tcs-git-helpers:git-setup suggestion.
        """
        repo_path = "/fake/repo/default-drift"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        drift_result = self._make_drift_result(dc, "DRIFT", "h0")
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: drift_result)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_default(cache_dir=cache_dir, repo_path=repo_path)

        assert exc_info.value.code == 1
        combined_stderr = "\n".join(stderr_lines)
        assert "h0" in combined_stderr
        assert "/tcs-git-helpers:git-setup" in combined_stderr

    def test_cmd_default_ok_produces_output(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_default with OK drift must not exit and must produce output.
        """
        repo_path = "/fake/repo/default-ok"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        ok_result = self._make_drift_result(dc, "OK", "h1")
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: ok_result)

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "symbolic-ref" in cmd:
                    return _git_result("feat/my-feature")
                if "status" in cmd and "--porcelain" in cmd:
                    return _git_result("")
                if "rev-list" in cmd:
                    return _git_result("0\n0")
                if "for-each-ref" in cmd:
                    return _git_result("feat/my-feature\nmain")
                if "worktree" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_default(cache_dir=cache_dir, repo_path=repo_path)

        assert output_lines, "cmd_default must produce output on OK drift"

    # ------------------------------------------------------------------
    # cmd_brief: MISSING → fall open, show '0 stale-merged', no exit
    # ------------------------------------------------------------------

    def test_cmd_brief_missing_falls_open_shows_zero_stale(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_brief with MISSING drift must NOT exit. CON-5: SessionStart is not
        the drift surface. The stale-count segment must show '0 stale-merged'
        when drift is not OK (fall-open / safe default).
        """
        repo_path = "/fake/repo/brief-missing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # Cache has entries but drift is MISSING → stale count must be 0
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        missing_result = self._make_drift_result(dc, "MISSING", None)
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: missing_result)

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "symbolic-ref" in cmd:
                    return _git_result("feat/my-feature")
                if "status" in cmd and "--porcelain" in cmd:
                    return _git_result("")
                if "rev-list" in cmd:
                    return _git_result("0\n0")
                if "for-each-ref" in cmd:
                    return _git_result("feat/my-feature\nmain")
                if "worktree" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        # Must not raise SystemExit
        try:
            gsa.cmd_brief(cache_dir=cache_dir, repo_path=repo_path)
        except SystemExit as exc:
            pytest.fail(f"cmd_brief raised SystemExit({exc.code}) on MISSING drift — must fall open per CON-5")

        assert output_lines, "cmd_brief must still produce output on MISSING drift"
        brief_line = output_lines[0]
        parts = brief_line.split(" • ")
        assert len(parts) >= 4, f"Expected ≥4 segments, got: {brief_line!r}"
        assert "0 stale-merged" in parts[3], (
            f"On MISSING drift, stale-count segment must be '0 stale-merged', got: {parts[3]!r}"
        )

    def test_cmd_brief_ok_shows_real_stale_count(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_brief with OK drift must show the real stale count from cache.
        """
        repo_path = "/fake/repo/brief-ok"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        ok_result = self._make_drift_result(dc, "OK", "h1")
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: ok_result)

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git":
                if "symbolic-ref" in cmd:
                    return _git_result("feat/my-feature")
                if "status" in cmd and "--porcelain" in cmd:
                    return _git_result("")
                if "rev-list" in cmd:
                    return _git_result("0\n0")
                if "for-each-ref" in cmd:
                    return _git_result("feat/my-feature\nmain")
                if "worktree" in cmd:
                    return _git_result("")
            return _git_result("")

        monkeypatch.setattr("subprocess.run", fake_run)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_brief(cache_dir=cache_dir, repo_path=repo_path)

        assert output_lines, "cmd_brief must produce output"
        brief_line = output_lines[0]
        parts = brief_line.split(" • ")
        assert len(parts) >= 4
        assert f"{len(STALE_ENTRIES)} stale-merged" in parts[3], (
            f"On OK drift, stale-count must show {len(STALE_ENTRIES)}, got: {parts[3]!r}"
        )

    # ------------------------------------------------------------------
    # cmd_json: MISSING → exit 1; DRIFT → exit 1; OK → produces JSON
    # ------------------------------------------------------------------

    def test_cmd_json_missing_exits_1(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_json with MISSING drift must exit 1 with a stderr message.
        """
        repo_path = "/fake/repo/json-missing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        missing_result = self._make_drift_result(dc, "MISSING", None)
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: missing_result)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_json(cache_dir=cache_dir, repo_path=repo_path)

        assert exc_info.value.code == 1
        combined_stderr = "\n".join(stderr_lines)
        assert "hooks not installed" in combined_stderr, (
            f"Expected 'hooks not installed' in stderr:\n{combined_stderr}"
        )

    def test_cmd_json_drift_exits_1(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_json with DRIFT must exit 1 and mention installed/expected versions.
        """
        repo_path = "/fake/repo/json-drift"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        drift_result = self._make_drift_result(dc, "DRIFT", "h0")
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: drift_result)

        output_lines: list[str] = []
        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, output_lines, stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_json(cache_dir=cache_dir, repo_path=repo_path)

        assert exc_info.value.code == 1
        combined_stderr = "\n".join(stderr_lines)
        assert "h0" in combined_stderr

    def test_cmd_json_ok_emits_valid_json(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_json with OK drift must not exit and must emit valid JSON.
        """
        repo_path = "/fake/repo/json-ok"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", STALE_ENTRIES)

        ok_result = self._make_drift_result(dc, "OK", "h1")
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: ok_result)

        output_lines: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s="", **_: output_lines.append(s))

        gsa.cmd_json(cache_dir=cache_dir, repo_path=repo_path)

        combined = "\n".join(output_lines)
        data = json.loads(combined)
        assert "stale_branches" in data

    # ------------------------------------------------------------------
    # cmd_overrides: drift check NOT performed (isolation test)
    # ------------------------------------------------------------------

    def test_cmd_overrides_no_drift_check(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        cmd_overrides must NOT call check_hook_bundle — this mode does not
        depend on hook state.
        """
        repo_path = "/fake/repo/overrides-isolation"
        plugin_data = tmp_path / "plugin_data"
        (plugin_data / "audit").mkdir(parents=True)

        drift_calls: list = []

        def spy_check_hook_bundle(rp, ver):
            drift_calls.append((rp, ver))
            return self._make_drift_result(dc, "OK", "h1")

        monkeypatch.setattr(gsa, "check_hook_bundle", spy_check_hook_bundle)
        monkeypatch.setattr("builtins.print", lambda s="", **_: None)

        gsa.cmd_overrides(repo_path=repo_path, limit=20, plugin_data_dir=plugin_data)

        assert drift_calls == [], (
            f"cmd_overrides must NOT call check_hook_bundle, but got calls: {drift_calls}"
        )

    # ------------------------------------------------------------------
    # cmd_cleanup refactored to use _drift_gate: re-verify MISSING/DRIFT
    # still exit 1 (regression guard after _drift_gate refactor in T2.4)
    # ------------------------------------------------------------------

    def test_cmd_cleanup_still_exits_1_on_missing_after_refactor(
        self, gsa, dc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        After refactoring cmd_cleanup to use _drift_gate, MISSING drift must
        still exit 1 — regression guard.
        """
        repo_path = "/fake/repo/cleanup-refactor-missing"
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        _write_stale_cache(cache_dir, repo_path, "main", [])

        missing_result = self._make_drift_result(dc, "MISSING", None)
        monkeypatch.setattr(gsa, "check_hook_bundle", lambda rp, ver: missing_result)

        stderr_lines: list[str] = []
        self._capture_print(monkeypatch, [], stderr_lines)

        with pytest.raises(SystemExit) as exc_info:
            gsa.cmd_cleanup(cache_dir=cache_dir, repo_path=repo_path, interactive=False)

        assert exc_info.value.code == 1
        assert "hooks not installed" in "\n".join(stderr_lines)
