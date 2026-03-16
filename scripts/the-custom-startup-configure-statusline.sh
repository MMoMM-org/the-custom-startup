#!/usr/bin/env bash
#
# The Custom Startup — Statusline Configurator
#
# Interactive wizard to install and configure any of the three statusline variants.
# Works both from a local clone and when piped directly from the web:
#
#   # From a local clone
#   ./scripts/the-custom-startup-configure-statusline.sh
#
#   # From the web (no clone needed)
#   curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/scripts/the-custom-startup-configure-statusline.sh | bash
#
# Options:
#   --global              Install globally (~/.config/the-custom-startup/)
#   --repo                Install per-repo (auto-detect git root)
#   --repo-path <path>    Install per-repo at a specific path
#   --source-url <url>    Override download base URL (default: GitHub raw)
#   --help

set -euo pipefail

# ==============================================================================
# Source URL (can be overridden via --source-url or SOURCE_URL env var)
# ==============================================================================

SOURCE_URL="${SOURCE_URL:-https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/scripts}"

# Quick pre-parse: extract --source-url before anything else so it's available
# for the lib download below. Full arg parsing happens later in parse_args().
_args=("$@")
for (( _i=0; _i<${#_args[@]}; _i++ )); do
  if [[ "${_args[$_i]}" == "--source-url" ]]; then
    SOURCE_URL="${_args[$(( _i + 1 ))]:-$SOURCE_URL}"
    break
  fi
done

# ==============================================================================
# Shared library — local or downloaded
# ==============================================================================

_script_path="${BASH_SOURCE[0]:-}"

# Detect whether we have a local clone to work from.
# Running via `curl | bash` sets BASH_SOURCE[0] to "" or "-", and the
# directory won't contain our files.
if [[ -n "$_script_path" && "$_script_path" != "-" \
    && -f "$(cd "$(dirname "$_script_path")" 2>/dev/null && pwd)/the-custom-startup-statusline-lib.sh" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$_script_path")" && pwd)"
  SOURCE_MODE="local"
else
  # Remote mode: download lib to a temp directory
  SCRIPT_DIR="$(mktemp -d)"
  SOURCE_MODE="remote"
  # Temp dir cleanup on exit
  trap 'rm -rf "$SCRIPT_DIR"' EXIT

  if ! command -v curl > /dev/null 2>&1; then
    echo "ERROR: curl is required for remote installation." >&2
    echo "  macOS:  curl is pre-installed" >&2
    echo "  Ubuntu: sudo apt install curl" >&2
    exit 1
  fi

  if ! curl -fsSL "$SOURCE_URL/the-custom-startup-statusline-lib.sh" -o "$SCRIPT_DIR/the-custom-startup-statusline-lib.sh" 2>/dev/null; then
    echo "ERROR: Failed to download the-custom-startup-statusline-lib.sh from $SOURCE_URL" >&2
    exit 1
  fi
fi

# shellcheck source=the-custom-startup-statusline-lib.sh
source "$SCRIPT_DIR/the-custom-startup-statusline-lib.sh"

# Convenience aliases — keep call sites readable
BRIGHT_GREEN="$TCS_COLOR_BRIGHT_GREEN"
info()    { tcs_info    "$@"; }
warn()    { tcs_warn    "$@"; }
error()   { tcs_error   "$@"; }
success() { tcs_success "$@"; }
ask()     { tcs_ask     "$@"; }
header()  { tcs_header  "$@"; }

# ==============================================================================
# State variables
# ==============================================================================

SCOPE=""          # global | repo
VARIANT=""        # enhanced | starship | standard
REPO_PATH=""      # explicit repo root (--repo-path) or auto-detected
PLAN="pro"
PLAN_CUSTOM_LIMIT=""
BUDGET_MODE="token"
CCUSAGE_OK=false
STARSHIP_OK=false

# ==============================================================================
# Helpers
# ==============================================================================

command_exists() { command -v "$1" > /dev/null 2>&1; }

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

# Fetch a file from local source dir or remote URL, write to dest.
# Always makes the dest file executable.
fetch_file() {
  local filename="$1" dest="$2"

  if [[ "$SOURCE_MODE" == "local" ]]; then
    cp "$SCRIPT_DIR/$filename" "$dest"
  else
    if ! curl -fsSL "$SOURCE_URL/$filename" -o "$dest" 2>/dev/null; then
      error "Failed to download $filename from $SOURCE_URL"
      return 1
    fi
  fi
  chmod +x "$dest" 2>/dev/null || true
}

# Fetch the shared lib (not executable) to a directory.
fetch_lib() {
  local dest_dir="$1"
  local dest="$dest_dir/the-custom-startup-statusline-lib.sh"

  if [[ "$SOURCE_MODE" == "local" ]]; then
    cp "$SCRIPT_DIR/the-custom-startup-statusline-lib.sh" "$dest"
  else
    if ! curl -fsSL "$SOURCE_URL/the-custom-startup-statusline-lib.sh" -o "$dest" 2>/dev/null; then
      error "Failed to download the-custom-startup-statusline-lib.sh from $SOURCE_URL"
      return 1
    fi
  fi
}

# Resolve repo root: explicit path → git auto-detect → cwd
resolve_repo_root() {
  if [[ -n "$REPO_PATH" ]]; then
    echo "$REPO_PATH"
  elif git rev-parse --show-toplevel > /dev/null 2>&1; then
    git rev-parse --show-toplevel
  else
    warn "Not inside a git repository. Using current directory."
    pwd
  fi
}

update_settings_json() {
  local settings_file="$1" script_path="$2"

  # jq guaranteed available — checked in check_all_requirements
  if jq -e '.statusLine' "$settings_file" > /dev/null 2>&1; then
    local existing_cmd
    existing_cmd=$(jq -r '.statusLine.command // ""' "$settings_file" 2>/dev/null)
    warn "Statusline already configured: ${existing_cmd}"
    if ! prompt_yn "Replace with the new one?" "n"; then
      info "Keeping existing configuration"
      return 0
    fi
  fi

  local tmp_file
  tmp_file=$(mktemp)
  if jq --arg cmd "$script_path" \
    '.statusLine = {"type": "command", "command": $cmd}' \
    "$settings_file" > "$tmp_file"; then
    mv "$tmp_file" "$settings_file"
    success "settings.json updated: $settings_file"
  else
    rm -f "$tmp_file"
    error "Failed to update $settings_file"
    return 1
  fi
}

generate_toml() {
  local toml_path="$1" plan="${2:-pro}" token_limit="${3:-}" budget_mode="${4:-token}"

  cat > "$toml_path" << EOF
# The Custom Startup — Statusline Configuration
# Generated by configure-statusline.sh — edit freely.
# Shared by all statusline variants.
#
# Global:   ~/.config/the-custom-startup/statusline.toml
# Per-repo: <repo>/.claude/statusline.toml  (overrides global, partial is fine)

# Claude subscription plan
# Options: auto | pro | max5x | max20x | api
plan          = "${plan}"
fallback_plan = "pro"
EOF

  if [[ -n "$token_limit" ]]; then
    cat >> "$toml_path" << EOF

# Manual token limit override (overrides plan default)
token_limit = ${token_limit}
EOF
  fi

  cat >> "$toml_path" << EOF

# Budget bar mode: "token" (enhanced default) | "cost" (standard default)
budget_mode = "${budget_mode}"

# Format string (standard statusline only)
format = "<path> <branch>  <model>  <context>  <session>  <help>"

# Cache TTLs (seconds)
ccusage_cache_ttl = 60
git_cache_ttl     = 15

# Display toggles (enhanced statusline)
show_budget_bar  = true
show_context_bar = true
show_duration    = true
show_git         = true
show_remote_url  = true

[thresholds.context]
warn   = 70
danger = 90

[thresholds.budget]
warn   = 70
danger = 90
EOF

  success "Config written: $toml_path"
}

# ==============================================================================
# Dependency checks — ALL run before any user questions
# ==============================================================================

check_dependencies() {
  local missing=()

  command_exists jq  || missing+=("jq")
  command_exists git || missing+=("git")

  # curl required in remote mode; good to have in local mode for scripts that
  # download at runtime
  if [[ "$SOURCE_MODE" == "remote" ]] && ! command_exists curl; then
    missing+=("curl")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    warn "Missing required tools: ${missing[*]}"
    local os; os=$(uname -s)
    case "$os" in
      Darwin)
        echo "  brew install ${missing[*]}" ;;
      Linux)
        echo "  sudo apt install ${missing[*]}  (Debian/Ubuntu)"
        echo "  sudo dnf install ${missing[*]}  (Fedora/RHEL)" ;;
      MSYS*|CYGWIN*|MINGW*)
        echo "  winget install jqlang.jq" ;;
    esac
    echo ""
    if ! prompt_yn "Continue anyway?" "n"; then exit 1; fi
  else
    success "Base dependencies: jq, git"
  fi
}

check_ccusage() {
  if ! command_exists bun; then
    warn "bun not found — token budget bar unavailable"
    echo "  Install: curl -fsSL https://bun.sh/install | bash"
    CCUSAGE_OK=false; return 1
  fi
  if ! bun x ccusage --version > /dev/null 2>&1; then
    warn "ccusage not found — token budget bar unavailable"
    echo "  Install: bun x ccusage"
    CCUSAGE_OK=false; return 1
  fi
  success "ccusage available"
  CCUSAGE_OK=true
}

check_starship() {
  if command_exists starship; then
    success "Starship: $(starship --version 2>/dev/null | head -1)"
    STARSHIP_OK=true
  else
    warn "Starship not installed — Starship variant unavailable"
    echo "  Install: curl -sS https://starship.rs/install.sh | sh"
    STARSHIP_OK=false
  fi
}

check_all_requirements() {
  header "Checking requirements"
  check_dependencies
  check_ccusage
  check_starship
  echo ""
  local src_note=""
  [[ "$SOURCE_MODE" == "remote" ]] && src_note="  ${DIM}(remote — files will be downloaded from ${SOURCE_URL})${RESET}"
  echo -e "  Enhanced : $( [[ "$CCUSAGE_OK"  == "true" ]] && echo "✓ ready" || echo "⚠ ready (token bar disabled)")"
  echo -e "  Starship : $( [[ "$STARSHIP_OK" == "true" ]] && echo "✓ ready" || echo "✗ unavailable (install starship first)")"
  echo    "  Standard : ✓ ready"
  echo -e "${src_note}"
  echo ""
}

# ==============================================================================
# Interactive selection
# ==============================================================================

select_location() {
  header "Installation scope"
  echo -e "  ${CYAN}1)${RESET} Global      — all sessions  (~/.config/the-custom-startup/ + ~/.claude/settings.json)"
  echo -e "  ${CYAN}2)${RESET} Current repo — this git repo (.claude/ in detected root)"
  echo -e "  ${CYAN}3)${RESET} Custom path  — specify a repo path manually"
  echo ""

  ask "Select scope [1-3]:"
  local choice
  read -r choice </dev/tty

  case "$choice" in
    1) SCOPE="global" ;;
    2) SCOPE="repo" ;;
    3)
      SCOPE="repo"
      ask "Enter path to repo root:"
      read -r REPO_PATH </dev/tty
      # Expand ~ manually (not done by read)
      REPO_PATH="${REPO_PATH/#\~/$HOME}"
      if [[ ! -d "$REPO_PATH" ]]; then
        error "Directory not found: $REPO_PATH"
        exit 1
      fi
      success "Repo path: $REPO_PATH"
      ;;
    *)
      warn "Invalid choice, defaulting to Global"
      SCOPE="global"
      ;;
  esac
}

select_variant() {
  header "Choose statusline variant"

  local ccusage_note="" starship_note=""
  [[ "$CCUSAGE_OK"  != "true" ]] && ccusage_note=" ${YELLOW}(token bar disabled)${RESET}"
  [[ "$STARSHIP_OK" != "true" ]] && starship_note=" ${RED}(unavailable)${RESET}"

  echo -e "  ${CYAN}1)${RESET} Enhanced  — Two-line: git, context + token budget bars, OSC 8 links${ccusage_note}"
  echo ""
  echo -e "  ${CYAN}2)${RESET} Starship  — Your Starship prompt extended with Claude data${starship_note}"
  echo ""
  echo -e "  ${CYAN}3)${RESET} Standard  — Single-line, placeholder-based, lightweight"
  echo ""

  ask "Select variant [1-3]:"
  local choice
  read -r choice </dev/tty

  case "$choice" in
    1) VARIANT="enhanced" ;;
    2)
      if [[ "$STARSHIP_OK" != "true" ]]; then
        error "Starship is not installed. Install it first, then re-run."
        exit 1
      fi
      VARIANT="starship"
      ;;
    3) VARIANT="standard" ;;
    *)
      warn "Invalid choice, defaulting to Enhanced"
      VARIANT="enhanced"
      ;;
  esac
}

select_plan() {
  header "Claude subscription plan"
  echo "  Sets the token budget limit for the budget bar."
  echo ""
  echo -e "  ${CYAN}1)${RESET} Pro     (\$20/mo)  — ~28,450 tokens / 5h window"
  echo -e "  ${CYAN}2)${RESET} Max 5x  (\$100/mo) — ~57,000 tokens / 5h window"
  echo -e "  ${CYAN}3)${RESET} Max 20x (\$200/mo) — ~142,500 tokens / 5h window"
  echo -e "  ${CYAN}4)${RESET} Custom  — enter limit manually"
  echo ""

  ask "Select plan [1-4]:"
  local choice
  read -r choice </dev/tty

  PLAN_CUSTOM_LIMIT=""
  case "$choice" in
    1) PLAN="pro" ;;
    2) PLAN="max5x" ;;
    3) PLAN="max20x" ;;
    4)
      PLAN="pro"
      ask "Enter token limit (e.g. 44000):"
      read -r PLAN_CUSTOM_LIMIT </dev/tty
      ;;
    *)
      warn "Invalid choice, defaulting to Pro"
      PLAN="pro"
      ;;
  esac

  echo ""
  echo "  Budget bar display mode:"
  echo -e "  ${CYAN}1)${RESET} token — tokens used vs plan limit  (recommended for Enhanced)"
  echo -e "  ${CYAN}2)${RESET} cost  — session USD vs threshold   (standard default)"
  echo ""
  ask "Select mode [1-2, default: 1]:"
  local mode_choice
  read -r mode_choice </dev/tty
  case "$mode_choice" in
    2) BUDGET_MODE="cost" ;;
    *) BUDGET_MODE="token" ;;
  esac
}

# ==============================================================================
# Install helpers
# ==============================================================================

# Resolve destination directory and settings file based on SCOPE / REPO_PATH.
# Sets: DEST_DIR, SETTINGS_FILE, TOML_DEST
_resolve_destinations() {
  local variant_filename="$1"

  if [[ "$SCOPE" == "global" ]]; then
    DEST_DIR="$TCS_GLOBAL_CONFIG_DIR"
    SETTINGS_FILE="$TCS_CLAUDE_SETTINGS"
    TOML_DEST="$TCS_GLOBAL_CONFIG_DIR/statusline.toml"
    mkdir -p "$DEST_DIR"
    # Ensure global settings.json exists
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    [[ ! -f "$SETTINGS_FILE" ]] && echo '{}' > "$SETTINGS_FILE"
  else
    local repo_root
    repo_root=$(resolve_repo_root)
    DEST_DIR="$repo_root/.claude"
    SETTINGS_FILE="$repo_root/.claude/settings.json"
    TOML_DEST="$repo_root/.claude/statusline.toml"
    mkdir -p "$DEST_DIR"
    [[ ! -f "$SETTINGS_FILE" ]] && echo '{}' > "$SETTINGS_FILE"
  fi

  SCRIPT_DEST="$DEST_DIR/$variant_filename"
}

# Install a variant: fetch script + lib, write toml if needed, update settings.
_install_variant() {
  local variant_filename="$1"
  local needs_toml="${2:-true}"

  _resolve_destinations "$variant_filename"

  info "Fetching $variant_filename..."
  fetch_file "$variant_filename" "$SCRIPT_DEST"
  success "Script installed: $SCRIPT_DEST"

  info "Fetching the-custom-startup-statusline-lib.sh..."
  fetch_lib "$DEST_DIR"
  success "Library installed: $DEST_DIR/the-custom-startup-statusline-lib.sh"

  if [[ "$needs_toml" == "true" ]]; then
    if [[ -f "$TOML_DEST" ]]; then
      if prompt_yn "Config already exists at $TOML_DEST — overwrite?" "n"; then
        generate_toml "$TOML_DEST" "$PLAN" "$PLAN_CUSTOM_LIMIT" "$BUDGET_MODE"
      else
        info "Preserving existing config"
      fi
    else
      generate_toml "$TOML_DEST" "$PLAN" "$PLAN_CUSTOM_LIMIT" "$BUDGET_MODE"
    fi
  fi

  info "Updating settings.json..."
  update_settings_json "$SETTINGS_FILE" "$SCRIPT_DEST"
}

# ==============================================================================
# Variant installers
# ==============================================================================

install_enhanced() {
  header "Installing Enhanced Statusline"
  [[ "$CCUSAGE_OK" != "true" ]] && warn "Token budget bar disabled until ccusage is installed"
  select_plan
  _install_variant "the-custom-startup-statusline-enhanced.sh" "true"
}

install_starship() {
  header "Installing Starship Statusline Bridge"
  _install_variant "the-custom-startup-statusline-starship.sh" "false"

  local doc_url="$SOURCE_URL/../docs/statusline-starship.md"
  [[ "$SOURCE_MODE" == "local" ]] && doc_url="$(dirname "$SCRIPT_DIR")/docs/statusline-starship.md"
  echo ""
  echo "  ${YELLOW}Next:${RESET} Add env_var modules to ~/.config/starship.toml"
  echo "  Guide: $doc_url"
  echo ""
}

install_standard() {
  header "Installing Standard Statusline"
  select_plan
  _install_variant "the-custom-startup-statusline-standard.sh" "true"
}

# ==============================================================================
# Argument parsing
# ==============================================================================

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --global)
        SCOPE="global" ;;
      --repo)
        SCOPE="repo" ;;
      --repo-path)
        SCOPE="repo"
        REPO_PATH="${2:?--repo-path requires a path argument}"
        REPO_PATH="${REPO_PATH/#\~/$HOME}"
        shift
        ;;
      --source-url)
        # Already consumed in pre-parse above; skip value here
        shift
        ;;
      --help|-h)
        cat << EOF
The Custom Startup — Statusline Configurator

Usage:
  configure-statusline.sh [OPTIONS]

  # From the web (no clone needed):
  curl -fsSL ${SOURCE_URL}/the-custom-startup-configure-statusline.sh | bash

Options:
  --global              Install for all sessions
  --repo                Install for current git repo
  --repo-path <path>    Install for repo at given path
  --source-url <url>    Download scripts from this base URL
                        (default: $SOURCE_URL)
  --help                Show this help

Without options, runs fully interactive.
EOF
        exit 0
        ;;
      *) warn "Unknown option: $1" ;;
    esac
    shift
  done
}

# ==============================================================================
# Entry point
# ==============================================================================

main() {
  parse_args "$@"

  printf "${BRIGHT_GREEN}┌────────────────────────────────────────┐\n"
  printf "${BRIGHT_GREEN}│  The Custom Startup — Statusline Setup │\n"
  printf "${BRIGHT_GREEN}└────────────────────────────────────────┘${RESET}\n\n"

  check_all_requirements

  [[ -z "$SCOPE" ]]   && select_location
  [[ -z "$VARIANT" ]] && select_variant

  case "$VARIANT" in
    enhanced) install_enhanced ;;
    starship) install_starship ;;
    standard) install_standard ;;
  esac

  echo ""
  printf "${BRIGHT_GREEN}Done!${RESET} Statusline will update after the next Claude response.\n"
  echo ""
  printf "  ${DIM}Re-run this script anytime to switch variants or update settings.${RESET}\n"
  if [[ "$SOURCE_MODE" == "remote" ]]; then
    printf "  ${DIM}Source: ${SOURCE_URL}${RESET}\n"
  fi
}

main "$@"
