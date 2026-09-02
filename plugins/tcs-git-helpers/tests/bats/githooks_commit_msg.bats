#!/usr/bin/env bats
#
# tests/bats/githooks_commit_msg.bats
#
# Coverage for templates/githooks/commit-msg
# Test count: 35
#
# Spec references:
#   - PRD M5/AC1-AC4 — Conventional Commits enforcement
#   - SDD §Repo-side .githooks/ Templates — commit-msg
#   - SDD §.githooks/.config schema (L679-L703)
#   - PRD M11/AC1 — standalone mode (no CLAUDE_PLUGIN_ROOT needed)
#   - Quality Requirements — commit-msg p99 ≤100ms
#
# Constraints exercised:
#   - bash 3.2 compatible (no associative arrays, no mapfile)
#   - POSIX patterns ([[:space:]]+, never \s+/\b)
#   - bats `! cmd` trap: use `run` + status checks, NOT bare `! cmd`
#   - mktemp: always use "${TMPDIR:-/tmp}/...XXXXXX" form
#   - No `^.{m,n}$` bounded quantifiers — use explicit length check

bats_require_minimum_version 1.5.0

load 'lib/helpers'

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  export TESTS_DIR PLUGIN_ROOT

  HOOK="$PLUGIN_ROOT/templates/githooks/commit-msg"
  export HOOK
}

setup() {
  # Create a fresh temp dir for message files.
  TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/tcs-commit-msg.XXXXXX")"
  export TMPDIR_TEST

  # Create a minimal git repo for MERGE_HEAD tests.
  REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-commit-msg-repo.XXXXXX")"
  export REPO

  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="tcs-test"
  export GIT_AUTHOR_EMAIL="test@tcs.invalid"
  export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
  export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

  git -C "$REPO" init -q -b main
  git -C "$REPO" config commit.gpgsign false
  git -C "$REPO" config tag.gpgsign false
  git -C "$REPO" config user.name "$GIT_AUTHOR_NAME"
  git -C "$REPO" config user.email "$GIT_AUTHOR_EMAIL"

  # Minimal initial commit so GIT_DIR/.git exists properly.
  printf 'init\n' > "$REPO/README.md"
  git -C "$REPO" add README.md
  git -C "$REPO" commit -q -m "feat: initial commit"

  # Clear any TCS_* vars that might leak from harness.
  unset TCS_PROTECTED_BRANCHES TCS_HOOK_EXCLUDE_PATHS_FILE \
        TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
        TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK \
        TCS_ENABLE_PR_PUSH_CHECK \
        CLAUDE_PLUGIN_ROOT
}

teardown() {
  if [ -n "${TMPDIR_TEST:-}" ] && [ -d "$TMPDIR_TEST" ]; then
    rm -rf "$TMPDIR_TEST"
  fi
  if [ -n "${REPO:-}" ] && [ -d "$REPO" ]; then
    chmod -R u+rwX "$REPO" 2>/dev/null || true
    rm -rf "$REPO"
  fi
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Write a commit message file and return its path via $MSG_FILE.
_write_msg() {
  MSG_FILE="$(mktemp "${TMPDIR_TEST}/msg.XXXXXX")"
  printf '%s\n' "$1" > "$MSG_FILE"
  export MSG_FILE
}

# Run the hook against $MSG_FILE; captures status in $status, output in $output.
_run_hook() {
  run bash -c '
    unset CLAUDE_PLUGIN_ROOT TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
          TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK
    bash "$1" "$2" 2>&1
  ' _ "$HOOK" "$MSG_FILE"
}

# Run hook with explicit env vars.
_run_hook_env() {
  # $1 = env string to export (e.g. "TCS_REQUIRE_SCOPE=1")
  run bash -c '
    eval "export $3"
    unset CLAUDE_PLUGIN_ROOT
    bash "$1" "$2" 2>&1
  ' _ "$HOOK" "$MSG_FILE" "$1"
}

# Run hook with CLAUDE_PLUGIN_ROOT set (enables config_parser sourcing).
_run_hook_with_root() {
  run bash -c '
    export CLAUDE_PLUGIN_ROOT="$3"
    unset TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
          TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK
    bash "$1" "$2" 2>&1
  ' _ "$HOOK" "$MSG_FILE" "$PLUGIN_ROOT"
}

# ---------------------------------------------------------------------------
# 1. Default types — all 11 accept conforming commits
# ---------------------------------------------------------------------------

@test "default type 'feat' accepts conforming commit" {
  _write_msg "feat: add login endpoint"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'fix' accepts conforming commit" {
  _write_msg "fix: correct off-by-one error"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'docs' accepts conforming commit" {
  _write_msg "docs: update README"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'style' accepts conforming commit" {
  _write_msg "style: format code"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'refactor' accepts conforming commit" {
  _write_msg "refactor: extract helper function"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'test' accepts conforming commit" {
  _write_msg "test: add unit tests for parser"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'chore' accepts conforming commit" {
  _write_msg "chore: update dependencies"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'perf' accepts conforming commit" {
  _write_msg "perf: cache expensive query"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'revert' accepts conforming commit" {
  _write_msg "revert: undo breaking change"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'build' accepts conforming commit" {
  _write_msg "build: upgrade webpack to v5"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "default type 'ci' accepts conforming commit" {
  _write_msg "ci: add GitHub Actions workflow"
  _run_hook
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 2. Invalid type → reject (AC1)
# ---------------------------------------------------------------------------

@test "invalid type 'random' is rejected" {
  _write_msg "random: some change"
  _run_hook
  [ "$status" -eq 1 ]
  [[ "$output" == *"type not in allowlist"* ]] || [[ "$output" == *"Conventional"* ]] || [[ "$output" == *"format"* ]]
}

@test "format failure cites references/conventional-commits.md" {
  # Spec compliance (T5.5): error output must point user to the reference doc.
  _write_msg "random: not allowed type"
  _run_hook
  [ "$status" -ne 0 ]
  [[ "$output" == *"conventional-commits.md"* ]] \
    || { echo "expected conventional-commits.md citation, got: $output" >&2; return 1; }
}

# ---------------------------------------------------------------------------
# 3. Scoped commit → accept
# ---------------------------------------------------------------------------

@test "scoped commit 'feat(auth): ...' is accepted" {
  _write_msg "feat(auth): add OAuth2 support"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "scoped commit accepts dots and hyphens in scope" {
  _write_msg "fix(api.v2-client): handle timeout"
  _run_hook
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 4. TCS_REQUIRE_SCOPE=1 without scope → reject (AC2)
# ---------------------------------------------------------------------------

@test "TCS_REQUIRE_SCOPE=1: type-only 'feat: foo' is rejected" {
  _write_msg "feat: add new feature"
  _run_hook_env "TCS_REQUIRE_SCOPE=1"
  [ "$status" -eq 1 ]
  [[ "$output" == *"scope"* ]] || [[ "$output" == *"Conventional"* ]] || [[ "$output" == *"format"* ]]
}

# ---------------------------------------------------------------------------
# 5. TCS_REQUIRE_SCOPE=1 with scope → accept (AC2 positive)
# ---------------------------------------------------------------------------

@test "TCS_REQUIRE_SCOPE=1: scoped 'feat(auth): foo' is accepted" {
  _write_msg "feat(auth): implement JWT"
  _run_hook_env "TCS_REQUIRE_SCOPE=1"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 6. Merge subjects excluded from format check (AC3)
# ---------------------------------------------------------------------------

@test "merge subject 'Merge branch ...' is accepted" {
  _write_msg "Merge branch 'main' into feat/foo"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "merge subject 'Merge pull request ...' is accepted" {
  _write_msg "Merge pull request #42 from user/feature-branch"
  _run_hook
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 7. MERGE_HEAD file present → accept any subject (AC3)
# ---------------------------------------------------------------------------

@test "MERGE_HEAD present: any subject is accepted" {
  # Create a fake MERGE_HEAD file in the repo's .git dir.
  printf 'deadbeef1234567890abcdef1234567890abcdef\n' > "$REPO/.git/MERGE_HEAD"
  _write_msg "random not a conventional commit"

  run bash -c '
    cd "$1"
    export GIT_DIR="$1/.git"
    unset CLAUDE_PLUGIN_ROOT TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
          TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK
    bash "$2" "$3" 2>&1
  ' _ "$REPO" "$HOOK" "$MSG_FILE"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 8. [skip-format-check] in subject → accept (AC4)
# ---------------------------------------------------------------------------

@test "[skip-format-check] in subject allows any format" {
  _write_msg "random subject [skip-format-check] with extra text"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "[skip-format-check] works even with invalid type" {
  _write_msg "wip: half-done work [skip-format-check]"
  _run_hook
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 9. Length validation preserved (default TCS_MAX_SUBJECT_LENGTH=90)
# ---------------------------------------------------------------------------

@test "subject of 90 chars is accepted (boundary)" {
  # 90-char valid conventional commit: "feat: " (6) + 84 'a' chars
  local subject
  subject="feat: $(printf '%0.sa' {1..84})"
  [ "${#subject}" -eq 90 ]
  _write_msg "$subject"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "subject of 91 chars is rejected (over default limit)" {
  # 91-char subject: "feat: " (6) + 85 'a' chars
  local subject
  subject="feat: $(printf '%0.sa' {1..85})"
  [ "${#subject}" -eq 91 ]
  _write_msg "$subject"
  _run_hook
  [ "$status" -eq 1 ]
  [[ "$output" == *"too long"* ]] || [[ "$output" == *"subject"* ]]
}

# ---------------------------------------------------------------------------
# 10. TCS_MAX_SUBJECT_LENGTH override
# ---------------------------------------------------------------------------

@test "TCS_MAX_SUBJECT_LENGTH=120: 100-char subject is accepted" {
  # 100-char valid conventional commit: "feat: " (6) + 94 'a' chars
  local subject
  subject="feat: $(printf '%0.sa' {1..94})"
  [ "${#subject}" -eq 100 ]
  _write_msg "$subject"
  _run_hook_env "TCS_MAX_SUBJECT_LENGTH=120"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 11. TCS_ALLOWED_COMMIT_TYPES override
# ---------------------------------------------------------------------------

@test "TCS_ALLOWED_COMMIT_TYPES='custom1 custom2': custom1 is accepted" {
  _write_msg "custom1: do something custom"
  _run_hook_env "TCS_ALLOWED_COMMIT_TYPES='custom1 custom2'"
  [ "$status" -eq 0 ]
}

@test "TCS_ALLOWED_COMMIT_TYPES='custom1 custom2': default 'feat' is rejected" {
  _write_msg "feat: this would normally pass"
  _run_hook_env "TCS_ALLOWED_COMMIT_TYPES='custom1 custom2'"
  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 12. TCS_ENABLE_CONVENTIONAL_CHECK=0 — format not enforced but length is
# ---------------------------------------------------------------------------

@test "TCS_ENABLE_CONVENTIONAL_CHECK=0: invalid type is accepted" {
  _write_msg "random: foo (would normally fail format)"
  _run_hook_env "TCS_ENABLE_CONVENTIONAL_CHECK=0"
  [ "$status" -eq 0 ]
}

@test "TCS_ENABLE_CONVENTIONAL_CHECK=0: length still enforced (91-char subject rejected)" {
  local subject
  subject="whatever $(printf '%0.sa' {1..82})"
  [ "${#subject}" -eq 91 ]
  _write_msg "$subject"
  _run_hook_env "TCS_ENABLE_CONVENTIONAL_CHECK=0"
  [ "$status" -eq 1 ]
  [[ "$output" == *"too long"* ]] || [[ "$output" == *"subject"* ]]
}

# ---------------------------------------------------------------------------
# 13. Standalone (no CLAUDE_PLUGIN_ROOT) — defaults work
# ---------------------------------------------------------------------------

@test "standalone without CLAUDE_PLUGIN_ROOT: feat: foo is accepted" {
  _write_msg "feat: hello world"
  run bash -c '
    unset CLAUDE_PLUGIN_ROOT TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
          TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK
    bash "$1" "$2" 2>&1
  ' _ "$HOOK" "$MSG_FILE"
  [ "$status" -eq 0 ]
}

@test "standalone without CLAUDE_PLUGIN_ROOT: random: foo is rejected" {
  _write_msg "random: not conventional"
  run bash -c '
    unset CLAUDE_PLUGIN_ROOT TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
          TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK
    bash "$1" "$2" 2>&1
  ' _ "$HOOK" "$MSG_FILE"
  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 14. Version marker on line 2
# ---------------------------------------------------------------------------

@test "version marker present on line 2" {
  # Source templates carry the v__TCS_GIT_HELPERS_VERSION__ placeholder, which
  # install_files.sh substitutes with the concrete version at install time.
  # Accept either form (use ERE so it is portable to BSD grep on macOS).
  local marker='# tcs-git-helpers: v(__TCS_GIT_HELPERS_VERSION__|[0-9]+\.[0-9]+\.[0-9]+)'
  run grep -nE "$marker" "$HOOK"
  [ "$status" -eq 0 ]

  local line_num
  line_num="$(grep -nE "$marker" "$HOOK" | head -1 | cut -d: -f1)"
  [ "$line_num" -eq 2 ]
}

# ---------------------------------------------------------------------------
# 15. Breaking change marker (!) accepted
# ---------------------------------------------------------------------------

@test "breaking change 'feat!: ...' is accepted" {
  _write_msg "feat!: remove deprecated API"
  _run_hook
  [ "$status" -eq 0 ]
}

@test "breaking change with scope 'feat(api)!: ...' is accepted" {
  _write_msg "feat(api)!: redesign authentication"
  _run_hook
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 16. Empty subject → reject
# ---------------------------------------------------------------------------

@test "empty subject is rejected" {
  _write_msg ""
  _run_hook
  [ "$status" -eq 1 ]
  [[ "$output" == *"empty"* ]] || [[ "$output" == *"subject"* ]]
}

# ---------------------------------------------------------------------------
# 17. Performance: p99 < 150ms over 100 invocations (D3: .githooks/ subprocess floor)
# ---------------------------------------------------------------------------

@test "perf: p99 under 150ms over 100 invocations (passing case)" {
  _write_msg "feat: passing performance test subject"

  local times_file
  times_file="$(mktemp "${TMPDIR:-/tmp}/tcs-commit-msg-perf.XXXXXX")"

  local ms_cmd='python3 -c "import time; print(int(time.time()*1000))"'

  local i
  for i in $(seq 1 100); do
    local t_start t_end elapsed
    t_start="$(eval "$ms_cmd")"
    bash -c '
      unset CLAUDE_PLUGIN_ROOT TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
            TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK
      bash "$1" "$2" >/dev/null 2>&1
      true
    ' _ "$HOOK" "$MSG_FILE"
    t_end="$(eval "$ms_cmd")"
    elapsed=$((t_end - t_start))
    printf '%d\n' "$elapsed" >> "$times_file"
  done

  local p50 p99
  p50="$(sort -n "$times_file" | awk 'NR==50{print}')"
  p99="$(sort -n "$times_file" | awk 'NR==99{print}')"
  rm -f "$times_file"

  echo "# perf p50=${p50}ms p99=${p99}ms" >&3

  # D3: budget raised from 100ms to 150ms — see plan/phase-5.md § Deviations
  [ "$p99" -lt "$(_perf_budget 150)" ]
}
