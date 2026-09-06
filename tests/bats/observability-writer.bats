#!/usr/bin/env bats
#
# tests/bats/observability-writer.bats
#
# spec 018 (observability of what loads and fires), T1.1 — the data-directory
# resolver only. Append/escape/rotate (T1.2) and redaction (T1.3) are later
# tasks in the same plan; this suite must not assume they exist yet.
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
