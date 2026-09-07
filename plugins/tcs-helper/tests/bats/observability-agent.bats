#!/usr/bin/env bats
#
# tests/bats/observability-agent.bats
#
# spec 018 (observability of what loads and fires), T2.3: the SubagentStart
# adapter. This suite covers plugins/tcs-helper/scripts/observability/log_agent.sh
# ONLY -- it must not assume anything about the instructions or skill adapters
# (T2.1, T2.2), which are separate files under construction in parallel.
#
# The adapter is invoked exactly as the harness would invoke it: as an
# external command, payload JSON on stdin, nothing sourced by the test except
# through that process boundary. This is deliberate -- CON-4/CON-5 (nothing
# on stdout, the caller's exit status untouched) are guarantees about the
# PROCESS, not about a sourced function, and can only be pinned by actually
# exec'ing the script.
#
# `agent_type` and `agent_id` are the two payload keys confirmed against the
# official Claude Code hooks documentation (see log_agent.sh's own header
# comment for the citation). The parent-agent payload key is UNVERIFIED --
# T2.4 is where that gets confirmed against a real nested dispatch -- so this
# suite fixes its fixtures to whatever constant log_agent.sh currently
# declares (read via _agent_parent_key below) rather than hard-coding a guess
# a second time; if T2.4 changes the constant, this suite keeps passing
# without a rewrite.
#
# bash 3.2 compatible; LC_ALL=C in effect via the sourced writer.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  ADAPTER="$REPO_ROOT/plugins/tcs-helper/scripts/observability/log_agent.sh"

  # The one payload key this suite cannot pin by citation (see header above)
  # -- read straight out of the adapter's own source so a future correction
  # to the constant (T2.4) does not silently desync the fixtures from it.
  PARENT_KEY="$(sed -n 's/^AGENT_PAYLOAD_KEY_PARENT="\([^"]*\)".*/\1/p' "$ADAPTER" | head -n1)"
  [ -n "$PARENT_KEY" ]

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-agent.XXXXXX")"
  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$FAKE_HOME"

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

  REPO_CANONICAL="$(cd "$REPO" && git rev-parse --show-toplevel)"
  REPO_NAME="$(basename "$REPO_CANONICAL")"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a flat JSON object of string fields from key=value args. Good enough
# for this adapter's payloads: none of the fixture values below contain a
# literal quote or backslash.
_payload_json() {
  local json="{" first=1 kv key val
  for kv in "$@"; do
    key="${kv%%=*}"
    val="${kv#*=}"
    if [ "$first" -eq 1 ]; then first=0; else json="$json,"; fi
    json="$json\"$key\":\"$val\""
  done
  json="$json}"
  printf '%s' "$json"
}

# Run the adapter as the harness would: cwd inside the repo, payload on
# stdin, CLAUDE_OBSERVABILITY_ENABLED=1 and CLAUDE_OBSERVABILITY_DATA pointed
# at an isolated per-test directory.
_run_adapter() {
  local data_dir="$1" payload="$2"
  bash -c '
    data_dir="$1"; payload="$2"
    cd "'"$REPO"'" || exit 90
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    printf "%s" "$payload" | "'"$ADAPTER"'"
  ' _ "$data_dir" "$payload"
}

# Same, but CLAUDE_OBSERVABILITY_ENABLED is left UNSET (not "0" -- the real
# default), for test 6.
_run_adapter_disabled() {
  local data_dir="$1" payload="$2"
  bash -c '
    data_dir="$1"; payload="$2"
    cd "'"$REPO"'" || exit 90
    unset CLAUDE_OBSERVABILITY_ENABLED
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    printf "%s" "$payload" | "'"$ADAPTER"'"
  ' _ "$data_dir" "$payload"
}

_events_file() {
  printf '%s/observability/events.jsonl' "$1"
}

_assert_absent() {              # _assert_absent <needle> <file>
  if grep -qF -- "$1" "$2"; then
    printf 'LEAK: %s found in %s\n' "$1" "$2" >&2
    return 1
  fi
  return 0
}

_assert_present() {             # _assert_present <needle> <file>
  if grep -qF -- "$1" "$2"; then
    return 0
  fi
  printf 'MISSING: %s not found in %s\n' "$1" "$2" >&2
  return 1
}

# ---------------------------------------------------------------------------
# 1. A dispatch payload yields exactly one kind:agent record carrying
#    agent_type AND agent_id with the CORRECT values -- not merely present,
#    and not transposed. Phase 1 shipped a generic key=value branch whose
#    $key and $val could be swapped with the whole suite staying green
#    because every assertion checked presence rather than value; this test
#    is written specifically to fail if that happens here too.
# ---------------------------------------------------------------------------

@test "a dispatch payload yields one kind:agent record with correct, non-transposed agent_type and agent_id" {
  local data_dir="$TEST_DIR/rec1"
  local payload
  payload="$(_payload_json \
    session_id=sess-1 \
    cwd="$REPO_CANONICAL" \
    agent_type=Explore \
    agent_id=agent-0001)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"kind":"agent"' "$file"
  _assert_present '"session":"sess-1"' "$file"
  _assert_present '"agent_type":"Explore"' "$file"
  _assert_present '"agent_id":"agent-0001"' "$file"

  # Not transposed: neither field carries the OTHER field's value.
  _assert_absent '"agent_type":"agent-0001"' "$file"
  _assert_absent '"agent_id":"Explore"' "$file"

  # No parent on a non-nested dispatch.
  _assert_absent '"parent_agent"' "$file"
}

# ---------------------------------------------------------------------------
# 2. A nested dispatch (payload carrying a parent) records parent_agent.
# ---------------------------------------------------------------------------

@test "a nested dispatch payload records parent_agent" {
  local data_dir="$TEST_DIR/rec2"
  local payload
  payload="$(_payload_json \
    session_id=sess-2 \
    cwd="$REPO_CANONICAL" \
    agent_type=security-reviewer \
    agent_id=agent-0002 \
    "$PARENT_KEY"=general-purpose)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"kind":"agent"' "$file"
  _assert_present '"agent_type":"security-reviewer"' "$file"
  _assert_present '"agent_id":"agent-0002"' "$file"
  _assert_present '"parent_agent":"general-purpose"' "$file"
}

# ---------------------------------------------------------------------------
# 3. A payload missing agent_type still produces a WELL-FORMED record: the
#    line must parse as exactly one JSON object (checked with python3's
#    json.loads, not merely "a line exists" -- a line-count assertion alone
#    would pass on malformed output), agent_type must be absent or empty, and
#    a record must still be produced (kind:agent, agent_id present).
# ---------------------------------------------------------------------------

@test "a payload missing agent_type still produces a well-formed record" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to validate JSON well-formedness"
  fi

  local data_dir="$TEST_DIR/rec3"
  local payload
  payload="$(_payload_json \
    session_id=sess-3 \
    cwd="$REPO_CANONICAL" \
    agent_id=agent-0003)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  # Parses as exactly one JSON object -- the well-formedness check itself.
  run python3 -c "
import json, sys
with open('$file', 'rb') as f:
    lines = [l for l in f.read().split(b'\n') if l]
assert len(lines) == 1, 'expected exactly one line, got %d' % len(lines)
obj = json.loads(lines[0].decode('utf-8'))
assert isinstance(obj, dict), 'line did not parse as a JSON object'
"
  [ "$status" -eq 0 ]

  _assert_present '"kind":"agent"' "$file"
  _assert_present '"agent_id":"agent-0003"' "$file"

  # agent_type is absent or empty -- never a stand-in value, never the whole
  # payload.
  run python3 -c "
import json
with open('$file') as f:
    obj = json.loads(f.readline())
val = obj.get('agent_type', '')
assert val == '', 'agent_type should be absent or empty, got %r' % (val,)
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 4. CON-4 -- the adapter writes nothing to stdout.
# ---------------------------------------------------------------------------

@test "the adapter writes nothing to stdout" {
  local data_dir="$TEST_DIR/rec4"
  local payload
  payload="$(_payload_json \
    session_id=sess-4 \
    cwd="$REPO_CANONICAL" \
    agent_type=Explore \
    agent_id=agent-0004)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# 5. CON-5 -- the adapter does not abort a `set -euo pipefail` caller and
#    leaves the caller's own exit status untouched.
# ---------------------------------------------------------------------------

@test "set -e survival: the adapter does not abort a strict caller" {
  local data_dir="$TEST_DIR/rec5"
  local payload
  payload="$(_payload_json \
    session_id=sess-5 \
    cwd="$REPO_CANONICAL" \
    agent_type=Explore \
    agent_id=agent-0005)"

  run env "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$data_dir" \
    bash -c "
      set -euo pipefail
      cd '$REPO'
      echo BEFORE
      printf '%s' '$payload' | '$ADAPTER'
      echo AFTER
    "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]
}

# Also exercise it against a malformed/empty payload -- the most likely input
# to trip an unguarded extraction and abort the script itself.
@test "set -e survival: an empty payload still lets a strict caller continue" {
  local data_dir="$TEST_DIR/rec5b"

  run env "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$data_dir" \
    bash -c "
      set -euo pipefail
      cd '$REPO'
      echo BEFORE
      printf '' | '$ADAPTER'
      echo AFTER
    "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]
}

# ---------------------------------------------------------------------------
# 6. With CLAUDE_OBSERVABILITY_ENABLED unset, a real dispatch produces no
#    record -- phrased as a real dispatch (mirroring test 1) so it proves
#    the adapter ran and chose not to write, rather than merely that no
#    input was given.
# ---------------------------------------------------------------------------

@test "CLAUDE_OBSERVABILITY_ENABLED unset: a real dispatch produces no record" {
  local data_dir="$TEST_DIR/rec6"
  local payload
  payload="$(_payload_json \
    session_id=sess-6 \
    cwd="$REPO_CANONICAL" \
    agent_type=Explore \
    agent_id=agent-0006)"

  run _run_adapter_disabled "$data_dir" "$payload"
  [ "$status" -eq 0 ]
  [ ! -d "$data_dir" ]
}

# ---------------------------------------------------------------------------
# 7. A payload field carrying a token-shaped canary must not leak into the
#    record beyond the fields the keep/drop table permits for kind:agent
#    (agent_type, agent_id, parent_agent, plus the four frozen fields).
#    Asserted by scanning the RAW record bytes for the canary, not by
#    checking one field -- a leak into a different field would pass a
#    field-value check.
# ---------------------------------------------------------------------------

@test "a canary in an unrecognised payload field never leaks into the record" {
  local data_dir="$TEST_DIR/rec7"
  local canary="CANARY-TOKEN-7f3a9c21"
  local payload
  payload="$(_payload_json \
    session_id=sess-7 \
    cwd="/Users/nobody/secret/$canary" \
    transcript_path="/Users/nobody/.claude/$canary.jsonl" \
    agent_type=Explore \
    agent_id=agent-0007)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]

  _assert_absent "$canary" "$file"
}
