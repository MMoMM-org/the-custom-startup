#!/usr/bin/env bash
# scripts/session-start-brief.sh
#
# tcs-git-helpers — SessionStart brief renderer (T3.2, M4).
#
# Emits — only when there is something actionable — a JSON SessionStart hook
# response that surfaces a user-visible notice AND/OR Claude-only context.
# When nothing needs attention the script exits 0 silently (no stdout, no
# stderr). Pure bash 3.2. NO jq. NO gh. Reads only local git + TSV cache.
# python3 is used opportunistically for JSON encoding; a sed-based fallback
# covers environments without it.
#
# Actionable triggers (any one → emit):
#   - drift_seg   : installed hook banner version != plugin.json version
#   - patterns_seg: tcs-patterns reporter prints DRIFT for an installed pattern
#   - cleanup_seg : stale-merged branch count > 0
#   - setup_seg   : repo missing .githooks/
#
# Output shape (JSON on stdout, exit 0):
#   {
#     "systemMessage": "[tcs-git-helpers] <actionable bits>",   // user-visible (omitted when nothing user-actionable)
#     "hookSpecificOutput": {
#       "hookEventName": "SessionStart",
#       "additionalContext": "<user msg if any>\n<protected-branch nudge if on main/master>"
#     }
#   }
#
# Channel rationale (per Claude Code hooks docs, May 2026):
#   - Plain stdout on SessionStart → additionalContext (Claude only); never user-visible.
#   - JSON `systemMessage` → user-visible TUI notice.
#   - JSON `hookSpecificOutput.additionalContext` → Claude context.
# We use both so the user is informed AND Claude can act on the same info.
#
# Constraints:
#   CON-1/ADR-2: bash 3.2 compat — no declare -A, no mapfile, no \s/\b PCRE
#   CON-2: p99 < 300ms; hot path: 3 git calls + 1 TSV read + format
#   CON-4: fail-open — never block session; exit 0 always
#   ADR-4: TSV parsed via grep/wc/head (no jq)
#   AC4: NO gh invocations
#
# SessionStart hook contract:
#   - stdin: JSON event payload (ignored — no data needed)
#   - stdout: JSON object as documented above, OR empty when idle
#   - stderr: empty
#   - exit: always 0 (fail-open)
#
# shellcheck shell=bash

set -uo pipefail

# Resolve script directory for relative lib sourcing.
_SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"

# Source cache library — exposes _read_stale_cache_tsv (only function we
# still call after the v2.2.2 cleanup; _stale_tsv_path was used by the
# cache-age suffix that no longer ships).
# Fail-open: if the lib is missing, treat stale-count as 0 and continue.
# shellcheck source=lib/cache.sh
if [ -f "$_SCRIPT_DIR/lib/cache.sh" ]; then
  # shellcheck disable=SC1091
  source "$_SCRIPT_DIR/lib/cache.sh"
else
  _read_stale_cache_tsv() { return 0; }
fi

# Fail-open wrapper: any unexpected error exits 0 with no output.
trap 'exit 0' ERR

# ----------------------------------------------------------------------
# 1. Verify we are inside a git repository. Exit 0 silently if not.
# ----------------------------------------------------------------------

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

# ----------------------------------------------------------------------
# 2. Branch name (git symbolic-ref --short HEAD ~24ms)
# ----------------------------------------------------------------------

branch="$(git symbolic-ref --short HEAD 2>/dev/null || true)"
if [ -z "$branch" ]; then
  # Detached HEAD — emit minimal notice and bail.
  printf '[tcs-git-helpers] <detached HEAD>\n'
  exit 0
fi

# ----------------------------------------------------------------------
# 3-5. Historic info-only segments (warn_prefix, state_seg, ab_seg) were
# removed in v2.2.2 — they were rendered into a plain-stdout brief that
# never reached the user (SessionStart stdout goes to Claude only). The
# user-visible nudge for protected branches now lives in section 9b's
# additionalContext path. Working-tree state and ahead/behind status are
# already in Claude's gitStatus env, so duplicating them here added no
# value while costing ~62ms per session start.
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# 6. Stale-merged count (TSV read ~3ms). Used by section 7 to decide
# whether to surface a cleanup suggestion. The historic stale_seg/
# staleness_suffix rendering was dropped with the dead info segments
# above — the cache-age suffix never reached the user either, and the
# 0 stale-merged label is non-actionable noise.
# ADR-4: parsed via grep/wc, no jq.
# ----------------------------------------------------------------------

stale_count=0
stale_rows="$(_read_stale_cache_tsv 2>/dev/null || true)"
if [ -n "$stale_rows" ]; then
  stale_count="$(printf '%s\n' "$stale_rows" | wc -l | tr -d '[:space:]')"
fi

# ----------------------------------------------------------------------
# 7. Cleanup suggestion when stale-count > 0
# ----------------------------------------------------------------------

cleanup_seg=""
if [ "$stale_count" -gt 0 ]; then
  cleanup_seg=" • run /tcs-git-helpers:git-audit --cleanup"
fi

# ----------------------------------------------------------------------
# 8. Setup hint when .githooks/ absent (M4 AC5)
# ----------------------------------------------------------------------

setup_seg=""
repo_top="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$repo_top" ] && [ ! -d "$repo_top/.githooks" ]; then
  setup_seg=" • run /tcs-git-helpers:git-setup"
fi

# ----------------------------------------------------------------------
# 8b. Hook version drift hint when .githooks/ present
# Compares the version banner stamped into installed hooks (lines 1–3:
# "# tcs-git-helpers: vX.Y.Z") against the plugin's current .claude-plugin/
# plugin.json version. Fail-open: any missing/unreadable piece → silent skip.
# Mutually exclusive with setup_seg (one fires only when .githooks/ exists,
# the other only when it doesn't).
# ----------------------------------------------------------------------

drift_seg=""
if [ -n "$repo_top" ] && [ -d "$repo_top/.githooks" ]; then
  _manifest="$_SCRIPT_DIR/../.claude-plugin/plugin.json"
  if [ -r "$_manifest" ]; then
    want_version="$(grep -E '"version"[[:space:]]*:' "$_manifest" 2>/dev/null \
      | head -1 \
      | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' || true)"

    # Banner pattern is "# tcs-git-helpers: <version>" — historically documented
    # as "vX.Y.Z" but install_files.sh currently writes bare "X.Y.Z". Match both.
    found_version=""
    for _h in pre-commit pre-push commit-msg post-merge; do
      if [ -r "$repo_top/.githooks/$_h" ]; then
        _marker="$(head -3 "$repo_top/.githooks/$_h" 2>/dev/null \
          | grep -E '^#[[:space:]]*tcs-git-helpers:[[:space:]]*v?[0-9]' \
          | head -1 || true)"
        if [ -n "$_marker" ]; then
          _raw="${_marker##*:}"
          found_version="$(printf '%s' "$_raw" \
            | sed -E 's/^[[:space:]]*v?//;s/[[:space:]]*$//' || true)"
          break
        fi
      fi
    done

    if [ -n "$want_version" ] && [ -n "$found_version" ] \
       && [ "$found_version" != "$want_version" ]; then
      drift_seg=" • hooks v${found_version} → v${want_version}; run /tcs-git-helpers:git-setup --update"
    fi
  fi
fi

# ----------------------------------------------------------------------
# 8c. Pattern drift hint (spec-020 T4.3). tcs-patterns writes
# <repo>/.claude/skills/.tcs-patterns-manifest; its patterns_drift.py
# reports drift against the catalogue. This segment only reads that
# reporter's stdout — a one-way dependency through a documented contract.
# Silent unless the reporter prints at least one well-formed
# DRIFT:<pattern>:<installed>:<catalogue> line; OK, MISSING and UNKNOWN are
# suppressed. Fail-open: no manifest, no python3, no reporter (tcs-patterns
# absent or at 1.x), a non-zero exit, or a malformed line → silence.
# The manifest test comes first so a repo without patterns never pays for
# a Python start.
# ----------------------------------------------------------------------

# True when dotted numeric version $1 > $2, compared field by field (BSD
# sort has no -V). A missing or non-numeric field compares as 0.
_version_gt() {
  local a="$1" b="$2" fa fb
  while [ -n "$a" ] || [ -n "$b" ]; do
    fa="${a%%.*}"
    fb="${b%%.*}"
    case "$a" in *.*) a="${a#*.}" ;; *) a="" ;; esac
    case "$b" in *.*) b="${b#*.}" ;; *) b="" ;; esac
    case "$fa" in ''|*[!0-9]*) fa=0 ;; esac
    case "$fb" in ''|*[!0-9]*) fb=0 ;; esac
    if [ "$((10#$fa))" -gt "$((10#$fb))" ]; then return 0; fi
    if [ "$((10#$fa))" -lt "$((10#$fb))" ]; then return 1; fi
  done
  return 1
}

# Print the path of tcs-patterns' patterns_drift.py, resolved from this
# script's own location only (not installed_plugins.json, not
# CLAUDE_PLUGIN_ROOT). Repository/marketplace layout first, then the plugin
# cache layout, where the highest numeric version carrying the script wins.
# Prints nothing when no candidate exists.
_find_patterns_drift() {
  local cand ver best="" best_ver=""
  cand="$_SCRIPT_DIR/../../tcs-patterns/scripts/patterns_drift.py"
  if [ -f "$cand" ]; then
    printf '%s' "$cand"
    return 0
  fi
  for cand in "$_SCRIPT_DIR"/../../../tcs-patterns/*/scripts/patterns_drift.py; do
    [ -f "$cand" ] || continue
    ver="${cand%/scripts/patterns_drift.py}"
    ver="${ver##*/}"
    case "$ver" in ''|*[!0-9.]*) continue ;; esac
    if [ -z "$best" ] || _version_gt "$ver" "$best_ver"; then
      best="$cand"
      best_ver="$ver"
    fi
  done
  if [ -n "$best" ]; then
    printf '%s' "$best"
  fi
  return 0
}

patterns_seg=""
if [ -n "$repo_top" ] && [ -f "$repo_top/.claude/skills/.tcs-patterns-manifest" ] \
   && command -v python3 >/dev/null 2>&1; then
  _drift_py="$(_find_patterns_drift 2>/dev/null)" || _drift_py=""
  if [ -n "$_drift_py" ]; then
    _drift_out="$(python3 "$_drift_py" "$repo_top" 2>/dev/null)" || _drift_out=""
    _drift_list=""
    while IFS=: read -r _kind _pat _inst _cat _rest; do
      [ "$_kind" = "DRIFT" ] && [ -z "$_rest" ] || continue
      case "$_pat" in ''|*[!a-z0-9-]*) continue ;; esac
      case "$_inst" in ''|*[!0-9]*) continue ;; esac
      case "$_cat" in ''|*[!0-9]*) continue ;; esac
      _drift_list="${_drift_list:+${_drift_list}, }${_pat} v${_inst} → v${_cat}"
    done <<< "$_drift_out"
    if [ -n "$_drift_list" ]; then
      patterns_seg=" • patterns ${_drift_list}; run /tcs-patterns:patterns-setup update"
    fi
  fi
fi

# ----------------------------------------------------------------------
# 9. Compose user_msg (systemMessage) and ctx_msg (additionalContext)
# Silent exit when neither is needed.
# ----------------------------------------------------------------------

# 9a. User-actionable bits = cleanup / hook drift / pattern drift / setup.
# Each segment already starts with " • "; strip the leading " • " of the
# first one and the rest read naturally.
actionable_segs="${cleanup_seg}${drift_seg}${patterns_seg}${setup_seg}"
user_msg=""
if [ -n "$actionable_segs" ]; then
  # ${var# • } strips a single leading " • "; bash 3.2 compatible.
  user_msg="[tcs-git-helpers] ${actionable_segs# • }"
fi

# 9b. Claude context = user message (when any) + protected-branch nudge.
ctx_msg=""
if [ -n "$user_msg" ]; then
  ctx_msg="$user_msg"
fi
case "$branch" in
  main|master)
    nudge="[tcs-git-helpers] On protected branch '${branch}': do not create or edit non-gitignored files here. Switch to a feature branch before any Write/Edit."
    if [ -n "$ctx_msg" ]; then
      ctx_msg="${ctx_msg}
${nudge}"
    else
      ctx_msg="$nudge"
    fi
    ;;
esac

# 9c. Silent when nothing to say.
if [ -z "$user_msg" ] && [ -z "$ctx_msg" ]; then
  exit 0
fi

# 9d. JSON-encode strings. Prefer python3; fall back to a sed-based escape
# that covers backslash, double-quote, newline, and tab (sufficient for our
# content — segments are plain ASCII + the • bullet, the nudge has \n).
_json_escape() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$1" | python3 -c 'import json,sys;sys.stdout.write(json.dumps(sys.stdin.read()))'
    return
  fi
  # Fallback: escape backslash, dquote, then convert newlines/tabs to escapes.
  _esc="$(printf '%s' "$1" \
    | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' \
    | awk 'BEGIN{ORS=""} NR>1{print "\\n"} {print}' \
    | sed -e $'s/\t/\\\\t/g')"
  printf '"%s"' "$_esc"
}

# 9e. Emit JSON. Build the parts list to omit empty fields cleanly.
_json_parts=""
if [ -n "$user_msg" ]; then
  _json_parts="\"systemMessage\":$(_json_escape "$user_msg")"
fi
if [ -n "$ctx_msg" ]; then
  _hso="\"hookEventName\":\"SessionStart\",\"additionalContext\":$(_json_escape "$ctx_msg")"
  if [ -n "$_json_parts" ]; then
    _json_parts="${_json_parts},\"hookSpecificOutput\":{${_hso}}"
  else
    _json_parts="\"hookSpecificOutput\":{${_hso}}"
  fi
fi

printf '{%s}\n' "$_json_parts"

exit 0
