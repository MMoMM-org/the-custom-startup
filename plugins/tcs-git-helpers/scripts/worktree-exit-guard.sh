#!/usr/bin/env bash
# scripts/worktree-exit-guard.sh — PreToolUse:ExitWorktree four-check guard (M8).
#
# Spec refs:
#   - SDD §Building Block View (worktree-exit-guard component table row)
#   - SDD §Runtime View Secondary Flow (worktree-exit sequence diagram)
#   - SDD §Quality Requirements (PreToolUse:ExitWorktree p99 ≤500ms)
#   - PRD M8 AC1-AC3 (uncommitted/untracked/unmerged/unpushed; override single-shot)
#   - ADR-1 (PreToolUse:ExitWorktree is the blockable native event)
#   - EC1 (denial ≤15 lines, 4-part structure)
#   - EC2 (cascading denial — ALL matched checks in ONE response)
#
# Hook contract:
#   stdin:  JSON {"tool_name":"ExitWorktree","tool_input":{"worktree_path":"…"}}
#   stdout: deny  → {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#                     "permissionDecision":"deny","permissionDecisionReason":"…"}}
#           allow → empty (exit 0)
#   stderr: human-facing notes (override consumed, errors)
#
# Behavior:
#   Inspect the worktree at tool_input.worktree_path. Run four checks in
#   parallel; if ANY trip, deny — unless CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
#   is set, in which case the override is consumed single-shot per ADR-5
#   (5-second sentinel double-tap window).
#
# Constraints (CON-1, CON-9):
#   - bash 3.2 compatible (no `declare -A`, no `mapfile`, no `${var,,}`).
#   - All git invocations operate against the worktree path; we cd into it
#     once so the lib helpers (which use `git -C "$PWD"`) inspect the right tree.
#   - No `set -e` — individual checks are best-effort and must not abort
#     each other on transient git failures.
# shellcheck shell=bash

set -uo pipefail

# --------------------------------------------------------------------------
# Stdin parse (JSON via jq)
# --------------------------------------------------------------------------

INPUT="$(cat 2>/dev/null || true)"
[ -z "$INPUT" ] && exit 0

if ! command -v jq >/dev/null 2>&1; then
  # jq is a shared dependency for all PreToolUse hooks (audit_log,
  # block-bad-git-ops). Fail open silently when missing — better than
  # falsely denying a worktree exit.
  exit 0
fi

TOOL="$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)"
WORKTREE_PATH="$(printf '%s' "$INPUT" \
                   | jq -r '.tool_input.worktree_path // ""' 2>/dev/null)"

[ "$TOOL" = "ExitWorktree" ] || exit 0
[ -n "$WORKTREE_PATH" ]       || exit 0
[ -d "$WORKTREE_PATH" ]       || exit 0

# Confirm it's actually a git working tree before doing any git work.
if ! git -C "$WORKTREE_PATH" rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

# --------------------------------------------------------------------------
# Library load
# --------------------------------------------------------------------------

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$PLUGIN_ROOT" ]; then
  # Resolve from script location so the hook is also invokable directly
  # (e.g. by bats tests) when Claude Code env vars aren't set.
  PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# shellcheck source-path=SCRIPTDIR
# shellcheck source=./lib/git_state.sh
# shellcheck disable=SC1091
. "$PLUGIN_ROOT/scripts/lib/git_state.sh"
# shellcheck source=./lib/override.sh
# shellcheck disable=SC1091
. "$PLUGIN_ROOT/scripts/lib/override.sh"
# shellcheck source=./lib/audit_log.sh
# shellcheck disable=SC1091
. "$PLUGIN_ROOT/scripts/lib/audit_log.sh"

# Lib helpers operate on $PWD — point at the worktree.
cd "$WORKTREE_PATH" || exit 0

# --------------------------------------------------------------------------
# Four checks (cascading per EC2 — collect ALL, deny once with the summary)
# --------------------------------------------------------------------------

# Checks 1 + 2 share `git status --porcelain` output: lines starting with `??`
# are untracked (check 2); all other lines are tracked changes (check 1).
PORCELAIN="$(git status --porcelain 2>/dev/null || true)"

MODIFIED_COUNT=0
UNTRACKED_COUNT=0
MODIFIED_NAMES=""
UNTRACKED_NAMES=""

if [ -n "$PORCELAIN" ]; then
  # Heredoc keeps the loop in the current shell — bash 3.2 has no `lastpipe`,
  # so piping into `while` would discard increments to the counters.
  # Both branches strip the porcelain v1 3-char prefix ("XY ") via `${line:3}`
  # for consistency — works for both untracked ("?? path") and tracked
  # ("XY path") lines.
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    name="${line:3}"
    case "$line" in
      '??'*)
        UNTRACKED_COUNT=$((UNTRACKED_COUNT + 1))
        if [ -z "$UNTRACKED_NAMES" ]; then
          UNTRACKED_NAMES="$name"
        else
          UNTRACKED_NAMES="$UNTRACKED_NAMES, $name"
        fi
        ;;
      *)
        MODIFIED_COUNT=$((MODIFIED_COUNT + 1))
        if [ -z "$MODIFIED_NAMES" ]; then
          MODIFIED_NAMES="$name"
        else
          MODIFIED_NAMES="$MODIFIED_NAMES, $name"
        fi
        ;;
    esac
  done <<EOF
$PORCELAIN
EOF
fi

# Check 3: unmerged commits — `git cherry origin/<default> <branch>` with `+`.
DEFAULT_BRANCH="$(_detect_default_branch)"
BRANCH_REF="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"

UNMERGED_COUNT=0
UNMERGED_SHAS=""
if [ -n "$BRANCH_REF" ] \
   && git rev-parse --verify --quiet "refs/remotes/origin/$DEFAULT_BRANCH" \
        >/dev/null 2>&1; then
  CHERRY="$(git cherry "origin/$DEFAULT_BRANCH" "$BRANCH_REF" 2>/dev/null || true)"
  if [ -n "$CHERRY" ]; then
    while IFS= read -r line; do
      case "$line" in
        '+ '*)
          UNMERGED_COUNT=$((UNMERGED_COUNT + 1))
          sha="${line#+ }"
          short="${sha:0:7}"
          if [ -z "$UNMERGED_SHAS" ]; then
            UNMERGED_SHAS="$short"
          else
            UNMERGED_SHAS="$UNMERGED_SHAS, $short"
          fi
          ;;
      esac
    done <<EOF
$CHERRY
EOF
  fi
fi

# Check 4: unpushed commits — branch has commits not on its upstream tracking
# ref. We inline `git rev-list --left-right --count @{u}...HEAD` here rather
# than calling `_get_branch_state` because that helper also invokes
# `_get_pr_state` → `gh pr list` (a 5-second-timeout network call) which
# would blow the SDD §Quality Requirements ≤500ms p99 budget for this hook.
# `@{u}` resolves to the branch's upstream tracking ref; falls back to 0
# when no upstream is configured (detached HEAD, fresh local branch).
UNPUSHED_COUNT=0
counts="$(git rev-list --left-right --count '@{u}...HEAD' 2>/dev/null || true)"
if [ -n "$counts" ]; then
  # Output is "<behind>\t<ahead>" — only the ahead count matters here.
  read -r _behind _ahead <<EOF
$counts
EOF
  case "${_ahead:-}" in
    ''|*[!0-9]*) UNPUSHED_COUNT=0 ;;
    *)           UNPUSHED_COUNT="$((_ahead + 0))" ;;
  esac
fi

# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------

FAIL_TOTAL=$(( (MODIFIED_COUNT  > 0 ? 1 : 0) \
             + (UNTRACKED_COUNT > 0 ? 1 : 0) \
             + (UNMERGED_COUNT  > 0 ? 1 : 0) \
             + (UNPUSHED_COUNT  > 0 ? 1 : 0) ))

if [ "$FAIL_TOTAL" -eq 0 ]; then
  exit 0
fi

# Override hatch — single-shot with 5s sentinel (M12 + ADR-5). The lib
# emits its own stderr banner ("override consumed: …") AND writes the
# audit_log line; we add the human-facing "[OVERRIDE] consumed —
# worktree exit allowed once" line as the hook-specific signal Marcus
# expects to see for this rule.
if _check_and_consume_override "WORKTREE_EXIT_WITH_CHANGES"; then
  printf '[OVERRIDE] consumed — worktree exit allowed once\n' >&2
  exit 0
fi

# --------------------------------------------------------------------------
# Cascading denial — order: modified → untracked → unmerged → unpushed.
# Reason fits in ≤15 lines per EC1: 1 header + ≤4 bullets + 1 options line.
# --------------------------------------------------------------------------

REASON="Cannot exit worktree:"

if [ "$MODIFIED_COUNT" -gt 0 ]; then
  noun="files"; [ "$MODIFIED_COUNT" -eq 1 ] && noun="file"
  REASON="$REASON
  - $MODIFIED_COUNT modified $noun ($MODIFIED_NAMES)"
fi
if [ "$UNTRACKED_COUNT" -gt 0 ]; then
  noun="files"; [ "$UNTRACKED_COUNT" -eq 1 ] && noun="file"
  REASON="$REASON
  - $UNTRACKED_COUNT untracked $noun ($UNTRACKED_NAMES)"
fi
if [ "$UNMERGED_COUNT" -gt 0 ]; then
  noun="commits"; [ "$UNMERGED_COUNT" -eq 1 ] && noun="commit"
  REASON="$REASON
  - $UNMERGED_COUNT unmerged $noun ($UNMERGED_SHAS)"
fi
if [ "$UNPUSHED_COUNT" -gt 0 ]; then
  noun="commits"; [ "$UNPUSHED_COUNT" -eq 1 ] && noun="commit"
  REASON="$REASON
  - $UNPUSHED_COUNT unpushed $noun"
fi
REASON="$REASON
Options: commit & push, stash, OR set CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1"

# Emit JSON via jq; literal newlines in $REASON become \n in the output.
jq -c -n \
  --arg reason "$REASON" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'

exit 0
