"""
test_bundle_lifecycle.py — pytest end-to-end test for the bundle lifecycle.

Spec: spec-012 Phase 3, T3.3
Contract: install → merge (post-merge hook writes stale-cache) → cleanup
          (drift gate + branch listing) → drift mutation → drift re-run exits 1.

Primary flows (3 sub-tests matching SDD primary flows):
  1. test_post_merge_hook_writes_stale_cache
  2. test_cleanup_lists_stale_branches
  3. test_cleanup_detects_version_drift

Setup strategy:
  - Throwaway git repo in pytest tmp dir (no global state leak).
  - install_files.sh called directly to simulate /tcs-git-helpers:git-setup.
  - gh stub injected via PATH (GH_STUB_SCENARIO=stale-3-branches).
  - CLAUDE_PLUGIN_DATA set to a tmp dir so cache files land predictably.
  - post-merge hook driven by actual `git merge --no-ff` (fires the installed hook).

Constraints:
  - No monkeypatching of production code — this is end-to-end.
  - git_status_audit.py invoked as a subprocess (CLI contract surface).
  - GIT_CONFIG_GLOBAL=/dev/null + GIT_CONFIG_SYSTEM=/dev/null so host gpgsign
    does not bleed into throwaway commits.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repo-relative paths
# ---------------------------------------------------------------------------

_PLUGIN_ROOT = Path(__file__).parent.parent.parent  # plugins/tcs-git-helpers/
_REPO_ROOT = _PLUGIN_ROOT.parent.parent              # the-custom-startup/
_INSTALL_SCRIPT = _PLUGIN_ROOT / "skills" / "git-setup" / "lib" / "install_files.sh"
_GH_STUB_DIR = _PLUGIN_ROOT / "tests" / "fixtures" / "gh_stubs"
_AUDIT_SCRIPT = _PLUGIN_ROOT / "scripts" / "git_status_audit.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_hash(repo_path: str) -> str:
    """12-char SHA1 prefix — mirrors lib-bundle.sh `shasum | head -c 12`."""
    return hashlib.sha1(repo_path.encode()).hexdigest()[:12]


def _run(
    cmd: list[str],
    *,
    cwd: str | Path | None = None,
    env: dict | None = None,
    capture: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def _git_env(extra: dict | None = None) -> dict:
    """Base env that suppresses host gpgsign/hooksPath config."""
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    if extra:
        env.update(extra)
    return env


# ---------------------------------------------------------------------------
# Session-scoped fixture: build the throwaway repo once for all 3 tests.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bundle_repo(tmp_path_factory: pytest.TempPathFactory):
    """
    Set up a throwaway git repo with:
      - install_files.sh run (simulates git-setup skill)
      - A feature branch with one commit
      - git merge --no-ff feature-branch on main (fires post-merge hook)
      - CLAUDE_PLUGIN_DATA pointing to a tmp cache dir
      - gh stub on PATH returning stale-3-branches scenario

    Returns a dict with all paths and state needed by the 3 sub-tests.
    """
    work_dir = tmp_path_factory.mktemp("bundle-lifecycle", numbered=False)
    repo_dir = work_dir / "repo"
    plugin_data_dir = work_dir / "plugin-data"
    repo_dir.mkdir()
    plugin_data_dir.mkdir()

    # Stub PATH: gh stub directory prepended so `gh` resolves to our stub.
    stub_path = f"{_GH_STUB_DIR}:{os.environ.get('PATH', '/usr/bin:/bin')}"

    base_env = _git_env({
        "CLAUDE_PLUGIN_DATA": str(plugin_data_dir),
        "CLAUDE_PLUGIN_ROOT": str(_PLUGIN_ROOT),
        "PATH": stub_path,
        "GH_STUB_SCENARIO": "stale-3-branches",
    })

    # ------------------------------------------------------------------ #
    # 1. Init repo
    # ------------------------------------------------------------------ #
    _run(["git", "init", "-q", "-b", "main", str(repo_dir)], env=base_env)
    _run(["git", "config", "user.name", "tcs-fixture"], cwd=repo_dir, env=base_env)
    _run(["git", "config", "user.email", "fixture@tcs.invalid"], cwd=repo_dir, env=base_env)
    _run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, env=base_env)
    # Initial commit on main
    _run(
        ["git", "commit", "--allow-empty", "-q", "-m", "chore: init"],
        cwd=repo_dir, env=base_env,
    )

    # ------------------------------------------------------------------ #
    # 2. Create local branches matching the gh stub's merged-PR headRefNames.
    #    stale-3-branches scenario returns:
    #      feat/stale-a  (PR #38)
    #      fix/stale-b   (PR #40)
    #      chore/stale-c (PR #42)
    #      feat/not-local (not a local branch → excluded)
    # ------------------------------------------------------------------ #
    for branch in ("feat/stale-a", "fix/stale-b", "chore/stale-c"):
        _run(["git", "branch", branch], cwd=repo_dir, env=base_env)

    # ------------------------------------------------------------------ #
    # 3. Create a feature branch for the merge target.
    # ------------------------------------------------------------------ #
    _run(["git", "checkout", "-b", "feat/trigger-merge"], cwd=repo_dir, env=base_env)
    _run(
        ["git", "commit", "--allow-empty", "-q", "-m", "feat: trigger"],
        cwd=repo_dir, env=base_env,
    )
    _run(["git", "checkout", "main"], cwd=repo_dir, env=base_env)

    # ------------------------------------------------------------------ #
    # 4. Install via install_files.sh (simulates /tcs-git-helpers:git-setup)
    # ------------------------------------------------------------------ #
    install_env = base_env.copy()
    install_env["TCS_GIT_HELPERS_SETUP_ACTIVE"] = "1"

    install_result = _run(
        ["bash", str(_INSTALL_SCRIPT)],
        cwd=repo_dir,
        env=install_env,
    )
    assert install_result.returncode == 0, (
        f"install_files.sh failed:\n"
        f"stdout: {install_result.stdout}\n"
        f"stderr: {install_result.stderr}"
    )

    # Verify install landed.
    assert (repo_dir / ".githooks" / "post-merge").exists(), "post-merge hook missing"
    assert (repo_dir / ".githooks" / "lib-bundle.sh").exists(), "lib-bundle.sh missing"
    assert (repo_dir / ".githooks" / "tcs-git-helpers-version").exists(), "version file missing"

    # ------------------------------------------------------------------ #
    # 5. Fire the installed post-merge hook via a real `git merge --no-ff`.
    # ------------------------------------------------------------------ #
    merge_result = _run(
        ["git", "merge", "--no-ff", "-m", "Merge feat/trigger-merge", "feat/trigger-merge"],
        cwd=repo_dir,
        env=base_env,
    )
    assert merge_result.returncode == 0, (
        f"git merge failed:\n"
        f"stdout: {merge_result.stdout}\n"
        f"stderr: {merge_result.stderr}"
    )

    # Compute the repo_hash for asserting cache file names.
    # Use resolved path so it matches what `git rev-parse --show-toplevel`
    # returns inside the hook (macOS /tmp → /private/tmp symlink resolution).
    repo_path_str = str(repo_dir.resolve())
    # shasum produces hex; lib-bundle.sh uses: printf '%s' | shasum | head -c 12
    # shasum on macOS outputs "<hash>  -\n"; head -c 12 gets first 12 chars of hash.
    shasum_result = _run(
        ["bash", "-c", f"printf '%s' '{repo_path_str}' | shasum | head -c 12"],
        env=base_env,
    )
    assert shasum_result.returncode == 0
    hook_repo_hash = shasum_result.stdout.strip()

    # Python hash (for git_status_audit.py path helpers)
    python_repo_hash = _repo_hash(repo_path_str)

    return {
        "repo_dir": repo_dir,
        "plugin_data_dir": plugin_data_dir,
        "cache_dir": plugin_data_dir / "cache",
        "repo_path_str": repo_path_str,
        "hook_repo_hash": hook_repo_hash,
        "python_repo_hash": python_repo_hash,
        "base_env": base_env,
        "stub_path": stub_path,
    }


# ---------------------------------------------------------------------------
# Test 1: post-merge hook writes stale-cache files
# ---------------------------------------------------------------------------

def test_post_merge_hook_writes_stale_cache(bundle_repo):
    """
    After git merge --no-ff fires the installed post-merge hook, both
    <cache_dir>/<repo_hash>-stale-cache.{tsv,json} must exist and contain
    at least one of the stale branches the gh stub returns.

    Validates SDD Primary Flow: stale-cache write on post-merge.
    """
    ctx = bundle_repo
    cache_dir = ctx["cache_dir"]
    hook_repo_hash = ctx["hook_repo_hash"]

    tsv_path = cache_dir / f"{hook_repo_hash}-stale-cache.tsv"
    json_path = cache_dir / f"{hook_repo_hash}-stale-cache.json"

    assert cache_dir.exists(), (
        f"Cache dir was not created: {cache_dir}"
    )
    assert tsv_path.exists(), (
        f"TSV cache file missing: {tsv_path}\n"
        f"Cache dir contents: {list(cache_dir.iterdir()) if cache_dir.exists() else '<missing>'}"
    )
    assert json_path.exists(), (
        f"JSON cache file missing: {json_path}"
    )

    # TSV must contain at least one of the stale branch names.
    tsv_content = tsv_path.read_text()
    stale_branch_names = ("feat/stale-a", "fix/stale-b", "chore/stale-c")
    assert any(name in tsv_content for name in stale_branch_names), (
        f"TSV cache does not contain any expected stale branch.\n"
        f"TSV content:\n{tsv_content}"
    )

    # JSON must be parseable. Both lib-bundle.sh and scripts/lib/cache.sh write
    # `stale_branches` — the T1.2 regression used `entries`, which was invisible
    # to git_status_audit.py._read_stale_cache. T3.3 exposed and fixed this.
    json_content = json.loads(json_path.read_text())
    assert isinstance(json_content, dict), "JSON cache root must be an object"
    assert "stale_branches" in json_content, (
        f"JSON cache missing 'stale_branches' key (found keys: {list(json_content.keys())}). "
        f"The bundle writer must use 'stale_branches' to match the reader contract."
    )
    assert "entries" not in json_content, (
        f"JSON cache contains legacy 'entries' key — this is the T1.2 regression. "
        f"Use 'stale_branches' instead."
    )
    entries = json_content.get("stale_branches", [])
    entry_names = [e.get("name") for e in entries]
    assert any(name in entry_names for name in stale_branch_names), (
        f"JSON stale_branches do not contain expected stale branch.\n"
        f"stale_branches: {entries}"
    )


# ---------------------------------------------------------------------------
# Test 2: --cleanup lists stale branches non-interactively
# ---------------------------------------------------------------------------

def test_cleanup_lists_stale_branches(bundle_repo):
    """
    After the post-merge hook has written the cache, invoking
    git_status_audit.py --cleanup (non-interactive via stdin=subprocess.DEVNULL)
    must print at least one of the stale branch names to stdout.

    Validates SDD Primary Flow: skill drift-check on --cleanup.
    """
    ctx = bundle_repo

    result = _run(
        [sys.executable, str(_AUDIT_SCRIPT), "--cleanup"],
        cwd=ctx["repo_dir"],
        env=ctx["base_env"],
    )

    # --cleanup exits 0 when drift is OK.
    assert result.returncode == 0, (
        f"--cleanup exited {result.returncode}.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    stale_branch_names = ("feat/stale-a", "fix/stale-b", "chore/stale-c")
    assert any(name in result.stdout for name in stale_branch_names), (
        f"--cleanup stdout does not list any stale branch.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 3: --cleanup detects version drift (exit 1 + drift message)
# ---------------------------------------------------------------------------

def test_cleanup_detects_version_drift(bundle_repo):
    """
    After mutating .githooks/tcs-git-helpers-version to 'h999',
    git_status_audit.py --cleanup must:
      - exit 1
      - print a drift message to stderr containing 'h999'

    Validates SDD Primary Flow: hook-version drift detection on --cleanup.
    """
    ctx = bundle_repo
    version_file = ctx["repo_dir"] / ".githooks" / "tcs-git-helpers-version"

    # Mutate installed version.
    original_version = version_file.read_text().strip()
    version_file.write_text("h999\n")

    try:
        result = _run(
            [sys.executable, str(_AUDIT_SCRIPT), "--cleanup"],
            cwd=ctx["repo_dir"],
            env=ctx["base_env"],
        )

        assert result.returncode == 1, (
            f"Expected exit 1 for drift, got {result.returncode}.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "h999" in result.stderr, (
            f"Expected drift message with 'h999' in stderr.\n"
            f"stderr: {result.stderr}"
        )
    finally:
        # Restore version so subsequent test runs don't see stale state.
        version_file.write_text(original_version + "\n")


# ---------------------------------------------------------------------------
# Test 4: --cleanup falls back to post-merge cache when gh is unauthenticated
# ---------------------------------------------------------------------------

def test_cleanup_falls_back_to_post_merge_cache_when_gh_unauth(bundle_repo):
    """
    When gh reports 'not authenticated' (exit 4), --cleanup must fall back to
    the hook-written stale-cache and still list stale branch names.

    This exercises the hook→reader pipeline directly: the live refresh path is
    skipped, so the output comes solely from the cache written by post-merge.

    Validates SDD Fallback Flow: unauthenticated gh → cached state served.

    W1 coverage gap: the 3 authenticated tests always overwrite the cache via
    refresh_stale_cache, hiding whether the hook-written cache is readable.
    This test proves the contract without the refresh intermediary.
    """
    ctx = bundle_repo

    # Override GH_STUB_SCENARIO to no-auth so gh auth status returns exit 4.
    no_auth_env = ctx["base_env"].copy()
    no_auth_env["GH_STUB_SCENARIO"] = "no-auth"

    result = _run(
        [sys.executable, str(_AUDIT_SCRIPT), "--cleanup"],
        cwd=ctx["repo_dir"],
        env=no_auth_env,
    )

    # --cleanup exits 0 (fallback path, not a drift error).
    assert result.returncode == 0, (
        f"--cleanup (no-auth) exited {result.returncode}.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # A fallback warning must appear on stderr (either "gh CLI not found" or
    # "unauthenticated" — the no-auth stub exits 4 on all invocations including
    # `gh --version`, so _gh_available() returns False and "not found" is emitted).
    assert "falling back to cached state" in result.stderr, (
        f"Expected fallback warning in stderr.\n"
        f"stderr: {result.stderr}"
    )

    # Stale branches from the hook-written cache must appear in stdout.
    stale_branch_names = ("feat/stale-a", "fix/stale-b", "chore/stale-c")
    assert any(name in result.stdout for name in stale_branch_names), (
        f"--cleanup (no-auth) stdout does not list any stale branch from cache.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
