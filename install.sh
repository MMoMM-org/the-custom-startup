#!/usr/bin/env bash
#
# The Custom Startup — Installer
#
# Works both from a local clone and when piped directly from the web:
#
#   # From a local clone
#   ./install.sh
#
#   # From the web (no clone needed)
#   curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
#
# Options:
#   --marketplace <org/repo>   Plugin marketplace (default: MMoMM-org/the-custom-startup)
#   --source-url <url>         Override raw base URL for file downloads
#   --plugins <start|team|both>  Skip plugin selection
#   --output-style <name>      Skip output style selection (or "skip")
#   --skip-statusline          Skip statusline setup
#   --agent-teams <y|n>        Skip agent teams question
#   --dry-run                  Show what would happen, do nothing
#   --global                   Install to ~/.claude (global)
#   --repo                     Install to .claude/ in current git repo
#   --repo-path <path>         Install to .claude/ in given repo
#   --help

set -euo pipefail

# ==============================================================================
# Source URL — can be overridden via --source-url or SOURCE_URL env var
# ==============================================================================

MARKETPLACE="${MARKETPLACE:-MMoMM-org/the-custom-startup}"
SOURCE_URL="${SOURCE_URL:-https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main}"

# Quick pre-parse: extract --source-url and --marketplace before anything else
# so they're available during source mode detection.  Full parse happens later.
_args=("$@")
for (( _i=0; _i<${#_args[@]}; _i++ )); do
  case "${_args[$_i]}" in
    --source-url)
      SOURCE_URL="${_args[$(( _i + 1 ))]:-$SOURCE_URL}"
      ;;
    --marketplace)
      MARKETPLACE="${_args[$(( _i + 1 ))]:-$MARKETPLACE}"
      ;;
  esac
done

# ==============================================================================
# Source mode detection
# ==============================================================================

_script_path="${BASH_SOURCE[0]:-}"

# Local mode: running from a clone that contains configure-statusline.sh
if [[ -n "$_script_path" && "$_script_path" != "-" \
    && -f "$(cd "$(dirname "$_script_path")" 2>/dev/null && pwd)/scripts/configure-statusline.sh" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$_script_path")" && pwd)"
  SOURCE_MODE="local"
else
  SCRIPT_DIR=""
  SOURCE_MODE="remote"
fi

# ==============================================================================
# State variables
# ==============================================================================

SCOPE=""          # global | repo
REPO_PATH=""
PLUGINS=""        # start | team | both
OUTPUT_STYLE=""   # "start:The Startup" | "start:The ScaleUp" | skip
AGENT_TEAMS=""    # y | n
DRY_RUN=false
SKIP_STATUSLINE=false

# ==============================================================================
# Colors
# ==============================================================================

GREEN='\033[0;32m'
BRIGHT_GREEN='\033[1;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

# ==============================================================================
# Logging
# ==============================================================================

info()    { printf "${DIM}  →${RESET} %s\n"    "$*"; }
warn()    { printf "${YELLOW}  !${RESET} %s\n" "$*" >&2; }
error()   { printf "${RED}  ✗${RESET} %s\n"    "$*" >&2; }
success() { printf "${GREEN}  ✓${RESET} %s\n"  "$*"; }
ask()     { printf "${CYAN}  ?${RESET} %s "     "$*"; }
header()  { printf "\n${BRIGHT_GREEN}▸ %s${RESET}\n" "$*"; }
dryrun()  { printf "${YELLOW}  [dry-run]${RESET} %s\n" "$*"; }

# ==============================================================================
# Banner
# ==============================================================================

banner() {
  printf "${BRIGHT_GREEN}"
  cat << 'EOF'

 ████████╗██╗  ██╗███████╗
    ██╔══╝██║  ██║██╔════╝
    ██║   ███████║█████╗
    ██║   ██╔══██║██╔══╝
    ██║   ██║  ██║███████╗
    ╚═╝   ╚═╝  ╚═╝╚══════╝

  ██████╗██╗   ██╗███████╗████████╗ ██████╗ ███╗   ███╗
 ██╔════╝██║   ██║██╔════╝╚══██╔══╝██╔═══██╗████╗ ████║
 ██║     ██║   ██║███████╗   ██║   ██║   ██║██╔████╔██║
 ██║     ██║   ██║╚════██║   ██║   ██║   ██║██║╚██╔╝██║
 ╚██████╗╚██████╔╝███████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
  ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝

  ███████╗████████╗ █████╗ ██████╗ ████████╗██╗   ██╗██████╗
  ██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚══██╔══╝██║   ██║██╔══██╗
  ███████╗   ██║   ███████║██████╔╝   ██║   ██║   ██║██████╔╝
  ╚════██║   ██║   ██╔══██║██╔══██╗   ██║   ██║   ██║██╔═══╝
  ███████║   ██║   ██║  ██║██║  ██║   ██║   ╚██████╔╝██║
  ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝

EOF
  printf "${RESET}"
  echo "  The framework for agentic software development"
  echo ""
}

# ==============================================================================
# Helpers
# ==============================================================================

command_exists() { command -v "$1" > /dev/null 2>&1; }

# Resolve the plugin name suffix from the marketplace repo (the part after /)
# e.g. "MMoMM-org/the-custom-startup" → "the-custom-startup"
marketplace_plugin_suffix() {
  echo "${MARKETPLACE##*/}"
}

# Prompt yes/no, return 0 for yes, 1 for no.
# Usage: prompt_yn "Question" [default: y|n]
prompt_yn() {
  local question="$1" default="${2:-y}"
  local prompt
  [[ "$default" == "y" ]] && prompt="[Y/n]" || prompt="[y/N]"
  ask "$question $prompt"
  local answer
  read -r answer </dev/tty
  case "$answer" in
    [nN]|[nN][oO]) return 1 ;;
    [yY]|[yY][eE][sS]) return 0 ;;
    "") [[ "$default" == "y" ]] && return 0 || return 1 ;;
    *) return 1 ;;
  esac
}

# Resolve SETTINGS_FILE and INSTALL_DIR from SCOPE / REPO_PATH.
# Sets globals: SETTINGS_FILE, INSTALL_DIR
resolve_paths() {
  if [[ "$SCOPE" == "global" ]]; then
    INSTALL_DIR="$HOME/.claude"
    SETTINGS_FILE="$HOME/.claude/settings.json"
  else
    local repo_root
    if [[ -n "$REPO_PATH" ]]; then
      repo_root="$REPO_PATH"
    elif git rev-parse --show-toplevel > /dev/null 2>&1; then
      repo_root="$(git rev-parse --show-toplevel)"
    else
      warn "Not inside a git repository. Falling back to global install."
      SCOPE="global"
      INSTALL_DIR="$HOME/.claude"
      SETTINGS_FILE="$HOME/.claude/settings.json"
      return
    fi
    INSTALL_DIR="$repo_root/.claude"
    SETTINGS_FILE="$repo_root/.claude/settings.json"
  fi
}

# Ensure SETTINGS_FILE exists and is valid JSON.
ensure_settings_json() {
  if [[ "$DRY_RUN" == "true" ]]; then
    dryrun "mkdir -p $INSTALL_DIR"
    dryrun "Create $SETTINGS_FILE if missing"
    return
  fi
  mkdir -p "$INSTALL_DIR"
  if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo '{}' > "$SETTINGS_FILE"
  elif ! jq empty "$SETTINGS_FILE" 2>/dev/null; then
    warn "settings.json malformed — creating backup and resetting"
    cp "$SETTINGS_FILE" "${SETTINGS_FILE}.bak"
    echo '{}' > "$SETTINGS_FILE"
  fi
}

# Write a jq expression to SETTINGS_FILE via a temp file.
# Usage: jq_write <jq-filter> [additional jq args...]
jq_write() {
  local filter="$1"; shift
  local tmp
  tmp=$(mktemp)
  if jq "$@" "$filter" "$SETTINGS_FILE" > "$tmp"; then
    mv "$tmp" "$SETTINGS_FILE"
  else
    rm -f "$tmp"
    return 1
  fi
}

# ==============================================================================
# Dependency checks — ALL run before any user questions
# ==============================================================================

check_all_requirements() {
  header "Checking requirements"

  local missing=()
  local os; os=$(uname -s 2>/dev/null || echo "unknown")

  # Hard requirement: claude CLI
  if ! command_exists claude; then
    error "Claude CLI is not installed"
    echo "    Install: curl -fsSL https://claude.ai/install.sh | sh"
    echo ""
    exit 1
  fi
  success "claude CLI"

  # Required: jq
  if ! command_exists jq; then
    missing+=("jq")
  else
    success "jq"
  fi

  # Required in remote mode: curl
  if [[ "$SOURCE_MODE" == "remote" ]] && ! command_exists curl; then
    missing+=("curl")
  elif command_exists curl; then
    success "curl"
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    warn "Missing required tools: ${missing[*]}"
    case "$os" in
      Darwin)
        echo "    brew install ${missing[*]}" ;;
      Linux)
        echo "    sudo apt install ${missing[*]}   (Debian/Ubuntu)"
        echo "    sudo dnf install ${missing[*]}   (Fedora/RHEL)" ;;
      MSYS*|CYGWIN*|MINGW*)
        echo "    winget install jqlang.jq" ;;
    esac
    echo ""
    exit 1
  fi

  echo ""
}

# ==============================================================================
# Detect existing installation state
# ==============================================================================

# Returns "none" | "installed" depending on whether the plugin is registered.
detect_existing_plugin() {
  local plugin_name="$1"
  if claude plugin list 2>/dev/null | grep -q "$plugin_name"; then
    echo "installed"
  else
    echo "none"
  fi
}

# Read a key from settings.json, return empty string if missing.
read_setting() {
  local key="$1"
  if [[ -f "$SETTINGS_FILE" ]]; then
    jq -r "$key // empty" "$SETTINGS_FILE" 2>/dev/null || true
  fi
}

# Show current install state and return whether anything is already installed.
detect_existing_state() {
  local suffix; suffix=$(marketplace_plugin_suffix)
  local has_start has_team has_style has_statusline

  has_start=$(detect_existing_plugin "start@${suffix}")
  has_team=$(detect_existing_plugin "team@${suffix}")
  has_style=$(read_setting '.outputStyle')
  has_statusline=$(read_setting '.statusLine.command')

  if [[ "$has_start" == "none" && "$has_team" == "none" && -z "$has_style" && -z "$has_statusline" ]]; then
    return  # Nothing installed — silent, continue normally
  fi

  header "Existing installation detected"
  [[ "$has_start" != "none" ]] && info "Plugin: start@${suffix} (installed)"
  [[ "$has_team"  != "none" ]] && info "Plugin: team@${suffix} (installed)"
  [[ -n "$has_style"      ]] && info "Output style: $has_style"
  [[ -n "$has_statusline" ]] && info "Statusline: $has_statusline"
  echo ""
  info "Re-running is safe — existing settings will be offered as defaults."
  echo ""
}

# ==============================================================================
# Interactive: scope selection
# ==============================================================================

select_scope() {
  header "Installation scope"
  echo "  ${CYAN}1)${RESET} Global      — all sessions  (~/.claude/settings.json)"
  echo "  ${CYAN}2)${RESET} Repo-local  — this git repo (.claude/ in repo root)"
  echo "  ${CYAN}3)${RESET} Custom path — specify repo path manually"
  echo ""
  ask "Select scope [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty

  case "$choice" in
    2)
      SCOPE="repo"
      ;;
    3)
      SCOPE="repo"
      ask "Enter path to repo root:"
      read -r REPO_PATH </dev/tty
      REPO_PATH="${REPO_PATH/#\~/$HOME}"
      if [[ ! -d "$REPO_PATH" ]]; then
        error "Directory not found: $REPO_PATH"
        exit 1
      fi
      success "Repo path: $REPO_PATH"
      ;;
    *)
      SCOPE="global"
      ;;
  esac
}

# ==============================================================================
# Interactive: plugin selection
# ==============================================================================

select_plugins() {
  local suffix; suffix=$(marketplace_plugin_suffix)

  header "Plugin selection"
  echo "  ${CYAN}1)${RESET} Both        — start@${suffix} + team@${suffix}  (recommended)"
  echo "  ${CYAN}2)${RESET} start only  — workflow orchestration skills"
  echo "  ${CYAN}3)${RESET} team only   — specialized agent library"
  echo ""
  ask "Select plugins [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty

  case "$choice" in
    2) PLUGINS="start" ;;
    3) PLUGINS="team"  ;;
    *) PLUGINS="both"  ;;
  esac
}

# ==============================================================================
# Interactive: output style selection
# ==============================================================================

select_output_style() {
  local existing; existing=$(read_setting '.outputStyle')
  local current_note=""
  [[ -n "$existing" ]] && current_note=" ${DIM}(current: $existing)${RESET}"

  header "Output style${current_note}"
  echo "  ${CYAN}1)${RESET} The Startup  — high-energy, parallel execution, startup DNA  (recommended)"
  echo "  ${CYAN}2)${RESET} The ScaleUp  — systematic, metrics-driven, scale-oriented"
  echo "  ${CYAN}3)${RESET} Skip         — keep current / set later"
  echo ""
  ask "Select style [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty

  case "$choice" in
    2) OUTPUT_STYLE="start:The ScaleUp" ;;
    3) OUTPUT_STYLE="skip" ;;
    *) OUTPUT_STYLE="start:The Startup" ;;
  esac
}

# ==============================================================================
# Interactive: agent teams
# ==============================================================================

select_agent_teams() {
  local existing; existing=$(read_setting '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS')
  if [[ "$existing" == "1" ]]; then
    success "Agent Teams already enabled"
    AGENT_TEAMS="y"
    return
  fi

  header "Agent Teams (experimental)"
  echo "  Enables multi-agent collaboration where specialized agents work"
  echo "  together on complex tasks via the Task tool."
  echo ""
  ask "Enable Agent Teams? [Y/n]:"
  local answer
  read -r answer </dev/tty
  case "$answer" in
    [nN]|[nN][oO]) AGENT_TEAMS="n" ;;
    *)              AGENT_TEAMS="y" ;;
  esac
}

# ==============================================================================
# Execution: marketplace + plugins
# ==============================================================================

install_marketplace() {
  local suffix; suffix=$(marketplace_plugin_suffix)
  info "Configuring marketplace: $MARKETPLACE"

  if [[ "$DRY_RUN" == "true" ]]; then
    dryrun "claude plugin marketplace add $MARKETPLACE"
    return
  fi

  if claude plugin marketplace add "$MARKETPLACE" >/dev/null 2>&1; then
    success "Marketplace: $MARKETPLACE"
  elif claude plugin marketplace update "$MARKETPLACE" >/dev/null 2>&1; then
    success "Marketplace updated: $MARKETPLACE"
  else
    success "Marketplace configured: $MARKETPLACE"
  fi
}

install_plugins() {
  local suffix; suffix=$(marketplace_plugin_suffix)
  local plugin_list=()

  case "$PLUGINS" in
    start) plugin_list=("start@${suffix}") ;;
    team)  plugin_list=("team@${suffix}")  ;;
    *)     plugin_list=("start@${suffix}" "team@${suffix}") ;;
  esac

  header "Installing plugins"

  local plugin
  for plugin in "${plugin_list[@]}"; do
    if [[ "$DRY_RUN" == "true" ]]; then
      dryrun "claude plugin install $plugin"
      continue
    fi
    info "Installing $plugin..."
    if claude plugin install "$plugin" >/dev/null 2>&1; then
      success "$plugin"
    else
      error "Failed to install $plugin"
      exit 2
    fi
  done
}

# ==============================================================================
# Execution: output style
# ==============================================================================

configure_output_style() {
  [[ "$OUTPUT_STYLE" == "skip" ]] && return

  if [[ "$DRY_RUN" == "true" ]]; then
    dryrun "Set outputStyle = \"$OUTPUT_STYLE\" in $SETTINGS_FILE"
    return
  fi

  if jq_write --arg style "$OUTPUT_STYLE" '.outputStyle = $style'; then
    success "Output style: $OUTPUT_STYLE"
  else
    error "Failed to set outputStyle in $SETTINGS_FILE"
    exit 4
  fi
}

# ==============================================================================
# Execution: agent teams
# ==============================================================================

configure_agent_teams() {
  if [[ "$AGENT_TEAMS" == "y" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
      dryrun "Set CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in $SETTINGS_FILE"
      return
    fi
    if jq_write '.env = (.env // {}) + {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}'; then
      success "Agent Teams enabled"
    else
      warn "Failed to enable Agent Teams — set manually in $SETTINGS_FILE"
    fi
  else
    info "Agent Teams skipped"
  fi
}

# ==============================================================================
# Execution: statusline
# ==============================================================================

run_statusline_configurator() {
  header "Statusline setup"

  # Build flags to pass through
  local flags=()
  [[ "$SCOPE" == "global" ]]  && flags+=("--global")
  [[ "$SCOPE" == "repo" && -z "$REPO_PATH" ]] && flags+=("--repo")
  [[ "$SCOPE" == "repo" && -n "$REPO_PATH" ]] && flags+=("--repo-path" "$REPO_PATH")
  [[ "$SOURCE_MODE" == "remote" ]] && flags+=("--source-url" "${SOURCE_URL}/scripts")

  if [[ "$DRY_RUN" == "true" ]]; then
    dryrun "Run configure-statusline.sh ${flags[*]:-}"
    return
  fi

  if [[ "$SOURCE_MODE" == "local" ]]; then
    local configurator="$SCRIPT_DIR/scripts/configure-statusline.sh"
    if [[ -f "$configurator" ]]; then
      bash "$configurator" "${flags[@]:-}"
      return
    fi
    warn "configure-statusline.sh not found locally, falling back to remote"
  fi

  # Remote mode: pipe from SOURCE_URL
  if ! command_exists curl; then
    error "curl is required to fetch configure-statusline.sh"
    exit 1
  fi
  local configurator_url="${SOURCE_URL}/scripts/configure-statusline.sh"
  info "Fetching configure-statusline.sh..."
  curl -fsSL "$configurator_url" | bash -s -- "${flags[@]:-}"
}

# ==============================================================================
# Summary
# ==============================================================================

print_summary() {
  local suffix; suffix=$(marketplace_plugin_suffix)

  echo ""
  printf "${BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  printf "${BRIGHT_GREEN}  Installation complete!${RESET}\n"
  printf "${BRIGHT_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  echo ""

  if [[ "$AGENT_TEAMS" != "y" ]]; then
    printf "  ${YELLOW}Tip:${RESET} Enable Agent Teams anytime in ${DIM}${SETTINGS_FILE}${RESET}:\n"
    printf "  ${DIM}  \"env\": { \"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS\": \"1\" }${RESET}\n"
    echo ""
  fi

  if [[ "$SKIP_STATUSLINE" == "true" ]]; then
    printf "  ${DIM}Statusline skipped. Run configure-statusline.sh separately to set up.${RESET}\n"
    echo ""
  fi

  printf "  ${DIM}Marketplace : ${MARKETPLACE}${RESET}\n"
  printf "  ${DIM}Settings    : ${SETTINGS_FILE}${RESET}\n"
  printf "  ${DIM}Docs        : https://github.com/${MARKETPLACE}${RESET}\n"
  echo ""
}

# ==============================================================================
# Usage
# ==============================================================================

usage() {
  local suffix; suffix=$(marketplace_plugin_suffix)
  cat << EOF
The Custom Startup — Installer

Usage:
  install.sh [OPTIONS]

  # From the web:
  curl -fsSL ${SOURCE_URL}/install.sh | bash

Options:
  --marketplace <org/repo>    Plugin marketplace (default: $MARKETPLACE)
  --source-url <url>          Override raw base URL for downloads
  --plugins <start|team|both> Skip plugin selection
  --output-style <name>       Skip output style selection
                              (values: "start:The Startup", "start:The ScaleUp", "skip")
  --skip-statusline           Skip statusline setup
  --agent-teams <y|n>         Skip agent teams question
  --dry-run                   Show what would happen, do nothing
  --global                    Install to ~/.claude  (global, default)
  --repo                      Install to .claude/ in current git repo
  --repo-path <path>          Install to .claude/ in given repo
  --help                      Show this help

Without options, runs fully interactive.
EOF
}

# ==============================================================================
# Argument parsing
# ==============================================================================

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --marketplace)
        MARKETPLACE="${2:?--marketplace requires a value}"
        shift ;;
      --source-url)
        # Already consumed in pre-parse; skip value here
        shift ;;
      --plugins)
        PLUGINS="${2:?--plugins requires start|team|both}"
        shift ;;
      --output-style)
        OUTPUT_STYLE="${2:?--output-style requires a value}"
        shift ;;
      --skip-statusline)
        SKIP_STATUSLINE=true ;;
      --agent-teams)
        AGENT_TEAMS="${2:?--agent-teams requires y|n}"
        shift ;;
      --dry-run)
        DRY_RUN=true ;;
      --global)
        SCOPE="global" ;;
      --repo)
        SCOPE="repo" ;;
      --repo-path)
        SCOPE="repo"
        REPO_PATH="${2:?--repo-path requires a path}"
        REPO_PATH="${REPO_PATH/#\~/$HOME}"
        if [[ ! -d "$REPO_PATH" ]]; then
          error "Directory not found: $REPO_PATH"
          exit 1
        fi
        shift ;;
      --help|-h)
        usage
        exit 0 ;;
      *)
        error "Unknown option: $1"
        usage
        exit 1 ;;
    esac
    shift
  done
}

# ==============================================================================
# Main
# ==============================================================================

main() {
  parse_args "$@"

  [[ "$DRY_RUN" == "true" ]] && printf "${YELLOW}DRY RUN — no changes will be made${RESET}\n\n"

  banner
  check_all_requirements

  # Scope first (needed to resolve SETTINGS_FILE)
  [[ -z "$SCOPE" ]] && select_scope
  resolve_paths
  ensure_settings_json

  # Detect and display existing state
  detect_existing_state

  # Remaining interactive selections
  [[ -z "$PLUGINS" ]]      && select_plugins
  [[ -z "$OUTPUT_STYLE" ]] && select_output_style
  [[ -z "$AGENT_TEAMS" ]]  && select_agent_teams

  echo ""
  header "Installing"

  install_marketplace
  install_plugins

  header "Configuring"

  configure_output_style
  configure_agent_teams

  if [[ "$SKIP_STATUSLINE" != "true" ]]; then
    run_statusline_configurator
  fi

  print_summary
}

main "$@"
