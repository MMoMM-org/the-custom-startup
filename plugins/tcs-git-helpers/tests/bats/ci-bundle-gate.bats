#!/usr/bin/env bats
#
# tests/bats/ci-bundle-gate.bats
#
# Test suite for scripts/ci/check-hook-bundle-version.sh
#
# Spec references:
#   - SDD §ADR-7 — CI enforcement of maintainer contract (CON-4)
#   - PRD §AC-F6.3 — CI gate fails when templates/githooks/* changed without version bump
#   - SDD §Risks / Maintainer forgets to bump
#
# Rule enforced:
#   If any file under plugins/tcs-git-helpers/templates/githooks/ changed in the diff
#   range AND plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version did NOT
#   change in the same range, the script must exit non-zero with a stderr message
#   naming the offending files and telling the maintainer what to do.
#
# Each test:
#   - Creates a throwaway git repo in BATS_TEST_TMPDIR
#   - Establishes a baseline commit (becomes <base>)
#   - Makes a test-specific change commit (becomes <head>)
#   - Invokes the gate script with <base-sha>..<head-sha>
#   - Asserts exit code and (on failure) stderr content

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
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/ci-bundle-gate.XXXXXX")"
  fi
  export TEST_DIR

  # Isolate git identity so tests do not depend on global config.
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
# Repo helpers
# ---------------------------------------------------------------------------

# Initialize a throwaway repo with the canonical structure:
#   plugins/tcs-git-helpers/templates/githooks/
#     post-merge
#     tcs-git-helpers-version
# Returns nothing; repo is in $TEST_DIR/repo.
_init_repo() {
  local repo="$TEST_DIR/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q

  # Populate the githooks template dir that the gate script watches.
  local hooks_dir="$repo/plugins/tcs-git-helpers/templates/githooks"
  mkdir -p "$hooks_dir"

  printf '#!/bin/bash\n# post-merge hook v1\n' > "$hooks_dir/post-merge"
  printf 'h1\n' > "$hooks_dir/tcs-git-helpers-version"

  git -C "$repo" add .
  git -C "$repo" commit -q -m "baseline"
}

# Return the SHA of HEAD in $TEST_DIR/repo.
_head_sha() {
  git -C "$TEST_DIR/repo" rev-parse HEAD
}

# ---------------------------------------------------------------------------
# T1: No githooks/* changes → exit 0
# ---------------------------------------------------------------------------

@test "no templates/githooks/* changes in diff range — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  # Change an unrelated file.
  printf 'README content\n' > "$TEST_DIR/repo/README.md"
  git -C "$TEST_DIR/repo" add README.md
  git -C "$TEST_DIR/repo" commit -q -m "add readme"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# T2: Hook template change + version bump → exit 0
# ---------------------------------------------------------------------------

@test "hook template change with tcs-git-helpers-version bump — exit 0" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  printf '#!/bin/bash\n# post-merge hook v2\n' > "$hooks_dir/post-merge"
  printf 'h2\n' > "$hooks_dir/tcs-git-helpers-version"

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "bump hook + version"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# T3: Hook template change WITHOUT version bump → exit non-zero
# ---------------------------------------------------------------------------

@test "hook template change without version bump — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  printf '#!/bin/bash\n# post-merge hook v2 — important fix\n' > "$hooks_dir/post-merge"
  # version file intentionally left unchanged at h1

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "fix hook without bumping version"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo" 2>&1
  [ "$status" -ne 0 ]
}

@test "hook template change without version bump — stderr names the offending file" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  printf '#!/bin/bash\n# post-merge hook changed\n' > "$hooks_dir/post-merge"

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "change hook no version bump"
  local head_sha
  head_sha="$(_head_sha)"

  # Capture stderr via 2>&1 redirect inside run subshell.
  run bash -c "bash \"$GATE_SCRIPT\" \"${base_sha}..${head_sha}\" \"$TEST_DIR/repo\" 2>&1 >/dev/null; echo \"exit:$?\""
  [[ "$output" == *"post-merge"* ]]
}

@test "hook template change without version bump — stderr tells maintainer what to do" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  printf '#!/bin/bash\n# pre-commit hook changed\n' > "$hooks_dir/pre-commit"
  mkdir -p "$hooks_dir"
  printf '#!/bin/bash\n# pre-commit\n' > "$hooks_dir/pre-commit"

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "change pre-commit no version bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash -c "bash \"$GATE_SCRIPT\" \"${base_sha}..${head_sha}\" \"$TEST_DIR/repo\" 2>&1 >/dev/null; echo \"exit:$?\""
  [[ "$output" == *"tcs-git-helpers-version"* ]]
}

# ---------------------------------------------------------------------------
# T4: lib-bundle.sh change WITHOUT version bump → exit non-zero
# ---------------------------------------------------------------------------

@test "lib-bundle.sh change without version bump — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  printf '# lib-bundle.sh v2\n_resolve_data_dir() { :; }\n' > "$hooks_dir/lib-bundle.sh"

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "update lib-bundle without bumping version"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
}

@test "lib-bundle.sh change without version bump — stderr names lib-bundle.sh" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  printf '# lib-bundle.sh changed\n' > "$hooks_dir/lib-bundle.sh"

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "lib-bundle change no version"
  local head_sha
  head_sha="$(_head_sha)"

  run bash -c "bash \"$GATE_SCRIPT\" \"${base_sha}..${head_sha}\" \"$TEST_DIR/repo\" 2>&1 >/dev/null; echo \"exit:$?\""
  [[ "$output" == *"lib-bundle.sh"* ]]
}

# ---------------------------------------------------------------------------
# T5: Comment-only / whitespace-only change → still exit non-zero
# (SDD ADR-7 trade-off: any diff in the dir counts)
# ---------------------------------------------------------------------------

@test "comment-only change to hook template without version bump — exit non-zero" {
  _init_repo
  local base_sha
  base_sha="$(_head_sha)"

  local hooks_dir="$TEST_DIR/repo/plugins/tcs-git-helpers/templates/githooks"
  # Only change is a comment line — functional code unchanged.
  printf '#!/bin/bash\n# post-merge hook v1\n# added a comment\n' > "$hooks_dir/post-merge"

  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "comment-only change no version bump"
  local head_sha
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
}
