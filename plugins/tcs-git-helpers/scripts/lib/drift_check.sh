#!/usr/bin/env bash
# scripts/lib/drift_check.sh — drift detection for installed hook bundle
# Spec: SDD §Internal API Changes / function: drift_check_hook_bundle
#
# drift_check_hook_bundle <repo_path> <expected_version> [<version_filename>]
#   Checks whether the installed hook bundle matches the expected version.
#
#   Inputs:
#     $1: repo_path (absolute path to repo root)
#     $2: expected_version (string, e.g. "h7")
#     $3: version_filename (optional; default: "tcs-git-helpers-version")
#         Name of the single-line marker file under .githooks/.
#         Pass a different value (e.g. "tcs-helper-rule-enforcer-version")
#         to check any other bundle marker file.
#
#   Outputs (via stdout):
#     "OK"                 # versions match
#     "MISSING"            # .githooks/<version_filename> does not exist
#     "DRIFT:<installed>"  # installed != expected
#
#   Exit code: 0 (always; caller decides action)
#   Side effects: none (read-only)
#   T3.2a: extended with optional third arg for alternate marker files.

drift_check_hook_bundle() {
  local repo_path="$1"
  local expected_version="$2"
  local version_filename="${3:-tcs-git-helpers-version}"
  local version_file="${repo_path}/.githooks/${version_filename}"

  if [ ! -f "$version_file" ]; then
    printf 'MISSING\n'
    return 0
  fi
  local installed
  installed="$(head -n 1 "$version_file" | tr -d '[:space:]')"
  if [ "$installed" = "$expected_version" ]; then
    printf 'OK\n'
  else
    printf 'DRIFT:%s\n' "$installed"
  fi
}
