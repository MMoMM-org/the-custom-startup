#!/usr/bin/env bats
#
# tests/bats/observability-expansion.bats
#
# spec 021 (observability v2), phase 2, T2.3: the UserPromptExpansion adapter
# (ADR-7). File under test:
#   plugins/tcs-helper/scripts/observability/log_expansion.sh
#
# Payload shapes were measured on Claude Code 2.1.296 (spec README/Context):
#   {"hook_event_name":"UserPromptExpansion","expansion_type":"slash_command",
#    "command_name":"tcs-issues:issue","command_args":"...",
#    "command_source":"plugin","prompt":"<whole expanded prompt>"}
#
# Every negative assertion (canary absent, nothing recorded) is paired with a
# positive one proving a record exists, so absence is never vacuous.
#
# bash 3.2 compatible. No jq dependency: records are compact JSON and are
# asserted by literal substring.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  ADAPTER="$REPO_ROOT/plugins/tcs-helper/scripts/observability/log_expansion.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-expansion.XXXXXX")"

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

  # A first exec costs 150-290 ms on macOS (memory
  # reference_macos-exec-cost-in-hook-path); pay it here, not in a timed test.
  printf '' | "$ADAPTER" >/dev/null 2>&1 || true
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

_run_adapter_enabled() {
  ( cd "$REPO" && \
    printf '%s' "$1" | env -u CLAUDE_OBSERVABILITY_DETAIL \
      "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" \
      "$ADAPTER" )
}

_run_adapter_detail() {
  ( cd "$REPO" && \
    printf '%s' "$1" | env \
      "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DETAIL=1" \
      "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" "$ADAPTER" )
}

_run_adapter_disabled() {
  ( cd "$REPO" && \
    printf '%s' "$1" | env -u CLAUDE_OBSERVABILITY_ENABLED \
      "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" "$ADAPTER" )
}

_run_adapter_enabled_from_file() {
  ( cd "$REPO" && \
    env -u CLAUDE_OBSERVABILITY_DETAIL \
      "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" \
      "$ADAPTER" < "$1" )
}

# bats only fails a test on the LAST command's status for `! cmd` and `[[ ]]`,
# so absence and presence are asserted through helpers that return explicitly.
_assert_absent() {              # _assert_absent <needle> <file>
  if grep -qF -- "$1" "$2"; then
    printf 'LEAK: %s found in %s\n' "$1" "$2" >&2
    return 1
  fi
  return 0
}

_assert_present() {             # _assert_present <needle> <file>
  if ! grep -qF -- "$1" "$2"; then
    printf 'MISSING: %s not found in %s\n' "$1" "$2" >&2
    return 1
  fi
  return 0
}

_assert_one_record() {
  [ -f "$EVENTS_FILE" ]
  run wc -l < "$EVENTS_FILE"
  [ "${output// /}" = "1" ]
}

_perf_budget_ms() {
  local budget="$1" slack="${TCS_PERF_SLACK:-1}"
  case "$slack" in
    ''|*[!0-9]*) slack=1 ;;
  esac
  [ "$slack" -lt 1 ] && slack=1
  printf '%d' $((budget * slack))
}

_now_ms() {
  perl -MTime::HiRes=time -e 'printf q{%d}, time()*1000'
}

# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------

@test "expansion: slash_command with args yields one typed skill record" {
  local payload
  payload='{"session_id":"sess-exp-1","hook_event_name":"UserPromptExpansion","expansion_type":"slash_command","command_name":"tcs-issues:issue","command_args":"list --state open","command_source":"plugin","prompt":"expanded text"}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"kind":"skill"' "$EVENTS_FILE"
  _assert_present '"session":"sess-exp-1"' "$EVENTS_FILE"
  _assert_present '"skill":"tcs-issues:issue"' "$EVENTS_FILE"
  _assert_present '"route":"typed"' "$EVENTS_FILE"
  _assert_present '"args_present":"yes"' "$EVENTS_FILE"
  _assert_present '"source":"plugin"' "$EVENTS_FILE"
}

@test "expansion: slash_command without args yields args_present no" {
  local payload
  payload='{"session_id":"sess-exp-2","expansion_type":"slash_command","command_name":"commit","command_args":"","command_source":"projectSettings","prompt":"expanded text"}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"skill":"commit"' "$EVENTS_FILE"
  _assert_present '"args_present":"no"' "$EVENTS_FILE"
  _assert_present '"source":"projectSettings"' "$EVENTS_FILE"
}

@test "expansion: an absent command_args key yields args_present no" {
  local payload
  payload='{"session_id":"sess-exp-3","expansion_type":"slash_command","command_name":"commit","command_source":"projectSettings","prompt":"expanded text"}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"args_present":"no"' "$EVENTS_FILE"
}

@test "expansion: a command_args look-alike inside the escaped prompt does not set args_present" {
  local payload
  payload='{"session_id":"sess-exp-4","expansion_type":"slash_command","command_name":"commit","command_args":"","command_source":"plugin","prompt":"see \"command_args\":\"inner\" here"}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"args_present":"no"' "$EVENTS_FILE"
}

@test "expansion: real non-empty command_args plus an escaped empty look-alike in the prompt yields args_present yes" {
  local payload
  payload='{"session_id":"sess-exp-4b","expansion_type":"slash_command","command_name":"commit","command_args":"real","command_source":"plugin","prompt":"see \"command_args\":\"\" here"}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"args_present":"yes"' "$EVENTS_FILE"
}

# ---------------------------------------------------------------------------
# Canary: argument and prompt text never reach the record (CON-13), in
# reduced AND detail mode.
# ---------------------------------------------------------------------------

@test "expansion: args and prompt text never reach the record in reduced mode" {
  local payload
  payload='{"session_id":"sess-exp-5","expansion_type":"slash_command","command_name":"tcs-issues:issue","command_args":"CANARY-ARGS-5150","command_source":"plugin","prompt":"CANARY-PROMPT-5150 body"}'

  run _run_adapter_enabled "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"skill":"tcs-issues:issue"' "$EVENTS_FILE"
  _assert_absent 'CANARY-ARGS-5150' "$EVENTS_FILE"
  _assert_absent 'CANARY-PROMPT-5150' "$EVENTS_FILE"
  _assert_absent 'command_args' "$EVENTS_FILE"
  _assert_absent '"prompt"' "$EVENTS_FILE"
}

@test "expansion: args and prompt text never reach the record in detail mode" {
  local payload
  payload='{"session_id":"sess-exp-6","expansion_type":"slash_command","command_name":"tcs-issues:issue","command_args":"CANARY-ARGS-6160","command_source":"plugin","prompt":"CANARY-PROMPT-6160 body"}'

  run _run_adapter_detail "$payload"
  [ "$status" -eq 0 ]
  _assert_one_record
  _assert_present '"skill":"tcs-issues:issue"' "$EVENTS_FILE"
  _assert_present '"args_present":"yes"' "$EVENTS_FILE"
  _assert_absent 'CANARY-ARGS-6160' "$EVENTS_FILE"
  _assert_absent 'CANARY-PROMPT-6160' "$EVENTS_FILE"
}

# ---------------------------------------------------------------------------
# Nothing recorded
# ---------------------------------------------------------------------------

@test "expansion: mcp_prompt records nothing (a slash_command control does)" {
  local mcp slash
  mcp='{"session_id":"sess-exp-7","expansion_type":"mcp_prompt","command_name":"server:prompt","command_args":"a","command_source":"mcp","prompt":"x"}'
  slash='{"session_id":"sess-exp-7","expansion_type":"slash_command","command_name":"server:prompt","command_args":"a","command_source":"plugin","prompt":"x"}'

  run _run_adapter_enabled "$mcp"
  [ "$status" -eq 0 ]
  [ ! -e "$EVENTS_FILE" ]

  run _run_adapter_enabled "$slash"
  [ "$status" -eq 0 ]
  _assert_one_record
}

@test "expansion: an unknown expansion_type or a missing one records nothing" {
  run _run_adapter_enabled '{"session_id":"s","expansion_type":"slash_command_x","command_name":"a","command_source":"plugin"}'
  [ "$status" -eq 0 ]
  run _run_adapter_enabled '{"session_id":"s","command_name":"a","command_source":"plugin"}'
  [ "$status" -eq 0 ]
  [ ! -e "$EVENTS_FILE" ]
}

@test "expansion: a missing or empty command_name records nothing (control does)" {
  run _run_adapter_enabled '{"session_id":"s","expansion_type":"slash_command","command_args":"a","command_source":"plugin"}'
  [ "$status" -eq 0 ]
  run _run_adapter_enabled '{"session_id":"s","expansion_type":"slash_command","command_name":"","command_source":"plugin"}'
  [ "$status" -eq 0 ]
  [ ! -e "$EVENTS_FILE" ]

  run _run_adapter_enabled '{"session_id":"s","expansion_type":"slash_command","command_name":"ok","command_source":"plugin"}'
  [ "$status" -eq 0 ]
  _assert_one_record
}

@test "expansion: disabled, malformed and empty payloads exit 0 silently" {
  local good
  good='{"session_id":"s","expansion_type":"slash_command","command_name":"ok","command_source":"plugin"}'

  run --separate-stderr _run_adapter_disabled "$good"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
  [ ! -e "$DATA_DIR" ]

  run --separate-stderr _run_adapter_enabled '{not json at all "expansion_type":"slash_command'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]

  run --separate-stderr _run_adapter_enabled ''
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
  [ ! -e "$EVENTS_FILE" ]
}

@test "expansion: a recorded payload writes nothing to stdout or stderr" {
  local good
  good='{"session_id":"s","expansion_type":"slash_command","command_name":"ok","command_source":"plugin"}'

  run --separate-stderr _run_adapter_enabled "$good"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
  _assert_one_record
}

@test "expansion: does not abort a set -euo pipefail caller" {
  local payload
  payload='{"session_id":"s","expansion_type":"slash_command","command_name":"ok","command_source":"plugin"}'

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
  _assert_one_record
}

# ---------------------------------------------------------------------------
# Scale: the payload carries the whole expanded prompt (ADR-6).
# ---------------------------------------------------------------------------

# Wall time in ms of one adapter run over payload file $1.
_time_run_ms() {
  local start end
  start="$(_now_ms)"
  _run_adapter_enabled_from_file "$1" >/dev/null 2>&1 || true
  end="$(_now_ms)"
  printf '%d' $((end - start))
}

# CPU milliseconds (user+sys of the script child only) for one run of script
# $1 fed payload file $2 THROUGH A PIPE. A pipe, not a redirected file: the real hook
# reads a pipe, where bash's read builtin takes one byte per syscall (ADR-6);
# from a seekable file it reads in chunks and the cost vanishes. The perl
# parent is the pipe's writer; its own CPU is excluded because times() splits
# the waited-for child ($t[2], $t[3]) from the parent ($t[0], $t[1]).
# Exit 127 if the adapter cannot be exec'd, so a missing script fails the test
# instead of measuring nothing.
# CPU time, not wall time: the host is routinely loaded, and wall time then
# swamps the difference (load average 260: wall deltas overlapped).
# shellcheck disable=SC2016
_cpu_run_ms() {
  ( cd "$REPO" && \
    env -u CLAUDE_OBSERVABILITY_DETAIL \
      "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" \
      perl -e 'open(my $in, "<", $ARGV[1]) or exit 126;
               my $data = do { local $/; <$in> };
               pipe(my $r, my $w) or exit 126;
               my $pid = fork();
               exit 126 unless defined $pid;
               if ($pid == 0) {
                 close $w; open(STDIN, "<&", $r) or exit 126;
                 open(STDOUT, ">", "/dev/null"); open(STDERR, ">", "/dev/null");
                 exec { $ARGV[0] } $ARGV[0]; exit 127;
               }
               close $r; syswrite($w, $data); close $w;
               waitpid($pid, 0);
               exit(($? >> 8) || 1) if $? != 0;
               my @t = times();
               printf q{%d}, ($t[2] + $t[3]) * 1000' "$1" "$2" )
}

# Interleaved best-of-5 CPU for two scripts over two payloads. Alternating the
# runs exposes all four cells to the same machine load, and the minimum drops
# scheduling noise. Sets REAL_BIG REAL_SMALL MUT_BIG MUT_SMALL (ms).
_best_cpu_quad() {      # _best_cpu_quad <real> <mutant> <big-file> <small-file>
  local t _
  REAL_BIG="" REAL_SMALL="" MUT_BIG="" MUT_SMALL=""
  for _ in 1 2 3 4 5; do
    t="$(_cpu_run_ms "$1" "$3")" || return 1
    if [ -z "$REAL_BIG" ] || [ "$t" -lt "$REAL_BIG" ]; then REAL_BIG="$t"; fi
    t="$(_cpu_run_ms "$1" "$4")" || return 1
    if [ -z "$REAL_SMALL" ] || [ "$t" -lt "$REAL_SMALL" ]; then REAL_SMALL="$t"; fi
    t="$(_cpu_run_ms "$2" "$3")" || return 1
    if [ -z "$MUT_BIG" ] || [ "$t" -lt "$MUT_BIG" ]; then MUT_BIG="$t"; fi
    t="$(_cpu_run_ms "$2" "$4")" || return 1
    if [ -z "$MUT_SMALL" ] || [ "$t" -lt "$MUT_SMALL" ]; then MUT_SMALL="$t"; fi
  done
}

# Same payload shape at a chosen prompt size; command fields first, the big
# prompt last (real field order).
_write_payload() {              # _write_payload <file> <prompt-bytes>
  perl -e 'print q({"session_id":"sess-large","hook_event_name":"UserPromptExpansion","expansion_type":"slash_command","command_name":"tcs-issues:issue","command_args":"CANARY-LARGE-ARGS","command_source":"plugin","prompt":"), "x" x $ARGV[0], q("})' "$2" > "$1"
  [ -s "$1" ]
}

@test "expansion: a 200 KB expanded prompt records correctly and under a gross ceiling" {
  if ! command -v perl >/dev/null 2>&1; then
    skip "perl not available for a sub-second clock"
  fi
  local payload_file="$TEST_DIR/large_payload.json"
  _write_payload "$payload_file" 204800

  local elapsed budget
  elapsed="$(_time_run_ms "$payload_file")"
  budget="$(_perf_budget_ms 1000)"
  if [ "$elapsed" -gt "$budget" ]; then
    printf 'SLOW: %s ms against a %s ms ceiling\n' "$elapsed" "$budget" >&2
    return 1
  fi

  _assert_one_record
  _assert_present '"skill":"tcs-issues:issue"' "$EVENTS_FILE"
  _assert_present '"args_present":"yes"' "$EVENTS_FILE"
  _assert_absent 'CANARY-LARGE-ARGS' "$EVENTS_FILE"
  _assert_absent 'xxxxxxxxxx' "$EVENTS_FILE"
}

# ADR-6: `IFS= read -r -d ''` takes one byte per syscall from a pipe, which is
# why this adapter must not copy that line from log_skill.sh. The cost is
# measured as a DIFFERENCE of child CPU time (200 KB minus ~1 KB, same payload
# shape, fed through a pipe like the real hook) and compared to a MUTANT: a copy
# of this very adapter with only the read line swapped for `read -d ''`,
# measured interleaved with it in the same run. A fixed millisecond bound was
# tried and does not hold: CPU time inflates on a loaded host (macOS bash 3.2,
# load average ~300: the correct reader's delta went from 50 to 100 ms), so
# any fixed number either flakes or passes the mutant. A scaled one (x4 in CI)
# is above the mutant. Measured on an idle-ish host (10 ms resolution), the
# mutant's delta exceeds the adapter's by:
#   macOS bash 3.2:  60-80 ms     Linux bash 5.2:  30-50 ms
# so the adapter must undercut its mutant by at least 15 ms of CPU. If the
# adapter ever reads with `read -d ''` the gap is <= 0 (measured on both) and this fails.
@test "expansion: reading 200 KB through a pipe costs at least 15 ms less CPU than the read -d mutant" {
  if ! command -v perl >/dev/null 2>&1; then
    skip "perl not available for a CPU clock"
  fi
  local big="$TEST_DIR/big.json" small="$TEST_DIR/small.json"
  _write_payload "$big" 204800
  _write_payload "$small" 1000

  # The mutant: same adapter, same sibling writer, only the read line swapped.
  local mdir="$TEST_DIR/mutant"
  mkdir -p "$mdir"
  cp "$(dirname "$ADAPTER")/logwrite.sh" "$mdir/logwrite.sh"
  # Matches the cat form AND an already-mutated read form, so a regressed
  # adapter yields a mutant identical to it (gap ~0) rather than a no-op swap.
  perl -pe 's/^(?:_payload="\$\(cat.*|IFS= read -r -d .*)$/IFS= read -r -d \x27\x27 _payload || true/' \
    "$ADAPTER" > "$mdir/log_expansion.sh"
  chmod +x "$mdir/log_expansion.sh"
  # The swap must have landed, or the comparison below compares nothing.
  _assert_present "IFS= read -r -d '' _payload || true" "$mdir/log_expansion.sh"

  _best_cpu_quad "$ADAPTER" "$mdir/log_expansion.sh" "$big" "$small"
  local real_delta mut_delta gap
  real_delta=$((REAL_BIG - REAL_SMALL))
  mut_delta=$((MUT_BIG - MUT_SMALL))
  gap=$((mut_delta - real_delta))
  if [ "$gap" -lt 15 ]; then
    printf 'READ COST: adapter delta %s ms (%s-%s), read -d mutant delta %s ms (%s-%s), gap %s ms < 15\n' \
      "$real_delta" "$REAL_BIG" "$REAL_SMALL" "$mut_delta" "$MUT_BIG" "$MUT_SMALL" "$gap" >&2
    return 1
  fi
  # 5 runs per size, one record each: proves the adapter really ran.
  run wc -l < "$EVENTS_FILE"
  [ "${output// /}" = "20" ]
}
