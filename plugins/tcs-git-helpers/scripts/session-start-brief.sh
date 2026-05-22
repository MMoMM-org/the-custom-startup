#!/usr/bin/env bash
# scripts/session-start-brief.sh
#
# tcs-git-helpers — SessionStart brief renderer (T3.2, M4).
#
# Emits a one-line branch-state brief to stderr on every SessionStart event.
# Pure bash 3.2. NO jq. NO gh. NO python. Reads only local git + TSV cache.
#
# Output format (SDD §UI Visualization Brief Layout):
#   [tcs-git-helpers] <branch> • <state> • <ahead/behind> • <stale-count> [• <staleness>] [• <suggestion>]
#
# Protected-branch prefix (main/master):
#   ⚠ [tcs-git-helpers] <branch> • ...
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
#   - stdout: empty (hook output goes to stderr)
#   - stderr: the brief line
#   - exit: always 0 (fail-open)
#
# shellcheck shell=bash

set -uo pipefail

# Idempotent guard (defensive; sources are rare in this file)
: "${CLAUDE_PLUGIN_DATA:=${HOME}/.claude/plugin-data}"

# Resolve script directory for relative lib sourcing.
_SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"

# Source cache library — exposes _read_stale_cache_tsv, _repo_hash, _stale_tsv_path, _cache_dir.
# Fail-open: if the lib is missing, we render with 0 stale-merged and continue.
# shellcheck source=lib/cache.sh
if [ -f "$_SCRIPT_DIR/lib/cache.sh" ]; then
  # shellcheck disable=SC1091
  source "$_SCRIPT_DIR/lib/cache.sh"
else
  # Minimal stub so the rest of the script doesn't error.
  _read_stale_cache_tsv() { return 0; }
  _stale_tsv_path()       { return 1; }
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
  printf '[tcs-git-helpers] <detached HEAD>\n' >&2
  exit 0
fi

# ----------------------------------------------------------------------
# 3. Protected-branch warning marker
# Hardcoded for v1: main, master.
# Future: read TCS_PROTECTED_BRANCHES from .githooks/.config.
# ----------------------------------------------------------------------

warn_prefix=""
case "$branch" in
  main|master)
    warn_prefix="⚠ "
    ;;
esac

# ----------------------------------------------------------------------
# 4. Working-tree state (git status --porcelain ~47ms)
# State grammar:
#   clean           — empty output
#   dirty (N modified) — N = line count of porcelain output
# ----------------------------------------------------------------------

porcelain="$(git status --porcelain 2>/dev/null || true)"
if [ -z "$porcelain" ]; then
  state_seg="clean"
else
  modified_count="$(printf '%s\n' "$porcelain" | wc -l | tr -d '[:space:]')"
  state_seg="dirty (${modified_count} modified)"
fi

# ----------------------------------------------------------------------
# 5. Ahead/behind vs upstream (git rev-list --left-right --count ~15ms)
# Grammar:
#   up to date      — both 0
#   N ahead         — ahead>0, behind=0
#   N behind        — ahead=0, behind>0
#   N ahead, M behind — both >0
#   no upstream     — command fails / no upstream configured
# ----------------------------------------------------------------------

counts="$(git rev-list --left-right --count '@{u}...HEAD' 2>/dev/null || true)"
if [ -z "$counts" ]; then
  ab_seg="no upstream"
else
  # rev-list emits "<behind><TAB><ahead>".
  # bash 3.2: use read with IFS=$'\t'.
  behind="${counts%%	*}"
  ahead="${counts##*	}"
  # Coerce to integer.
  behind="$(( behind + 0 ))"
  ahead="$(( ahead + 0 ))"

  if [ "$behind" -eq 0 ] && [ "$ahead" -eq 0 ]; then
    ab_seg="up to date"
  elif [ "$behind" -eq 0 ] && [ "$ahead" -gt 0 ]; then
    ab_seg="${ahead} ahead"
  elif [ "$behind" -gt 0 ] && [ "$ahead" -eq 0 ]; then
    ab_seg="${behind} behind"
  else
    ab_seg="${ahead} ahead, ${behind} behind"
  fi
fi

# ----------------------------------------------------------------------
# 6. Stale-merged count + staleness (TSV read ~3ms)
# ADR-4: parsed via grep/wc, no jq.
# Staleness: now - updated_iso > 24h → append "(cache Nh old)"
# ----------------------------------------------------------------------

stale_count=0
stale_rows="$(_read_stale_cache_tsv 2>/dev/null || true)"
if [ -n "$stale_rows" ]; then
  stale_count="$(printf '%s\n' "$stale_rows" | wc -l | tr -d '[:space:]')"
fi

# Build stale segment.
stale_seg="${stale_count} stale-merged"

# Check cache staleness (>24h since updated_iso header).
staleness_suffix=""
tsv_path="$(_stale_tsv_path 2>/dev/null || true)"
if [ -n "$tsv_path" ] && [ -r "$tsv_path" ]; then
  # Extract updated_iso from comment header: "# updated_iso=2026-05-09T14:23:11Z"
  updated_iso="$(grep -m1 '^# updated_iso=' "$tsv_path" 2>/dev/null | cut -d= -f2- || true)"

  if [ -n "$updated_iso" ]; then
    # Convert updated_iso to epoch seconds.
    # Try BSD date -j -u -f first (macOS), then GNU date -u -d.
    updated_epoch=""
    if updated_epoch="$(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$updated_iso" +%s 2>/dev/null)"; then
      :
    elif updated_epoch="$(date -u -d "$updated_iso" +%s 2>/dev/null)"; then
      :
    fi

    if [ -n "$updated_epoch" ]; then
      now_epoch="$(date +%s)"
      age_secs="$(( now_epoch - updated_epoch ))"
      age_hours="$(( age_secs / 3600 ))"
      if [ "$age_secs" -gt 86400 ]; then
        staleness_suffix=" (cache ${age_hours}h old)"
      fi
    fi
  fi
fi

stale_seg="${stale_seg}${staleness_suffix}"

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
# 9. Compose and emit the brief line
# ----------------------------------------------------------------------

brief="${warn_prefix}[tcs-git-helpers] ${branch} • ${state_seg} • ${ab_seg} • ${stale_seg}${cleanup_seg}${drift_seg}${setup_seg}"

printf '%s\n' "$brief" >&2

exit 0
