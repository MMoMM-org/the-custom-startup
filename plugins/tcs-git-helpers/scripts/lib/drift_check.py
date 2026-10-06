"""
drift_check.py — skill-side drift check helper for tcs-git-helpers.

Reads the installed bundle version from
  <repo_path>/<marker_dir>/<version_filename>
(marker_dir defaults to .githooks)

and compares it against an expected version string.

Three-state result (mirrors the bash helper drift_check.sh):
  OK      — installed version matches expected
  MISSING — version file does not exist (hooks not installed, or
            installed before bundle versioning — ADR-8)
  DRIFT   — installed version differs from expected

Public API:
  check_bundle(
      repo_path: Path,
      expected_version: str,
      version_filename: str = "tcs-git-helpers-version",
      marker_dir: str = ".githooks",
  ) -> DriftResult

  check_hook_bundle(
      repo_path: Path,
      expected_version: str,
      version_filename: str = "tcs-git-helpers-version",
  ) -> DriftResult

check_hook_bundle is a thin wrapper over check_bundle with marker_dir pinned
to ".githooks" (spec 020 T4.1 added marker_dir).

The default value of version_filename preserves backward compatibility
with all existing callers. Pass a different filename to check any other
single-line bundle marker file (e.g., "tcs-helper-rule-enforcer-version").

Side effects: none (read-only).
Python 3.9+ compatible.

Spec: SDD/Internal API Changes / function: check_hook_bundle
T3.2a: extended with optional version_filename param (Option A).
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Tool-input override scan helper (CON-2 Python parity — T2.3)
# ---------------------------------------------------------------------------


def scan_tool_input_for_override(cmd: Optional[str], env_var: str) -> bool:
    """Return True if cmd starts with exactly '<env_var>=1<whitespace>+'.

    Mirrors the bash helper _scan_tool_input_for_override in override.sh.
    Both return False for None/empty cmd (CON-5: unset and empty are equivalent).

    Regex: re.ASCII is passed so \\s matches only POSIX [[:space:]] (space, tab,
    newline, carriage-return, form-feed, vertical-tab) — same set as bash
    [[:space:]], preventing Unicode whitespace from widening the match relative
    to bash.  re.escape(env_var) prevents caller-supplied metachars from
    widening the pattern (defensive — matches bash's literal variable expansion).
    """
    if not cmd:
        return False
    pattern = re.compile(r"^" + re.escape(env_var) + r"=1\s+", re.ASCII)
    return bool(pattern.match(cmd))

# Default bundle marker filename; used when version_filename is not supplied.
# Kept as a module-level constant for documentation — not referenced in the
# function body (the parameter default carries the value at call time).
_VERSION_FILENAME = "tcs-git-helpers-version"


class DriftStatus(enum.Enum):
    """Classification of installed bundle version against expected."""

    OK = "OK"
    MISSING = "MISSING"
    DRIFT = "DRIFT"


@dataclass(frozen=True)
class DriftResult:
    """Immutable result returned by check_bundle and check_hook_bundle."""

    status: DriftStatus
    installed_version: Optional[str]


def check_bundle(
    repo_path: Path,
    expected_version: str,
    version_filename: str = "tcs-git-helpers-version",
    marker_dir: str = ".githooks",
) -> DriftResult:
    """Return the drift classification for an installed bundle marker.

    Args:
        repo_path: Absolute path to the repository root.
        expected_version: The version string the skill requires (e.g. "h7").
        version_filename: Name of the single-line marker file under marker_dir.
        marker_dir: Directory, relative to repo_path, holding the marker.
            Defaults to ".githooks".

    Returns:
        DriftResult with status OK / MISSING / DRIFT and the installed
        version string (None when MISSING).
    """
    version_file = repo_path / marker_dir / version_filename

    if not version_file.exists():
        return DriftResult(status=DriftStatus.MISSING, installed_version=None)

    # Match bash `tr -d '[:space:]'` — remove ALL whitespace including internal
    installed = re.sub(r'\s+', '', version_file.read_text().split("\n")[0])

    if installed == expected_version:
        return DriftResult(status=DriftStatus.OK, installed_version=installed)

    return DriftResult(status=DriftStatus.DRIFT, installed_version=installed)


def check_hook_bundle(
    repo_path: Path,
    expected_version: str,
    version_filename: str = "tcs-git-helpers-version",
) -> DriftResult:
    """Drift classification for the hook bundle under .githooks/.

    Thin wrapper over check_bundle; signature and defaults are unchanged.
    """
    return check_bundle(repo_path, expected_version, version_filename, ".githooks")
