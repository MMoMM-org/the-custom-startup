#!/usr/bin/env bats
#
# tests/bats/observability-set-u-safety.bats
#
# spec 019 (observability rollout across active repos), Phase 1 — regression
# coverage for a `set -u` unsafety defect found during phase validation.
#
# _read_observability_bundle_version (bundle_version.sh) and
# _drift_check_observability_bundle (drift_check.sh) both document a
# positional argument as OPTIONAL ([<version_file>] / [<marker_path>]) but
# read it as a bare "$1"/"$2" — which aborts with "unbound variable" under
# `set -u` when the function is called in exactly its documented
# no-optional-argument form. None of the other suites in this directory run
# under `set -u` (bats does not enable it for test bodies), so this defect
# passed 171 green tests undetected. Phase 4's `status` verb is specified to
# call _drift_check_observability_bundle with the marker path omitted, and
# this repo's own CI gate (check-hook-bundle-version.sh) runs
# `set -uo pipefail` — so this is not hypothetical.
#
# This suite does NOT re-cover ordinary (non-`set -u`) behaviour — see
# observability-bundle-version.bats and observability-drift-check.bats for
# that. It exists solely to pin the `set -u` contract.
#
# bash 3.2 compatible (CON-1): no `[[ =~ ]]` with PCRE classes or bounded
# quantifiers here — only literal string/status comparisons.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  VERSION_HELPER="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/bundle_version.sh"
  DRIFT_HELPER="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/drift_check.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-obs-set-u.XXXXXX")"

  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$FAKE_HOME"
  export HOME="$FAKE_HOME"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# 1. _read_observability_bundle_version, no argument, under `set -u`.
# ---------------------------------------------------------------------------

@test "set -u: _read_observability_bundle_version with no argument succeeds and resolves the template marker" {
  run bash -c "set -u; . '$VERSION_HELPER'; _read_observability_bundle_version"
  [ "$status" -eq 0 ]
  [ "$output" = "h1" ]
}

# ---------------------------------------------------------------------------
# 2. _drift_check_observability_bundle, marker path omitted, under `set -u`
#    — this is Phase 4's documented `status` verb call shape.
# ---------------------------------------------------------------------------

@test "set -u: _drift_check_observability_bundle with marker path omitted succeeds (MISSING, nothing installed)" {
  run bash -c "set -u; . '$DRIFT_HELPER'; _drift_check_observability_bundle 'h1'"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

@test "set -u: _drift_check_observability_bundle with marker path omitted succeeds (OK, matching marker installed)" {
  mkdir -p "$HOME/.claude/observability"
  printf 'h1\n' > "$HOME/.claude/observability/tcs-helper-observability-version"

  run bash -c "set -u; . '$DRIFT_HELPER'; _drift_check_observability_bundle 'h1'"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ---------------------------------------------------------------------------
# 3. End-to-end: the full install path under `set -u`, the check that
#    actually found the defect (_install_observability_bundle sources
#    bundle_version.sh and calls _read_observability_bundle_version with no
#    argument internally).
# ---------------------------------------------------------------------------

@test "set -u: _install_observability_bundle (end-to-end) succeeds and installs into HOME" {
  INSTALL_HELPER="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/bundle_install.sh"

  run bash -c "set -u; . '$INSTALL_HELPER'; _install_observability_bundle"
  [ "$status" -eq 0 ]
  [ -f "$HOME/.claude/observability/tcs-helper-observability-version" ]
}
