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

# Same as _run_adapter_enabled, but the payload comes from a FILE rather
# than a shell argument — for the large-payload test below, where passing
# a 200 KB+ string through a positional parameter is unnecessary indirection
# a fixture file avoids.
_run_adapter_enabled_from_file() {
  ( cd "$REPO" && \
    env -u CLAUDE_OBSERVABILITY_DETAIL \
      "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" \
      "$ADAPTER" < "$1" )
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
  # No file at all is created — a Bash tool_name returns before the writer's
  # mkdir -p ever runs, so there is nowhere for the canary to leak into.
  # (Not an `if [ -e "$DATA_DIR" ]; then ...` guard around the grep: that
  # branch can never execute given the assertion above, so it would never
  # actually run the check it claims to make.)
  [ ! -e "$DATA_DIR" ]
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

# ---------------------------------------------------------------------------
# 8. Mutation-survivor fix: the tool-name gate must be an EXACT match, not a
#    prefix match. `[ "$tool_name" = "Skill" ]` widened to a `Skill*` glob
#    left every test above green, because no fixture used a tool_name that
#    is Skill-prefixed but a genuinely different tool.
# ---------------------------------------------------------------------------

@test "skill: a Skill-prefixed but different tool_name produces no record" {
  local payload
  payload='{"session_id":"sess-skill-8","cwd":"/x","tool_name":"SkillOther","tool_input":{"skill":"tcs-helper:memory-add"}}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ ! -e "$EVENTS_FILE" ]
}

# ---------------------------------------------------------------------------
# 9. Mutation-survivor fix: `args` must never be emitted, even when a real
#    value is present. This is more than a coverage gap — `args` is free
#    text a user typed (paths, quoted content, secrets) and it is NOT on the
#    writer's bare-name deny list (command full_command hook_command content
#    file_content transcript_path cwd prompt prompt_text response
#    response_text), so the fail-safe would not catch an adapter that starts
#    emitting it. This test is the only thing standing between a future edit
#    and a silent leak.
# ---------------------------------------------------------------------------

@test "skill: args is never emitted, even when tool_input carries a real args value" {
  local payload
  payload='{"session_id":"sess-skill-9","cwd":"/x","tool_name":"Skill","tool_input":{"skill":"tcs-helper:memory-add","args":"CANARY-ARGS-9182736450"}}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  [ -f "$EVENTS_FILE" ]

  if command -v jq >/dev/null 2>&1; then
    run jq -e -c . "$EVENTS_FILE"
    [ "$status" -eq 0 ]
    run jq -r '.skill' "$EVENTS_FILE"
    [ "$output" = "tcs-helper:memory-add" ]
    run jq -r 'has("args")' "$EVENTS_FILE"
    [ "$output" = "false" ]
  fi

  _assert_absent 'CANARY-ARGS-9182736450' "$EVENTS_FILE"
  _assert_absent '"args"' "$EVENTS_FILE"
}

# ---------------------------------------------------------------------------
# 10. Performance hazard pin (found by review, fixed centrally in
#    logwrite.sh — NOT in this file's scope). _observability_field's
#    absent-key path was measured quadratic in payload size: 40 ms / 130 ms /
#    490 ms / 1918 ms for 10 / 20 / 40 / 80 KB tails when the sought key is
#    missing. This adapter was safe only because tool_name, session_id and
#    skill all appear ahead of the free-text `args` tail in a real payload —
#    nothing pinned that fact, so a key becoming optional or the fields
#    reordering would have turned a working hook into a multi-minute stall
#    with every test above still green (none of them carries a realistically
#    large payload). The extractor now short-circuits an absent key with a
#    `case` presence check, so field order no longer decides the cost; this
#    test keeps the adapter honest either way.
#
#    Bound chosen from measurement, not guessed: a real-shaped 200 KB+
#    payload with this adapter's actual field order measured ~20-50 ms
#    end-to-end on this machine (a 2 MB payload of the same shape measured
#    ~0.4 s). The 3000 ms base below leaves that ~60-150x of headroom while
#    still catching the failure mode this test exists for: per the measured
#    curve above, an accidental fall onto a quadratic path at this payload
#    size would take single-digit to tens of seconds, not fail-at-the-margin.
#
#    Measured with a SUB-SECOND clock. `date +%s` (whole seconds) carries
#    +/-1s of ambiguity, so a run that printed "3" against a `-le 3` bound
#    could have been anything from 2.001s to 3.999s — the assertion was
#    genuinely undecided at its own boundary. BSD `date` has no %N; perl's
#    Time::HiRes is in the base install everywhere this suite runs.
#    $TCS_PERF_SLACK (4 in CI, see .github/workflows/tests.yml) scales the
#    base, and 3000x4 = 12000 ms still sits an order of magnitude below the
#    multi-minute stall this test guards against.
# ---------------------------------------------------------------------------

# Scale a wall-clock budget (in ms) by $TCS_PERF_SLACK, the convention
# plugins/tcs-git-helpers/tests/bats/lib/helpers.bash established. Duplicated
# rather than sourced: these observability suites are deliberately
# standalone, and reaching into another plugin's test library for ten lines
# would couple two suites with no other relationship.
_perf_budget_ms() {
  local budget="$1" slack="${TCS_PERF_SLACK:-1}"
  case "$slack" in
    ''|*[!0-9]*) slack=1 ;;
  esac
  [ "$slack" -lt 1 ] && slack=1
  printf '%d' $((budget * slack))
}

# Milliseconds since the epoch. q{} rather than single quotes so the same
# one-liner can be pasted inside a single-quoted `bash -c` body elsewhere.
_now_ms() {
  perl -MTime::HiRes=time -e 'printf q{%d}, time()*1000'
}

@test "skill: a 200KB+ args payload in real field order completes quickly and records correctly" {
  if ! command -v perl >/dev/null 2>&1; then
    skip "perl not available for a sub-second clock"
  fi

  local payload_file="$TEST_DIR/large_payload.json"
  local big
  big="$(printf 'x%.0s' $(seq 1 300000))"
  printf '{"session_id":"sess-skill-perf","cwd":"/x","tool_name":"Skill","tool_input":{"skill":"tcs-helper:memory-add","args":"%s"}}' \
    "$big" > "$payload_file"
  run wc -c < "$payload_file"
  [ "${output// /}" -gt 300000 ]

  local start end elapsed budget
  start="$(_now_ms)"
  run _run_adapter_enabled_from_file "$payload_file"
  end="$(_now_ms)"
  [ "$status" -eq 0 ]

  elapsed=$((end - start))
  budget="$(_perf_budget_ms 3000)"
  if [ "$elapsed" -gt "$budget" ]; then
    printf 'SLOW: %s ms against a %s ms budget\n' "$elapsed" "$budget" >&2
    return 1
  fi

  [ -f "$EVENTS_FILE" ]
  if command -v jq >/dev/null 2>&1; then
    run jq -e -c . "$EVENTS_FILE"
    [ "$status" -eq 0 ]
    run jq -r '.skill' "$EVENTS_FILE"
    [ "$output" = "tcs-helper:memory-add" ]
  fi
}
