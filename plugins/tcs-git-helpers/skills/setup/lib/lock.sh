#!/usr/bin/env bash
# tcs-git-helpers: v1.0.0
# skills/setup/lib/lock.sh — PID-file lock for /tcs-git-helpers:setup.
#
# Uses the repo's .githooks/.setup.lock (NOT the plugin-data lock under
# ${CLAUDE_PLUGIN_DATA}/cache) so two concurrent setup runs against the same
# repo serialize even when the plugin-data dir is per-user.
#
# Spec refs:
#   - PRD M10 AC4 (concurrent setup; 5min stale reclaim)
#   - SDD §Building Block View — setup/SKILL.md "Lock-file serialized"
#   - ADR-10 / EC3 (idempotency on Ctrl-C; reclaim by liveness or 5min TTL)
#
# Lock file format (one line):
#   <pid>:<unix-timestamp>
#
# CLI:
#   lock.sh acquire   # exits 0 on success, non-zero on contention/timeout
#   lock.sh release   # idempotent; only removes the lock if we own it
#
# Env knobs:
#   TCS_LOCK_TIMEOUT  Bounded wait in seconds when acquiring (default 10).
#
# Constraints:
#   - bash 3.2 (no flock; uses set -C noclobber for atomic create)
#   - macOS-friendly (no GNU coreutils dep)

set -euo pipefail

_lock_dir() {
  # Resolve the repo top-level; fall back to $PWD if not in a git repo so the
  # caller still gets a deterministic location for the contract test.
  local top
  if top="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    printf '%s/.githooks' "$top"
  else
    printf '%s/.githooks' "$PWD"
  fi
}

_lock_path() {
  printf '%s/.setup.lock' "$(_lock_dir)"
}

_try_acquire_once() {
  local lock_file="$1"
  local now self_entry
  now="$(date +%s)"
  self_entry="$$:$now"

  if (set -C; printf '%s\n' "$self_entry" > "$lock_file") 2>/dev/null; then
    return 0
  fi

  local existing pid ts
  existing="$(cat "$lock_file" 2>/dev/null)" || return 1
  pid="${existing%%:*}"
  ts="${existing#*:}"
  ts="${ts%%[!0-9]*}"

  if [ -z "$pid" ] || [ -z "$ts" ]; then
    rm -f "$lock_file" 2>/dev/null
    return 1
  fi
  if ! [ "$pid" -eq "$pid" ] 2>/dev/null; then
    rm -f "$lock_file" 2>/dev/null
    return 1
  fi

  # Stale by liveness OR 5-minute TTL → reclaim. Don't acquire here; let the
  # next iteration race-create cleanly so two contenders don't both succeed.
  if ! kill -0 "$pid" 2>/dev/null || [ $((now - ts)) -gt 300 ]; then
    rm -f "$lock_file" 2>/dev/null
  fi
  return 1
}

_acquire() {
  local lock_file
  lock_file="$(_lock_path)"
  mkdir -p "$(dirname "$lock_file")" 2>/dev/null || {
    printf '[tcs-git-helpers:setup] ERROR: cannot create %s\n' "$(dirname "$lock_file")" >&2
    return 1
  }

  local timeout="${TCS_LOCK_TIMEOUT:-10}"
  local max=$((timeout * 10))
  [ "$max" -lt 1 ] && max=1
  local i=0
  while [ "$i" -lt "$max" ]; do
    if _try_acquire_once "$lock_file"; then
      return 0
    fi
    sleep 0.1
    i=$((i + 1))
  done
  printf '[tcs-git-helpers:setup] ERROR: another setup run holds %s\n' "$lock_file" >&2
  return 1
}

_release() {
  local lock_file
  lock_file="$(_lock_path)"
  [ -f "$lock_file" ] || return 0
  local existing pid
  existing="$(cat "$lock_file" 2>/dev/null)" || return 0
  pid="${existing%%:*}"
  if [ "$pid" = "$$" ]; then
    rm -f "$lock_file" 2>/dev/null
  fi
  return 0
}

case "${1:-}" in
  acquire) _acquire ;;
  release) _release ;;
  path)    _lock_path ;;
  *)
    printf 'usage: %s {acquire|release|path}\n' "$0" >&2
    exit 2
    ;;
esac
