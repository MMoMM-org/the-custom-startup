#!/usr/bin/env bats
# #192 — every write form of `git config … core.hooksPath` is refused outside
# git-setup, and every read form is allowed.
#
# Before #192 five write forms passed: a non-canonical key case (git config
# keys are case-insensitive), an option carrying a value (`--file <f>`), two
# options in a row, the git 2.46 `config set` subcommand, and -- worst -- any
# command that ALSO contained a read, because the read check short-circuited
# the write check across every clause of the command.
#
# Driven end to end through block-bad-git-ops.sh: the read/write decision is
# made in the dispatcher, not by a single pattern.

bats_require_minimum_version 1.5.0

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"
  REPOS_ROOT="$("$FIXTURE_DIR/repos/build.sh" 2>/dev/null)"
  export TESTS_DIR PLUGIN_ROOT FIXTURE_DIR REPOS_ROOT
}

teardown_file() {
  if [ -n "${REPOS_ROOT:-}" ] && [ -d "$REPOS_ROOT" ]; then
    chmod -R u+rwX "$REPOS_ROOT" 2>/dev/null || true
    rm -rf "$REPOS_ROOT"
  fi
}

setup() {
  HOOK="$PLUGIN_ROOT/scripts/block-bad-git-ops.sh"
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-hpc.XXXXXX")"
  export CLAUDE_PLUGIN_DATA
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH
  GH_STUB_SCENARIO="no-pr"
  export GH_STUB_SCENARIO
  unset TCS_GIT_HELPERS_SETUP_ACTIVE CLAUDE_ALLOW_HOOKSPATH_OVERRIDE CLAUDE_ALLOW_GIT_BAD_OPS
  cd "$REPOS_ROOT/clean-repo"
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

load 'lib/helpers'

# _decision <command> — prints deny or allow, as the hook decides it.
_decision() {
  local out
  out="$(_run_hook_with_cmd "$1")"
  case "$out" in
    *'"permissionDecision":"deny"'*HOOKSPATH_OVERRIDE*) printf 'deny' ;;
    *'"permissionDecision":"deny"'*) printf 'deny-other' ;;
    *) printf 'allow' ;;
  esac
}

# _expect <decision> <command>...  — collects every mismatch, fails once.
_expect() {
  local want="$1" c got misses=""
  shift
  for c in "$@"; do
    got="$(_decision "$c")"
    [ "$got" = "$want" ] || misses="${misses}"$'\n'"  want ${want}, got ${got}: ${c}"
  done
  if [ -n "$misses" ]; then
    echo "mismatches:${misses}" >&2
    return 1
  fi
}

@test "write forms that already were refused stay refused" {
  _expect deny \
    "git config core.hooksPath /dev/null" \
    "git config --local core.hooksPath /dev/null" \
    "git config --global core.hooksPath /dev/null" \
    "git config --unset core.hooksPath"
}

@test "a non-canonical key case is refused (config keys are case-insensitive)" {
  _expect deny \
    "git config core.hookspath /dev/null" \
    "git config CORE.HOOKSPATH /dev/null" \
    "git config Core.HooksPath /dev/null"
}

@test "options carrying a value, or several options, do not hide the key" {
  _expect deny \
    "git config --file .git/config core.hooksPath /dev/null" \
    "git config --local --replace-all core.hooksPath /dev/null" \
    "git config -f .git/config core.hooksPath /dev/null"
}

@test "the git 2.46 config set / unset subcommands are refused" {
  _expect deny \
    "git config set core.hooksPath /dev/null" \
    "git config unset core.hooksPath"
}

@test "a read elsewhere in the command does not wave a write through" {
  _expect deny \
    "git config --get core.hooksPath && git config core.hooksPath /dev/null" \
    "git config core.hooksPath /dev/null; git config --get core.hooksPath"
}

@test "global options in front of config do not hide a write" {
  _expect deny \
    "git -C $REPOS_ROOT/clean-repo config core.hookspath /dev/null"
}

@test "read forms are allowed" {
  _expect allow \
    "git config --get core.hooksPath" \
    "git config --get core.hookspath" \
    "git config --get-all core.hooksPath" \
    "git config --get-regexp core.hooksPath" \
    "git config --local --get core.hooksPath" \
    "git config get core.hooksPath"
}

@test "an unrelated key that only starts like it is allowed" {
  _expect allow \
    "git config core.hooksPathology yes" \
    "git config core.editor vim"
}

@test "inline -c in any case is refused" {
  _expect deny \
    "git -c core.hookspath=/dev/null commit -m x" \
    "git -c CORE.HOOKSPATH=/dev/null commit -m x"
}
