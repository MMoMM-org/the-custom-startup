#!/usr/bin/env bash
# scripts/nudge-hook.sh — PostToolUse:Bash success-only soft nudges
#
# Fires advisory nudges to stderr after key git/gh operations succeed.
# Never blocks (always exit 0). Pure bash — ZERO git or gh invocations.
#
# Spec refs:
#   - PRD §Feature M9 (AC1-AC7) — trigger map + suppression rules
#   - SDD §Building Block View — nudge-hook component
#   - PRD OQ9  — 60s same-nudge dedup per repo
#   - PRD OQ10 — exit_status field availability + fallback
#
# Constraints (CON-1, CON-9):
#   - bash 3.2 macOS-compat (no declare -A, no mapfile, no ${var,,})
#   - POSIX ERE only: [[:space:]]+, [[:<:]]/[[:>:]] — NEVER \s/\b
#   - NO git, NO gh subprocess invocations
#   - jq IS used for stdin parsing but with set -uo pipefail (NOT -e)
#     and 2>/dev/null || echo "" on every jq command-substitution
#     (T2.1/T2.2/T2.3 all shipped the set -euo + jq fail-closed trap)
#
# Repo-hash strategy — Option A (no git call):
#   lib/cache.sh's _repo_hash() calls `git rev-parse --show-toplevel`
#   when invoked with no argument. To keep this hook git-free, we pass
#   $CLAUDE_PROJECT_DIR directly to _repo_hash() as its first argument;
#   the function accepts a path arg and hashes it without shelling to git.
#   $CLAUDE_PROJECT_DIR is always populated in Claude Code hook contexts
#   (per docs/ai/external/claude/hooks.md L55).
#
# Tie-break: at most ONE rule fires per invocation. The trigger map is
# evaluated top-to-bottom (verify-base first); the first match wins and
# we exit immediately after emitting. This is both predictable and cheap.

set -uo pipefail
# NOT set -e: pattern-match functions return 1 on no-match, which would
# abort the script under -e. Same rationale as block-bad-git-ops.sh.

# ---------------------------------------------------------------------------
# Read hook envelope (stdin JSON) — fail-open on malformed input
# ---------------------------------------------------------------------------
#
# || echo "" on every jq substitution: a jq parse failure would otherwise
# cause the assignment itself to fail under set -uo pipefail (exit_status
# of the command substitution propagates). Defense-in-depth against the
# T2.x fail-closed trap.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
[ -z "$CMD" ] && exit 0

# ---------------------------------------------------------------------------
# Exit-status suppression (PRD M9 AC6, PRD OQ10)
# ---------------------------------------------------------------------------
#
# Probe several field names; the exact name is unconfirmed at write-time
# (PRD OQ10). If the field is found AND non-zero → suppress nudge.
# If the field is missing entirely → fire anyway (per OQ10 fallback).

EXIT_STATUS=$(printf '%s' "$INPUT" | jq -r '
  .exit_status // .tool_response.exit_code // .tool_response.exit_status // .tool_response.status // empty
' 2>/dev/null || echo "")

if [ -n "$EXIT_STATUS" ] && [ "$EXIT_STATUS" != "0" ]; then
  exit 0  # failed command — suppress nudge (M9 AC6)
fi

# ---------------------------------------------------------------------------
# Source libs
# ---------------------------------------------------------------------------

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" && pwd)" || exit 0
# shellcheck source=./lib/pattern_match.sh disable=SC1091
. "$_LIB_DIR/pattern_match.sh"
# shellcheck source=./lib/cache.sh disable=SC1091
. "$_LIB_DIR/cache.sh"

# ---------------------------------------------------------------------------
# Repo-hash derivation (Option A — no git call)
# ---------------------------------------------------------------------------
#
# Pass $CLAUDE_PROJECT_DIR directly to _repo_hash so it hashes the path
# string without invoking `git rev-parse`. Falls back to $HOME if the env
# var is unset (edge-case in tests without CLAUDE_PROJECT_DIR).

_REPO_DIR="${CLAUDE_PROJECT_DIR:-${HOME}}"
_REPO_HASH=$(_repo_hash "$_REPO_DIR" 2>/dev/null || echo "unknown")
_CACHE_DIR=$(_cache_dir 2>/dev/null || echo "${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugin-data}/cache")

# ---------------------------------------------------------------------------
# Dedup helper
# ---------------------------------------------------------------------------
#
# _check_and_update_dedup <rule_key>
#   Returns 0 if the nudge should fire (either no prior sentinel or sentinel
#   is older than 60 seconds). As a side-effect, writes/refreshes the sentinel.
#   Returns 1 if the nudge was already fired within the last 60 seconds.
#
# Sentinel file: ${_CACHE_DIR}/<repo-hash>-nudge-<rule_key>
# Content: unix epoch (seconds) of last fire.

_check_and_update_dedup() {
  local rule="$1"
  local sentinel="${_CACHE_DIR}/${_REPO_HASH}-nudge-${rule}"
  local now
  now=$(date +%s)

  if [ -f "$sentinel" ]; then
    local last
    last=$(cat "$sentinel" 2>/dev/null || echo "0")
    # Validate: must be all digits.
    case "$last" in
      ''|*[!0-9]*) last=0 ;;
    esac
    if [ $((now - last)) -lt 60 ]; then
      return 1  # within 60s window — suppress (M9 AC7)
    fi
  fi

  # Write (or refresh) sentinel — create parent dir if needed.
  mkdir -p "$_CACHE_DIR" 2>/dev/null || true
  printf '%s\n' "$now" > "$sentinel" 2>/dev/null || true
  return 0
}

# ---------------------------------------------------------------------------
# Nudge emitter
# ---------------------------------------------------------------------------
#
# _emit_nudge <rule_key> <text> <ref_doc>
#   Checks dedup, then emits to stderr if the dedup window has passed.

_emit_nudge() {
  local rule="$1"
  local text="$2"
  local ref_doc="$3"
  local plugin_root="${CLAUDE_PLUGIN_ROOT:-}"

  _check_and_update_dedup "$rule" || return 0

  if [ -n "$plugin_root" ]; then
    printf 'tcs-git-helpers: %s — see %s/references/%s\n' \
      "$text" "$plugin_root" "$ref_doc" >&2
  else
    printf 'tcs-git-helpers: %s — see references/%s\n' \
      "$text" "$ref_doc" >&2
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Trigger map (PRD §Feature M9, 5 rules, first-match wins)
# ---------------------------------------------------------------------------
#
# Patterns use POSIX ERE only (_match_command from lib/pattern_match.sh).
# The full $CMD string is matched as a substring, so compound forms like
# `cd foo && git checkout -b x` are caught without tokenization.
#
# Rule ordering (tie-break comment):
#   verify-base is checked before verify-pr-title because `git push -u` and
#   `git checkout -b` could theoretically appear in the same compound
#   command; the new-branch signal is higher priority (user just created a
#   branch — verify base is the most urgent nudge). All other rules are
#   mutually exclusive in practice.

# AC1: git checkout -b <name> | git switch -c <name>
if _match_command "$CMD" 'git[[:space:]]+(checkout[[:space:]]+-b|switch[[:space:]]+-c)[[:space:]]+[^[:space:]]+'; then
  _emit_nudge "verify-base" \
    "new branch — verify the base is up-to-date before working" \
    "branch-lifecycle.md"
  exit 0
fi

# AC2a: gh pr create
if _match_command "$CMD" 'gh[[:space:]]+pr[[:space:]]+create[[:>:]]'; then
  _emit_nudge "verify-pr-title" \
    "confirm the PR title matches Conventional Commits (squash-merge implication)" \
    "pr-vs-commit-messages.md"
  exit 0
fi

# AC2b: git push -u <remote> <branch>  (first push — new PR signal)
if _match_command "$CMD" 'git[[:space:]]+push[[:space:]]+(.*[[:space:]]+)?-u[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+'; then
  _emit_nudge "verify-pr-title" \
    "confirm the PR title matches Conventional Commits (squash-merge implication)" \
    "pr-vs-commit-messages.md"
  exit 0
fi

# AC3: gh pr merge
if _match_command "$CMD" 'gh[[:space:]]+pr[[:space:]]+merge[[:>:]]'; then
  _emit_nudge "cleanup-after-merge" \
    "PR merged — run /tcs-git-helpers:status --cleanup to surface stale branches" \
    "stale-branch-cleanup.md"
  exit 0
fi

# AC4: git rebase (any variant)
if _match_command "$CMD" 'git[[:space:]]+rebase[[:>:]]'; then
  _emit_nudge "verify-history" \
    "rebase complete — verify history with git log --oneline -10" \
    "rebase-vs-merge.md"
  exit 0
fi

# AC5: git stash pop
if _match_command "$CMD" 'git[[:space:]]+stash[[:space:]]+pop[[:>:]]'; then
  _emit_nudge "verify-orig-cleanup" \
    "stash pop — verify .orig file cleanup" \
    "working-tree-hygiene.md"
  exit 0
fi

# No rule matched — silent exit (AC6 unrecognized command path).
exit 0
