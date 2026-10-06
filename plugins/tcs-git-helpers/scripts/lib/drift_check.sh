#!/usr/bin/env bash
# scripts/lib/drift_check.sh — drift detection for an installed bundle marker
# Spec: 012 (origin: drift_check_hook_bundle); spec 020 T4.1 generalised it to
#   drift_check_bundle with the marker_dir argument.
# Locale: the marker is classified under LC_ALL=C, scoped to that one pipeline
#   (not exported). BSD `tr -d '[:space:]'` is locale-dependent: a UTF-8 caller
#   would have U+00A0 stripped and an invalid byte abort it ("Illegal byte
#   sequence"). The contract is ASCII whitespace only, bytes passed through,
#   matching the Python twin drift_check.py (re.ASCII, lenient decode).
#
# drift_check_bundle <repo_path> <expected_version> [<version_filename>] [<marker_dir>]
#   Checks whether an installed bundle matches the expected version.
#   drift_check_hook_bundle <repo_path> <expected_version> [<version_filename>]
#   is a thin wrapper pinning marker_dir to .githooks (all pre-020 callers).
#
#   Inputs:
#     $1: repo_path (absolute path to repo root)
#     $2: expected_version (string, e.g. "h7")
#     $3: version_filename (optional; default: "tcs-git-helpers-version")
#         Name of the single-line marker file under <marker_dir>/.
#         Pass a different value (e.g. "tcs-helper-rule-enforcer-version")
#         to check any other bundle marker file.
#
#     $4: marker_dir (optional; default: ".githooks")
#         Directory, relative to repo_path, that holds the marker file.
#         (drift_check_bundle only; spec 020 T4.1)
#
#   Outputs (via stdout):
#     "OK"                 # versions match
#     "MISSING"            # <marker_dir>/<version_filename> is not a regular file
#     "DRIFT:<installed>"  # installed != expected
#
#   Exit code: 0 (always; caller decides action)
#   Side effects: none (read-only)
#   T3.2a: extended with optional third arg for alternate marker files.

drift_check_bundle() {
  local repo_path="$1"
  local expected_version="$2"
  local version_filename="${3:-tcs-git-helpers-version}"
  local marker_dir="${4:-.githooks}"
  local version_file="${repo_path}/${marker_dir}/${version_filename}"

  if [ ! -f "$version_file" ]; then
    printf 'MISSING\n'
    return 0
  fi
  local installed
  installed="$(head -n 1 "$version_file" | LC_ALL=C tr -d '[:space:]')"
  if [ "$installed" = "$expected_version" ]; then
    printf 'OK\n'
  else
    printf 'DRIFT:%s\n' "$installed"
  fi
}

drift_check_hook_bundle() {
  drift_check_bundle "$1" "$2" "${3:-tcs-git-helpers-version}" ".githooks"
}
