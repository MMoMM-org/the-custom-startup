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
#   - POSIX ERE patterns ([[:space:]]+ and ([^[:alnum:]_]|$) for a trailing
#     word boundary) — never \s+/\b, never the BSD-only [[:<:]]/[[:>:]]
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

  # Build the _is_ahead_of_merged runner script once; tests reference IS_AHEAD_RUNNER.
  IS_AHEAD_RUNNER="$BATS_TMPDIR/is_ahead_runner.sh"
  cat > "$IS_AHEAD_RUNNER" << 'RUNNER_EOF'
#!/usr/bin/env bash
set -uo pipefail
PLUGIN_ROOT="$1"; shift
BRANCH="$1";      shift
MERGED_SHA="$1";  shift

# Source git_state.sh for any indirect deps the function may acquire later.
# shellcheck source=/dev/null
. "$PLUGIN_ROOT/scripts/lib/git_state.sh"

# Extract _is_ahead_of_merged from block-bad-git-ops.sh without sourcing the
# full script (which would call exit 0 after the early tool-name guard).
# awk: collect lines from function header until the closing `}` on its own line.
_fn_def=$(awk '
  /^_is_ahead_of_merged\(\)[[:space:]]*\{/ { p=1 }
  p { print }
  p && /^\}[[:space:]]*$/ { p=0; exit }
' "$PLUGIN_ROOT/scripts/block-bad-git-ops.sh")

if [ -z "$_fn_def" ]; then
  printf 'RUNNER: _is_ahead_of_merged not found in block-bad-git-ops.sh\n' >&2
  exit 99
fi

eval "$_fn_def"

_is_ahead_of_merged "$BRANCH" "$MERGED_SHA"
RUNNER_EOF
  chmod +x "$IS_AHEAD_RUNNER"

  export REPOS_ROOT TESTS_DIR PLUGIN_ROOT FIXTURE_DIR IS_AHEAD_RUNNER
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
# Helpers — loaded from shared lib
# ----------------------------------------------------------------------

load 'lib/helpers'

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
# Malformed-stdin fail-open (mirrors T2.3 review fix 1606411)
# ----------------------------------------------------------------------
# A non-zero hook exit would unconditionally block ALL Bash tool calls.
# These tests pin the contract: malformed input → exit 0 + no deny.

@test "malformed JSON stdin — exits 0, no deny (fail-open)" {
  run bash -c 'printf "%s" "not-json{{{" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty stdin — exits 0, no deny" {
  run bash -c 'printf "" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "missing tool_input — exits 0, no deny" {
  run bash -c 'printf "%s" "{\"tool_name\":\"Bash\"}" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "missing tool_name field — exits 0, no deny" {
  run bash -c 'printf "%s" "{}" | bash "$1"' _ "$HOOK"
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

@test "CHECKOUT_DOT: negative — git checkout main is allowed" {
  # Plain branch checkout — does not match PATTERN_CHECKOUT_DOT (which
  # requires `.` as its own argument). Note this hits PATTERN_BRANCH_RESUME
  # too; in non-fixture cwd the target ref doesn't exist locally so the
  # M3 squash-merge handler bails out → ALLOW.
  run _run_hook_with_cmd "git checkout main"
  _assert_allow
}

@test "DESTRUCTIVE_CHECKOUT: positive — git checkout -- <path> denies" {
  run _run_hook_with_cmd "git checkout -- src/file.ts"
  _assert_deny_for_rule "DESTRUCTIVE_CHECKOUT"
}

@test "CHECKOUT_PATH: negative — git checkout without -- separator is allowed" {
  # No `--` between checkout and the arg — bare-branch form, not pathspec.
  # Does not match PATTERN_CHECKOUT_PATH (which requires the literal `--`
  # separator). The same caveat as CHECKOUT_DOT applies re: PATTERN_BRANCH_RESUME.
  run _run_hook_with_cmd "git checkout feat/some-branch"
  _assert_allow
}

@test "DESTRUCTIVE_RESTORE: positive — --worktree --source denies" {
  run _run_hook_with_cmd "git restore --worktree --source=HEAD~1 src/"
  _assert_deny_for_rule "DESTRUCTIVE_RESTORE"
}

@test "DESTRUCTIVE_RESTORE: positive — --staged denies" {
  run _run_hook_with_cmd "git restore --staged src/file.ts"
  _assert_deny_for_rule "DESTRUCTIVE_RESTORE"
}

@test "DESTRUCTIVE_RESTORE: negative — bare git restore <path> is allowed" {
  # Plain `git restore <path>` (no --staged, no --worktree+--source) is the
  # safe form: it only restores tracked changes from the index, which is
  # recoverable via the index. Does not match PATTERN_RESTORE_DESTRUCTIVE.
  run _run_hook_with_cmd "git restore src/file.ts"
  _assert_allow
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

@test "REFLOG_EXPIRE: negative — git reflog show is allowed" {
  # Read-only reflog subcommands (show/list) do not match PATTERN_REFLOG_EXPIRE.
  run _run_hook_with_cmd "git reflog show"
  _assert_allow
}

@test "NO_VERIFY: positive — git commit --no-verify denies" {
  run _run_hook_with_cmd 'git commit --no-verify -m "msg"'
  _assert_deny_for_rule "NO_VERIFY"
}

@test "NO_VERIFY: positive — git commit -n denies" {
  run _run_hook_with_cmd 'git commit -n -m "msg"'
  _assert_deny_for_rule "NO_VERIFY"
}

@test "NO_VERIFY: negative — git commit -m without --no-verify is allowed" {
  # Plain commit without the bypass flag — does not match PATTERN_NO_VERIFY.
  run _run_hook_with_cmd 'git commit -m "msg"'
  _assert_allow
}

# ----------------------------------------------------------------------
# NO_VERIFY: quoted-body false-positive regression (v2.2.1 fix)
#
# Real user report: a `git commit -m "$(cat <<'EOF' …body with `-n,`… EOF)"`
# heredoc tripped NO_VERIFY because the greedy `.*` in PATTERN_NO_VERIFY
# allowed `-n[[:>:]]` to match text INSIDE the -m message body. Fix is a
# `_strip_quoted` preprocessing step applied ONLY to the NO_VERIFY check
# (CON-7 narrow scope; other patterns unchanged).
# ----------------------------------------------------------------------

@test "NO_VERIFY: negative — -n inside double-quoted -m body is allowed" {
  # The literal "-n," appears in a release-notes body; must not match the flag.
  run _run_hook_with_cmd 'git commit -m "release notes: see -n, foo bar"'
  _assert_allow
}

@test "NO_VERIFY: negative — -n inside single-quoted -m body is allowed" {
  run _run_hook_with_cmd "git commit -m 'fix: stop using -n flag'"
  _assert_allow
}

@test "NO_VERIFY: negative — --no-verify inside -m body is allowed" {
  run _run_hook_with_cmd 'git commit -m "docs: explain --no-verify trap"'
  _assert_allow
}

@test "NO_VERIFY: negative — heredoc body mentioning -n is allowed (user report)" {
  # Real user report: `git commit -m "$(cat <<'EOF' …body with -n,… EOF)"`
  # tripped NO_VERIFY because the body text reached the regex. With the
  # _strip_quoted fix, the entire outer "$(...)" wrapper is one double-quoted
  # segment (no inner `"` chars in this form) and is replaced by spaces
  # before NO_VERIFY runs.
  local cmd='git commit -m "$(cat <<'"'"'EOF'"'"'
release notes
fix: see -n, flag
EOF
)"'
  run _run_hook_with_cmd "$cmd"
  _assert_allow
}

@test "NO_VERIFY: nested \" inside \$(…) no longer trips (was a known limitation)" {
  # WAS: the quote-scanner read the inner `"` of `printf "x"` as closing the
  # outer double-quoted argument, so the message body leaked back to the regex
  # and a harmless commit was denied. The old test pinned that behaviour so
  # that a smarter scanner would trip it and force this review — which is what
  # happened (issue #23).
  #
  # NOW: _strip_quoted carries a nesting stack, so entering `$(` saves the
  # enclosing quote state and the substitution's own quotes are its own. The
  # substitution's CODE is still matched — see the deny case below — only its
  # quoted arguments are blanked.
  run _run_hook_with_cmd 'git commit -m "$(printf "release notes\nfix: see -n flag\n")"'
  [ "$status" -eq 0 ]
  _assert_allow
}

@test "NO_VERIFY: a genuine bypass inside \$(…) is still denied" {
  # The counterpart that makes the test above safe: substitution content is
  # code and stays in scope. Blanking the whole region would fail OPEN.
  run _run_hook_with_cmd 'echo "$(git commit -m x -n)"'
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"deny"'* ]] \
    || { echo "expected deny for a real bypass inside a substitution, got: $output" >&2; return 1; }
}

@test "NO_VERIFY: positive — -n AFTER closing quote still denies" {
  # Quote-strip must not be so aggressive that it kills the real flag when
  # it appears outside the quoted message.
  run _run_hook_with_cmd 'git commit -m "msg" -n'
  _assert_deny_for_rule "NO_VERIFY"
}

@test "NO_VERIFY: positive — --no-verify AFTER closing quote still denies" {
  run _run_hook_with_cmd 'git commit -m "msg" --no-verify'
  _assert_deny_for_rule "NO_VERIFY"
}

# ----------------------------------------------------------------------
# NO_VERIFY: sibling-isolation regression (T1.2 — spec-015 fix)
#
# The old dispatcher used _match_command on _strip_quoted(CMD), which let the
# unbounded .* in PATTERN_NO_VERIFY bridge from `git commit` into a sibling
# command's -n flag. These tests verify the fix: _match_no_verify splits on
# shell separators so only the git commit clause is tested.
# ----------------------------------------------------------------------

@test "NO_VERIFY: sibling echo -n — ALLOWS (no false-positive deny)" {
  # BUG REGRESSION: old code denied this. _match_no_verify must split on &&.
  run _run_hook_with_cmd 'git commit -m "done" && echo -n ok'
  _assert_allow
}

@test "NO_VERIFY: chained genuine bypass git add && git commit -n — DENIES" {
  # Both clauses are git commands; the commit clause carries -n.
  run _run_hook_with_cmd 'git add . && git commit -n -m "done"'
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

@test "PUSH_DELETE_FLAG: negative — regular git push origin main is allowed" {
  # Plain push has no --delete flag → does not match PATTERN_PUSH_DELETE_FLAG.
  # PATTERN_PUSH still matches and the push-to-closed-PR check fires; with
  # default gh stub returning `[]` (NO_PR), the check allows.
  run _run_hook_with_cmd "git push origin main"
  _assert_allow
}

@test "REMOTE_BRANCH_DELETE: positive — refspec :branch denies" {
  run _run_hook_with_cmd "git push origin :feat/old"
  _assert_deny_for_rule "REMOTE_BRANCH_DELETE"
}

@test "REMOTE_BRANCH_DELETE: positive — gh api ref delete denies" {
  run _run_hook_with_cmd "gh api repos/o/r/git/refs/heads/feat/old -X DELETE"
  _assert_deny_for_rule "REMOTE_BRANCH_DELETE"
}

@test "REMOTE_BRANCH_DELETE: positive — gh api --method DELETE ref denies" {
  run _run_hook_with_cmd "gh api --method DELETE repos/o/r/git/refs/heads/feat/old"
  _assert_deny_for_rule "REMOTE_BRANCH_DELETE"
}

@test "GH_REF_DELETE: negative — gh api PATCH on non-ref path is allowed" {
  run _run_hook_with_cmd "gh api repos/o/r/pulls/123 -X PATCH"
  _assert_allow
}

@test "PUSH_COLON_DELETE: negative — refspec main:main (no leading colon) is allowed" {
  # `<src>:<dst>` is a normal refspec pair, not a delete. PATTERN_PUSH_COLON_DELETE
  # requires `:<branch>` immediately after the remote — i.e., empty src
  # (which `main:main` does not have).
  run _run_hook_with_cmd "git push origin main:main"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: -c inline denies" {
  run _run_hook_with_cmd "git -c core.hooksPath=/dev/null commit -m m"
  _assert_deny_for_rule "HOOKSPATH_OVERRIDE"
}

@test "HOOKSPATH_INLINE: negative — other -c flags are allowed" {
  # Only `-c core.hooksPath=…` is sensitive; other config-key overrides
  # like user.email are routine and must not trigger the hook.
  run _run_hook_with_cmd "git -c user.email=x@y.z log --oneline"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: git config core.hooksPath denies outside setup" {
  run _run_hook_with_cmd "git config core.hooksPath .githooks"
  _assert_deny_for_rule "HOOKSPATH_OVERRIDE"
}

@test "HOOKSPATH_OVERRIDE: denial cites references/sandbox-and-git-config.md (T5.6)" {
  # T5.6 spec compliance: HOOKSPATH_OVERRIDE explains the .git/config sandbox
  # interaction (CON-7), so the denial body must cite sandbox-and-git-config.md.
  run _run_hook_with_cmd "git config core.hooksPath .githooks"
  _assert_deny_for_rule "HOOKSPATH_OVERRIDE"
  [[ "$output" == *"sandbox-and-git-config.md"* ]] \
    || { echo "expected sandbox-and-git-config.md citation, got: $output" >&2; return 1; }
}

@test "HOOKSPATH_OVERRIDE: git config core.hooksPath ALLOWED with setup sentinel" {
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  run _run_hook_with_cmd "git config core.hooksPath .githooks"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: read-only --get core.hooksPath is allowed without sentinel" {
  # `git config --get core.hooksPath` is read-only — debugging, never mutating.
  # Must not trigger HOOKSPATH_OVERRIDE even when TCS_GIT_HELPERS_SETUP_ACTIVE is unset.
  run _run_hook_with_cmd "git config --get core.hooksPath"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: read-only --get-all core.hooksPath is allowed" {
  run _run_hook_with_cmd "git config --get-all core.hooksPath"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: read-only --get-regexp core\\.hooksPath is allowed" {
  run _run_hook_with_cmd "git config --get-regexp core\\.hooksPath"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: --get with --show-scope still allowed (multi-flag read)" {
  # Some debugging chains use multiple read flags. Ensure the multi-flag form
  # still classifies as read.
  run _run_hook_with_cmd "git config --get-all --show-scope core.hooksPath"
  _assert_allow
}

@test "HOOKSPATH_OVERRIDE: --unset still denied (write disguised as flag)" {
  # `--unset` mutates, so the deny path must still fire — regression test
  # that the read-form exclusion didn't accidentally allow --unset.
  run _run_hook_with_cmd "git config --unset core.hooksPath"
  _assert_deny_for_rule "HOOKSPATH_OVERRIDE"
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

@test "#42: cd-prefixed inline override (the harness command shape) → ALLOWED end-to-end" {
  run _run_hook_with_cmd "cd /repo && CLAUDE_ALLOW_RESET_HARD=1 git reset --hard"
  _assert_allow
}

@test "#42: override placed mid-command → DENIED with near-miss diagnostic hint" {
  run _run_hook_with_cmd "git reset --hard && CLAUDE_ALLOW_RESET_HARD=1 echo done"
  _assert_deny_for_rule "RESET_HARD"
  [[ "$output" == *"Override token present but not applied"* ]] \
    || { echo "expected #42 near-miss hint in deny body, got: $output" >&2; return 1; }
}

@test "override: master CLAUDE_ALLOW_GIT_BAD_OPS=1 → ALLOWED + master=true audit + warning" {
  export CLAUDE_ALLOW_GIT_BAD_OPS=1
  run --separate-stderr _run_hook_with_cmd "git reset --hard"
  _assert_allow
  # PRD M7 AC3 verbatim — backticks around `CLAUDE_ALLOW_<X>=1` ARE part of
  # the user-facing contract (not markdown), so pin the exact byte sequence
  # end-to-end through the dispatcher. lib_override.bats already pins this
  # at the lib boundary; this test pins it at the hook boundary, which is
  # what Claude actually sees on stderr.
  [[ "$stderr" == *'⚠ MASTER OVERRIDE — strongly prefer granular `CLAUDE_ALLOW_<X>=1`'* ]] \
    || { echo "expected verbatim PRD M7 AC3 master-override warning, got: $stderr" >&2; return 1; }
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

# S1-AC1 wording lock — preserve the existing parenthesized override-hint
# suffix verbatim. ADR-9 keeps the wording as-is; M2 makes the documented
# mechanism actually work, but the suffix wording stays. A future refactor
# that changes the format (e.g. drops the parens or repunctuates) must
# trip this lock so the change is reviewed against ADR-9.
@test "S1 wording lock: deny suffix is exactly (override: prefix the command with CLAUDE_ALLOW_<RULE>=1)" {
  run _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$output" == *"(override: prefix the command with CLAUDE_ALLOW_RESET_HARD=1)"* ]] \
    || { echo "expected '(override: prefix the command with CLAUDE_ALLOW_RESET_HARD=1)' literal in output, got: $output" >&2; return 1; }
}

# ----------------------------------------------------------------------
# Reference-doc path resolution — CLAUDE_PLUGIN_ROOT is expanded, not
# emitted as literal text (so users can paste the path into `cat`).
# ----------------------------------------------------------------------

@test "denial References footer resolves \$CLAUDE_PLUGIN_ROOT to its value" {
  export CLAUDE_PLUGIN_ROOT="/sentinel/plugin/root"
  run _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  # Resolved path appears
  [[ "$output" == *"/sentinel/plugin/root/references/destructive-ops.md"* ]] \
    || { echo "expected resolved References path, got: $output" >&2; return 1; }
  # And the unresolved literal does NOT
  [[ "$output" != *'${CLAUDE_PLUGIN_ROOT}'* ]] \
    || { echo "found unresolved \${CLAUDE_PLUGIN_ROOT} in output: $output" >&2; return 1; }
}

@test "denial References footer falls back to 'tcs-git-helpers' when CLAUDE_PLUGIN_ROOT unset" {
  unset CLAUDE_PLUGIN_ROOT
  run _run_hook_with_cmd "git reset --hard"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tcs-git-helpers/references/destructive-ops.md"* ]] \
    || { echo "expected fallback path, got: $output" >&2; return 1; }
  [[ "$output" != *'${CLAUDE_PLUGIN_ROOT}'* ]] \
    || { echo "found unresolved \${CLAUDE_PLUGIN_ROOT} in output: $output" >&2; return 1; }
}

@test "M3 squash-merge-trap reference resolves \$CLAUDE_PLUGIN_ROOT" {
  export CLAUDE_PLUGIN_ROOT="/sentinel/plugin/root"
  cd "$REPOS_ROOT/squash-merged"
  # Switch to main first so the branch-resume regex fires (mirrors M3 fixture
  # test convention at line 614).
  git checkout -q main
  run _run_hook_with_cmd "git checkout feat/squashed"
  [ "$status" -eq 0 ]
  [[ "$output" == *"/sentinel/plugin/root/references/squash-merge-trap.md"* ]] \
    || { echo "expected resolved squash-merge-trap path, got: $output" >&2; return 1; }
  [[ "$output" != *'${CLAUDE_PLUGIN_ROOT}'* ]] \
    || { echo "found unresolved literal in output: $output" >&2; return 1; }
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
  [ "$elapsed_ms" -lt "$(_perf_budget 1000)" ] \
    || { echo "non-push hook took ${elapsed_ms}ms (>1000ms smoke threshold)" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.2: _is_ahead_of_merged helper unit tests (ADR-8 / M1-AC2)
#
# _is_ahead_of_merged <branch> <merged_sha> lives in block-bad-git-ops.sh.
# Since that script calls `exit 0` early when stdin is not a Bash hook
# envelope, we test the function in isolation via a per-test bash subprocess
# that sources only the needed libs and defines the function.
#
# Return codes (per SDD §Interface Specifications):
#   0 — HEAD is ahead of merged_sha (allow; emits ADR-8 stderr note)
#   1 — deny (HEAD==SHA, divergent, or object-missing)
#   2 — SHA argument empty (caller treats as deny)
#
# Each test uses _run_is_ahead_of_merged <branch> <merged_sha> inside a
# temp git repo with the relevant commit topology.
# ----------------------------------------------------------------------

# Run _is_ahead_of_merged in a fresh git repo with the given topology.
# Caller must `cd <repo_dir>` first so git commands resolve to the right repo.
# Usage: _run_is_ahead_of_merged <branch> <merged_sha>
# Sets $status and $stderr (via run --separate-stderr).
_run_is_ahead_of_merged() {
  local branch="$1" merged_sha="$2"
  run --separate-stderr bash "$IS_AHEAD_RUNNER" "$PLUGIN_ROOT" "$branch" "$merged_sha"
}

# ----------------------------------------------------------------------
# T1.2-C1: Empty SHA argument → returns 2, no stderr output
# ----------------------------------------------------------------------

@test "_is_ahead_of_merged: empty SHA → returns 2, no stderr" {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ahead-c1.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  printf 'a\n' > "$repo/a"
  git -C "$repo" add a
  git -C "$repo" commit -q -m "init"
  cd "$repo"
  _run_is_ahead_of_merged "main" ""
  rm -rf "$repo"
  [ "$status" -eq 2 ]
  [ -z "$stderr" ] || { echo "expected no stderr, got: $stderr" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.2-C2: HEAD SHA equals provided SHA → returns 1, no stderr note
# (ghost-branch / genuine squash-merge-trap: no new commits after merge)
# ----------------------------------------------------------------------

@test "_is_ahead_of_merged: HEAD equals merged_sha → returns 1, no stderr" {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ahead-c2.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  printf 'a\n' > "$repo/a"
  git -C "$repo" add a
  git -C "$repo" commit -q -m "init"
  local head_sha
  head_sha=$(git -C "$repo" rev-parse HEAD)
  cd "$repo"
  _run_is_ahead_of_merged "main" "$head_sha"
  rm -rf "$repo"
  [ "$status" -eq 1 ]
  [ -z "$stderr" ] || { echo "expected no stderr, got: $stderr" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.2-C3: merged_sha is an ancestor of HEAD AND HEAD != SHA → returns 0
#           AND stderr contains the exact ADR-8 wording (allow + note)
# ----------------------------------------------------------------------

@test "_is_ahead_of_merged: merged_sha is ancestor of HEAD → returns 0, ADR-8 stderr" {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ahead-c3.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  printf 'a\n' > "$repo/a"
  git -C "$repo" add a
  git -C "$repo" commit -q -m "base"
  local merged_sha
  merged_sha=$(git -C "$repo" rev-parse HEAD)
  # Add a new commit so HEAD != merged_sha but merged_sha IS ancestor of HEAD.
  printf 'b\n' > "$repo/b"
  git -C "$repo" add b
  git -C "$repo" commit -q -m "new work"
  cd "$repo"
  _run_is_ahead_of_merged "main" "$merged_sha"
  rm -rf "$repo"
  [ "$status" -eq 0 ]
  local expected_note="tcs-git-helpers: PR was merged; HEAD is ahead by new commits. A new PR will be required for this push."
  [[ "$stderr" == *"$expected_note"* ]] \
    || { echo "expected ADR-8 note in stderr, got: $stderr" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.2-C4: merged_sha NOT ancestor of HEAD (divergent) → returns 1, no stderr
# ----------------------------------------------------------------------

@test "_is_ahead_of_merged: divergent history (not ancestor) → returns 1, no stderr" {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ahead-c4.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  printf 'a\n' > "$repo/a"
  git -C "$repo" add a
  git -C "$repo" commit -q -m "base"
  # Create a divergent SHA: a commit on a side branch NOT in main's history.
  git -C "$repo" checkout -q -b side
  printf 's\n' > "$repo/side.txt"
  git -C "$repo" add side.txt
  git -C "$repo" commit -q -m "side"
  local divergent_sha
  divergent_sha=$(git -C "$repo" rev-parse HEAD)
  git -C "$repo" checkout -q main
  cd "$repo"
  # HEAD is on main; divergent_sha is on side branch — not an ancestor of main.
  _run_is_ahead_of_merged "main" "$divergent_sha"
  rm -rf "$repo"
  [ "$status" -eq 1 ]
  [ -z "$stderr" ] || { echo "expected no stderr, got: $stderr" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.2-C5: SHA not present in local object store (shallow clone simulation)
#           → returns 1 (conservative fallback), no stderr note
# ----------------------------------------------------------------------

@test "_is_ahead_of_merged: SHA absent from object store → returns 1, no stderr" {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ahead-c5.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  printf 'a\n' > "$repo/a"
  git -C "$repo" add a
  git -C "$repo" commit -q -m "init"
  cd "$repo"
  # 40 hex zeros: syntactically valid SHA but absent from any real object store.
  local phantom_sha="0000000000000000000000000000000000000000"
  _run_is_ahead_of_merged "main" "$phantom_sha"
  rm -rf "$repo"
  [ "$status" -eq 1 ]
  [ -z "$stderr" ] || { echo "expected no stderr, got: $stderr" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.2 stdout purity: _is_ahead_of_merged MUST NOT write to stdout
# (would corrupt the permissionDecision JSON on the real hook's stdout)
# ----------------------------------------------------------------------

@test "_is_ahead_of_merged: ancestor path produces no stdout output" {
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ahead-stdout.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  printf 'a\n' > "$repo/a"
  git -C "$repo" add a
  git -C "$repo" commit -q -m "base"
  local merged_sha
  merged_sha=$(git -C "$repo" rev-parse HEAD)
  printf 'b\n' > "$repo/b"
  git -C "$repo" add b
  git -C "$repo" commit -q -m "new"
  cd "$repo"
  run --separate-stderr bash "$IS_AHEAD_RUNNER" "$PLUGIN_ROOT" "main" "$merged_sha"
  rm -rf "$repo"
  [ "$status" -eq 0 ]
  [ -z "$output" ] || { echo "expected empty stdout, got: $output" >&2; return 1; }
}

# ----------------------------------------------------------------------
# T1.3: _check_push_to_closed_pr — ahead-check integration (M1-AC1/2/3)
#
# These tests verify the wiring added in T1.3:
#   - M1-AC1: MERGED + HEAD==merged_sha → deny (no regression on deny path)
#   - M1-AC2: MERGED + HEAD ahead by N commits → allow + ADR-8 stderr note
#   - M1-AC3: NO_PR → allow (M1-AC2 logic not entered; no regression)
#   - Cache-hit: merge_commit cached → no gh pr view call (zero spy entries)
#   - Cache-miss: MERGED state cached, no merge_commit → one gh pr view call;
#                 result written to cache
#   - SHA-resolution-fail: gh pr view returns empty → fall through to deny
#
# Test pattern: build a temp git repo with controlled history, pre-populate
# the PR-state cache so gh pr list is never called (cache-hit for state),
# then run the hook. For cache-miss tests, omit merge_commit from cache.
#
# _seed_pr_cache <repo_path> <branch> <state> [<merge_commit>]
#   Write a fresh (non-expired) PR-state cache entry for the given repo.
#   Uses jq — test setup already ensures jq is available.
# ----------------------------------------------------------------------

# _seed_pr_cache and _build_ahead_repo are provided by load 'lib/helpers' (see top of file).

# ----------------------------------------------------------------------
# M1-AC1: MERGED PR, HEAD == merged SHA → push DENIED (no regression)
# The deny path must produce the existing squash-merge-trap message.
# ----------------------------------------------------------------------

@test "T1.3 M1-AC1: MERGED PR HEAD==merged_sha → DENY PUSH_TO_CLOSED_PR" {
  local repo branch merged_sha
  branch="feat/t13-ac1"
  repo="$(_build_ahead_repo "$branch" 0)"
  merged_sha="$(git -C "$repo" rev-parse HEAD)"

  # Pre-populate cache: state=MERGED, merge_commit=HEAD (ghost branch)
  _seed_pr_cache "$repo" "$branch" "MERGED" "$merged_sha"

  cd "$repo"
  run _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"
  _assert_deny_for_rule "PUSH_TO_CLOSED_PR"
  # Pin the existing _record_deny wording so a future refactor can't silently
  # swap the message text and slip past the rule-name+references assertion.
  [[ "$output" == *"PR for branch"* ]] \
    || { echo "expected existing deny wording 'PR for branch', got: $output" >&2; return 1; }
  [[ "$output" == *"is MERGED"* ]] \
    || { echo "expected 'is MERGED' in deny output, got: $output" >&2; return 1; }
}

# ----------------------------------------------------------------------
# M1-AC2: MERGED PR, HEAD ahead by N commits → push ALLOWED + ADR-8 note
# ----------------------------------------------------------------------

@test "T1.3 M1-AC2: MERGED PR HEAD ahead → ALLOW with ADR-8 stderr note" {
  local repo branch base_sha
  branch="feat/t13-ac2"
  repo="$(_build_ahead_repo "$branch" 0)"
  # HEAD at this point is the base commit; record it as the merged SHA.
  base_sha="$(git -C "$repo" rev-parse HEAD)"
  # Add a commit so HEAD is ahead of base_sha.
  printf 'new work\n' > "$repo/new.txt"
  git -C "$repo" add new.txt
  git -C "$repo" commit -q -m "new work"

  # Pre-populate cache: state=MERGED, merge_commit=base_sha (HEAD is now ahead)
  _seed_pr_cache "$repo" "$branch" "MERGED" "$base_sha"

  cd "$repo"
  run --separate-stderr _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"
  _assert_allow
  local expected_note="PR was merged; HEAD is ahead by new commits"
  [[ "$stderr" == *"$expected_note"* ]] \
    || { echo "expected ADR-8 note in stderr, got: $stderr" >&2; return 1; }
}

# ----------------------------------------------------------------------
# M1-AC3: Branch with NO_PR → ALLOW (M1 MERGED block not entered)
# ----------------------------------------------------------------------

@test "T1.3 M1-AC3: NO_PR branch → ALLOW (ahead-check not entered)" {
  local repo branch
  branch="feat/t13-ac3"
  repo="$(_build_ahead_repo "$branch" 1)"

  # Pre-populate cache with NO_PR state — no merge_commit field.
  _seed_pr_cache "$repo" "$branch" "NO_PR"

  cd "$repo"
  run _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"
  _assert_allow
}

# ----------------------------------------------------------------------
# Cache-hit: merge_commit already cached → zero gh pr view invocations
# ----------------------------------------------------------------------

@test "T1.3 cache-hit: merge_commit cached → no gh pr view call" {
  local repo branch merged_sha spy_file
  branch="feat/t13-cache-hit"
  repo="$(_build_ahead_repo "$branch" 0)"
  merged_sha="$(git -C "$repo" rev-parse HEAD)"

  # Pre-populate cache with merge_commit present (cache hit).
  _seed_pr_cache "$repo" "$branch" "MERGED" "$merged_sha"

  # Set up spy to track gh pr view calls.
  spy_file="$(mktemp "${TMPDIR:-/tmp}/tcs-gh-spy.XXXXXX")"
  export GH_STUB_SPY_FILE="$spy_file"

  cd "$repo"
  run _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"

  # Capture spy state and clean up immediately — assertions after this line
  # can `return 1` and would otherwise orphan the tempfile in $TMPDIR.
  local call_count=0
  if [ -f "$spy_file" ]; then
    call_count=$(wc -l < "$spy_file" | tr -d ' ')
  fi
  rm -f "$spy_file"
  unset GH_STUB_SPY_FILE

  # merge_commit was cached → no gh pr view call.
  [ "$call_count" -eq 0 ] \
    || { echo "expected 0 gh pr view calls (cache hit), got: $call_count" >&2; return 1; }
  # HEAD == merged_sha → deny path.
  _assert_deny_for_rule "PUSH_TO_CLOSED_PR"
}

# ----------------------------------------------------------------------
# Cache-miss: MERGED state cached but no merge_commit → one gh pr view call;
# result written back to cache.
# ----------------------------------------------------------------------

@test "T1.3 cache-miss: MERGED+no merge_commit → one gh pr view call; SHA cached" {
  local repo branch spy_file expected_sha resolved_path hash cache_file
  branch="feat/t13-cache-miss"
  repo="$(_build_ahead_repo "$branch" 1)"

  # Seed cache with MERGED but no merge_commit (simulates first push after
  # state was cached without SHA).
  _seed_pr_cache "$repo" "$branch" "MERGED"

  # Use merged-pr scenario: pr-view.json returns a non-empty mergeCommit SHA.
  export GH_STUB_SCENARIO="merged-pr"

  spy_file="$(mktemp "${TMPDIR:-/tmp}/tcs-gh-spy.XXXXXX")"
  export GH_STUB_SPY_FILE="$spy_file"

  # Compute cache file path BEFORE rm -rf so we can read it after the run.
  # Mirrors _seed_pr_cache's hashing (symlink-resolved path → shasum head -c 12).
  resolved_path="$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null)" \
    || resolved_path="$repo"
  hash="$(printf '%s' "$resolved_path" | shasum 2>/dev/null | head -c 12)"
  cache_file="$CLAUDE_PLUGIN_DATA/cache/${hash}-pr-state.json"
  # SHA from merged-pr/pr-view.json {"mergeCommit":{"oid":"d8c4a23..."}}.
  expected_sha="d8c4a23719fbe21b8b7d6f1e2c5a90b3e7f4d6c1"

  cd "$repo"
  run _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"

  # Capture spy state and clean up immediately — assertions after this line
  # can `return 1` and would otherwise orphan the tempfile in $TMPDIR.
  local call_count=0
  if [ -f "$spy_file" ]; then
    call_count=$(wc -l < "$spy_file" | tr -d ' ')
  fi
  rm -f "$spy_file"
  unset GH_STUB_SPY_FILE

  # Exactly one gh pr view call was made (cache miss → fetch SHA).
  [ "$call_count" -eq 1 ] \
    || { echo "expected 1 gh pr view call (cache miss), got: $call_count" >&2; return 1; }

  # Verify the resolved SHA was written back to the cache via T1.1's extended
  # writer — the merge_commit field round-trips so a subsequent push would
  # hit the cache-hit path (zero gh calls).
  [ -f "$cache_file" ] \
    || { echo "expected cache file at $cache_file" >&2; return 1; }
  local cached_sha
  cached_sha="$(jq -r --arg b "$branch" '.branch_state[$b].merge_commit // empty' "$cache_file")"
  [ "$cached_sha" = "$expected_sha" ] \
    || { echo "expected cached merge_commit=$expected_sha, got: $cached_sha" >&2; return 1; }
}

# ----------------------------------------------------------------------
# SHA-resolution-fail: gh pr view returns empty → _is_ahead_of_merged
# returns 2 → falls through to override/deny (no regression in deny path)
# ----------------------------------------------------------------------

@test "T1.3 SHA-fail: gh returns empty mergeCommit → fall-through to DENY" {
  local repo branch
  branch="feat/t13-sha-fail"
  repo="$(_build_ahead_repo "$branch" 1)"

  # Seed cache: MERGED state, no merge_commit.
  _seed_pr_cache "$repo" "$branch" "MERGED"

  # Use scenario where pr-view returns null mergeCommit (→ empty jq output).
  export GH_STUB_SCENARIO="merged-pr-no-sha"

  cd "$repo"
  run _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"

  # SHA unavailable → _is_ahead_of_merged returns 2 → deny path fires.
  _assert_deny_for_rule "PUSH_TO_CLOSED_PR"
  # Pin the existing _record_deny wording — confirms the pre-existing deny
  # path fired (not a new SHA-resolution-specific error path).
  [[ "$output" == *"PR for branch"* ]] \
    || { echo "expected existing deny wording 'PR for branch', got: $output" >&2; return 1; }
  [[ "$output" == *"is MERGED"* ]] \
    || { echo "expected 'is MERGED' in deny output, got: $output" >&2; return 1; }
}

# ----------------------------------------------------------------------
# #42 sibling: git-op literals quoted inside another command's argument
# (commit/PR bodies, echo/printf payloads, heredocs) must NOT trip a
# denial. The matcher must look at real command clauses, not substring-
# scan the whole command string.
# ----------------------------------------------------------------------

@test "#42 sibling: 'git reset --hard' quoted inside a commit message → ALLOWED" {
  run _run_hook_with_cmd 'git commit -m "revert the git reset --hard hack"'
  _assert_allow
}

@test "#42 sibling: 'git push --force' inside an echo string → ALLOWED" {
  run _run_hook_with_cmd 'echo "reminder: never git push --force on main"'
  _assert_allow
}

@test "#42 sibling: 'git stash drop' inside a printf payload → ALLOWED" {
  run _run_hook_with_cmd "printf '%s\\n' 'run git stash drop to clean up'"
  _assert_allow
}

@test "#42 sibling: destructive literal inside a gh PR body → ALLOWED" {
  run _run_hook_with_cmd 'gh pr create --title x --body "we ran git reset --hard earlier"'
  _assert_allow
}

# Regression guards: real destructive ops (bare and cd-prefixed) still fire.
@test "#42 sibling regression: bare 'git reset --hard' still DENIED" {
  run _run_hook_with_cmd "git reset --hard"
  _assert_deny_for_rule "RESET_HARD"
}

@test "#42 sibling regression: cd-prefixed 'git reset --hard' still DENIED" {
  run _run_hook_with_cmd "cd /tmp && git reset --hard"
  _assert_deny_for_rule "RESET_HARD"
}

@test "#42 sibling regression: real 'git push --force' (unquoted) still DENIED" {
  run _run_hook_with_cmd "git push --force origin main"
  _assert_deny_for_rule "FORCE_PUSH"
}

# Shell-executor payloads are CODE, not data — must stay caught (no regression
# of the subshell-evasion guard).
@test "#42 sibling: bash -c '<destructive>' is still DENIED (executor payload)" {
  run _run_hook_with_cmd "bash -c 'git push --force origin main'"
  _assert_deny_for_rule "FORCE_PUSH"
}

@test "#42 sibling: sh -c \"<destructive>\" is still DENIED (executor payload)" {
  run _run_hook_with_cmd 'sh -c "git reset --hard"'
  _assert_deny_for_rule "RESET_HARD"
}
