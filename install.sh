#!/usr/bin/env bash
#
# The Custom Startup — Interactive Install Wizard
#
# Usage:
#   ./install.sh
#   curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

MARKETPLACE="MMoMM-org/the-custom-startup"
SOURCE_URL="${SOURCE_URL:-https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/scripts}"
STATUSLINE_DIR=""  # set dynamically in choose_statusline() based on TARGET

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
  cat << EOF
${BRIGHT_GREEN}
████████ ██   ██ ███████
   ██    ██   ██ ██
   ██    ███████ █████
   ██    ██   ██ ██
   ██    ██   ██ ███████

 ██████ ██    ██ ███████ ████████  ██████  ███    ███
██      ██    ██ ██         ██    ██    ██ ████  ████
██      ██    ██ ███████    ██    ██    ██ ██ ████ ██
██      ██    ██      ██    ██    ██    ██ ██  ██  ██
 ██████  ██████  ███████    ██     ██████  ██      ██

 █████  ██████  ███████ ███   ██ ████████ ██  ██████
██   ██ ██      ██      ████  ██    ██    ██ ██
███████ ██  ███ █████   ██ ██ ██    ██    ██ ██
██   ██ ██   ██ ██      ██  ████    ██    ██ ██
██   ██  ██████ ███████ ██   ███    ██    ██  ██████

███████ ████████  █████  ██████  ████████ ██   ██ ██████
██         ██    ██   ██ ██   ██    ██    ██   ██ ██   ██
███████    ██    ███████ ██████     ██    ██   ██ ██████
     ██    ██    ██   ██ ██   ██    ██    ██   ██ ██
███████    ██    ██   ██ ██   ██    ██     █████  ██
${RESET}
EOF
  printf "The Custom Agentic Startup — spec-driven development for Claude Code\n\n"
}

# ==============================================================================
# State — collected by wizard steps, applied in do_install()
# ==============================================================================

TARGET=""          # global | current | other
INSTALL_DIR=""     # ~ | $PWD | <path>
SETTINGS_FILE=""   # resolved settings.json path
PLUGINS=""         # space-separated list: start@the-custom-startup team@the-custom-startup
OUTPUT_STYLE=""    # e.g. "start:The Startup" or ""
SPECS_DIR_NAME=""  # e.g. "the-custom-startup"
AGENT_TEAMS=""     # yes | no
STATUSLINE=""      # yes | skip
STATUSLINE_REPLACE="" # yes | keep | skip  (when existing found)

# ==============================================================================
# Step 1: check_dependencies
# ==============================================================================

check_dependencies() {
  local missing=""

  command -v claude >/dev/null 2>&1 || missing="claude $missing"
  command -v jq     >/dev/null 2>&1 || missing="jq $missing"
  command -v curl   >/dev/null 2>&1 || missing="curl $missing"

  if [[ -n "$missing" ]]; then
    error "Missing required tools: $missing"
    local os; os=$(uname -s 2>/dev/null || echo "Unknown")
    case "$os" in
      Darwin)
        echo ""
        echo "  Install missing tools:"
        echo "    brew install $missing" ;;
      Linux)
        echo ""
        echo "  Install missing tools:"
        echo "    sudo apt install $missing   (Debian/Ubuntu)"
        echo "    sudo dnf install $missing   (Fedora/RHEL)" ;;
    esac
    echo ""
    echo "  For Claude CLI: https://claude.ai/download"
    exit 1
  fi
  success "Dependencies: claude, jq, curl"
}

# ==============================================================================
# Step 2: choose_target
# ==============================================================================

choose_target() {
  printf "\n${BRIGHT_GREEN}── Install Target${RESET}\n\n"
  printf "  ${CYAN}1)${RESET} Global         — applies to all Claude sessions\n"
  printf "  ${CYAN}2)${RESET} Current repo   — this git repository only\n"
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

  # Resolve settings file location
  if [[ "$TARGET" == "global" ]]; then
    SETTINGS_FILE="$HOME/.claude/settings.json"
  else
    SETTINGS_FILE="$INSTALL_DIR/.claude/settings.json"
  fi
}

# ==============================================================================
# Step 3: choose_plugins
# ==============================================================================

choose_plugins() {
  printf "\n${BRIGHT_GREEN}── Plugins${RESET}\n\n"
  printf "  ${CYAN}1)${RESET} Both           — start + team  (recommended)\n"
  printf "  ${CYAN}2)${RESET} start only     — workflow skills\n"
  printf "  ${CYAN}3)${RESET} team only      — specialist agents\n"
  printf "\n"
  ask "Select plugins [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    2) PLUGINS="start@the-custom-startup" ;;
    3) PLUGINS="team@the-custom-startup" ;;
    *)  PLUGINS="start@the-custom-startup team@the-custom-startup" ;;
  esac
  success "Plugins: $PLUGINS"
}

# ==============================================================================
# Step 4: choose_output_style
# ==============================================================================

choose_output_style() {
  printf "\n${BRIGHT_GREEN}── Output Style${RESET}\n\n"
  printf "  ${CYAN}1)${RESET} The Startup    — high-energy, delivery-focused  (recommended)\n"
  printf "  ${CYAN}2)${RESET} The ScaleUp    — structured, process-oriented\n"
  printf "  ${CYAN}3)${RESET} Skip           — keep current style\n"
  printf "\n"
  ask "Select output style [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    2) OUTPUT_STYLE="start:The ScaleUp" ;;
    3) OUTPUT_STYLE="" ;;
    *) OUTPUT_STYLE="start:The Startup" ;;
  esac
  if [[ -n "$OUTPUT_STYLE" ]]; then
    success "Output style: $OUTPUT_STYLE"
  else
    info "Output style: skipped"
  fi
}

# ==============================================================================
# Step 5: choose_specs_dir
# ==============================================================================

choose_specs_dir() {
  printf "\n${BRIGHT_GREEN}── Specs Directory${RESET}\n\n"
  printf "  The specs directory stores your specification files (PRDs, SDDs, plans).\n"
  printf "  Written to .claude/startup.toml — skills use this to find your specs.\n"
  printf "\n"
  ask "Specs directory name [default: the-custom-startup]:"
  local choice
  read -r choice </dev/tty
  SPECS_DIR_NAME="${choice:-the-custom-startup}"
  success "Specs directory: $SPECS_DIR_NAME"
}

# ==============================================================================
# Step 6: choose_agent_teams
# ==============================================================================

choose_agent_teams() {
  printf "\n${BRIGHT_GREEN}── Agent Teams${RESET}\n\n"
  printf "  Enables multi-agent collaboration where specialists work in parallel.\n"
  printf "  ${DIM}(experimental feature — CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1)${RESET}\n"
  printf "\n"

  # Check if already enabled
  if [[ -f "$SETTINGS_FILE" ]] && \
     jq -e '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS == "1"' "$SETTINGS_FILE" >/dev/null 2>&1; then
    success "Agent Teams already enabled"
    AGENT_TEAMS="yes"
    return
  fi

  ask "Enable Agent Teams? [Y/n]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    [nN]|[nN][oO]) AGENT_TEAMS="no";  info "Agent Teams: skipped" ;;
    *)              AGENT_TEAMS="yes"; success "Agent Teams: enabled" ;;
  esac
}

# ==============================================================================
# Step 7: choose_statusline
# ==============================================================================

choose_statusline() {
  printf "\n${BRIGHT_GREEN}── Statusline${RESET}\n\n"

  # Compute display path based on target
  if [[ "$TARGET" == "global" ]]; then
    STATUSLINE_DIR="$HOME/.config/the-custom-startup"
  else
    STATUSLINE_DIR="$INSTALL_DIR/.claude"
  fi

  # Check for existing statusLine config in settings.json
  if [[ -f "$SETTINGS_FILE" ]] && jq -e '.statusLine' "$SETTINGS_FILE" >/dev/null 2>&1; then
    local existing_cmd
    existing_cmd=$(jq -r '.statusLine.command // ""' "$SETTINGS_FILE" 2>/dev/null)
    warn "Existing statusLine detected: ${existing_cmd}"
    printf "\n"
    printf "  ${CYAN}1)${RESET} Keep existing\n"
    printf "  ${CYAN}2)${RESET} Replace with new one\n"
    printf "  ${CYAN}3)${RESET} Skip\n"
    printf "\n"
    ask "Choose [1-3, default: 1]:"
    local choice
    read -r choice </dev/tty
    case "$choice" in
      2) STATUSLINE="yes"; STATUSLINE_REPLACE="yes" ;;
      3) STATUSLINE="skip" ;;
      *) STATUSLINE="yes"; STATUSLINE_REPLACE="keep" ;;
    esac
  else
    printf "  Install an interactive statusline showing model, context, and session info.\n\n"
    ask "Install statusline? [Y/n]:"
    local choice
    read -r choice </dev/tty
    case "$choice" in
      [nN]|[nN][oO]) STATUSLINE="skip" ;;
      *)              STATUSLINE="yes" ;;
    esac
  fi

  case "$STATUSLINE" in
    yes)  success "Statusline: will install → $STATUSLINE_DIR/" ;;
    skip) info "Statusline: skipped" ;;
  esac
}

# ==============================================================================
# Step 8: confirm_summary
# ==============================================================================

# Return plugin display string (space separated → comma separated)
_plugin_display() {
  echo "$PLUGINS" | sed 's/@the-custom-startup//g' | tr ' ' ','
}

confirm_summary() {
  printf "\n${BRIGHT_GREEN}── Summary${RESET}\n\n"
  printf "  The following will be installed:\n\n"

  printf "  %-22s %s\n" "Plugins (global):" "$(_plugin_display)"
  printf "  %-22s %s\n" "Settings target:" "$SETTINGS_FILE"

  if [[ -n "$OUTPUT_STYLE" ]]; then
    printf "  %-22s %s\n" "Output style:" "$OUTPUT_STYLE"
  else
    printf "  %-22s %s\n" "Output style:" "(skipped)"
  fi

  local toml_dir
  if [[ "$TARGET" == "global" ]]; then
    toml_dir="$HOME/.claude/startup.toml"
  else
    toml_dir="$INSTALL_DIR/.claude/startup.toml"
  fi
  printf "  %-22s %s  (written to %s)\n" "Specs directory:" "${SPECS_DIR_NAME}/specs" "$toml_dir"

  if [[ "$AGENT_TEAMS" == "yes" ]]; then
    printf "  %-22s %s\n" "Agent Teams:" "enabled"
  else
    printf "  %-22s %s\n" "Agent Teams:" "(skipped)"
  fi

  case "$STATUSLINE" in
    yes)
      if [[ "$STATUSLINE_REPLACE" == "keep" ]]; then
        printf "  %-22s %s\n" "Statusline:" "keep existing"
      else
        printf "  %-22s %s\n" "Statusline:" "install → $STATUSLINE_DIR/"
      fi
      ;;
    skip)
      printf "  %-22s %s\n" "Statusline:" "(skipped)"
      ;;
  esac

  printf "\n"
  ask "Proceed? [Y/n]:"
  local answer
  read -r answer </dev/tty
  case "$answer" in
    [nN]|[nN][oO])
      printf "\nInstallation cancelled.\n"
      exit 0
      ;;
  esac
}

# ==============================================================================
# Step 9: do_install
# ==============================================================================

do_install() {
  printf "\n${BRIGHT_GREEN}── Installing${RESET}\n\n"

  # --- Marketplace + plugins (always global) ----------------------------------
  info "Configuring marketplace..."
  if claude plugin marketplace add "$MARKETPLACE" >/dev/null 2>&1; then
    success "Marketplace added"
  elif claude plugin marketplace update "$MARKETPLACE" >/dev/null 2>&1; then
    success "Marketplace updated"
  else
    success "Marketplace configured"
  fi

  for plugin in $PLUGINS; do
    info "Installing $plugin..."
    if claude plugin install "$plugin" >/dev/null 2>&1; then
      success "Plugin: $plugin"
    elif claude plugin update "$plugin" >/dev/null 2>&1; then
      success "Plugin: $plugin (updated)"
    else
      error "Failed to install $plugin"
      exit 2
    fi
  done

  # --- settings.json ----------------------------------------------------------
  local settings_dir
  settings_dir="$(dirname "$SETTINGS_FILE")"
  mkdir -p "$settings_dir"

  if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo '{}' > "$SETTINGS_FILE"
  fi

  # Validate JSON — backup and reset if corrupt
  if ! jq empty "$SETTINGS_FILE" 2>/dev/null; then
    warn "settings.json malformed, creating backup"
    cp "$SETTINGS_FILE" "${SETTINGS_FILE}.bak"
    echo '{}' > "$SETTINGS_FILE"
  fi

  # Output style
  if [[ -n "$OUTPUT_STYLE" ]]; then
    info "Configuring output style..."
    local tmp; tmp=$(mktemp)
    if jq --arg style "$OUTPUT_STYLE" '.outputStyle = $style' "$SETTINGS_FILE" > "$tmp"; then
      mv "$tmp" "$SETTINGS_FILE"
      success "Output style: $OUTPUT_STYLE"
    else
      rm -f "$tmp"
      warn "Failed to set output style"
    fi
  fi

  # Agent Teams
  if [[ "$AGENT_TEAMS" == "yes" ]]; then
    info "Enabling Agent Teams..."
    local tmp; tmp=$(mktemp)
    if jq '.env = (.env // {}) + {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}' "$SETTINGS_FILE" > "$tmp"; then
      mv "$tmp" "$SETTINGS_FILE"
      success "Agent Teams enabled"
    else
      rm -f "$tmp"
      warn "Failed to enable Agent Teams"
    fi
  fi

  # --- startup.toml -----------------------------------------------------------
  local toml_dir
  if [[ "$TARGET" == "global" ]]; then
    toml_dir="$HOME/.claude"
  else
    toml_dir="$INSTALL_DIR/.claude"
  fi
  mkdir -p "$toml_dir"

  local toml_file="$toml_dir/startup.toml"
  info "Writing startup.toml..."
  cat > "$toml_file" << EOF
# The Custom Startup — Configuration
# Generated by install.sh — edit freely.

[paths]
specs_dir = "${SPECS_DIR_NAME}/specs"
ideas_dir = "${SPECS_DIR_NAME}/ideas"
EOF
  success "startup.toml written: $toml_file"

  # --- Statusline -------------------------------------------------------------
  if [[ "$STATUSLINE" == "yes" && "$STATUSLINE_REPLACE" != "keep" ]]; then
    # Determine the target flag to pass to configure-statusline.sh
    local sl_flag=""
    case "$TARGET" in
      global)  sl_flag="--global" ;;
      current) sl_flag="--repo" ;;
      other)   sl_flag="--repo-path $INSTALL_DIR" ;;
    esac

    # Determine whether we have a local clone of configure-statusline.sh
    local this_script
    this_script="${BASH_SOURCE[0]:-}"
    local configure_script=""
    if [[ -n "$this_script" && "$this_script" != "-" ]]; then
      local this_dir
      this_dir="$(cd "$(dirname "$this_script")" 2>/dev/null && pwd)"
      if [[ -f "$this_dir/scripts/the-custom-startup-configure-statusline.sh" ]]; then
        configure_script="$this_dir/scripts/the-custom-startup-configure-statusline.sh"
      fi
    fi

    info "Running statusline configurator..."
    if [[ -n "$configure_script" ]]; then
      # shellcheck disable=SC2086
      bash "$configure_script" $sl_flag
    else
      # Remote: download and run
      local tmp_cfg; tmp_cfg=$(mktemp)
      if curl -fsSL "$SOURCE_URL/the-custom-startup-configure-statusline.sh" -o "$tmp_cfg" 2>/dev/null; then
        chmod +x "$tmp_cfg"
        # shellcheck disable=SC2086
        bash "$tmp_cfg" $sl_flag
        rm -f "$tmp_cfg"
      else
        warn "Could not download configure-statusline.sh — skipping statusline"
      fi
    fi
  elif [[ "$STATUSLINE" == "yes" && "$STATUSLINE_REPLACE" == "keep" ]]; then
    info "Keeping existing statusline configuration"
  fi
}

# ==============================================================================
# Completion message
# ==============================================================================

print_completion() {
  printf "\n${BRIGHT_GREEN}Installation complete!${RESET}\n\n"

  if [[ "$AGENT_TEAMS" != "yes" ]]; then
    printf "${YELLOW}  Tip:${RESET} Enable Agent Teams later by adding to %s:\n" "$SETTINGS_FILE"
    printf "${DIM}       \"env\": { \"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS\": \"1\" }${RESET}\n\n"
  fi

  printf "${DIM}  Learn more: https://github.com/MMoMM-org/the-custom-startup${RESET}\n\n"
}

# ==============================================================================
# Usage
# ==============================================================================

usage() {
  cat << EOF
Usage: $0 [OPTIONS]

Options:
  -h, --help    Show this help message

Interactive installation wizard for The Custom Startup framework.
Installs plugins, configures output style, sets up statusline, and
writes .claude/startup.toml with your specs directory preference.
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
  choose_plugins
  choose_output_style
  choose_specs_dir
  choose_agent_teams
  choose_statusline
  confirm_summary
  do_install
  print_completion
}

main "$@"
