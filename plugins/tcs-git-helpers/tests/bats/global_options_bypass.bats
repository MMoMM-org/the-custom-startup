#!/usr/bin/env bats
# #171 — git global options must not disarm the destructive-op guard.
#
# 18 of the 20 git patterns were anchored as `git[[:space:]]+<subcommand>`, so
# any global option in between (`-C <path>`, `-c k=v`, `--no-pager`,
# `--git-dir=…`) made the guard never fire -- including `git -C <abspath>`, the
# form this repo's own override guidance prescribes. The same substring anchor
# matched for the wrong reason on a path ending in `.git`.
#
# Assertions use `[ ]` or an explicit `|| return 1`, never a non-final bare
# `[[ ]]`: bats only fails on a bare `[[ ]]` when it is the body's last
# statement.

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
  # shellcheck source=../../scripts/lib/pattern_match.sh disable=SC1091
  . "$PLUGIN_ROOT/scripts/lib/pattern_match.sh"
  HOOK="$PLUGIN_ROOT/scripts/block-bad-git-ops.sh"
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-gob.XXXXXX")"
  export CLAUDE_PLUGIN_DATA
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH
  GH_STUB_SCENARIO="no-pr"
  export GH_STUB_SCENARIO
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

load 'lib/helpers'

# _fires <command> <pattern> — 0 iff the guard's own matching path fires.
_fires() {
  _match_clauses "$(_clausify "$1")" "$2"
}

# The global-option prefixes every rule must see through. "" is the plain form.
PREFIXES=(
  ""
  "-C /tmp/x "
  "-c user.name=x "
  "--no-pager "
  "-C /tmp/x --no-pager "
  "--git-dir=/r/.git "
)

# _assert_rule_sees_through_prefixes <pattern-var> <command after "git ">
_assert_rule_sees_through_prefixes() {
  local pattern="${!1}" rest="$2" prefix misses=""
  for prefix in "${PREFIXES[@]}"; do
    _fires "git ${prefix}${rest}" "$pattern" || misses="${misses} [git ${prefix}${rest}]"
  done
  if [ -n "$misses" ]; then
    echo "$1 did not fire for:${misses}" >&2
    return 1
  fi
}

# --- 1. the issue's matrix: 18 rules x 6 forms --------------------------------

@test "RESET_HARD sees through global options"            { _assert_rule_sees_through_prefixes PATTERN_RESET_HARD "reset --hard HEAD"; }
@test "CLEAN_FORCE sees through global options"           { _assert_rule_sees_through_prefixes PATTERN_CLEAN_FORCE "clean -fd"; }
@test "CHECKOUT_DOT sees through global options"          { _assert_rule_sees_through_prefixes PATTERN_CHECKOUT_DOT "checkout ."; }
@test "CHECKOUT_PATH sees through global options"         { _assert_rule_sees_through_prefixes PATTERN_CHECKOUT_PATH "checkout -- README.md"; }
@test "RESTORE_DESTRUCTIVE sees through global options"   { _assert_rule_sees_through_prefixes PATTERN_RESTORE_DESTRUCTIVE "restore --staged README.md"; }
@test "BRANCH_FORCE_DELETE sees through global options"   { _assert_rule_sees_through_prefixes PATTERN_BRANCH_FORCE_DELETE "branch -D old"; }
@test "STASH_DESTROY sees through global options"         { _assert_rule_sees_through_prefixes PATTERN_STASH_DESTROY "stash drop"; }
@test "REFLOG_EXPIRE sees through global options"         { _assert_rule_sees_through_prefixes PATTERN_REFLOG_EXPIRE "reflog expire --all"; }
@test "NO_VERIFY sees through global options"             { _assert_rule_sees_through_prefixes PATTERN_NO_VERIFY "commit --no-verify -m msg"; }
@test "PUSH sees through global options"                  { _assert_rule_sees_through_prefixes PATTERN_PUSH "push"; }
@test "PUSH_FORCE sees through global options"            { _assert_rule_sees_through_prefixes PATTERN_PUSH_FORCE "push --force origin br"; }
@test "PUSH_DELETE_FLAG sees through global options"      { _assert_rule_sees_through_prefixes PATTERN_PUSH_DELETE_FLAG "push origin --delete br"; }
@test "PUSH_COLON_DELETE sees through global options"     { _assert_rule_sees_through_prefixes PATTERN_PUSH_COLON_DELETE "push origin :br"; }
@test "BRANCH_CREATE sees through global options"         { _assert_rule_sees_through_prefixes PATTERN_BRANCH_CREATE "checkout -b feat/x"; }
@test "BRANCH_RESUME sees through global options"         { _assert_rule_sees_through_prefixes PATTERN_BRANCH_RESUME "checkout feat/x"; }
@test "HOOKSPATH_INLINE sees through global options"      { _assert_rule_sees_through_prefixes PATTERN_HOOKSPATH_INLINE "-c core.hooksPath=/dev/null commit"; }
@test "HOOKSPATH_CONFIG sees through global options"      { _assert_rule_sees_through_prefixes PATTERN_HOOKSPATH_CONFIG "config core.hooksPath .x"; }
@test "HOOKSPATH_CONFIG_READ sees through global options" { _assert_rule_sees_through_prefixes PATTERN_HOOKSPATH_CONFIG_READ "config --get core.hooksPath"; }

# --- 2. negatives -------------------------------------------------------------

@test "a path ending in .git does not stand in for the git command" {
  if _fires "ls /r/.git reset --hard" "$PATTERN_RESET_HARD"; then
    echo "RESET_HARD fired on a .git path suffix" >&2
    return 1
  fi
  if _fires "cat repo.git push" "$PATTERN_PUSH"; then
    echo "PUSH fired on a .git path suffix" >&2
    return 1
  fi
}

@test "normalisation does not invent a destructive form: -C x reset --soft" {
  if _fires "git -C /tmp/x reset --soft HEAD~1" "$PATTERN_RESET_HARD"; then
    echo "RESET_HARD fired on reset --soft" >&2
    return 1
  fi
}

@test "/usr/bin/git still counts as git" {
  _fires "/usr/bin/git -C /tmp/x reset --hard" "$PATTERN_RESET_HARD"
}

# --- 3. hooksPath set as a global option --------------------------------------

@test "HOOKSPATH_INLINE fires behind another global option" {
  _fires "git -C /tmp/x -c core.hooksPath=/dev/null commit -m x" "$PATTERN_HOOKSPATH_INLINE"
}

@test "HOOKSPATH_INLINE fires on the lower-case key (git config keys are case-insensitive)" {
  _fires "git -c core.hookspath=/dev/null commit -m x" "$PATTERN_HOOKSPATH_INLINE"
}

@test "HOOKSPATH_INLINE fires on --config-env" {
  _fires "git --config-env=core.hooksPath=HP commit -m x" "$PATTERN_HOOKSPATH_INLINE"
}

# --- 4. unit: normalisation and -C resolution ---------------------------------

@test "_normalize_git_clause strips value-taking and flag globals" {
  [ "$(_normalize_git_clause "git -C /a -c k=v --no-pager --git-dir /g --work-tree=/w reset --hard")" = "git reset --hard" ]
}

@test "_normalize_git_clause keeps a leading command and env assignment" {
  [ "$(_normalize_git_clause "env X=1 git -C /a push origin main")" = "env X=1 git push origin main" ]
}

@test "_git_dash_c_dir: none, one, relative chain, absolute reset" {
  [ "$(_git_dash_c_dir "git reset --hard")" = "" ]
  [ "$(_git_dash_c_dir "git -C /a reset --hard")" = "/a" ]
  [ "$(_git_dash_c_dir "git -C a -C b status")" = "a/b" ]
  [ "$(_git_dash_c_dir "git -C a -C /abs -C b status")" = "/abs/b" ]
}

# --- 5-7. end to end through the hook ------------------------------------------

@test "hook denies git -C <repo> reset --hard" {
  cd "$REPOS_ROOT/clean-repo"
  run _run_hook_with_cmd "git -C $REPOS_ROOT/clean-repo reset --hard HEAD"
  _assert_deny_for_rule "RESET_HARD"
}

@test "hook honours the override in front of git -C" {
  cd "$REPOS_ROOT/clean-repo"
  run _run_hook_with_cmd "CLAUDE_ALLOW_RESET_HARD=1 git -C $REPOS_ROOT/clean-repo reset --hard HEAD"
  _assert_allow
}

@test "stateful: git -C <dirty repo> switch -c is checked in THAT repo (deny)" {
  cd "$REPOS_ROOT/clean-repo"
  run _run_hook_with_cmd "git -C $REPOS_ROOT/dirty switch -c feat/x"
  _assert_deny_for_rule "BRANCH_FROM_UNFINISHED"
}

@test "stateful: from a dirty cwd, git -C <clean main repo> checkout -b is allowed" {
  cd "$REPOS_ROOT/dirty"
  run _run_hook_with_cmd "git -C $REPOS_ROOT/clean-repo checkout -b feat/x"
  _assert_allow
}

@test "stateful: git -C <repo> checkout <squash-merged branch> reaches RESUME_MERGED_BRANCH" {
  git -C "$REPOS_ROOT/squash-merged" checkout -q main
  cd "$REPOS_ROOT/clean-repo"
  run _run_hook_with_cmd "git -C $REPOS_ROOT/squash-merged checkout feat/squashed"
  _assert_deny_for_rule "RESUME_MERGED_BRANCH"
}
