"""prompt_lint.py --repo over the tracked prompt-file set has no unsuppressed errors.

A finding that is real but out of scope to fix here goes into KNOWN_OPEN, keyed by
path, check and the issue that tracks it. Each entry must still match a finding,
so a fixed issue fails the test until its entry is removed.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins/tcs-helper/skills/prompt-author/scripts/prompt_lint.py"

KNOWN_OPEN = []


def _known_open(finding):
    for entry in KNOWN_OPEN:
        low, high = entry["lines"]
        if (finding["path"], finding["check"]) == (entry["path"], entry["check"]) \
                and low <= finding["line"] <= high:
            return entry
    return None


@pytest.fixture(scope="module")
def repo_run():
    if not SCRIPT.is_file():
        pytest.fail("prompt_lint.py does not exist yet: {}".format(SCRIPT))
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--json", "--repo"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=120,
    )
    elapsed = time.monotonic() - started
    assert result.returncode in (0, 1), result.stderr
    return json.loads(result.stdout), elapsed


def test_repo_has_no_unsuppressed_errors_outside_known_open(repo_run):
    data, _ = repo_run
    errors = [f for f in data["findings"] if f["level"] == "error" and not f["suppressed"]]
    unexpected = [f for f in errors if _known_open(f) is None]
    assert unexpected == [], "\n".join(
        "{path}:{line}: {check} {message}".format(**f) for f in unexpected)


def test_every_known_open_entry_still_matches_a_finding(repo_run):
    data, _ = repo_run
    matched = [_known_open(f) for f in data["findings"]]
    stale = [e for e in KNOWN_OPEN if e not in matched]
    assert stale == [], "issue fixed? remove from KNOWN_OPEN: {}".format(stale)


def test_every_suppression_carries_a_reason(repo_run):
    data, _ = repo_run
    assert all(f["reason"] for f in data["findings"] if f["suppressed"])


def test_repo_run_lints_the_prompt_file_set(repo_run):
    data, _ = repo_run
    assert data["files"] > 100
    paths = {f["path"] for f in data["findings"]}
    assert not any("/experiment/" in p or "/fixtures/" in p for p in paths)


@pytest.mark.perf
def test_repo_run_takes_under_ten_seconds(repo_run):
    _, elapsed = repo_run
    assert elapsed < 10.0
