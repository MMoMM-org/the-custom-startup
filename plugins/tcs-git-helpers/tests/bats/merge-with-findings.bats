#!/usr/bin/env bats
#
# tests/bats/merge-with-findings.bats
#
# MERGE_WITH_FINDINGS (#292): block-bad-git-ops.sh denies `gh pr merge` and
# `gh api -X PUT …/pulls/N/merge` while the PR has unresolved review threads,
# change requests, comments after the last commit, open code-scanning alerts
# or running checks. gh is the offline stub (tests/fixtures/gh_stubs);
# GH_STUB_ARGV_LOG records what the hook asked it.

bats_require_minimum_version 1.5.0

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"
  REPOS_ROOT="$("$FIXTURE_DIR/repos/build.sh" 2>/dev/null)"
  export REPOS_ROOT TESTS_DIR PLUGIN_ROOT FIXTURE_DIR
}

teardown_file() {
  if [ -n "${REPOS_ROOT:-}" ] && [ -d "$REPOS_ROOT" ]; then
    chmod -R u+rwX "$REPOS_ROOT" 2>/dev/null || true
    rm -rf "$REPOS_ROOT"
  fi
}

setup() {
  HOOK="$PLUGIN_ROOT/scripts/block-bad-git-ops.sh"
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-mwf.XXXXXX")"
  AUDIT_FILE="$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl"
  GH_STUB_ARGV_LOG="$BATS_TEST_TMPDIR/gh-argv"
  : > "$GH_STUB_ARGV_LOG"
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  GH_STUB_SCENARIO="merge-findings"
  export CLAUDE_PLUGIN_DATA GH_STUB_ARGV_LOG PATH GH_STUB_SCENARIO
  unset CLAUDE_ALLOW_MERGE_WITH_FINDINGS CLAUDE_ALLOW_GIT_BAD_OPS
  cd "$REPOS_ROOT/clean-unmerged"
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

load 'lib/helpers'

_reason() {
  printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty'
}

_gh_calls() { cat "$GH_STUB_ARGV_LOG"; }

# --- deny ---------------------------------------------------------------

@test "merge with findings: denies and counts every kind" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50 --squash"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  reason="$(_reason)"
  _has "$reason" "PR #50 is not ready"
  _has "$reason" "1 unresolved thread(s), 1 change request(s), 1 code scanning alert(s), 1 new comment(s), 2 running check(s)"
  _has "$reason" "CLAUDE_ALLOW_MERGE_WITH_FINDINGS=1"
  _has "$reason" "gh pr checks 50 --watch"
}

@test "merge with findings: names the findings, at most five, then a pointer" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50 --squash"
  reason="$(_reason)"
  _has "$reason" "unresolved thread scripts/live-open.mjs:36 github-advanced-security: CodeQL / Improper code sanitization"
  _has "$reason" "changes requested by alice"
  _has "$reason" "code scanning alert #2 js/bad-code-sanitization scripts/live-open.mjs:36"
  _has "$reason" "comment by bob after the last commit: Heads-up"
  _has "$reason" "check still running: Analyze (javascript-typescript)"
  _has "$reason" "and 1 more (gh pr view 50 --comments)"
  _lacks "$reason" "ci/legacy"
}

@test "merge with findings: resolved, outdated, own, earlier, hidden and finished items do not count" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50"
  reason="$(_reason)"
  _lacks "$reason" "resolved.mjs"
  _lacks "$reason" "outdated.mjs"
  _lacks "$reason" "own note by the author"
  _lacks "$reason" "old remark before the fix"
  _lacks "$reason" "hidden spam"
  _lacks "$reason" "Analyze (actions)"
  _lacks "$reason" "review by github-advanced-security"
}

@test "merge with findings: the denial stays within 15 lines" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50"
  [ "$(_reason | wc -l | tr -d ' ')" -le 15 ]
}

@test "merge with findings: gh api PUT on pulls/N/merge is a merge too" {
  run --separate-stderr _run_hook_with_cmd "gh api -X PUT repos/test-user/test-repo/pulls/50/merge -f merge_method=squash"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_gh_calls)" "pr view 50 -R test-user/test-repo --json"
}

@test "merge with findings: method after the path, and {owner}/{repo} placeholders" {
  run --separate-stderr _run_hook_with_cmd "gh api repos/{owner}/{repo}/pulls/50/merge --method PUT"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_gh_calls)" "pr view 50 --json"
  _lacks "$(_gh_calls)" "-R {owner}"
}

# --- allow --------------------------------------------------------------

@test "merge with findings: a clean PR merges" {
  export GH_STUB_SCENARIO=merge-clean
  run --separate-stderr _run_hook_with_cmd "gh pr merge 51 --squash --delete-branch"
  _assert_allow
}

@test "merge with findings: the inline override allows and is audited" {
  run --separate-stderr _run_hook_with_cmd "CLAUDE_ALLOW_MERGE_WITH_FINDINGS=1 gh pr merge 50 --squash"
  _assert_allow
  _has "$(cat "$AUDIT_FILE")" "CLAUDE_ALLOW_MERGE_WITH_FINDINGS"
}

@test "merge with findings: --disable-auto merges nothing and asks gh nothing" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50 --disable-auto"
  _assert_allow
  [ ! -s "$GH_STUB_ARGV_LOG" ]
}

@test "merge with findings: GET on pulls/N/merge only asks whether it is merged" {
  run --separate-stderr _run_hook_with_cmd "gh api repos/test-user/test-repo/pulls/50/merge"
  _assert_allow
  [ ! -s "$GH_STUB_ARGV_LOG" ]
}

@test "merge with findings: other gh pr commands and quoted mentions ask gh nothing" {
  run --separate-stderr _run_hook_with_cmd "gh pr view 50 --comments && echo 'next: gh pr merge 50'"
  _assert_allow
  [ ! -s "$GH_STUB_ARGV_LOG" ]
}

@test "merge with findings: a failed PR lookup fails open with a note" {
  export GH_STUB_SCENARIO=no-auth
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50"
  _assert_allow
  _has "$stderr" "fail-open"
}

@test "merge with findings: a failed thread lookup still checks the rest" {
  export GH_STUB_SCENARIO=merge-no-threads
  run --separate-stderr _run_hook_with_cmd "gh pr merge 52"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_reason)" "changes requested by alice"
  _has "$stderr" "review threads of PR #52 unavailable"
}

# --- which PR -----------------------------------------------------------

@test "merge with findings: no selector asks about the current branch's PR" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge --squash"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_gh_calls)" "|pr view --json"
}

@test "merge with findings: a selector after a blanked quoted value is still found" {
  run --separate-stderr _run_hook_with_cmd 'gh pr merge -b "fixes #12; thanks" 50 --squash'
  _has "$(_gh_calls)" "pr view 50 --json"
}

@test "merge with findings: a quoted -R value is read from the raw command" {
  run --separate-stderr _run_hook_with_cmd 'gh pr merge 50 --repo "test-user/test-repo"'
  _has "$(_gh_calls)" "pr view 50 -R test-user/test-repo --json"
}

@test "merge with findings: gh -R before the subcommand" {
  run --separate-stderr _run_hook_with_cmd "gh -R test-user/test-repo pr merge 50"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_gh_calls)" "pr view 50 -R test-user/test-repo --json"
}

@test "merge with findings: gh runs in the directory a preceding cd names" {
  # Normalised the way cd leaves $PWD: macOS TMPDIR ends in `/`, so the raw
  # path carries a `//` that gh's working directory does not.
  other="$(cd "$REPOS_ROOT/closed-pr" && pwd)"
  run --separate-stderr _run_hook_with_cmd "cd $other && gh pr merge 50"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_gh_calls)" "$other|pr view 50"
}

@test "merge with findings: cascades with other rules in one denial" {
  run --separate-stderr _run_hook_with_cmd "gh pr merge 50 && git reset --hard"
  _assert_deny_for_rule "MERGE_WITH_FINDINGS"
  _has "$(_reason)" "2 rule(s) matched"
}
