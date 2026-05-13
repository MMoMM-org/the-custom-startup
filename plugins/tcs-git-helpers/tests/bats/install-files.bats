#!/usr/bin/env bats
#
# tests/bats/install-files.bats
#
# Integration tests for skills/git-setup/lib/install_files.sh.
# Focuses on the T1.4 additions: lib-bundle.sh copy and tcs-git-helpers-version
# file write, alongside the existing hook-copy behaviour.
#
# Assertions:
#   IF1  After install, .githooks/ contains all four hooks + lib-bundle.sh +
#        tcs-git-helpers-version
#   IF2  Every installed hook carries the substituted bundle-version banner
#        (no __HOOK_BUNDLE_VERSION__ placeholder remaining)
#   IF3  Installed .githooks/tcs-git-helpers-version equals plugin's
#        templates/githooks/tcs-git-helpers-version byte-for-byte (after trim)
#   IF4  lib-bundle.sh is copied byte-equal (no substitution applied)
#
# Spec refs:
#   - SDD §Directory Map — Repo install state (after /tcs-git-helpers:git-setup)
#   - SDD §ADR-2 — HOOK_BUNDLE_VERSION single-line version file
#   - plan/phase-1.md T1.4

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  INSTALL_SCRIPT="$PLUGIN_ROOT/skills/git-setup/lib/install_files.sh"
  TEMPLATES="$PLUGIN_ROOT/templates/githooks"
  export TESTS_DIR PLUGIN_ROOT INSTALL_SCRIPT TEMPLATES
}

setup() {
  # Each test gets its own isolated scratch dir and git repo.
  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/install-files.XXXXXX")"
  fi
  export TEST_DIR

  # Isolate git identity.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="tcs-test"
  export GIT_AUTHOR_EMAIL="test@tcs.invalid"
  export GIT_COMMITTER_NAME="tcs-test"
  export GIT_COMMITTER_EMAIL="test@tcs.invalid"
  export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
  export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

  # Build a minimal git repo for each test.
  local repo="$TEST_DIR/repo"
  mkdir -p "$repo"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.name "tcs-test"
  git -C "$repo" config user.email "test@tcs.invalid"
  git -C "$repo" config commit.gpgsign false
  printf 'initial\n' > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "feat: initial"

  REPO="$repo"
  export REPO
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# Run install_files.sh inside the test repo, pointing CLAUDE_PLUGIN_ROOT at the
# plugin root so the script can locate its templates.
_run_install() {
  run env CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" \
    bash -c "cd '$REPO' && '$INSTALL_SCRIPT'"
}

# ---------------------------------------------------------------------------
# IF1: all expected files present after install
# ---------------------------------------------------------------------------

@test "IF1 install writes all four hooks into .githooks/" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/pre-commit"  ]
  [ -f "$REPO/.githooks/pre-push"    ]
  [ -f "$REPO/.githooks/commit-msg"  ]
  [ -f "$REPO/.githooks/post-merge"  ]
}

@test "IF1 install writes lib-bundle.sh into .githooks/" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/lib-bundle.sh" ]
}

@test "IF1 install writes tcs-git-helpers-version into .githooks/" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/tcs-git-helpers-version" ]
}

# ---------------------------------------------------------------------------
# IF2: every installed hook has bundle-version banner substituted
# ---------------------------------------------------------------------------

@test "IF2 installed pre-commit contains no __HOOK_BUNDLE_VERSION__ placeholder" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/pre-commit" ]
  run grep -c '__HOOK_BUNDLE_VERSION__' "$REPO/.githooks/pre-commit"
  # grep -c returns 0 lines matching; exit code 1 means no match (what we want)
  [ "$status" -ne 0 ] || [ "$output" = "0" ]
}

@test "IF2 installed pre-push contains no __HOOK_BUNDLE_VERSION__ placeholder" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/pre-push" ]
  run grep -c '__HOOK_BUNDLE_VERSION__' "$REPO/.githooks/pre-push"
  [ "$status" -ne 0 ] || [ "$output" = "0" ]
}

@test "IF2 installed commit-msg contains no __HOOK_BUNDLE_VERSION__ placeholder" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/commit-msg" ]
  run grep -c '__HOOK_BUNDLE_VERSION__' "$REPO/.githooks/commit-msg"
  [ "$status" -ne 0 ] || [ "$output" = "0" ]
}

@test "IF2 installed post-merge contains no __HOOK_BUNDLE_VERSION__ placeholder" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/post-merge" ]
  run grep -c '__HOOK_BUNDLE_VERSION__' "$REPO/.githooks/post-merge"
  [ "$status" -ne 0 ] || [ "$output" = "0" ]
}

@test "IF2 installed pre-commit carries tcs-git-helpers-bundle banner with real version" {
  _run_install
  # The banner line must exist and contain the version token from the version file.
  local bundle_ver
  bundle_ver="$(tr -d '[:space:]' < "$TEMPLATES/tcs-git-helpers-version")"
  run grep "tcs-git-helpers-bundle: ${bundle_ver}" "$REPO/.githooks/pre-commit"
  [ "$status" -eq 0 ]
}

@test "IF2 installed pre-push carries tcs-git-helpers-bundle banner with real version" {
  _run_install
  local bundle_ver
  bundle_ver="$(tr -d '[:space:]' < "$TEMPLATES/tcs-git-helpers-version")"
  run grep "tcs-git-helpers-bundle: ${bundle_ver}" "$REPO/.githooks/pre-push"
  [ "$status" -eq 0 ]
}

@test "IF2 installed commit-msg carries tcs-git-helpers-bundle banner with real version" {
  _run_install
  local bundle_ver
  bundle_ver="$(tr -d '[:space:]' < "$TEMPLATES/tcs-git-helpers-version")"
  run grep "tcs-git-helpers-bundle: ${bundle_ver}" "$REPO/.githooks/commit-msg"
  [ "$status" -eq 0 ]
}

@test "IF2 installed post-merge carries tcs-git-helpers-bundle banner with real version" {
  _run_install
  local bundle_ver
  bundle_ver="$(tr -d '[:space:]' < "$TEMPLATES/tcs-git-helpers-version")"
  run grep "tcs-git-helpers-bundle: ${bundle_ver}" "$REPO/.githooks/post-merge"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# IF3: installed tcs-git-helpers-version byte-equals template source (after trim)
# ---------------------------------------------------------------------------

@test "IF3 installed tcs-git-helpers-version content equals template source" {
  _run_install
  local expected actual
  expected="$(tr -d '[:space:]' < "$TEMPLATES/tcs-git-helpers-version")"
  actual="$(tr -d '[:space:]' < "$REPO/.githooks/tcs-git-helpers-version")"
  [ "$actual" = "$expected" ]
}

# ---------------------------------------------------------------------------
# IF4: lib-bundle.sh is copied byte-equal (no substitution)
# ---------------------------------------------------------------------------

@test "IF4 installed lib-bundle.sh is byte-equal to template source" {
  _run_install
  run diff "$TEMPLATES/lib-bundle.sh" "$REPO/.githooks/lib-bundle.sh"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# IF5: lib-config-parser.sh is copied byte-equal to scripts/lib/config_parser.sh
# ---------------------------------------------------------------------------

@test "IF5 install writes lib-config-parser.sh into .githooks/" {
  _run_install
  [ "$status" -eq 0 ]
  [ -f "$REPO/.githooks/lib-config-parser.sh" ]
}

@test "IF5 installed lib-config-parser.sh is byte-equal to template source" {
  _run_install
  run diff "$TEMPLATES/lib-config-parser.sh" "$REPO/.githooks/lib-config-parser.sh"
  [ "$status" -eq 0 ]
}
