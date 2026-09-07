#!/usr/bin/env bats
#
# tests/bats/observability-selfcheck.bats
#
# spec 018 (observability of what loads and fires), T2.4: selfcheck.sh.
# This suite covers plugins/tcs-helper/scripts/observability/selfcheck.sh
# ONLY -- it must not assume anything about the .claude/settings.json
# registration, which is a separate, deliberately-out-of-scope task (T2.4's
# owner registers hooks by hand, after this file is reviewed).
#
# selfcheck.sh is HUMAN-FACING, NOT A HOOK (see its own header for the
# reasoning): nothing in this spec pipes a hook payload into it, so CON-4
# (nothing on stdout) and CON-5 (exit status never changes) do not bind it.
# It prints human-readable lines on purpose, and its exit status is
# meaningful: 0 when recording is off (a choice) or confirmed working, 1
# when it is ON but a genuine round-trip proves it cannot actually record.
#
# The writer is fail-open by design (CON-5): it always returns 0 and leaves
# no trace of its own failures. selfcheck therefore cannot be trusted to
# answer "is it recording?" by checking the writer's exit status, or by
# checking that a directory or file merely exists -- both would stay green
# in exactly the cases this file exists to catch. Every "recording" assertion
# below is therefore paired with a REAL filesystem check (the log file's
# existence and line count), not just a string in selfcheck's stdout, so
# that a stub that reads the env var and prints conditional text without
# ever touching disk cannot pass this suite.
#
# bash 3.2 compatible; LC_ALL=C in effect via the sourced writer.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  SELFCHECK="$REPO_ROOT/plugins/tcs-helper/scripts/observability/selfcheck.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-selfcheck.XXXXXX")"
  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$FAKE_HOME"

  REPO="$TEST_DIR/myrepo"
  mkdir -p "$REPO"
  export GIT_CONFIG_GLOBAL=/dev/null
  git -C "$REPO" init -q -b main
  git -C "$REPO" config user.email "t@t"
  git -C "$REPO" config user.name "t"
  git -C "$REPO" config commit.gpgsign false
  printf 'base\n' >"$REPO/base.txt"
  git -C "$REPO" add base.txt
  git -C "$REPO" commit -q -m "base"

  REPO_CANONICAL="$(cd "$REPO" && git rev-parse --show-toplevel)"
}

teardown() {
  # A test that made a directory unwritable must be able to clean itself up.
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_events_file() {
  printf '%s/observability/events.jsonl' "$1"
}

# Run selfcheck as a human would: cwd inside the repo, the two switches
# exported (or not), CLAUDE_OBSERVABILITY_DATA pointed at an isolated
# per-test directory. No stdin -- selfcheck takes none.
_run_selfcheck() {
  local data_dir="$1" enabled="$2" detail="$3"
  bash -c '
    data_dir="$1"; enabled="$2"; detail="$3"
    cd "'"$REPO"'" || exit 90
    if [ -n "$enabled" ]; then export CLAUDE_OBSERVABILITY_ENABLED="$enabled"; else unset CLAUDE_OBSERVABILITY_ENABLED; fi
    if [ -n "$detail" ]; then export CLAUDE_OBSERVABILITY_DETAIL="$detail"; else unset CLAUDE_OBSERVABILITY_DETAIL; fi
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    "'"$SELFCHECK"'"
  ' _ "$data_dir" "$enabled" "$detail"
}

_line_count() {
  local f="$1" n
  [ -f "$f" ] || { printf '0'; return 0; }
  n="$(wc -l <"$f" 2>/dev/null)" || n=0
  printf '%s' "${n//[[:space:]]/}"
}

# ---------------------------------------------------------------------------
# 1. Both switches unset: reports "not recording", exits 0, and creates NO
#    data directory as a side effect of merely checking.
# ---------------------------------------------------------------------------

@test "disabled: reports not recording, exits 0, creates no data directory" {
  local data_dir="$TEST_DIR/rec1"
  [ ! -e "$data_dir" ]

  run _run_selfcheck "$data_dir" "" ""
  [ "$status" -eq 0 ]

  [[ "$output" == *"not recording"* ]]
  [[ "$output" != *"nothing had been logged"* ]]

  # The side-effect guarantee: checking must not itself start recording.
  [ ! -e "$data_dir" ]
  [ ! -d "$data_dir/observability" ]
}

# ---------------------------------------------------------------------------
# 2. Enabled (detail off): reports enabled, detail off, the record path, and
#    confirms recording via a genuine round-trip -- which a real file on disk
#    must back up, not merely the printed text.
# ---------------------------------------------------------------------------

@test "enabled, no detail: reports enabled, detail off, record path, and round-trips a probe onto disk" {
  local data_dir="$TEST_DIR/rec2"

  run _run_selfcheck "$data_dir" "1" ""
  [ "$status" -eq 0 ]

  [[ "$output" == *"enabled: yes"* ]]
  [[ "$output" == *"detail: no"* ]]

  local file
  file="$(_events_file "$data_dir")"
  [[ "$output" == *"$file"* ]]

  # Real filesystem state, not just the message: the probe actually landed.
  [ -d "$data_dir/observability" ]
  [ -f "$file" ]
  [ "$(_line_count "$file")" -ge 1 ]
  grep -qF '"kind":"state"' "$file"
}

# ---------------------------------------------------------------------------
# 3. Both switches set: reports detail on.
# ---------------------------------------------------------------------------

@test "enabled with detail: reports detail on" {
  local data_dir="$TEST_DIR/rec3"

  run _run_selfcheck "$data_dir" "1" "1"
  [ "$status" -eq 0 ]

  [[ "$output" == *"enabled: yes"* ]]
  [[ "$output" == *"detail: yes"* ]]
}

# ---------------------------------------------------------------------------
# 4. Recording on with an EMPTY log (nothing logged before this check) is
#    distinguished from recording off. Asserted on real filesystem state,
#    not merely the message: before running, the data directory must not
#    exist at all; after running, it must exist with a log file carrying
#    EXACTLY the one line this run's own probe wrote -- so a stub that
#    prints conditional text without ever touching disk cannot pass this.
# ---------------------------------------------------------------------------

@test "enabled, previously-empty log: distinguished from 'off', and the disk backs it up" {
  local data_dir="$TEST_DIR/rec4"
  [ ! -e "$data_dir" ]

  run _run_selfcheck "$data_dir" "1" ""
  [ "$status" -eq 0 ]

  [[ "$output" != *"not recording"* ]]
  [[ "$output" == *"nothing had been logged"* ]]

  local file
  file="$(_events_file "$data_dir")"
  [ -d "$data_dir/observability" ]
  [ -f "$file" ]
  [ "$(_line_count "$file")" -eq 1 ]
  grep -qF '"kind":"state"' "$file"
}

# ---------------------------------------------------------------------------
# 5. Recording on with EXISTING entries: the last-write time (of what
#    existed BEFORE this run's own probe) is reported, as information.
# ---------------------------------------------------------------------------

@test "enabled, pre-existing entries: the last-write time is reported" {
  local data_dir="$TEST_DIR/rec5"
  local dir="$data_dir/observability"
  mkdir -p "$dir"
  printf '{"ts":"2020-01-02T03:04:05Z","kind":"skill","session":"s","repo":"r","skill":"x"}\n' \
    >"$dir/events.jsonl"

  run _run_selfcheck "$data_dir" "1" ""
  [ "$status" -eq 0 ]

  [[ "$output" == *"2020-01-02T03:04:05Z"* ]]
  [[ "$output" != *"nothing had been logged"* ]]

  # The probe from THIS run is appended on top of the pre-existing line.
  local file="$dir/events.jsonl"
  [ "$(_line_count "$file")" -ge 2 ]
}

# ---------------------------------------------------------------------------
# 6. Data directory exists but is unwritable: reports that it cannot record
#    -- never claims success merely because the directory (or the writer's
#    always-0 exit status) exists.
# ---------------------------------------------------------------------------

@test "enabled, unwritable directory: reports it cannot record" {
  if [ "$(id -u)" = "0" ]; then
    skip "running as root -- permission bits are not enforced"
  fi

  local data_dir="$TEST_DIR/rec6"
  local dir="$data_dir/observability"
  mkdir -p "$dir"
  chmod 0500 "$dir"

  run _run_selfcheck "$data_dir" "1" ""
  [ "$status" -eq 1 ]

  [[ "$output" == *"cannot record"* ]]
  [[ "$output" != *"nothing had been logged"* ]]
  [[ "$output" != *"probe write confirmed"* ]]

  chmod 0700 "$dir"
  # No file was ever created inside the unwritable directory.
  [ ! -f "$dir/events.jsonl" ]
}

# ---------------------------------------------------------------------------
# 7. The kind:state record is a well-formed single JSON object carrying
#    enabled, detail and note.
# ---------------------------------------------------------------------------

@test "the kind:state record is well-formed and carries enabled, detail, note" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to validate JSON well-formedness"
  fi

  local data_dir="$TEST_DIR/rec7"
  run _run_selfcheck "$data_dir" "1" "1"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]

  run python3 -c "
import json
with open('$file') as f:
    lines = [l for l in f if l.strip()]
assert len(lines) == 1, 'expected exactly one line, got %d' % len(lines)
obj = json.loads(lines[0])
assert isinstance(obj, dict)
assert obj.get('kind') == 'state'
assert 'enabled' in obj, 'enabled missing'
assert 'detail' in obj, 'detail missing'
assert 'note' in obj, 'note missing'
assert obj['enabled'] == '1'
assert obj['detail'] == '1'
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 8. Exit status distinguishes "off" (0), "on and working" (0), and
#    "on but cannot record" (1) -- pinned separately from the message text.
# ---------------------------------------------------------------------------

@test "exit status: 0 when off, 0 when recording works, 1 when it cannot record" {
  if [ "$(id -u)" = "0" ]; then
    skip "running as root -- permission bits are not enforced"
  fi

  run _run_selfcheck "$TEST_DIR/off" "" ""
  [ "$status" -eq 0 ]

  run _run_selfcheck "$TEST_DIR/works" "1" ""
  [ "$status" -eq 0 ]

  local dir="$TEST_DIR/broken/observability"
  mkdir -p "$dir"
  chmod 0500 "$dir"
  run _run_selfcheck "$TEST_DIR/broken" "1" ""
  [ "$status" -eq 1 ]
  chmod 0700 "$dir"
}
