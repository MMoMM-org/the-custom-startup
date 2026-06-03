#!/usr/bin/env bats
# T1.1 — Plugin Manifest + Hook Registration
# Validates plugins/tcs-git-helpers structure so Claude Code can load it cleanly.
# Verifies:
#   - .claude-plugin/plugin.json: required fields + valid JSON
#   - hooks/hooks.json: three-level nested format, all 6 hook entry points
#   - PreToolUse (Bash, Edit|Write|NotebookEdit, ExitWorktree), PostToolUse (Bash),
#     SessionStart events registered
#   - All referenced scripts exist with bash shebang (stubs OK in this task)

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."

setup() {
  command -v jq >/dev/null || skip "jq required for JSON assertions"
}

# ---------------------------------------------------------------------------
# .claude-plugin/plugin.json
# ---------------------------------------------------------------------------

@test "plugin.json exists" {
  [ -f "${PLUGIN_ROOT}/.claude-plugin/plugin.json" ]
}

@test "plugin.json is valid JSON" {
  jq -e . "${PLUGIN_ROOT}/.claude-plugin/plugin.json"
}

@test "plugin.json has name 'tcs-git-helpers'" {
  run jq -r '.name' "${PLUGIN_ROOT}/.claude-plugin/plugin.json"
  [ "$status" -eq 0 ]
  [ "$output" = "tcs-git-helpers" ]
}

@test "plugin.json version is valid semver" {
  # Versions are auto-bumped on merge (.github/workflows/auto-bump-versions.yml),
  # so assert semver SHAPE rather than a hardcoded literal that goes stale.
  run jq -r '.version' "${PLUGIN_ROOT}/.claude-plugin/plugin.json"
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

@test "plugin.json has non-empty description" {
  run jq -r '.description // ""' "${PLUGIN_ROOT}/.claude-plugin/plugin.json"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
  [ "$output" != "null" ]
}

@test "plugin.json has author" {
  run jq -e '.author' "${PLUGIN_ROOT}/.claude-plugin/plugin.json"
  [ "$status" -eq 0 ]
}

@test "plugin.json has at least one keyword" {
  run jq -r '.keywords | length' "${PLUGIN_ROOT}/.claude-plugin/plugin.json"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
}

# ---------------------------------------------------------------------------
# hooks/hooks.json — three-level nested format
# ---------------------------------------------------------------------------

@test "hooks.json exists" {
  [ -f "${PLUGIN_ROOT}/hooks/hooks.json" ]
}

@test "hooks.json is valid JSON" {
  jq -e . "${PLUGIN_ROOT}/hooks/hooks.json"
}

@test "hooks.json has top-level 'hooks' key (level 1)" {
  run jq -e '.hooks | type == "object"' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "hooks.json events are arrays of matcher blocks (level 2)" {
  run jq -e '[.hooks[] | type == "array"] | all' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "hooks.json matcher blocks contain hooks array (level 3)" {
  run jq -e '[.hooks[][] | (.hooks | type == "array")] | all' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Required hook events registered
# ---------------------------------------------------------------------------

@test "hooks.json registers PreToolUse event" {
  run jq -e '.hooks.PreToolUse | length > 0' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "hooks.json registers PostToolUse event" {
  run jq -e '.hooks.PostToolUse | length > 0' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "hooks.json registers SessionStart event" {
  run jq -e '.hooks.SessionStart | length > 0' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "SessionStart has matcher 'startup|resume|clear|compact'" {
  run jq -r '[.hooks.SessionStart[].matcher] | index("startup|resume|clear|compact")' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
  [ "$output" != "null" ]
}

# ---------------------------------------------------------------------------
# PreToolUse matchers: Bash, Edit|Write|NotebookEdit, ExitWorktree
# (per SDD §Building Block View; "PreToolUse:ExitWorktree" notation = matcher value)
# ---------------------------------------------------------------------------

@test "PreToolUse has matcher 'Bash'" {
  run jq -e '[.hooks.PreToolUse[].matcher] | index("Bash")' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "PreToolUse has matcher covering Edit, Write, and NotebookEdit" {
  run jq -r '[.hooks.PreToolUse[].matcher] | join(" ")' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Edit"* ]]
  [[ "$output" == *"Write"* ]]
  [[ "$output" == *"NotebookEdit"* ]]
}

@test "PreToolUse has matcher 'ExitWorktree'" {
  run jq -e '[.hooks.PreToolUse[].matcher] | index("ExitWorktree")' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

@test "PostToolUse has matcher 'Bash'" {
  run jq -e '[.hooks.PostToolUse[].matcher] | index("Bash")' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# All 6 hook entry-point scripts referenced + present
# ---------------------------------------------------------------------------

@test "hooks.json references all 6 entry-point scripts" {
  run jq -r '[.. | objects | .command? // empty] | join("\n")' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *"block-bad-git-ops.sh"* ]]
  [[ "$output" == *"pre-edit-branch-check.sh"* ]]
  [[ "$output" == *"protect-git-internals.sh"* ]]
  [[ "$output" == *"nudge-hook.sh"* ]]
  [[ "$output" == *"session-start-brief.sh"* ]]
  [[ "$output" == *"worktree-exit-guard.sh"* ]]
}

@test "hooks.json uses \${CLAUDE_PLUGIN_ROOT} for all command paths" {
  run jq -r '[.. | objects | select(.type? == "command") | .command] | .[]' "${PLUGIN_ROOT}/hooks/hooks.json"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
  while IFS= read -r cmd; do
    [[ "$cmd" == *'${CLAUDE_PLUGIN_ROOT}'* ]] || {
      echo "command missing CLAUDE_PLUGIN_ROOT: $cmd" >&2
      return 1
    }
  done <<< "$output"
}

@test "all 6 entry-point scripts exist on disk" {
  for s in block-bad-git-ops.sh pre-edit-branch-check.sh protect-git-internals.sh \
           nudge-hook.sh session-start-brief.sh worktree-exit-guard.sh; do
    [ -f "${PLUGIN_ROOT}/scripts/$s" ] || {
      echo "missing script: $s" >&2
      return 1
    }
  done
}

@test "all 6 entry-point scripts have bash shebang" {
  for s in block-bad-git-ops.sh pre-edit-branch-check.sh protect-git-internals.sh \
           nudge-hook.sh session-start-brief.sh worktree-exit-guard.sh; do
    head -n 1 "${PLUGIN_ROOT}/scripts/$s" | grep -qE '^#!.*bash' || {
      echo "missing bash shebang: $s" >&2
      return 1
    }
  done
}

@test "all 6 entry-point scripts are executable" {
  for s in block-bad-git-ops.sh pre-edit-branch-check.sh protect-git-internals.sh \
           nudge-hook.sh session-start-brief.sh worktree-exit-guard.sh; do
    [ -x "${PLUGIN_ROOT}/scripts/$s" ] || {
      echo "not executable: $s" >&2
      return 1
    }
  done
}

@test "all 6 entry-point stub scripts exit cleanly (return 0)" {
  for s in block-bad-git-ops.sh pre-edit-branch-check.sh protect-git-internals.sh \
           nudge-hook.sh session-start-brief.sh worktree-exit-guard.sh; do
    # Stubs accept JSON on stdin (real hooks do) but should always exit 0.
    echo '{}' | "${PLUGIN_ROOT}/scripts/$s" || {
      echo "stub script failed: $s" >&2
      return 1
    }
  done
}
