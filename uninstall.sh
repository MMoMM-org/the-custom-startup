#!/usr/bin/env bash
#
# The Custom Startup — Uninstall Wizard
#
# Usage:
#   ./uninstall.sh
#   bash <(curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/uninstall.sh)

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

PLUGINS="tcs-start@the-custom-startup tcs-team@the-custom-startup"

# ==============================================================================
# Colors
# ==============================================================================

GREEN=$'\033[0;32m'
BRIGHT_GREEN=$'\033[1;32m'
YELLOW=$'\033[0;33m'
RED=$'\033[0;31m'
CYAN=$'\033[0;36m'
DIM=$'\033[2m'
RESET=$'\033[0m'

# ==============================================================================
# Logging
# ==============================================================================

info()    { printf "${DIM}  →${RESET} %s\n" "$*"; }
warn()    { printf "${YELLOW}  !${RESET} %s\n" "$*" >&2; }
error()   { printf "${RED}  ✗${RESET} %s\n" "$*" >&2; }
success() { printf "${GREEN}  ✓${RESET} %s\n" "$*"; }
ask()     { printf "${CYAN}  ?${RESET} %s " "$*"; }

# ==============================================================================
# Banner
# ==============================================================================

banner() {
  printf "${BRIGHT_GREEN}"
  printf "The Custom Agentic Startup — Uninstall\n"
  printf "${RESET}\n"
}

# ==============================================================================
# State — set by wizard steps, used in do_uninstall()
# ==============================================================================

TARGET=""
INSTALL_DIR=""
SETTINGS_FILE=""

# Detected items (non-empty = found)
FOUND_PLUGINS=""       # space-separated list
FOUND_OUTPUT_STYLE=""  # e.g. "tcs-tcs-start:The Startup"
FOUND_AGENT_TEAMS=""   # "yes" if set
FOUND_STATUSLINE=""    # command string
FOUND_SL_SCRIPTS_DIR="" # directory containing statusline scripts
FOUND_TOML=""          # absolute path to startup.toml
FOUND_PROMPTS_BASE=""  # base dir containing templates/ docs/ bin/

# ==============================================================================
# Step 1: check_dependencies
# ==============================================================================

check_dependencies() {
  local missing=""
  command -v claude >/dev/null 2>&1 || missing="claude $missing"
  command -v jq     >/dev/null 2>&1 || missing="jq $missing"
  if [[ -n "$missing" ]]; then
    error "Missing required tools: $missing"
    exit 1
  fi
  success "Dependencies: claude, jq"
}

# ==============================================================================
# Step 2: choose_target
# ==============================================================================

choose_target() {
  printf "\n${BRIGHT_GREEN}── Install Target${RESET}\n\n"
  printf "  Where was The Custom Startup installed?\n\n"
  printf "  ${CYAN}1)${RESET} Global         — ~/.claude/settings.json\n"
  printf "  ${CYAN}2)${RESET} Current repo   — ./.claude/settings.json\n"
  printf "  ${CYAN}3)${RESET} Other repo     — specify a path\n"
  printf "\n"
  ask "Select target [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    2)
      TARGET="current"
      if git rev-parse --show-toplevel >/dev/null 2>&1; then
        INSTALL_DIR="$(git rev-parse --show-toplevel)"
      else
        INSTALL_DIR="$PWD"
      fi
      success "Target: current repo ($INSTALL_DIR)"
      ;;
    3)
      TARGET="other"
      ask "Enter repo path:"
      read -r INSTALL_DIR </dev/tty
      INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"
      if [[ ! -d "$INSTALL_DIR" ]]; then
        error "Directory not found: $INSTALL_DIR"
        exit 1
      fi
      success "Target: $INSTALL_DIR"
      ;;
    *)
      TARGET="global"
      INSTALL_DIR="$HOME"
      success "Target: global"
      ;;
  esac

  if [[ "$TARGET" == "global" ]]; then
    SETTINGS_FILE="$HOME/.claude/settings.json"
  else
    SETTINGS_FILE="$INSTALL_DIR/.claude/settings.json"
  fi
}

# ==============================================================================
# Step 3: detect_installation
# ==============================================================================

detect_installation() {
  printf "\n${BRIGHT_GREEN}── Detecting Installation${RESET}\n\n"

  # --- Plugins ----------------------------------------------------------------
  local plugin
  for plugin in $PLUGINS; do
    if claude plugin list 2>/dev/null | grep -q "^${plugin%%@*}"; then
      FOUND_PLUGINS="$FOUND_PLUGINS $plugin"
      info "Plugin: $plugin"
    fi
  done

  # --- settings.json ----------------------------------------------------------
  if [[ -f "$SETTINGS_FILE" ]]; then
    local style
    style=$(jq -r '.outputStyle // ""' "$SETTINGS_FILE" 2>/dev/null)
    case "$style" in
      "tcs-tcs-start:The Startup"|"tcs-tcs-start:The ScaleUp")
        FOUND_OUTPUT_STYLE="$style"
        info "Output style: $style"
        ;;
    esac

    if jq -e '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS == "1"' "$SETTINGS_FILE" >/dev/null 2>&1; then
      FOUND_AGENT_TEAMS="yes"
      info "Agent Teams: enabled"
    fi

    local sl_cmd
    sl_cmd=$(jq -r '.statusLine.command // ""' "$SETTINGS_FILE" 2>/dev/null)
    if [[ "$sl_cmd" == *"the-custom-startup"* ]]; then
      FOUND_STATUSLINE="$sl_cmd"
      # Derive scripts directory from the command path
      local expanded="${sl_cmd/#\~/$HOME}"
      FOUND_SL_SCRIPTS_DIR="$(dirname "$expanded")"
      info "StatusLine: $sl_cmd"
    fi
  fi

  # --- startup.toml -----------------------------------------------------------
  local toml_dir
  if [[ "$TARGET" == "global" ]]; then
    toml_dir="$HOME/.claude"
  else
    toml_dir="$INSTALL_DIR/.claude"
  fi
  local toml_file="$toml_dir/startup.toml"
  if [[ -f "$toml_file" ]]; then
    FOUND_TOML="$toml_file"
    info "startup.toml: $toml_file"

    # Read prompts_dir to find downloaded files base
    local prompts_rel
    prompts_rel=$(grep '^prompts_dir' "$toml_file" 2>/dev/null \
      | sed 's/^prompts_dir[[:space:]]*=[[:space:]]*"\(.*\)"/\1/' || true)
    if [[ -n "$prompts_rel" ]]; then
      # Resolve to absolute path
      local abs_prompts
      if [[ "$prompts_rel" = /* ]]; then
        abs_prompts="$prompts_rel"
      else
        abs_prompts="$toml_dir/$prompts_rel"
      fi
      # Go up one level (templates/ → base)
      local base
      base="$(dirname "$abs_prompts")"
      if [[ -d "$base/templates" || -d "$base/docs" || -d "$base/bin" ]]; then
        FOUND_PROMPTS_BASE="$base"
        info "Downloaded files: $base/"
      fi
    fi
  fi

  printf "\n"
}

# ==============================================================================
# Step 4: show_summary + confirm
# ==============================================================================

show_summary() {
  printf "\n${BRIGHT_GREEN}── What Will Be Removed${RESET}\n\n"

  local found_anything=false

  [[ -n "${FOUND_PLUGINS# }" ]] && {
    printf "  %-22s %s\n" "Plugins:" "${FOUND_PLUGINS# }"
    found_anything=true
  }
  [[ -n "$FOUND_OUTPUT_STYLE" ]] && {
    printf "  %-22s %s\n" "Output style:" "$FOUND_OUTPUT_STYLE"
    found_anything=true
  }
  [[ -n "$FOUND_AGENT_TEAMS" ]] && {
    printf "  %-22s %s\n" "Agent Teams:" "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
    found_anything=true
  }
  [[ -n "$FOUND_STATUSLINE" ]] && {
    printf "  %-22s %s\n" "StatusLine:" "$FOUND_STATUSLINE"
    found_anything=true
  }
  [[ -n "$FOUND_TOML" ]] && {
    printf "  %-22s %s\n" "startup.toml:" "$FOUND_TOML"
    found_anything=true
  }

  if ! $found_anything; then
    printf "  Nothing found. The Custom Startup does not appear to be installed\n"
    printf "  (checked: %s)\n\n" "$SETTINGS_FILE"
    exit 0
  fi

  if [[ -n "$FOUND_PROMPTS_BASE" ]]; then
    printf "\n"
    printf "  ${YELLOW}Optional — downloaded files${RESET} (will ask before deleting):\n"
    [[ -d "$FOUND_PROMPTS_BASE/templates" ]] && printf "    %s/templates/\n" "$FOUND_PROMPTS_BASE"
    [[ -d "$FOUND_PROMPTS_BASE/docs"      ]] && printf "    %s/docs/\n"      "$FOUND_PROMPTS_BASE"
    [[ -d "$FOUND_PROMPTS_BASE/bin"       ]] && printf "    %s/bin/\n"       "$FOUND_PROMPTS_BASE"
  fi

  if [[ -n "$FOUND_SL_SCRIPTS_DIR" && -d "$FOUND_SL_SCRIPTS_DIR" ]]; then
    printf "\n"
    printf "  ${YELLOW}Optional — statusline scripts${RESET} (will ask before deleting):\n"
    printf "    %s/\n" "$FOUND_SL_SCRIPTS_DIR"
  fi

  printf "\n"
  ask "Proceed with uninstall? [Y/n]:"
  local answer
  read -r answer </dev/tty
  case "$answer" in
    [nN]|[nN][oO])
      printf "\nUninstall cancelled.\n"
      exit 0
      ;;
  esac
}

# ==============================================================================
# Step 5: do_uninstall
# ==============================================================================

do_uninstall() {
  printf "\n${BRIGHT_GREEN}── Uninstalling${RESET}\n\n"

  # --- Plugins ----------------------------------------------------------------
  if [[ -n "${FOUND_PLUGINS# }" ]]; then
    local plugin
    for plugin in ${FOUND_PLUGINS# }; do
      info "Uninstalling $plugin..."
      if claude plugin uninstall "$plugin" >/dev/null 2>&1; then
        success "Plugin removed: $plugin"
      else
        warn "Could not uninstall $plugin"
      fi
    done
  fi

  # --- settings.json ----------------------------------------------------------
  if [[ -f "$SETTINGS_FILE" ]]; then
    local tmp

    if [[ -n "$FOUND_OUTPUT_STYLE" ]]; then
      tmp=$(mktemp)
      jq 'del(.outputStyle)' "$SETTINGS_FILE" > "$tmp" && mv "$tmp" "$SETTINGS_FILE"
      success "Output style removed"
    fi

    if [[ -n "$FOUND_AGENT_TEAMS" ]]; then
      tmp=$(mktemp)
      jq 'del(.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS)' "$SETTINGS_FILE" > "$tmp" && mv "$tmp" "$SETTINGS_FILE"
      tmp=$(mktemp)
      jq 'if (.env // {}) == {} then del(.env) else . end' "$SETTINGS_FILE" > "$tmp" && mv "$tmp" "$SETTINGS_FILE"
      success "Agent Teams removed"
    fi

    if [[ -n "$FOUND_STATUSLINE" ]]; then
      tmp=$(mktemp)
      jq 'del(.statusLine)' "$SETTINGS_FILE" > "$tmp" && mv "$tmp" "$SETTINGS_FILE"
      success "statusLine removed"
    fi
  fi

  # --- startup.toml -----------------------------------------------------------
  if [[ -n "$FOUND_TOML" ]]; then
    rm -f "$FOUND_TOML"
    success "startup.toml deleted"
  fi

  # --- Downloaded files (optional) --------------------------------------------
  if [[ -n "$FOUND_PROMPTS_BASE" ]]; then
    printf "\n"
    ask "Delete downloaded templates and scripts? (${FOUND_PROMPTS_BASE}/templates|docs|bin) [y/N]:"
    local choice
    read -r choice </dev/tty
    case "$choice" in
      [yY]|[yY][eE][sS])
        rm -rf "$FOUND_PROMPTS_BASE/templates" \
                "$FOUND_PROMPTS_BASE/docs" \
                "$FOUND_PROMPTS_BASE/bin" 2>/dev/null || true
        success "Downloaded files deleted"
        ;;
      *)
        info "Kept: $FOUND_PROMPTS_BASE/"
        ;;
    esac
  fi

  # --- Statusline scripts (optional) ------------------------------------------
  if [[ -n "$FOUND_SL_SCRIPTS_DIR" && -d "$FOUND_SL_SCRIPTS_DIR" ]]; then
    ask "Delete statusline scripts? (${FOUND_SL_SCRIPTS_DIR}/) [y/N]:"
    local choice
    read -r choice </dev/tty
    case "$choice" in
      [yY]|[yY][eE][sS])
        rm -rf "$FOUND_SL_SCRIPTS_DIR"
        success "Statusline scripts deleted: $FOUND_SL_SCRIPTS_DIR/"
        ;;
      *)
        info "Kept: $FOUND_SL_SCRIPTS_DIR/"
        ;;
    esac
  fi
}

# ==============================================================================
# Completion
# ==============================================================================

print_completion() {
  printf "\n${BRIGHT_GREEN}Uninstall complete!${RESET}\n\n"
  printf "${DIM}  To reinstall: ./install.sh${RESET}\n\n"
}

# ==============================================================================
# Usage
# ==============================================================================

usage() {
  cat << EOF
Usage: $0 [OPTIONS]

Options:
  -h, --help    Show this help message

Interactive uninstall wizard for The Custom Startup framework.
Removes plugins, cleans settings.json, and deletes installed files.
EOF
}

# ==============================================================================
# Argument parsing
# ==============================================================================

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      *)
        error "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done
}

# ==============================================================================
# Main
# ==============================================================================

main() {
  parse_args "$@"

  banner
  check_dependencies
  choose_target
  detect_installation
  show_summary
  do_uninstall
  print_completion
}

main "$@"
