#!/usr/bin/env bash
#
# The Custom Startup — Enhanced Statusline
#
# Two-line statusline with git info, context bar, token budget bar (via ccusage),
# OSC 8 hyperlinks, and session cost/duration.
#
# Configuration: ~/.config/the-agentic-startup/statusline.toml
#                or <repo>/.claude/statusline.toml  (per-repo override)
#
# Dependencies: jq, ccusage (bun x ccusage), git
# Input:        JSON from Claude Code via stdin
# Output:       Two formatted statusline lines with ANSI colors

# ==============================================================================
# Shared library
# ==============================================================================

source "$(dirname "${BASH_SOURCE[0]}")/the-custom-startup-statusline-lib.sh"

# ==============================================================================
# Input parsing
# ==============================================================================

read_input() {
  IFS= read -r -d '' JSON_INPUT || true

  MODEL=$(echo "$JSON_INPUT"        | jq -r '.model.display_name // "?"')
  CURRENT_DIR=$(echo "$JSON_INPUT"  | jq -r '.workspace.current_dir // .cwd // ""')
  CTX_PCT=$(tcs_round_int \
    "$(echo "$JSON_INPUT" | jq -r '.context_window.used_percentage // 0')") || CTX_PCT=0

  # Server-side subscription usage. Every read guards at the leaf: `rate_limits`
  # appears only for subscribers after the first API response, and each window
  # disappears independently once its resets_at passes — so the parent can be
  # present while five_hour is not.
  RL_5H=$(echo "$JSON_INPUT"       | jq -r '.rate_limits.five_hour.used_percentage // empty')
  RL_5H_RESET=$(echo "$JSON_INPUT" | jq -r '.rate_limits.five_hour.resets_at // empty')
  RL_7D=$(echo "$JSON_INPUT"       | jq -r '.rate_limits.seven_day.used_percentage // empty')

  # `cost` is not part of the statusline payload contract — it is absent on every
  # version checked, including 2.1.252. Read it as empty rather than 0 so the
  # renderer can tell "no cost available" from "nothing spent", and print nothing
  # instead of a permanent $0.00.
  DURATION_MS=$(echo "$JSON_INPUT"  | jq -r '.cost.total_duration_ms // empty')
  SESSION_COST=$(echo "$JSON_INPUT" | jq -r '.cost.total_cost_usd // empty')
}

# Time until an epoch-seconds deadline, as "2h 14m" / "43m". Empty when the
# deadline is missing or already past.
format_reset_in() {
  local target="${1:-}" now diff
  [[ -n "$target" ]] || return 0
  target=$(tcs_round_int "$target") || return 0
  now=$(date +%s)
  diff=$(( target - now ))
  [[ "$diff" -gt 0 ]] || return 0
  if [[ "$diff" -ge 3600 ]]; then
    printf '%dh %dm left' "$(( diff / 3600 ))" "$(( (diff % 3600) / 60 ))"
  else
    printf '%dm left' "$(( diff / 60 ))"
  fi
}

# ==============================================================================
# Formatters
# ==============================================================================

format_dirty() {
  local out=""
  [[ "${TCS_GIT_STAGED:-0}"   -gt 0 ]] && out+="${GREEN}+${TCS_GIT_STAGED}${RESET}"
  [[ "${TCS_GIT_MODIFIED:-0}" -gt 0 ]] && out+="${YELLOW}~${TCS_GIT_MODIFIED}${RESET}"
  [[ -n "$out" ]] && echo " $out"
}

# ==============================================================================
# Output
# ==============================================================================

render() {
  local line1="" line2=""

  # ── Line 1: identity ────────────────────────────────────────────────────────
  line1+="${CYAN}[${MODEL}]${RESET}"

  local dir_name="${CURRENT_DIR##*/}"
  [[ -n "$dir_name" ]] && line1+=" | 📁 ${dir_name}"

  if [[ "$tcs_cfg_show_git" == "true" && "$tcs_cfg_show_remote_url" == "true" \
      && -n "${TCS_GIT_REMOTEURL:-}" ]]; then
    line1+=" | ${YELLOW}🔗 ${TCS_GIT_REMOTEURL}${RESET}"
  fi

  if [[ "$tcs_cfg_show_git" == "true" && -n "${TCS_GIT_BRANCH:-}" ]]; then
    line1+=" | 🌿 ${TCS_GIT_BRANCH}$(format_dirty)"
  fi

  # ── Line 2: metrics ─────────────────────────────────────────────────────────

  # Context bar (block style, 10 chars)
  if [[ "$tcs_cfg_show_context_bar" == "true" ]]; then
    local ctx_bar
    ctx_bar=$(tcs_block_bar "$CTX_PCT" "$tcs_cfg_context_warn" "$tcs_cfg_context_danger")
    line2+="🧠 ${ctx_bar} ${CTX_PCT}%"
  fi

  # Duration
  if [[ "$tcs_cfg_show_duration" == "true" ]]; then
    local dur
    dur=$(tcs_format_duration "${DURATION_MS:-0}")
    [[ -n "$dur" ]] && line2+=" | ⏱ ${dur}"
  fi

  # Budget bar.
  #
  # rate_limits carries the server's own percentage — the same figure /usage and
  # the Claude apps report. It needs no plan constant, no subprocess and no
  # network. The ccusage token mode it supersedes divided input+output tokens by
  # a guessed per-plan limit; real usage runs past the max20x constant by more
  # than 2x without throttling, so that bar pegged at 100% while the window was
  # nowhere near spent.
  #
  # No dollar figure is shown beside it: `cost` is not in the statusline payload,
  # and the 5-hour window's own spend needs ccusage. For a subscriber the rate
  # limit *is* the budget signal, so a permanent $0.00 next to it only misleads.
  local budget_mode="${tcs_cfg_budget_mode:-token}"

  if [[ "$tcs_cfg_show_budget_bar" == "true" ]]; then
    if [[ -n "${RL_5H:-}" ]]; then
      local rl_pct rl_bar rl_reset
      rl_pct=$(tcs_round_int "$RL_5H") || rl_pct=0
      rl_bar=$(tcs_block_bar "$rl_pct" "$tcs_cfg_budget_warn" "$tcs_cfg_budget_danger")
      line2+=" | 🎫 ${rl_bar} ${rl_pct}% 5h"

      if [[ -n "${RL_7D:-}" ]]; then
        local rl_7d
        rl_7d=$(tcs_round_int "$RL_7D") || rl_7d=0
        line2+=" · ${rl_7d}% 7d"
      fi

      rl_reset=$(format_reset_in "${RL_5H_RESET:-}")
      [[ -n "$rl_reset" ]] && line2+=" | ⏳ ${rl_reset}"

    elif [[ "$budget_mode" == "token" && "${TCS_BLOCK_TOKENS:-0}" -gt 0 ]]; then
      # Token bar: inputTokens + outputTokens vs plan limit (ccusage)
      local tok_bar
      tok_bar=$(tcs_block_bar \
        "$TCS_BLOCK_TOKEN_PCT" "$tcs_cfg_budget_warn" "$tcs_cfg_budget_danger")
      local cost_fmt
      cost_fmt=$(LC_ALL=C awk -v c="${TCS_BLOCK_COST:-0}" 'BEGIN { printf "$%.2f", c + 0 }')
      line2+=" | 💰 ${tok_bar} ${TCS_BLOCK_TOKEN_PCT}% ${cost_fmt}"
      [[ -n "${TCS_BLOCK_TIME_LEFT:-}" ]] && line2+=" | ⏳ ${TCS_BLOCK_TIME_LEFT}"

    elif [[ "$budget_mode" == "cost" && -n "${SESSION_COST:-}" ]]; then
      # Cost bar: session cost vs plan danger threshold. Reached only when the
      # payload actually carries a cost — otherwise there is nothing to scale.
      local cost_pct=0
      if [[ -n "$tcs_cfg_cost_danger" ]]; then
        cost_pct=$(LC_ALL=C awk -v c="$SESSION_COST" -v d="$tcs_cfg_cost_danger" \
          'BEGIN { pct = int(c / d * 100); print (pct > 100 ? 100 : pct) }')
      fi
      local cost_bar cost_fmt
      cost_bar=$(tcs_block_bar "$cost_pct" "$tcs_cfg_budget_warn" "$tcs_cfg_budget_danger")
      cost_fmt=$(LC_ALL=C awk -v c="$SESSION_COST" 'BEGIN { printf "$%.2f", c + 0 }')
      line2+=" | 💰 ${cost_bar} ${cost_pct}% ${cost_fmt}"
    fi
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

Config: ~/.config/the-agentic-startup/statusline.toml
        <repo>/.claude/statusline.toml  (per-repo override)

Key options:
  plan         = pro | max5x | max20x | api | auto
  budget_mode  = token | cost
  token_limit  = <number>  (manual override)
  show_budget_bar   = true | false
  show_context_bar  = true | false
  show_duration     = true | false
  show_git          = true | false
  show_remote_url   = true | false

  [thresholds.context]  warn / danger
  [thresholds.budget]   warn / danger

Token limits per 5h window (inputTokens + outputTokens):
  pro:    ~28,450   max5x: ~57,000   max20x: ~142,500
EOF
  exit 0
}

# ==============================================================================
# Main
# ==============================================================================

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help

tcs_load_config
read_input
tcs_load_git_info "$CURRENT_DIR"
tcs_load_ccusage  "$CURRENT_DIR"
render
