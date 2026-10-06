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

T3.2a extension — optional version_filename parameter:
  4. BACKWARD_COMPAT — omitting version_filename still works on tcs-git-helpers-version
  5. CUSTOM_MISSING   — custom filename absent → MISSING
  6. CUSTOM_OK        — custom filename present with matching content → OK
  7. CUSTOM_DRIFT     — custom filename present with different content → DRIFT
"""
from __future__ import annotations

import importlib.util
import os
import shlex
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
_BASH_LIB_OVERRIDE = _PLUGIN_ROOT / "scripts" / "lib" / "override.sh"


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


def _write_custom_version_file(repo_path: Path, filename: str, content: str) -> None:
    githooks = repo_path / ".githooks"
    githooks.mkdir(parents=True, exist_ok=True)
    (githooks / filename).write_text(content)


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


def _call_bash_scan(cmd: str, env_var: str) -> bool:
    """
    Invoke the bash _scan_tool_input_for_override helper via subprocess.
    Sources cache.sh then override.sh, sets CMD, and calls the function.
    Returns True if exit status is 0 (match), False if 1 (no match).
    """
    cache_sh = _PLUGIN_ROOT / "scripts" / "lib" / "cache.sh"
    # shlex.quote (not repr) — repr emits Python string literals; bash does
    # not honour backslash escapes inside single quotes, so any cmd mixing
    # single and double quote chars would silently produce wrong CMD or a
    # syntax error and mask a real parity divergence.
    script = (
        f'export CLAUDE_PLUGIN_DATA="$(mktemp -d)"; '
        f'CMD={shlex.quote(cmd)}; '
        f'source "{cache_sh}"; '
        f'source "{_BASH_LIB_OVERRIDE}"; '
        f'_scan_tool_input_for_override {shlex.quote(env_var)}'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0


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


# ---------------------------------------------------------------------------
# T3.2a — optional version_filename parameter
# ---------------------------------------------------------------------------

_RULE_ENFORCER_FILENAME = "tcs-helper-rule-enforcer-version"


class TestDefaultFilenameBackwardCompat:
    """Omitting version_filename must behave identically to the 2-arg form."""

    def test_check_hook_bundle_default_filename_backward_compat(
        self, dc, tmp_path: Path
    ) -> None:
        """2-arg call succeeds on tcs-git-helpers-version (default filename)."""
        _write_version_file(tmp_path, "h7\n")
        result = dc.check_hook_bundle(tmp_path, "h7")
        assert result.status == dc.DriftStatus.OK
        assert result.installed_version == "h7"


class TestCustomFilename:
    """version_filename parameter routes drift-check to an alternate marker file."""

    def test_check_hook_bundle_custom_filename_missing(
        self, dc, tmp_path: Path
    ) -> None:
        """Custom filename absent → MISSING (file never installed)."""
        result = dc.check_hook_bundle(
            tmp_path, "1.0.0", version_filename=_RULE_ENFORCER_FILENAME
        )
        assert result.status == dc.DriftStatus.MISSING
        assert result.installed_version is None

    def test_check_hook_bundle_custom_filename_ok(
        self, dc, tmp_path: Path
    ) -> None:
        """Custom filename present with matching content → OK."""
        _write_custom_version_file(tmp_path, _RULE_ENFORCER_FILENAME, "1.0.0\n")
        result = dc.check_hook_bundle(
            tmp_path, "1.0.0", version_filename=_RULE_ENFORCER_FILENAME
        )
        assert result.status == dc.DriftStatus.OK
        assert result.installed_version == "1.0.0"

    def test_check_hook_bundle_custom_filename_drift(
        self, dc, tmp_path: Path
    ) -> None:
        """Custom filename present with different content → DRIFT."""
        _write_custom_version_file(tmp_path, _RULE_ENFORCER_FILENAME, "1.0.0\n")
        result = dc.check_hook_bundle(
            tmp_path, "1.0.1", version_filename=_RULE_ENFORCER_FILENAME
        )
        assert result.status == dc.DriftStatus.DRIFT
        assert result.installed_version == "1.0.0"


# ---------------------------------------------------------------------------
# Spec 020 T4.1 — check_bundle takes a marker directory
# ---------------------------------------------------------------------------

_PATTERNS_FILENAME = "tcs-patterns-version"


def _write_marker(repo_path: Path, marker_dir: str, filename: str, content: str) -> None:
    d = repo_path / marker_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content)


def _call_bash_bundle(
    repo_path: Path, expected: str, filename: str, marker_dir: str
) -> str:
    script = (
        f"source {shlex.quote(str(_BASH_HELPER))}; "
        f"drift_check_bundle {shlex.quote(str(repo_path))} {shlex.quote(expected)} "
        f"{shlex.quote(filename)} {shlex.quote(marker_dir)}"
    )
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=10
    )
    result.check_returncode()
    return result.stdout.strip()


class TestCheckBundleMarkerDir:
    def test_missing_in_custom_dir(self, dc, tmp_path: Path) -> None:
        r = dc.check_bundle(tmp_path, "1.0", _PATTERNS_FILENAME, ".tcs-patterns")
        assert r.status == dc.DriftStatus.MISSING
        assert r.installed_version is None

    def test_ok_in_custom_dir(self, dc, tmp_path: Path) -> None:
        _write_marker(tmp_path, ".tcs-patterns", _PATTERNS_FILENAME, "1.0\n")
        r = dc.check_bundle(tmp_path, "1.0", _PATTERNS_FILENAME, ".tcs-patterns")
        assert r.status == dc.DriftStatus.OK
        assert r.installed_version == "1.0"

    def test_drift_in_custom_dir(self, dc, tmp_path: Path) -> None:
        _write_marker(tmp_path, ".tcs-patterns", _PATTERNS_FILENAME, "0.9\n")
        r = dc.check_bundle(tmp_path, "1.0", _PATTERNS_FILENAME, ".tcs-patterns")
        assert r.status == dc.DriftStatus.DRIFT
        assert r.installed_version == "0.9"

    def test_githooks_marker_not_read_when_dir_differs(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h7\n")
        r = dc.check_bundle(
            tmp_path, "h7", "tcs-git-helpers-version", ".tcs-patterns"
        )
        assert r.status == dc.DriftStatus.MISSING

    def test_custom_dir_marker_not_read_by_default_dir(self, dc, tmp_path: Path) -> None:
        _write_marker(tmp_path, ".tcs-patterns", "tcs-git-helpers-version", "h7\n")
        r = dc.check_bundle(tmp_path, "h7")
        assert r.status == dc.DriftStatus.MISSING

    def test_default_dir_equals_hook_bundle_wrapper(self, dc, tmp_path: Path) -> None:
        _write_version_file(tmp_path, "h1\n")
        assert dc.check_bundle(tmp_path, "h7") == dc.check_hook_bundle(tmp_path, "h7")


_BUNDLE_DIRS = [".githooks", ".tcs-patterns", "nested/dir"]
_BUNDLE_CONTENTS = [None, "h7\n", "  h 7  \r\n", "h1\n", "   \n"]


@pytest.mark.parametrize("marker_dir", _BUNDLE_DIRS)
@pytest.mark.parametrize("content", _BUNDLE_CONTENTS, ids=repr)
def test_bundle_parity_python_matches_bash(
    dc, tmp_path: Path, marker_dir: str, content: Optional[str]
) -> None:
    """check_bundle and drift_check_bundle agree across marker dirs x verdicts."""
    if content is not None:
        _write_marker(tmp_path, marker_dir, _PATTERNS_FILENAME, content)
    py_wire = _status_to_bash_wire(
        dc, dc.check_bundle(tmp_path, "h7", _PATTERNS_FILENAME, marker_dir)
    )
    bash_wire = _call_bash_bundle(tmp_path, "h7", _PATTERNS_FILENAME, marker_dir)
    assert py_wire == bash_wire
    if content is None:
        assert bash_wire == "MISSING"


# Marker shapes the text-only grid above cannot express: a directory at the
# marker path, a non-breaking space, and bytes that are not valid UTF-8.
# BSD `tr -d '[:space:]'` is locale-dependent: in a UTF-8 locale it strips
# U+00A0 and aborts on an invalid byte, while the helper's contract is ASCII
# whitespace only on whatever bytes the file holds. Bash therefore runs under
# both a C and a UTF-8 caller locale; the helper must pin its own.
_BYTES_PARITY_CASES: list[tuple[str, Optional[bytes]]] = [
    ("directory-at-marker-path", None),
    ("nbsp-is-not-whitespace", b"h\xc2\xa07\n"),
    ("invalid-utf8-byte", b"h\xff7\n"),
    ("invalid-utf8-only-after-first-line", b"h7\n\xff\xfe\n"),
]


@pytest.mark.parametrize("locale", ["C", "en_US.UTF-8"])
@pytest.mark.parametrize(
    "content", [c for _, c in _BYTES_PARITY_CASES], ids=[i for i, _ in _BYTES_PARITY_CASES]
)
def test_bundle_parity_on_non_text_markers(
    dc, tmp_path: Path, content: Optional[bytes], locale: str
) -> None:
    """Python agrees with bash when the marker is a directory or holds odd bytes."""
    marker = tmp_path / ".tcs-patterns" / _PATTERNS_FILENAME
    marker.parent.mkdir(parents=True)
    if content is None:
        marker.mkdir()
    else:
        marker.write_bytes(content)

    py_wire = _status_to_bash_wire(
        dc, dc.check_bundle(tmp_path, "h7", _PATTERNS_FILENAME, ".tcs-patterns")
    )
    script = (
        f"source {shlex.quote(str(_BASH_HELPER))}; "
        f"drift_check_bundle {shlex.quote(str(tmp_path))} h7 "
        f"{shlex.quote(_PATTERNS_FILENAME)} .tcs-patterns"
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        timeout=10,
        env={**os.environ, "LC_ALL": locale},
    )
    result.check_returncode()
    bash_wire = result.stdout.decode("utf-8", errors="replace").strip()
    assert py_wire == bash_wire


# ---------------------------------------------------------------------------
# T2.3 — CON-2 parity rows: scan_tool_input_for_override (bash ↔ Python)
#
# Each row mirrors a BATS scenario from lib_override.bats §_scan_tool_input.
# The Python helper must agree with bash on every (cmd, env_var) input.
# CON-2: bash and Python implementations of the same logic MUST agree on
# classification for every input in the parity test table.
# ---------------------------------------------------------------------------

_SCAN_PARITY_TABLE: list[tuple[Optional[str], str, bool]] = [
    # (cmd, env_var, expected_match)
    #
    # positive match — granular env-var prefix at position 0, whitespace after =1
    ("CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push", "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR", True),
    # master positive match — CLAUDE_ALLOW_GIT_BAD_OPS prefix (ADR-4)
    ("CLAUDE_ALLOW_GIT_BAD_OPS=1 git push",        "CLAUDE_ALLOW_GIT_BAD_OPS",        True),
    # empty CMD — bash returns 1 for empty string (CON-5)
    ("",                                            "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR", False),
    # mid-command bypass — token not at position 0 (regex anchored to ^)
    ("git push && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 foo", "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR", False),
    # shell-quoting trick — injection after quote (M2 PRD edge case)
    ("git push' && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1; '", "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR", False),
    # =10 false-positive guard — [[:space:]]+ after =1 rejects =10
    ("CLAUDE_ALLOW_FOO=10 git push",               "CLAUDE_ALLOW_FOO",                False),
    # leading-whitespace bypass — leading space before token, ^ anchored rejects
    (" CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push", "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR", False),
]

# unset CMD maps to None in the table; bash treats unset and empty identically
# per CON-5 — bash guard: `[ -z "${CMD:-}" ]` returns 1 for both.
_SCAN_PARITY_TABLE_WITH_UNSET: list[tuple[Optional[str], str, bool]] = [
    (None, "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR", False),
]


@pytest.mark.parametrize(
    "cmd,env_var,expected_match",
    _SCAN_PARITY_TABLE,
    ids=[
        "granular-positive",
        "master-positive",
        "empty-cmd",
        "mid-command",
        "shell-quoting-trick",
        "equals-10-false-positive",
        "leading-whitespace",
    ],
)
def test_scan_parity_python_matches_bash(
    dc,
    cmd: str,
    env_var: str,
    expected_match: bool,
) -> None:
    """Python scan_tool_input_for_override must agree with bash for every fixture."""
    py_result = dc.scan_tool_input_for_override(cmd, env_var)
    assert py_result == expected_match, (
        f"Python: scan_tool_input_for_override({cmd!r}, {env_var!r}) "
        f"returned {py_result!r}; expected {expected_match!r}"
    )

    # Cross-check against bash implementation when available.
    if not _BASH_LIB_OVERRIDE.exists():
        pytest.skip(
            f"Bash override lib not yet at {_BASH_LIB_OVERRIDE}; "
            "parity check will run once T2.1 lands"
        )
    bash_cmd = cmd  # may be empty string — bash treats "" same as unset via ${CMD:-}
    bash_result = _call_bash_scan(bash_cmd, env_var)
    assert bash_result == expected_match, (
        f"Bash returned {bash_result!r}; expected {expected_match!r} for "
        f"CMD={cmd!r}, env_var={env_var!r}"
    )


@pytest.mark.parametrize(
    "cmd,env_var,expected_match",
    _SCAN_PARITY_TABLE_WITH_UNSET,
    ids=["unset-cmd"],
)
def test_scan_parity_unset_cmd(
    dc,
    cmd: Optional[str],
    env_var: str,
    expected_match: bool,
) -> None:
    """Unset CMD (None) and empty CMD must both yield False — CON-5 parity."""
    # Pass None to signal unset — Python helper receives None and treats it as no-match.
    py_result = dc.scan_tool_input_for_override(cmd, env_var)
    assert py_result == expected_match, (
        f"Python: scan_tool_input_for_override(None, {env_var!r}) "
        f"returned {py_result!r}; expected {expected_match!r}"
    )
