#!/usr/bin/env bats
#
# tests/bats/observability-instructions.bats
#
# spec 018 (observability of what loads and fires), T2.1: the InstructionsLoaded
# adapter. This suite covers plugins/tcs-helper/scripts/observability/log_instructions.sh
# ONLY — it must not assume anything about the skill or agent adapters (T2.2, T2.3),
# which are separate files under construction in parallel.
#
# The adapter is invoked exactly as the harness would invoke it: as an external
# command, payload JSON on stdin, nothing sourced by the test except through that
# process boundary. This is deliberate — CON-4/CON-5 (nothing on stdout, the
# caller's exit status untouched) are guarantees about the PROCESS, not about a
# sourced function, and can only be pinned by actually exec'ing the script.
#
# bash 3.2 compatible; LC_ALL=C in effect via the sourced writer.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  ADAPTER="$REPO_ROOT/plugins/tcs-helper/scripts/observability/log_instructions.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-instr.XXXXXX")"
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

# Same, but CLAUDE_OBSERVABILITY_ENABLED is left UNSET (not "0" — the real
# default), for test 9.
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
# 1. session_start: one record, reason from load_reason, scope from
#    memory_type, repo-relative path.
# ---------------------------------------------------------------------------

@test "session_start payload yields one record with reason, scope and repo-relative path" {
  local data_dir="$TEST_DIR/rec1"
  local payload
  payload="$(_payload_json \
    session_id=sess-1 \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"kind":"instruction"' "$file"
  _assert_present '"session":"sess-1"' "$file"
  _assert_present '"reason":"session_start"' "$file"
  _assert_present '"scope":"Project"' "$file"
  _assert_present '"path":"base.txt"' "$file"

  # An eager, session_start load carries neither parent nor trigger.
  _assert_absent '"parent"' "$file"
  _assert_absent '"trigger"' "$file"
}

# ---------------------------------------------------------------------------
# 2. path_glob_match: trigger populated from trigger_file_path.
# ---------------------------------------------------------------------------

@test "a payload carrying globs yields reason path_glob_match with trigger populated" {
  local data_dir="$TEST_DIR/rec2"
  local payload
  payload="$(_payload_json \
    session_id=sess-2 \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=path_glob_match \
    globs='**/*.md' \
    trigger_file_path="$REPO_CANONICAL/base.txt")"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"reason":"path_glob_match"' "$file"
  _assert_present '"trigger":"base.txt"' "$file"
  _assert_absent '"parent"' "$file"
}

# ---------------------------------------------------------------------------
# 3. include: parent populated from parent_file_path.
# ---------------------------------------------------------------------------

@test "a payload carrying parent_file_path yields reason include with parent populated" {
  local data_dir="$TEST_DIR/rec3"
  local payload
  payload="$(_payload_json \
    session_id=sess-3 \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Local \
    load_reason=include \
    parent_file_path="$REPO_CANONICAL/base.txt")"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"reason":"include"' "$file"
  _assert_present '"parent":"base.txt"' "$file"
  _assert_absent '"trigger"' "$file"
}

# ---------------------------------------------------------------------------
# 4. An absolute path OUTSIDE the repo is reduced to its basename — asserted
#    by scanning the raw record bytes for the absolute path and requiring its
#    absence, not by inspecting one field (a leak into a different field
#    would pass a field-value check).
# ---------------------------------------------------------------------------

@test "an absolute path outside the repo is reduced to basename, never emitted whole" {
  local data_dir="$TEST_DIR/rec4"
  local outside_path="/Users/nobody/.claude/CLAUDE.md"
  local payload
  payload="$(_payload_json \
    session_id=sess-4 \
    file_path="$outside_path" \
    memory_type=User \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]

  _assert_absent "$outside_path" "$file"
  _assert_absent "/Users/nobody" "$file"
  _assert_present '"path":"CLAUDE.md"' "$file"
}

# ---------------------------------------------------------------------------
# 5. bytes carries the size of the loaded file, verified against a fixture
#    of known size.
# ---------------------------------------------------------------------------

@test "bytes carries the size of the loaded file" {
  local data_dir="$TEST_DIR/rec5"
  local fixture="$REPO_CANONICAL/sized-fixture.txt"
  printf '0123456789' > "$fixture"   # exactly 10 bytes, no trailing newline

  local payload
  payload="$(_payload_json \
    session_id=sess-5 \
    file_path="$fixture" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  _assert_present '"bytes":"10"' "$file"
}

# ---------------------------------------------------------------------------
# 6. A path that cannot be stat'ed yields a record WITHOUT the bytes field —
#    not zero, not empty, absent — and the record itself still exists.
# ---------------------------------------------------------------------------

@test "a path that cannot be stat'ed yields a record without bytes, not a missing record" {
  local data_dir="$TEST_DIR/rec6"
  local missing="$REPO_CANONICAL/does-not-exist-xyz.md"
  [ ! -e "$missing" ]

  local payload
  payload="$(_payload_json \
    session_id=sess-6 \
    file_path="$missing" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  # Not present in ANY form — no "bytes" key at all, not "0", not "".
  _assert_absent '"bytes"' "$file"
  _assert_present '"kind":"instruction"' "$file"
}

# ---------------------------------------------------------------------------
# 7. CON-4 — the adapter writes nothing to stdout.
# ---------------------------------------------------------------------------

@test "the adapter writes nothing to stdout" {
  local data_dir="$TEST_DIR/rec7"
  local payload
  payload="$(_payload_json \
    session_id=sess-7 \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# 8. CON-5 — the adapter does not abort a `set -euo pipefail` caller and
#    leaves the caller's own exit status untouched.
# ---------------------------------------------------------------------------

@test "set -e survival: the adapter does not abort a strict caller" {
  local data_dir="$TEST_DIR/rec8"
  local payload
  payload="$(_payload_json \
    session_id=sess-8 \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

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

# Also exercise it against a malformed/empty payload — the most likely input
# to trip an unguarded extraction and abort the script itself.
@test "set -e survival: an empty payload still lets a strict caller continue" {
  local data_dir="$TEST_DIR/rec8b"

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
# 9. With CLAUDE_OBSERVABILITY_ENABLED unset, no record and no data directory
#    are created.
# ---------------------------------------------------------------------------

@test "CLAUDE_OBSERVABILITY_ENABLED unset creates no directory and no file" {
  local data_dir="$TEST_DIR/rec9"
  local payload
  payload="$(_payload_json \
    session_id=sess-9 \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter_disabled "$data_dir" "$payload"
  [ "$status" -eq 0 ]
  [ ! -d "$data_dir" ]
}
