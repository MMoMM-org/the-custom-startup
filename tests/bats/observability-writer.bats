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

  if command -v jq >/dev/null 2>&1; then
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
  fi
}

@test "write: ts is UTC RFC3339 at second precision" {
  local data_dir="$TEST_DIR/rec2"
  run _call_writer "$data_dir" hook sess-2
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  local ts
  if command -v jq >/dev/null 2>&1; then
    ts="$(jq -r '.ts' "$file")"
  else
    ts="$(grep -o '"ts":"[^"]*"' "$file" | head -1 | sed -e 's/^"ts":"//' -e 's/"$//')"
  fi
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

  if command -v jq >/dev/null 2>&1; then
    run jq -e -c . "$file"
    [ "$status" -eq 0 ]
    run jq -r '.session' "$file"
    [ "$output" = "$val" ]
  fi
}

@test "write: a literal newline, CR and tab are escaped so one record never splits" {
  local data_dir="$TEST_DIR/rec4"
  local val=$'line1\nline2\ttabbed\rcr'
  run _call_writer "$data_dir" hook "$val"
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  run wc -l < "$file"
  [ "${output// /}" = "1" ]

  if command -v jq >/dev/null 2>&1; then
    run jq -e -c . "$file"
    [ "$status" -eq 0 ]
    run jq -r '.session' "$file"
    [ "$output" = "$val" ]
  fi
}

# ---------------------------------------------------------------------------
# 5. No forking in the write path
# ---------------------------------------------------------------------------

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

  if command -v jq >/dev/null 2>&1; then
    run jq -r '.session | length' "$file"
    [ "$output" = "256" ]
    run jq -r '.truncated' "$file"
    [ "$output" = "true" ]
  fi
}

@test "write: a field at or under 256 characters carries no truncated field" {
  local data_dir="$TEST_DIR/rec6b"
  run _call_writer "$data_dir" hook short
  [ "$status" -eq 0 ]
  local file="$data_dir/observability/events.jsonl"

  if command -v jq >/dev/null 2>&1; then
    run jq -r 'has("truncated")' "$file"
    [ "$output" = "false" ]
  fi
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
