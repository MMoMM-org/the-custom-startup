#!/usr/bin/env bats
#
# tests/bats/nudge-hook.bats
#
# Coverage for scripts/nudge-hook.sh — PostToolUse:Bash success-only soft nudges
#
# Spec references:
#   - PRD §Feature M9 trigger map (AC1-AC7)
#   - SDD §Building Block View — nudge-hook
#   - PRD OQ9 — 60s same-nudge dedup per repo
#   - PRD OQ10 — exit_status field fallback
#
# Constraints exercised:
#   - bash 3.2 compatible
#   - Pure bash: ZERO git / gh subprocess invocations
#   - jq fail-open: malformed stdin → exit 0 (NOT fail-closed)
#   - AC6 — no nudge on non-zero exit_status
#   - AC7 — 60s dedup per repo per rule

bats_require_minimum_version 1.5.0

# ----------------------------------------------------------------------
# Setup / teardown
# ----------------------------------------------------------------------

setup() {
  PLUGIN_ROOT="$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/nudge-hook.sh"

  # Sandbox CLAUDE_PLUGIN_DATA so dedup sentinels don't pollute real data.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-git-helpers-t33-XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  # Use a stable fake project dir for repo-hash derivation (no git calls).
  CLAUDE_PROJECT_DIR="/tmp/fake-test-repo"
  export CLAUDE_PROJECT_DIR

  # Fake plugin root for reference path formatting.
  CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  export CLAUDE_PLUGIN_ROOT
}

teardown() {
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

# Build a PostToolUse:Bash JSON envelope and pipe it to the hook.
# $1 = bash command string
# $2 = exit_status (optional; omit to simulate "field missing" → fire anyway)
_run_hook() {
  local cmd="$1"
  local exit_status="${2:-}"
  local input
  if [ -n "$exit_status" ]; then
    input=$(jq -n --arg c "$cmd" --argjson s "$exit_status" \
      '{tool_name:"Bash", tool_input:{command:$c}, exit_status:$s}')
  else
    input=$(jq -n --arg c "$cmd" \
      '{tool_name:"Bash", tool_input:{command:$c}}')
  fi
  printf '%s' "$input" | bash "$HOOK"
}

# Assert that stderr contains the given substring.
_assert_stderr_contains() {
  local needle="$1"
  [[ "$stderr" == *"$needle"* ]] \
    || { printf 'expected stderr to contain: %s\ngot: %s\n' "$needle" "$stderr" >&2; return 1; }
  return 0
}

# Assert that stderr does NOT contain the given substring.
_assert_stderr_empty() {
  [ -z "$stderr" ] \
    || { printf 'expected empty stderr, got: %s\n' "$stderr" >&2; return 1; }
  return 0
}

# ----------------------------------------------------------------------
# Sanity
# ----------------------------------------------------------------------

@test "hook script exists and is executable" {
  [ -f "$HOOK" ]
  [ -x "$HOOK" ]
}

# ----------------------------------------------------------------------
# Trigger map — AC1 (verify-base)
# ----------------------------------------------------------------------

@test "test_trigger_git_checkout_dash_b_emits_verify_base_nudge" {
  run --separate-stderr _run_hook "git checkout -b feat/my-feature"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"
  _assert_stderr_contains "branch-lifecycle.md"
}

@test "test_trigger_git_switch_dash_c_emits_verify_base_nudge" {
  run --separate-stderr _run_hook "git switch -c feat/my-feature"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"
  _assert_stderr_contains "branch-lifecycle.md"
}

# ----------------------------------------------------------------------
# Trigger map — AC2 (verify-pr-title)
# ----------------------------------------------------------------------

@test "test_trigger_gh_pr_create_emits_pr_title_nudge" {
  run --separate-stderr _run_hook "gh pr create --title 'my pr'"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "Conventional Commits"
  _assert_stderr_contains "pr-vs-commit-messages.md"
}

@test "test_trigger_git_push_dash_u_emits_pr_title_nudge" {
  run --separate-stderr _run_hook "git push -u origin feat/my-feature"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "Conventional Commits"
  _assert_stderr_contains "pr-vs-commit-messages.md"
}

# ----------------------------------------------------------------------
# Trigger map — AC3 (cleanup-after-merge)
# ----------------------------------------------------------------------

@test "test_trigger_gh_pr_merge_emits_cleanup_nudge" {
  # PRD M9 AC3: nudge suggests /tcs-git-helpers:git-audit --cleanup.
  # T5.5 spec compliance: nudge now cites stale-branch-cleanup.md reference doc.
  run --separate-stderr _run_hook "gh pr merge --squash"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "/tcs-git-helpers:git-audit --cleanup"
  _assert_stderr_contains "stale-branch-cleanup.md"
}

# ----------------------------------------------------------------------
# Trigger map — AC4 (verify-history)
# ----------------------------------------------------------------------

@test "test_trigger_git_rebase_emits_history_nudge" {
  run --separate-stderr _run_hook "git rebase main"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "git log --oneline -10"
  _assert_stderr_contains "rebase-vs-merge.md"
}

# ----------------------------------------------------------------------
# Trigger map — AC5 (verify-orig-cleanup)
# ----------------------------------------------------------------------

@test "test_trigger_git_stash_pop_emits_orig_cleanup_nudge" {
  run --separate-stderr _run_hook "git stash pop"
  [ "$status" -eq 0 ]
  _assert_stderr_contains ".orig"
  _assert_stderr_contains "working-tree-hygiene.md"
}

# ----------------------------------------------------------------------
# AC6 — no nudge on unrecognized command
# ----------------------------------------------------------------------

@test "test_no_nudge_on_unrecognized_command" {
  run --separate-stderr _run_hook "ls -la"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

# ----------------------------------------------------------------------
# AC6 — no nudge when exit_status nonzero
# ----------------------------------------------------------------------

@test "test_no_nudge_when_exit_status_nonzero" {
  # Even a trigger command should NOT emit a nudge when exit_status=1.
  run --separate-stderr _run_hook "git checkout -b feat/fail" 1
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

# Also probe tool_response.exit_code (alternate field name per PRD OQ10)
@test "test_no_nudge_when_tool_response_exit_code_nonzero" {
  local input
  input=$(jq -n --arg c "git checkout -b feat/fail" \
    '{tool_name:"Bash", tool_input:{command:$c}, tool_response:{exit_code:1}}')
  run --separate-stderr bash -c 'printf "%s" "$1" | bash "$2"' _ "$input" "$HOOK"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

# Also probe tool_response.exit_status (nested arm — third field variant per PRD OQ10)
@test "test_no_nudge_when_tool_response_exit_status_nonzero" {
  local input
  input=$(jq -n --arg c "git checkout -b feat/fail" \
    '{tool_name:"Bash", tool_input:{command:$c}, tool_response:{exit_status:1}}')
  run --separate-stderr bash -c 'printf "%s" "$1" | bash "$2"' _ "$input" "$HOOK"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

# W3 — unrelated tool_response.status (e.g. HTTP 200) must NOT suppress nudge (OQ10 fail-open)
@test "test_unrelated_status_field_does_not_suppress_nudge" {
  # A tool_response with status:200 (HTTP status, not a process exit code) must
  # not be treated as an exit-code carrier. OQ10 fail-open: field missing or
  # not an authoritatively-named exit field → fire the nudge anyway.
  # With the old bare "status" arm, status:200 was treated as exit_status=200
  # (nonzero) and the nudge was suppressed — incorrect.
  local input
  input=$(jq -n --arg c "git checkout -b feat/x" \
    '{tool_name:"Bash", tool_input:{command:$c}, tool_response:{status:200}}')
  run --separate-stderr bash -c 'printf "%s" "$1" | bash "$2"' _ "$input" "$HOOK"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"
}

# ----------------------------------------------------------------------
# AC7 — 60s same-nudge dedup
# ----------------------------------------------------------------------

@test "test_dedup_within_60s_suppresses_second_nudge" {
  # First invocation should emit the nudge.
  run --separate-stderr _run_hook "git checkout -b feat/a"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"

  # Immediately fire again — dedup sentinel is fresh (< 60s ago).
  run --separate-stderr _run_hook "git checkout -b feat/b"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

@test "test_dedup_after_60s_re_fires" {
  # Fire once to lay the sentinel.
  run --separate-stderr _run_hook "git checkout -b feat/a"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"

  # Back-date the sentinel file by 61 seconds using a past epoch.
  local sentinel_dir="$CLAUDE_PLUGIN_DATA/cache"
  # Find the sentinel (there should be exactly one nudge-verify-base file).
  local sentinel_file
  sentinel_file=$(find "$sentinel_dir" -name '*-nudge-verify-base' 2>/dev/null | head -1)
  [ -n "$sentinel_file" ] || { echo "sentinel file not found" >&2; return 1; }

  # Write an epoch that is 61 seconds in the past.
  local old_epoch
  old_epoch=$(( $(date +%s) - 61 ))
  printf '%s\n' "$old_epoch" > "$sentinel_file"

  # Second invocation should fire now (dedup expired).
  run --separate-stderr _run_hook "git checkout -b feat/b"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"
}

# ----------------------------------------------------------------------
# NO git invocations (pure bash constraint)
# ----------------------------------------------------------------------

@test "test_no_git_invocations" {
  # Install a git stub that exits 99 and writes a sentinel file.
  local stub_dir sentinel
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-t33-gitstub-XXXXXX")"
  sentinel="$stub_dir/git-was-called"

  cat > "$stub_dir/git" <<'STUB'
#!/bin/sh
printf '%s\n' "git-stub invoked: $*" > "${STUB_SENTINEL}"
exit 99
STUB
  chmod +x "$stub_dir/git"

  STUB_SENTINEL="$sentinel" PATH="$stub_dir:$PATH" \
    run --separate-stderr bash -c \
      'printf "%s" "$1" | STUB_SENTINEL="$STUB_SENTINEL" bash "$2"' \
      _ "$(jq -n --arg c 'git checkout -b feat/x' \
            '{tool_name:"Bash",tool_input:{command:$c}}')" \
      "$HOOK"

  # Hook must exit 0 regardless (nudges never block).
  [ "$status" -eq 0 ]
  # Sentinel must NOT exist: the hook did not invoke git.
  [ ! -f "$sentinel" ]
  rm -rf "$stub_dir"
}

# ----------------------------------------------------------------------
# NO gh invocations (pure bash constraint)
# ----------------------------------------------------------------------

@test "test_no_gh_invocations" {
  local stub_dir sentinel
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-t33-ghstub-XXXXXX")"
  sentinel="$stub_dir/gh-was-called"

  cat > "$stub_dir/gh" <<'STUB'
#!/bin/sh
printf '%s\n' "gh-stub invoked: $*" > "${STUB_SENTINEL}"
exit 99
STUB
  chmod +x "$stub_dir/gh"

  STUB_SENTINEL="$sentinel" PATH="$stub_dir:$PATH" \
    run --separate-stderr bash -c \
      'printf "%s" "$1" | STUB_SENTINEL="$STUB_SENTINEL" bash "$2"' \
      _ "$(jq -n --arg c 'gh pr merge --squash' \
            '{tool_name:"Bash",tool_input:{command:$c}}')" \
      "$HOOK"

  [ "$status" -eq 0 ]
  [ ! -f "$sentinel" ]
  rm -rf "$stub_dir"
}

# ----------------------------------------------------------------------
# jq fail-open — malformed stdin must not crash (mirrors T2.1 review fix)
# ----------------------------------------------------------------------

@test "test_no_jq_failclose_on_malformed_stdin" {
  run --separate-stderr bash -c 'printf "%s" "not-json{{{" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

@test "malformed stdin empty string — exits 0, no nudge" {
  run --separate-stderr bash -c 'printf "" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

@test "non-Bash tool_name — exits 0, no nudge" {
  run --separate-stderr bash -c \
    'printf "%s" "{\"tool_name\":\"Edit\",\"tool_input\":{}}" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  _assert_stderr_empty
}

# ----------------------------------------------------------------------
# Performance — p99 < 50ms (spec budget per SDD §Quality Requirements)
# ----------------------------------------------------------------------

@test "test_perf_p99_under_50ms" {
  # 100 invocations of a trigger command; collect wall-clock times; assert p99 < 50ms.
  # Using perl HiRes for sub-millisecond precision (consistent with block-bad-git-ops perf test).
  # Budget: 50ms p99 per spec (SDD §Quality Requirements perf table; phase-3.md T3.3 step 4).
  #
  # W2 fix: dedup sentinel is cleared before each iteration so every run exercises
  # the full trigger path (dedup-check → lib-source → rule-eval → emit).
  # Without this, invocations #2-#100 hit the suppressed path (cheap 2-fork early
  # exit) and produce a dishonestly low measurement.
  local cmd_json
  cmd_json=$(jq -n --arg c "git stash pop" \
    '{tool_name:"Bash",tool_input:{command:$c}}')

  local times_file
  times_file="$(mktemp "${TMPDIR:-/tmp}/tcs-t33-perf-XXXXXX")"

  local i
  for i in $(seq 1 100); do
    # Clear dedup sentinels so each iteration takes the full trigger path.
    rm -f "$CLAUDE_PLUGIN_DATA"/cache/*-nudge-* 2>/dev/null || true

    local t0 t1
    t0=$(perl -MTime::HiRes -e 'printf "%d", Time::HiRes::time()*1000')
    printf '%s' "$cmd_json" | bash "$HOOK" >/dev/null 2>&1 || true
    t1=$(perl -MTime::HiRes -e 'printf "%d", Time::HiRes::time()*1000')
    printf '%d\n' $((t1 - t0)) >> "$times_file"
  done

  # Sort and pick p99 (the 99th sample out of 100 = the 99th line when sorted).
  local p99
  p99=$(sort -n "$times_file" | sed -n '99p')
  rm -f "$times_file"

  [ -n "$p99" ] || { echo "no timing data collected" >&2; return 1; }
  [ "$p99" -lt 50 ] \
    || { echo "p99=${p99}ms exceeds 50ms spec budget" >&2; return 1; }
}

# ----------------------------------------------------------------------
# Compound command — full command string match (AC1 substring match)
# ----------------------------------------------------------------------

@test "test_compound_command_with_chained_trigger" {
  # A compound shell command: regex must match substring, not just start.
  run --separate-stderr _run_hook "cd /tmp/foo && git checkout -b feat/x"
  [ "$status" -eq 0 ]
  _assert_stderr_contains "verify the base is up-to-date"
  _assert_stderr_contains "branch-lifecycle.md"
}
