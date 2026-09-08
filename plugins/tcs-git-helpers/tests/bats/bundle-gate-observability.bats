#!/usr/bin/env bats
#
# tests/bats/bundle-gate-observability.bats
#
# Test suite for the observability-bundle extension to
# scripts/ci/check-hook-bundle-version.sh (spec-019, T1.4).
#
# Spec references:
#   - spec-019 Phase 1, T1.4 — one CI gate protecting two bundles
#   - Pinned ruling: observability sources are matched by a per-bundle glob
#     (*.sh) under plugins/tcs-helper/scripts/observability/; its marker is
#     plugins/tcs-helper/templates/observability/tcs-helper-observability-version
#     — a DIFFERENT directory from the sources.
#   - Pinned ruling: the git-helpers bundle's glob must stay match-everything,
#     so non-.sh hook files (post-merge, pre-commit, ...) stay protected.
#
# Each test builds a throwaway git repo (never this repo's history) with both
# bundle layouts populated, makes a test-specific commit, and invokes the gate
# with <base-sha>..<head-sha>.

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  GATE_SCRIPT="$PLUGIN_ROOT/scripts/ci/check-hook-bundle-version.sh"
  export TESTS_DIR PLUGIN_ROOT GATE_SCRIPT

  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/bundle-gate-observability.XXXXXX")"
  fi
  export TEST_DIR

  # Isolate git identity/config so a failed `git init` cannot fall back to
  # this repo's real .git/ and leak fixture commits onto the working branch.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="bats-ci"
  export GIT_AUTHOR_EMAIL="bats-ci@tcs.invalid"
  export GIT_COMMITTER_NAME="bats-ci"
  export GIT_COMMITTER_EMAIL="bats-ci@tcs.invalid"
  export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
  export GIT_COMMITTER_DATE="2026-01-01T00:00:00+0000"
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# ---------------------------------------------------------------------------
# Repo helper — populates BOTH bundle layouts so cross-bundle isolation is
# actually exercised (a change to one bundle must never trip the other's gate).
# ---------------------------------------------------------------------------

_init_repo() {
  local repo="$TEST_DIR/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q

  # git-helpers bundle: templates/githooks/ — match-everything glob.
  local hooks_dir="$repo/plugins/tcs-git-helpers/templates/githooks"
  mkdir -p "$hooks_dir"
  printf '#!/bin/bash\n# pre-commit hook v1\n' > "$hooks_dir/pre-commit"
  printf '#!/bin/bash\n# post-merge hook v1\n' > "$hooks_dir/post-merge"
  printf '# lib-bundle v1\n' > "$hooks_dir/lib-bundle.sh"
  printf 'h1\n' > "$hooks_dir/tcs-git-helpers-version"

  # observability bundle: sources and marker live in DIFFERENT directories.
  local obs_dir="$repo/plugins/tcs-helper/scripts/observability"
  local obs_marker_dir="$repo/plugins/tcs-helper/templates/observability"
  mkdir -p "$obs_dir" "$obs_marker_dir"
  printf '#!/bin/bash\n# logwrite v1\n' > "$obs_dir/logwrite.sh"
  printf '# Observability bundle\n\nInstall notes.\n' > "$obs_dir/README.md"
  printf 'o1\n' > "$obs_marker_dir/tcs-helper-observability-version"

  git -C "$repo" add .
  git -C "$repo" commit -q -m "baseline"
}

_head_sha() {
  git -C "$TEST_DIR/repo" rev-parse HEAD
}

_commit_all() {
  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "$1"
}

# ---------------------------------------------------------------------------
# 1. Observability source changed without a marker bump — FAIL
# ---------------------------------------------------------------------------

@test "observability .sh source changed without marker bump — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# logwrite v2\n' > "$TEST_DIR/repo/plugins/tcs-helper/scripts/observability/logwrite.sh"
  _commit_all "logwrite.sh v2, no marker bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 2. Same change WITH a marker bump — PASS
# ---------------------------------------------------------------------------

@test "observability .sh source changed WITH marker bump — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# logwrite v2\n' > "$TEST_DIR/repo/plugins/tcs-helper/scripts/observability/logwrite.sh"
  printf 'o2\n' > "$TEST_DIR/repo/plugins/tcs-helper/templates/observability/tcs-helper-observability-version"
  _commit_all "logwrite.sh v2 + marker bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 3. Diff touching neither bundle — PASS (unaffected)
# ---------------------------------------------------------------------------

@test "diff touching neither bundle — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf 'unrelated change\n' > "$TEST_DIR/repo/NOTES.md"
  _commit_all "unrelated file"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 4. Regression (mandatory): git-helpers pre-commit (NON-.sh) changed without
#    bump — must STILL fail. Proves the *.sh filter is not applied here.
# ---------------------------------------------------------------------------

@test "regression: git-helpers pre-commit (non-.sh) changed without bump — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# pre-commit hook v2\n' > "$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks/pre-commit"
  _commit_all "pre-commit v2, no version bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 5. Regression: git-helpers change WITH its bump — still passes.
# ---------------------------------------------------------------------------

@test "regression: git-helpers pre-commit changed WITH version bump — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# pre-commit hook v2\n' > "$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks/pre-commit"
  printf 'h2\n' > "$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version"
  _commit_all "pre-commit v2 + version bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 6. Observability README.md changed alone — PASS (extension filter proof)
# ---------------------------------------------------------------------------

@test "observability README.md changed alone — exit 0, no bump required" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '# Observability bundle\n\nInstall notes, corrected typo.\n' \
    > "$TEST_DIR/repo/plugins/tcs-helper/scripts/observability/README.md"
  _commit_all "README prose fix only"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 7. Failure output names the changed file and the marker to bump.
# ---------------------------------------------------------------------------

@test "observability failure message names changed file and marker to bump" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# logwrite v2\n' > "$TEST_DIR/repo/plugins/tcs-helper/scripts/observability/logwrite.sh"
  _commit_all "logwrite.sh v2, no marker bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash -c "bash \"$GATE_SCRIPT\" \"${base_sha}..${head_sha}\" \"$TEST_DIR/repo\" 2>&1 >/dev/null; echo \"exit:\$?\""
  [[ "$output" == *"logwrite.sh"* ]]
  [[ "$output" == *"tcs-helper-observability-version"* ]]
}
