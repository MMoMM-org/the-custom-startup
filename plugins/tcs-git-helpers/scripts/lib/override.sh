#!/usr/bin/env bash
# shellcheck shell=bash
# scripts/lib/override.sh — Single-shot env-var override consumption with a
# 5-second sentinel double-tap window.
#
# Spec refs:
#   - SDD §Implementation Examples (`_check_and_consume_override` walkthrough)
#   - ADR-5 (env-var consumption + 5s sentinel approximates true single-shot)
#   - PRD M7 AC3 (master override emits loud stderr warning)
#   - PRD M12 AC1-AC5 (single-shot semantics + audit trail; audit failure
#                       does NOT block the underlying hook decision)
#
# Public API:
#   _check_and_consume_override <rule>
#       Where <rule> is the rule name (e.g., RESET_HARD).
#         1. If `CLAUDE_ALLOW_<rule>` is "1": consume the granular override.
#         2. Otherwise if `CLAUDE_ALLOW_GIT_BAD_OPS` is "1": consume the
#            master override (emits a loud stderr warning per M7 AC3).
#         3. Otherwise: return 1 (no override active).
#
#       On consumption: writes a 5-second sentinel under
#         ${CLAUDE_PLUGIN_DATA}/cache/override-consumed-<env_var>
#       atomically (write-tmp + mv), emits an audit_log line, prints
#       "override consumed: <env_var>" to stderr, sets globals
#       OVERRIDE_VAR / OVERRIDE_MASTER, unsets the env-var in the current
#       process, and returns 0.
#
#       If the same env-var was consumed within the last 5 seconds (sentinel
#       file exists with a recent epoch), the call returns 1 and prints a
#       "denying as double-tap" stderr line. No new audit line is written.
#
# Globals exposed (set on every successful consumption; reset on entry):
#   OVERRIDE_VAR     — env-var name that was consumed (e.g.,
#                      CLAUDE_ALLOW_RESET_HARD, CLAUDE_ALLOW_GIT_BAD_OPS)
#   OVERRIDE_MASTER  — "1" iff the master switch was consumed, else "0"
#
# Constraints:
#   - bash 3.2 compatible (no `declare -A`, no `mapfile`, no `${var,,}`).
#   - Sentinel write is atomic: write to .tmp, then `mv`.
#   - mkdir failure on the sentinel directory MUST NOT block consumption —
#     it degrades double-tap protection gracefully (CON: graceful degradation
#     over false-deny, per SDD §Error Handling and plan T1.6 constraint).
#   - audit_log failure (or audit_log.sh not sourced) MUST NOT block
#     consumption (M12 AC5). audit_log.sh is consumed via a
#     `command -v _audit_log` guard so override.sh stays non-blocking when
#     the audit lib isn't sourced or the call fails — defense-in-depth on
#     top of `_audit_log`'s own always-return-0 contract.

# Source cache.sh for `_cache_dir` so the cache directory layout is owned
# in exactly one place (DRY). Re-sourcing is harmless: cache.sh defines
# functions only, with no side effects at source time.
_OVERRIDE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=./cache.sh
# shellcheck disable=SC1091
. "$_OVERRIDE_LIB_DIR/cache.sh"

# Resolve the sentinel path for a given env-var name. Lives under the
# canonical cache directory from cache.sh.
_override_sentinel_path() {
  local env_var="$1"
  printf '%s/override-consumed-%s' "$(_cache_dir)" "$env_var"
}

# Scan the CMD global variable for a recognized single-shot override prefix.
#
# Usage: _scan_tool_input_for_override <env_var>
#   env_var — the exact CLAUDE_ALLOW_<RULE> or CLAUDE_ALLOW_GIT_BAD_OPS name.
#
# Returns:
#   0 — "<env_var>=1<whitespace>+" is the first token, optionally after a single
#       leading `cd <path> &&|;|<newline>` / `pushd <path> …` directory-change
#       prefix (the Claude Code Bash tool's default command shapes — see #42 for
#       the `&&`/`;` forms and the newline-separated multi-line form).
#   1 — CMD is unset, empty, or the prefix is absent / mid-command.
#
# Side effects: none. No I/O. Caller handles sentinel + audit (CON-5).
# Bash 3.2 compatible: uses [[ =~ ]] with a variable-held pattern (CON-1).
_scan_tool_input_for_override() {
  local env_var="$1"
  [ -z "${CMD:-}" ] && return 1
  # Flatten newlines to `;` first: `sed` is line-oriented and bash `=~` anchors
  # `^` to string start, so neither can bridge a `cd <path>⏎override` shape on
  # its own. A newline is a statement separator semantically identical to `;`,
  # and we only mutate this scan copy (never the executed command), so the
  # rewrite is safe and keeps `cd <path>⏎override` equivalent to `cd <path>; …`.
  # Then strip one leading `cd|pushd <args> &&|;` so an override placed first
  # *after* the harness's directory change still counts as the first token
  # (#42). Only a single benign cd/pushd is tolerated — anything else keeps the
  # position-0 rule (a second command before the override is NOT stripped).
  local scan
  scan="$(printf '%s' "$CMD" | tr '\n' ';' | sed -E 's/^[[:space:]]*(cd|pushd)[[:space:]]+[^&;]*(&&|;)[[:space:]]*//')"
  local pattern="^${env_var}=1[[:space:]]+"
  [[ "$scan" =~ $pattern ]] && return 0
  return 1
}

# Public entry point. Returns 0 on consumption, 1 otherwise.
_check_and_consume_override() {
  local rule="${1:-}"
  if [ -z "$rule" ]; then
    return 1
  fi

  local env_var="CLAUDE_ALLOW_${rule}"
  local master_var="CLAUDE_ALLOW_GIT_BAD_OPS"

  # Reset globals every entry — callers may inspect them after a no-override
  # return (and we don't want stale state from a prior consume to leak).
  OVERRIDE_VAR=""
  OVERRIDE_MASTER="0"

  # Resolve which override (if any) is active. Granular wins over master
  # per M12 §Edge Cases ("Master + granular both set: granular wins").
  # `${!var:-0}` is bash 2.0+ indirect expansion — supported on bash 3.2.
  local _scan_path=0
  if [ "${!env_var:-0}" = "1" ]; then
    OVERRIDE_VAR="$env_var"
    OVERRIDE_MASTER="0"
  elif [ "${!master_var:-0}" = "1" ]; then
    OVERRIDE_VAR="$master_var"
    OVERRIDE_MASTER="1"
  else
    # M2: env-var path found nothing — scan CMD for inline prefix (ADR-2).
    # Granular scan first (granular wins over master per M12 §Edge Cases).
    if _scan_tool_input_for_override "$env_var"; then
      OVERRIDE_VAR="$env_var"
      OVERRIDE_MASTER="0"
      _scan_path=1
    elif _scan_tool_input_for_override "$master_var"; then
      OVERRIDE_VAR="$master_var"
      OVERRIDE_MASTER="1"
      _scan_path=1
    else
      return 1
    fi
  fi

  # 5-second double-tap window: if a sentinel exists with an epoch within
  # 5s of `now`, refuse to re-consume. Sentinel content is a unix epoch
  # written by a prior successful consumption.
  local sentinel sentinel_ts now
  sentinel="$(_override_sentinel_path "$OVERRIDE_VAR")"
  if [ -f "$sentinel" ]; then
    sentinel_ts="$(cat "$sentinel" 2>/dev/null)"
    case "$sentinel_ts" in
      ''|*[!0-9]*) sentinel_ts=0 ;;
    esac
    now="$(date +%s)"
    if [ $((now - sentinel_ts)) -lt 5 ]; then
      printf 'tcs-git-helpers: %s consumed <5s ago — denying as double-tap\n' \
        "$OVERRIDE_VAR" >&2
      return 1
    fi
  fi

  # Consume: write sentinel atomically. Failure to mkdir/write the sentinel
  # MUST NOT block the consumption — we only lose double-tap protection.
  local sentinel_dir="${sentinel%/*}"
  if mkdir -p "$sentinel_dir" 2>/dev/null; then
    local now_ts
    now_ts="$(date +%s)"
    if { printf '%s\n' "$now_ts" > "${sentinel}.tmp"; } 2>/dev/null; then
      mv "${sentinel}.tmp" "$sentinel" 2>/dev/null \
        || rm -f "${sentinel}.tmp" 2>/dev/null
    fi
  else
    printf 'tcs-git-helpers: cannot create %s — double-tap protection degraded\n' \
      "$sentinel_dir" >&2
  fi

  # Audit. M12 AC5: audit-write failure NEVER blocks the underlying hook
  # decision. _audit_log itself is built to return 0 on failure, but we
  # also guard against the symbol not being defined (caller forgot to
  # source audit_log.sh) and against any unexpected non-zero exit.
  if command -v _audit_log >/dev/null 2>&1; then
    local master_field="false"
    if [ "$OVERRIDE_MASTER" = "1" ]; then
      master_field="true"
    fi
    if [ "$_scan_path" = "1" ]; then
      _audit_log env_var="$OVERRIDE_VAR" master="$master_field" \
        tool_input_truncated="1" \
        >/dev/null 2>&1 || true
    else
      _audit_log env_var="$OVERRIDE_VAR" master="$master_field" \
        >/dev/null 2>&1 || true
    fi
  fi

  if [ "$OVERRIDE_MASTER" = "1" ]; then
    # PRD M7 AC3 verbatim — the backticks around `CLAUDE_ALLOW_<X>=1` ARE
    # part of the contract, not markdown. Single-quoted format keeps them
    # literal (backticks would otherwise be command substitution).
    # shellcheck disable=SC2016  # backticks are intentionally LITERAL output
    printf '⚠ MASTER OVERRIDE — strongly prefer granular `CLAUDE_ALLOW_<X>=1`\n' >&2
  fi
  printf 'tcs-git-helpers: override consumed: %s\n' "$OVERRIDE_VAR" >&2

  # Unset env-var in current process scope per M12 user-flow step 4.
  # Safe even if it's already gone or read-only — `|| true` swallows.
  unset "$OVERRIDE_VAR" 2>/dev/null || true

  return 0
}
