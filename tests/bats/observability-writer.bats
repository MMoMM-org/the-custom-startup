#!/usr/bin/env bats
#
# tests/bats/observability-writer.bats
#
# spec 018 (observability of what loads and fires). T1.1 (the data-directory
# resolver) is covered above. This file also covers T1.2 — append, escape,
# truncate and rotate. Redaction and field extraction (T1.3, `_field`) are a
# later task in the same plan; this suite must not assume they exist yet.

bats_require_minimum_version 1.5.0
#
# The resolver under test lives in .claude/observability/logwrite.sh, which is
# untracked by design: `.claude/` is gitignored wholesale in this repo (see
# .gitignore), and Phase 1 ships a library and its tests only — nothing is
# registered as a hook, so a defect here cannot reach a real session. This
# suite is the tracked evidence that the untracked file behaves.
#
# _observability_data_dir duplicates
# plugins/tcs-git-helpers/scripts/lib/plugin_data.sh's _plugin_data_dir
# contract on purpose (ADR-1): a self-contained writer can't source a plugin
# library, so the fallback has to reproduce the harness's own directory shape
# rather than invent a new one. The parity test below is what keeps that
# deliberate copy honest — same pattern as
# plugins/tcs-git-helpers/tests/bats/cache-path-parity.bats.
#
# bash 3.2 compatible.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WRITER="$REPO_ROOT/.claude/observability/logwrite.sh"
  PLUGIN_DATA_LIB="$REPO_ROOT/plugins/tcs-git-helpers/scripts/lib/plugin_data.sh"

  # macOS exports TMPDIR with a trailing slash. Left in, every fixture path
  # carries a "//" and the parity comparison ends up testing the test's own
  # string building rather than the resolvers.
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability.XXXXXX")"
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

  # git rev-parse resolves symlinks (/tmp -> /private/tmp on macOS); every
  # resolver sees the canonical form, so the expectations must too.
  REPO_CANONICAL="$(cd "$REPO" && git rev-parse --show-toplevel)"
  REPO_NAME="$(basename "$REPO_CANONICAL")"
}

teardown() {
  # T1.2's fail-open cases chmod parts of TEST_DIR read-only to simulate an
  # unwritable directory; restore write/execute before removal so teardown
  # itself cannot fail (same pattern as lib_audit_log.bats's teardown).
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Resolver drivers
#
# $1 is the env var to control ("unset", or a value to set it to).
# ---------------------------------------------------------------------------

_run_env() {
  local var="$1" mode="$2" cmd="$3"
  if [ "$mode" = "unset" ]; then
    env -u "$var" "HOME=$FAKE_HOME" bash -c "$cmd"
  else
    env "$var=$mode" "HOME=$FAKE_HOME" bash -c "$cmd"
  fi
}

_via_writer() {
  _run_env CLAUDE_OBSERVABILITY_DATA "$1" \
    "cd '$REPO' && . '$WRITER' && _observability_data_dir"
}

_via_plugin() {
  _run_env CLAUDE_PLUGIN_DATA "$1" \
    "cd '$REPO' && . '$PLUGIN_DATA_LIB' && _plugin_data_dir"
}

# ---------------------------------------------------------------------------
# 1. CLAUDE_OBSERVABILITY_DATA override
# ---------------------------------------------------------------------------

@test "resolver: CLAUDE_OBSERVABILITY_DATA wins, trailing slashes stripped" {
  run _via_writer "$TEST_DIR/explicit///"
  [ "$status" -eq 0 ]
  [ "$output" = "$TEST_DIR/explicit" ]
}

# ---------------------------------------------------------------------------
# 2. Default derivation
# ---------------------------------------------------------------------------

@test "resolver: unset derives HOME/.claude/plugins/data/observability-<repo>" {
  run _via_writer unset
  [ "$status" -eq 0 ]
  [ "$output" = "$FAKE_HOME/.claude/plugins/data/observability-${REPO_NAME}" ]
}

# ---------------------------------------------------------------------------
# 3. Outside a git repository
# ---------------------------------------------------------------------------

@test "resolver: outside a git repo returns non-zero and prints nothing" {
  run env -u CLAUDE_OBSERVABILITY_DATA "HOME=$FAKE_HOME" \
    "GIT_CEILING_DIRECTORIES=$TEST_DIR" \
    bash -c "cd '$TEST_DIR' && . '$WRITER' && _observability_data_dir"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# 4. Parity with the plugin resolver — both are actually executed, not
#    restated as two copies of the same expected string.
# ---------------------------------------------------------------------------

@test "parity: observability resolver matches the plugin resolver's shape" {
  local obs_path plugin_path obs_parent plugin_parent

  obs_path="$(_via_writer unset)"
  plugin_path="$(_via_plugin unset)"

  [ -n "$obs_path" ]
  [ -n "$plugin_path" ]

  obs_parent="$(dirname "$obs_path")"
  plugin_parent="$(dirname "$plugin_path")"

  # Same parent directory (same $HOME/.claude/plugins/data root).
  [ "$obs_parent" = "$plugin_parent" ]

  # Same repo-basename derivation, differing only by the plugin-specific
  # prefix — "the same shape", not a byte-identical path.
  [ "$(basename "$obs_path")" = "observability-${REPO_NAME}" ]
  [ "$(basename "$plugin_path")" = "tcs-git-helpers-${REPO_NAME}" ]
}

@test "parity: trailing-slash stripping agrees under override" {
  local override obs_path plugin_path
  override="$TEST_DIR/explicit///"

  obs_path="$(_via_writer "$override")"
  plugin_path="$(_via_plugin "$override")"

  # Both resolvers strip the same override the same way — the case test 1
  # only exercised for the writer alone. If either copy's stripping loop
  # ever diverges (e.g. one starts collapsing internal "//" too), this is
  # the assertion that catches it.
  [ "$obs_path" = "$TEST_DIR/explicit" ]
  [ "$plugin_path" = "$TEST_DIR/explicit" ]
  [ "$obs_path" = "$plugin_path" ]
}

# ---------------------------------------------------------------------------
# 5. SDD-AC-10 — resolved path is outside the repository working tree
# ---------------------------------------------------------------------------

@test "resolver: resolved path is outside the repository working tree" {
  local obs_path
  obs_path="$(_via_writer unset)"
  case "$obs_path" in
    "$REPO_CANONICAL"|"$REPO_CANONICAL"/*)
      echo "resolved path is inside the repo working tree: $obs_path" >&2
      return 1
      ;;
  esac
}

# ---------------------------------------------------------------------------
# T1.2 — append, escape, truncate and rotate.
#
# _observability_write is the single public entry point these tests drive:
#   _observability_write kind=<kind> session=<id>
# `ts` and `repo` are frozen fields the writer computes itself (SDD/ADR-8);
# a caller cannot override them. Every test below invokes the real function
# through a subshell so it exercises the exact resolution/gating/append path
# a hook adapter would.
# ---------------------------------------------------------------------------

# Runs _observability_write in a repo-rooted subshell with the enable switch
# on. $1 = data dir, $2 = kind, $3 = session. Positional passing (not string
# interpolation) so a session value can carry quotes, backslashes, control
# bytes or invalid UTF-8 without any additional escaping in the test itself.
_call_writer() {
  bash -c '
    data_dir="$1"; kind="$2"; session="$3"
    cd "'"$REPO"'" || exit 90
    . "'"$WRITER"'" || exit 91
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    _observability_write kind="$kind" session="$session"
  ' _ "$1" "$2" "$3"
}

# Same shape as _call_writer, but forwards any additional key=value pairs
# straight through to _observability_write — for exercising the generic
# "any other key=value pair is written through verbatim" branch (T1.2's own
# stated contract), which _call_writer above has no way to reach.
_call_writer_extra() {
  local data_dir="$1" kind="$2" session="$3"
  shift 3
  bash -c '
    data_dir="$1"; kind="$2"; session="$3"; shift 3
    cd "'"$REPO"'" || exit 90
    . "'"$WRITER"'" || exit 91
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    _observability_write kind="$kind" session="$session" "$@"
  ' _ "$data_dir" "$kind" "$session" "$@"
}

# Wraps a call to _observability_write between a known stdout line and a
# known stderr line, then exits with $2 — the shape the fail-open cases need
# to prove the CALLER's status/streams, not the writer's, are what matters.
# $1 = data dir, $2 = caller exit code.
_caller_wrapper() {
  bash -c '
    data_dir="$1"; exit_code="$2"
    cd "'"$REPO"'" || exit 95
    . "'"$WRITER"'" || exit 96
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    echo "CALLER_STDOUT"
    echo "CALLER_STDERR" >&2
    _observability_write kind=hook session=sess-fail
    exit "$exit_code"
  ' _ "$1" "$2"
}

# ---------------------------------------------------------------------------
# 1-2. Record shape and timestamp
# ---------------------------------------------------------------------------

@test "write: one JSON object per line carrying ts, kind, session, repo" {
  local data_dir="$TEST_DIR/rec1"
  run _call_writer "$data_dir" hook sess-1
  [ "$status" -eq 0 ]

  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify record content"
  fi
  run jq -e -c . "$file"
  [ "$status" -eq 0 ]
  run jq -r '.kind' "$file"
  [ "$output" = "hook" ]
  run jq -r '.session' "$file"
  [ "$output" = "sess-1" ]
  run jq -r 'has("ts")' "$file"
  [ "$output" = "true" ]
  run jq -r 'has("repo")' "$file"
  [ "$output" = "true" ]
  run jq -r '.repo' "$file"
  [ "$output" = "$REPO_NAME" ]
}

@test "write: ts is UTC RFC3339 at second precision" {
  local data_dir="$TEST_DIR/rec2"
  run _call_writer "$data_dir" hook sess-2
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to extract ts"
  fi
  local ts
  ts="$(jq -r '.ts' "$file")"
  [[ "$ts" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# ---------------------------------------------------------------------------
# 3-4. Escaping — quotes/backslashes and control characters
# ---------------------------------------------------------------------------

@test "write: backslashes and double quotes are escaped and the record still parses" {
  local data_dir="$TEST_DIR/rec3"
  local val='she said "hi" \ then left'
  run _call_writer "$data_dir" hook "$val"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify the escaped value round-trips"
  fi
  run jq -e -c . "$file"
  [ "$status" -eq 0 ]
  run jq -r '.session' "$file"
  [ "$output" = "$val" ]
}

@test "write: a literal newline, CR and tab are escaped so one record never splits" {
  local data_dir="$TEST_DIR/rec4"
  local val=$'line1\nline2\ttabbed\rcr'
  run _call_writer "$data_dir" hook "$val"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify the escaped value round-trips"
  fi
  run jq -e -c . "$file"
  [ "$status" -eq 0 ]
  run jq -r '.session' "$file"
  [ "$output" = "$val" ]
}

# ---------------------------------------------------------------------------
# 5. No forking in the write path
# ---------------------------------------------------------------------------

# This is a static grep over the source TEXT — a lightweight proxy for "no
# stream-editor process is forked while escaping", not equivalent to the
# runtime fork-COUNTING done by tests 21/22 below (which shadow `git` and
# count actual invocations). A word that merely contains "sed"/"jq"/"awk"
# as a substring inside a longer identifier would still be missed by \b
# word-boundary matching in the wrong direction, and this test would not
# catch a helper that forks one of these tools indirectly through another
# function it calls — it only proves the literal words are absent from
# this file's own text.
@test "write: escaping forks no sed, jq or awk process" {
  run grep -nE '\b(sed|jq|awk)\b' "$WRITER"
  [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 6. Field length limit and truncated:true
# ---------------------------------------------------------------------------

@test "write: a field over 256 characters is cut to 256 and truncated:true is set" {
  local data_dir="$TEST_DIR/rec6"
  local long
  long="$(printf 'x%.0s' $(seq 1 300))"
  [ "${#long}" -eq 300 ]

  run _call_writer "$data_dir" hook "$long"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify truncation"
  fi
  run jq -r '.session | length' "$file"
  [ "$output" = "256" ]
  run jq -r '.truncated' "$file"
  [ "$output" = "true" ]
}

@test "write: a field at or under 256 characters carries no truncated field" {
  local data_dir="$TEST_DIR/rec6b"
  run _call_writer "$data_dir" hook short
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify the absence of truncated"
  fi
  run jq -r 'has("truncated")' "$file"
  [ "$output" = "false" ]
}

# ---------------------------------------------------------------------------
# 7. Rotation: .jsonl -> .1 -> .2 -> .3, no .4 ever created
# ---------------------------------------------------------------------------

@test "write: rotation cascades .jsonl -> .1 -> .2 -> .3 with no .4 ever created" {
  local data_dir="$TEST_DIR/rec7"
  local dir="$data_dir/observability"
  local file="$dir/events.jsonl"
  mkdir -p "$dir"

  printf 'OLDEST_LOST\n' > "$file.3"
  printf 'OLD_TWO\n'     > "$file.2"
  printf 'OLD_ONE\n'     > "$file.1"
  dd if=/dev/zero of="$file" bs=1024 count=1000 status=none

  run wc -c < "$file"
  [ "${output// /}" = "1024000" ]

  run _call_writer "$data_dir" hook sess-rot
  [ "$status" -eq 0 ]

  [ ! -f "$file.4" ]
  [ -f "$file.3" ]
  run cat "$file.3"
  [ "$output" = "OLD_TWO" ]
  run cat "$file.2"
  [ "$output" = "OLD_ONE" ]
  run wc -c < "$file.1"
  [ "${output// /}" = "1024000" ]
  run wc -l < "$file"
  [ "${output// /}" = "1" ]
}

@test "write: below the rotation threshold, no .1 is created" {
  local data_dir="$TEST_DIR/rec7b"
  local dir="$data_dir/observability"
  local file="$dir/events.jsonl"
  mkdir -p "$dir"
  dd if=/dev/zero of="$file" bs=1 count=1023999 status=none

  run _call_writer "$data_dir" hook sess-norot
  [ "$status" -eq 0 ]

  [ ! -f "$file.1" ]
  run wc -c < "$file"
  [ "${output// /}" -gt 1023999 ]
}

# ---------------------------------------------------------------------------
# 8. Enable switch unset -> no directory, no file
# ---------------------------------------------------------------------------

@test "write: CLAUDE_OBSERVABILITY_ENABLED unset creates no directory and no file" {
  local data_dir="$TEST_DIR/rec8"
  run env -u CLAUDE_OBSERVABILITY_ENABLED "CLAUDE_OBSERVABILITY_DATA=$data_dir" \
    bash -c "cd '$REPO' && . '$WRITER' && _observability_write kind=hook session=sess-off"
  [ "$status" -eq 0 ]
  [ ! -e "$data_dir" ]
}

# ---------------------------------------------------------------------------
# 9. Fail-open: unwritable directory, simulated write failure, failed
#    rotation each leave the CALLER's exit status, stdout and stderr alone.
# ---------------------------------------------------------------------------

@test "fail-open: an unwritable directory leaves the caller's status and streams untouched" {
  local parent="$TEST_DIR/rec9a_parent"
  mkdir -p "$parent"
  chmod 500 "$parent"
  local data_dir="$parent/child"

  run --separate-stderr _caller_wrapper "$data_dir" 42
  [ "$status" -eq 42 ]
  [ "$output" = "CALLER_STDOUT" ]
  [ "$stderr" = "CALLER_STDERR" ]

  chmod 700 "$parent"
  [ ! -d "$data_dir" ]
}

@test "fail-open: a simulated write failure leaves the caller's status and streams untouched" {
  local data_dir="$TEST_DIR/rec9b"
  mkdir -p "$data_dir/observability"
  chmod 555 "$data_dir/observability"

  run --separate-stderr _caller_wrapper "$data_dir" 43
  [ "$status" -eq 43 ]
  [ "$output" = "CALLER_STDOUT" ]
  [ "$stderr" = "CALLER_STDERR" ]

  chmod 755 "$data_dir/observability"
}

@test "fail-open: a failed rotation leaves the caller's status and streams untouched" {
  local data_dir="$TEST_DIR/rec9c"
  local dir="$data_dir/observability"
  mkdir -p "$dir"
  dd if=/dev/zero of="$dir/events.jsonl" bs=1024 count=1000 status=none
  chmod 555 "$dir"

  run --separate-stderr _caller_wrapper "$data_dir" 44
  [ "$status" -eq 44 ]
  [ "$output" = "CALLER_STDOUT" ]
  [ "$stderr" = "CALLER_STDERR" ]

  chmod 755 "$dir"
}

# ---------------------------------------------------------------------------
# 10. Non-UTF-8 bytes replaced before reaching a field (CON-10)
# ---------------------------------------------------------------------------

@test "write: non-UTF-8 bytes are replaced with ? before reaching a field" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi

  local data_dir="$TEST_DIR/rec10"
  local bad=$'bad\xffbyte'
  run _call_writer "$data_dir" hook "$bad"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
data = open('$file', 'rb').read()
assert b'\xff' not in data, 'raw invalid UTF-8 byte reached the record'
assert b'bad?byte' in data, 'sanitized value with ? substitution is missing'
data.decode('utf-8')
"
  [ "$status" -eq 0 ]
}


# ---------------------------------------------------------------------------
# 11. CON-7: the write path forks `git rev-parse` at most once per record,
#    in BOTH the override and default data-dir paths (spec-compliance
#    finding: _observability_data_dir and _observability_repo_field used to
#    each fork it independently — up to two forks per record on the default,
#    real-world path where CLAUDE_OBSERVABILITY_DATA is unset).
# ---------------------------------------------------------------------------

@test "write: git rev-parse is forked at most once per record (override path)" {
  local data_dir="$TEST_DIR/recgit1"
  local counter="$TEST_DIR/recgit1_calls"
  : > "$counter"

  bash -c '
    data_dir="$1"; counter="$2"
    cd "'"$REPO"'" || exit 90
    . "'"$WRITER"'" || exit 91
    git() {
      if [ "$1" = "rev-parse" ]; then
        printf "x" >> "$counter"
      fi
      command git "$@"
    }
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    _observability_write kind=hook session=sess-gitcount-override
  ' _ "$data_dir" "$counter"

  local calls
  calls="$(wc -c < "$counter")"
  # Exactly one: the `repo` field always needs the toplevel, override or
  # not — "one fork in both paths is the goal, not zero".
  [ "${calls// /}" -eq 1 ]
}

@test "write: git rev-parse is forked at most once per record (default path)" {
  local counter="$TEST_DIR/recgit2_calls"
  : > "$counter"

  bash -c '
    counter="$1"
    cd "'"$REPO"'" || exit 90
    export HOME="'"$FAKE_HOME"'"
    . "'"$WRITER"'" || exit 91
    git() {
      if [ "$1" = "rev-parse" ]; then
        printf "x" >> "$counter"
      fi
      command git "$@"
    }
    export CLAUDE_OBSERVABILITY_ENABLED=1
    unset CLAUDE_OBSERVABILITY_DATA
    _observability_write kind=hook session=sess-gitcount-default
  ' _ "$counter"

  local calls
  calls="$(wc -c < "$counter")"
  # This is the path the finding was about: _observability_data_dir's own
  # repo-derived branch and _observability_repo_field must now share one
  # resolved toplevel instead of each forking independently.
  [ "${calls// /}" -eq 1 ]
}

# ---------------------------------------------------------------------------
# 12. CON-10 well-formedness: sequence-length checks alone accept four
#    structurally invalid byte patterns (RFC 3629 Table 3-7). Each must
#    still be replaced with '?', not passed through.
# ---------------------------------------------------------------------------

@test "write: an overlong 3-byte sequence (E0 80 80) is replaced with ?" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi
  local data_dir="$TEST_DIR/recutf1"
  local bad=$'ab\xe0\x80\x80cd'
  run _call_writer "$data_dir" hook "$bad"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
data = open('$file', 'rb').read()
assert b'\xe0\x80\x80' not in data, 'overlong 3-byte sequence reached the record'
assert b'ab' in data and b'cd' in data
data.decode('utf-8')
"
  [ "$status" -eq 0 ]
}

@test "write: a UTF-16 surrogate half (ED A0 80) is replaced with ?" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi
  local data_dir="$TEST_DIR/recutf2"
  local bad=$'ab\xed\xa0\x80cd'
  run _call_writer "$data_dir" hook "$bad"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
data = open('$file', 'rb').read()
assert b'\xed\xa0\x80' not in data, 'surrogate-half sequence reached the record'
assert b'ab' in data and b'cd' in data
data.decode('utf-8')
"
  [ "$status" -eq 0 ]
}

@test "write: an overlong 4-byte sequence (F0 80 80 80) is replaced with ?" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi
  local data_dir="$TEST_DIR/recutf3"
  local bad=$'ab\xf0\x80\x80\x80cd'
  run _call_writer "$data_dir" hook "$bad"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
data = open('$file', 'rb').read()
assert b'\xf0\x80\x80\x80' not in data, 'overlong 4-byte sequence reached the record'
assert b'ab' in data and b'cd' in data
data.decode('utf-8')
"
  [ "$status" -eq 0 ]
}

@test "write: a codepoint above U+10FFFF (F4 90 80 80) is replaced with ?" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi
  local data_dir="$TEST_DIR/recutf4"
  local bad=$'ab\xf4\x90\x80\x80cd'
  run _call_writer "$data_dir" hook "$bad"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
data = open('$file', 'rb').read()
assert b'\xf4\x90\x80\x80' not in data, 'out-of-range codepoint sequence reached the record'
assert b'ab' in data and b'cd' in data
data.decode('utf-8')
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 13. CON-10 well-formedness, accept side: the four boundary-valid sequences
#    that sit exactly one byte away from the four rejected cases above. A
#    later edit that tightens one bound by a single value would start
#    replacing legitimate non-ASCII path bytes with '?' and every existing
#    test would still pass, since none of them feeds valid multi-byte UTF-8
#    through the sanitizer. This is what would catch that regression.
# ---------------------------------------------------------------------------

@test "write: boundary-valid multi-byte UTF-8 sequences survive unchanged" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi
  local data_dir="$TEST_DIR/recutf5"
  # U+0800 (E0 A0 80), U+D7FF (ED 9F BF), U+10000 (F0 90 80 80),
  # U+10FFFF (F4 8F BF BF) — one byte away from the four rejected cases.
  local good=$'a\xe0\xa0\x80b\xed\x9f\xbfc\xf0\x90\x80\x80d\xf4\x8f\xbf\xbfe'
  run _call_writer "$data_dir" hook "$good"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
data = open('$file', 'rb').read()
assert b'\xe0\xa0\x80' in data, 'U+0800 (E0 A0 80) was altered'
assert b'\xed\x9f\xbf' in data, 'U+D7FF (ED 9F BF) was altered'
assert b'\xf0\x90\x80\x80' in data, 'U+10000 (F0 90 80 80) was altered'
assert b'\xf4\x8f\xbf\xbf' in data, 'U+10FFFF (F4 8F BF BF) was altered'
data.decode('utf-8')
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 14. The writer must not fail CLOSED under a `set -e` caller. Real hooks in
#    this repo already run under `set -euo pipefail`
#    (claude-docker-home/.claude/hooks/block-main-edits.sh,
#    session-start.sh) — this is not hypothetical. _caller_wrapper above
#    never sets `set -e`, so tests 17-19 cannot see this failure mode; these
#    three source the writer into a genuinely `set -euo pipefail` shell and
#    assert a line placed AFTER _observability_write still runs.
# ---------------------------------------------------------------------------

@test "set -e survival: outside a git repo, a line after the call still runs" {
  local outside="$TEST_DIR/outside_repo_sete"
  mkdir -p "$outside"

  run env -u CLAUDE_OBSERVABILITY_DATA "HOME=$FAKE_HOME" \
    "GIT_CEILING_DIRECTORIES=$TEST_DIR" \
    bash -c "
      set -euo pipefail
      cd '$outside'
      . '$WRITER'
      export CLAUDE_OBSERVABILITY_ENABLED=1
      echo BEFORE
      _observability_write kind=hook session=sete-outside
      echo AFTER
    "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]
}

@test "set -e survival: an unwritable PARENT directory (mkdir fails), a line after still runs" {
  local parent="$TEST_DIR/sete_unwritable_parent"
  mkdir -p "$parent"
  chmod 500 "$parent"
  local data_dir="$parent/child"

  run bash -c "
    set -euo pipefail
    cd '$REPO'
    . '$WRITER'
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA='$data_dir'
    echo BEFORE
    _observability_write kind=hook session=sete-unwritable-parent
    echo AFTER
  "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]

  chmod 700 "$parent"
}

# This is the coordinator's literal reproduction: the directory EXISTS (so
# `mkdir -p ... || return 0` above is a no-op success, never even reached as
# a failure), but is not writable — the abort happens at the FINAL APPEND
# (`printf ... >>"$events_file"`), the one line the original bug report
# named directly ("the return 0 at :348 is never reached when the append
# fails. That is literally SDD-AC-12's scenario").
@test "set -e survival: an existing unwritable directory (append fails), a line after still runs" {
  local data_dir="$TEST_DIR/sete_unwritable_existing"
  mkdir -p "$data_dir/observability"
  chmod 555 "$data_dir/observability"

  run bash -c "
    set -euo pipefail
    cd '$REPO'
    . '$WRITER'
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA='$data_dir'
    echo BEFORE
    _observability_write kind=hook session=sete-unwritable-existing
    echo AFTER
  "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]

  chmod 755 "$data_dir/observability"
}

@test "set -e survival: a failing date, a line after the call still runs" {
  local data_dir="$TEST_DIR/sete_faildate"

  run bash -c "
    set -euo pipefail
    cd '$REPO'
    . '$WRITER'
    date() { return 1; }
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA='$data_dir'
    echo BEFORE
    _observability_write kind=hook session=sete-faildate
    echo AFTER
  "
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'BEFORE\nAFTER')" ]

  # The dead-code-under-errexit trap this pins: `ts="$(date ...)"` (bare,
  # unguarded) would abort BEFORE the fallback line `[ -z "$ts" ] &&
  # ts="1970-..."` ever ran — so the fallback existing in the source proves
  # nothing on its own without this test actually forcing date to fail.
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify the ts fallback value"
  fi
  run jq -r '.ts' "$file"
  [ "$output" = "1970-01-01T00:00:00Z" ]
}

# ---------------------------------------------------------------------------
# 15. CON-10/field-limit: the 256 limit is bytes, not characters (LC_ALL=C
#    makes ${#clean} and ${clean:0:256} byte-oriented already; this pins
#    that as deliberate, not accidental). 150 'Ā' (U+0100, 2 bytes each) is
#    150 characters — comfortably under 256 characters — but 300 bytes,
#    comfortably OVER 256 bytes. Byte-aligned (256 / 2 = 128 exactly) so
#    this test is isolated from the mid-sequence healing concern below.
# ---------------------------------------------------------------------------

@test "write: the 256 limit is bytes — 150 two-byte characters (300 bytes) still truncates" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify byte length"
  fi
  local data_dir="$TEST_DIR/recbytes1"
  local a_with_macron=$'\xc4\x80'    # U+0100, LATIN CAPITAL LETTER A WITH MACRON
  local val="" i
  for ((i = 0; i < 150; i++)); do val="$val$a_with_macron"; done

  run _call_writer "$data_dir" hook "$val"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
import json
data = open('$file', 'rb').read()
text = data.decode('utf-8')
obj = json.loads(text.strip())
val = obj['session']
# 150 characters is well under a 256-CHARACTER limit — if truncation were
# character-counted, this value would pass through unmodified. It must not.
assert obj.get('truncated') is True, 'a 300-byte value was not truncated'
assert len(val.encode('utf-8')) == 256, 'expected exactly 256 bytes, got %d' % len(val.encode('utf-8'))
assert len(val) == 128, 'expected exactly 128 characters (256 bytes / 2), got %d' % len(val)
assert val == 'Ā' * 128
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 16. The sanitize -> cut -> re-sanitize ordering: a cut that lands INSIDE a
#    multi-byte sequence must be healed, not left as a broken tail. 87 '€'
#    (U+20AC, 3 bytes each) = 261 bytes; cutting at byte 256 lands after 85
#    complete '€' (255 bytes) plus the lead byte only of the 86th — the
#    second sanitize pass must replace that dangling lead byte with '?'.
# ---------------------------------------------------------------------------

@test "write: a 256-byte cut landing mid-sequence is healed, not left broken" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify raw bytes"
  fi
  local data_dir="$TEST_DIR/recheal1"
  local euro=$'\xe2\x82\xac'    # U+20AC, EURO SIGN
  local val="" i
  for ((i = 0; i < 87; i++)); do val="$val$euro"; done

  run _call_writer "$data_dir" hook "$val"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
import json
data = open('$file', 'rb').read()
text = data.decode('utf-8')    # fails outright if a raw broken byte reached the record
obj = json.loads(text.strip())
val = obj['session']
assert obj.get('truncated') is True
encoded = val.encode('utf-8')
assert len(encoded) == 256, 'expected exactly 256 bytes, got %d' % len(encoded)
assert val == ('€' * 85) + '?', 'expected 85 intact euro signs plus one healed ?, got %r' % val
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 17. The frozen field order (ts, kind, session, repo) is a real contract —
#    "a reader that positionally inspects a line must not break when a
#    later kind adds fields" (SDD/Application Data Models). Every other
#    test reads fields via jq's `.field` lookup or `has()`, which is
#    order-independent and cannot fail no matter what order the writer
#    emits keys in. This test reads the raw line as TEXT instead.
#
# Caveat, same candour as the sed/jq/awk grep test above: the `grep -oE`
# key-order check below is a plain regex over raw text, not a JSON parser —
# it cannot see an escaping backslash. A value containing an escaped
# sequence like `\"ts\":` could in principle register as a spurious key
# match. Not a live defect with this test's fixed, backslash-free value
# ("sess-order"); worth stating rather than assuming no one will ever widen
# this test with a value that could trip it.
# ---------------------------------------------------------------------------

@test "write: the frozen field order is ts, kind, session, repo, checked as raw text" {
  local data_dir="$TEST_DIR/recorder1"
  run _call_writer "$data_dir" hook sess-order
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  local line
  line="$(cat "$file")"

  # A plain regex over the raw text, not jq's order-independent field
  # lookup: this is what actually catches a writer that emits, say, kind
  # before ts while every value stays correct.
  local keys
  keys="$(printf '%s' "$line" | grep -oE '"(ts|kind|session|repo)":' | tr -d '":')"
  local expected
  expected="$(printf 'ts\nkind\nsession\nrepo')"
  [ "$keys" = "$expected" ]
}

# ---------------------------------------------------------------------------
# 18. Rotation: does the explicit `rm -f "$f.3"` discard actually do
#    anything? `mv "$f.2" "$f.3"` overwrites unconditionally regardless of
#    whether .3 pre-existed, so in every FULL-chain state (.1/.2/.3 all
#    present, what every other rotation test constructs) the discard is a
#    no-op — a mutation that deletes it leaves the whole suite green. It
#    only diverges in a PARTIAL chain: .3 present, .2 ABSENT (e.g. left
#    behind by an earlier failed/interrupted rotation). In that state
#    nothing else ever touches .3, so the discard is what actually clears
#    a stale .3 rather than leaving it stranded.
# ---------------------------------------------------------------------------

@test "write: rotation discards a stale .3 when .2 is absent (partial-chain divergence)" {
  local data_dir="$TEST_DIR/recrot_partial"
  local dir="$data_dir/observability"
  local file="$dir/events.jsonl"
  mkdir -p "$dir"

  printf 'STALE_THREE\n' > "$file.3"
  # Deliberately no .2 — this is the one state where the discard and the
  # unconditional-overwrite-via-mv genuinely disagree.
  printf 'OLD_ONE\n' > "$file.1"
  dd if=/dev/zero of="$file" bs=1024 count=1000 status=none

  run _call_writer "$data_dir" hook sess-partial-rot
  [ "$status" -eq 0 ]

  # With the discard: .3 is removed and nothing replaces it (no .2 existed
  # to move into it). Without the discard, "STALE_THREE" would still be
  # sitting in .3 right now.
  [ ! -f "$file.3" ]

  # The rest of the chain still shifts normally regardless.
  [ -f "$file.2" ]
  run cat "$file.2"
  [ "$output" = "OLD_ONE" ]
  run wc -c < "$file.1"
  [ "${output// /}" = "1024000" ]
}

# ---------------------------------------------------------------------------
# 19. The generic key=value branch — T1.2's own stated contract ("any other
#    key=value pair is written through verbatim, after the four frozen
#    fields") — had no test at all. A mutation swapping $key and $val in
#    that branch left all 35 tests green. Asserts the CORRECT VALUE, not
#    merely presence (a $key/$val swap would still make the field
#    "present", just backwards), and that extras land after the frozen
#    four, as raw text.
# ---------------------------------------------------------------------------

@test "write: a generic key=value pair is written verbatim, with the correct value, after the frozen fields" {
  local data_dir="$TEST_DIR/recextra1"
  run _call_writer_extra "$data_dir" hook sess-extra "myfield=myvalue" "second=anothervalue"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not available to verify extra field values"
  fi
  # The value, not just the key's existence: a $key/$val swap would still
  # produce a record with SOME field present, just holding the wrong thing
  # (or the key and value transposed) — has()/existence checks alone would
  # not catch that.
  run jq -r '.myfield' "$file"
  [ "$output" = "myvalue" ]
  run jq -r '.second' "$file"
  [ "$output" = "anothervalue" ]

  # Ordering: extras appear AFTER ts, kind, session, repo, in the order
  # given — as raw text, not via jq's order-independent lookup (same
  # rationale as test 17 above).
  local line keys expected
  line="$(cat "$file")"
  keys="$(printf '%s' "$line" | grep -oE '"(ts|kind|session|repo|myfield|second)":' | tr -d '":')"
  expected="$(printf 'ts\nkind\nsession\nrepo\nmyfield\nsecond')"
  [ "$keys" = "$expected" ]
}

# ---------------------------------------------------------------------------
# 20. C0 control bytes below 0x20 (other than tab/newline/CR, already
#    escaped) must become \u00XX, not pass through raw. `jq` parses a raw
#    control byte in a JSON string leniently; Python's json.loads does not
#    — and report.py (ADR-6) is Python. Checked with Python's own parser,
#    not jq, because jq accepting the line would prove nothing about the
#    actual failure this fix exists to prevent. The byte is constructed at
#    runtime via `chr(27)`/`printf` rather than written literally in this
#    source file.
# ---------------------------------------------------------------------------

@test "write: a C0 control byte is escaped so Python's json.loads accepts the record" {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify JSON legality"
  fi
  local data_dir="$TEST_DIR/recctrl1"
  local esc
  esc="$(printf '\033')"
  local val="esc${esc}ape"
  run _call_writer "$data_dir" hook "$val"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  run python3 -c "
import json
data = open('$file', 'rb').read()
text = data.decode('utf-8')
obj = json.loads(text.strip())    # raises 'Invalid control character' if unescaped
expected = 'esc' + chr(27) + 'ape'
assert obj['session'] == expected, repr(obj['session'])
"
  [ "$status" -eq 0 ]

  # The raw byte must not appear literally on disk either -- it has to
  # actually be the six-byte escape sequence, not merely something
  # json.loads tolerated by accident. The expected marker is built at
  # runtime from chr(92) (backslash) plus plain digits, rather than
  # typed as a literal escape token in this source file.
  run python3 -c "
data = open('$file', 'rb').read()
assert bytes([27]) not in data, 'raw ESC byte reached the record'
marker = (chr(92) + 'u001b').encode('ascii')
assert marker in data, 'expected the backslash-u-001b escape sequence on disk'
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# T1.3 — extraction and reduction.
#
# Drivers for the three helpers this task adds. They deliberately do NOT go
# through _call_writer above: T1.3's contract is about what a value looks
# like BEFORE it becomes a field, and about which caller-supplied fields the
# writer refuses to emit — neither is reachable through T1.2's three-argument
# driver.
# ---------------------------------------------------------------------------

# _observability_field <payload> <key>, run in a fresh shell with the writer
# sourced. Payload and key are passed as POSITIONAL arguments, never
# interpolated into the snippet, so a payload containing quotes, backslashes
# or shell metacharacters reaches the function byte-for-byte as the harness
# would deliver it on stdin.
_call_field() {
  bash -c '
    cd "$1" || exit 90
    . "$2" || exit 91
    _observability_field "$3" "$4"
  ' _ "$REPO" "$WRITER" "$1" "$2"
}

# _observability_program_name <command string>
_call_program_name() {
  bash -c '
    cd "$1" || exit 90
    . "$2" || exit 91
    _observability_program_name "$3"
  ' _ "$REPO" "$WRITER" "$1"
}

# _observability_redact_path <path> <toplevel>
_call_redact_path() {
  bash -c '
    cd "$1" || exit 90
    . "$2" || exit 91
    _observability_redact_path "$3" "$4"
  ' _ "$REPO" "$WRITER" "$1" "$2"
}

# Same as _call_writer_extra, but with CLAUDE_OBSERVABILITY_DETAIL under the
# caller's control: $1 is "1" (detail on) or anything else (detail off, the
# default — the variable is explicitly UNSET, not set to 0, so the test
# exercises the real default rather than a falsy value).
_call_writer_detail() {
  local detail="$1" data_dir="$2" kind="$3" session="$4"
  shift 4
  bash -c '
    detail="$1"; data_dir="$2"; kind="$3"; session="$4"; repo="$5"; writer="$6"
    shift 6
    cd "$repo" || exit 90
    . "$writer" || exit 91
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    if [ "$detail" = "1" ]; then
      export CLAUDE_OBSERVABILITY_DETAIL=1
    else
      unset CLAUDE_OBSERVABILITY_DETAIL
    fi
    _observability_write kind="$kind" session="$session" "$@"
  ' _ "$detail" "$data_dir" "$kind" "$session" "$REPO" "$WRITER" "$@"
}

# Extract TWO keys from one payload and write both as fields, in one shell:
# $3, the key under test, becomes `probe`; $4, a key known to be present,
# becomes `seen`. The second extraction is not decoration — without it the
# absent-key test would pass with no extractor on disk at all (a missing
# function yields an empty value, and an empty value leaks nothing). `seen`
# is what makes the test demand a WORKING extractor before it will accept the
# absence of a leak.
#
# The extracted `probe` value is also dropped in extracted.txt so a test can
# assert on it directly as well as scanning the record.
_field_then_write() {
  bash -c '
    data_dir="$1"; payload="$2"; key="$3"; present_key="$4"
    repo="$5"; writer="$6"
    cd "$repo" || exit 90
    . "$writer" || exit 91
    mkdir -p "$data_dir" || exit 92
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    v="$(_observability_field "$payload" "$key")" || v=""
    s="$(_observability_field "$payload" "$present_key")" || s=""
    printf "%s" "$v" > "$data_dir/extracted.txt"
    _observability_write kind=skill session=sess-guard "probe=$v" "seen=$s"
  ' _ "$1" "$2" "$3" "$4" "$REPO" "$WRITER"
}

# bats runs a test body under `set -e`, and a function returning non-zero as a
# simple command DOES fail the test — but `! grep -q ...` does NOT unless it is
# the body's last command. Every absence assertion below therefore goes through
# these helpers, never through a bare `! grep`.
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
# 21. SDD-AC-11 — the redaction-critical line of the whole design.
#
# `_field`'s guard is `[ "$body" = "$1" ]`. Prefix removal that finds no match
# returns the string UNCHANGED, so without that guard a request for an absent
# key returns the ENTIRE payload — which, on a Bash PreToolUse, is the full
# command line including any credential on it.
#
# Asserted by scanning the RAW RECORD BYTES for the canary, not by looking up
# a field: a test that only checked `field == ""` would stay green even if the
# payload leaked into some other field. The canary sits ~74 bytes into the
# payload, comfortably inside the writer's 256-byte field cut, so a removed
# guard cannot hide behind truncation.
# ---------------------------------------------------------------------------

@test "extract: a payload missing the requested key yields empty, never the whole payload" {
  local data_dir="$TEST_DIR/red21"
  local payload
  payload='{"tool_name":"Bash","tool_input":{"command":"curl -H \"Authorization: Bearer sk-ant-LEAKCANARY-0123456789\" https://example.com"},"session_id":"sess-abc","transcript_path":"/Users/nobody/.claude/projects/p/t.jsonl","cwd":"/x"}'

  run _field_then_write "$data_dir" "$payload" globs session_id
  [ "$status" -eq 0 ]

  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  # 1. The extractor is real and working on THIS payload — asserted first, so
  #    that the three absence checks below cannot be satisfied by an extractor
  #    that does not exist and therefore extracts nothing at all.
  _assert_present '"seen":"sess-abc"' "$file"

  # 2. The absent key returned nothing.
  run cat "$data_dir/extracted.txt"
  [ "$output" = "" ]
  _assert_present '"probe":""' "$file"

  # 3. And nothing from the payload reached the record, under any field name.
  _assert_absent 'sk-ant-LEAKCANARY-0123456789' "$file"
  _assert_absent 'Authorization' "$file"
  _assert_absent 'example.com' "$file"
  _assert_absent '/Users/nobody' "$file"
}

@test "extract: a present key is extracted, so the guard test above is not vacuous" {
  local payload
  payload='{"session_id":"sess-abc","memory_type":"Project","load_reason":"session_start"}'

  run _call_field "$payload" session_id
  [ "$status" -eq 0 ]
  [ "$output" = "sess-abc" ]

  run _call_field "$payload" load_reason
  [ "$status" -eq 0 ]
  [ "$output" = "session_start" ]
}

# ---------------------------------------------------------------------------
# 21b. The extractor's OTHER guard: an empty key.
#
# `_observability_field`'s first line refuses an empty key, with a comment
# claiming the pattern would otherwise be `*"":"` and would match unrelated
# text. That claim went untested when the guard was written — the same shape
# of defect as the absent-key guard before test 38 existed: a protection
# asserted in a comment with nothing behind it.
#
# The claim is TRUE and the guard is REACHABLE. `"":"` is a legal JSON byte
# sequence — an empty-string key, which `tool_input` is free to carry — and
# against the payload below an unguarded call returns
# `sk-ant-EMPTYKEYCANARY-42`, not the empty string. (The absent-key guard
# does NOT cover this case: the prefix removal genuinely matches, so `$body`
# differs from the payload and that guard never fires.)
#
# The payload is built so the test cannot be vacuous. If the empty-key guard
# is removed, the extractor returns the canary and both the field assertion
# and the raw-bytes scan below fail.
# ---------------------------------------------------------------------------

@test "extract: an empty key yields empty, even when the payload contains an empty-key sequence" {
  local payload
  payload='{"tool_name":"Bash","tool_input":{"":"sk-ant-EMPTYKEYCANARY-42","command":"echo hi"},"session_id":"sess-empty"}'

  run _call_field "$payload" ""
  [ "$status" -eq 0 ]
  [ "$output" = "" ]

  # And through the writer, scanned as raw record bytes — the same discipline
  # test 38 uses, for the same reason: a field that merely reads empty proves
  # nothing about what landed elsewhere in the line.
  local data_dir="$TEST_DIR/red21b"
  run _field_then_write "$data_dir" "$payload" "" session_id
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  # The extractor is working on THIS payload, so the absence below is a real
  # result and not the silence of a function that did nothing.
  _assert_present '"seen":"sess-empty"' "$file"
  _assert_present '"probe":""' "$file"
  _assert_absent 'sk-ant-EMPTYKEYCANARY-42' "$file"
}

# ---------------------------------------------------------------------------
# 22. SDD-AC-8 — reduced mode keeps a Bash call's program name (argv[0]) and
#    drops every argument. The keep/drop split mirrors the harness's own
#    `bash_command` (always) vs `full_command` (gated) distinction.
# ---------------------------------------------------------------------------

@test "reduce: reduced mode keeps a Bash call's program name and drops its arguments" {
  local cmd
  cmd='curl -H "Authorization: Bearer sk-ant-ARGCANARY-9876543210" https://example.com'

  run _call_program_name "$cmd"
  [ "$status" -eq 0 ]
  [ "$output" = "curl" ]

  # And that value, written as a field, carries the program and nothing else
  # off that command line.
  local data_dir="$TEST_DIR/red22"
  run _call_writer_detail 0 "$data_dir" skill sess-prog "program=$output"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  _assert_present '"program":"curl"' "$file"
  _assert_absent 'sk-ant-ARGCANARY-9876543210' "$file"
  _assert_absent 'Authorization' "$file"
  _assert_absent 'example.com' "$file"
}

@test "reduce: a path-qualified program is reduced to its name, leaking no directory" {
  # argv[0] can itself be an absolute path under \$HOME. "Program name" is the
  # name; the directory is exactly the absolute-home-path leak reduced mode
  # exists to prevent.
  run _call_program_name "/Users/nobody/.local/bin/deploy --token sk-ant-PATHCANARY"
  [ "$status" -eq 0 ]
  [ "$output" = "deploy" ]

  run _call_program_name "   npm  run build"
  [ "$status" -eq 0 ]
  [ "$output" = "npm" ]

  run _call_program_name ""
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}

# ---------------------------------------------------------------------------
# 23. Repo-relative paths (R-3): inside the repo a path becomes relative;
#    anywhere else it is reduced to its basename. Never an absolute path, so
#    never an absolute home path.
# ---------------------------------------------------------------------------

@test "reduce: a path inside the repo becomes repo-relative, one outside becomes a basename" {
  run _call_redact_path "$REPO_CANONICAL/docs/ai/memory/active.md" "$REPO_CANONICAL"
  [ "$status" -eq 0 ]
  [ "$output" = "docs/ai/memory/active.md" ]

  run _call_redact_path "/Users/nobody/.claude/CLAUDE.md" "$REPO_CANONICAL"
  [ "$status" -eq 0 ]
  [ "$output" = "CLAUDE.md" ]

  # Already relative: left alone.
  run _call_redact_path "docs/notes.md" "$REPO_CANONICAL"
  [ "$status" -eq 0 ]
  [ "$output" = "docs/notes.md" ]

  # The toplevel itself.
  run _call_redact_path "$REPO_CANONICAL" "$REPO_CANONICAL"
  [ "$status" -eq 0 ]
  [ "$output" = "." ]

  run _call_redact_path "" "$REPO_CANONICAL"
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}

# ---------------------------------------------------------------------------
# 24. SDD-AC-9 — the deny-list scan. One record, built exactly as a Phase 2
#    adapter would build it, then scanned for every category the keep/drop
#    table forbids: file content, a hook command string, `transcript_path`,
#    and any absolute home path.
# ---------------------------------------------------------------------------

@test "reduce: a reduced record carries no file content, no hook command, no transcript_path, no absolute home path" {
  local data_dir="$TEST_DIR/red24"
  local home_path="/Users/nobody/.claude/settings.json"
  local transcript="/Users/nobody/.claude/projects/p/transcript.jsonl"
  local hook_cmd='bash .claude/observability/log_skill.sh --secret sk-ant-HOOKCANARY'
  local content='FILECONTENTCANARY the entire body of the loaded instruction file'
  local rel outside
  rel="$(_call_redact_path "$REPO_CANONICAL/docs/ai/memory/active.md" "$REPO_CANONICAL")"
  # A second path, this one OUTSIDE the repo and under a home directory — the
  # `parent` field of an `include` load is routinely a user-global CLAUDE.md.
  # Without it the deny-list scan would never exercise the branch that turns an
  # absolute outside path into a basename, and "no absolute home path" would be
  # pinned only by the redaction helper's own unit test.
  outside="$(_call_redact_path "$home_path" "$REPO_CANONICAL")"

  run _call_writer_detail 0 "$data_dir" instruction sess-deny \
    "path=$rel" \
    "parent=$outside" \
    "scope=Project" \
    "reason=session_start" \
    "bytes=2048" \
    "transcript_path=$transcript" \
    "cwd=$REPO_CANONICAL" \
    "detail:content=$content" \
    "detail:hook_command=$hook_cmd" \
    "detail:absolute=$home_path"
  [ "$status" -eq 0 ]

  local file="$data_dir/observability/events.jsonl"
  [ -f "$file" ]

  # Kept: identity, scope, reason, the repo-relative path, and `bytes`
  # (a size is metadata, not content — PRD F4 cannot be produced without it).
  _assert_present '"kind":"instruction"' "$file"
  _assert_present '"path":"docs/ai/memory/active.md"' "$file"
  _assert_present '"parent":"settings.json"' "$file"
  _assert_present '"scope":"Project"' "$file"
  _assert_present '"reason":"session_start"' "$file"
  _assert_present '"bytes":"2048"' "$file"

  # Dropped, every category in the keep/drop table.
  _assert_absent 'FILECONTENTCANARY' "$file"
  _assert_absent 'sk-ant-HOOKCANARY' "$file"
  _assert_absent 'log_skill.sh' "$file"
  _assert_absent "$transcript" "$file"
  _assert_absent 'transcript_path' "$file"
  _assert_absent '/Users/nobody' "$file"

  # No absolute path of ANY kind: the record must not carry the repo toplevel
  # either (that is the `cwd` the table drops), nor the real \$HOME.
  _assert_absent "$REPO_CANONICAL" "$file"
  _assert_absent "$HOME/" "$file"
}

# ---------------------------------------------------------------------------
# 25. ADR-4 — detail mode adds the extra fields and needs its OWN switch.
#    Same call, same fields, twice: once with CLAUDE_OBSERVABILITY_DETAIL
#    unset and once with it set.
# ---------------------------------------------------------------------------

@test "detail: the extra fields appear only when CLAUDE_OBSERVABILITY_DETAIL is set" {
  local content='FILECONTENTCANARY body text'
  local transcript='/Users/nobody/.claude/projects/p/transcript.jsonl'

  local off_dir="$TEST_DIR/red25off"
  run _call_writer_detail 0 "$off_dir" instruction sess-d1 \
    "path=docs/a.md" "detail:content=$content" "transcript_path=$transcript"
  [ "$status" -eq 0 ]
  local off_file="$off_dir/observability/events.jsonl"
  _assert_present '"path":"docs/a.md"' "$off_file"
  _assert_absent 'FILECONTENTCANARY' "$off_file"
  _assert_absent 'transcript' "$off_file"

  local on_dir="$TEST_DIR/red25on"
  run _call_writer_detail 1 "$on_dir" instruction sess-d1 \
    "path=docs/a.md" "detail:content=$content" "transcript_path=$transcript"
  [ "$status" -eq 0 ]
  local on_file="$on_dir/observability/events.jsonl"
  _assert_present '"path":"docs/a.md"' "$on_file"
  _assert_present '"content":"FILECONTENTCANARY body text"' "$on_file"
  _assert_present '"transcript_path":"/Users/nobody/.claude/projects/p/transcript.jsonl"' "$on_file"
}

# ---------------------------------------------------------------------------
# 26. ADR-4 — both switches default off, and DETAIL is subordinate: it cannot
#    turn recording on by itself. Test 8 above pins "ENABLED unset -> nothing";
#    this pins the other half, that DETAIL=1 alone does not undo it.
# ---------------------------------------------------------------------------

@test "detail: CLAUDE_OBSERVABILITY_DETAIL alone records nothing at all" {
  local data_dir="$TEST_DIR/red26"
  run env -u CLAUDE_OBSERVABILITY_ENABLED "CLAUDE_OBSERVABILITY_DETAIL=1" \
    "CLAUDE_OBSERVABILITY_DATA=$data_dir" \
    bash -c "cd '$REPO' && . '$WRITER' && _observability_write kind=hook session=sess-detail-only content=SHOULDNOTEXIST"
  [ "$status" -eq 0 ]
  [ ! -e "$data_dir" ]
}

# $1/$2 are the values to give ENABLED/DETAIL, or "unset". Both are cleared
# from the environment first, so a variable that happens to be set in the
# session running bats cannot decide the result.
_gate_says() {
  local enabled="$1" detail="$2"
  local -a pre=(env -u CLAUDE_OBSERVABILITY_ENABLED -u CLAUDE_OBSERVABILITY_DETAIL)
  [ "$enabled" = "unset" ] || pre[${#pre[@]}]="CLAUDE_OBSERVABILITY_ENABLED=$enabled"
  [ "$detail" = "unset" ]  || pre[${#pre[@]}]="CLAUDE_OBSERVABILITY_DETAIL=$detail"
  "${pre[@]}" bash -c "cd '$REPO' && . '$WRITER' && \
    if _observability_detail_enabled; then echo ON; else echo OFF; fi"
}

@test "detail: the gate helper requires BOTH switches" {
  run _gate_says unset unset
  [ "$output" = "OFF" ]
  run _gate_says 1 unset
  [ "$output" = "OFF" ]
  run _gate_says unset 1
  [ "$output" = "OFF" ]
  run _gate_says 1 1
  [ "$output" = "ON" ]
}

# ---------------------------------------------------------------------------
# 27. The two ways prefix-removal extraction fails while still LOOKING right.
#    Neither is named in the task text; both are properties the SDD's `_field`
#    shape either has or does not, and a reviewer cannot tell by reading it.
#
#    (a) An ESCAPED QUOTE inside a value. `${body%%\"*}` stops at the first
#        `"` byte, and a backslash-escaped quote is still a `"` byte. The
#        extractor therefore UNDER-captures — it stops early. That is a known
#        and accepted limitation (SDD/Known Technical Issues: "a string
#        operation, not a JSON parser"); what must never happen is the
#        opposite, OVER-capture, where the rest of the payload rides along.
#        Both directions are asserted here. If the extractor is ever taught
#        about `\"`, the exact-value assertion below is the one to update —
#        deliberately, not by accident.
#
#    (b) A key that is a SUBSTRING of another key. The search pattern is
#        `*"key":"`, INCLUDING the opening quote, so `path` cannot match
#        inside `"file_path":"` — the byte before `path` there is `_`, not a
#        quote. Dropping that opening quote from the pattern would make
#        `_field "$payload" path` return the file path, and every short key
#        would silently pick up a longer neighbour's value.
# ---------------------------------------------------------------------------

@test "extract: an escaped quote in a value under-captures but never over-captures" {
  local payload
  payload='{"file_path":"/tmp/we\"ird/name.md","memory_type":"Project","load_reason":"session_start"}'

  run _call_field "$payload" file_path
  [ "$status" -eq 0 ]

  # Under-capture, documented: the scan stops at the escaped quote's `"` byte,
  # leaving the backslash as the last character.
  [ "$output" = '/tmp/we\' ]

  # Over-capture is the failure that matters, and it did not happen: nothing
  # after the value's closing quote came along.
  case "$output" in
    *memory_type*|*Project*|*load_reason*|*session_start*)
      printf 'OVER-CAPTURE: %s\n' "$output" >&2
      return 1
      ;;
  esac

  # A trailing lone backslash must still leave the record legal JSON — the
  # escaper, not the extractor, is what makes that true, and this is the one
  # case that reaches it with a dangling backslash.
  if ! command -v python3 >/dev/null 2>&1; then
    skip "python3 not available to verify JSON legality"
  fi
  local data_dir="$TEST_DIR/red27a"
  run _field_then_write "$data_dir" "$payload" file_path load_reason
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"
  run python3 -c "
import json
obj = json.loads(open('$file', 'rb').read().decode('utf-8').strip())
assert obj['probe'] == '/tmp/we' + chr(92), repr(obj['probe'])
"
  [ "$status" -eq 0 ]
}

@test "extract: a key that is a substring of another key does not match the wrong field" {
  local payload
  payload='{"file_path":"/repo/docs/a.md","memory_type":"Project","parent_file_path":"/repo/CLAUDE.md"}'

  # `path` is a suffix of `file_path`; `type` is a suffix of `memory_type`.
  # Both must miss, because the pattern carries the opening quote.
  run _call_field "$payload" path
  [ "$status" -eq 0 ]
  [ "$output" = "" ]

  run _call_field "$payload" type
  [ "$status" -eq 0 ]
  [ "$output" = "" ]

  # And the real keys still resolve — including the one whose name CONTAINS
  # another key's name, which must return its own value, not the shorter
  # key's.
  run _call_field "$payload" file_path
  [ "$status" -eq 0 ]
  [ "$output" = "/repo/docs/a.md" ]

  run _call_field "$payload" parent_file_path
  [ "$status" -eq 0 ]
  [ "$output" = "/repo/CLAUDE.md" ]
}

# ---------------------------------------------------------------------------
# 28. CON-5: nothing added by T1.3 may fail CLOSED. Every helper is called
#    under `set -euo pipefail` in its worst case — absent key, empty command,
#    empty path — and a line after the call must still run.
# ---------------------------------------------------------------------------

@test "set -e survival: the extraction and reduction helpers never abort a strict caller" {
  local data_dir="$TEST_DIR/red28"
  run bash -c "
    set -euo pipefail
    cd '$REPO'
    . '$WRITER'
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA='$data_dir'
    a=\"\$(_observability_field '{\"k\":\"v\"}' absent)\"
    b=\"\$(_observability_field '' anything)\"
    c=\"\$(_observability_program_name '')\"
    d=\"\$(_observability_redact_path '' '')\"
    e=\"\$(_observability_redact_path '/x/y' '')\"
    _observability_write kind=hook session=sess-strict 'detail:content=x' 'cwd=/y'
    echo REACHED
  "
  [ "$status" -eq 0 ]
  [ "$output" = "REACHED" ]
}
