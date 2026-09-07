#!/usr/bin/env bats
#
# tests/bats/observability-timed-wrapper.bats
#
# spec 018 (observability of what loads and fires), phase 3, T3.5: the
# per-hook timing wrapper. File under test:
#   plugins/tcs-helper/scripts/observability/timed-wrapper.sh
#
# T1.4 (see docs/XDD/specs/018-.../README.md) measured six hook
# configurations and found configuration-only per-hook attribution
# empirically impossible: two entries under two DISTINCT matcher strings
# still collapse into one `hook_execution_complete` measurement group
# (arrangement B), and hooks sharing a group run in parallel, so subtraction
# cannot recover a single hook's duration either (arrangement F). The skip
# condition on T3.5 does not apply; this wrapper is the mechanism.
#
# This wrapper sits IN THE HOOK PATH. Two protocol hazards drive most of the
# tests below:
#
#   Hazard 1 (stdin): the wrapper must never read the hook payload itself --
#   `hook_event`/`matcher` come only from its own CLI flags. Reading stdin
#   here would silently empty the payload for every wrapped hook, in every
#   session, for as long as the wrapper stayed installed.
#
#   Hazard 2 (streams): CON-4 says a hook's stdout is parsed as JSON by the
#   harness and CON-5 says a hook's exit status must never change because of
#   a recording failure. `time` itself writes to stderr, so timing must be
#   captured without perturbing the wrapped command's own stdout, stderr or
#   exit status -- including the blocking case, exit 2.
#
# CLI shape (fixed by the task spec, not otherwise documented in the SDD):
#   timed-wrapper.sh --event <event> --matcher <matcher> -- <cmd> [args...]
#
# Every test invokes the wrapper as the harness would invoke a hook command:
# an external process, nothing sourced. Byte-identical claims are checked by
# redirecting to files and comparing with `cmp`, never through bats' own
# `run` (which normalises trailing newlines and would hide exactly the bugs
# this suite exists to catch).
#
# bash 3.2 compatible; this suite itself runs under whatever bash `bats` is
# installed under and can use modern bash freely -- only the script under
# test has to survive bash 3.2 / BSD userland.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  WRAPPER="$REPO_ROOT/plugins/tcs-helper/scripts/observability/timed-wrapper.sh"
  LOGWRITE="$REPO_ROOT/plugins/tcs-helper/scripts/observability/logwrite.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-timed-wrapper.XXXXXX")"

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

  # --- fixture "hooks" -------------------------------------------------
  #
  # cat_and_exit.sh: streams stdin straight to stdout (never through a
  # variable, so it is safe for content with embedded newlines and no
  # trailing newline), writes a marker to stderr, then exits with the code
  # given as $1. One fixture covers stdin passthrough, stdout passthrough,
  # exit-status preservation and the no-trailing-newline case together.
  FIXTURE_CAT="$TEST_DIR/cat_and_exit.sh"
  cat > "$FIXTURE_CAT" <<'EOF'
#!/usr/bin/env bash
cat
printf 'STDERR-MARKER-%s' "${2:-x}" 1>&2
exit "${1:-0}"
EOF
  chmod +x "$FIXTURE_CAT"

  # interleaved.sh: ignores stdin, writes distinguishable chunks to both
  # streams, for the interleaved-output case.
  FIXTURE_INTERLEAVED="$TEST_DIR/interleaved.sh"
  cat > "$FIXTURE_INTERLEAVED" <<'EOF'
#!/usr/bin/env bash
printf 'OUT-A'
printf 'ERR-A' 1>&2
printf 'OUT-B'
printf 'ERR-B' 1>&2
exit "${1:-0}"
EOF
  chmod +x "$FIXTURE_INTERLEAVED"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_assert_present() {             # _assert_present <needle> <file>
  if grep -qF -- "$1" "$2"; then
    return 0
  fi
  printf 'MISSING: %s not found in %s\n' "$1" "$2" >&2
  return 1
}

_assert_absent() {               # _assert_absent <needle> <file>
  if grep -qF -- "$1" "$2"; then
    printf 'LEAK: %s found in %s\n' "$1" "$2" >&2
    return 1
  fi
  return 0
}

_line_count() {
  local f="$1" n
  [ -f "$f" ] || { printf '0'; return 0; }
  n="$(wc -l <"$f" 2>/dev/null)" || n=0
  printf '%s' "${n// /}"
}

# Scale a wall-clock budget (in ms) by $TCS_PERF_SLACK, the convention
# plugins/tcs-git-helpers/tests/bats/lib/helpers.bash established and
# .github/workflows/tests.yml sets to 4. Duplicated here for the same reason
# the three sibling observability suites duplicate it: they source nothing but
# the file under test.
#
# This suite went in without it and the near-zero bound below failed under
# ordinary CPU contention on a developer machine -- a shared CI runner is the
# same condition. The base budget is chosen so base x 4 still sits far below
# the 1000x unit regression these bounds exist to catch.
_perf_budget_ms() {
  local budget="$1" slack="${TCS_PERF_SLACK:-1}"
  case "$slack" in
    ''|*[!0-9]*) slack=1 ;;
  esac
  [ "$slack" -lt 1 ] && slack=1
  printf '%d' $((budget * slack))
}

# ---------------------------------------------------------------------------
# 1. stdout passthrough byte-identical (including a trailing newline case)
#    and exit status 0 preserved. cwd is inside the fixture repo, matching
#    where a real hook runs.
# ---------------------------------------------------------------------------

@test "stdout is byte-identical to the unwrapped command, exit 0 preserved" {
  cd "$REPO"
  local direct_out="$TEST_DIR/direct.out"
  local wrapped_out="$TEST_DIR/wrapped.out"

  printf 'payload-line-one\npayload-line-two\n' | "$FIXTURE_CAT" 0 marker \
    >"$direct_out" 2>/dev/null
  local direct_status=$?

  unset CLAUDE_OBSERVABILITY_ENABLED
  printf 'payload-line-one\npayload-line-two\n' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 marker \
    >"$wrapped_out" 2>/dev/null
  local wrapped_status=$?

  [ "$wrapped_status" -eq "$direct_status" ]
  [ "$wrapped_status" -eq 0 ]
  cmp -s "$direct_out" "$wrapped_out"
}

# ---------------------------------------------------------------------------
# 2. stderr passthrough byte-identical.
# ---------------------------------------------------------------------------

@test "stderr is byte-identical to the unwrapped command" {
  cd "$REPO"
  local direct_err="$TEST_DIR/direct.err"
  local wrapped_err="$TEST_DIR/wrapped.err"

  printf 'x' | "$FIXTURE_CAT" 0 zzz >/dev/null 2>"$direct_err"

  unset CLAUDE_OBSERVABILITY_ENABLED
  printf 'x' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 zzz \
    >/dev/null 2>"$wrapped_err"

  cmp -s "$direct_err" "$wrapped_err"
}

# ---------------------------------------------------------------------------
# 3-5. Exit status preserved: 0, 1, and the blocking case, 2.
# ---------------------------------------------------------------------------

# NOTE on `set +e`/`set -e` below: bats runs each test body under `set -e`
# (confirmed empirically -- a bare nonzero-exit command aborts the test
# immediately, before a later `[ "$?" -eq N ]` line ever runs). Every
# invocation below that is EXPECTED to return non-zero must therefore be
# fenced with `set +e` / `set -e` so the real exit status can be captured
# and asserted on, rather than the test aborting on the very statement it
# means to check.

@test "exit status 0 is preserved" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED
  set +e
  printf '' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null
  local got=$?
  set -e
  [ "$got" -eq 0 ]
}

@test "exit status 1 is preserved" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED
  set +e
  printf '' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 1 m \
    >/dev/null 2>/dev/null
  local got=$?
  set -e
  [ "$got" -eq 1 ]
}

@test "exit status 2 (the blocking case) is preserved" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED
  set +e
  printf '' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 2 m \
    >/dev/null 2>/dev/null
  local got=$?
  set -e
  [ "$got" -eq 2 ]
}

@test "exit status 2 is preserved with recording enabled too" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  set +e
  printf '' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 2 m \
    >/dev/null 2>/dev/null
  local got=$?
  set -e
  [ "$got" -eq 2 ]
}

# ---------------------------------------------------------------------------
# 6. A kind:hook record is written, carrying scope_note=single, and the
#    hook_event/matcher fields match the CLI flags given -- never read from
#    stdin.
# ---------------------------------------------------------------------------

@test "recording enabled: a kind:hook record is written with scope_note single" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  printf 'irrelevant-payload' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null
  [ "$?" -eq 0 ]

  [ -f "$EVENTS_FILE" ]
  [ "$(_line_count "$EVENTS_FILE")" = "1" ]

  _assert_present '"kind":"hook"' "$EVENTS_FILE"
  _assert_present '"scope_note":"single"' "$EVENTS_FILE"
  _assert_present '"hook_event":"PreToolUse"' "$EVENTS_FILE"
  _assert_present '"matcher":"Skill"' "$EVENTS_FILE"
  _assert_present '"exit":"0"' "$EVENTS_FILE"
  _assert_present '"ms":"' "$EVENTS_FILE"
}

# Pull an integer `"ms":"<digits>"` value out of the (single-line) events
# file. Deliberately requires the value to be pure digits -- a leftover
# decimal point or a comma would fail this extraction rather than silently
# produce a wrong number, which is exactly the shape of bug this test file
# exists to catch permanently.
_ms_value() {
  local f="$1" line
  line="$(grep -o '"ms":"[0-9]*"' "$f" | head -n1)" || return 1
  [ -n "$line" ] || return 1
  line="${line#*:\"}"
  line="${line%\"}"
  printf '%s' "$line"
}

# ---------------------------------------------------------------------------
# 6b. THE unit regression test. `TIMEFORMAT='%3R'` reports decimal SECONDS
#     with exactly three fraction digits (e.g. "0.204"); the on-disk field
#     is named `ms` and both the README and report.py read it as
#     MILLISECONDS. Writing raw %3R output straight into `ms` understates
#     every duration by exactly 1000x -- a 500 ms hook would read back as
#     "0.5 ms", comfortably under CON-7's 1 ms budget instead of 500x over
#     it. Every other test in this file wraps a sub-millisecond fixture
#     command, where "0.001" (seconds, wrong) and "1" (ms, right) both look
#     like "basically instant" -- which is exactly how this shipped
#     unnoticed. `sleep 0.2` is slow enough that seconds and milliseconds
#     are never visually confusable.
#
#     Margin is deliberately WIDE (150-600, nominally 200) to survive a
#     loaded CI runner without flaking: this test's entire job is to catch
#     a 1000x unit error, not to pin a precise duration, and a test that
#     flakes gets silenced rather than fixed. Confirmed failing against the
#     pre-fix wrapper: `sleep 0.2` wrote the raw, unconverted %3R value
#     ("0.204" or similar) straight into `ms`, so `_ms_value`'s digits-only
#     extraction below cannot even find a pure-integer `"ms":"..."` value in
#     the record and returns empty -- failing this test's `[ -n "$ms" ]`
#     line before the range check is ever reached, which is itself proof
#     the field was carrying seconds, not milliseconds.
# ---------------------------------------------------------------------------

@test "REGRESSION (1000x unit bug): a known ~200ms command records ms in a plausible millisecond range" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  "$WRAPPER" --event PreToolUse --matcher Skill -- "$(command -v sleep)" 0.2 \
    >/dev/null 2>/dev/null
  [ "$?" -eq 0 ]

  [ -f "$EVENTS_FILE" ]
  local ms
  ms="$(_ms_value "$EVENTS_FILE")"
  [ -n "$ms" ]
  [ "$ms" -ge 150 ]
  [ "$ms" -le "$(_perf_budget_ms 600)" ]
}

@test "a near-zero duration records ms as 0, never empty or garbage" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  printf 'p' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null

  [ -f "$EVENTS_FILE" ]
  local ms
  ms="$(_ms_value "$EVENTS_FILE")"
  [ -n "$ms" ]
  case "$ms" in
    ''|*[!0-9]*) false ;;
    *) ;;
  esac
  [ "$ms" -ge 0 ]
  [ "$ms" -lt "$(_perf_budget_ms 150)" ]
}

@test "a multi-second duration records ms with the integer multiplier exercised (not 1000x skipped)" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  "$WRAPPER" --event PreToolUse --matcher Skill -- "$(command -v sleep)" 1.3 \
    >/dev/null 2>/dev/null
  [ "$?" -eq 0 ]

  [ -f "$EVENTS_FILE" ]
  local ms
  ms="$(_ms_value "$EVENTS_FILE")"
  [ -n "$ms" ]
  # 1.3 seconds = ~1300ms. With the formula broken (int + frac instead of int*1000 + frac),
  # the result would be ~301ms. Our lower bound of 1150 catches the mutation while our upper
  # bound of 1800 allows for system load without flaking. This ensures the * 1000 multiplier
  # on the integer seconds term is actually exercised by the test, not hidden by int=0.
  [ "$ms" -ge 1150 ]
  [ "$ms" -le "$(_perf_budget_ms 1800)" ]
}

# ---------------------------------------------------------------------------
# 7. hook_event/matcher in the record match whatever CLI flags were given,
#    even when they look nothing like a real event/matcher pair -- proof the
#    values come from argv, not from guessing or from stdin content.
# ---------------------------------------------------------------------------

@test "the record's hook_event and matcher come from the CLI flags given" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  printf '{"hook_event":"SomethingElse","matcher":"NotThis"}' | \
    "$WRAPPER" --event SubagentStart --matcher '.*' -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null

  _assert_present '"hook_event":"SubagentStart"' "$EVENTS_FILE"
  _assert_present '"matcher":".*"' "$EVENTS_FILE"
  _assert_absent '"hook_event":"SomethingElse"' "$EVENTS_FILE"
  _assert_absent '"matcher":"NotThis"' "$EVENTS_FILE"
}

# ---------------------------------------------------------------------------
# 8. Recording disabled: no record, and no behaviour change at all (stdout,
#    stderr and exit status all match the unwrapped run exactly).
# ---------------------------------------------------------------------------

@test "recording disabled: no record and no behaviour change" {
  cd "$REPO"
  local direct_out="$TEST_DIR/direct2.out"
  local wrapped_out="$TEST_DIR/wrapped2.out"
  local direct_err="$TEST_DIR/direct2.err"
  local wrapped_err="$TEST_DIR/wrapped2.err"

  set +e
  printf 'stdin-payload\nwith two lines' | "$FIXTURE_CAT" 1 mkr \
    >"$direct_out" 2>"$direct_err"
  local direct_status=$?
  set -e

  unset CLAUDE_OBSERVABILITY_ENABLED
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  set +e
  printf 'stdin-payload\nwith two lines' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 1 mkr \
    >"$wrapped_out" 2>"$wrapped_err"
  local wrapped_status=$?
  set -e

  [ "$wrapped_status" -eq "$direct_status" ]
  cmp -s "$direct_out" "$wrapped_out"
  cmp -s "$direct_err" "$wrapped_err"

  # No record at all -- the data directory must not even have been created,
  # matching PRD F3's "off costs nothing".
  [ ! -e "$EVENTS_FILE" ]
}

# ---------------------------------------------------------------------------
# 9. The wrapper is absent from the hook path after "uninstall": running the
#    real fixture directly (as a session would once the wrapper entry is
#    removed from hook registration) behaves identically to running it
#    through the wrapper, and adds no kind:hook record -- nothing of the
#    wrapper's own bookkeeping remains once it is no longer in the chain.
# ---------------------------------------------------------------------------

@test "wrapper absent from the hook path after uninstall: direct run is unaffected and adds no record" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  # "install" + "reproduce": one run through the wrapper writes one record.
  printf 'p' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null
  [ -f "$EVENTS_FILE" ]
  [ "$(_line_count "$EVENTS_FILE")" = "1" ]

  # "uninstall": the hook is now invoked directly, wrapper out of the chain.
  local direct_out="$TEST_DIR/uninstalled.out"
  local direct_err="$TEST_DIR/uninstalled.err"
  printf 'p' | "$FIXTURE_CAT" 0 m >"$direct_out" 2>"$direct_err"
  local direct_status=$?

  [ "$direct_status" -eq 0 ]
  [ "$(cat "$direct_out")" = "p" ]

  # "read": no new record appeared from the direct run.
  [ "$(_line_count "$EVENTS_FILE")" = "1" ]
}

# ---------------------------------------------------------------------------
# 10. Stdin passed through byte-identically (Hazard 1) -- including no
#     trailing newline and an embedded NUL-free binary-ish byte sequence.
#     This is the test that would catch the wrapper reading the payload for
#     itself instead of taking event/matcher from argv.
# ---------------------------------------------------------------------------

@test "stdin is passed through byte-identically, no trailing newline" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED

  local input_file="$TEST_DIR/stdin_payload.bin"
  printf 'line-one\nline-two\twith-tab\xc3\xa9-accented-no-trailing-newline' > "$input_file"

  local wrapped_out="$TEST_DIR/stdin_echo.out"
  "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    <"$input_file" >"$wrapped_out" 2>/dev/null

  cmp -s "$input_file" "$wrapped_out"
}

@test "stdin is passed through byte-identically with recording enabled" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  local input_file="$TEST_DIR/stdin_payload2.bin"
  printf '{"session_id":"abc","tool_input":{"skill":"x"}}' > "$input_file"

  local wrapped_out="$TEST_DIR/stdin_echo2.out"
  "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    <"$input_file" >"$wrapped_out" 2>/dev/null

  cmp -s "$input_file" "$wrapped_out"
}

# ---------------------------------------------------------------------------
# 11. Output with no trailing newline, and interleaved stdout/stderr, are
#     both preserved exactly (each stream separately byte-identical).
# ---------------------------------------------------------------------------

@test "output with no trailing newline is preserved exactly" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  local wrapped_out="$TEST_DIR/notrail.out"
  printf 'no-trailing-newline-in' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >"$wrapped_out" 2>/dev/null

  [ "$(cat "$wrapped_out")" = "no-trailing-newline-in" ]
  # Byte-exact, not just string-equal after $()-style trimming.
  local expected_bytes wrapped_bytes
  expected_bytes="$(printf 'no-trailing-newline-in' | wc -c)"
  wrapped_bytes="$(wc -c <"$wrapped_out")"
  [ "${expected_bytes// /}" = "${wrapped_bytes// /}" ]
}

@test "interleaved stdout and stderr are each preserved byte-identically" {
  cd "$REPO"
  local direct_out="$TEST_DIR/inter_direct.out"
  local direct_err="$TEST_DIR/inter_direct.err"
  local wrapped_out="$TEST_DIR/inter_wrapped.out"
  local wrapped_err="$TEST_DIR/inter_wrapped.err"

  "$FIXTURE_INTERLEAVED" 0 >"$direct_out" 2>"$direct_err" </dev/null

  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_INTERLEAVED" 0 \
    >"$wrapped_out" 2>"$wrapped_err" </dev/null

  cmp -s "$direct_out" "$wrapped_out"
  cmp -s "$direct_err" "$wrapped_err"
}

# ---------------------------------------------------------------------------
# 12. CON-5: a failure inside the logging path (the events directory cannot
#     be created because a plain file already occupies that path) leaves the
#     wrapped command's exit status and both streams completely untouched.
# ---------------------------------------------------------------------------

@test "CON-5: a logging-path failure leaves exit status and streams untouched" {
  cd "$REPO"
  local blocked="$TEST_DIR/blocked_data_dir"
  printf 'not a directory' > "$blocked"

  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$blocked"

  local direct_out="$TEST_DIR/con5_direct.out"
  local direct_err="$TEST_DIR/con5_direct.err"
  local wrapped_out="$TEST_DIR/con5_wrapped.out"
  local wrapped_err="$TEST_DIR/con5_wrapped.err"

  set +e
  printf 'payload' | "$FIXTURE_CAT" 2 mk >"$direct_out" 2>"$direct_err"
  local direct_status=$?
  set -e

  set +e
  printf 'payload' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 2 mk \
    >"$wrapped_out" 2>"$wrapped_err"
  local wrapped_status=$?
  set -e

  [ "$wrapped_status" -eq "$direct_status" ]
  [ "$wrapped_status" -eq 2 ]
  cmp -s "$direct_out" "$wrapped_out"
  cmp -s "$direct_err" "$wrapped_err"
}

# ---------------------------------------------------------------------------
# 13. The wrapper still runs the hook correctly (transparent passthrough)
#     when logwrite.sh cannot be sourced at all -- copy the wrapper alone to
#     a directory with no logwrite.sh alongside it.
# ---------------------------------------------------------------------------

@test "the wrapper still runs the hook when logwrite.sh cannot be sourced" {
  local lonely_dir="$TEST_DIR/lonely"
  mkdir -p "$lonely_dir"
  cp "$WRAPPER" "$lonely_dir/timed-wrapper.sh"
  chmod +x "$lonely_dir/timed-wrapper.sh"
  # Deliberately no logwrite.sh here.

  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  local direct_out="$TEST_DIR/lonely_direct.out"
  local wrapped_out="$TEST_DIR/lonely_wrapped.out"

  printf 'payload-for-lonely' | "$FIXTURE_CAT" 0 lm >"$direct_out" 2>/dev/null
  local direct_status=$?

  printf 'payload-for-lonely' | \
    "$lonely_dir/timed-wrapper.sh" --event PreToolUse --matcher Skill -- \
    "$FIXTURE_CAT" 0 lm >"$wrapped_out" 2>/dev/null
  local wrapped_status=$?

  [ "$wrapped_status" -eq "$direct_status" ]
  [ "$wrapped_status" -eq 0 ]
  cmp -s "$direct_out" "$wrapped_out"
}

# ---------------------------------------------------------------------------
# 14. The wrapper does not abort a strict `set -euo pipefail` caller (same
#     posture as the other adapters -- CON-5's spirit applied to the
#     wrapper's own invocation).
# ---------------------------------------------------------------------------

@test "set -e survival: the wrapper does not abort a strict caller" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  run env "CLAUDE_OBSERVABILITY_ENABLED=1" "CLAUDE_OBSERVABILITY_DATA=$DATA_DIR" \
    bash -c "
      set -euo pipefail
      cd '$REPO'
      echo BEFORE
      printf 'x' | '$WRAPPER' --event PreToolUse --matcher Skill -- '$FIXTURE_CAT' 0 m >/dev/null 2>/dev/null
      echo AFTER
    "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]
}

# ---------------------------------------------------------------------------
# 15. CON-3: the recorded `ms` value uses a dot decimal separator even under
#     a comma-decimal locale. This is the exact bug class recorded in this
#     repo's own memory (printf '%.0f' under a comma locale) applied to
#     `time`'s TIMEFORMAT output instead.
# ---------------------------------------------------------------------------

@test "CON-3: ms uses a dot decimal separator even under a comma-decimal locale" {
  if ! locale -a 2>/dev/null | grep -qi '^de_DE'; then
    skip "de_DE locale not available on this machine"
  fi

  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  export LC_ALL
  LC_ALL="$(locale -a 2>/dev/null | grep -i '^de_DE' | head -n1)"

  printf 'p' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null

  [ -f "$EVENTS_FILE" ]
  _assert_absent '"ms":"0,' "$EVENTS_FILE"
  _assert_absent '"ms":"1,' "$EVENTS_FILE"
}

# ---------------------------------------------------------------------------
# 16. Never writes to stdout from the logging path -- the wrapper's own
#     stdout carries only what the wrapped command itself produced.
# ---------------------------------------------------------------------------

@test "the wrapper's logging path never writes to stdout" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  local wrapped_out="$TEST_DIR/nostdout.out"
  printf '' | "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >"$wrapped_out" 2>/dev/null

  # FIXTURE_CAT with empty stdin produces empty stdout -- so the wrapper's
  # own file must be empty too, proving nothing from the logging path leaked
  # onto the wrapped command's stdout.
  [ ! -s "$wrapped_out" ]
}

# ---------------------------------------------------------------------------
# T3.5 SESSION CAVEAT: the hook record's `session` field comes from the
# environment variable $CLAUDE_CODE_SESSION_ID, not from the payload stdin.
# It is taken as-is when present, and empty when absent. This test suite
# verifies that assumption (marked UNVERIFIED in the SDD, T3.6 confirms it
# against live sessions).
# ---------------------------------------------------------------------------

@test "T3.5: with CLAUDE_CODE_SESSION_ID set, the hook record carries that session value" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  export CLAUDE_CODE_SESSION_ID="test-session-abc123"

  printf 'payload-with-session' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null

  [ -f "$EVENTS_FILE" ]
  _assert_present '"session":"test-session-abc123"' "$EVENTS_FILE"
}

@test "T3.5: with CLAUDE_CODE_SESSION_ID unset, the hook record carries an empty session" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  unset CLAUDE_CODE_SESSION_ID

  printf 'payload-no-session' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null

  [ -f "$EVENTS_FILE" ]
  _assert_present '"session":""' "$EVENTS_FILE"
  # Verify the wrapper still functioned correctly despite empty session
  _assert_present '"kind":"hook"' "$EVENTS_FILE"
  _assert_present '"exit":"0"' "$EVENTS_FILE"
}

@test "T3.5: session comes from the env var, not parsed from stdin payload" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  export CLAUDE_CODE_SESSION_ID="env-var-session"

  # Feed a different session_id in the payload on stdin
  printf '{"session_id":"payload-session-different","tool_input":{"skill":"test"}}' | \
    "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    >"$TEST_DIR/payload_pass_check.out" 2>/dev/null

  [ -f "$EVENTS_FILE" ]
  # The record must carry the env var's value, not the payload's
  _assert_present '"session":"env-var-session"' "$EVENTS_FILE"
  _assert_absent '"session":"payload-session-different"' "$EVENTS_FILE"

  # Verify stdin was passed through byte-identically (it reached the fixture)
  [ "$(cat "$TEST_DIR/payload_pass_check.out")" = '{"session_id":"payload-session-different","tool_input":{"skill":"test"}}' ]
}

@test "T3.5: stdin is passed through byte-identically with CLAUDE_CODE_SESSION_ID set" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  export CLAUDE_CODE_SESSION_ID="test-session"

  local input_file="$TEST_DIR/stdin_with_session_env.bin"
  printf 'multi-line\nstdin\nwith\ttabs\xc3\xa9' > "$input_file"

  local wrapped_out="$TEST_DIR/stdin_with_session_env.out"
  "$WRAPPER" --event PreToolUse --matcher Skill -- "$FIXTURE_CAT" 0 m \
    <"$input_file" >"$wrapped_out" 2>/dev/null

  cmp -s "$input_file" "$wrapped_out"
}

# ---------------------------------------------------------------------------
# `timeout` is GNU coreutils and is NOT on macOS -- neither is `gtimeout`
# unless someone installed coreutils. The bats CI matrix includes
# macos-latest, where every `timeout`-bounded test below exited 127 (command
# not found) rather than exercising the wrapper at all. `_timeout` keeps
# coreutils' contract (124 on expiry, otherwise the command's own status) and
# falls back to perl, which ships on both runners.
#
# The fallback forks rather than exec'ing: an alarm timer survives exec but
# the ALRM handler does not, so an exec'd child would die with SIGALRM (142)
# instead of reporting 124. stdin is inherited by the child, which the
# pipeline-fed tests below depend on.
# ---------------------------------------------------------------------------

_timeout() {
  local secs="$1"
  shift

  if command -v timeout >/dev/null 2>&1; then
    command timeout "$secs" "$@"
    return $?
  fi
  if command -v gtimeout >/dev/null 2>&1; then
    command gtimeout "$secs" "$@"
    return $?
  fi

  perl -e '
    my $secs = shift @ARGV;
    my $pid  = fork();
    die "fork failed\n" unless defined $pid;
    if ($pid == 0) { exec { $ARGV[0] } @ARGV; exit 127; }
    $SIG{ALRM} = sub { kill "KILL", $pid; waitpid($pid, 0); exit 124 };
    alarm $secs;
    waitpid($pid, 0);
    my $st = $?;
    alarm 0;
    exit(($st & 127) ? 128 + ($st & 127) : ($st >> 8));
  ' "$secs" "$@"
}

# ---------------------------------------------------------------------------
# CRITICAL DEFECT (found live): `shift 2` in the argument parser is a no-op
# when only one positional parameter remains (bash leaves $@ unchanged and
# returns non-zero, which this parser ignores) -- so a `--event` or
# `--matcher` flag with no following value never advances $1, and the
# `while [ $# -gt 0 ]` loop spins forever. A hang in the hook path blocks the
# tool call indefinitely: not fail-open, not fail-closed. Every test below is
# bounded by `timeout` so a regression fails the suite instead of wedging the
# run.
# ---------------------------------------------------------------------------

@test "malformed: --event with no value does not hang (bounded by timeout)" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED
  run _timeout 5 "$WRAPPER" --event
  [ "$status" -ne 124 ]
  [ "$status" -eq 0 ]
}

@test "malformed: --matcher trailing with no value, no --, does not hang and does not exec the flag" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED
  run _timeout 5 "$WRAPPER" --event PreToolUse --matcher
  [ "$status" -ne 124 ]
  [ "$status" -ne 127 ]
  [ "$status" -eq 0 ]
}

@test "malformed: --event with no value does not hang, recording enabled" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"
  run _timeout 5 "$WRAPPER" --matcher Skill --event
  [ "$status" -ne 124 ]
  [ "$status" -eq 0 ]
}

@test "regression guard: --matcher \"\" (legitimate empty matcher) with a proper command still runs" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED

  local wrapped_out="$TEST_DIR/emptymatcher.out"
  set +e
  printf 'x' | _timeout 5 "$WRAPPER" --event PreToolUse --matcher "" -- "$FIXTURE_CAT" 0 m \
    >"$wrapped_out" 2>/dev/null
  local got=$?
  set -e

  [ "$got" -eq 0 ]
  [ "$(cat "$wrapped_out")" = "x" ]
}

@test "regression guard: --matcher \"\" with recording enabled still writes the record with an empty matcher" {
  cd "$REPO"
  export CLAUDE_OBSERVABILITY_ENABLED=1
  export CLAUDE_OBSERVABILITY_DATA="$DATA_DIR"

  printf 'x' | _timeout 5 "$WRAPPER" --event PreToolUse --matcher "" -- "$FIXTURE_CAT" 0 m \
    >/dev/null 2>/dev/null

  [ -f "$EVENTS_FILE" ]
  _assert_present '"matcher":""' "$EVENTS_FILE"
}

@test "malformed: no -- separator at all still runs the command via the existing fallthrough" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED

  local direct_out="$TEST_DIR/noSep_direct.out"
  local wrapped_out="$TEST_DIR/noSep_wrapped.out"

  printf 'y' | "$FIXTURE_CAT" 0 m >"$direct_out" 2>/dev/null
  local direct_status=$?

  set +e
  printf 'y' | _timeout 5 "$WRAPPER" --event PreToolUse --matcher Skill "$FIXTURE_CAT" 0 m \
    >"$wrapped_out" 2>/dev/null
  local wrapped_status=$?
  set -e

  [ "$wrapped_status" -ne 124 ]
  [ "$wrapped_status" -eq "$direct_status" ]
  cmp -s "$direct_out" "$wrapped_out"
}

@test "malformed: -- with no command after it exits 0 without hanging" {
  cd "$REPO"
  unset CLAUDE_OBSERVABILITY_ENABLED
  run _timeout 5 "$WRAPPER" --event PreToolUse --matcher Skill --
  [ "$status" -ne 124 ]
  [ "$status" -eq 0 ]
}
