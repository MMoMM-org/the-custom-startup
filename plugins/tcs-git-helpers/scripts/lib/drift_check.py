"""
drift_check.py — skill-side drift check helper for tcs-git-helpers.

Reads the installed hook bundle version from
  <repo_path>/.githooks/tcs-git-helpers-version

and compares it against an expected version string.

Three-state result (mirrors the bash helper drift_check.sh):
  OK      — installed version matches expected
  MISSING — version file does not exist (hooks not installed, or
            installed before bundle versioning — ADR-8)
  DRIFT   — installed version differs from expected

Public API:
  check_hook_bundle(repo_path: Path, expected_version: str) -> DriftResult

Side effects: none (read-only).
Python 3.9+ compatible.

Spec: SDD/Internal API Changes / function: check_hook_bundle
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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


def check_hook_bundle(repo_path: Path, expected_version: str) -> DriftResult:
    """Return the drift classification for the repo's installed hook bundle.

    Args:
        repo_path: Absolute path to the repository root.
        expected_version: The version string the skill requires (e.g. "h7").

    Returns:
        DriftResult with status OK / MISSING / DRIFT and the installed
        version string (None when MISSING).
    """
    version_file = repo_path / ".githooks" / _VERSION_FILENAME

    if not version_file.exists():
        return DriftResult(status=DriftStatus.MISSING, installed_version=None)

    # Match bash `tr -d '[:space:]'` — remove ALL whitespace including internal
    installed = re.sub(r'\s+', '', version_file.read_text().split("\n")[0])

    if installed == expected_version:
        return DriftResult(status=DriftStatus.OK, installed_version=installed)

    return DriftResult(status=DriftStatus.DRIFT, installed_version=installed)
