#!/usr/bin/env bats
#
# tests/bats/best-effort-write-silence.bats
#
# Every cache and sentinel write in this plugin is best-effort: it must never
# block a commit, a push or a merge, and it must never print a raw shell error.
#
# The trap is that `cmd > "$f.tmp" 2>/dev/null` does not do that. Redirections
# are applied left to right, so the output redirection is attempted *before*
# stderr is pointed at /dev/null — a failing `>` is reported on the still-open
# stderr, and neither the `2>/dev/null` nor a trailing `|| true` can suppress
# it. Grouping (`{ cmd > "$f.tmp"; } 2>/dev/null`) is what actually works;
# `{ cmd; } > "$f.tmp" 2>/dev/null` does not, because the group's redirection
# is again applied before its stderr redirection.
#
# The symptom is one raw line on every push in a sandboxed environment:
#   .githooks/pre-push: line 131: …/<hash>-pr-state.json.tmp: Operation not permitted
#
# Structured `tcs-git-helpers: … skipped — …` lines are deliberate and allowed;
# raw interpreter errors are not.
#
# bash 3.2 compatible.

bats_require_minimum_version 1.5.0

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  BUNDLE="$PLUGIN_ROOT/templates/githooks/lib-bundle.sh"
  CACHE_LIB="$PLUGIN_ROOT/scripts/lib/cache.sh"
  OVERRIDE_LIB="$PLUGIN_ROOT/scripts/lib/override.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-silence.XXXXXX")"

  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$FAKE_HOME"

  REPO="$TEST_DIR/myrepo"
  mkdir -p "$REPO"
  git -C "$REPO" init -q -b main
  git -C "$REPO" config user.email "t@t"
  git -C "$REPO" config user.name "t"
  git -C "$REPO" config commit.gpgsign false
  printf 'base\n' > "$REPO/base.txt"
  git -C "$REPO" add base.txt
  git -C "$REPO" commit -q -m "base"

  # An existing but unwritable data dir. mkdir -p succeeds on it, so the
  # guards upstream of the write do not fire — the redirection is what fails.
  RO_DATA="$TEST_DIR/readonly"
  mkdir -p "$RO_DATA/cache"
  chmod 500 "$RO_DATA/cache"
}

teardown() {
  [ -n "${RO_DATA:-}" ] && [ -d "$RO_DATA/cache" ] && chmod 700 "$RO_DATA/cache" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# root ignores the permission bits, so the write succeeds and there is nothing
# to assert. Skip rather than pass vacuously.
_skip_if_root() {
  [ "$(id -u)" != "0" ] || skip "running as root — permission bits do not apply"
}

# Fail when stderr carries anything other than the plugin's own structured
# lines. Reports what leaked, since "stderr was not empty" alone does not say.
_assert_no_raw_stderr() {
  local err="$1"
  local leaked
  leaked="$(printf '%s\n' "$err" | grep -v '^tcs-git-helpers:' | grep -v '^[[:space:]]*$' || true)"
  if [ -n "$leaked" ]; then
    {
      echo "raw interpreter output reached stderr:"
      printf '%s\n' "$leaked" | sed 's/^/  /'
    } >&2
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# The reported symptom: the pre-push hook's inline PR-state cache write
# ---------------------------------------------------------------------------

@test "pre-push inline PR-state write stays silent when the cache dir is unwritable" {
  _skip_if_root
  command -v jq >/dev/null 2>&1 || skip "jq not installed"

  run --separate-stderr env CLAUDE_PLUGIN_DATA="$RO_DATA" HOME="$FAKE_HOME" \
    bash -c "
      cd '$REPO'
      # Lift the writer out of the hook without running the push path around
      # it. _inline_repo_hash comes along, and _resolve_data_dir from the
      # bundle the hook sources — without both the writer returns at its
      # third line and never reaches the redirection under test.
      . '$BUNDLE'
      sed -n '/^_inline_repo_hash()/,/^}/p;/^_inline_write_pr_state_cache()/,/^}/p' \
        '$PLUGIN_ROOT/templates/githooks/pre-push' > '$TEST_DIR/writer.sh'
      . '$TEST_DIR/writer.sh'
      # Precondition: the writer must actually reach the write.
      type _resolve_data_dir >/dev/null 2>&1 || { echo 'FIXTURE: no _resolve_data_dir' >&2; exit 9; }
      type _inline_repo_hash >/dev/null 2>&1 || { echo 'FIXTURE: no _inline_repo_hash' >&2; exit 9; }
      _inline_write_pr_state_cache 'feat/x' 'OPEN' '7'
    "

  _assert_no_raw_stderr "$stderr"
}

# ---------------------------------------------------------------------------
# The same construct in the installed bundle and in the plugin libraries
# ---------------------------------------------------------------------------

@test "lib-bundle _write_stale_cache emits only structured lines when unwritable" {
  _skip_if_root

  run --separate-stderr env CLAUDE_PLUGIN_DATA="$RO_DATA" HOME="$FAKE_HOME" \
    bash -c "
      cd '$REPO'
      . '$BUNDLE'
      printf 'feat/x\t7\t2026-09-04T10:00:00Z\n' \
        | _write_stale_cache '2026-09-04T10:00:01Z' '$REPO' 'main'
    "

  _assert_no_raw_stderr "$stderr"
}

@test "cache.sh _write_stale_cache stays silent when the cache dir is unwritable" {
  _skip_if_root

  run --separate-stderr env CLAUDE_PLUGIN_DATA="$RO_DATA" HOME="$FAKE_HOME" \
    bash -c "
      cd '$REPO'
      . '$CACHE_LIB'
      printf 'feat/x\t7\t2026-09-04T10:00:00Z\n' \
        | _write_stale_cache '2026-09-04T10:00:01Z' '$REPO' 'main'
    "

  _assert_no_raw_stderr "$stderr"
}

@test "cache.sh _write_pr_state_cache stays silent when the cache dir is unwritable" {
  _skip_if_root

  run --separate-stderr env CLAUDE_PLUGIN_DATA="$RO_DATA" HOME="$FAKE_HOME" \
    bash -c "
      cd '$REPO'
      . '$CACHE_LIB'
      _write_pr_state_cache 'feat/x' 'OPEN' '7'
    "

  _assert_no_raw_stderr "$stderr"
}

@test "cache.sh _write_pr_state_cache stays silent without jq as well" {
  _skip_if_root

  run --separate-stderr env CLAUDE_PLUGIN_DATA="$RO_DATA" HOME="$FAKE_HOME" \
    bash -c "
      cd '$REPO'
      . '$CACHE_LIB'
      # Force the no-jq fallback branch, which writes through a brace group.
      command() { if [ \"\$2\" = jq ]; then return 1; fi; builtin command \"\$@\"; }
      _write_pr_state_cache 'feat/x' 'OPEN' '7'
    "

  _assert_no_raw_stderr "$stderr"
}

@test "override.sh sentinel write stays silent when the sentinel dir is unwritable" {
  _skip_if_root

  run --separate-stderr env CLAUDE_PLUGIN_DATA="$RO_DATA" HOME="$FAKE_HOME" \
    CLAUDE_ALLOW_TEST_RULE=1 \
    bash -c "
      cd '$REPO'
      . '$OVERRIDE_LIB'
      type _check_and_consume_override >/dev/null 2>&1 \
        || { echo 'FIXTURE: no _check_and_consume_override' >&2; exit 9; }
      _check_and_consume_override 'TEST_RULE' || true
    "

  _assert_no_raw_stderr "$stderr"
}

# ---------------------------------------------------------------------------
# Static guard — the idiom itself, so a new writer cannot reintroduce it
# ---------------------------------------------------------------------------

@test "guard: no best-effort write redirects before silencing stderr" {
  cd "$PLUGIN_ROOT"

  # `> "<something>.tmp" 2>/dev/null` — the redirection is attempted first, so
  # the failure is reported before stderr is silenced. Group it instead.
  run grep -rn --exclude-dir=__pycache__ --exclude-dir=tests \
    '> *"\${*[A-Za-z_]*}*\.tmp" *2>/dev/null' scripts/ templates/
  [ "$status" -ne 0 ] || {
    {
      echo "redirect-then-silence found; wrap it as { … > \"\$f.tmp\"; } 2>/dev/null"
      echo "$output"
    } >&2
    return 1
  }
}
