#!/bin/bash
# shellcheck shell=bash
# scripts/block-eslint-disable.sh — PreToolUse:Write|Edit|NotebookEdit guard.
#
# Denies any write that introduces a disabled ESLint rule into an Obsidian
# plugin repository. The Obsidian community-plugin reviewer (community.obsidian.md
# portal; legacy path: the obsidianmd/obsidian-releases PR bot) scans submissions
# for disabled rules and rejects the plugin from official registration if any are
# found — for EVERY rule the project's ESLint config loads, not just obsidianmd/*.
# There is no "justified disable" exception, so the fix is always code-side.
#
# This is the write-time counterpart to the `obsidian-plugin` skill's Step 11,
# which only catches disables at audit time (i.e. after they were written).
#
# Scope gate — the hook stays silent unless ALL of these hold:
#   1. The target file lives inside a git repository, and
#   2. that repository looks like an Obsidian plugin
#      (manifest.json with "minAppVersion", or package.json depending on
#      "obsidian"), and
#   3. the target file is not Markdown (docs legitimately quote the pattern).
#
# Detection (mirrors the grep patterns in obsidian-plugin/SKILL.md Step 11):
#   - any file:    the literal string `eslint-disable` (line, block, file form)
#   - ESLint config files and package.json: a rule mapped to "off"
#
# Escape hatch: CLAUDE_ALLOW_ESLINT_DISABLE=1 in the environment.
#
# Hook contract:
#   - stdin: Claude Code PreToolUse JSON
#       { "tool_name": "...", "tool_input": { "file_path": ..., "content": ...,
#                                             "new_string": ..., "new_source": ... } }
#   - stdout (deny only):
#       {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#                              "permissionDecision":"deny",
#                              "permissionDecisionReason":"..."}}
#   - exit: always 0 — denial travels via JSON, never via exit code, so a
#           malformed payload can never hard-block an unrelated edit.
#
# Constraints: bash 3.2 compatible (POSIX globs via `case`, no \s / \b regex).

set -euo pipefail

# Explicit opt-out for the rare case where a disable is deliberate (e.g. a repo
# that will never be submitted to the community directory).
if [ "${CLAUDE_ALLOW_ESLINT_DISABLE:-0}" = "1" ]; then
  exit 0
fi

INPUT=$(cat)

# `|| true` on every jq pipeline: a parse error must fall through to exit 0
# rather than trip `set -e` and block the underlying tool call.
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || true)
case "$TOOL" in
  Write|Edit|NotebookEdit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' 2>/dev/null || true)
[ -z "$FILE_PATH" ] && exit 0

# Documentation may quote the forbidden pattern verbatim — this file does.
case "$FILE_PATH" in
  *.md|*.mdx|*/node_modules/*) exit 0 ;;
esac

# Only the incoming text matters. old_string is what is being replaced, so a
# removal of an existing disable must not be blocked by its own payload.
CONTENT=$(printf '%s' "$INPUT" | jq -r '
  [.tool_input.content, .tool_input.new_string, .tool_input.new_source]
  | map(select(. != null)) | join("\n")' 2>/dev/null || true)
[ -z "$CONTENT" ] && exit 0

# ── Scope gate: is the target inside an Obsidian plugin repo? ──────────────
# Walk up to the nearest existing ancestor — the file itself may not exist yet
# and its parent directory may be created by the same tool call.
DIR=$(dirname "$FILE_PATH")
while [ ! -d "$DIR" ] && [ "$DIR" != "/" ] && [ -n "$DIR" ]; do
  DIR=$(dirname "$DIR")
done
[ -d "$DIR" ] || exit 0

REPO_DIR=$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null || true)
[ -z "$REPO_DIR" ] && exit 0

IS_OBSIDIAN=0
if [ -f "${REPO_DIR}/manifest.json" ] && grep -q "minAppVersion" "${REPO_DIR}/manifest.json" 2>/dev/null; then
  IS_OBSIDIAN=1
elif [ -f "${REPO_DIR}/package.json" ] && grep -qE '"obsidian"[[:space:]]*:' "${REPO_DIR}/package.json" 2>/dev/null; then
  IS_OBSIDIAN=1
fi
[ "$IS_OBSIDIAN" = "1" ] || exit 0

# ── Detection ─────────────────────────────────────────────────────────────
VIOLATION=""
MATCH=""

if printf '%s' "$CONTENT" | grep -q "eslint-disable" 2>/dev/null; then
  VIOLATION="inline eslint-disable comment"
  MATCH=$(printf '%s' "$CONTENT" | grep -m1 "eslint-disable" 2>/dev/null || true)
fi

if [ -z "$VIOLATION" ]; then
  BASENAME=$(basename "$FILE_PATH")
  case "$BASENAME" in
    .eslintrc*|eslint.config.*|package.json)
      if printf '%s' "$CONTENT" | grep -qE "['\"][a-zA-Z@/_-]+['\"][[:space:]]*:[[:space:]]*\[?[[:space:]]*['\"]off['\"]" 2>/dev/null; then
        VIOLATION="rule turned off in ESLint config"
        MATCH=$(printf '%s' "$CONTENT" | grep -m1 -E "['\"][a-zA-Z@/_-]+['\"][[:space:]]*:[[:space:]]*\[?[[:space:]]*['\"]off['\"]" 2>/dev/null || true)
      fi
      ;;
  esac
fi

[ -z "$VIOLATION" ] && exit 0

# ── Deny ──────────────────────────────────────────────────────────────────
# Trim the matched line so the reason stays readable in the tool result.
MATCH=$(printf '%s' "$MATCH" | sed 's/^[[:space:]]*//' | cut -c1-120)

# Targeted remediation for the rules that keep coming up in practice.
HINT="Change the code so the rule passes. If a type or global is missing, declare it (ambient .d.ts, @types/* devDependency) instead of silencing the rule."
case "$MATCH" in
  *sentence-case*)
    HINT="obsidianmd/ui/sentence-case: rewrite the UI string in sentence case ('Enable live preview', not 'Enable Live Preview'). Proper nouns stay capitalised." ;;
  *prefer-active-window-timers*)
    HINT="obsidianmd/prefer-active-window-timers: use activeWindow.setInterval/setTimeout in production code; in tests spy on activeWindow (vi.spyOn(activeWindow, 'setInterval')) instead of vi.useFakeTimers()." ;;
  *manage-class*)
    HINT="obsidianmd/manage-class: use el.addClass / removeClass / toggleClass instead of assigning el.className." ;;
  *no-html-element-creation*)
    HINT="obsidianmd/no-html-element-creation: use Obsidian's createEl / createDiv / createSpan helpers instead of document.createElement." ;;
  *prefer-import*|*__filename*|*__dirname*)
    HINT="@typescript-eslint/prefer-import on CJS globals: add @types/node to devDependencies, or declare the global in src/types/runtime-globals.d.ts." ;;
esac

REASON="Refusing to ${TOOL} '${FILE_PATH}': ${VIOLATION} detected (${MATCH}). This repo is an Obsidian plugin, and the community-plugin reviewer rejects any submission containing a disabled ESLint rule — every rule the config loads, no 'justified disable' exception. ${HINT} See the /obsidian-plugin skill (Step 11) for the full list of non-disable fixes. If this repo will never be submitted to the community directory, relaunch Claude with CLAUDE_ALLOW_ESLINT_DISABLE=1."

jq -nc --arg reason "$REASON" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'

exit 0
