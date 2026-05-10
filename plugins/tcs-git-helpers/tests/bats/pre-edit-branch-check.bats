#!/usr/bin/env bats
# Tests for scripts/pre-edit-branch-check.sh (T2.2).
#
# Coverage:
#   - Tool gate: non-editing tools / empty file_path → exit 0 silent
#   - CLAUDE_ALLOW_MAIN_EDITS=1 escape on main → exit 0 silent (M11 AC3 parity)
#   - main / master deny: emits user-global-compatible JSON shape
#   - Gitignored paths exempt on main
#   - State bypass: rebase / merge / cherry-pick / bisect / detached HEAD
#     → exit 0 with stderr "bypass: state-X"
#   - Squash-merge orphan branch → exit 0 with stderr WARNING (NOT a deny)
#   - Active and merge-commit branches → exit 0 silent (no warning, no deny)
#
# Spec refs:
#   - SDD §Building Block View — pre-edit-branch-check
#   - PRD M11 AC3 — coexistence with user-global block-main-edits.sh

bats_require_minimum_version 1.5.0

setup() {
  PLUGIN_ROOT="$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/pre-edit-branch-check.sh"

  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/pre-edit-branch-check.XXXXXX")"
  fi
  export TEST_DIR

  # Stub plugin-data dir — audit_log lib resolves under it; sourced libs
  # define functions only and don't write anything at source time, but we
  # keep CLAUDE_PLUGIN_DATA inside the test sandbox for hygiene.
  TMP_DATA="$TEST_DIR/plugin-data"
  mkdir -p "$TMP_DATA"
  export CLAUDE_PLUGIN_DATA="$TMP_DATA"

  export GIT_AUTHOR_NAME="bats" GIT_AUTHOR_EMAIL="b@a.ts"
  export GIT_COMMITTER_NAME="bats" GIT_COMMITTER_EMAIL="b@a.ts"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  unset CLAUDE_ALLOW_MAIN_EDITS

  MADE_REPO_PATH=""
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# Build a synthetic origin + work tree under $TEST_DIR.
# Modes:
#   minimal       — main only, one commit, pushed (no feat branch)
#   feat-active   — feat branch with one unmerged commit ahead of origin/main
#                   (cherry → all `+`; not dangerous)
#   feat-squash   — feat's patch was cherry-picked onto a moved main so the
#                   feat tip is orphan from origin/main but its patch IS
#                   applied (cherry → all `-`; the squash trap)
#   feat-merge    — feat merged into main via --no-ff; feat tip IS ancestor
#                   of origin/main (safe; no warning expected)
_make_repo() {
  local kind="$1"
  local origin="$TEST_DIR/origin-$kind.git"
  local work="$TEST_DIR/work-$kind"
  rm -rf "$origin" "$work"
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

  if [ "$kind" = "minimal" ]; then
    MADE_REPO_PATH="$work"
    return 0
  fi

  git -C "$work" checkout -q -b feat
  printf 'b\n' > "$work/b.txt"
  git -C "$work" add b.txt
  git -C "$work" commit -q -m 'feat-1'
  git -C "$work" push -q -u origin feat

  case "$kind" in
    feat-active)
      :
      ;;
    feat-squash)
      # Move main forward, then cherry-pick feat onto it. feat tip is now
      # orphan vs origin/main but its patch IS applied — `git cherry` reports
      # the feat commit as `-`, the dangerous-squash signature.
      git -C "$work" checkout -q main
      printf 'main-extra\n' > "$work/main_extra.txt"
      git -C "$work" add main_extra.txt
      git -C "$work" commit -q -m 'main-extra'
      git -C "$work" cherry-pick "$(git -C "$work" rev-parse feat)" >/dev/null 2>&1
      git -C "$work" push -q origin main
      git -C "$work" fetch -q origin
      git -C "$work" checkout -q feat
      ;;
    feat-merge)
      git -C "$work" checkout -q main
      git -C "$work" merge --no-ff -q -m 'merge feat' feat
      git -C "$work" push -q origin main
      git -C "$work" fetch -q origin
      git -C "$work" checkout -q feat
      ;;
  esac
  MADE_REPO_PATH="$work"
  return 0
}

# Run the hook with `$1` JSON on stdin. Captures stdout in $output, stderr
# in $stderr (via --separate-stderr), and exit code in $status.
_run_hook() {
  local input_file="$TEST_DIR/input.json"
  printf '%s' "$1" > "$input_file"
  run --separate-stderr bash -c '"$1" < "$2"' _ "$HOOK" "$input_file"
}

# ---------- Tool gate ----------

@test "non-editing tool (Bash) → exit 0 silent" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  _run_hook '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "Write with empty file_path → exit 0 silent" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  _run_hook '{"tool_name":"Write","tool_input":{}}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Write outside any git repo → exit 0 silent" {
  local outside="$TEST_DIR/no-repo"
  mkdir -p "$outside"
  cd "$outside"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$outside/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------- main / master deny ----------

@test "Write on main → deny JSON (user-global-compatible shape)" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
  printf '%s' "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' | grep -q "main"
  printf '%s' "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' | grep -q "Write"
  printf '%s' "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' | grep -q "foo.txt"
}

@test "Edit on master → deny JSON" {
  _make_repo minimal
  git -C "$MADE_REPO_PATH" branch -m main master >/dev/null 2>&1
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
  printf '%s' "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' | grep -q "master"
}

@test "NotebookEdit on main → deny JSON" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"NotebookEdit\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/nb.ipynb\"}}"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
  printf '%s' "$output" | jq -er '.hookSpecificOutput.permissionDecisionReason' | grep -q "NotebookEdit"
}

# ---------- Escape hatches ----------

@test "CLAUDE_ALLOW_MAIN_EDITS=1 on main → exit 0 silent (parity with user-global)" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  export CLAUDE_ALLOW_MAIN_EDITS=1
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  unset CLAUDE_ALLOW_MAIN_EDITS
}

@test "gitignored path on main → exit 0 silent (exempt)" {
  _make_repo minimal
  printf 'ignored.txt\n' > "$MADE_REPO_PATH/.gitignore"
  git -C "$MADE_REPO_PATH" add .gitignore
  git -C "$MADE_REPO_PATH" commit -q -m 'add gitignore'
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/ignored.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------- State bypass ----------

@test "rebase in progress (rebase-merge) → exit 0 with bypass: state-rebase" {
  _make_repo minimal
  mkdir -p "$MADE_REPO_PATH/.git/rebase-merge"
  printf 'main\n' > "$MADE_REPO_PATH/.git/rebase-merge/head-name"
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "bypass: state-rebase"
}

@test "rebase in progress (rebase-apply, am/legacy) → exit 0 with bypass: state-rebase" {
  # `git am` and the legacy interactive-rebase backend leave a .git/rebase-apply/
  # directory instead of rebase-merge/. The hook accepts EITHER as the
  # rebase-in-progress signal — pin both code paths so a future `||→&&` typo
  # is caught.
  _make_repo minimal
  mkdir -p "$MADE_REPO_PATH/.git/rebase-apply"
  printf 'main\n' > "$MADE_REPO_PATH/.git/rebase-apply/head-name"
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "bypass: state-rebase"
}

@test "merge in progress → exit 0 with bypass: state-merge" {
  _make_repo minimal
  printf '%s\n' "$(git -C "$MADE_REPO_PATH" rev-parse HEAD)" > "$MADE_REPO_PATH/.git/MERGE_HEAD"
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "bypass: state-merge"
}

@test "cherry-pick in progress → exit 0 with bypass: state-cherry-pick" {
  _make_repo minimal
  printf '%s\n' "$(git -C "$MADE_REPO_PATH" rev-parse HEAD)" > "$MADE_REPO_PATH/.git/CHERRY_PICK_HEAD"
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "bypass: state-cherry-pick"
}

@test "bisect in progress → exit 0 with bypass: state-bisect" {
  _make_repo minimal
  : > "$MADE_REPO_PATH/.git/BISECT_LOG"
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "bypass: state-bisect"
}

@test "detached HEAD → exit 0 with bypass: state-detached" {
  _make_repo minimal
  git -C "$MADE_REPO_PATH" checkout -q --detach HEAD
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "bypass: state-detached"
}

# ---------- Squash-merge orphan augmentation ----------

@test "squash-merge orphan branch → exit 0 with WARNING (no deny)" {
  _make_repo feat-squash
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  printf '%s' "$stderr" | grep -q "WARNING"
  printf '%s' "$stderr" | grep -qi "squash"
}

@test "active feat branch (cherry → all '+') → exit 0 silent (no warning)" {
  _make_repo feat-active
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  ! printf '%s' "$stderr" | grep -q "WARNING"
}

@test "merge-commit branch (safe ancestor) → exit 0 silent (no warning)" {
  _make_repo feat-merge
  cd "$MADE_REPO_PATH"
  _run_hook "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$MADE_REPO_PATH/foo.txt\"}}"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  ! printf '%s' "$stderr" | grep -q "WARNING"
}

# ----------------------------------------------------------------------
# Robustness: malformed JSON stdin → fail-open (regression-trap for the
# `|| true` guards on the jq pipelines). Without those guards, a parse
# error under `set -euo pipefail` would propagate as a non-zero exit and
# unconditionally block the underlying Edit/Write/NotebookEdit call.
# Mirrors the canonical pattern from T2.3 (commit 1606411).
# ----------------------------------------------------------------------

@test "malformed JSON stdin → fail-open exit 0, no output" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  run --separate-stderr bash -c 'printf "%s" "not-json" | "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "truncated JSON stdin → fail-open exit 0, no output" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  run --separate-stderr bash -c 'printf "%s" "{\"tool_name\":\"Write\"" | "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "empty stdin → fail-open exit 0, no output" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  run --separate-stderr bash -c 'printf "" | "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Regression-trap: file_path with embedded tab MUST round-trip verbatim
# through the hook into the deny reason. An earlier `@tsv` combined-jq
# parse silently re-encoded tabs as the literal 2-char escape `\t`, which
# corrupted both `git check-ignore` and the deny payload. Two separate
# `jq -r` reads avoid that class of bug entirely.
# ----------------------------------------------------------------------

@test "file_path with embedded tab survives hook intact (deny reason has real tab)" {
  _make_repo minimal
  cd "$MADE_REPO_PATH"
  TAB=$(printf '\t')
  TARGET="${MADE_REPO_PATH}/foo${TAB}bar.txt"
  # Build the JSON via jq so the tab is encoded as a real tab character
  # inside the string (not as backslash-t).
  INPUT_JSON=$(jq -nc --arg fp "$TARGET" '{tool_name:"Write",tool_input:{file_path:$fp}}')
  _run_hook "$INPUT_JSON"
  [ "$status" -eq 0 ]
  printf '%s' "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
  REASON=$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason')
  # The reason must contain the literal tab-bearing relpath, NOT the
  # backslash-t escape that @tsv would have produced.
  printf '%s' "$REASON" | grep -qF "foo${TAB}bar.txt"
  ! printf '%s' "$REASON" | grep -qF 'foo\tbar.txt'
}
