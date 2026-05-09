#!/usr/bin/env bats
# T3.4 — hooks.json Registration Update for Phase 3
# Validates hooks.json registration of all Phase 2 and Phase 3 hook entry points.
# Ensures:
#   - Valid JSON structure
#   - All Phase 2 PreToolUse entries present (Bash, Edit|Write|NotebookEdit, ExitWorktree)
#   - All Phase 3 PostToolUse and SessionStart entries present
#   - Command paths use ${CLAUDE_PLUGIN_ROOT} (no absolute paths)
#   - No unknown top-level keys (future drift detection)

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
HOOKS_JSON="${PLUGIN_ROOT}/hooks/hooks.json"

setup() {
  command -v jq >/dev/null || skip "jq required for JSON assertions"
}

# ---------------------------------------------------------------------------
# Basic JSON validity
# ---------------------------------------------------------------------------

@test "test_hooks_json_is_valid_json" {
  jq -e . "$HOOKS_JSON"
}

# ---------------------------------------------------------------------------
# Phase 2: PreToolUse:Bash → block-bad-git-ops.sh
# ---------------------------------------------------------------------------

@test "test_pre_tool_use_bash_includes_block_bad_git_ops" {
  run jq -e '.hooks.PreToolUse[] | select(.matcher == "Bash") | .hooks[] | select(.command | contains("block-bad-git-ops.sh"))' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Phase 2: PreToolUse:Edit|Write|NotebookEdit → pre-edit-branch-check.sh + protect-git-internals.sh
# ---------------------------------------------------------------------------

@test "test_pre_tool_use_edit_write_includes_pre_edit_branch_check" {
  run jq -e '.hooks.PreToolUse[] | select(.matcher == "Edit|Write|NotebookEdit") | .hooks[] | select(.command | contains("pre-edit-branch-check.sh"))' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
}

@test "test_pre_tool_use_edit_write_includes_protect_git_internals" {
  run jq -e '.hooks.PreToolUse[] | select(.matcher == "Edit|Write|NotebookEdit") | .hooks[] | select(.command | contains("protect-git-internals.sh"))' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Phase 2: PreToolUse:ExitWorktree → worktree-exit-guard.sh
# ---------------------------------------------------------------------------

@test "test_pre_tool_use_exit_worktree_includes_worktree_exit_guard" {
  run jq -e '.hooks.PreToolUse[] | select(.matcher == "ExitWorktree") | .hooks[] | select(.command | contains("worktree-exit-guard.sh"))' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Phase 3: PostToolUse:Bash → nudge-hook.sh
# ---------------------------------------------------------------------------

@test "test_post_tool_use_bash_includes_nudge_hook" {
  run jq -e '.hooks.PostToolUse[] | select(.matcher == "Bash") | .hooks[] | select(.command | contains("nudge-hook.sh"))' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Phase 3: SessionStart with matcher "startup|resume|clear|compact" → session-start-brief.sh
# ---------------------------------------------------------------------------

@test "test_session_start_matcher_includes_brief" {
  run jq -e '.hooks.SessionStart[] | select(.matcher == "startup|resume|clear|compact") | .hooks[] | select(.command | contains("session-start-brief.sh"))' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Convention check: all command paths use ${CLAUDE_PLUGIN_ROOT}
# ---------------------------------------------------------------------------

@test "test_all_command_paths_use_claude_plugin_root" {
  run jq -r '[.. | objects | select(.type? == "command") | .command] | .[]' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
  while IFS= read -r cmd; do
    # shellcheck disable=SC2016
    [[ "$cmd" == *'${CLAUDE_PLUGIN_ROOT}'* ]] || {
      echo "command missing CLAUDE_PLUGIN_ROOT: $cmd" >&2
      return 1
    }
  done <<< "$output"
}

# ---------------------------------------------------------------------------
# Future drift detection: no unknown top-level keys
# ---------------------------------------------------------------------------

@test "test_no_unknown_top_level_keys" {
  run jq -e 'keys' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
  # Only "description" and "hooks" are expected at top level
  run jq -r 'keys[]' "$HOOKS_JSON"
  [ "$status" -eq 0 ]
  while IFS= read -r key; do
    if [[ "$key" != "description" && "$key" != "hooks" ]]; then
      echo "unexpected top-level key: $key" >&2
      return 1
    fi
  done <<< "$output"
}
