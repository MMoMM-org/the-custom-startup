#!/usr/bin/env bats
#
# tests/bats/protect-git-internals.bats
#
# Tests for scripts/protect-git-internals.sh — PreToolUse:Edit|Write|
# NotebookEdit guard for git-internal paths (.githooks/*, .git/config,
# .git/hooks/*).
#
# Spec references:
#   - SDD §Implementation Examples (ADR-11 sentinel logic)
#   - research/security.md §5 (Hook-bypass surface; block edits to
#     .githooks/*, .git/config, .git/hooks/*)
#   - ADR-11 (TCS_GIT_HELPERS_SETUP_ACTIVE env-var sentinel)
#
# Constraints exercised here:
#   - bash 3.2 compatible
#   - JSON in: stdin → tool_input.file_path
#   - JSON out: hookSpecificOutput.permissionDecision (deny on match)
#   - Exit 0 always; allow path emits no stdout

bats_require_minimum_version 1.5.0

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/protect-git-internals.sh"

  # macOS mktemp ignores $TMPDIR by default; pass it explicitly so the
  # sandbox-writable path is honored.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-protect-bats.XXXXXX")"
  export CLAUDE_PLUGIN_DATA
  export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"

  # Sandbox a tiny git repo so audit_log has a `repo`/`branch` to record.
  REPO="$CLAUDE_PLUGIN_DATA/repo"
  mkdir -p "$REPO"
  (
    cd "$REPO" || exit 1
    git init -q
    git config user.email "t@t"
    git config user.name "t"
    : > a
    git add a
    git commit -q -m init
  )
  cd "$REPO" || return 1

  # Defensive: ensure the sentinel does not leak in from the caller.
  unset TCS_GIT_HELPERS_SETUP_ACTIVE
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
  unset TCS_GIT_HELPERS_SETUP_ACTIVE
}

# Build a tool_input JSON, pipe into the hook, capture status+stdout via run.
_invoke_hook() {
  local tool="$1" path="$2"
  local payload
  payload="$(jq -nc --arg t "$tool" --arg p "$path" \
    '{tool_name:$t,tool_input:{file_path:$p}}')"
  printf '%s' "$payload" | "$HOOK"
}

# ----------------------------------------------------------------------
# Sensitive paths — denied when sentinel unset (ADR-11)
# ----------------------------------------------------------------------

@test "Edit <repo>/.githooks/pre-commit denied when sentinel unset" {
  run _invoke_hook Edit "$REPO/.githooks/pre-commit"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
  echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"'
}

@test "Write <repo>/.githooks/.config denied when sentinel unset" {
  run _invoke_hook Write "$REPO/.githooks/.config"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}

@test "Edit <repo>/.git/config denied when sentinel unset" {
  run _invoke_hook Edit "$REPO/.git/config"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}

@test "Edit <repo>/.git/hooks/post-merge denied when sentinel unset" {
  run _invoke_hook Edit "$REPO/.git/hooks/post-merge"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}

@test "denial reason mentions TCS_GIT_HELPERS_SETUP_ACTIVE" {
  run _invoke_hook Edit "$REPO/.githooks/pre-commit"
  [ "$status" -eq 0 ]
  echo "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' \
    | grep -q "TCS_GIT_HELPERS_SETUP_ACTIVE"
}

@test "denial reason names the matched file path" {
  run _invoke_hook Edit "$REPO/.git/config"
  [ "$status" -eq 0 ]
  echo "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' \
    | grep -qF "$REPO/.git/config"
}

# ----------------------------------------------------------------------
# Sentinel set — sensitive paths allowed (ADR-11 setup-skill case)
# ----------------------------------------------------------------------

@test "Edit <repo>/.githooks/pre-commit allowed when sentinel=1" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _invoke_hook Edit "$REPO/.githooks/pre-commit"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Write <repo>/.githooks/.config allowed when sentinel=1" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _invoke_hook Write "$REPO/.githooks/.config"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Edit <repo>/.git/config allowed when sentinel=1" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _invoke_hook Edit "$REPO/.git/config"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Edit <repo>/.git/hooks/post-merge allowed when sentinel=1" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _invoke_hook Edit "$REPO/.git/hooks/post-merge"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Non-sensitive paths — always allowed (sentinel-agnostic)
# ----------------------------------------------------------------------

@test "Edit <repo>/src/foo.ts allowed (sentinel unset)" {
  run _invoke_hook Edit "$REPO/src/foo.ts"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Write <repo>/README.md allowed (sentinel unset)" {
  run _invoke_hook Write "$REPO/README.md"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-sensitive path also allowed when sentinel=1" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _invoke_hook Edit "$REPO/src/foo.ts"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "deeply-nested non-sensitive path allowed" {
  run _invoke_hook Edit "$REPO/a/b/c/d/e.txt"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# NotebookEdit — same semantics as Edit/Write
# ----------------------------------------------------------------------

@test "NotebookEdit on .git/hooks/foo denied when sentinel unset" {
  run _invoke_hook NotebookEdit "$REPO/.git/hooks/post-merge"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}

@test "NotebookEdit on .git/hooks/foo allowed when sentinel=1" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _invoke_hook NotebookEdit "$REPO/.git/hooks/post-merge"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Tool other than Edit/Write/NotebookEdit — untouched
# ----------------------------------------------------------------------

@test "Bash tool input is untouched (exit 0, no stdout)" {
  local payload='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c 'printf "%s" "$1" | "$2"' _ "$payload" "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Edge: empty file_path → allow silently (nothing to check)
# ----------------------------------------------------------------------

@test "empty tool_input.file_path → allow silently" {
  local payload='{"tool_name":"Edit","tool_input":{}}'
  run bash -c 'printf "%s" "$1" | "$2"' _ "$payload" "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Sentinel value other than literal "1" → still deny
# (ADR-11 contracts the value as exactly "1"; defensive against typos)
# ----------------------------------------------------------------------

@test "sentinel set to '0' → deny (only literal '1' allows)" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=0
  run _invoke_hook Edit "$REPO/.git/config"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}

@test "sentinel set to 'true' → deny (only literal '1' allows)" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=true
  run _invoke_hook Edit "$REPO/.git/config"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}

@test "sentinel set to '' → deny" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=""
  run _invoke_hook Edit "$REPO/.git/config"
  [ "$status" -eq 0 ]
  echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
}
