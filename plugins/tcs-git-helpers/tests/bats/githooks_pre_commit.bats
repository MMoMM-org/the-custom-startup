#!/usr/bin/env bats
#
# tests/bats/githooks_pre_commit.bats
#
# Coverage for templates/githooks/pre-commit
#
# Spec references:
#   - SDD §Repo-side .githooks/ Templates — pre-commit (generalized exclusion list)
#   - SDD §.githooks/.config schema (L679-L703)
#   - ADR-12 — single-coder branch-protection preset (protected-branches list)
#   - PRD M5/AC1 — pre-commit handles branch protection + secret detection
#   - PRD M11/AC1 — standalone mode (no CLAUDE_PLUGIN_ROOT needed)
#   - Quality Requirements — .githooks/pre-commit p99 ≤300ms
#
# Constraints exercised:
#   - bash 3.2 compatible (no associative arrays, no mapfile)
#   - POSIX patterns ([[:space:]]+, never \s+/\b)
#   - bats `! cmd` trap: use `run` + status checks, NOT bare `! cmd`
#   - mktemp: always use "${TMPDIR:-/tmp}/...XXXXXX" form
#   - git init in tempdir: set GIT_CONFIG_GLOBAL + GIT_CONFIG_SYSTEM

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  export TESTS_DIR PLUGIN_ROOT

  HOOK="$PLUGIN_ROOT/templates/githooks/pre-commit"
  export HOOK
}

setup() {
  # Create a fresh temp repo for each test.
  REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-pre-commit.XXXXXX")"
  export REPO

  # Isolate git identity + config.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="tcs-test"
  export GIT_AUTHOR_EMAIL="test@tcs.invalid"
  export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
  export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
  export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
  export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

  # Init repo on main branch.
  git -C "$REPO" init -q -b main
  git -C "$REPO" config commit.gpgsign false
  git -C "$REPO" config tag.gpgsign false
  git -C "$REPO" config user.name "$GIT_AUTHOR_NAME"
  git -C "$REPO" config user.email "$GIT_AUTHOR_EMAIL"

  # Create an initial commit (needed for amend tests).
  printf 'initial\n' > "$REPO/README.md"
  git -C "$REPO" add README.md
  git -C "$REPO" commit -q -m "feat: initial commit"

  # Install our pre-commit hook (symlink to avoid copying on each test).
  mkdir -p "$REPO/.githooks"
  ln -sf "$HOOK" "$REPO/.githooks/pre-commit"
  chmod +x "$REPO/.githooks/pre-commit"
  git -C "$REPO" config core.hooksPath .githooks

  # Clear any TCS_* vars that might leak from harness.
  unset TCS_PROTECTED_BRANCHES TCS_HOOK_EXCLUDE_PATHS_FILE \
        TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
        TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK \
        TCS_ENABLE_PR_PUSH_CHECK TCS_ALLOW_AMEND_ON_PROTECTED \
        CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
}

teardown() {
  if [ -n "${REPO:-}" ] && [ -d "$REPO" ]; then
    chmod -R u+rwX "$REPO" 2>/dev/null || true
    rm -rf "$REPO"
  fi
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Stage a file in the test repo.
# $1 = filename (relative to repo root); $2 = content (default "test content")
_stage_file() {
  local file="$1" content="${2:-test content}"
  printf '%s\n' "$content" > "$REPO/$file"
  git -C "$REPO" add "$file"
}

# Run the pre-commit hook directly in the context of the test repo.
# Sets GIT_DIR so the hook sees the right repo.
_run_hook() {
  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    export CLAUDE_PLUGIN_ROOT="${3:-}"
    export GIT_REFLOG_ACTION="${4:-}"
    bash "$2"
  ' _ "$REPO" "$HOOK" "${CLAUDE_PLUGIN_ROOT:-}" "${GIT_REFLOG_ACTION:-}"
}

# Run the hook with a specific branch.
# Switches to the branch in the repo before running.
_switch_and_stage_and_run() {
  local branch="$1" file="${2:-safe.txt}" content="${3:-safe content}"

  # Create branch if it doesn't exist (except main which already exists).
  case "$branch" in
    main) ;;
    *)
      git -C "$REPO" checkout -q -b "$branch" 2>/dev/null || git -C "$REPO" checkout -q "$branch"
      ;;
  esac

  _stage_file "$file" "$content"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    export CLAUDE_PLUGIN_ROOT="${3:-}"
    export GIT_REFLOG_ACTION="${4:-}"
    bash "$2"
  ' _ "$REPO" "$HOOK" "${CLAUDE_PLUGIN_ROOT:-}" "${GIT_REFLOG_ACTION:-}"
}

# ---------------------------------------------------------------------------
# 1. Block commits to main by default
# ---------------------------------------------------------------------------

@test "blocks commit to main by default" {
  # Already on main from setup; stage a normal file.
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
  [[ "$output" == *"main"* ]] || [[ "$stderr" == *"main"* ]]
}

# ---------------------------------------------------------------------------
# 2. Block commits to master by default
# ---------------------------------------------------------------------------

@test "blocks commit to master by default" {
  git -C "$REPO" checkout -q -b master
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 3. Block commits to production by default
# ---------------------------------------------------------------------------

@test "blocks commit to production by default" {
  git -C "$REPO" checkout -q -b production
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 4. Block commits to release by default
# ---------------------------------------------------------------------------

@test "blocks commit to release by default" {
  git -C "$REPO" checkout -q -b release
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 5. Allow commits to feature branches
# ---------------------------------------------------------------------------

@test "allows commit to feature branch" {
  git -C "$REPO" checkout -q -b feat/foo
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 6. Block staged .env file (even on feature branch)
# ---------------------------------------------------------------------------

@test "blocks staged .env file on feature branch" {
  git -C "$REPO" checkout -q -b feat/env-test
  _stage_file ".env" "SECRET=abc123"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2" 2>&1
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
  # stderr (combined via 2>&1) should mention the secret pattern.
  [[ "$output" == *".env"* ]] || [[ "$output" == *"env"* ]] || [[ "$output" == *"secret"* ]] || [[ "$output" == *"Secret"* ]]
}

# ---------------------------------------------------------------------------
# 7. Block staged credentials.json
# ---------------------------------------------------------------------------

@test "blocks staged credentials.json" {
  git -C "$REPO" checkout -q -b feat/creds-test
  _stage_file "credentials.json" '{"api_key":"secret"}'

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2" 2>&1
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 8. Block staged .pem key
# ---------------------------------------------------------------------------

@test "blocks staged .pem key" {
  git -C "$REPO" checkout -q -b feat/pem-test
  _stage_file "secret.pem" "-----BEGIN RSA PRIVATE KEY-----"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2" 2>&1
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 9. Block staged id_rsa (SSH key)
# ---------------------------------------------------------------------------

@test "blocks staged id_rsa" {
  git -C "$REPO" checkout -q -b feat/ssh-test
  _stage_file "id_rsa" "-----BEGIN OPENSSH PRIVATE KEY-----"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2" 2>&1
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 10. Exclusion list bypasses secret block
# ---------------------------------------------------------------------------

@test "exclude-paths bypasses secret block for matched file" {
  git -C "$REPO" checkout -q -b feat/exclude-test

  # Write the exclude-paths file with the pattern.
  printf 'tests/fixtures/.env\n' > "$REPO/.githooks/exclude-paths"

  # Stage the excluded .env file.
  mkdir -p "$REPO/tests/fixtures"
  _stage_file "tests/fixtures/.env" "TEST_ONLY=true"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 11a. TCS_PROTECTED_BRANCHES config override — main NOT in custom list → allowed
# ---------------------------------------------------------------------------

@test "TCS_PROTECTED_BRANCHES config override: main not in custom list is allowed" {
  # Config says only staging|trunk are protected.
  mkdir -p "$REPO/.githooks"
  printf 'TCS_PROTECTED_BRANCHES=staging|trunk\n' > "$REPO/.githooks/.config"

  # On main (not in custom list) — should be allowed.
  _stage_file "safe.txt"

  # We need CLAUDE_PLUGIN_ROOT to point to our plugin so config_parser.sh is sourced.
  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    export CLAUDE_PLUGIN_ROOT="$3"
    unset GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK" "$PLUGIN_ROOT"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 11b. TCS_PROTECTED_BRANCHES config override — staging IS in custom list → blocked
# ---------------------------------------------------------------------------

@test "TCS_PROTECTED_BRANCHES config override: staging in custom list is blocked" {
  # Config says only staging|trunk are protected.
  mkdir -p "$REPO/.githooks"
  printf 'TCS_PROTECTED_BRANCHES=staging|trunk\n' > "$REPO/.githooks/.config"

  git -C "$REPO" checkout -q -b staging
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    export CLAUDE_PLUGIN_ROOT="$3"
    unset GIT_REFLOG_ACTION
    bash "$2"
  ' _ "$REPO" "$HOOK" "$PLUGIN_ROOT"

  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 12. Amend on protected with TCS_ALLOW_AMEND_ON_PROTECTED=1 → allowed
# ---------------------------------------------------------------------------

@test "amend on protected branch with TCS_ALLOW_AMEND_ON_PROTECTED=1 is allowed" {
  mkdir -p "$REPO/.githooks"
  printf 'TCS_ALLOW_AMEND_ON_PROTECTED=1\n' > "$REPO/.githooks/.config"

  # On main; stage a file; simulate amend via GIT_REFLOG_ACTION.
  _stage_file "amend-file.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    export CLAUDE_PLUGIN_ROOT="$3"
    export GIT_REFLOG_ACTION="commit (amend)"
    bash "$2"
  ' _ "$REPO" "$HOOK" "$PLUGIN_ROOT"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 13. Amend on protected without override → blocked
# ---------------------------------------------------------------------------

@test "amend on protected branch without TCS_ALLOW_AMEND_ON_PROTECTED is blocked" {
  # No .config (uses defaults — TCS_ALLOW_AMEND_ON_PROTECTED=0).
  _stage_file "amend-file.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    export CLAUDE_PLUGIN_ROOT="$3"
    export GIT_REFLOG_ACTION="commit (amend)"
    bash "$2"
  ' _ "$REPO" "$HOOK" "$PLUGIN_ROOT"

  # Even though it's an amend, protected branch still blocks it.
  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 14. Version marker present on line 2
# ---------------------------------------------------------------------------

@test "version marker present as first comment line (line 2)" {
  # Line 1 = shebang, line 2 = version marker.
  run grep -n '# tcs-git-helpers: v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' "$HOOK"
  [ "$status" -eq 0 ]

  # The match must be on line 2.
  local line_num
  line_num="$(grep -n '# tcs-git-helpers: v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' "$HOOK" | head -1 | cut -d: -f1)"
  [ "$line_num" -eq 2 ]
}

# ---------------------------------------------------------------------------
# 15. Performance: p99 ≤ 300ms over 100 invocations
# ---------------------------------------------------------------------------

@test "perf: p99 under 300ms over 100 invocations (passing case)" {
  git -C "$REPO" checkout -q -b feat/perf-test

  # Stage a safe file once; the hook exits 0 on this branch.
  _stage_file "safe.txt"

  local times_file
  times_file="$(mktemp "${TMPDIR:-/tmp}/tcs-pre-commit-perf.XXXXXX")"

  # Use python3 for millisecond timestamps (BSD date on macOS does not support %N).
  local ms_cmd='python3 -c "import time; print(int(time.time()*1000))"'

  local i
  for i in $(seq 1 100); do
    local t_start t_end elapsed
    t_start="$(eval "$ms_cmd")"
    bash -c '
      cd "$1"
      export GIT_DIR="$1/.git"
      unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION
      bash "$2" >/dev/null 2>&1
      true
    ' _ "$REPO" "$HOOK"
    t_end="$(eval "$ms_cmd")"
    elapsed=$((t_end - t_start))
    printf '%d\n' "$elapsed" >> "$times_file"
  done

  # Sort and pick p99 (index 98 in 0-based; line 99 in 1-based sorted list).
  local p50 p99
  p50="$(sort -n "$times_file" | awk 'NR==50{print}')"
  p99="$(sort -n "$times_file" | awk 'NR==99{print}')"
  rm -f "$times_file"

  echo "# perf p50=${p50}ms p99=${p99}ms" >&3

  [ "$p99" -lt 300 ]
}

# ---------------------------------------------------------------------------
# 16. Standalone: works without CLAUDE_PLUGIN_ROOT (hard-coded defaults)
# ---------------------------------------------------------------------------

@test "standalone without CLAUDE_PLUGIN_ROOT: blocks main, allows feat branch" {
  # Test 16a: block on main (default protected).
  _stage_file "safe.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION TCS_PROTECTED_BRANCHES
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 1 ]

  # Test 16b: allow on feat branch.
  git -C "$REPO" checkout -q -b feat/standalone-test
  _stage_file "safe2.txt"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT GIT_REFLOG_ACTION TCS_PROTECTED_BRANCHES
    bash "$2"
  ' _ "$REPO" "$HOOK"

  [ "$status" -eq 0 ]
}
