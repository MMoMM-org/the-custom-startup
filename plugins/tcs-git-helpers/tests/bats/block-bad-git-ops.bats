#!/usr/bin/env bats
#
# tests/bats/block-bad-git-ops.bats
#
# Coverage for scripts/block-bad-git-ops.sh — PreToolUse:Bash dispatcher
# that runs the 14+ destructive-pattern matchers against tool_input.command,
# enforces the M1 (push-to-closed-PR), M2 (branch-from-unfinished), M3
# (resume-squash-merged) gates, and emits cascading-denial JSON to stdout.
#
# Spec references:
#   - SDD §Implementation Examples — block-bad-git-ops dispatcher skeleton
#   - SDD §Runtime View Primary Flow — push-to-closed-PR sequence
#   - SDD §Quality Requirements — denial ≤15 lines, non-push p99 ≤80ms,
#                                 push p99 ≤5000ms with timeout
#   - PRD M1, M2, M3, M7, M12 acceptance criteria
#   - PRD EC2 — cascading denial: report ALL matched rules, not first only
#
# Constraints exercised:
#   - bash 3.2 compatible (no associative arrays, no mapfile)
#   - POSIX ERE patterns ([[:space:]]+, [[:>:]]) — never \s+/\b
#   - No `coreutils timeout` dependency (CON-3) — pure-bash timeout path
#   - gh fail-open per CON-4: exit 4 / 124 / 1 → ALLOW with stderr warning
#   - bats `! cmd` trap: use `_assert_no_match` / `run` + status checks
#                        instead of bare `! cmd` (silently passes mid-test)

bats_require_minimum_version 1.5.0

# ----------------------------------------------------------------------
# Setup / teardown
# ----------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"

  # Build synthetic repos once per test file. build.sh prints OUT_DIR on stdout.
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

  # Sandbox CLAUDE_PLUGIN_DATA so override sentinels & audit don't leak
  # into the user's real plugin data dir.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-bbgo.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  CACHE_DIR="$CLAUDE_PLUGIN_DATA/cache"
  AUDIT_FILE="$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl"

  # PATH-prepend gh stub so any `gh` call hits canned responses, not real GitHub.
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH

  # Default scenario; individual tests override via `export GH_STUB_SCENARIO=…`.
  GH_STUB_SCENARIO="default"
  export GH_STUB_SCENARIO

  # Defensive: clear any leaked override env-vars from prior shell.
  unset CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_CLEAN_FORCE \
        CLAUDE_ALLOW_DESTRUCTIVE_CHECKOUT CLAUDE_ALLOW_DESTRUCTIVE_RESTORE \
        CLAUDE_ALLOW_FORCE_BRANCH_DELETE CLAUDE_ALLOW_STASH_DESTROY \
        CLAUDE_ALLOW_REFLOG_EXPIRE CLAUDE_ALLOW_NO_VERIFY \
        CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_FORCE_PUSH \
        CLAUDE_ALLOW_REMOTE_BRANCH_DELETE CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED \
        CLAUDE_ALLOW_RESUME_MERGED_BRANCH CLAUDE_ALLOW_HOOKSPATH_OVERRIDE \
        CLAUDE_ALLOW_GIT_BAD_OPS TCS_GIT_HELPERS_SETUP_ACTIVE
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

# Build a tool_input JSON envelope and pipe it to the hook.
# $1 = bash command string. Returns the hook's stdout/stderr/exit via $output etc.
_run_hook_with_cmd() {
  local cmd="$1"
  local input
  input=$(jq -n --arg c "$cmd" '{tool_name:"Bash", tool_input:{command:$c}}')
  printf '%s' "$input" | bash "$HOOK"
}

# Run the hook and assert: exit 0, stdout contains a deny JSON, deny reason
# mentions the supplied rule name. Use `run --separate-stderr` outside.
_assert_deny_for_rule() {
  local rule="$1"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"deny"'* ]] \
    || { echo "expected deny JSON, got: $output" >&2; return 1; }
  [[ "$output" == *"$rule"* ]] \
    || { echo "expected rule $rule in reason, got: $output" >&2; return 1; }
  return 0
}

# Run the hook and assert: exit 0, NO deny JSON on stdout (allow path).
_assert_allow() {
  [ "$status" -eq 0 ]
  if [[ "$output" == *'"permissionDecision":"deny"'* ]]; then
    echo "expected ALLOW (no deny JSON), got: $output" >&2
    return 1
  fi
  return 0
}

# ----------------------------------------------------------------------
# Sanity
# ----------------------------------------------------------------------

@test "hook script exists and is executable" {
  [ -f "$HOOK" ]
  [ -x "$HOOK" ]
}

@test "non-Bash tool — exits 0 silently with no stdout" {
  run bash -c 'printf "%s" '"'"'{"tool_name":"Edit","tool_input":{}}'"'"' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty command — exits 0 silently" {
  run bash -c 'printf "%s" '"'"'{"tool_name":"Bash","tool_input":{"command":""}}'"'"' | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-git command — exits 0 silently" {
  run _run_hook_with_cmd "ls -la"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Per-pattern positive matches (M7)
# ----------------------------------------------------------------------

@test "RESET_HARD: positive — denies with rule name" {
  run _run_hook_with_cmd "git reset --hard origin/main"
  _assert_deny_for_rule "RESET_HARD"
}

@test "RESET_HARD: negative — git reset --soft is allowed" {
  run _run_hook_with_cmd "git reset --soft HEAD~1"
  _assert_allow
}

@test "CLEAN_FORCE: positive — denies" {
  run _run_hook_with_cmd "git clean -fdx"
  _assert_deny_for_rule "CLEAN_FORCE"
}

@test "CLEAN_FORCE: negative — git clean -n is allowed" {
  run _run_hook_with_cmd "git clean -n"
  _assert_allow
}

@test "DESTRUCTIVE_CHECKOUT: positive — git checkout . denies" {
  run _run_hook_with_cmd "git checkout ."
  _assert_deny_for_rule "DESTRUCTIVE_CHECKOUT"
}

@test "DESTRUCTIVE_CHECKOUT: positive — git checkout -- <path> denies" {
  run _run_hook_with_cmd "git checkout -- src/file.ts"
  _assert_deny_for_rule "DESTRUCTIVE_CHECKOUT"
}

@test "DESTRUCTIVE_RESTORE: positive — --worktree --source denies" {
  run _run_hook_with_cmd "git restore --worktree --source=HEAD~1 src/"
  _assert_deny_for_rule "DESTRUCTIVE_RESTORE"
}

@test "DESTRUCTIVE_RESTORE: positive — --staged denies" {
  run _run_hook_with_cmd "git restore --staged src/file.ts"
  _assert_deny_for_rule "DESTRUCTIVE_RESTORE"
}

@test "FORCE_BRANCH_DELETE: positive — git branch -D denies" {
  run _run_hook_with_cmd "git branch -D feat/old"
  _assert_deny_for_rule "FORCE_BRANCH_DELETE"
}

@test "FORCE_BRANCH_DELETE: negative — git branch -d is allowed" {
  run _run_hook_with_cmd "git branch -d feat/old"
  _assert_allow
}

@test "STASH_DESTROY: positive — git stash drop denies" {
  run _run_hook_with_cmd "git stash drop"
  _assert_deny_for_rule "STASH_DESTROY"
}

@test "STASH_DESTROY: positive — git stash clear denies" {
  run _run_hook_with_cmd "git stash clear"
  _assert_deny_for_rule "STASH_DESTROY"
}

@test "STASH_DESTROY: negative — git stash pop is allowed" {
  run _run_hook_with_cmd "git stash pop"
  _assert_allow
}

@test "REFLOG_EXPIRE: positive — denies" {
  run _run_hook_with_cmd "git reflog expire --all"
  _assert_deny_for_rule "REFLOG_EXPIRE"
}

@test "NO_VERIFY: positive — git commit --no-verify denies" {
  run _run_hook_with_cmd 'git commit --no-verify -m "msg"'
  _assert_deny_for_rule "NO_VERIFY"
}

@test "NO_VERIFY: positive — git commit -n denies" {
  run _run_hook_with_cmd 'git commit -n -m "msg"'
  _assert_deny_for_rule "NO_VERIFY"
}

@test "FORCE_PUSH: positive — git push --force denies" {
  run _run_hook_with_cmd "git push --force origin main"
  _assert_deny_for_rule "FORCE_PUSH"
}

@test "FORCE_PUSH: negative — --force-with-lease is allowed" {
  # gh stub returns NO_PR by default → push allowed
  run _run_hook_with_cmd "git push --force-with-lease origin main"
  _assert_allow
}

@test "REMOTE_BRANCH_DELETE: positive — --delete denies" {
  run _run_hook_with_cmd "git push origin --delete feat/old"
  _assert_deny_for_rule "REMOTE_BRANCH_DELETE"
}

@test "REMOTE_BRANCH_DELETE: positive — refspec :branch denies" {
  run _run_hook_with_cmd "git push origin :feat/old"
  _assert_deny_for_rule "REMOTE_BRANCH_DELETE"
}

@test "HOOKSPATH_OVERRIDE: -c inline denies" {
  run _run_hook_with_cmd "git -c core.hooksPath=/dev/null commit -m m"
  _assert_deny_for_rule "HOOKSPATH_OVERRIDE"
}

@test "HOOKSPATH_OVERRIDE: git config core.hooksPath denies outside setup" {
  run _run_hook_with_cmd "git config core.hooksPath .githooks"
  _assert_deny_for_rule "HOOKSPATH_OVERRIDE"
}

@test "HOOKSPATH_OVERRIDE: git config core.hooksPath ALLOWED with setup sentinel" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _run_hook_with_cmd "git config core.hooksPath .githooks"
  _assert_allow
}

# ----------------------------------------------------------------------
# Compound / bypass-evasion (CAUGHT — substring match on full command)
# ----------------------------------------------------------------------

@test "compound: cd foo && git reset --hard — DENIES" {
  run _run_hook_with_cmd "cd /tmp && git reset --hard origin/main"
  _assert_deny_for_rule "RESET_HARD"
}

@test "subshell: bash -c 'git push --force origin main' — DENIES" {
  # PATTERN_PUSH_FORCE requires whitespace OR end-of-string after --force; the
  # closing-quote-only form `bash -c "git push --force"` does NOT match (a
  # documented limitation of pattern_match.sh — surfaced separately).
  run _run_hook_with_cmd 'bash -c "git push --force origin main"'
  _assert_deny_for_rule "FORCE_PUSH"
}

# ----------------------------------------------------------------------
# Cascading denials (EC2)
# ----------------------------------------------------------------------

@test "cascading: --force + --delete reports BOTH rules in one denial (EC2)" {
  # PATTERN_PUSH_FORCE and PATTERN_PUSH_DELETE_FLAG both match this cmd.
  # FORCE_PUSH + NO_VERIFY would NOT cascade because PATTERN_NO_VERIFY is
  # `git commit`-specific and PATTERN_HOOKSPATH_INLINE / NO_VERIFY don't both
  # fire on `git -c ... commit ...` (NO_VERIFY pattern requires no chars
  # between `git` and `commit`).
  run _run_hook_with_cmd "git push --force --delete origin feat/old"
  _assert_deny_for_rule "FORCE_PUSH"
  [[ "$output" == *"REMOTE_BRANCH_DELETE"* ]] \
    || { echo "expected FORCE_PUSH AND REMOTE_BRANCH_DELETE, got: $output" >&2; return 1; }
  # Exactly one permissionDecision response (cascading, not two separate emits)
  local count
  count=$(printf '%s' "$output" | grep -c '"permissionDecision"' || true)
  [ "$count" = "1" ]
}

@test "cascading: denial reason fits ≤15 lines (SDD §Quality Requirements)" {
  run _run_hook_with_cmd "git push --force --delete origin feat/old"
  [ "$status" -eq 0 ]
  local reason
  reason=$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason')
  local n
  n=$(printf '%s\n' "$reason" | wc -l | tr -d ' ')
  [ "$n" -le 15 ] || { echo "denial reason has $n lines (>15)" >&2; return 1; }
}

# ----------------------------------------------------------------------
# Override consumption (M12 single-shot)
# ----------------------------------------------------------------------

@test "override: CLAUDE_ALLOW_RESET_HARD=1 → first call ALLOWED, sentinel + audit written" {
  export CLAUDE_ALLOW_RESET_HARD=1
  run _run_hook_with_cmd "git reset --hard"
  _assert_allow
  [ -f "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD" ]
  [ -f "$AUDIT_FILE" ]
  run jq -r '.env_var' "$AUDIT_FILE"
  [ "$output" = "CLAUDE_ALLOW_RESET_HARD" ]
  run jq -r '.master' "$AUDIT_FILE"
  [ "$output" = "false" ]
}

@test "override: second call within 5s window — re-denied (double-tap)" {
  export CLAUDE_ALLOW_RESET_HARD=1
  mkdir -p "$CACHE_DIR"
  printf '%s\n' "$(date +%s)" > "$CACHE_DIR/override-consumed-CLAUDE_ALLOW_RESET_HARD"
  run _run_hook_with_cmd "git reset --hard"
  _assert_deny_for_rule "RESET_HARD"
}

@test "override: master CLAUDE_ALLOW_GIT_BAD_OPS=1 → ALLOWED + master=true audit + warning" {
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  _assert_allow
  [[ "$stderr" == *"MASTER OVERRIDE"* ]]
  [ -f "$AUDIT_FILE" ]
  run jq -r '.master' "$AUDIT_FILE"
  [ "$output" = "true" ]
}

@test "override: granular does NOT cross-bypass other rules" {
  # CLAUDE_ALLOW_RESET_HARD set, but we run --force-push: that's still denied.
  export CLAUDE_ALLOW_RESET_HARD=1
  run _run_hook_with_cmd "git push --force origin main"
  _assert_deny_for_rule "FORCE_PUSH"
}

# ----------------------------------------------------------------------
# Bypass during multi-step git ops (rebase / merge / cherry-pick / detached)
# ----------------------------------------------------------------------

@test "bypass: rebase-in-progress → exit 0 with stderr bypass message, no deny" {
  cd "$REPOS_ROOT/rebase-in-progress"
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [ -z "$output" ] || ! [[ "$output" == *'"permissionDecision":"deny"'* ]]
  [[ "$stderr" == *"bypass"* ]]
}

@test "bypass: detached-HEAD → exit 0 with bypass, no deny even on destructive cmd" {
  cd "$REPOS_ROOT/detached-head"
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"bypass"* ]]
  [[ "$stderr" == *"detached"* ]]
}

@test "bypass: simulated MERGE_HEAD file → bypass triggers" {
  cd "$REPOS_ROOT/clean-unmerged"
  : > .git/MERGE_HEAD
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"bypass"* ]]
  [[ "$stderr" == *"merge"* ]]
  rm -f .git/MERGE_HEAD
}

@test "bypass: simulated CHERRY_PICK_HEAD → bypass triggers" {
  cd "$REPOS_ROOT/clean-unmerged"
  : > .git/CHERRY_PICK_HEAD
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"bypass"* ]]
  [[ "$stderr" == *"cherry-pick"* ]]
  rm -f .git/CHERRY_PICK_HEAD
}

@test "bypass: simulated BISECT_LOG → bypass triggers" {
  cd "$REPOS_ROOT/clean-unmerged"
  : > .git/BISECT_LOG
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$stderr" == *"bypass"* ]]
  [[ "$stderr" == *"bisect"* ]]
  rm -f .git/BISECT_LOG
}

# ----------------------------------------------------------------------
# M1: push-to-closed-PR — gh truth-table fail-open semantics
# ----------------------------------------------------------------------

@test "M1: gh stub CLOSED → DENY with PUSH_TO_CLOSED_PR" {
  cd "$REPOS_ROOT/closed-pr"
  export GH_STUB_SCENARIO=closed-pr
  run _run_hook_with_cmd "git push origin feat/closed-pr-branch"
  _assert_deny_for_rule "PUSH_TO_CLOSED_PR"
}

@test "M1: gh stub OPEN → ALLOW (no deny)" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=open-pr
  run _run_hook_with_cmd "git push origin feat/clean-unmerged"
  _assert_allow
}

@test "M1: gh stub no-PR (\\[\\]) → ALLOW" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=no-pr
  run _run_hook_with_cmd "git push origin feat/clean-unmerged"
  _assert_allow
}

@test "M1: gh stub no-auth (exit 4) → fail-open ALLOW with stderr warning" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=no-auth
  run --separate-stderr _run_hook_with_cmd "git push origin feat/clean-unmerged"
  _assert_allow
  [[ "$stderr" == *"fail-open"* ]] \
    || [[ "$stderr" == *"UNKNOWN"* ]] \
    || { echo "expected fail-open warning, got stderr: $stderr" >&2; return 1; }
}

@test "M1: gh stub timeout (exit 124) → fail-open ALLOW" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=timeout
  run --separate-stderr _run_hook_with_cmd "git push origin feat/clean-unmerged"
  _assert_allow
}

@test "M1: gh stub network-fail (exit 1) → fail-open ALLOW" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=network-fail
  run --separate-stderr _run_hook_with_cmd "git push origin feat/clean-unmerged"
  _assert_allow
}

@test "M1: override CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 → ALLOW + audit" {
  cd "$REPOS_ROOT/closed-pr"
  export GH_STUB_SCENARIO=closed-pr
  export CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
  run _run_hook_with_cmd "git push origin feat/closed-pr-branch"
  _assert_allow
  [ -f "$AUDIT_FILE" ]
  run jq -r '.env_var' "$AUDIT_FILE"
  [ "$output" = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ]
}

# ----------------------------------------------------------------------
# M2: branch creation from unfinished work
# ----------------------------------------------------------------------

@test "M2: clean-unmerged + checkout -b new → DENY BRANCH_FROM_UNFINISHED" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=no-pr
  run _run_hook_with_cmd "git checkout -b feat/another"
  _assert_deny_for_rule "BRANCH_FROM_UNFINISHED"
}

@test "M2: dirty tree + switch -c → DENY BRANCH_FROM_UNFINISHED" {
  cd "$REPOS_ROOT/dirty"
  export GH_STUB_SCENARIO=no-pr
  run _run_hook_with_cmd "git switch -c feat/another"
  _assert_deny_for_rule "BRANCH_FROM_UNFINISHED"
}

@test "M2: clean-unmerged + override → ALLOW once" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=no-pr
  export CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1
  run _run_hook_with_cmd "git checkout -b feat/another"
  _assert_allow
}

@test "M2: PR is OPEN — branch creation ALLOWED (work in flight)" {
  cd "$REPOS_ROOT/clean-unmerged"
  export GH_STUB_SCENARIO=open-pr
  run _run_hook_with_cmd "git checkout -b feat/another"
  _assert_allow
}

# ----------------------------------------------------------------------
# M3: resume squash-merged branch
# ----------------------------------------------------------------------

@test "M3: squash-merged branch + git checkout <branch> → DENY RESUME_MERGED_BRANCH" {
  cd "$REPOS_ROOT/squash-merged"
  # Currently checked out at feat/squashed; switch to main first so the
  # checkout target ref resolves and the branch-resume regex fires.
  git checkout -q main
  run _run_hook_with_cmd "git checkout feat/squashed"
  _assert_deny_for_rule "RESUME_MERGED_BRANCH"
}

@test "M3: merge-commit-merged branch → ALLOW (false-positive avoidance)" {
  cd "$REPOS_ROOT/merge-commit-merged"
  git checkout -q main
  run _run_hook_with_cmd "git checkout feat/merge-commit"
  _assert_allow
}

@test "M3: override CLAUDE_ALLOW_RESUME_MERGED_BRANCH=1 → ALLOW + audit" {
  cd "$REPOS_ROOT/squash-merged"
  git checkout -q main
  export CLAUDE_ALLOW_RESUME_MERGED_BRANCH=1
  run _run_hook_with_cmd "git checkout feat/squashed"
  _assert_allow
  run jq -r '.env_var' "$AUDIT_FILE"
  [ "$output" = "CLAUDE_ALLOW_RESUME_MERGED_BRANCH" ]
}

# ----------------------------------------------------------------------
# JSON shape — schema sanity
# ----------------------------------------------------------------------

@test "denial JSON is well-formed and has hookSpecificOutput shape" {
  run _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  # Stash $output before re-using `run`, which rebinds $output each call.
  local raw="$output"
  printf '%s' "$raw" | jq -e . >/dev/null
  printf '%s' "$raw" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
  printf '%s' "$raw" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
  printf '%s' "$raw" | jq -e '.hookSpecificOutput.permissionDecisionReason | type == "string"' >/dev/null
}

@test "denial reason mentions override env-var name" {
  run _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CLAUDE_ALLOW_RESET_HARD"* ]]
}

# ----------------------------------------------------------------------
# Performance smoke — non-push ≤ 80ms p99 budget (loose check, single run)
# ----------------------------------------------------------------------

@test "perf: non-push pattern completes under 1s smoke threshold" {
  # Loose smoke; not statistical p99. Asserts we're not catastrophically slow
  # (e.g., accidentally running gh on every invocation). Uses perl for
  # subsecond precision since `date +%s` rounds to whole seconds and would
  # report 1000ms whenever the call straddles a second boundary.
  cd "$REPOS_ROOT/clean-unmerged"
  local t0 t1 elapsed_ms
  t0=$(perl -MTime::HiRes -e 'printf "%d", Time::HiRes::time()*1000')
  _run_hook_with_cmd "git reset --hard" >/dev/null 2>&1 || true
  t1=$(perl -MTime::HiRes -e 'printf "%d", Time::HiRes::time()*1000')
  elapsed_ms=$((t1 - t0))
  [ "$elapsed_ms" -lt 1000 ] \
    || { echo "non-push hook took ${elapsed_ms}ms (>1000ms smoke threshold)" >&2; return 1; }
}
