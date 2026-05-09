#!/bin/bash
# shellcheck shell=bash
# scripts/protect-git-internals.sh — PreToolUse:Edit|Write|NotebookEdit guard.
#
# Denies edits to git-internal paths unless TCS_GIT_HELPERS_SETUP_ACTIVE=1 is
# set in the environment (the setup-skill sentinel per ADR-11).
#
# Sensitive paths (research/security.md §5):
#   - <repo>/.githooks/<anything>     (templates this plugin ships into repos)
#   - <repo>/.githooks/.config        (config file under the hooks dir)
#   - <repo>/.git/config              (per-repo git config)
#   - <repo>/.git/hooks/<anything>    (built-in git hooks dir)
# Any other path: ALLOW (exit 0 without writing to stdout).
#
# Spec refs:
#   - SDD §Implementation Examples (ADR-11 sentinel logic)
#   - SDD §Building Block View — protect-git-internals
#   - research/security.md §5 (Hook-Bypass Surface Inventory)
#   - ADR-11 (TCS_GIT_HELPERS_SETUP_ACTIVE env-var sentinel; setup skill
#             exports the var inside a subshell to bound its scope)
#
# Hook contract:
#   - stdin: Claude Code PreToolUse JSON
#       { "tool_name": "...", "tool_input": { "file_path": "..." } }
#   - stdout (deny only):
#       {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#                              "permissionDecision":"deny",
#                              "permissionDecisionReason":"..."}}
#   - exit: always 0 (denial is communicated via JSON, not via exit code)
#
# Constraints (PRD/SDD):
#   - bash 3.2 compatible (no regex \s/\b; only POSIX glob via `case`).
#   - Performance budget ≤80ms p99: single env-var check + single `case` glob.
#   - Audit on deny via lib/audit_log.sh; audit failure must NEVER block.

set -euo pipefail

# Resolve plugin root (Claude Code sets CLAUDE_PLUGIN_ROOT; fall back for tests).
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# shellcheck source=/dev/null
. "${PLUGIN_ROOT}/scripts/lib/audit_log.sh"

INPUT=$(cat)

# `|| true` on each jq pipeline keeps a malformed-stdin parse error from
# tripping `set -e` on the command-substitution exit status. Mirrors the
# fail-open pattern in lib/audit_log.sh: empty TOOL/FILE_PATH → fall through
# the `case` blocks → exit 0. This is critical: a non-zero exit from this
# hook would unconditionally block the underlying Edit/Write/NotebookEdit.
#
# Only Edit/Write/NotebookEdit carry a meaningful tool_input.file_path.
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || true)
case "$TOOL" in
  Edit|Write|NotebookEdit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || true)
[ -z "$FILE_PATH" ] && exit 0

# Match sensitive-path patterns. bash `case` glob — POSIX-clean, bash-3.2-safe.
# Order matters only for which `pattern` we record in the audit row; the deny
# decision is identical across branches.
PATTERN=""
case "$FILE_PATH" in
  */.githooks/.config)  PATTERN=".githooks/.config" ;;
  */.githooks/*)        PATTERN=".githooks/*" ;;
  */.git/config)        PATTERN=".git/config" ;;
  */.git/hooks/*)       PATTERN=".git/hooks/*" ;;
esac

# Not a sensitive path → allow silently.
[ -z "$PATTERN" ] && exit 0

# Setup-skill sentinel set to literal "1" → allow (ADR-11).
if [ "${TCS_GIT_HELPERS_SETUP_ACTIVE:-0}" = "1" ]; then
  exit 0
fi

# Deny. Audit first (best-effort; never blocks), then emit decision JSON.
# master=false: the audit-schema `master` flag distinguishes master-override
# consumption (CLAUDE_ALLOW_GIT_BAD_OPS) from granular env-var consumption.
# This hook's gate is a granular setup sentinel (TCS_GIT_HELPERS_SETUP_ACTIVE),
# not a master override — so master is always false on this row.
_audit_log \
  hook=protect-git-internals \
  env_var=TCS_GIT_HELPERS_SETUP_ACTIVE \
  master=false \
  command="<edit:>${FILE_PATH}" \
  pattern="$PATTERN" \
  tool_input_truncated=false || true

REASON="Refusing to ${TOOL} '${FILE_PATH}': edits to git-internal paths (matched ${PATTERN}) are blocked outside the setup skill. To allow during /tcs-git-helpers:setup, the skill exports TCS_GIT_HELPERS_SETUP_ACTIVE=1 in a bounded subshell (per ADR-11)."

jq -nc --arg reason "$REASON" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'

exit 0
