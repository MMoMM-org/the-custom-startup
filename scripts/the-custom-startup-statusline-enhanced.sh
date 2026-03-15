#!/bin/bash
#
# The Custom Startup — Enhanced Statusline
#
# Two-line statusline with git info, context bar, token budget bar (via ccusage),
# OSC 8 hyperlinks, and session cost/duration.
#
# Configuration: ~/.config/the-agentic-startup/statusline-enhanced.toml
#                or <repo>/.claude/statusline-enhanced.toml  (per-repo override)
#
# Dependencies: jq, ccusage (bun x ccusage), git
# Input:        JSON from Claude Code via stdin
# Output:       Two formatted statusline lines with ANSI colors

set -euo pipefail

# ==============================================================================
# Constants
# ==============================================================================

readonly GLOBAL_CONFIG_DIR="$HOME/.config/the-agentic-startup"
readonly GLOBAL_CONFIG_FILE="$GLOBAL_CONFIG_DIR/statusline-enhanced.toml"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
readonly CYAN='\033[36m'
readonly GREEN='\033[32m'
readonly YELLOW='\033[33m'
readonly RED='\033[31m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

# ==============================================================================
# Configuration defaults
# ==============================================================================

cfg_plan="pro"
cfg_token_limit=""          # auto from plan if empty
cfg_token_limit_manual=""   # explicit override
cfg_context_warn=70
cfg_context_danger=90
cfg_token_warn=70
cfg_token_danger=90
cfg_ccusage_cache_ttl=60    # seconds
cfg_git_cache_ttl=15        # seconds
cfg_show_token_bar=true
cfg_show_context_bar=true
cfg_show_cost=false         # cost shown via token bar by default
cfg_show_duration=true
cfg_show_git=true
cfg_show_remote_url=true

# Plan token limits per 5-hour billing window (input + output tokens, no cache reads)
declare -A PLAN_TOKEN_LIMITS=(
  [pro]=44000
  [max5x]=88000
  [max20x]=220000
)

# ==============================================================================
# TOML parser (simple key=value, no arrays)
# ==============================================================================

toml_get() {
  local file="$1" key="$2" section="${3:-}"
  [[ ! -f "$file" ]] && return 1

  local in_section="" value=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    if [[ "$line" =~ ^\[([a-zA-Z0-9_.]+)\] ]]; then
      in_section="${BASH_REMATCH[1]}"
      continue
    fi

    if [[ "$line" =~ ^[[:space:]]*([a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]*=[[:space:]]*(.+)$ ]]; then
      local k="${BASH_REMATCH[1]}" v="${BASH_REMATCH[2]}"
      if [[ ( -z "$section" && -z "$in_section" ) || "$in_section" == "$section" ]]; then
        if [[ "$k" == "$key" ]]; then
          v="${v%%#*}"
          v="${v%"${v##*[![:space:]]}"}"
          v="${v#\"}" v="${v%\"}"
          echo "$v"
          return 0
        fi
      fi
    fi
  done < "$file"
  return 1
}

# ==============================================================================
# Config loading (global → per-repo override)
# ==============================================================================

load_config() {
  # Per-repo config overrides global: look for .claude/statusline-enhanced.toml
  # Walk up from current dir to find a .claude/ directory
  local repo_config=""
  local dir
  dir=$(pwd)
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/.claude/statusline-enhanced.toml" ]]; then
      repo_config="$dir/.claude/statusline-enhanced.toml"
      break
    fi
    dir="$(dirname "$dir")"
  done

  # Load from global config, then overlay repo config
  for config_file in "$GLOBAL_CONFIG_FILE" "$repo_config"; do
    [[ -z "$config_file" || ! -f "$config_file" ]] && continue

    local v
    v=$(toml_get "$config_file" "plan")             && cfg_plan="$v"
    v=$(toml_get "$config_file" "token_limit")      && cfg_token_limit_manual="$v"
    v=$(toml_get "$config_file" "ccusage_cache_ttl") && cfg_ccusage_cache_ttl="$v"
    v=$(toml_get "$config_file" "git_cache_ttl")    && cfg_git_cache_ttl="$v"
    v=$(toml_get "$config_file" "show_token_bar")   && cfg_show_token_bar="$v"
    v=$(toml_get "$config_file" "show_context_bar") && cfg_show_context_bar="$v"
    v=$(toml_get "$config_file" "show_cost")        && cfg_show_cost="$v"
    v=$(toml_get "$config_file" "show_duration")    && cfg_show_duration="$v"
    v=$(toml_get "$config_file" "show_git")         && cfg_show_git="$v"
    v=$(toml_get "$config_file" "show_remote_url")  && cfg_show_remote_url="$v"

    v=$(toml_get "$config_file" "warn"   "thresholds.context") && cfg_context_warn="$v"
    v=$(toml_get "$config_file" "danger" "thresholds.context") && cfg_context_danger="$v"
    v=$(toml_get "$config_file" "warn"   "thresholds.token")   && cfg_token_warn="$v"
    v=$(toml_get "$config_file" "danger" "thresholds.token")   && cfg_token_danger="$v"
  done

  # Resolve token limit: manual override → plan default
  if [[ -n "$cfg_token_limit_manual" ]]; then
    cfg_token_limit="$cfg_token_limit_manual"
  else
    cfg_token_limit="${PLAN_TOKEN_LIMITS[$cfg_plan]:-${PLAN_TOKEN_LIMITS[pro]}}"
  fi
}

# ==============================================================================
# Input parsing
# ==============================================================================

read_input() {
  IFS= read -r -d '' JSON_INPUT || true

  MODEL=$(echo "$JSON_INPUT"        | jq -r '.model.display_name // "?"')
  CURRENT_DIR=$(echo "$JSON_INPUT"  | jq -r '.workspace.current_dir // .cwd // ""')
  CTX_PCT=$(echo "$JSON_INPUT"      | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
  DURATION_MS=$(echo "$JSON_INPUT"  | jq -r '.cost.total_duration_ms // 0')
  SESSION_COST=$(echo "$JSON_INPUT" | jq -r '.cost.total_cost_usd // 0')
}

# ==============================================================================
# Cache helpers
# ==============================================================================

cache_is_stale() {
  local file="$1" max_age="$2"
  [[ ! -f "$file" ]] && return 0
  local mtime
  mtime=$(stat -f %m "$file" 2>/dev/null || stat -c %Y "$file" 2>/dev/null || echo 0)
  [[ $(( $(date +%s) - mtime )) -gt "$max_age" ]]
}

cache_key() {
  echo "$1" | cksum | cut -d' ' -f1
}

# ==============================================================================
# Git info (cached)
# ==============================================================================

load_git_info() {
  BRANCH="" STAGED=0 MODIFIED=0 REMOTEURL=""

  [[ "$cfg_show_git" != "true" ]] && return

  local cache_file="/tmp/tcs-statusline-git-$(cache_key "$CURRENT_DIR")"

  if cache_is_stale "$cache_file" "$cfg_git_cache_ttl"; then
    if git -C "$CURRENT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
      local branch staged modified remote remote_url repo_name
      branch=$(git -C "$CURRENT_DIR" branch --show-current 2>/dev/null || echo "HEAD")
      staged=$(git -C "$CURRENT_DIR" diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
      modified=$(git -C "$CURRENT_DIR" diff --numstat 2>/dev/null | wc -l | tr -d ' ')
      remote=$(git -C "$CURRENT_DIR" remote get-url origin 2>/dev/null \
        | sed 's/git@github.com:/https:\/\/github.com\//' \
        | sed 's/\.git$//' || echo "")
      repo_name=$(basename "$remote" 2>/dev/null || echo "")

      local osc_link=""
      if [[ -n "$remote" && "$cfg_show_remote_url" == "true" ]]; then
        # OSC 8 hyperlink: \e]8;;URL\aTEXT\e]8;;\a
        osc_link=$(printf '\e]8;;%s\a%s\e]8;;\a' "$remote" "$repo_name")
      fi

      printf '%s|%s|%s|%s\n' "$branch" "$staged" "$modified" "$osc_link" > "$cache_file"
    else
      printf '|||' > "$cache_file"
    fi
  fi

  IFS='|' read -r BRANCH STAGED MODIFIED REMOTEURL < "$cache_file"
}

# ==============================================================================
# ccusage token budget (cached)
# ==============================================================================

load_token_budget() {
  BLOCK_TOKENS=0 BLOCK_COST="0" TIME_LEFT="" TOKEN_PCT=0

  [[ "$cfg_show_token_bar" != "true" ]] && return

  local cache_file="/tmp/tcs-statusline-ccusage-$(cache_key "$CURRENT_DIR")"

  if cache_is_stale "$cache_file" "$cfg_ccusage_cache_ttl"; then
    local timeout_cmd=""
    command -v gtimeout > /dev/null 2>&1 && timeout_cmd="gtimeout 5"
    command -v timeout  > /dev/null 2>&1 && timeout_cmd="timeout 5"

    local blocks_json
    blocks_json=$($timeout_cmd bun x ccusage blocks --json 2>/dev/null || echo "")

    if [[ -n "$blocks_json" ]]; then
      # Active block: filter isActive==true, non-gap; take first match
      local active_block
      active_block=$(echo "$blocks_json" | jq -r \
        '[.blocks[] | select(.isActive == true and .isGap == false)] | .[0]' 2>/dev/null)

      if [[ -n "$active_block" && "$active_block" != "null" ]]; then
        # Token budget: inputTokens + outputTokens (excludes cache reads)
        local input_tokens output_tokens
        input_tokens=$(echo "$active_block" | jq -r '.tokenCounts.inputTokens // 0')
        output_tokens=$(echo "$active_block" | jq -r '.tokenCounts.outputTokens // 0')
        BLOCK_TOKENS=$(( input_tokens + output_tokens ))

        BLOCK_COST=$(echo "$active_block" | jq -r '.costUSD // 0')

        local remaining_mins
        remaining_mins=$(echo "$active_block" | jq -r '.projection.remainingMinutes // empty')
        if [[ -n "$remaining_mins" && "$remaining_mins" != "null" ]]; then
          local m
          m=$(printf '%.0f' "$remaining_mins" 2>/dev/null || echo 0)
          if [[ "$m" -ge 60 ]]; then
            TIME_LEFT="$(( m / 60 ))h $(( m % 60 ))m left"
          else
            TIME_LEFT="${m}m left"
          fi
        fi
      fi
    fi

    printf '%s|%s|%s\n' "$BLOCK_TOKENS" "$BLOCK_COST" "$TIME_LEFT" > "$cache_file"
  fi

  IFS='|' read -r BLOCK_TOKENS BLOCK_COST TIME_LEFT < "$cache_file"

  # Calculate percentage: used tokens / plan limit
  if [[ "$cfg_token_limit" -gt 0 && "$BLOCK_TOKENS" -ge 0 ]]; then
    TOKEN_PCT=$(( BLOCK_TOKENS * 100 / cfg_token_limit ))
    [[ "$TOKEN_PCT" -gt 100 ]] && TOKEN_PCT=100
  fi
}

# ==============================================================================
# Formatters
# ==============================================================================

format_duration() {
  local ms="$1"
  [[ -z "$ms" || "$ms" -eq 0 ]] && return
  local total_s=$(( ms / 1000 ))
  local h=$(( total_s / 3600 ))
  local m=$(( (total_s % 3600) / 60 ))
  local s=$(( total_s % 60 ))
  if   [[ "$h" -gt 0 && "$m" -gt 0 ]]; then echo "${h}h ${m}m"
  elif [[ "$h" -gt 0 ]];               then echo "${h}h"
  elif [[ "$m" -gt 0 ]];               then echo "${m}m ${s}s"
  else                                       echo "${s}s"
  fi
}

# Block bar: 10 chars, █ filled / ░ empty, color-coded
block_bar() {
  local pct="$1" warn="$2" danger="$3"
  local color="$GREEN"
  [[ "$pct" -ge "$warn" ]]   && color="$YELLOW"
  [[ "$pct" -ge "$danger" ]] && color="$RED"

  local filled=$(( pct / 10 ))
  local empty=$(( 10 - filled ))
  local bar
  bar=$(printf "%${filled}s" | tr ' ' '█')$(printf "%${empty}s" | tr ' ' '░')
  printf '%b%s%b' "$color" "$bar" "$RESET"
}

format_dirty() {
  local out=""
  [[ "${STAGED:-0}"    -gt 0 ]] && out+="${GREEN}+${STAGED}${RESET}"
  [[ "${MODIFIED:-0}"  -gt 0 ]] && out+="${YELLOW}~${MODIFIED}${RESET}"
  [[ -n "$out" ]] && echo " $out"
}

# ==============================================================================
# Output
# ==============================================================================

render() {
  local line1="" line2=""

  # ── Line 1: identity ────────────────────────────────────────────────────────
  line1+="${CYAN}[${MODEL}]${RESET}"

  # Directory (basename)
  local dir_name="${CURRENT_DIR##*/}"
  [[ -n "$dir_name" ]] && line1+=" | 📁 ${dir_name}"

  # Remote URL (OSC 8 hyperlink)
  if [[ "$cfg_show_git" == "true" && "$cfg_show_remote_url" == "true" && -n "$REMOTEURL" ]]; then
    line1+=" | ${YELLOW}🔗 ${REMOTEURL}${RESET}"
  fi

  # Branch + dirty indicator
  if [[ "$cfg_show_git" == "true" && -n "$BRANCH" ]]; then
    line1+=" | 🌿 ${BRANCH}$(format_dirty)"
  fi

  # ── Line 2: metrics ─────────────────────────────────────────────────────────

  # Context bar
  if [[ "$cfg_show_context_bar" == "true" ]]; then
    local ctx_bar
    ctx_bar=$(block_bar "$CTX_PCT" "$cfg_context_warn" "$cfg_context_danger")
    line2+="🧠 ${ctx_bar} ${CTX_PCT}%"
  fi

  # Duration
  if [[ "$cfg_show_duration" == "true" ]]; then
    local dur
    dur=$(format_duration "$DURATION_MS")
    [[ -n "$dur" ]] && line2+=" | ⏱ ${dur}"
  fi

  # Token budget bar
  if [[ "$cfg_show_token_bar" == "true" && "$BLOCK_TOKENS" -gt 0 ]]; then
    local tok_bar
    tok_bar=$(block_bar "$TOKEN_PCT" "$cfg_token_warn" "$cfg_token_danger")
    local cost_fmt
    cost_fmt=$(printf '$%.2f' "$BLOCK_COST" 2>/dev/null || echo '$0.00')
    line2+=" | 💰 ${tok_bar} ${TOKEN_PCT}% ${cost_fmt}"
    [[ -n "$TIME_LEFT" ]] && line2+=" | ⏳ ${TIME_LEFT}"
  fi

  # Optional: raw session cost (off by default, token bar subsumes this)
  if [[ "$cfg_show_cost" == "true" ]]; then
    local session_cost_fmt
    session_cost_fmt=$(printf '$%.2f' "$SESSION_COST" 2>/dev/null || echo '$0.00')
    line2+=" | session ${session_cost_fmt}"
  fi

  echo -e "$line1"
  [[ -n "$line2" ]] && echo -e "$line2"
}

# ==============================================================================
# Help
# ==============================================================================

show_help() {
  cat << EOF
The Custom Startup — Enhanced Statusline

Usage: the-custom-startup-statusline-enhanced.sh [--help]
Input: JSON from Claude Code via stdin

Config files (global → per-repo override):
  ~/.config/the-agentic-startup/statusline-enhanced.toml
  <repo>/.claude/statusline-enhanced.toml

Options:
  plan             = pro | max5x | max20x   (default: pro)
  token_limit      = <number>               (manual override, e.g. 44000)
  ccusage_cache_ttl = <seconds>             (default: 60)
  git_cache_ttl    = <seconds>              (default: 15)
  show_token_bar   = true | false
  show_context_bar = true | false
  show_cost        = true | false           (raw session cost, off by default)
  show_duration    = true | false
  show_git         = true | false
  show_remote_url  = true | false

  [thresholds.context]
  warn   = 70
  danger = 90

  [thresholds.token]
  warn   = 70
  danger = 90

Token budget bar:
  Tracks inputTokens + outputTokens in the active ccusage billing block.
  Pro plan limit:   ~44,000 tokens / 5h window
  Max 5x limit:     ~88,000 tokens / 5h window
  Max 20x limit:    ~220,000 tokens / 5h window
EOF
  exit 0
}

# ==============================================================================
# Main
# ==============================================================================

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help

load_config
read_input
load_git_info
load_token_budget
render
