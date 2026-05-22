"""
drift_check.py — skill-side drift check helper for tcs-git-helpers.

Reads the installed hook bundle version from
  <repo_path>/.githooks/<version_filename>

and compares it against an expected version string.

Three-state result (mirrors the bash helper drift_check.sh):
  OK      — installed version matches expected
  MISSING — version file does not exist (hooks not installed, or
            installed before bundle versioning — ADR-8)
  DRIFT   — installed version differs from expected

Public API:
  check_hook_bundle(
      repo_path: Path,
      expected_version: str,
      version_filename: str = "tcs-git-helpers-version",
  ) -> DriftResult

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

# Default bundle marker filename; used when version_filename is not supplied.
# Kept as a module-level constant for documentation — not referenced in the
# function body (the parameter default carries the value at call time).
_VERSION_FILENAME = "tcs-git-helpers-version"


class DriftStatus(enum.Enum):
    """Classification of installed hook bundle version against expected."""

    OK = "OK"
    MISSING = "MISSING"
    DRIFT = "DRIFT"


@dataclass(frozen=True)
class DriftResult:
    """Immutable result returned by check_hook_bundle."""

    status: DriftStatus
    installed_version: Optional[str]


def check_hook_bundle(
    repo_path: Path,
    expected_version: str,
    version_filename: str = "tcs-git-helpers-version",
) -> DriftResult:
    """Return the drift classification for the repo's installed hook bundle.

    Args:
        repo_path: Absolute path to the repository root.
        expected_version: The version string the skill requires (e.g. "h7").
        version_filename: Name of the single-line marker file under
            .githooks/ that contains the installed bundle version.
            Defaults to "tcs-git-helpers-version" for backward
            compatibility with all existing callers.  Pass a different
            value (e.g. "tcs-helper-rule-enforcer-version") to check
            any other bundle marker file.

    Returns:
        DriftResult with status OK / MISSING / DRIFT and the installed
        version string (None when MISSING).
    """
    version_file = repo_path / ".githooks" / version_filename

    if not version_file.exists():
        return DriftResult(status=DriftStatus.MISSING, installed_version=None)

    # Match bash `tr -d '[:space:]'` — remove ALL whitespace including internal
    installed = re.sub(r'\s+', '', version_file.read_text().split("\n")[0])

    if installed == expected_version:
        return DriftResult(status=DriftStatus.OK, installed_version=installed)

    return DriftResult(status=DriftStatus.DRIFT, installed_version=installed)
