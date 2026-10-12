#!/usr/bin/env bats
#
# plugins/tcs-helper/tests/bats/observability-tool.bats
#
# spec 021 (observability v2), T2.1: log_tool.sh -- dispatch on tool_name, the
# non-git Bash fast path, and the skill (tool route) and dispatch records.
# The git record itself is T2.2; here a git-looking Bash payload only has to
# REACH the hand-off point (it sources the writer).
#
# The adapter is exec'd as an external process, payload on stdin, as the
# harness does. The "nothing was sourced" assertions use a stub fixture: a
# copy of the script next to a logwrite.sh/git_ops.sh that drop a marker file
# when sourced, so the assertion can fail (a plain output check cannot).

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  SCRIPTS="$REPO_ROOT/plugins/tcs-helper/scripts/observability"
  ADAPTER="$SCRIPTS/log_tool.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-tool.XXXXXX")"

  REPO="$TEST_DIR/github/myrepo"
  mkdir -p "$REPO"
  export GIT_CONFIG_GLOBAL=/dev/null
  git -C "$REPO" init -q -b main
  git -C "$REPO" config user.email "t@t"
  git -C "$REPO" config user.name "t"
  git -C "$REPO" config commit.gpgsign false
  printf 'base\n' > "$REPO/base.txt"
  git -C "$REPO" add base.txt
  git -C "$REPO" commit -q -m "base"

  # Stub fixture: the real script beside writers that only leave markers.
  STUB="$TEST_DIR/stub"
  MARKER="$TEST_DIR/sourced.marker"
  mkdir -p "$STUB"
  cp "$ADAPTER" "$STUB/log_tool.sh"
  printf ': > "%s"\n_observability_field() { :; }\n_observability_write() { :; }\n' "$MARKER" > "$STUB/logwrite.sh"
  printf ': > "%s.git_ops"\n' "$MARKER" > "$STUB/git_ops.sh"

  DATA="$TEST_DIR/data"
  EVENTS="$DATA/observability/events.jsonl"

  # Warm the fixtures: macOS charges 150-290 ms for the first exec of a file.
  printf '{}' | CLAUDE_OBSERVABILITY_ENABLED=1 "$ADAPTER" >/dev/null 2>&1
  printf '{}' | CLAUDE_OBSERVABILITY_ENABLED=1 "$STUB/log_tool.sh" >/dev/null 2>&1
  rm -f "$MARKER" "$MARKER.git_ops"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Run <script> with <payload> on stdin from cwd $REPO, recording enabled.
# Extra env assignments may follow as NAME=VALUE arguments.
_run_with() {
  local script="$1" payload="$2"
  shift 2
  run --separate-stderr env CLAUDE_OBSERVABILITY_ENABLED=1 \
    CLAUDE_OBSERVABILITY_DATA="$DATA" "$@" \
    bash -c 'cd "$1" && printf "%s" "$2" | "$3"' _ "$REPO" "$payload" "$script"
}

_run_tool() { _run_with "$ADAPTER" "$@"; }

# Same, payload read from a file (a 200 KB payload does not fit in argv).
_run_file() {
  local script="$1" file="$2"
  run --separate-stderr env CLAUDE_OBSERVABILITY_ENABLED=1 \
    CLAUDE_OBSERVABILITY_DATA="$DATA" \
    bash -c 'cd "$1" && "$2" < "$3"' _ "$REPO" "$script" "$file"
}

_hook() {   # _hook <tool_name> <tool_input json> [extra top-level json fragment]
  printf '{"session_id":"sess-t","transcript_path":"/home/u/github/.claude/projects/x/s.jsonl","cwd":"%s"%s,"permission_mode":"default","hook_event_name":"PreToolUse","tool_name":"%s","tool_input":%s,"tool_use_id":"toolu_01ABC"}' \
    "$REPO" "${3:-}" "$1" "$2"
}

_assert_absent() {
  if grep -qF -- "$1" "$2"; then printf 'LEAK: %s in %s\n' "$1" "$2" >&2; return 1; fi
  return 0
}

_assert_present() {
  if grep -qF -- "$1" "$2"; then return 0; fi
  printf 'MISSING: %s in %s\n' "$1" "$2" >&2
  return 1
}

_assert_silent() {
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

# ---------------------------------------------------------------------------
# Skill, tool route
# ---------------------------------------------------------------------------

@test "Skill payload writes one skill record with route tool" {
  _run_tool "$(_hook Skill '{"skill":"tcs-issues:issue","args":"CANARY-ARGS-1"}')"
  _assert_silent
  [ "$(wc -l < "$EVENTS" | tr -d ' ')" = "1" ]
  _assert_present '"kind":"skill"' "$EVENTS"
  _assert_present '"skill":"tcs-issues:issue"' "$EVENTS"
  _assert_present '"route":"tool"' "$EVENTS"
  _assert_present '"session":"sess-t"' "$EVENTS"
  _assert_absent 'CANARY-ARGS-1' "$EVENTS"
}

# ---------------------------------------------------------------------------
# Agent dispatch
# ---------------------------------------------------------------------------

@test "named Agent payload writes a dispatch record from the main session" {
  _run_tool "$(_hook Agent '{"description":"CANARY-DESC-7","prompt":"CANARY-PROMPT-1","subagent_type":"Explore","name":"probe-1"}')"
  _assert_silent
  _assert_present '"kind":"dispatch"' "$EVENTS"
  _assert_present '"subagent_type":"Explore"' "$EVENTS"
  _assert_present '"name":"probe-1"' "$EVENTS"
  _assert_present '"tool_use_id":"toolu_01ABC"' "$EVENTS"
  _assert_present '"caller":"main"' "$EVENTS"
  _assert_absent 'caller_agent' "$EVENTS"
  _assert_absent 'CANARY-PROMPT-1' "$EVENTS"
  _assert_absent 'CANARY-DESC-7' "$EVENTS"
}

@test "unnamed Agent payload writes name as empty string" {
  _run_tool "$(_hook Agent '{"description":"d","prompt":"p","subagent_type":"Explore"}')"
  _assert_silent
  _assert_present '"name":""' "$EVENTS"
  _assert_present '"subagent_type":"Explore"' "$EVENTS"
}

@test "Agent payload inside a subagent records caller subagent with its type and id" {
  _run_tool "$(_hook Agent '{"description":"d","prompt":"p","subagent_type":"Explore","name":"n"}' ',"agent_id":"ag-123","agent_type":"general-purpose"')"
  _assert_silent
  _assert_present '"caller":"subagent"' "$EVENTS"
  _assert_present '"caller_agent_type":"general-purpose"' "$EVENTS"
  _assert_present '"caller_agent_id":"ag-123"' "$EVENTS"
  _assert_present '"subagent_type":"Explore"' "$EVENTS"
}

@test "a prompt that quotes agent_id keys cannot forge the caller" {
  _run_tool "$(_hook Agent '{"description":"d","prompt":"{\"agent_id\":\"forged\"}","subagent_type":"Explore"}')"
  _assert_silent
  _assert_present '"caller":"main"' "$EVENTS"
  _assert_absent 'forged' "$EVENTS"
}

@test "description appears only with detail on, prompt never" {
  _run_tool "$(_hook Agent '{"description":"CANARY-DESC-7","prompt":"CANARY-PROMPT-1","subagent_type":"Explore"}')" \
    CLAUDE_OBSERVABILITY_DETAIL=1
  _assert_silent
  _assert_present 'CANARY-DESC-7' "$EVENTS"
  _assert_absent 'CANARY-PROMPT-1' "$EVENTS"
}

# ---------------------------------------------------------------------------
# Bash: the fast path
# ---------------------------------------------------------------------------

@test "non-git Bash payload writes nothing and sources nothing" {
  _run_with "$STUB/log_tool.sh" "$(_hook Bash '{"command":"ls -la","description":"list"}')"
  _assert_silent
  [ ! -e "$MARKER" ]
  [ ! -e "$MARKER.git_ops" ]
  [ ! -e "$EVENTS" ]
}

@test "non-git Bash payload sources nothing even when cwd and transcript contain github" {
  # setup() puts the repo under .../github/..., and the transcript path has
  # github too; the hook payload below carries both.
  _run_with "$STUB/log_tool.sh" "$(_hook Bash '{"command":"npm test"}')"
  _assert_silent
  [ ! -e "$MARKER" ]
}

@test "positive control: a git Bash payload does source the writer" {
  _run_with "$STUB/log_tool.sh" "$(_hook Bash '{"command":"git status"}')"
  _assert_silent
  [ -e "$MARKER" ]
}

@test "positive control: the stub is sourced for Skill and Agent payloads" {
  _run_with "$STUB/log_tool.sh" "$(_hook Skill '{"skill":"x"}')"
  [ -e "$MARKER" ]
  rm -f "$MARKER"
  _run_with "$STUB/log_tool.sh" "$(_hook Agent '{"subagent_type":"x"}')"
  [ -e "$MARKER" ]
}

@test "other tool names write nothing and source nothing" {
  local t
  for t in Read Edit Task Write Grep; do
    _run_with "$STUB/log_tool.sh" "$(_hook "$t" '{"file_path":"/x"}')"
    _assert_silent
    [ ! -e "$MARKER" ]
  done
}

# ---------------------------------------------------------------------------
# Fail open
# ---------------------------------------------------------------------------

@test "disabled: no record, stdin drained, exit 0, silent" {
  # Drain proof: a producer writing more than a pipe buffer (64 KB) is killed
  # by SIGPIPE (status 141) if the adapter exits without reading. The shell
  # gets /dev/null as its own stdin so nothing here can block on an inherited
  # terminal or pipe.
  local big
  big="$(printf 'x%.0s' $(seq 1 200000))"
  _hook Skill "{\"skill\":\"x\",\"args\":\"$big\"}" > "$TEST_DIR/drain.json"
  run --separate-stderr env -u CLAUDE_OBSERVABILITY_ENABLED CLAUDE_OBSERVABILITY_DATA="$DATA" \
    bash -c 'cd "$1" && cat "$2" | "$3"; echo "producer:${PIPESTATUS[0]} adapter:${PIPESTATUS[1]}"' \
    _ "$REPO" "$TEST_DIR/drain.json" "$ADAPTER" < /dev/null
  [ "$status" -eq 0 ]
  [ "$output" = "producer:0 adapter:0" ]
  [ -z "$stderr" ]
  [ ! -e "$EVENTS" ]
}

@test "disabled: a stub is not sourced" {
  run --separate-stderr env -u CLAUDE_OBSERVABILITY_ENABLED CLAUDE_OBSERVABILITY_DATA="$DATA" \
    bash -c 'cd "$1" && printf "%s" "$2" | "$3"' _ "$REPO" "$(_hook Skill '{"skill":"x"}')" "$STUB/log_tool.sh" < /dev/null
  _assert_silent
  [ ! -e "$MARKER" ]
}

@test "malformed, empty and whitespace payloads exit 0 silently" {
  local p
  for p in '' '   ' '{"tool_name":"Skill"' 'not json at all' '{"tool_name":"Agent","tool_input":' '"tool_name":"Bash"'; do
    _run_tool "$p"
    _assert_silent
  done
}

@test "a 200 KB payload exits 0 silently and records correctly" {
  local big
  big="$(printf 'x%.0s' $(seq 1 200000))"
  _hook Agent "{\"description\":\"d\",\"prompt\":\"$big\",\"subagent_type\":\"Explore\"}" > "$TEST_DIR/big1.json"
  local t0 t1
  t0="$(_now_ms)"
  _run_file "$ADAPTER" "$TEST_DIR/big1.json"
  t1="$(_now_ms)"
  _assert_silent
  _assert_present '"subagent_type":"Explore"' "$EVENTS"
  _assert_present '"tool_use_id":"toolu_01ABC"' "$EVENTS"
  # Keys sit behind a 200 KB prompt; a quadratic extractor took 41 s each.
  printf "200KB Agent dispatch: %s ms\n" "$((t1 - t0))" >&3
  [ $((t1 - t0)) -le "$(_perf_budget_ms 1000)" ]
  _hook Bash "{\"command\":\"echo $big\"}" > "$TEST_DIR/big2.json"
  _run_file "$ADAPTER" "$TEST_DIR/big2.json"
  _assert_silent
}

# ---------------------------------------------------------------------------
# Performance: the non-git path (CON-7)
# ---------------------------------------------------------------------------

# Copied, not sourced: these observability suites are standalone.
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

@test "perf: the non-git Bash path costs no more than a bare shell start plus cat" {
  if ! command -v perl >/dev/null 2>&1; then skip "perl not available for a sub-second clock"; fi

  local payload_file="$TEST_DIR/p.json" big
  big="$(printf 'y%.0s' $(seq 1 50000))"
  printf '%s' "$(_hook Bash "{\"command\":\"ls $big\"}")" > "$payload_file"

  local i t0 t1 per_call budget
  # Warm-up exec of the exact file under test.
  CLAUDE_OBSERVABILITY_ENABLED=1 CLAUDE_OBSERVABILITY_DATA="$DATA" "$STUB/log_tool.sh" < "$payload_file" >/dev/null 2>&1
  t0="$(_now_ms)"
  for i in 1 2 3 4 5 6 7 8 9 10; do
    CLAUDE_OBSERVABILITY_ENABLED=1 CLAUDE_OBSERVABILITY_DATA="$DATA" "$STUB/log_tool.sh" < "$payload_file" >/dev/null 2>&1
  done
  t1="$(_now_ms)"
  per_call=$(( (t1 - t0) / 10 ))
  budget="$(_perf_budget_ms 100)"
  printf 'non-git per-call: %d ms (budget %d ms)\n' "$per_call" "$budget" >&3
  [ "$per_call" -le "$budget" ]
  [ ! -e "$MARKER" ]
}
