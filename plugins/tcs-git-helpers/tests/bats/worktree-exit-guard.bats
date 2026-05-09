#!/usr/bin/env bats
# Tests for plugins/tcs-git-helpers/scripts/worktree-exit-guard.sh
#
# Coverage per plan/phase-2.md T2.4:
#   - exits 0 silently when tool_name is not ExitWorktree
#   - exits 0 silently when tool_input.worktree_path is missing
#   - allows clean worktree
#   - denies when working tree has modified files          (check 1)
#   - denies when untracked files present                   (check 2)
#   - denies when branch has unmerged commits (cherry +)    (check 3)
#   - denies when branch has unpushed commits (ahead>0)     (check 4)
#   - cascading denial reports ALL four checks (EC2)
#   - denial response includes override hint
#   - CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1 allows once + sentinel + audit
#   - subsequent attempt within 5s re-denies (double-tap)
#   - allow path emits override-consumed banner on stderr

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/worktree-exit-guard.sh"
  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/worktree-exit-guard.XXXXXX")"
  fi
  export TEST_DIR
  export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  export CLAUDE_PLUGIN_DATA="$TEST_DIR/plugin-data"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache" "$CLAUDE_PLUGIN_DATA/audit"

  export GIT_AUTHOR_NAME="bats"
  export GIT_AUTHOR_EMAIL="b@a.ts"
  export GIT_COMMITTER_NAME="bats"
  export GIT_COMMITTER_EMAIL="b@a.ts"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  unset CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES 2>/dev/null || true
  unset CLAUDE_ALLOW_GIT_BAD_OPS 2>/dev/null || true

  MADE_REPO_PATH=""
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# Build a synthetic origin + working tree under $TEST_DIR.
# Modes (one fixture per check + a combined one for cascading):
#   clean             — main with one commit, pushed; no working changes
#   modified          — clean + a tracked file modified                  (check 1)
#   untracked         — clean + an untracked file                        (check 2)
#   unmerged-pushed   — feat with one commit pushed to its upstream;     (check 3)
#                       commit absent from origin/main → cherry '+',
#                       BRANCH_AHEAD vs origin/feat = 0 (so check 4 quiet)
#   unpushed-unmerged — feat with 2 local commits beyond upstream;       (checks 3+4)
#                       BRANCH_AHEAD=2 + cherry '+' for all 3 commits
#   all-four          — modified + untracked + unmerged + unpushed       (cascading)
_make_repo() {
  local kind="$1"
  local origin="$TEST_DIR/origin-$kind.git"
  local work="$TEST_DIR/work-$kind"

  git init --bare --initial-branch=main "$origin" >/dev/null 2>&1 \
    || { git init --bare "$origin" >/dev/null 2>&1; \
         git -C "$origin" symbolic-ref HEAD refs/heads/main; }
  git init --initial-branch=main "$work" >/dev/null 2>&1 \
    || { git init "$work" >/dev/null 2>&1; \
         git -C "$work" checkout -B main >/dev/null 2>&1; }
  git -C "$work" remote add origin "$origin"
  printf 'a\n' > "$work/a.txt"
  git -C "$work" add a.txt
  git -C "$work" commit -q -m 'init'
  git -C "$work" push -q -u origin main
  git -C "$work" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

  case "$kind" in
    clean)
      :
      ;;
    modified)
      printf 'modified\n' >> "$work/a.txt"
      ;;
    untracked)
      printf 'untracked content\n' > "$work/new.txt"
      ;;
    unmerged-pushed)
      git -C "$work" checkout -q -b feat
      printf 'b\n' > "$work/b.txt"
      git -C "$work" add b.txt
      git -C "$work" commit -q -m 'feat-1'
      git -C "$work" push -q -u origin feat
      ;;
    unpushed-unmerged)
      git -C "$work" checkout -q -b feat
      printf 'b\n' > "$work/b.txt"
      git -C "$work" add b.txt
      git -C "$work" commit -q -m 'feat-1'
      git -C "$work" push -q -u origin feat
      # Two more local commits (not pushed) → ahead=2; cherry '+' for all 3.
      printf 'c\n' > "$work/c.txt"
      git -C "$work" add c.txt
      git -C "$work" commit -q -m 'feat-2'
      printf 'd\n' > "$work/d.txt"
      git -C "$work" add d.txt
      git -C "$work" commit -q -m 'feat-3'
      ;;
    all-four)
      git -C "$work" checkout -q -b feat
      printf 'b\n' > "$work/b.txt"
      git -C "$work" add b.txt
      git -C "$work" commit -q -m 'feat-1'
      git -C "$work" push -q -u origin feat
      printf 'c\n' > "$work/c.txt"
      git -C "$work" add c.txt
      git -C "$work" commit -q -m 'feat-2'
      printf 'mod\n' >> "$work/a.txt"
      printf 'unt\n' > "$work/u.txt"
      ;;
  esac

  MADE_REPO_PATH="$work"
}

# Invoke the hook with a synthetic ExitWorktree payload pointing at $1.
_invoke_hook() {
  local worktree="$1"
  local payload
  payload=$(printf '{"tool_name":"ExitWorktree","tool_input":{"worktree_path":"%s"}}' \
              "$worktree")
  printf '%s' "$payload" | bash "$HOOK"
}

@test "exits 0 silently when tool_name is not ExitWorktree" {
  _make_repo modified
  payload='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "printf '%s' '$payload' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "exits 0 silently when worktree_path is missing" {
  payload='{"tool_name":"ExitWorktree","tool_input":{}}'
  run bash -c "printf '%s' '$payload' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "exits 0 silently when worktree_path is not a directory" {
  payload='{"tool_name":"ExitWorktree","tool_input":{"worktree_path":"/nonexistent/path/abc"}}'
  run bash -c "printf '%s' '$payload' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "exits 0 silently when worktree_path is a real but non-git directory" {
  # Pure directory with no .git — guards `git rev-parse --git-dir` exit-zero
  # path. Without `git init`, every git command would fall through to the
  # parent .git of $PWD or fail; the hook must short-circuit before that.
  non_git_dir="$TEST_DIR/not-a-repo"
  mkdir -p "$non_git_dir"
  run _invoke_hook "$non_git_dir"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "allows clean worktree (all 4 checks pass)" {
  _make_repo clean
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "denies when working tree has modified files (check 1)" {
  _make_repo modified
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"permissionDecision":"deny"'
  printf '%s' "$output" | grep -q 'modified'
  printf '%s' "$output" | grep -q 'a.txt'
}

@test "denies when untracked files present (check 2)" {
  _make_repo untracked
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"permissionDecision":"deny"'
  printf '%s' "$output" | grep -q 'untracked'
  printf '%s' "$output" | grep -q 'new.txt'
}

@test "denies when branch has unmerged commits via git cherry (check 3)" {
  _make_repo unmerged-pushed
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"permissionDecision":"deny"'
  printf '%s' "$output" | grep -q 'unmerged'
  # Branch tip == origin/feat tip → unpushed must be quiet on this fixture.
  ! printf '%s' "$output" | grep -q 'unpushed'
}

@test "denies when branch has unpushed commits (check 4)" {
  _make_repo unpushed-unmerged
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"permissionDecision":"deny"'
  printf '%s' "$output" | grep -q 'unpushed'
  # Same fixture also has unmerged commits — both should be reported.
  printf '%s' "$output" | grep -q 'unmerged'
}

@test "cascading denial reports ALL four checks in one response (EC2)" {
  _make_repo all-four
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q 'modified'
  printf '%s' "$output" | grep -q 'untracked'
  printf '%s' "$output" | grep -q 'unmerged'
  printf '%s' "$output" | grep -q 'unpushed'
  # Single denial response — exactly one permissionDecision present.
  count=$(printf '%s' "$output" | grep -c '"permissionDecision":"deny"' || true)
  [ "$count" = "1" ]
}

@test "denial response includes override hint" {
  _make_repo modified
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q 'CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES'
}

@test "denial response cites references/worktree-discipline.md (T5.6)" {
  # T5.6 spec compliance: every denial body must cite the relevant reference
  # doc so the user has a self-contained pointer to the rationale.
  _make_repo modified
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q 'worktree-discipline.md'
}

@test "denial reason fits within 15 lines (EC1)" {
  _make_repo all-four
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  # Extract the reason field's content, count embedded \n-separated lines.
  reason=$(printf '%s' "$output" \
             | sed -n 's/.*"permissionDecisionReason":"\(.*\)"}}.*/\1/p')
  [ -n "$reason" ]
  # +1 because the first line has no leading separator
  newline_count=$(printf '%s' "$reason" | grep -o '\\n' | wc -l | tr -d ' ')
  line_count=$((newline_count + 1))
  [ "$line_count" -le 15 ]
}

@test "CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1 allows once and writes sentinel" {
  _make_repo modified
  export CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
  # Capture stdout only — stderr carries the "override consumed" banner
  # which we test separately, but it must NOT leak deny JSON to stdout.
  output_only=$(_invoke_hook "$MADE_REPO_PATH" 2>/dev/null)
  status=$?
  [ "$status" -eq 0 ]
  ! printf '%s' "$output_only" | grep -q '"permissionDecision":"deny"'
  # Sentinel exists after consumption (5s window).
  [ -f "$CLAUDE_PLUGIN_DATA/cache/override-consumed-CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES" ]
}

@test "subsequent attempt within 5s re-denies (double-tap protection)" {
  _make_repo modified
  export CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
  output_only=$(_invoke_hook "$MADE_REPO_PATH" 2>/dev/null)
  status=$?
  [ "$status" -eq 0 ]
  ! printf '%s' "$output_only" | grep -q '"permissionDecision":"deny"'
  # Override.sh unsets the env var inside the hook subshell — the parent
  # bats process still has it set, so re-export is unnecessary.
  export CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"permissionDecision":"deny"'
}

@test "audit log entry written on override consumption" {
  _make_repo modified
  export CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
  run _invoke_hook "$MADE_REPO_PATH"
  [ "$status" -eq 0 ]
  audit_file="$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl"
  [ -f "$audit_file" ]
  grep -q 'CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES' "$audit_file"
}

@test "stderr emits override-consumed banner on allow path" {
  _make_repo modified
  export CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
  payload=$(printf '{"tool_name":"ExitWorktree","tool_input":{"worktree_path":"%s"}}' \
              "$MADE_REPO_PATH")
  # Capture stderr only by routing it to stdout and discarding stdout.
  run bash -c "printf '%s' '$payload' | bash '$HOOK' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q 'OVERRIDE'
}
