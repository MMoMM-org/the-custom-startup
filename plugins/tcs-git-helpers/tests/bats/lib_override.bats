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
        CLAUDE_ALLOW_PUSH_TO_CLOSED_PR \
        OVERRIDE_VAR OVERRIDE_MASTER CMD

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
        CLAUDE_ALLOW_PUSH_TO_CLOSED_PR \
        OVERRIDE_VAR OVERRIDE_MASTER CMD
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

# ----------------------------------------------------------------------
# _scan_tool_input_for_override — CMD prefix matching (T2.1 / spec-014)
# ----------------------------------------------------------------------

@test "_scan_tool_input_for_override: match — granular prefix in CMD → returns 0" {
  CMD="CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push"
  run _scan_tool_input_for_override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  [ "$status" -eq 0 ]
}

@test "_scan_tool_input_for_override: match — master CLAUDE_ALLOW_GIT_BAD_OPS prefix → returns 0 (ADR-4)" {
  CMD="CLAUDE_ALLOW_GIT_BAD_OPS=1 git push"
  run _scan_tool_input_for_override CLAUDE_ALLOW_GIT_BAD_OPS
  [ "$status" -eq 0 ]
}

@test "_scan_tool_input_for_override: no match — empty CMD → returns 1, no error output (CON-5)" {
  CMD=""
  run --separate-stderr _scan_tool_input_for_override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  [ "$status" -eq 1 ]
  [ -z "$stderr" ]
}

@test "_scan_tool_input_for_override: no match — unset CMD → returns 1, no error output (CON-5)" {
  unset CMD
  run --separate-stderr _scan_tool_input_for_override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  [ "$status" -eq 1 ]
  [ -z "$stderr" ]
}

@test "_scan_tool_input_for_override: no match — override token mid-command (M2-AC-REGEX anchor) → returns 1" {
  CMD="git push && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 foo"
  run _scan_tool_input_for_override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  [ "$status" -eq 1 ]
}

@test "_scan_tool_input_for_override: no match — shell-quoting trick (M2 PRD edge case) → returns 1" {
  CMD="git push' && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1; '"
  run _scan_tool_input_for_override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  [ "$status" -eq 1 ]
}

@test "_scan_tool_input_for_override: no match — =10 false-positive guard ([[:space:]]+ after =1 rejects) → returns 1" {
  CMD="CLAUDE_ALLOW_FOO=10 git push"
  run _scan_tool_input_for_override CLAUDE_ALLOW_FOO
  [ "$status" -eq 1 ]
}

@test "_scan_tool_input_for_override: no match — leading whitespace before token (regex anchored to ^) → returns 1" {
  CMD=" CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push"
  run _scan_tool_input_for_override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  [ "$status" -eq 1 ]
}

# ----------------------------------------------------------------------
# M2: Tool-Input Scan integration into _check_and_consume_override (T2.2)
# ----------------------------------------------------------------------

# M2-AC1: env-var path unchanged; scan NOT invoked when env-var present.
@test "M2-AC1: env-var set → consumed via env-var path; scan not called" {
  export CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
  CMD="unrelated command"
  # Spy on _scan_tool_input_for_override: stub increments a counter.
  _SCAN_COUNT=0
  _scan_tool_input_for_override() { _SCAN_COUNT=$((_SCAN_COUNT + 1)); return 1; }

  _check_and_consume_override PUSH_TO_CLOSED_PR
  local rc=$?

  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
  [ "$OVERRIDE_MASTER" = "0" ]
  # Sentinel written for the granular var.
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
  # Scan must not have been called (env-var short-circuit).
  [ "$_SCAN_COUNT" -eq 0 ]
}

# M2-AC2: env-var absent; CMD prefix → consumed via scan path; audit log
# records tool_input_truncated=true.
@test "M2-AC2: no env-var, CMD prefix present → consumed via scan; sentinel written; audit has tool_input_truncated" {
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  CMD="CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin foo"

  _check_and_consume_override PUSH_TO_CLOSED_PR
  local rc=$?

  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
  [ "$OVERRIDE_MASTER" = "0" ]
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
  # Audit line must exist and tool_input_truncated must be true.
  [ -f "$AUDIT_FILE" ]
  run jq -r '.tool_input_truncated' "$AUDIT_FILE"
  [ "$output" = "true" ]
}

# M2-AC3: env-var absent, CMD empty → no override; returns 1; no error output
# (CON-5); sentinel NOT written.
@test "M2-AC3: no env-var, CMD empty → returns 1; no sentinel; no stderr (CON-5)" {
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_GIT_BAD_OPS
  CMD=""

  run --separate-stderr _check_and_consume_override PUSH_TO_CLOSED_PR

  [ "$status" -eq 1 ]
  [ -z "$stderr" ]
  [ ! -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
}

# M2-AC3 variant: unset CMD → same result.
@test "M2-AC3 (unset CMD): no env-var, CMD unset → returns 1; no stderr (CON-5)" {
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_GIT_BAD_OPS CMD

  run --separate-stderr _check_and_consume_override PUSH_TO_CLOSED_PR

  [ "$status" -eq 1 ]
  [ -z "$stderr" ]
}

# M2-AC4: env-var AND CMD prefix both present → env-var path wins; scan never
# invoked (spy verifies); exactly one sentinel write.
@test "M2-AC4: env-var AND CMD prefix both present → env-var wins; scan not called" {
  export CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
  CMD="CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin main"
  _SCAN_COUNT=0
  _scan_tool_input_for_override() { _SCAN_COUNT=$((_SCAN_COUNT + 1)); return 1; }

  _check_and_consume_override PUSH_TO_CLOSED_PR
  local rc=$?

  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
  [ "$OVERRIDE_MASTER" = "0" ]
  [ "$_SCAN_COUNT" -eq 0 ]
  # Exactly one sentinel file.
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
}

# Master-override scan: CLAUDE_ALLOW_GIT_BAD_OPS=1 prefix in CMD, no env-var
# → consumed via scan path with OVERRIDE_MASTER=1; audit reflects master.
@test "M2 master scan: CLAUDE_ALLOW_GIT_BAD_OPS prefix in CMD → OVERRIDE_MASTER=1; audit master=true" {
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_GIT_BAD_OPS
  CMD="CLAUDE_ALLOW_GIT_BAD_OPS=1 git push origin main"

  _check_and_consume_override PUSH_TO_CLOSED_PR
  local rc=$?

  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_GIT_BAD_OPS" ]
  [ "$OVERRIDE_MASTER" = "1" ]
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_GIT_BAD_OPS" ]
  run jq -r '.master' "$AUDIT_FILE"
  [ "$output" = "true" ]
  run jq -r '.tool_input_truncated' "$AUDIT_FILE"
  [ "$output" = "true" ]
}

# M7 AC3 contract verified for env-var-path master at line 201-207; this
# test pins the same contract for the scan-path master so the warning can't
# silently regress when the scan branch is touched.
@test "M2 master scan: M7 AC3 LOUD stderr warning fires on scan-path master consumption" {
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_GIT_BAD_OPS
  CMD="CLAUDE_ALLOW_GIT_BAD_OPS=1 git push origin main"

  run --separate-stderr _check_and_consume_override PUSH_TO_CLOSED_PR

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"MASTER OVERRIDE"* ]]
  [[ "$stderr" == *"granular"* ]]
}

# Granular-over-master precedence preserved when both env-vars set.
@test "M2 regression: granular env-var wins over master env-var (existing behavior)" {
  export CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
  export CLAUDE_ALLOW_GIT_BAD_OPS=1

  _check_and_consume_override PUSH_TO_CLOSED_PR
  local rc=$?

  [ "$rc" -eq 0 ]
  [ "$OVERRIDE_VAR" = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
  [ "$OVERRIDE_MASTER" = "0" ]
  # Master sentinel must NOT be written.
  [ ! -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_GIT_BAD_OPS" ]
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
}

# CON-4: double-tap sentinel fires on scan-path consumption.
@test "M2 CON-4: scan-path consumption is subject to 5s double-tap sentinel" {
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_GIT_BAD_OPS
  CMD="CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin main"

  # Pre-plant a fresh sentinel (simulates a recent scan-path consumption).
  mkdir -p "$CACHE_DIR"
  printf '%s\n' "$(date +%s)" \
    > "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_PUSH_TO_CLOSED_PR"

  run --separate-stderr _check_and_consume_override PUSH_TO_CLOSED_PR

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"double-tap"* ]]
}
