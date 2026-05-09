#!/usr/bin/env bash
# shellcheck shell=bash
# scripts/lib/audit_log.sh — Append-only JSONL audit with size-based rotation.
#
# Spec refs:
#   - SDD §Audit Log Schema  (overrides.jsonl, field set, RFC3339 ts)
#   - ADR-7                  (1 MB rotation, .1/.2; older NOT auto-deleted)
#   - PRD M12 AC3-AC5        (one JSONL line per consumption; rotation;
#                              audit failure NEVER blocks the underlying hook)
#
# Public API:
#   _audit_log key=value [key=value ...]
#       Append one JSON object to ${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl.
#       Auto-fills `ts` (UTC RFC3339), `repo` (git toplevel), `branch`.
#       Caller-provided keys: hook, env_var, master, command, pattern,
#                              tool_input_truncated.
#       NEVER blocks the caller — failures are logged to stderr only.
#       Always returns 0.
#
# Constraints:
#   - bash 3.2 compatible (no `declare -A`, no `mapfile`, no `${var^^}`).
#   - Field order is FROZEN: ts, repo, branch, hook, env_var, master,
#     command, pattern, tool_input_truncated.
#   - Rotation chain caps at .3; no .4+ files ever created.

# Resolve the canonical audit-file path.
_audit_log_path() {
  local data_dir="${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugins/data/tcs-git-helpers}"
  printf '%s/audit/overrides.jsonl' "$data_dir"
}

# Portable file size in bytes. Returns 0 if the file is missing.
_audit_log_size() {
  local f="$1"
  [ -f "$f" ] || { printf '0'; return 0; }
  if stat -f%z "$f" 2>/dev/null; then
    return 0
  fi
  stat -c%s "$f" 2>/dev/null || printf '0'
}

# Rotate when size >= 1024000 bytes (1 MB threshold per ADR-7).
# Chain: .jsonl -> .1 -> .2 -> .3 (oldest). On rotation, the existing
# .3 is overwritten (i.e. removed before the cascade); no .4+ is ever
# produced. Failures are absorbed — caller must not block on rotation.
_rotate_if_oversized() {
  local f="$1"
  [ -f "$f" ] || return 0
  local size
  size="$(_audit_log_size "$f")"
  case "$size" in
    ''|*[!0-9]*) return 0 ;;
  esac
  if [ "$size" -lt 1024000 ]; then
    return 0
  fi
  [ -f "$f.3" ] && rm -f "$f.3" 2>/dev/null
  [ -f "$f.2" ] && mv "$f.2" "$f.3" 2>/dev/null
  [ -f "$f.1" ] && mv "$f.1" "$f.2" 2>/dev/null
  mv "$f" "$f.1" 2>/dev/null
  return 0
}

# Minimal JSON string escape: backslash and double-quote.
# Callers pre-truncate command/pattern to single-line ASCII (CON: 256 chars
# max per SDD §Audit Log Schema), so embedded newlines/CR are out of scope.
_audit_log_json_escape() {
  printf '%s' "$1" | LC_ALL=C sed -e 's|\\|\\\\|g' -e 's|"|\\"|g'
}

# Normalize bool-ish input to literal `true` or `false`.
_audit_log_normalize_bool() {
  case "$1" in
    true|1|TRUE|True|yes|YES) printf 'true' ;;
    *)                        printf 'false' ;;
  esac
}

# Build JSON via jq -c -n (preferred path).
_audit_log_build_jq() {
  local ts="$1" repo="$2" branch="$3" hook="$4" env_var="$5"
  local master="$6" command="$7" pattern="$8" trunc="$9"
  jq -c -n \
    --arg     ts                   "$ts" \
    --arg     repo                 "$repo" \
    --arg     branch               "$branch" \
    --arg     hook                 "$hook" \
    --arg     env_var              "$env_var" \
    --argjson master               "$master" \
    --arg     command              "$command" \
    --arg     pattern              "$pattern" \
    --argjson tool_input_truncated "$trunc" \
    '{ts:$ts,repo:$repo,branch:$branch,hook:$hook,env_var:$env_var,master:$master,command:$command,pattern:$pattern,tool_input_truncated:$tool_input_truncated}'
}

# Build JSON via printf-escape (fallback when jq is unavailable).
# Field order matches the canonical schema exactly.
_audit_log_build_printf() {
  local ts="$1" repo="$2" branch="$3" hook="$4" env_var="$5"
  local master="$6" command="$7" pattern="$8" trunc="$9"
  local ts_e repo_e branch_e hook_e env_e cmd_e pat_e
  ts_e="$(_audit_log_json_escape "$ts")"
  repo_e="$(_audit_log_json_escape "$repo")"
  branch_e="$(_audit_log_json_escape "$branch")"
  hook_e="$(_audit_log_json_escape "$hook")"
  env_e="$(_audit_log_json_escape "$env_var")"
  cmd_e="$(_audit_log_json_escape "$command")"
  pat_e="$(_audit_log_json_escape "$pattern")"
  printf '{"ts":"%s","repo":"%s","branch":"%s","hook":"%s","env_var":"%s","master":%s,"command":"%s","pattern":"%s","tool_input_truncated":%s}' \
    "$ts_e" "$repo_e" "$branch_e" "$hook_e" "$env_e" \
    "$master" "$cmd_e" "$pat_e" "$trunc"
}

# Public entry point. Always returns 0; emits stderr on any failure.
_audit_log() {
  local hook="" env_var="" master="false"
  local command="" pattern="" trunc="false"

  local kv key val
  for kv in "$@"; do
    key="${kv%%=*}"
    val="${kv#*=}"
    case "$key" in
      hook)                 hook="$val" ;;
      env_var)              env_var="$val" ;;
      master)               master="$(_audit_log_normalize_bool "$val")" ;;
      command)              command="$val" ;;
      pattern)              pattern="$val" ;;
      tool_input_truncated) trunc="$(_audit_log_normalize_bool "$val")" ;;
      *) ;; # unknown keys are silently dropped — caller bug, not ours
    esac
  done

  local ts repo branch
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
  [ -z "$ts" ] && ts="1970-01-01T00:00:00Z"
  repo="$(git rev-parse --show-toplevel 2>/dev/null)"
  [ -z "$repo" ] && repo="${PWD:-}"
  branch="$(git symbolic-ref --short HEAD 2>/dev/null)"
  [ -z "$branch" ] && branch="<detached>"

  local audit_file audit_dir
  audit_file="$(_audit_log_path)"
  audit_dir="${audit_file%/*}"

  if ! mkdir -p "$audit_dir" 2>/dev/null; then
    printf 'audit_log: cannot create audit dir %s — skipping write\n' \
      "$audit_dir" >&2
    return 0
  fi

  _rotate_if_oversized "$audit_file"

  local line=""
  if command -v jq >/dev/null 2>&1; then
    line="$(_audit_log_build_jq \
      "$ts" "$repo" "$branch" "$hook" "$env_var" \
      "$master" "$command" "$pattern" "$trunc" 2>/dev/null)"
  fi
  if [ -z "$line" ]; then
    line="$(_audit_log_build_printf \
      "$ts" "$repo" "$branch" "$hook" "$env_var" \
      "$master" "$command" "$pattern" "$trunc")"
  fi

  if ! printf '%s\n' "$line" >>"$audit_file" 2>/dev/null; then
    printf 'audit_log: failed to append to %s\n' "$audit_file" >&2
  fi

  return 0
}
