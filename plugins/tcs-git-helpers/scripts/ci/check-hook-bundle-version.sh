#!/bin/bash
#
# scripts/ci/check-hook-bundle-version.sh
#
# CI gate enforcing the maintainer contract (SDD ADR-7 / PRD CON-4):
#
#   If any file under plugins/tcs-git-helpers/templates/githooks/ changed in the
#   given diff range AND plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version
#   did NOT change in the same range, exit non-zero with a message naming the
#   offending files and explaining the fix.
#
# Usage:
#   check-hook-bundle-version.sh [<diff-range>] [<repo-path>]
#
#   <diff-range>   Git diff range passed to `git diff --name-only`.
#                  Default: origin/main..HEAD
#   <repo-path>    Root of the git repo to run `git diff` in.
#                  Default: current working directory.
#
# Exit codes:
#   0  — no violation (no githooks changes, or version was bumped alongside)
#   1  — violation (githooks files changed without version bump)
#
# Bash 3.2 compatible. shellcheck clean.

set -uo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

readonly HOOKS_DIR="plugins/tcs-git-helpers/templates/githooks"
readonly VERSION_FILE="${HOOKS_DIR}/tcs-git-helpers-version"

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

DIFF_RANGE="${1:-origin/main..HEAD}"
REPO_PATH="${2:-.}"

# ---------------------------------------------------------------------------
# Collect changed paths in the diff range
# ---------------------------------------------------------------------------

changed_paths="$(git -C "$REPO_PATH" diff --name-only "$DIFF_RANGE" 2>&1)" || {
  printf 'check-hook-bundle-version: git diff failed: %s\n' "$changed_paths" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Classify changed paths
# ---------------------------------------------------------------------------

hooks_changed=0
version_bumped=0
offending_files=""

while IFS= read -r path; do
  [ -z "$path" ] && continue

  case "$path" in
    "${HOOKS_DIR}"/*)
      if [ "$path" = "$VERSION_FILE" ]; then
        version_bumped=1
      else
        hooks_changed=1
        offending_files="${offending_files}  ${path}
"
      fi
      ;;
  esac
done <<EOF
$changed_paths
EOF

# ---------------------------------------------------------------------------
# Enforce the rule
# ---------------------------------------------------------------------------

if [ "$hooks_changed" -eq 1 ] && [ "$version_bumped" -eq 0 ]; then
  printf 'check-hook-bundle-version: FAIL\n' >&2
  printf '\n' >&2
  printf 'The following files in %s changed without a matching bump\n' "$HOOKS_DIR" >&2
  printf 'to %s:\n' "$VERSION_FILE" >&2
  printf '\n' >&2
  printf '%s' "$offending_files" >&2
  printf '\n' >&2
  printf 'Fix: bump %s (any new value) and commit before merging.\n' "$VERSION_FILE" >&2
  exit 1
fi

exit 0
