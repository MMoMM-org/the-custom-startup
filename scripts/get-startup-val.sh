#!/bin/bash
# get-startup-val.sh — resolve a key from TCS startup.toml configuration
#
# Lookup chain (first match wins):
#   1. [tcs] section in .claude/startup.toml (repo-local)
#   2. [tcs] section in startup.toml found via CLAUDE.md @include chain
#   3. [tcs] section in ~/.claude/startup.toml (global)
#   4. Smart default derived from docs_base (for known dir keys)
#   5. [default] argument supplied by caller
#   6. Built-in fallback for known keys
#
# Usage: scripts/get-startup-val.sh <key> [default]
#   key     — TOML key name under [tcs] (e.g. docs_base, specs_dir, ideas_dir)
#   default — optional fallback if nothing else resolves
#
# Output: resolved value to stdout, exit 0 always
#
# Known keys and built-in fallbacks:
#   docs_base  → docs/XDD
#   specs_dir  → {docs_base}/specs
#   ideas_dir  → {docs_base}/ideas
#   adr_dir    → {docs_base}/adr
#   plans_dir  → {docs_base}/plans
#
# Bash 3.2 compatible (macOS default shell). No declare -A.

set -euo pipefail

KEY="${1:-}"
CALLER_DEFAULT="${2:-}"

if [ -z "$KEY" ]; then
  echo "Usage: get-startup-val.sh <key> [default]" >&2
  exit 1
fi

# ─── TOML parsing helpers ──────────────────────────────────────────────────

# _tcs_val <file> <key>
# Read a key from the [tcs] section of a TOML file.
# Returns value (without quotes) and exits 0, or returns nothing and exits 1.
_tcs_val() {
  local file="$1"
  local key="$2"
  [ -f "$file" ] || return 1

  local in_tcs=0
  local val=""
  while IFS= read -r line; do
    # Detect section headers
    case "$line" in
      "[tcs]")
        in_tcs=1
        continue
        ;;
      "["*)
        in_tcs=0
        continue
        ;;
    esac

    [ "$in_tcs" = "1" ] || continue

    # Match key = value (with optional spaces around =)
    case "$line" in
      "${key} ="*|"${key}="*)
        val="${line#*=}"        # strip up to and including first =
        val="${val#"${val%%[! ]*}"}"  # ltrim spaces
        val="${val%"${val##*[! ]}"}"  # rtrim spaces (bash 3.2 safe)
        val="${val#\"}" ; val="${val%\"}"  # strip double quotes
        val="${val#\'}" ; val="${val%\'}"  # strip single quotes
        printf '%s' "$val"
        return 0
        ;;
    esac
  done < "$file"

  return 1
}

# ─── CLAUDE.md @include chain ─────────────────────────────────────────────

# _include_toml
# Parse CLAUDE.md for @~/path lines. For each, check if startup.toml exists there.
# Returns the first matching toml path, or empty.
_include_toml() {
  local claude_md="$PWD/CLAUDE.md"
  [ -f "$claude_md" ] || return 0

  local line dir toml
  while IFS= read -r line; do
    # Match lines like: @~/some/path  or  @~/some/path/file.md
    case "$line" in
      "@~/"*)
        dir="${line#@}"
        # Expand ~ manually (bash 3.2: ${HOME})
        dir="${HOME}${dir#\~}"
        # Strip filename if present (keep directory)
        dir="$(dirname "$dir")"
        # If the line points at a directory directly, use it as-is
        [ -d "$dir" ] || dir="$(dirname "$dir")"
        toml="${dir}/startup.toml"
        if [ -f "$toml" ]; then
          printf '%s' "$toml"
          return 0
        fi
        ;;
    esac
  done < "$claude_md"

  return 0
}

# ─── Known-key default derivation ─────────────────────────────────────────

# _derived_default <key> <docs_base>
# Return a smart default for known dir keys based on docs_base.
_derived_default() {
  local key="$1"
  local base="$2"
  case "$key" in
    docs_base)  printf '%s' "$base" ;;
    specs_dir)  printf '%s' "${base}/specs" ;;
    ideas_dir)  printf '%s' "${base}/ideas" ;;
    adr_dir)    printf '%s' "${base}/adr" ;;
    plans_dir)  printf '%s' "${base}/plans" ;;
    *)          return 1 ;;
  esac
  return 0
}

# _builtin_base — hardcoded docs_base fallback
_builtin_base() {
  printf '%s' "docs/XDD"
}

# ─── Main resolution logic ─────────────────────────────────────────────────

main() {
  local val=""

  # 1. Repo-local .claude/startup.toml
  val=$(_tcs_val "$PWD/.claude/startup.toml" "$KEY") && {
    printf '%s\n' "$val"; return 0
  }

  # 2. CLAUDE.md @include chain
  local include_toml
  include_toml=$(_include_toml)
  if [ -n "$include_toml" ]; then
    val=$(_tcs_val "$include_toml" "$KEY") && {
      printf '%s\n' "$val"; return 0
    }
  fi

  # 3. Global ~/.claude/startup.toml
  val=$(_tcs_val "$HOME/.claude/startup.toml" "$KEY") && {
    printf '%s\n' "$val"; return 0
  }

  # 4. Smart default derived from docs_base (resolve base first via same chain)
  local base=""
  # Try to get docs_base from any toml in the chain
  base=$(_tcs_val "$PWD/.claude/startup.toml" "docs_base") \
    || { [ -n "$include_toml" ] && base=$(_tcs_val "$include_toml" "docs_base"); } \
    || base=$(_tcs_val "$HOME/.claude/startup.toml" "docs_base") \
    || base=$(_builtin_base)

  val=$(_derived_default "$KEY" "$base") && {
    printf '%s\n' "$val"; return 0
  }

  # 5. Caller-supplied default
  if [ -n "$CALLER_DEFAULT" ]; then
    printf '%s\n' "$CALLER_DEFAULT"; return 0
  fi

  # 6. Return empty (key not found, no fallback)
  return 0
}

main
