#!/usr/bin/env bats
#
# tests/bats/observability-skill.bats
#
# spec 018 (observability of what loads and fires), phase 2, T2.2: the
# PreToolUse (matcher: Skill) adapter. File under test:
#   plugins/tcs-helper/scripts/observability/log_skill.sh
#
# This suite is deliberately self-contained (own fixtures, own assert
# helpers) rather than extending observability-writer.bats — T2.2's BINDING
# NOTE says stay strictly inside this task's own two files, and this is a
# NEW bats file for a NEW adapter, not an addition to the writer's suite.
#
# Tests 3, 4 and 7 below are negative assertions ("no record", "no leak").
# They are trustworthy only because test 1 is a POSITIVE CONTROL that proves
# the adapter actually writes a correct record when it should: phase 1 had a
# redaction test pass vacuously because a missing function returns empty and
# empty leaks nothing. Every negative test here shares that same fixture
# style (a live adapter invocation, a real events file) specifically so a
# "nothing happens because nothing is wired up" implementation cannot pass
# test 1 and therefore cannot pass silently through the negatives either.
#
# bash 3.2 compatible.

bats_require_minimum_version 1.5.0

setup() {
  # Derived via git, not a relative "../.." count — robust to this file
  # moving and to being invoked from any cwd (same rationale as
  # observability-writer.bats's setup()).
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  ADAPTER="$REPO_ROOT/plugins/tcs-helper/scripts/observability/log_skill.sh"

  # macOS exports TMPDIR with a trailing slash; strip it so fixture paths
  # never carry a spurious "//".
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-skill.XXXXXX")"

  REPO="$TEST_DIR/myrepo"
  mkdir -p "$REPO"
  export GIT_CONFIG_GLOBAL=/dev/null
  git -C "$REPO" init -q -b main
  git -C "$REPO" config user.email "t@t"
  git -C "$REPO" config user.name "t"
  git -C "$REPO" config commit.gpgsign false
  printf 'base\n' > "$REPO/base.txt"
  git -C "$REPO" add base.txt
  git -C "$REPO" commit -q -m "base"

  DATA_DIR="$TEST_DIR/data"
  EVENTS_FILE="$DATA_DIR/observability/events.jsonl"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Drivers. $1 = payload (delivered on stdin byte-for-byte via printf '%s',
# never interpolated into a shell snippet, so quotes/backslashes in a
# payload reach the adapter exactly as the harness would deliver them).
# ---------------------------------------------------------------------------

_run_adapter_enabled() {
  ( cd "$REPO" && \
    printf '%s' "$1" | env -u CLAUDE_OBSERVABILITY_DETAIL \
      "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" \
      "$ADAPTER" )
}

_run_adapter_disabled() {
  ( cd "$REPO" && \
    printf '%s' "$1" | env -u CLAUDE_OBSERVABILITY_ENABLED \
      "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" "$ADAPTER" )
}

# bats runs a test body under `set -e`, and `! grep -q ...` only fails the
# test as the body's LAST command — not in the middle of one. Every absence
# assertion below goes through this helper instead of a bare `! grep`
# (same trap observability-writer.bats's own helpers guard against).
_assert_absent() {              # _assert_absent <needle> <file>
  if grep -qF -- "$1" "$2"; then
    printf 'LEAK: %s found in %s\n' "$1" "$2" >&2
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 1. Positive control (SDD-AC-16 / PRD F5): a Skill tool call yields exactly
#    one kind=skill record naming the skill — the CORRECT value, not mere
#    presence. Everything else in this file leans on this test being real.
# ---------------------------------------------------------------------------

@test "skill: a Skill tool call yields one kind=skill record naming the skill" {
  local payload
  payload='{"session_id":"sess-skill-1","cwd":"/x","tool_name":"Skill","tool_input":{"skill":"tcs-helper:context-bridge"}}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ -f "$EVENTS_FILE" ]

  run wc -l < "$EVENTS_FILE"
  [ "${output// /}" = "1" ]

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify record content"
  fi
  run jq -e -c . "$EVENTS_FILE"
  [ "$status" -eq 0 ]
  run jq -r '.kind' "$EVENTS_FILE"
  [ "$output" = "skill" ]
  run jq -r '.skill' "$EVENTS_FILE"
  [ "$output" = "tcs-helper:context-bridge" ]
  run jq -r '.session' "$EVENTS_FILE"
  [ "$output" = "sess-skill-1" ]
}

# ---------------------------------------------------------------------------
# 2. Redaction-critical (the central risk this task exists to hold): a
#    payload whose tool_input lacks the expected key yields a record with an
#    EMPTY skill field, and the serialised tool_input object never appears
#    anywhere in the raw record bytes. Asserted by scanning raw bytes for a
#    canary, not merely by checking `skill == ""` — a field-only check would
#    still pass if the payload leaked into some OTHER field.
# ---------------------------------------------------------------------------

@test "skill: tool_input missing the expected key yields empty skill, never the serialised object" {
  local payload
  payload='{"session_id":"sess-skill-2","cwd":"/x","tool_name":"Skill","tool_input":{"unexpected_key":"CANARY-SKILLOBJ-8675309","nested":{"deep":"CANARY-SKILLOBJ-8675309"}}}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ -f "$EVENTS_FILE" ]

  if command -v jq >/dev/null 2>&1; then
    run jq -e -c . "$EVENTS_FILE"
    [ "$status" -eq 0 ]
    run jq -r '.skill' "$EVENTS_FILE"
    [ "$output" = "" ]
  fi

  _assert_absent 'CANARY-SKILLOBJ-8675309' "$EVENTS_FILE"
  _assert_absent 'unexpected_key' "$EVENTS_FILE"
  _assert_absent 'tool_input' "$EVENTS_FILE"
}

# ---------------------------------------------------------------------------
# 3. A non-Skill tool call yields no record at all.
# ---------------------------------------------------------------------------

@test "skill: a non-Skill tool call yields no record at all" {
  local payload
  payload='{"session_id":"sess-skill-3","cwd":"/x","tool_name":"Bash","tool_input":{"command":"echo hi"}}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ ! -e "$EVENTS_FILE" ]
}

# ---------------------------------------------------------------------------
# 4. A Bash payload carrying a token-shaped canary on its command line
#    produces no record at all, and the canary appears nowhere in the log
#    file (it cannot, since no file is even created — but this pins the
#    "no record" guarantee against exactly the payload shape the SDD calls
#    out: "a Bash PreToolUse carries the full command line").
# ---------------------------------------------------------------------------

@test "skill: a Bash payload with a canary command produces no record and no leak" {
  local payload
  payload='{"session_id":"sess-skill-4","cwd":"/x","tool_name":"Bash","tool_input":{"command":"curl -H \"Authorization: Bearer CANARY-BASHTOKEN-424242\" https://example.com"}}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ ! -e "$EVENTS_FILE" ]

  if [ -e "$DATA_DIR" ]; then
    _assert_absent 'CANARY-BASHTOKEN-424242' "$EVENTS_FILE"
  fi
}

# ---------------------------------------------------------------------------
# 5. CON-4: nothing on stdout — the harness parses a hook's stdout as JSON.
# ---------------------------------------------------------------------------

@test "skill: writes nothing to stdout" {
  local payload
  payload='{"session_id":"sess-skill-5","cwd":"/x","tool_name":"Skill","tool_input":{"skill":"tcs-helper:memory-add"}}'

  run --separate-stderr _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# 6. CON-5: does not abort a `set -euo pipefail` caller and leaves the
#    caller's own exit status untouched. Real hooks in this repo already run
#    under `set -euo pipefail` (see observability-writer.bats's own test of
#    the same property on the writer) — this is not hypothetical.
# ---------------------------------------------------------------------------

@test "skill: does not abort a set -euo pipefail caller" {
  local payload
  payload='{"session_id":"sess-skill-6","cwd":"/x","tool_name":"Skill","tool_input":{"skill":"tcs-helper:memory-add"}}'

  run bash -c "
    set -euo pipefail
    cd '$REPO'
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA='$DATA_DIR'
    echo BEFORE
    printf '%s' '$payload' | '$ADAPTER'
    echo AFTER
  "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]
}

# ---------------------------------------------------------------------------
# 7. CLAUDE_OBSERVABILITY_ENABLED unset, phrased as a Skill call specifically
#    (mirroring test 1) so this proves the adapter RAN and chose not to
#    write, rather than passing because nothing was ever invoked.
# ---------------------------------------------------------------------------

@test "skill: a Skill call with CLAUDE_OBSERVABILITY_ENABLED unset produces no record" {
  local payload
  payload='{"session_id":"sess-skill-7","cwd":"/x","tool_name":"Skill","tool_input":{"skill":"tcs-helper:memory-add"}}'

  run _run_adapter_disabled "$payload"
  [ "$status" -eq 0 ]
  [ ! -e "$DATA_DIR" ]
}
