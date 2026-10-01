#!/bin/bash
#
# scripts/ci/check-hook-bundle-version.sh
#
# CI gate enforcing the maintainer contract (SDD ADR-7 / PRD CON-4), extended
# in spec-019 T1.4 to cover every versioned bundle this repo ships — one gate,
# many bundles:
#
#   For each bundle below: if any file matching its glob under its sources
#   directory changed in the given diff range AND its marker file did NOT
#   change in the same range, exit non-zero with a message naming the
#   offending files and the marker to bump.
#
# Bundles (sources_dir, marker_file, glob):
#   - git-helpers githooks: glob "*" (match everything). Most hook files
#     (pre-commit, post-merge, ...) have no extension, so filtering by
#     extension would silently stop protecting them — this bundle's glob
#     must never narrow past match-everything.
#   - observability scripts: glob "*.sh". README.md ships inside the
#     installed bundle but is prose, not a source — a wording fix must not
#     force a marker bump. The marker lives in a different directory from
#     the sources it gates.
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
#   0  — no violation (no gated bundle changed, or its marker was bumped alongside)
#   1  — violation (a bundle's sources changed without its marker bump)
#
# Bash 3.2 compatible. shellcheck clean.

set -uo pipefail

# ---------------------------------------------------------------------------
# Bundle table: sources_dir|marker_file|glob  (one bundle per line)
# ---------------------------------------------------------------------------

BUNDLES='plugins/tcs-git-helpers/templates/githooks|plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version|*
plugins/tcs-helper/scripts/observability|plugins/tcs-helper/templates/observability/tcs-helper-observability-version|*.sh'

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
# Per-bundle check: does a gated source file in $1 (sources_dir) match glob
# $3 and change without $2 (marker_file) also changing?
# ---------------------------------------------------------------------------

overall_fail=0

check_bundle() {
  local sources_dir="$1"
  local marker_file="$2"
  local glob="$3"

  local bundle_changed=0
  local marker_bumped=0
  local offending_files=""
  local path base matches

  while IFS= read -r path; do
    [ -z "$path" ] && continue

    if [ "$path" = "$marker_file" ]; then
      marker_bumped=1
      continue
    fi

    case "$path" in
      "${sources_dir}"/*)
        base="$(basename "$path")"
        matches=0
        # Literal per-glob dispatch (not `case "$base" in $glob)`) — a
        # variable used directly as a case pattern trips shellcheck SC2254,
        # and the whole point of this table is that "*" must stay an exact,
        # auditable match-everything, never a value that could drift.
        case "$glob" in
          '*')
            matches=1
            ;;
          '*.sh')
            case "$base" in
              *.sh) matches=1 ;;
            esac
            ;;
          *)
            printf 'check-hook-bundle-version: unknown glob "%s" in bundle table\n' "$glob" >&2
            exit 1
            ;;
        esac
        if [ "$matches" -eq 1 ]; then
          bundle_changed=1
          offending_files="${offending_files}  ${path}
"
        fi
        ;;
    esac
  done <<PATHS_EOF
$changed_paths
PATHS_EOF

  if [ "$bundle_changed" -eq 1 ] && [ "$marker_bumped" -eq 0 ]; then
    printf 'check-hook-bundle-version: FAIL\n' >&2
    printf '\n' >&2
    printf 'The following files in %s changed without a matching bump\n' "$sources_dir" >&2
    printf 'to %s:\n' "$marker_file" >&2
    printf '\n' >&2
    printf '%s' "$offending_files" >&2
    printf '\n' >&2
    printf 'Fix: bump %s (any new value) and commit before merging.\n' "$marker_file" >&2
    overall_fail=1
  fi
}

# ---------------------------------------------------------------------------
# Enforce the rule for every bundle
# ---------------------------------------------------------------------------

while IFS='|' read -r bundle_sources_dir bundle_marker_file bundle_glob; do
  [ -z "$bundle_sources_dir" ] && continue
  check_bundle "$bundle_sources_dir" "$bundle_marker_file" "$bundle_glob"
done <<BUNDLES_EOF
$BUNDLES
BUNDLES_EOF

exit "$overall_fail"
