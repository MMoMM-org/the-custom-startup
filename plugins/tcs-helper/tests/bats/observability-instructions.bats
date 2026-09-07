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
# 1b. A payload that omits load_reason entirely must not have the adapter
#    INVENT a value. session_start is the harness's real default for eager
#    loads, but the SDD's own emission-site contract says the field is
#    always present on a real payload — so a payload missing it entirely is
#    an anomaly, not a normal eager load. Fabricating "session_start" would
#    make that anomaly indistinguishable from a genuine one downstream (the
#    report cannot tell an invented value from a real one). The record still
#    carries `reason` (the schema has no `?` on it), just empty — honest
#    about not knowing, the same posture `bytes` already takes on a stat
#    failure.
# ---------------------------------------------------------------------------

@test "a payload with no load_reason at all yields reason empty, never a fabricated session_start" {
  local data_dir="$TEST_DIR/rec1b"
  local payload
  payload="$(_payload_json \
    session_id=sess-1b \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project)"
    # load_reason deliberately omitted

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"reason":""' "$file"
  _assert_absent '"reason":"session_start"' "$file"
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

@test "bytes is 0, not absent, for a genuinely empty file" {
  local data_dir="$TEST_DIR/rec6b"
  local fixture="$REPO_CANONICAL/empty-fixture.txt"
  : > "$fixture"   # genuinely empty: 0 bytes, distinct from a missing file

  local payload
  payload="$(_payload_json \
    session_id=sess-6b \
    file_path="$fixture" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  # Present, with the value "0" — never absent (that would be indistinguishable
  # from a stat failure) and never the empty string.
  _assert_present '"bytes":"0"' "$file"
  _assert_absent '"bytes":""' "$file"
}

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

# ---------------------------------------------------------------------------
# 10. PRD F3 — "off costs nothing" is not just "writes nothing", it is
#    "forks nothing". The writer's own gate (checked inside
#    _observability_write) already makes the two versions of this adapter —
#    with and without its OWN early gate at the top of the file — externally
#    identical: same exit status, same (absent) file, same (empty) stdout.
#    Only a fork-counting shim on PATH can tell them apart, mirroring
#    observability-writer.bats's own git-fork-counting tests.
# ---------------------------------------------------------------------------

# Prepend a shim directory to PATH with counting stand-ins for `git` and
# `stat`. Each invocation appends one byte to its counter file; the shim
# never touches the real binaries, so a call that reaches here would never
# reach the genuine git/stat either — this is a strict upper bound on what
# the adapter invoked, not a passthrough wrapper.
_make_fork_shim() {
  local shim_dir="$1" git_counter="$2" stat_counter="$3"
  mkdir -p "$shim_dir"
  : > "$git_counter"
  : > "$stat_counter"

  {
    printf '#!/usr/bin/env bash\n'
    printf 'printf x >> %q\n' "$git_counter"
    printf 'exit 0\n'
  } > "$shim_dir/git"
  chmod +x "$shim_dir/git"

  {
    printf '#!/usr/bin/env bash\n'
    printf 'printf x >> %q\n' "$stat_counter"
    printf 'exit 1\n'
  } > "$shim_dir/stat"
  chmod +x "$shim_dir/stat"
}

@test "CLAUDE_OBSERVABILITY_ENABLED unset forks neither git nor stat (PRD F3)" {
  local shim_dir="$TEST_DIR/shim_off"
  local git_counter="$TEST_DIR/off_git_calls"
  local stat_counter="$TEST_DIR/off_stat_calls"
  _make_fork_shim "$shim_dir" "$git_counter" "$stat_counter"

  local payload
  payload="$(_payload_json \
    session_id=sess-off \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

  run bash -c '
    shim_dir="$1"; payload="$2"; adapter="$3"
    cd "'"$REPO"'" || exit 90
    unset CLAUDE_OBSERVABILITY_ENABLED
    PATH="$shim_dir:$PATH"
    printf "%s" "$payload" | "$adapter"
  ' _ "$shim_dir" "$payload" "$ADAPTER"
  [ "$status" -eq 0 ]

  [ ! -s "$git_counter" ]
  [ ! -s "$stat_counter" ]
}

# Same shim, same payload, ENABLED=1 this time — proves the shim actually
# intercepts calls the adapter makes, so the disabled-path assertion above
# is not vacuously true because the shim was never reached at all.
@test "CLAUDE_OBSERVABILITY_ENABLED=1 does fork git and attempt stat (shim sanity check)" {
  local shim_dir="$TEST_DIR/shim_on"
  local git_counter="$TEST_DIR/on_git_calls"
  local stat_counter="$TEST_DIR/on_stat_calls"
  _make_fork_shim "$shim_dir" "$git_counter" "$stat_counter"
  local data_dir="$TEST_DIR/shim_on_data"

  local payload
  payload="$(_payload_json \
    session_id=sess-on \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

  run bash -c '
    shim_dir="$1"; payload="$2"; adapter="$3"; data_dir="$4"
    cd "'"$REPO"'" || exit 90
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    PATH="$shim_dir:$PATH"
    printf "%s" "$payload" | "$adapter"
  ' _ "$shim_dir" "$payload" "$ADAPTER" "$data_dir"
  [ "$status" -eq 0 ]

  [ -s "$git_counter" ]
  [ -s "$stat_counter" ]
}

# ---------------------------------------------------------------------------
# 11. A record with no usable path carries no information: PRD F4's
#    denominator (instructions configured vs. loaded) would be inflated by
#    a phantom load that never named a file. Same posture as `bytes` and
#    `reason` above — better to write nothing than something the report
#    cannot distinguish from a real event. No data directory should even be
#    created, since that would itself be an observable side effect of a
#    payload that named no file.
# ---------------------------------------------------------------------------

@test "an entirely empty payload produces no phantom record" {
  local data_dir="$TEST_DIR/rec_phantom_empty"
  run _run_adapter "$data_dir" ""
  [ "$status" -eq 0 ]
  [ ! -d "$data_dir" ]
}

@test "a well-formed payload missing file_path produces no phantom record" {
  local data_dir="$TEST_DIR/rec_phantom_nofile"
  local payload
  payload="$(_payload_json \
    session_id=sess-phantom \
    memory_type=Project \
    load_reason=session_start)"
    # file_path deliberately omitted

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]
  [ ! -d "$data_dir" ]
}

# ---------------------------------------------------------------------------
# 12. The toplevel itself as `file_path` — the one legitimate empty-LOOKING
#    case the phantom-record guard's own comment names by hand
#    ("`_observability_redact_path` reduces it to `.`, and `.` is non-empty").
#    That comment was the only thing standing behind the behaviour: no test
#    constructed the case, so a guard rewritten to check `_file_path` instead
#    of `_path`, or a redactor that returned "" instead of ".", would have
#    dropped a real load with the whole suite green.
# ---------------------------------------------------------------------------

@test "file_path equal to the repo toplevel yields path \".\" and a record IS written" {
  local data_dir="$TEST_DIR/rec_toplevel"
  local payload
  payload="$(_payload_json \
    session_id=sess-toplevel \
    file_path="$REPO_CANONICAL" \
    memory_type=Project \
    load_reason=session_start)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"path":"."' "$file"
  _assert_present '"reason":"session_start"' "$file"
  # The absolute toplevel is what was redacted away; it must not survive
  # anywhere in the line.
  _assert_absent "$REPO_CANONICAL" "$file"
}

# ---------------------------------------------------------------------------
# 13. CON-7 end to end: ONE `git rev-parse` per record, not two.
#
#    This adapter resolves the toplevel itself (it needs one for every
#    `_observability_redact_path` call) and `_observability_write` used to
#    resolve it AGAIN, independently, on every call — two forks of the same
#    command per recorded event, on the hot path of a hook that fires once
#    per instruction file loaded. Test 10's shim sanity check only asserted
#    the counter was non-empty, which is satisfied by one fork or by five.
# ---------------------------------------------------------------------------

@test "the adapter and the writer share ONE git rev-parse per record" {
  local shim_dir="$TEST_DIR/shim_once"
  local git_counter="$TEST_DIR/once_git_calls"
  local stat_counter="$TEST_DIR/once_stat_calls"
  _make_fork_shim "$shim_dir" "$git_counter" "$stat_counter"
  local data_dir="$TEST_DIR/shim_once_data"

  local payload
  payload="$(_payload_json \
    session_id=sess-once \
    file_path="$REPO_CANONICAL/base.txt" \
    memory_type=Project \
    load_reason=session_start)"

  run bash -c '
    shim_dir="$1"; payload="$2"; adapter="$3"; data_dir="$4"
    cd "'"$REPO"'" || exit 90
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    PATH="$shim_dir:$PATH"
    printf "%s" "$payload" | "$adapter"
  ' _ "$shim_dir" "$payload" "$ADAPTER" "$data_dir"
  [ "$status" -eq 0 ]

  # The shim prints nothing and exits 0, so the resolved toplevel is empty —
  # which is exactly the "pass it even when empty" case the writer's
  # pre-resolved-toplevel contract has to honour, or it would fork again to
  # "fix" the empty value. A record is still written (the path falls back to
  # its basename), so this is not a vacuous count over a skipped write.
  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  _assert_present '"path":"base.txt"' "$file"

  local calls
  calls="$(wc -c < "$git_counter")"
  [ "${calls// /}" -eq 1 ]
}
