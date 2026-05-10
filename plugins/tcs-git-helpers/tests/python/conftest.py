"""
conftest.py — shared fixtures for git_status_audit.py pytest suite.

All fixtures use tmp_path (pytest-managed, avoids macOS sandbox mktemp issue).
The synthetic repo suite is session-scoped to avoid rebuilding 9 repos per test.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# Resolve the scripts directory relative to repo root so tests can import
# git_status_audit without installing it.
_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # the-custom-startup/
_SCRIPTS_DIR = _REPO_ROOT / "plugins" / "tcs-git-helpers" / "scripts"
_FIXTURES_DIR = _REPO_ROOT / "plugins" / "tcs-git-helpers" / "tests" / "fixtures"
_GH_STUB = _FIXTURES_DIR / "gh_stubs" / "gh"


@pytest.fixture(scope="session")
def scripts_dir() -> Path:
    return _SCRIPTS_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return _FIXTURES_DIR


@pytest.fixture(scope="session")
def gh_stub_path() -> Path:
    return _GH_STUB


# ---------------------------------------------------------------------------
# Synthetic repo suite (built once per session via build.sh)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def synthetic_repos(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Build synthetic test repos using tests/fixtures/repos/build.sh.
    Returns the OUT_DIR path containing all scenario repos.

    Uses GIT_CONFIG_GLOBAL=/dev/null so host gpgsign/hooksPath do not leak.
    The build output dir is outside the parent repo (under pytest's tmp dir).
    """
    build_script = _FIXTURES_DIR / "repos" / "build.sh"
    out_dir = tmp_path_factory.mktemp("synthetic-repos", numbered=False)

    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"

    result = subprocess.run(
        ["bash", str(build_script), str(out_dir)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail(
            f"build.sh failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return out_dir


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d


@pytest.fixture()
def plugin_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "plugin_data"
    d.mkdir()
    (d / "cache").mkdir()
    (d / "audit").mkdir()
    return d


# ---------------------------------------------------------------------------
# Standard stale-branch entries for tests
# ---------------------------------------------------------------------------

STALE_ENTRIES = [
    {"name": "feat/old-thing", "pr_number": 38, "merged_at": "2026-04-12T10:00:00Z"},
    {"name": "fix/another-thing", "pr_number": 40, "merged_at": "2026-04-15T09:00:00Z"},
]
