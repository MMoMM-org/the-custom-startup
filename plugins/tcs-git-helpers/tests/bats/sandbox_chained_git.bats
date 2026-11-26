#!/usr/bin/env bats
#
# tests/bats/sandbox_chained_git.bats
#
# SANDBOX_CHAINED_GIT (#311): with the #303 sandbox template applied, a git
# command that writes .git/config is denied unless it is the whole Bash call,
# because chained it stays sandboxed and half-completes with exit 0.
#
# Not in the command corpus: the rule depends on settings files, which the
# corpus format cannot express.

bats_require_minimum_version 1.5.0

load 'lib/helpers'

RULE="SANDBOX_CHAINED_GIT"

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/block-bad-git-ops.sh"
  TEMPLATE="$PLUGIN_ROOT/templates/claude-settings/sandbox-git.json"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com
  export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com
  # No real gh, no real user settings, a private audit dir.
  mkdir -p "$BATS_TEST_TMPDIR/bin" "$BATS_TEST_TMPDIR/home"
  printf '#!/bin/sh\nexit 1\n' > "$BATS_TEST_TMPDIR/bin/gh"
  chmod +x "$BATS_TEST_TMPDIR/bin/gh"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  export HOME="$BATS_TEST_TMPDIR/home"
  export CLAUDE_PLUGIN_DATA="$BATS_TEST_TMPDIR/data"
  unset CLAUDE_ALLOW_SANDBOX_CHAINED_GIT CLAUDE_ALLOW_GIT_BAD_OPS

  REMOTE="$BATS_TEST_TMPDIR/remote.git"
  REPO="$BATS_TEST_TMPDIR/repo"
  git init -q --bare "$REMOTE"
  git init -q "$REPO"
  git -C "$REPO" checkout -q -b main
  git -C "$REPO" commit -q --allow-empty -m init
  git -C "$REPO" remote add origin "$REMOTE"
  git -C "$REPO" push -q origin main 2>/dev/null
  git -C "$REPO" fetch -q origin
  REPO="$(cd "$REPO" && pwd -P)"
  export CLAUDE_PROJECT_DIR="$REPO"
  cd "$REPO"
}

_template() {
  mkdir -p "$REPO/.claude"
  cp "$TEMPLATE" "$REPO/.claude/settings.json"
}

_hook() {
  run _run_hook_with_cmd "$1"
  [ "$status" -eq 0 ]
}

_denied() {
  _hook "$1"
  _has "$output" "[$RULE]"
}

_allowed() {
  _hook "$1"
  _lacks "$output" "[$RULE]"
}

# --- push -u -----------------------------------------------------------------

@test "P1 chained push -u is denied with the fix in the reason" {
  _template
  _denied 'git push -u origin feat; echo "rc=$?"'
  _has "$output" "Run it alone"
  _has "$output" "references/"
}

@test "P2 bare push -u is allowed" {
  _template
  _allowed 'git push -u origin feat'
  _allowed 'git push --set-upstream origin feat'
}

@test "P3 every chained form is denied" {
  _template
  _denied 'cd . && git push -u origin feat'
  _denied 'git -C . push -u origin feat'
  _denied 'FOO=1 git push -u origin feat'
  _denied 'git push -u origin feat 2>&1'
  _denied 'git push -u origin feat | tail -1'
  _denied 'git push -fu origin feat && true'
  _denied 'git status
git push -u origin feat'
}

@test "P4 chained push without -u is allowed" {
  _template
  _allowed 'git push origin feat && git status'
  _allowed 'git commit -m "push -u later" && git push origin feat'
}

@test "P5 a push -u only quoted in another command is allowed" {
  _template
  _allowed 'echo "git push -u origin feat; ls"'
}

# --- branch creation ---------------------------------------------------------

@test "B1 chained checkout -b from a remote branch is denied" {
  _template
  _denied 'git checkout -b feat origin/main && git status'
  _denied 'git switch -c feat origin/main; git status'
  _denied 'git checkout -b feat --track main && git status'
}

@test "B2 bare checkout -b from a remote branch is allowed" {
  _template
  _allowed 'git checkout -b feat origin/main'
}

@test "B3 chained checkout -b that sets no tracking is allowed" {
  _template
  _allowed 'git checkout -b feat && git status'
  _allowed 'git checkout -b feat main && git status'
  _allowed 'git checkout -b feat --no-track origin/main && git status'
}

@test "B4 branch.autoSetupMerge=false: a remote start point sets no tracking" {
  _template
  git config branch.autoSetupMerge false
  _allowed 'git checkout -b feat origin/main && git status'
}

@test "B5 chained branch --set-upstream-to is denied" {
  _template
  _denied 'git branch --set-upstream-to=origin/main main && git status'
  _denied 'git branch -u origin/main; git status'
}

# --- remote ------------------------------------------------------------------

@test "R1 chained remote add / set-url is denied, remote -v is not" {
  _template
  _denied 'git remote add up https://example.com/x.git && git fetch up'
  _denied 'git remote set-url origin https://example.com/y.git; git remote -v'
  _allowed 'git remote -v | cat'
}

# --- settings gate -----------------------------------------------------------

@test "S1 without the template nothing is denied" {
  _allowed 'git push -u origin feat; echo "rc=$?"'
  _allowed 'git checkout -b feat origin/main && git status'
}

@test "S2 sandbox.enabled false in local settings switches the rule off" {
  _template
  printf '{"sandbox":{"enabled":false}}\n' > "$REPO/.claude/settings.local.json"
  _allowed 'git push -u origin feat; echo "rc=$?"'
}

@test "S3 the exclusion in user settings counts too" {
  mkdir -p "$HOME/.claude"
  printf '{"sandbox":{"excludedCommands":["git push *"]}}\n' > "$HOME/.claude/settings.json"
  _denied 'git push -u origin feat; echo "rc=$?"'
}

@test "S4 an operation whose exclusion is missing is allowed" {
  mkdir -p "$REPO/.claude"
  printf '{"sandbox":{"excludedCommands":["git push *"]}}\n' > "$REPO/.claude/settings.json"
  _allowed 'git remote add up https://example.com/x.git && git fetch up'
}

@test "S5 malformed settings fail open" {
  mkdir -p "$REPO/.claude"
  printf '{ not json\n' > "$REPO/.claude/settings.json"
  _allowed 'git push -u origin feat; echo "rc=$?"'
}

# --- override ----------------------------------------------------------------

@test "O1 the granular override allows the chained call" {
  _template
  _allowed 'CLAUDE_ALLOW_SANDBOX_CHAINED_GIT=1 git push -u origin feat; echo "rc=$?"'
}

# --- lib ---------------------------------------------------------------------

@test "L1 lib is shellcheck-clean" {
  command -v shellcheck >/dev/null 2>&1 || skip "shellcheck not installed"
  run shellcheck -x "$PLUGIN_ROOT/scripts/lib/sandbox_chain.sh"
  [ "$status" -eq 0 ]
}
