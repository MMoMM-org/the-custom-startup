"""
test_drift_check.py — pytest suite for scripts/lib/drift_check.py

TDD cycle: tests written RED first; they import from
scripts/lib/drift_check.py which does not exist yet, so they will
fail with ImportError until the implementation is in place.

Covers:
  1. MISSING  — .githooks/tcs-git-helpers-version does not exist
  2. OK       — installed version matches expected
  3. DRIFT    — installed version differs from expected

Plus a 10-row parity table asserting the python helper produces the
same classification as the bash helper (scripts/lib/drift_check.sh)
for identical inputs. If the bash helper is not present yet the parity
tests are skipped via pytest.skip (T2.1 may land after T2.2).
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Dynamic import of drift_check (not installed; loaded by path)
# ---------------------------------------------------------------------------

_PLUGIN_ROOT = Path(__file__).parent.parent.parent  # plugins/tcs-git-helpers/
_LIB_PATH = _PLUGIN_ROOT / "scripts" / "lib" / "drift_check.py"
_BASH_HELPER = _PLUGIN_ROOT / "scripts" / "lib" / "drift_check.sh"


def _load_module():
    import sys
    spec = importlib.util.spec_from_file_location("drift_check", _LIB_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve forward-reference annotations
    # (Python 3.14 + from __future__ import annotations requires module in sys.modules)
    sys.modules["drift_check"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        del sys.modules["drift_check"]
        raise
    return mod


@pytest.fixture(scope="module")
def dc():
    """Loaded drift_check module."""
    return _load_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_version_file(repo_path: Path, content: str) -> None:
    githooks = repo_path / ".githooks"
    githooks.mkdir(parents=True, exist_ok=True)
    (githooks / "tcs-git-helpers-version").write_text(content)


def _call_bash_helper(repo_path: Path, expected_version: str) -> str:
    """
    Subprocess-call the bash helper: source drift_check.sh and call
    drift_check_hook_bundle <repo_path> <expected_version>.
    Returns stripped stdout.
    Raises subprocess.CalledProcessError if the bash helper exits non-zero.
    """
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{_BASH_HELPER}"; drift_check_hook_bundle "{repo_path}" "{expected_version}"',
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    result.check_returncode()
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Core unit tests
# ---------------------------------------------------------------------------


class TestMissing:
    """When .githooks/tcs-git-helpers-version does not exist."""

    def test_status_is_missing(self, dc, tmp_path: Path) -> None:
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.MISSING

    def test_installed_version_is_none(self, dc, tmp_path: Path) -> None:
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.installed_version is None

    def test_result_is_frozen(self, dc, tmp_path: Path) -> None:
        result = dc.check_hook_bundle(tmp_path, "h7")
        with pytest.raises((AttributeError, TypeError)):
            result.status = dc.DriftStatus.OK  # type: ignore[misc]


class TestOK:
    """When installed version matches expected."""

    def test_status_is_ok_exact_match(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h7\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.OK

    def test_installed_version_is_returned(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h7\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.installed_version == "h7"

    def test_strips_trailing_newline(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h7\n\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.OK

    def test_strips_crlf(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h7\r\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.OK

    def test_strips_leading_and_trailing_whitespace(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "  h7  \n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.OK


class TestDrift:
    """When installed version differs from expected."""

    def test_status_is_drift(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h1\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.DRIFT

    def test_installed_version_returned_on_drift(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h1\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.installed_version == "h1"

    def test_drift_strips_whitespace_before_compare(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "  h5  \r\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.DRIFT
        assert result.installed_version == "h5"

    def test_empty_version_file_is_drift_not_missing(self, dc, tmp_path: Path) -> None:
        """A file that exists but has only whitespace still yields DRIFT (file is present)."""
        _write_version_file(tmp_path, "   \n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        # Empty stripped content "" != "h7" → DRIFT
        assert result.status == dc.DriftStatus.DRIFT

    def test_different_prefix_is_drift(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "v2\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.DRIFT


# ---------------------------------------------------------------------------
# Parity tests — python vs bash helper must agree on every row
# ---------------------------------------------------------------------------

# Fixture table columns:
#   (installed_file_content_or_None, expected_version, want_status_string)
#
# `want_status_string` uses the bash wire format:
#   "OK", "MISSING", or "DRIFT:<installed>" where <installed> is stripped content.
#
_PARITY_TABLE: list[tuple[Optional[str], str, str]] = [
    # MISSING cases (file absent)
    (None,          "h7",    "MISSING"),
    (None,          "h1",    "MISSING"),
    # OK cases (file content, after strip, equals expected)
    ("h7\n",        "h7",    "OK"),
    ("h1\n",        "h1",    "OK"),
    ("h7\r\n",      "h7",    "OK"),
    ("  h7  \n",    "h7",    "OK"),
    ("h 7\n",       "h7",    "OK"),  # internal space removed by tr -d '[:space:]'
    # DRIFT cases (file exists but content != expected)
    ("h1\n",        "h7",    "DRIFT:h1"),
    ("h5\n",        "h7",    "DRIFT:h5"),
    ("  h3  \r\n",  "h7",    "DRIFT:h3"),
    ("v2\n",        "h7",    "DRIFT:v2"),
]


def _status_to_bash_wire(dc, result) -> str:
    """Convert a python DriftResult to the bash wire format for comparison."""
    if result.status == dc.DriftStatus.MISSING:
        return "MISSING"
    if result.status == dc.DriftStatus.OK:
        return "OK"
    # DRIFT
    return f"DRIFT:{result.installed_version}"


@pytest.mark.parametrize(
    "file_content,expected_version,want_status",
    _PARITY_TABLE,
    ids=[
        "missing-h7",
        "missing-h1",
        "ok-h7",
        "ok-h1",
        "ok-h7-crlf",
        "ok-h7-spaces",
        "ok-h7-internal-space",
        "drift-h1-vs-h7",
        "drift-h5-vs-h7",
        "drift-h3-spaces-crlf",
        "drift-v2-vs-h7",
    ],
)
def test_parity_python_matches_bash(
    dc,
    tmp_path: Path,
    file_content: Optional[str],
    expected_version: str,
    want_status: str,
) -> None:
    """Python and bash helpers must classify identically for every fixture row."""
    # Set up the tmp repo
    if file_content is not None:
        _write_version_file(tmp_path, file_content)

    # Python result
    py_result = dc.check_hook_bundle(tmp_path, expected_version)
    py_wire = _status_to_bash_wire(dc, py_result)

    # Bash result (skip if helper not present yet — T2.1 may still be in flight)
    if not _BASH_HELPER.exists():
        pytest.skip(
            f"Bash helper not yet present at {_BASH_HELPER}; "
            "parity test will run once T2.1 lands"
        )

    bash_wire = _call_bash_helper(tmp_path, expected_version)

    # Both must agree with the fixture expectation
    assert py_wire == want_status, (
        f"Python returned {py_wire!r}; expected {want_status!r}"
    )
    assert bash_wire == want_status, (
        f"Bash returned {bash_wire!r}; expected {want_status!r}"
    )
