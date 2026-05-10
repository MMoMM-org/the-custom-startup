#!/usr/bin/env bats
# Tests for plugins/tcs-git-helpers/scripts/lib/git_state.sh
#
# Coverage per plan/phase-1.md T1.3 + review fixes (W1–W4):
#   - _get_branch_state populates expected vars (clean / dirty / no-upstream)
#   - _is_branch_squash_merged returns 0 for all-`-` cherry, 1 for mixed/all-`+`,
#                                       2 on git error
#   - _is_branch_dangerously_merged returns 1 (safe) for merge-commit,
#                                          0 (dangerous) for squash, 2 on git error
#   - _bypass_state_check returns 0 for {rebase, merge, cherry-pick, bisect, detached HEAD}
#   - _detect_default_branch resolves origin/HEAD chain
#   - git_safe passes through git output and exit codes

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$PLUGIN_ROOT/scripts/lib/git_state.sh"
  # Prefer bats-provided per-test tmpdir; fall back to repo-local scratch dir.
  # Avoids /var/folders if sandboxed.
  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/lib_git_state.XXXXXX")"
  fi
  export TEST_DIR
  export GIT_AUTHOR_NAME="bats" GIT_AUTHOR_EMAIL="b@a.ts"
  export GIT_COMMITTER_NAME="bats" GIT_COMMITTER_EMAIL="b@a.ts"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  MADE_REPO_PATH=""
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# Build a synthetic origin + clone in $TEST_DIR.
# Sets MADE_REPO_PATH to the work-tree path; does NOT cd. Callers must `cd
# "$MADE_REPO_PATH"` (or pass it via `-C`) before invoking lib functions —
# the lib uses `git -C "$PWD"` for worktree-correctness.
#
# Modes:
#   minimal       — main branch, one commit, pushed; no feat
#   active        — feat with 2 unmerged commits, pushed (cherry → all `+`)
#   squash        — feat's commits cherry-picked onto main individually so the patches
#                   land on main under new SHAs while feat's original commits remain
#                   orphan from origin/main (cherry → all `-`). This models GitHub's
#                   "rebase and merge" path and is what `git cherry` actually detects
#                   as the squash trap (true GitHub squash-merge collapses to a single
#                   patch-id and is caught only by the gh cross-check, not git cherry).
#   merge-commit  — feat with 2 commits merged via --no-ff onto main; main pushed
#                   (cherry → empty, since feat tip becomes ancestor of origin/main)
#   mixed         — feat has 3 commits; first one cherry-picked onto main → 1 `-`, 2 `+`
_make_repo() {
  local kind="$1"
  local origin="$TEST_DIR/origin.git"
  local work="$TEST_DIR/work"
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
  # Pin origin/HEAD deterministically.
  git -C "$work" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

  if [ "$kind" = "minimal" ]; then
    MADE_REPO_PATH="$work"
    return 0
  fi

  git -C "$work" checkout -q -b feat
  printf 'b\n' > "$work/b.txt"
  git -C "$work" add b.txt
  git -C "$work" commit -q -m 'feat-1'
  printf 'c\n' > "$work/c.txt"
  git -C "$work" add c.txt
  git -C "$work" commit -q -m 'feat-2'
  if [ "$kind" = "mixed" ]; then
    printf 'd\n' > "$work/d.txt"
    git -C "$work" add d.txt
    git -C "$work" commit -q -m 'feat-3'
  fi
  git -C "$work" push -q -u origin feat

  case "$kind" in
    active)
      # leave feat unmerged; feat is current branch
      :
      ;;
    squash)
      # Cherry-pick all feat commits onto main individually. From git's
      # perspective this is identical to a rebase-merge: each feat patch lands
      # on main under a NEW SHA. `git cherry origin/main feat` will then mark
      # every original feat commit as `-` (patch already applied), and feat's
      # tip is not an ancestor of origin/main — the dangerous-squash signature.
      #
      # Subtlety: feat's parent IS main. Cherry-picking feat-1 directly onto
      # main produces the same SHA (same parent, same content). We advance
      # main by one unrelated commit first to force fresh SHAs on the picked
      # commits.
      git -C "$work" checkout -q main
      printf 'main-extra\n' > "$work/main_extra.txt"
      git -C "$work" add main_extra.txt
      git -C "$work" commit -q -m 'main-extra'
      git -C "$work" cherry-pick "$(git -C "$work" rev-parse feat~1)" "$(git -C "$work" rev-parse feat)" >/dev/null 2>&1
      git -C "$work" push -q origin main
      git -C "$work" fetch -q origin
      git -C "$work" checkout -q feat
      ;;
    merge-commit)
      git -C "$work" checkout -q main
      git -C "$work" merge --no-ff -q -m 'merge feat' feat
      git -C "$work" push -q origin main
      git -C "$work" fetch -q origin
      git -C "$work" checkout -q feat
      ;;
    mixed)
      git -C "$work" checkout -q main
      # cherry-pick the first feat commit onto main (creates new SHA, same patch)
      git -C "$work" cherry-pick "$(git -C "$work" rev-parse feat~2)" >/dev/null 2>&1
      git -C "$work" push -q origin main
      git -C "$work" fetch -q origin
      git -C "$work" checkout -q feat
      ;;
  esac
  MADE_REPO_PATH="$work"
  return 0
}

@test "_detect_default_branch resolves main via origin/HEAD" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _detect_default_branch
  [ "$status" -eq 0 ]
  [ "$output" = "main" ]
}

@test "_detect_default_branch falls back to local main when origin/HEAD missing" {
  _make_repo minimal
  git -C "$MADE_REPO_PATH" update-ref -d refs/remotes/origin/HEAD 2>/dev/null || true
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _detect_default_branch
  [ "$status" -eq 0 ]
  [[ "$output" = "main" || "$output" = "master" ]]
}

@test "_is_branch_squash_merged returns 0 when all cherry lines are '-' (squash)" {
  _make_repo squash
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _is_branch_squash_merged feat main
  [ "$status" -eq 0 ]
}

@test "_is_branch_squash_merged returns 1 when cherry output is mixed" {
  _make_repo mixed
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _is_branch_squash_merged feat main
  [ "$status" -eq 1 ]
}

@test "_is_branch_squash_merged returns 1 when cherry output is all '+' (active)" {
  _make_repo active
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _is_branch_squash_merged feat main
  [ "$status" -eq 1 ]
}

@test "_is_branch_squash_merged returns 2 on git error (W1)" {
  # Calling against a non-existent branch makes `git cherry` fail; the
  # `|| return 2` guard must surface as exit status 2.
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _is_branch_squash_merged no-such-branch main
  [ "$status" -eq 2 ]
}

@test "_is_branch_dangerously_merged returns 1 (safe) for merge-commit case" {
  _make_repo merge-commit
  cd "$MADE_REPO_PATH"
  source "$LIB"
  # branch tip IS ancestor of origin/main → safe to resume
  run _is_branch_dangerously_merged feat main
  [ "$status" -eq 1 ]
}

@test "_is_branch_dangerously_merged returns 0 (dangerous) for squash case" {
  _make_repo squash
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _is_branch_dangerously_merged feat main
  [ "$status" -eq 0 ]
}

@test "_is_branch_dangerously_merged returns 2 on git error (W2)" {
  # `git rev-parse <unknown-ref>` fails → `|| return 2` guard fires.
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run _is_branch_dangerously_merged no-such-branch main
  [ "$status" -eq 2 ]
}

@test "_get_branch_state populates all expected vars on a clean repo" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  [ "$BRANCH_NAME" = "main" ]
  [ -n "$BRANCH_STATE" ]
  [ "$BRANCH_STATE" = "clean" ]
  [ "$BRANCH_AHEAD" = "0" ]
  [ "$BRANCH_BEHIND" = "0" ]
  [ -n "${PR_STATE:-x}" ]
  [ -n "${PR_NUMBER+x}" ]
  [ "$DETACHED_HEAD" = "0" ]
  [ "$REBASE_IN_PROGRESS" = "0" ]
  [ "$MERGE_IN_PROGRESS" = "0" ]
  [ "$CHERRY_PICK_IN_PROGRESS" = "0" ]
  [ "$BISECT_IN_PROGRESS" = "0" ]
}

@test "_get_branch_state marks BRANCH_STATE=dirty when working tree has changes" {
  _make_repo minimal
  printf 'modified\n' >> "$MADE_REPO_PATH/a.txt"
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  [ "$BRANCH_STATE" = "dirty" ]
}

@test "_get_branch_state populates 0/0 when upstream not set (W3)" {
  # A branch created with `checkout -b` from a local branch does NOT inherit
  # tracking by default. `@{u}` is unresolvable; `git rev-list --left-right
  # --count @{u}...HEAD` exits non-zero. The lib's `|| true` guard must keep
  # _get_branch_state succeeding with AHEAD=0 / BEHIND=0.
  _make_repo minimal
  git -C "$MADE_REPO_PATH" checkout -q -b orphan
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  [ "$BRANCH_NAME" = "orphan" ]
  [ "$BRANCH_AHEAD" = "0" ]
  [ "$BRANCH_BEHIND" = "0" ]
  [ "$DETACHED_HEAD" = "0" ]
}

@test "_bypass_state_check returns 0 during rebase" {
  _make_repo minimal
  mkdir -p "$MADE_REPO_PATH/.git/rebase-merge"
  printf 'main\n' > "$MADE_REPO_PATH/.git/rebase-merge/head-name"
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  run _bypass_state_check
  [ "$status" -eq 0 ]
}

@test "_bypass_state_check returns 0 during merge" {
  _make_repo minimal
  printf '%s\n' "$(git -C "$MADE_REPO_PATH" rev-parse HEAD)" > "$MADE_REPO_PATH/.git/MERGE_HEAD"
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  run _bypass_state_check
  [ "$status" -eq 0 ]
}

@test "_bypass_state_check returns 0 during cherry-pick" {
  _make_repo minimal
  printf '%s\n' "$(git -C "$MADE_REPO_PATH" rev-parse HEAD)" > "$MADE_REPO_PATH/.git/CHERRY_PICK_HEAD"
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  run _bypass_state_check
  [ "$status" -eq 0 ]
}

@test "_bypass_state_check returns 0 during bisect" {
  _make_repo minimal
  : > "$MADE_REPO_PATH/.git/BISECT_LOG"
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  run _bypass_state_check
  [ "$status" -eq 0 ]
}

@test "_bypass_state_check returns 0 with detached HEAD" {
  _make_repo minimal
  git -C "$MADE_REPO_PATH" checkout -q --detach HEAD
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  [ "$DETACHED_HEAD" = "1" ]
  run _bypass_state_check
  [ "$status" -eq 0 ]
}

@test "_bypass_state_check returns 1 in clean state" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  source "$LIB"
  _get_branch_state
  run _bypass_state_check
  [ "$status" -eq 1 ]
}

@test "git_safe passes through git output and exit code" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  source "$LIB"
  run git_safe rev-parse --abbrev-ref HEAD
  [ "$status" -eq 0 ]
  [ "$output" = "main" ]
  # `git rev-parse <unknown-flag>` echoes the flag with rc=0; pick a
  # command that genuinely fails (rev-parse against an unknown ref).
  run git_safe rev-parse --verify refs/heads/no-such-branch-here
  [ "$status" -ne 0 ]
}
