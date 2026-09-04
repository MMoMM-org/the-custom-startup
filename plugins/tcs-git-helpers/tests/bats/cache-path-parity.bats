#!/usr/bin/env bats
#
# tests/bats/cache-path-parity.bats
#
# Every path resolver in the plugin must agree with lib-bundle.sh's
# _resolve_data_dir. That one is canonical because it is the only resolver that
# has to work with no environment at all — git spawns post-merge and pre-push,
# and git-spawned processes receive none of the harness variables.
#
# The harness sets
#     CLAUDE_PLUGIN_DATA = $HOME/.claude/plugins/data/<plugin>-<repo basename>
# so the no-environment fallback has to reconstruct exactly that shape. When it
# does not, the writer and the reader use different directories and the reader
# silently serves a stale cache — there is no error, the data is just old.
#
# Resolvers under test:
#   1. templates/githooks/lib-bundle.sh  _resolve_data_dir   (canonical)
#   2. scripts/lib/cache.sh              _cache_dir
#   3. scripts/git_status_audit.py       _plugin_data_dir + _cache_dir
#   4. scripts/lib/audit_log.sh          _audit_log_path
#
# bash 3.2 compatible.

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  BUNDLE="$PLUGIN_ROOT/templates/githooks/lib-bundle.sh"
  CACHE_LIB="$PLUGIN_ROOT/scripts/lib/cache.sh"
  AUDIT_LIB="$PLUGIN_ROOT/scripts/lib/audit_log.sh"
  PY_HELPER="$BATS_TEST_DIRNAME/lib/print_resolved_path.py"

  # macOS exports TMPDIR with a trailing slash. Left in, every fixture path
  # carries a "//" and the parity comparison ends up testing the test's own
  # string building rather than the resolvers.
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-parity.XXXXXX")"
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

  # git rev-parse resolves symlinks (/tmp -> /private/tmp on macOS); every
  # resolver sees the canonical form, so the expectations must too.
  REPO_CANONICAL="$(cd "$REPO" && git rev-parse --show-toplevel)"
  REPO_NAME="$(basename "$REPO_CANONICAL")"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Resolver drivers — each prints one cache-directory path.
#
# $1 selects the environment: "unset" drops CLAUDE_PLUGIN_DATA, anything else
# is used as its value.
# ---------------------------------------------------------------------------

# Run a command under a stubbed HOME, with CLAUDE_PLUGIN_DATA either unset or
# set to $1. No eval — the command string reaches `bash -c` intact.
_run_env() {
  local mode="$1"
  local cmd="$2"
  if [ "$mode" = "unset" ]; then
    env -u CLAUDE_PLUGIN_DATA "HOME=$FAKE_HOME" bash -c "$cmd"
  else
    env "CLAUDE_PLUGIN_DATA=$mode" "HOME=$FAKE_HOME" bash -c "$cmd"
  fi
}

_via_bundle() {
  _run_env "$1" "cd '$REPO' && . '$BUNDLE' && _resolve_data_dir"
}

_via_cache_lib() {
  _run_env "$1" "cd '$REPO' && . '$CACHE_LIB' && _cache_dir"
}

_via_python() {
  _run_env "$1" "cd '$REPO' && python3 '$PY_HELPER' cache"
}

# Same call, stderr only — used to explain a mismatch.
_via_python_diag() {
  _run_env "$1" "cd '$REPO' && python3 '$PY_HELPER' cache 2>&1 >/dev/null" | tr '\n' ' '
}

# audit_log.sh resolves <data dir>/audit/overrides.jsonl. Strip the suffix so
# it can be compared against the other resolvers' <data dir>/cache.
_via_audit_lib_data() {
  local p
  p="$(_run_env "$1" "cd '$REPO' && . '$AUDIT_LIB' && _audit_log_path")"
  printf '%s' "${p%/audit/overrides.jsonl}"
}

# Compare one resolver against the canonical path, reporting both sides — and
# whatever the resolver wrote to stderr — when they differ. A parity assertion
# that only says "not equal" cannot tell you whether the path was wrong or the
# resolver never ran at all.
_assert_parity() {
  local label="$1" expected="$2" actual="$3" diag="${4:-}"
  if [ -z "$expected" ]; then
    echo "canonical resolver produced nothing" >&2
    return 1
  fi
  if [ "$actual" != "$expected" ]; then
    {
      echo "$label disagrees with lib-bundle.sh"
      echo "  expected: [$expected]"
      echo "  actual:   [$actual]"
      [ -n "$diag" ] && echo "  stderr:   $diag"
    } >&2
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 1. The canonical rule itself
# ---------------------------------------------------------------------------

@test "canonical: no environment reconstructs the harness path shape" {
  run _via_bundle unset
  [ "$status" -eq 0 ]
  [ "$output" = "$FAKE_HOME/.claude/plugins/data/tcs-git-helpers-${REPO_NAME}/cache" ]
}

@test "canonical: CLAUDE_PLUGIN_DATA wins when set" {
  run _via_bundle "$TEST_DIR/explicit"
  [ "$status" -eq 0 ]
  [ "$output" = "$TEST_DIR/explicit/cache" ]
}

# ---------------------------------------------------------------------------
# 2. Parity — every resolver against the canonical one, both environments
# ---------------------------------------------------------------------------

@test "parity: cache.sh matches the bundle with CLAUDE_PLUGIN_DATA unset" {
  _assert_parity "cache.sh" "$(_via_bundle unset)" "$(_via_cache_lib unset)"
}

@test "parity: cache.sh matches the bundle with CLAUDE_PLUGIN_DATA set" {
  _assert_parity "cache.sh" "$(_via_bundle "$TEST_DIR/explicit")" "$(_via_cache_lib "$TEST_DIR/explicit")"
}

@test "parity: git_status_audit.py matches the bundle with CLAUDE_PLUGIN_DATA unset" {
  _assert_parity "git_status_audit.py" "$(_via_bundle unset)" "$(_via_python unset)" "$(_via_python_diag unset)"
}

@test "parity: git_status_audit.py matches the bundle with CLAUDE_PLUGIN_DATA set" {
  _assert_parity "git_status_audit.py" \
    "$(_via_bundle "$TEST_DIR/explicit")" \
    "$(_via_python "$TEST_DIR/explicit")" \
    "$(_via_python_diag "$TEST_DIR/explicit")"
}

@test "parity: audit_log.sh shares the data dir with CLAUDE_PLUGIN_DATA unset" {
  local expected
  expected="$(_via_bundle unset)"
  _assert_parity "audit_log.sh" "${expected%/cache}" "$(_via_audit_lib_data unset)"
}

@test "parity: audit_log.sh shares the data dir with CLAUDE_PLUGIN_DATA set" {
  local expected
  expected="$(_via_bundle "$TEST_DIR/explicit")"
  _assert_parity "audit_log.sh" "${expected%/cache}" "$(_via_audit_lib_data "$TEST_DIR/explicit")"
}

@test "parity: a CLAUDE_PLUGIN_DATA with a trailing slash does not split them" {
  local base="$TEST_DIR/explicit"
  mkdir -p "$base"
  _assert_parity "cache.sh" "$(_via_bundle "$base/")" "$(_via_cache_lib "$base/")"
  _assert_parity "git_status_audit.py" \
    "$(_via_bundle "$base/")" \
    "$(_via_python "$base/")" \
    "$(_via_python_diag "$base/")"
}

# ---------------------------------------------------------------------------
# 3. Writer/reader round trip — the failure the parity is there to prevent
# ---------------------------------------------------------------------------

@test "round trip: the bundle's write is visible to cache.sh's read" {
  _run_env unset "cd '$REPO' && . '$BUNDLE' && printf 'feat/x\t7\t2026-09-04T10:00:00Z\n' | _write_stale_cache '2026-09-04T10:00:01Z' '$REPO_CANONICAL' 'main'"

  run _run_env unset "cd '$REPO' && . '$CACHE_LIB' && _read_stale_cache_tsv"
  [ "$status" -eq 0 ]
  [[ "$output" == *"feat/x"* ]]
}

# ---------------------------------------------------------------------------
# 4. Drift guard — a new resolver added later must join the table above
# ---------------------------------------------------------------------------

@test "drift guard: no production code carries a competing default path" {
  cd "$PLUGIN_ROOT"

  # The retired default from before the resolvers were harmonised.
  run grep -rn --exclude-dir=__pycache__ "claude/plugin-data" scripts/ templates/ hooks/ skills/
  [ "$status" -ne 0 ] || {
    echo "stale '~/.claude/plugin-data' default still present:" >&2
    echo "$output" >&2
    return 1
  }

  # The data-dir literal may appear only where the canonical rule is defined:
  # the self-contained bundle, and the plugin-side library it mirrors.
  run grep -rln --exclude-dir=__pycache__ "plugins/data/tcs-git-helpers" scripts/ templates/ hooks/ skills/
  [ "$status" -eq 0 ]
  local f
  for f in $output; do
    case "$f" in
      templates/githooks/lib-bundle.sh|scripts/lib/plugin_data.sh) ;;
      *)
        echo "unexpected resolver in $f — add it to cache-path-parity.bats" >&2
        return 1
        ;;
    esac
  done
}
