#!/usr/bin/env bats
#
# tests/bats/bundle-gate-patterns.bats
#
# Test suite for the per-pattern extension to
# scripts/ci/check-hook-bundle-version.sh (spec-020, T1.4).
#
# Spec references:
#   - spec-020 ADR-9 — a SINGLE bundle row keyed to one marker cannot gate
#     21 independently-versioned patterns: bumping ANY one VERSION would
#     satisfy the row no matter which pattern's files actually changed.
#   - Pinned design: derive the changed pattern names from the diff itself
#     (not the working tree) and call the existing check_bundle() once per
#     changed pattern, each with its OWN marker
#     (plugins/tcs-patterns/templates/patterns/<name>/VERSION) and glob '*'.
#
# Each test builds a throwaway git repo (never this repo's history) with a
# couple of pattern directories populated, makes a test-specific commit, and
# invokes the gate with <base-sha>..<head-sha>.

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
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/bundle-gate-patterns.XXXXXX")"
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
# Assertion helper — a bare `[[ ]]` only fails a bats test when it is the
# body's LAST statement, so every substring check routes through grep -qF
# instead of relying on statement position.
# ---------------------------------------------------------------------------

_assert_contains() {
  printf '%s' "$output" | grep -qF -- "$1"
}

# ---------------------------------------------------------------------------
# Repo helper — populates two pattern directories (A and B) plus the
# pre-existing git-helpers and observability bundle layouts, so cross-bundle
# and cross-pattern isolation are both actually exercised.
# ---------------------------------------------------------------------------

_init_repo() {
  local repo="$TEST_DIR/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q

  # Pre-existing bundle 1: git-helpers githooks (match-everything glob).
  local hooks_dir="$repo/plugins/tcs-git-helpers/templates/githooks"
  mkdir -p "$hooks_dir"
  printf '#!/bin/bash\n# pre-commit hook v1\n' > "$hooks_dir/pre-commit"
  printf 'h1\n' > "$hooks_dir/tcs-git-helpers-version"

  # Pre-existing bundle 2: observability scripts (*.sh glob).
  local obs_dir="$repo/plugins/tcs-helper/scripts/observability"
  local obs_marker_dir="$repo/plugins/tcs-helper/templates/observability"
  mkdir -p "$obs_dir" "$obs_marker_dir"
  printf '#!/bin/bash\n# logwrite v1\n' > "$obs_dir/logwrite.sh"
  printf 'o1\n' > "$obs_marker_dir/tcs-helper-observability-version"

  # Pattern A: tcs-patterns/templates/patterns/pattern-a/
  local pattern_a="$repo/plugins/tcs-patterns/templates/patterns/pattern-a"
  mkdir -p "$pattern_a/reference"
  printf '# Pattern A\n' > "$pattern_a/SKILL.md"
  printf '# Pattern A reference\n' > "$pattern_a/reference/notes.md"
  printf '1\n' > "$pattern_a/VERSION"

  # Pattern B: tcs-patterns/templates/patterns/pattern-b/
  local pattern_b="$repo/plugins/tcs-patterns/templates/patterns/pattern-b"
  mkdir -p "$pattern_b/reference"
  printf '# Pattern B\n' > "$pattern_b/SKILL.md"
  printf '# Pattern B reference\n' > "$pattern_b/reference/notes.md"
  printf '1\n' > "$pattern_b/VERSION"

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
# 1. Pattern changed without its own VERSION — FAIL, names file + marker.
# ---------------------------------------------------------------------------

@test "pattern-a reference changed without its VERSION bump — exit non-zero, names file and marker" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '# Pattern A reference v2\n' > "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-a/reference/notes.md"
  _commit_all "pattern-a notes v2, no VERSION bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash -c "bash \"$GATE_SCRIPT\" \"${base_sha}..${head_sha}\" \"$TEST_DIR/repo\" 2>&1 >/dev/null; echo \"exit:\$?\""
  _assert_contains "exit:1"
  _assert_contains "pattern-a/reference/notes.md"
  _assert_contains "plugins/tcs-patterns/templates/patterns/pattern-a/VERSION"
}

# ---------------------------------------------------------------------------
# 2. Same change WITH pattern-a's VERSION bumped — PASS.
# ---------------------------------------------------------------------------

@test "pattern-a reference changed WITH its VERSION bump — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '# Pattern A reference v2\n' > "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-a/reference/notes.md"
  printf '2\n' > "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-a/VERSION"
  _commit_all "pattern-a notes v2 + VERSION bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 3. THE case that matters: pattern-a's file changed, but pattern-B's
#    VERSION bumped instead — must STILL fail. A naive "some VERSION under
#    templates/patterns/ changed" implementation would wrongly pass this.
# ---------------------------------------------------------------------------

@test "pattern-a changed, pattern-b's VERSION bumped instead — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  printf '# Pattern A reference v2\n' > "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-a/reference/notes.md"
  printf '2\n' > "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-b/VERSION"
  _commit_all "pattern-a changed, pattern-b VERSION bumped (wrong pattern)"
  local head_sha
  head_sha="$(_head_sha)"

  run bash -c "bash \"$GATE_SCRIPT\" \"${base_sha}..${head_sha}\" \"$TEST_DIR/repo\" 2>&1 >/dev/null; echo \"exit:\$?\""
  _assert_contains "exit:1"
  _assert_contains "pattern-a/reference/notes.md"
  _assert_contains "plugins/tcs-patterns/templates/patterns/pattern-a/VERSION"
}

# ---------------------------------------------------------------------------
# 4. A diff touching no pattern — exit 0, gate silent on patterns.
# ---------------------------------------------------------------------------

@test "diff touching no pattern — exit 0" {
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
# 5. Regression: the three pre-existing bundles behave exactly as before.
#    One representative case (git-helpers githooks changed without its
#    version bump, still fails) stands in for the whole pre-existing suite,
#    which bundle-gate-observability.bats and ci-bundle-gate.bats already
#    cover in full.
# ---------------------------------------------------------------------------

@test "regression: git-helpers pre-commit changed without version bump — exit non-zero" {
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
# 6. A file DELETED from a pattern without bumping its VERSION — non-zero.
#    Deletion is a mutation like any other and requires a version move.
# ---------------------------------------------------------------------------

@test "pattern-a file deleted without VERSION bump — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  rm "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-a/reference/notes.md"
  _commit_all "delete pattern-a notes.md, no VERSION bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 7. A WHOLE pattern directory deleted, VERSION included — exit 0. The
#    marker is in the changeset, so the contract is satisfied; pin this so
#    nobody later "fixes" it into a failure.
# ---------------------------------------------------------------------------

@test "whole pattern-a directory deleted including VERSION — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  rm -rf "$TEST_DIR/repo/plugins/tcs-patterns/templates/patterns/pattern-a"
  _commit_all "remove pattern-a entirely"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}
