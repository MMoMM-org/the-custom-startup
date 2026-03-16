#!/usr/bin/env bash
#
# The Custom Startup — Standard Statusline
#
# Single-line, placeholder-based statusline for Claude Code.
# Shows session cost (USD) as the budget indicator.
#
# Configuration: ~/.config/the-agentic-startup/statusline.toml
#                or <repo>/.claude/statusline.toml  (per-repo override)
#
# Format placeholders:
#   <path>    - Directory path (abbreviated)
#   <branch>  - Git branch with icon (* if dirty)
#   <model>   - Model name and output style
#   <context> - Context usage bar (Braille) and percentage
#   <session> - Session duration and cost (🕐 💰)
#   <lines>   - Lines added/removed
#   <spec>    - Active specification ID
#   <help>    - Help text
#
# Input:  JSON from Claude Code via stdin
# Output: Single formatted statusline with ANSI colors
#
# Dependencies: jq
# Performance target: <50ms

# ==============================================================================
# Shared library
# ==============================================================================

source "$(dirname "${BASH_SOURCE[0]}")/the-custom-startup-statusline-lib.sh"

# ==============================================================================
# Script-specific constants
# ==============================================================================

readonly BRAILLE_CHARS=("⠀" "⡀" "⡄" "⡆" "⡇" "⣇" "⣧" "⣷" "⣿")
readonly VALID_PLACEHOLDERS="path|branch|model|context|session|lines|spec|help"

# ==============================================================================
# Input parsing
# ==============================================================================

IFS= read -r -d '' json_input || true

{
  read -r current_dir
  read -r model_name
  read -r output_style
  read -r context_size
  read -r context_used
  read -r session_cost
  read -r session_duration_ms
  read -r lines_added
  read -r lines_removed
} <<< "$(echo "$json_input" | jq -r '
  (.workspace.current_dir // .cwd),
  .model.display_name,
  (.output_style.name | split(":") | .[-1]),
  .context_window.context_window_size,
  ((.context_window.current_usage.input_tokens // 0)
    + (.context_window.current_usage.cache_creation_input_tokens // 0)
    + (.context_window.current_usage.cache_read_input_tokens // 0)),
  .cost.total_cost_usd,
  .cost.total_duration_ms,
  .cost.total_lines_added,
  .cost.total_lines_removed
' 2>/dev/null)"

# ==============================================================================
# Formatters
# ==============================================================================

format_path() {
  local path="$current_dir"

  if [[ "$path" == "$HOME" ]]; then
    path="~"
  elif [[ "$path" == "$HOME"/* ]]; then
    path="~${path#$HOME}"
  fi

  local prefix=""
  if [[ "$path" == ~* ]]; then
    prefix="~"
    path="${path:1}"
  fi

  [[ "$path" == /* ]] && path="${path:1}"

  local IFS='/'
  read -ra parts <<< "$path"
  local count=${#parts[@]}
  local result=""

  for (( i = 0; i < count; i++ )); do
    local part="${parts[$i]}"
    [[ -z "$part" ]] && continue
    if [[ $i -lt $(( count - 1 )) ]]; then
      result+="/${part:0:1}"
    else
      result+="/${part}"
    fi
  done

  echo "📁 ${prefix}${result}"
}

format_branch() {
  local dir="$current_dir"

  [[ "$dir" == "$HOME" ]]   && dir="~"
  [[ "$dir" == "$HOME"/* ]] && dir="~${dir#$HOME}"
  [[ "$dir" =~ ^~ ]]        && dir="${dir/#\~/$HOME}"

  local branch="" dirty=""

  local git_head="${dir}/.git/HEAD"
  if [[ -f "$git_head" && -r "$git_head" ]]; then
    local head_content
    head_content=$(<"$git_head")
    if [[ "$head_content" =~ ^ref:[[:space:]]*refs/heads/(.+)$ ]]; then
      branch="${BASH_REMATCH[1]}"
    else
      branch="HEAD"
    fi
  elif command -v git &>/dev/null && [[ -d "${dir}/.git" ]]; then
    branch=$(cd "$dir" 2>/dev/null && git symbolic-ref --short HEAD 2>/dev/null || echo "")
    [[ -z "$branch" ]] && branch="HEAD"
  fi

  [[ -z "$branch" ]] && return

  if [[ -d "${dir}/.git" ]] && command -v git &>/dev/null; then
    if ! (cd "$dir" 2>/dev/null && git diff --quiet HEAD 2>/dev/null); then
      dirty="*"
    fi
  fi

  echo "⎇ ${branch}${dirty}"
}

# Braille-based context bar (5 chars, sub-character precision)
format_context() {
  [[ -z "$context_size" || "$context_size" == "null" || "$context_size" -eq 0 ]] && return

  # Include ~45k token compaction buffer
  local percent=$(( (context_used + 45000) * 100 / context_size ))
  [[ "$percent" -gt 100 ]] && percent=100

  local bar="" width=5
  local total_units=$(( width * 8 ))
  local filled_units=$(( percent * total_units / 100 ))

  for (( i = 0; i < width; i++ )); do
    local char_fill=$(( filled_units - (i * 8) ))
    [[ "$char_fill" -lt 0 ]] && char_fill=0
    [[ "$char_fill" -gt 8 ]] && char_fill=8
    bar+="${BRAILLE_CHARS[$char_fill]}"
  done

  local color="$TCS_COLOR_DEFAULT"
  [[ "$percent" -ge "$tcs_cfg_context_warn" ]]   && color="$TCS_COLOR_WARNING"
  [[ "$percent" -ge "$tcs_cfg_context_danger" ]]  && color="$TCS_COLOR_DANGER"

  echo "🧠 ${color}${bar} ${percent}%${TCS_STYLE_RESET}"
}

format_session() {
  local result=""

  if [[ -n "$session_duration_ms" && "$session_duration_ms" != "null" \
      && "$session_duration_ms" -gt 0 ]]; then
    local dur
    dur=$(tcs_format_duration "$session_duration_ms")
    [[ -n "$dur" ]] && result="🕐 ${dur}"
  fi

  if [[ -n "$session_cost" && "$session_cost" != "null" ]]; then
    local formatted_cost cost_color
    formatted_cost=$(printf "%.2f" "$session_cost")
    cost_color="$TCS_COLOR_SUCCESS"

    if tcs_decimal_gte "$session_cost" "$tcs_cfg_cost_danger"; then
      cost_color="$TCS_COLOR_DANGER"
    elif tcs_decimal_gte "$session_cost" "$tcs_cfg_cost_warn"; then
      cost_color="$TCS_COLOR_WARNING"
    fi

    if [[ -n "$result" ]]; then
      result+="  💰 ${cost_color}\$${formatted_cost}${TCS_STYLE_RESET}"
    else
      result="💰 ${cost_color}\$${formatted_cost}${TCS_STYLE_RESET}"
    fi
  fi

  echo "$result"
}

format_lines() {
  [[ -z "$lines_added"   || "$lines_added"   == "null" ]] && return
  [[ -z "$lines_removed" || "$lines_removed" == "null" ]] && return
  [[ "$lines_added" -eq 0 && "$lines_removed" -eq 0 ]]   && return

  echo "${TCS_COLOR_SUCCESS}+${lines_added}${TCS_STYLE_RESET}/${TCS_COLOR_DANGER}-${lines_removed}${TCS_STYLE_RESET}"
}

format_spec() {
  local dir="$current_dir"
  [[ "$dir" == "$HOME"/* ]] && dir="${dir#$HOME}"
  [[ "$dir" == "~"/* ]]     && dir="${dir:1}"

  if [[ "$dir" =~ \.start/specs/([0-9]+)- ]] \
  || [[ "$dir" =~ docs/specs/([0-9]+)- ]]; then
    echo "📋 ${BASH_REMATCH[1]}"
  fi
}

# ==============================================================================
# Help
# ==============================================================================

show_help() {
  cat << EOF
The Custom Startup — Standard Statusline

Usage: the-custom-startup-statusline-standard.sh [--help]

Config: ~/.config/the-agentic-startup/statusline.toml
        <repo>/.claude/statusline.toml  (per-repo override)

Format placeholders:
  <path>    - Abbreviated directory (e.g., ~/C/p/project)
  <branch>  - Git branch, * if dirty  (e.g., ⎇ main*)
  <model>   - Model and output style  (e.g., 🤖 Opus (The Startup))
  <context> - Braille context bar     (e.g., 🧠 ⣿⣿⡇⠀⠀ 50%)
  <session> - Duration and cost       (e.g., 🕐 30m  💰 \$1.50)
  <lines>   - Lines added/removed     (e.g., +156/-23)
  <spec>    - Active spec ID          (e.g., 📋 005)
  <help>    - Help text

Plan-based cost thresholds:
  pro     warn: \$1.50  danger: \$5.00
  max5x   warn: \$5.00  danger: \$15.00
  max20x  warn: \$10.00 danger: \$30.00
  api     warn: \$2.00  danger: \$10.00
EOF
  exit 0
}

# ==============================================================================
# Main
# ==============================================================================

main() {
  [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help

  tcs_load_config

  local format="$tcs_cfg_format"

  local path_part branch_part model_part context_part \
        session_part lines_part spec_part help_part

  [[ "$format" == *"<path>"* ]]    && path_part=$(format_path)
  [[ "$format" == *"<branch>"* ]]  && branch_part=$(format_branch)
  [[ "$format" == *"<model>"* ]]   && model_part="🤖 ${model_name} (${output_style})"
  [[ "$format" == *"<context>"* ]] && context_part=$(format_context)
  [[ "$format" == *"<session>"* ]] && session_part=$(format_session)
  [[ "$format" == *"<lines>"* ]]   && lines_part=$(format_lines)
  [[ "$format" == *"<spec>"* ]]    && spec_part=$(format_spec)
  [[ "$format" == *"<help>"* ]]    && \
    help_part="${TCS_COLOR_MUTED}\033[3m? for shortcuts${TCS_STYLE_RESET}"

  # Warn about unknown placeholders
  local unknown
  unknown=$(echo "$format" | grep -oE '<[a-z]+>' \
    | grep -vE "<(${VALID_PLACEHOLDERS})>" | tr '\n' ' ')
  [[ -n "$unknown" ]] && echo "Warning: Unknown placeholders: $unknown" >&2

  # Substitute placeholders
  local statusline="$format"
  statusline="${statusline//<path>/$path_part}"
  statusline="${statusline//<branch>/$branch_part}"
  statusline="${statusline//<model>/$model_part}"
  statusline="${statusline//<context>/$context_part}"
  statusline="${statusline//<session>/$session_part}"
  statusline="${statusline//<lines>/$lines_part}"
  statusline="${statusline//<spec>/$spec_part}"
  statusline="${statusline//<help>/$help_part}"

  # Collapse triple spaces left by empty placeholders
  while [[ "$statusline" == *"   "* ]]; do
    statusline="${statusline//   /  }"
  done
  statusline="${statusline#"${statusline%%[![:space:]]*}"}"
  statusline="${statusline%"${statusline##*[![:space:]]}"}"

  echo -e "${TCS_STYLE_RESET}${statusline}"
}

main "$@"
