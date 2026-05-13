#!/bin/bash
# tcs-git-helpers: __HOOK_BUNDLE_VERSION__
# lib-bundle.sh — shared helper library for tcs-git-helpers installed hooks
#
# Sourced by the four installed hook files via relative path:
#   source "$(dirname "$0")/lib-bundle.sh"
#
# Rules (CON-7, CON-8, CON-9):
#   - Bash 3.2 compatible (no declare -A, no mapfile, no flock)
#   - STDOUT always silent — all diagnostics go to stderr
#   - Functions exit/return 0 unless explicitly signalling failure via
#     return code (_resolve_data_dir may return 1 on git failure)
#   - Safe to source under set -uo pipefail
#
# Public API:
#   _resolve_data_dir     — print the cache dir path; return 1 if not in a git repo
#   _emit_skip            — write one structured stderr line; return 0
#   _guard_gh             — return 0 if gh is available and authenticated
#   _guard_jq             — return 0 if jq is available
#
# Spec refs:
#   - SDD §Implementation Examples / hook resolves its data dir without env vars
#   - SDD §ADR-6 — structured single-line stderr messages
#   - SDD §CON-7, CON-8, CON-9

# ---------------------------------------------------------------------------
# _resolve_data_dir
#
# Print the absolute path to the cache directory where stale-branch files live.
# Respects an explicit CLAUDE_PLUGIN_DATA override (lets tests + power users
# redirect); otherwise derives the path deterministically from $HOME and the
# git repo basename.
#
# Returns:
#   0  — path printed to stdout
#   1  — not inside a git repository (nothing printed)
# ---------------------------------------------------------------------------

_resolve_data_dir() {
  # 1. User-explicit override wins (lets tests + power users redirect).
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    printf '%s/cache' "$CLAUDE_PLUGIN_DATA"
    return 0
  fi

  # 2. Derive deterministically from repo identity (the normal production path).
  local repo_path repo_name
  repo_path="$(git rev-parse --show-toplevel 2>/dev/null)" || return 1
  repo_name="$(basename "$repo_path")"
  printf '%s/.claude/plugins/data/tcs-git-helpers-%s/cache' "$HOME" "$repo_name"
}

# ---------------------------------------------------------------------------
# _emit_skip <action> <reason> <suggestion>
#
# Write one structured stderr line and return 0.
# Format (SDD ADR-6):
#   tcs-git-helpers: <action> skipped — <reason>. <suggestion>.
#
# STDOUT: nothing
# STDERR: exactly one line
# ---------------------------------------------------------------------------

_emit_skip() {
  local action="$1"
  local reason="$2"
  local suggestion="$3"
  printf 'tcs-git-helpers: %s skipped — %s. %s.\n' \
    "$action" "$reason" "$suggestion" >&2
}

# ---------------------------------------------------------------------------
# _guard_gh
#
# Return 0 if gh is installed; emit a skip message and return 1 if not.
# Callers pass the action name used in the skip message.
#
# Usage: _guard_gh <action> || return 0
# ---------------------------------------------------------------------------

_guard_gh() {
  local action="${1:-hook}"
  if ! command -v gh >/dev/null 2>&1; then
    _emit_skip "$action" \
      "gh CLI not installed" \
      "Install gh to enable stale-branch detection"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# _guard_jq
#
# Return 0 if jq is installed; emit a skip message and return 1 if not.
#
# Usage: _guard_jq <action> || return 0
# ---------------------------------------------------------------------------

_guard_jq() {
  local action="${1:-hook}"
  if ! command -v jq >/dev/null 2>&1; then
    _emit_skip "$action" \
      "jq not installed" \
      "Install jq to enable stale-branch detection"
    return 1
  fi
}
