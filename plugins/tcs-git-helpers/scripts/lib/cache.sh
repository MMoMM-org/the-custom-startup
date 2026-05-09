#!/usr/bin/env bash
#
# scripts/lib/cache.sh
#
# tcs-git-helpers — cache layer for stale-branch and PR-state caches,
# plus a PID-file lock without `flock` (POSIX-portable, bash 3.2 safe,
# macOS-friendly).
#
# Files (under ${CLAUDE_PLUGIN_DATA}/cache/):
#   <repo-hash>-stale-cache.tsv   Hot-path read by SessionStart (ADR-4).
#   <repo-hash>-stale-cache.json  Sibling consumed by /tcs-git-helpers:status --json.
#   <repo-hash>-pr-state.json     60s TTL push-state cache.
#   <repo-hash>.lock              PID:TIMESTAMP — reclaimed if PID dead or
#                                 timestamp older than 5 minutes.
#
# Spec: SDD §Cache Schemas; SDD §Data Storage Changes; ADR-4.
#
# Conventions:
#   - All writes: write to <file>.tmp, then `mv` (atomic on POSIX same-fs).
#   - Reads of missing OR corrupt files return empty with exit 0.
#   - Pure bash 3.2: no `declare -A`, no `mapfile`, no `flock`.

# ----------------------------------------------------------------------
# Path helpers
# ----------------------------------------------------------------------

_cache_dir() {
  local data_dir="${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugin-data}"
  printf '%s/cache' "$data_dir"
}

# Derive a repo-stable 12-char hex hash (SHA1 prefix of repo top-level path).
# When called without arguments, uses `git rev-parse --show-toplevel` from $PWD.
_repo_hash() {
  local repo_path="${1:-}"
  if [ -z "$repo_path" ]; then
    repo_path="$(git rev-parse --show-toplevel 2>/dev/null)" || return 1
  fi
  printf '%s' "$repo_path" | shasum 2>/dev/null | head -c 12
}

_stale_tsv_path() {
  local hash
  hash="$(_repo_hash)" || return 1
  printf '%s/%s-stale-cache.tsv' "$(_cache_dir)" "$hash"
}

_stale_json_path() {
  local hash
  hash="$(_repo_hash)" || return 1
  printf '%s/%s-stale-cache.json' "$(_cache_dir)" "$hash"
}

_pr_state_path() {
  local hash
  hash="$(_repo_hash)" || return 1
  printf '%s/%s-pr-state.json' "$(_cache_dir)" "$hash"
}

_lock_path() {
  local hash
  hash="$(_repo_hash)" || return 1
  printf '%s/%s.lock' "$(_cache_dir)" "$hash"
}

# ----------------------------------------------------------------------
# JSON helpers (no jq dep on the SessionStart hot-path)
# ----------------------------------------------------------------------

# Minimal JSON-string escape for the small set of inputs we emit (ISO
# timestamps, branch names, repo paths). Avoids pulling jq into hot paths.
_json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

# ----------------------------------------------------------------------
# Stale-branch cache (TSV body + comment header, JSON sibling)
# ----------------------------------------------------------------------

# Read the data rows of the stale cache TSV. Outputs body lines (no
# `#`-prefixed comment header) on stdout. Tolerates missing or corrupt
# files and never crashes.
_read_stale_cache_tsv() {
  local f
  f="$(_stale_tsv_path)" || return 0
  [ -r "$f" ] || return 0
  # Drop comments and blank lines; suppress any read errors on truncated files.
  grep -v '^#' "$f" 2>/dev/null | grep -v '^[[:space:]]*$' 2>/dev/null
  return 0
}

# Write the stale-branch cache (TSV + JSON sibling).
# Reads branch rows from stdin: TAB-separated:
#   branch_name<TAB>pr_number<TAB>merged_at_iso
# Args:
#   $1 updated_iso   RFC3339 UTC timestamp of this update
#   $2 repo_path     Absolute path to the repo top-level
#   $3 default_branch  e.g. "main" or "master"
_write_stale_cache() {
  local updated_iso="${1:-}"
  local repo_path="${2:-}"
  local default_branch="${3:-}"
  local dir tsv json hash
  hash="$(_repo_hash)" || return 1
  dir="$(_cache_dir)"
  tsv="$dir/${hash}-stale-cache.tsv"
  json="$dir/${hash}-stale-cache.json"

  mkdir -p "$dir" 2>/dev/null || return 1

  # Buffer stdin once so we can write both files.
  local body
  body="$(cat)"

  # --- TSV (atomic mv) ---
  {
    printf '# tcs-git-helpers stale cache v1\n'
    printf '# updated_iso=%s\n' "$updated_iso"
    printf '# repo_path=%s\n' "$repo_path"
    printf '# default_branch=%s\n' "$default_branch"
    if [ -n "$body" ]; then
      printf '%s\n' "$body"
    fi
  } > "${tsv}.tmp" && mv "${tsv}.tmp" "$tsv"

  # --- JSON sibling (atomic mv) ---
  _emit_stale_json "$updated_iso" "$repo_path" "$default_branch" "$body" \
    > "${json}.tmp" && mv "${json}.tmp" "$json"
}

# Build the stale-cache JSON sibling. Pure printf escaping (no jq dep).
_emit_stale_json() {
  local updated_iso="$1"
  local repo_path="$2"
  local default_branch="$3"
  local body="$4"
  local first=1
  local name pr_number merged_at

  printf '{\n'
  printf '  "version": 1,\n'
  printf '  "updated_iso": "%s",\n' "$(_json_escape "$updated_iso")"
  printf '  "repo_path": "%s",\n'   "$(_json_escape "$repo_path")"
  printf '  "default_branch": "%s",\n' "$(_json_escape "$default_branch")"
  printf '  "stale_branches": ['

  if [ -n "$body" ]; then
    while IFS=$'\t' read -r name pr_number merged_at; do
      [ -z "$name" ] && continue
      if [ "$first" -eq 1 ]; then
        printf '\n'
        first=0
      else
        printf ',\n'
      fi
      # pr_number must be a JSON number; default to 0 if blank/non-numeric.
      case "$pr_number" in
        ''|*[!0-9]*) pr_number=0 ;;
      esac
      printf '    {"name":"%s","pr_number":%s,"merged_at":"%s"}' \
        "$(_json_escape "$name")" \
        "$pr_number" \
        "$(_json_escape "$merged_at")"
    done <<EOF
$body
EOF
    if [ "$first" -eq 0 ]; then
      printf '\n  '
    fi
  fi
  printf ']\n'
  printf '}\n'
}

# ----------------------------------------------------------------------
# PR state cache (60s TTL)
# ----------------------------------------------------------------------

# Convert RFC3339 UTC ("2026-05-09T14:23:11Z") to epoch seconds.
# Tries BSD `date -j -u -f` first, then GNU `date -u -d`. Echoes nothing
# and returns non-zero on failure.
_iso_to_epoch() {
  local iso="$1"
  if date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$iso" +%s 2>/dev/null; then
    return 0
  fi
  date -u -d "$iso" +%s 2>/dev/null
}

# Read PR state for one branch from cache. Honors a 60s TTL via per-entry
# `checked_iso`. Outputs the bare state (e.g. "OPEN", "MERGED", "NO_PR")
# or empty on miss/expired/corrupt. Never crashes.
_read_pr_state_cache() {
  local branch="${1:-}"
  [ -n "$branch" ] || return 0

  local f
  f="$(_pr_state_path)" || return 0
  [ -r "$f" ] || return 0
  command -v jq >/dev/null 2>&1 || return 0

  # Validate JSON; bail to empty if corrupt.
  jq -e . "$f" >/dev/null 2>&1 || return 0

  local checked state now epoch
  checked="$(jq -r --arg b "$branch" '.branch_state[$b].checked_iso // empty' "$f" 2>/dev/null)"
  state="$(jq -r --arg b "$branch"   '.branch_state[$b].state       // empty' "$f" 2>/dev/null)"

  [ -n "$state" ]   || return 0
  [ -n "$checked" ] || return 0

  if epoch="$(_iso_to_epoch "$checked")"; then
    now="$(date +%s)"
    if [ $((now - epoch)) -lt 60 ]; then
      printf '%s' "$state"
    fi
  fi
  return 0
}

# Write/update PR state for one branch.
# Args: $1=branch, $2=state, $3=pr_number (optional, defaults to 0/omitted)
_write_pr_state_cache() {
  local branch="${1:-}"
  local state="${2:-}"
  local pr_number="${3:-0}"
  [ -n "$branch" ] || return 1
  [ -n "$state" ]  || return 1

  local dir f now_iso
  f="$(_pr_state_path)" || return 1
  dir="$(_cache_dir)"
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  mkdir -p "$dir" 2>/dev/null || return 1

  if command -v jq >/dev/null 2>&1; then
    local current
    if [ -r "$f" ] && jq -e . "$f" >/dev/null 2>&1; then
      current="$(cat "$f")"
    else
      current='{"version":1,"updated_iso":"","branch_state":{}}'
    fi
    printf '%s' "$current" \
      | jq --arg branch "$branch" \
           --arg state "$state" \
           --arg pr_number "$pr_number" \
           --arg now "$now_iso" \
           '.version = 1
            | .updated_iso = $now
            | .branch_state[$branch] = (
                { state: $state, checked_iso: $now }
                + (if (($pr_number|tonumber?) // 0) > 0
                   then { number: ($pr_number|tonumber) }
                   else {} end)
              )' > "${f}.tmp" 2>/dev/null \
      && mv "${f}.tmp" "$f"
  else
    # Fallback: write a minimal single-entry JSON. Acceptable for v1 since
    # downstream readers are jq-aware; this branch only matters when jq is
    # missing during fallback.
    {
      printf '{\n'
      printf '  "version": 1,\n'
      printf '  "updated_iso": "%s",\n' "$now_iso"
      printf '  "branch_state": {\n'
      printf '    "%s": {"state":"%s","checked_iso":"%s"' \
        "$(_json_escape "$branch")" \
        "$(_json_escape "$state")" \
        "$now_iso"
      case "$pr_number" in
        ''|*[!0-9]*) : ;;
        0) : ;;
        *) printf ',"number":%s' "$pr_number" ;;
      esac
      printf '}\n'
      printf '  }\n'
      printf '}\n'
    } > "${f}.tmp" && mv "${f}.tmp" "$f"
  fi
}

# ----------------------------------------------------------------------
# PID-file lock (no flock; kill -0 + 5min stale TTL)
# ----------------------------------------------------------------------

# Single non-blocking attempt. On miss, examines an existing lock and
# reclaims it iff PID is dead OR timestamp is older than 5 minutes.
# Returns 0 on success, non-zero if the lock is currently held by a live
# owner or contention raced us.
_try_acquire_lock_once() {
  local lock_file="$1"
  local now self_entry
  now="$(date +%s)"
  self_entry="$$:$now"

  # Atomic create using `set -C` (noclobber); ignore stderr from a race.
  if (set -C; printf '%s\n' "$self_entry" > "$lock_file") 2>/dev/null; then
    return 0
  fi

  # Lock exists; check staleness.
  local existing pid ts
  existing="$(cat "$lock_file" 2>/dev/null)" || return 1
  pid="${existing%%:*}"
  ts="${existing#*:}"
  ts="${ts%%[!0-9]*}"

  # Malformed lock content → reclaim.
  if [ -z "$pid" ] || [ -z "$ts" ]; then
    rm -f "$lock_file" 2>/dev/null
    return 1
  fi
  if ! [ "$pid" -eq "$pid" ] 2>/dev/null; then
    rm -f "$lock_file" 2>/dev/null
    return 1
  fi

  # Stale by liveness or 5-min TTL → reclaim; do NOT acquire here, let the
  # next iteration race-acquire so two contenders don't both succeed.
  if ! kill -0 "$pid" 2>/dev/null || [ $((now - ts)) -gt 300 ]; then
    rm -f "$lock_file" 2>/dev/null
  fi
  return 1
}

# Acquire the per-repo lock with a bounded wait.
# Args: $1=timeout_seconds (default 10).
# Polls every 100ms; returns 0 on acquire, non-zero on timeout.
_acquire_lock() {
  local timeout="${1:-10}"
  local lock_file
  lock_file="$(_lock_path)" || return 1
  mkdir -p "$(dirname "$lock_file")" 2>/dev/null || return 1

  local i=0
  local max=$((timeout * 10))
  [ "$max" -lt 1 ] && max=1
  while [ "$i" -lt "$max" ]; do
    if _try_acquire_lock_once "$lock_file"; then
      return 0
    fi
    sleep 0.1
    i=$((i + 1))
  done
  return 1
}

# Release the lock if (and only if) the current shell owns it.
# Idempotent — missing lock or foreign-owned lock is a silent no-op.
_release_lock() {
  local lock_file
  lock_file="$(_lock_path)" || return 0
  [ -f "$lock_file" ] || return 0
  local existing pid
  existing="$(cat "$lock_file" 2>/dev/null)" || return 0
  pid="${existing%%:*}"
  if [ "$pid" = "$$" ]; then
    rm -f "$lock_file" 2>/dev/null
  fi
  return 0
}
