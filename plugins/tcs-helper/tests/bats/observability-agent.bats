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
# comment for the citation). A parent-agent payload key was investigated at
# T2.4 against a real, live-captured nested dispatch and found not to exist
# -- SubagentStart carries no parent-identifying field under any name. This
# suite therefore pins the DELIBERATE ABSENCE of `parent_agent` from the
# record rather than testing for its presence (see the test below named
# "a parent-looking payload field never produces a parent_agent record").
#
# bash 3.2 compatible; LC_ALL=C in effect via the sourced writer.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  ADAPTER="$REPO_ROOT/plugins/tcs-helper/scripts/observability/log_agent.sh"

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
# 2. A parent-looking payload field never produces a parent_agent record.
#
# T2.4 measured a real, live nested subagent dispatch (a `general-purpose`
# subagent that itself dispatched an `Explore` subagent five seconds later)
# and found its SubagentStart payload carries no parent-identifying field
# under any name -- see log_agent.sh's own header comment and the README
# Decisions Log entry dated 2026-09-07 for the three lines of evidence. This
# replaces an earlier version of this test, which fed the adapter a payload
# shape ("parent_agent_type": "...") no harness has ever been observed to
# produce and asserted that a `parent_agent` field appeared in the record --
# testing a fiction rather than the real payload contract.
#
# This test pins the opposite, now-settled behaviour: even a payload that
# DOES carry a plausible parent-shaped field must not cause the adapter to
# invent a `parent_agent` record field, so a future edit cannot quietly
# reintroduce one the harness never supplies. The fixture uses
# `parent_agent_type` -- the very key this adapter used to (wrongly) guess
# at -- specifically because it is the most tempting name to accidentally
# wire back up.
# ---------------------------------------------------------------------------

@test "a parent-looking payload field never produces a parent_agent record" {
  local data_dir="$TEST_DIR/rec2"
  local payload
  payload="$(_payload_json \
    session_id=sess-2 \
    cwd="$REPO_CANONICAL" \
    agent_type=security-reviewer \
    agent_id=agent-0002 \
    parent_agent_type=general-purpose)"

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

  # The deliberate absence: no parent_agent field, and the parent-looking
  # value never leaks into the record under any name.
  _assert_absent '"parent_agent"' "$file"
  _assert_absent 'general-purpose' "$file"
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

# ---------------------------------------------------------------------------
# 8. Test 7's canary protection only reaches the two fields its fixture
#    happens to seed (cwd, transcript_path) -- it says nothing about a
#    deny-listed field extracted and emitted under a DIFFERENT name, which
#    is exactly the blind spot the phase-2 BINDING NOTE calls out: the
#    writer's bare-name deny list is an exact-match fail-safe, so a field
#    like `prompt` re-emitted as `psummary` bypasses it entirely. This test
#    seeds the canary in `prompt` (bare-name deny-listed) instead, so the
#    guarantee generalises past the two names test 7 happens to cover.
#
#    Confirmed RED against a scratch mutation: temporarily adding
#      _prompt="$(_observability_field "$_payload" prompt)" || _prompt=""
#      ... psummary="$_prompt" ...
#    to log_agent.sh (extracting `prompt` and re-emitting it under the
#    unlisted name `psummary`) makes this test fail while test 7 stays
#    green -- proving test 7 alone would not have caught it.
# ---------------------------------------------------------------------------

@test "a canary in the deny-listed 'prompt' field never leaks into the record under any field name" {
  local data_dir="$TEST_DIR/rec8"
  local canary="CANARY-PROMPT-9b4e21ac"
  local payload
  payload="$(_payload_json \
    session_id=sess-8 \
    cwd="$REPO_CANONICAL" \
    prompt="do the thing $canary" \
    agent_type=Explore \
    agent_id=agent-0008)"

  run _run_adapter "$data_dir" "$payload"
  [ "$status" -eq 0 ]

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]

  _assert_absent "$canary" "$file"
}

# ---------------------------------------------------------------------------
# 9. Large-payload path. `_observability_field` (logwrite.sh) used to be
#    quadratic when the sought key is ABSENT from a large payload -- this
#    adapter used to call it unconditionally for AGENT_PAYLOAD_KEY_PARENT, a
#    key absent on every non-nested dispatch (the common case), so the
#    common case paid the worst case. That extraction is gone now (spec 018
#    correction, 2026-09-07: T2.4 established no parent field exists to
#    extract -- see log_agent.sh's header comment), which removes this
#    adapter's own trigger for the defect entirely; the underlying fix still
#    stands centrally in logwrite.sh with a `case` presence pre-check
#    (pinned by observability-writer.bats), since another adapter's own
#    absent-key lookups can still hit the same shape. This test is the
#    ADAPTER-level guard: the whole 150 KB payload must still go through
#    this script's three extraction calls in milliseconds, and a further
#    regression in THIS adapter's own calls (e.g. an accidental
#    full-payload scan added here) is caught rather than silently accepted.
#
#    THE BOUND, and why it is not 30s any more. The original bound was
#    calibrated against the BROKEN baseline: this exact payload shape
#    measured ~6.6s against the quadratic extractor, and 30s was chosen to
#    sit above it with headroom for slow runners. That makes the test blind
#    to the very defect it exercises -- reintroducing the quadratic path
#    costs ~6.6s again and sails straight through a 30s ceiling.
#
#    Re-measured after the fix, on the same machine: the same payload
#    through the same adapter completes end to end in ~30 ms (process
#    spawn, sourcing the writer, three extractions, one `git rev-parse`, one
#    `date`, the append). The base bound below is 1000 ms -- ~33x above the
#    measured cost -- scaled by $TCS_PERF_SLACK, which CI sets to 4. The
#    base is 1000 and not 2000 precisely because of that multiplier: the
#    ceiling has to stay below the 6.6s reversion signal on every runner,
#    and 1000x4 = 4000 ms does while 2000x4 = 8000 ms would not. A slack
#    factor that lifts the ceiling past the regression makes the test
#    decorative.
#
#    The watchdog below is no longer the assertion, only a hang-stopper: a
#    truly pathological payload (the reviewer measured a 2 MB one at "did
#    not finish inside two minutes") must not stall the suite while the
#    elapsed-time assertion waits for it.
# ---------------------------------------------------------------------------

_LARGE_PAYLOAD_WATCHDOG_SECS=20

# Scale a wall-clock budget (in ms) by $TCS_PERF_SLACK, the convention
# plugins/tcs-git-helpers/tests/bats/lib/helpers.bash established and
# .github/workflows/tests.yml sets to 4. Duplicated rather than sourced:
# these observability suites are deliberately standalone, and reaching into
# another plugin's test library for ten lines would couple two suites with no
# other relationship.
_perf_budget_ms() {
  local budget="$1" slack="${TCS_PERF_SLACK:-1}"
  case "$slack" in
    ''|*[!0-9]*) slack=1 ;;
  esac
  [ "$slack" -lt 1 ] && slack=1
  printf '%d' $((budget * slack))
}

# Portable bounded run: no dependency on GNU `timeout`/`gtimeout`, which
# this repo's own macOS CI runners do not ship (CON-1's BSD-userland
# concern applies to the TEST too, not just the adapter). Backgrounds the
# adapter and a watchdog subshell side by side; whichever the plain
# foreground `wait` on the adapter's pid returns from first decides the
# outcome -- a normal exit reports its real status, a watchdog kill makes
# `wait` return a signal-based nonzero status, which the assertion below
# treats the same as "did not finish correctly". bash 3.2 compatible: no
# `wait -n` (bash 4.3+) and no fractional `sleep` (BSD sleep has none).
#
# The watchdog's own stdout/stderr/fd3/fd4 are all closed off up front --
# NOT cosmetic, and not just `2>&1`. Without this, every call was measured
# to take the FULL `secs` bound even on the fast path: `kill
# "$watchdog_pid"` (below) kills the watchdog SUBSHELL, but not the
# `sleep` it is currently blocked in -- that grandchild is reparented and
# keeps running to completion, and for as long as it still holds an
# inherited output fd open, bats' `run` (which captures via `$(...)`,
# itself reading a pipe that only reports EOF once every holder of the
# write end has closed it) blocks until that fd's last writer closes, i.e.
# until the orphaned sleep finishes on its own. `>/dev/null 2>&1` alone was
# NOT enough here: bats-core (libexec/bats-core/bats-exec-test) also keeps
# fd 3 as a duplicate of the original stdout (`exec 3<&1`, bypassing
# `run`'s own redirection) and tracing.bash keeps fd 4 for the same
# purpose -- both still get inherited by anything backgrounded unless
# closed explicitly. Closing all four is what lets `run` return as soon as
# the real work (the `wait "$target_pid"` below) actually finishes, rather
# than whenever the watchdog's last orphaned descendant happens to exit.
#
# It also MEASURES the run and prints the elapsed milliseconds as its only
# line of stdout (the adapter itself writes nothing there -- test 4 pins
# that), so the caller can assert a real duration instead of inferring one
# from "the watchdog did not fire". perl's Time::HiRes, not `date +%s`:
# whole seconds carry +/-1s of ambiguity, which is most of a bound measured
# in hundreds of milliseconds, and BSD `date` has no %N. The one-liner uses
# q{} rather than single quotes so it can sit inside this single-quoted
# `bash -c` body without escaping. The clock is stopped the instant the
# adapter is reaped, before the watchdog teardown.
_run_adapter_bounded() {
  local secs="$1" data_dir="$2" payload_file="$3"
  bash -c '
    secs="$1"; data_dir="$2"; payload_file="$3"
    cd "'"$REPO"'" || exit 90
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    start="$(perl -MTime::HiRes=time -e "printf q{%d}, time()*1000")"
    "'"$ADAPTER"'" < "$payload_file" &
    target_pid=$!
    ( sleep "$secs"
      kill -TERM "$target_pid" 2>/dev/null
      sleep 1
      kill -KILL "$target_pid" 2>/dev/null
    ) >/dev/null 2>&1 3>&- 4>&- &
    watchdog_pid=$!
    if wait "$target_pid"; then
      result=0
    else
      result=$?
    fi
    end="$(perl -MTime::HiRes=time -e "printf q{%d}, time()*1000")"
    kill "$watchdog_pid" 2>/dev/null
    wait "$watchdog_pid" 2>/dev/null
    printf "%s\n" "$((end - start))"
    exit "$result"
  ' _ "$secs" "$data_dir" "$payload_file"
}

@test "a large payload (150 KB, parent key absent) completes within the bound and writes a well-formed record" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to build the large fixture payload"
  fi
  if ! command -v perl >/dev/null 2>&1; then
    skip "perl not available for a sub-second clock"
  fi

  local data_dir="$TEST_DIR/rec9"
  local payload_file="$TEST_DIR/large_payload.json"

  # agent_type/agent_id sit near the FRONT, matching a real payload's
  # shape; the padding stands in for the rest of a large real payload and
  # is what made the ABSENT parent-key search expensive before the
  # extractor's presence pre-check landed. Compact separators -- a space
  # after ':' would stop `_observability_field`'s own `"key":"` match from
  # ever landing, silently turning this into a no-op test.
  python3 -c "
import json
pad = 'x' * 150000
obj = {
    'session_id': 'sess-large',
    'cwd': '$REPO_CANONICAL',
    'agent_type': 'Explore',
    'agent_id': 'agent-large',
    'padding': pad,
}
with open('$payload_file', 'w') as f:
    f.write(json.dumps(obj, separators=(',', ':')))
"
  [ -f "$payload_file" ]

  run _run_adapter_bounded "$_LARGE_PAYLOAD_WATCHDOG_SECS" "$data_dir" "$payload_file"
  [ "$status" -eq 0 ]

  # The measured duration, in milliseconds, against the bound argued for in
  # this section's header. Asserted on the number rather than on "the
  # watchdog did not fire", so the failure message names the real cost.
  local elapsed_ms="${output// /}"
  local budget_ms
  budget_ms="$(_perf_budget_ms 1000)"
  if [ "$elapsed_ms" -gt "$budget_ms" ]; then
    printf 'SLOW: %s ms against a %s ms budget\n' "$elapsed_ms" "$budget_ms" >&2
    return 1
  fi

  local file
  file="$(_events_file "$data_dir")"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  _assert_present '"kind":"agent"' "$file"
  _assert_present '"agent_type":"Explore"' "$file"
  _assert_present '"agent_id":"agent-large"' "$file"
}
