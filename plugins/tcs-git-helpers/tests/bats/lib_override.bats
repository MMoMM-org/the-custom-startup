#!/usr/bin/env bats
#
# tests/bats/lib_override.bats
#
# Tests for scripts/lib/override.sh — single-shot env-var override
# consumption with a 5-second sentinel double-tap window.
#
# Spec references:
#   - SDD §Implementation Examples (`_check_and_consume_override` walkthrough)
#   - ADR-5 (env-var consumption + 5s sentinel approximates true single-shot)
#   - PRD M7 AC3 (master override emits loud stderr warning)
#   - PRD M12 AC1-AC5 (single-shot semantics + audit trail; audit failure
#                       does NOT block underlying hook decision)
#
# Constraints exercised here:
#   - bash 3.2 compatible
#   - Sentinel under ${CLAUDE_PLUGIN_DATA}/cache/override-consumed-<env_var>
#   - mkdir failure on sentinel dir → graceful degradation (still consumes)
#   - audit_log failure must not block consumption

bats_require_minimum_version 1.5.0

setup() {
  # macOS mktemp ignores $TMPDIR by default; pass it explicitly so the
  # sandbox-writable path is honored.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-override-bats.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  LIB="$PLUGIN_ROOT/scripts/lib/override.sh"
  AUDIT_LIB="$PLUGIN_ROOT/scripts/lib/audit_log.sh"

  CACHE_DIR="$CLAUDE_PLUGIN_DATA/cache"
  AUDIT_FILE="$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl"

  # Sandbox a tiny git repo so audit_log has a `repo`/`branch` to record
  # and so `_check_and_consume_override` callers' git context is real.
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

  # Defensive: ensure no stray override env-vars leak in from the caller.
  unset CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_GIT_BAD_OPS \
        OVERRIDE_VAR OVERRIDE_MASTER

  # shellcheck source=/dev/null
  source "$AUDIT_LIB"
  # shellcheck source=/dev/null
  source "$LIB"
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
  unset CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_GIT_BAD_OPS \
        OVERRIDE_VAR OVERRIDE_MASTER
}

# ----------------------------------------------------------------------
# Sourcing
# ----------------------------------------------------------------------

@test "lib loads without errors" {
  source "$LIB"
}

# ----------------------------------------------------------------------
# env-var unset → return 1 (no consumption)
# ----------------------------------------------------------------------

@test "no override set → returns 1, no sentinel, no audit" {
  run _check_and_consume_override RESET_HARD
  [ "$status" -eq 1 ]
  [ ! -e "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD" ]
  [ ! -f "$AUDIT_FILE" ]
}

@test "missing rule arg → returns 1" {
  run _check_and_consume_override
  [ "$status" -eq 1 ]
}

# ----------------------------------------------------------------------
# Granular env-var set + no sentinel → consumed
# ----------------------------------------------------------------------

@test "granular env-var set + no sentinel → returns 0, sentinel written, OVERRIDE_VAR/OVERRIDE_MASTER set" {
  export CLAUDE_ALLOW_RESET_HARD=1
  _check_and_consume_override RESET_HARD
  local rc=$?
  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_RESET_HARD" ]
  [ "$OVERRIDE_MASTER" = "0" ]
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD" ]
}

@test "granular consumption emits stderr 'override consumed'" {
  export CLAUDE_ALLOW_RESET_HARD=1
  run --separate-stderr _check_and_consume_override RESET_HARD
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"override consumed"* ]]
  [[ "$stderr" == *"CLAUDE_ALLOW_RESET_HARD"* ]]
}

@test "granular consumption appends one audit_log line with env_var/master" {
  export CLAUDE_ALLOW_RESET_HARD=1
  _check_and_consume_override RESET_HARD
  [ -f "$AUDIT_FILE" ]
  run wc -l < "$AUDIT_FILE"
  [ "${output// /}" = "1" ]
  run jq -r '.env_var' "$AUDIT_FILE"
  [ "$output" = "CLAUDE_ALLOW_RESET_HARD" ]
  run jq -r '.master' "$AUDIT_FILE"
  [ "$output" = "false" ]
}

# ----------------------------------------------------------------------
# Sentinel <5s old → double-tap denial
# ----------------------------------------------------------------------

@test "sentinel <5s old → double-tap denial (returns 1, stderr explains)" {
  export CLAUDE_ALLOW_RESET_HARD=1
  mkdir -p "$CACHE_DIR"
  printf '%s\n' "$(date +%s)" > "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD"

  run --separate-stderr _check_and_consume_override RESET_HARD
  [ "$status" -eq 1 ]
  [[ "$stderr" == *"double-tap"* ]]
  [[ "$stderr" == *"CLAUDE_ALLOW_RESET_HARD"* ]]
}

@test "double-tap denial does NOT append an audit line" {
  export CLAUDE_ALLOW_RESET_HARD=1
  mkdir -p "$CACHE_DIR"
  printf '%s\n' "$(date +%s)" > "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD"

  _check_and_consume_override RESET_HARD || true
  [ ! -f "$AUDIT_FILE" ]
}

# ----------------------------------------------------------------------
# Sentinel >5s old → consumed normally (sentinel-content based)
# ----------------------------------------------------------------------

@test "sentinel >5s old → consumed normally (returns 0, sentinel refreshed)" {
  export CLAUDE_ALLOW_RESET_HARD=1
  mkdir -p "$CACHE_DIR"
  local old_ts
  old_ts=$(($(date +%s) - 10))
  printf '%s\n' "$old_ts" > "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD"

  _check_and_consume_override RESET_HARD
  local rc=$?
  [ "$rc" -eq 0 ]

  # Sentinel content refreshed to a strictly more recent epoch.
  local new_ts
  new_ts=$(cat "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD")
  [ "$new_ts" -gt "$old_ts" ]
}

@test "sentinel with non-numeric content → treated as ts=0, consumed normally" {
  export CLAUDE_ALLOW_RESET_HARD=1
  mkdir -p "$CACHE_DIR"
  printf 'corrupt\n' > "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD"

  _check_and_consume_override RESET_HARD
  local rc=$?
  [ "$rc" -eq 0 ]
}

# ----------------------------------------------------------------------
# Master override (CLAUDE_ALLOW_GIT_BAD_OPS) — M7 AC3
# ----------------------------------------------------------------------

@test "master CLAUDE_ALLOW_GIT_BAD_OPS=1 + granular unset → consumed, OVERRIDE_MASTER=1" {
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  _check_and_consume_override RESET_HARD
  local rc=$?
  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_GIT_BAD_OPS" ]
  [ "$OVERRIDE_MASTER" = "1" ]
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_GIT_BAD_OPS" ]
}

@test "master override emits LOUD stderr warning per M7 AC3" {
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  run --separate-stderr _check_and_consume_override RESET_HARD
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"MASTER OVERRIDE"* ]]
  [[ "$stderr" == *"granular"* ]]
}

@test "master override stderr matches PRD M7 AC3 VERBATIM (incl. backticks)" {
  # Pin the exact AC3 string — the backticks around `CLAUDE_ALLOW_<X>=1` are
  # part of the contract per requirements.md line 192. Don't relax this
  # assertion: the looser "granular" / "MASTER OVERRIDE" matches above let
  # backticks regress silently.
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  run --separate-stderr _check_and_consume_override RESET_HARD
  [ "$status" -eq 0 ]
  [[ "$stderr" == *'`CLAUDE_ALLOW_<X>=1`'* ]]
  [[ "$stderr" == *'⚠ MASTER OVERRIDE — strongly prefer granular `CLAUDE_ALLOW_<X>=1`'* ]]
}

@test "master override audit line has master:true" {
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  _check_and_consume_override RESET_HARD
  run jq -r '.master' "$AUDIT_FILE"
  [ "$output" = "true" ]
  run jq -r '.env_var' "$AUDIT_FILE"
  [ "$output" = "CLAUDE_ALLOW_GIT_BAD_OPS" ]
}

# ----------------------------------------------------------------------
# Granular wins over master when both set (M12 §Edge Cases)
# ----------------------------------------------------------------------

@test "granular + master both set → granular wins (OVERRIDE_MASTER=0, master not consumed)" {
  export CLAUDE_ALLOW_RESET_HARD=1
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  _check_and_consume_override RESET_HARD
  local rc=$?
  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_RESET_HARD" ]
  [ "$OVERRIDE_MASTER" = "0" ]
  # Master sentinel must NOT be written when granular wins.
  [ ! -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_GIT_BAD_OPS" ]
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD" ]
}

# ----------------------------------------------------------------------
# Graceful degradation: mkdir failure on sentinel dir
# ----------------------------------------------------------------------

@test "mkdir failure on sentinel dir → returns 0 (graceful degradation, stderr warns)" {
  export CLAUDE_ALLOW_RESET_HARD=1
  # Squat the cache path with a regular file so `mkdir -p cache/` fails.
  : > "$CLAUDE_PLUGIN_DATA/cache"

  run --separate-stderr _check_and_consume_override RESET_HARD
  [ "$status" -eq 0 ]
  # Still emits the "override consumed" line.
  [[ "$stderr" == *"override consumed"* ]]
}

# ----------------------------------------------------------------------
# Audit failure must NOT block consumption (M12 AC5)
# ----------------------------------------------------------------------

@test "audit_log returning non-zero does not block consumption" {
  export CLAUDE_ALLOW_RESET_HARD=1
  # Override _audit_log with a stub that fails. _check_and_consume_override
  # must still return 0 and emit "override consumed".
  _audit_log() { return 1; }

  run --separate-stderr _check_and_consume_override RESET_HARD
  unset -f _audit_log

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"override consumed"* ]]
}

@test "audit_log entirely undefined does not block consumption" {
  export CLAUDE_ALLOW_RESET_HARD=1
  # Source override.sh in a fresh subshell with NO audit_log loaded. The
  # consumption must still succeed; we just lose the audit line.
  run --separate-stderr bash -c '
    set -e
    LIB="'"$LIB"'"
    export CLAUDE_PLUGIN_DATA="'"$CLAUDE_PLUGIN_DATA"'-noaudit"
    mkdir -p "$CLAUDE_PLUGIN_DATA"
    # shellcheck source=/dev/null
    . "$LIB"
    _check_and_consume_override RESET_HARD
  '
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"override consumed"* ]]
}
