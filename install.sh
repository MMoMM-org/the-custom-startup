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
REPO_RAW_URL="${REPO_RAW_URL:-https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main}"
SOURCE_URL="${SOURCE_URL:-$REPO_RAW_URL/scripts}"
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
PLUGINS=""         # space-separated list: tcs-workflow@the-custom-startup tcs-team@the-custom-startup
OUTPUT_STYLE=""    # e.g. "tcs-workflow:The Startup" or ""
SPECS_DIR_NAME=""  # e.g. "the-custom-startup"
PROMPTS=""         # yes | skip
PROMPTS_BASE_DIR="" # absolute path, e.g. ~/.claude/the-custom-startup
AGENT_TEAMS=""     # yes | no
SATORI="no"        # yes | no
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
  printf "  ${CYAN}1)${RESET} Recommended       — tcs-workflow + tcs-team + tcs-helper (workflow, agents, Memory Bank)\n"
  printf "  ${CYAN}2)${RESET} Core only         — tcs-workflow + tcs-team (workflow + agents, no Memory Bank)\n"
  printf "  ${CYAN}3)${RESET} All               — everything including tcs-patterns (domain pattern skills)\n"
  printf "  ${CYAN}4)${RESET} Pick and choose   — select individual plugins\n"
  printf "\n"
  ask "Select plugins [1-4, default: 1]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    2) PLUGINS="tcs-workflow@the-custom-startup tcs-team@the-custom-startup" ;;
    3) PLUGINS="tcs-workflow@the-custom-startup tcs-team@the-custom-startup tcs-helper@the-custom-startup tcs-patterns@the-custom-startup" ;;
    4) _pick_plugins ;;
    *) PLUGINS="tcs-workflow@the-custom-startup tcs-team@the-custom-startup tcs-helper@the-custom-startup" ;;
  esac
  success "Plugins: $PLUGINS"
}

_pick_plugins() {
  PLUGINS=""
  printf "\n  Select which plugins to install (y/n for each):\n\n"

  ask "tcs-workflow — core workflow skills (20 skills, required for others) [Y/n]:"
  local c; read -r c </dev/tty
  case "$c" in [nN]|[nN][oO]) ;; *) PLUGINS="$PLUGINS tcs-workflow@the-custom-startup" ;; esac

  ask "tcs-team     — 15 specialist agents across 8 roles [Y/n]:"
  read -r c </dev/tty
  case "$c" in [nN]|[nN][oO]) ;; *) PLUGINS="$PLUGINS tcs-team@the-custom-startup" ;; esac

  ask "tcs-helper   — Memory Bank, skill authoring, git workflows [Y/n]:"
  read -r c </dev/tty
  case "$c" in [nN]|[nN][oO]) ;; *) PLUGINS="$PLUGINS tcs-helper@the-custom-startup" ;; esac

  ask "tcs-patterns — 17 domain pattern skills (architecture, testing, platforms) [y/N]:"
  read -r c </dev/tty
  case "$c" in [yY]|[yY][eE][sS]) PLUGINS="$PLUGINS tcs-patterns@the-custom-startup" ;; esac

  PLUGINS="${PLUGINS# }"
  if [[ -z "$PLUGINS" ]]; then
    warn "No plugins selected — at minimum tcs-workflow is recommended"
    ask "Install tcs-workflow anyway? [Y/n]:"
    read -r c </dev/tty
    case "$c" in [nN]|[nN][oO]) ;; *) PLUGINS="tcs-workflow@the-custom-startup" ;; esac
  fi
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
    2) OUTPUT_STYLE="tcs-workflow:The ScaleUp" ;;
    3) OUTPUT_STYLE="" ;;
    *) OUTPUT_STYLE="tcs-workflow:The Startup" ;;
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
  printf "  The base directory for XDD specs, ADRs, and ideas.\n"
  printf "  Written to .claude/startup.toml [tcs] docs_base — skills use this to find your specs.\n"
  printf "  Specs will be stored under <docs_base>/specs/.\n"
  printf "\n"
  ask "Docs base directory [default: docs/XDD]:"
  local choice
  read -r choice </dev/tty
  SPECS_DIR_NAME="${choice:-docs/XDD}"
  success "Docs base: $SPECS_DIR_NAME"
}

# ==============================================================================
# Step 6: choose_prompts
# ==============================================================================

choose_prompts() {
  printf "\n${BRIGHT_GREEN}── Multi-AI Templates${RESET}\n\n"

  # Compute default base dir — same parent as specs
  local toml_dir
  if [[ "$TARGET" == "global" ]]; then
    toml_dir="$HOME/.claude"
  else
    toml_dir="$INSTALL_DIR/.claude"
  fi
  local default_base="$toml_dir/$SPECS_DIR_NAME"

  printf "  Prompt templates and utility scripts for working with Claude.ai,\n"
  printf "  Perplexity, and the spec export/import workflow.\n"
  printf "\n"
  printf "  Default: ${DIM}%s/${RESET}\n" "$default_base"
  printf "    ${DIM}templates/${RESET}   brainstorm, PRD, research, constitution prompts\n"
  printf "    ${DIM}docs/${RESET}        multi-ai-workflow guide\n"
  printf "    ${DIM}bin/${RESET}         export-spec.sh, import-spec.sh\n"
  printf "\n"
  printf "  ${CYAN}1)${RESET} Yes — install to default path\n"
  printf "  ${CYAN}2)${RESET} Yes — specify different path\n"
  printf "  ${CYAN}3)${RESET} Skip\n"
  printf "\n"
  ask "Select [1-3, default: 1]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    2)
      ask "Enter base directory:"
      read -r PROMPTS_BASE_DIR </dev/tty
      PROMPTS_BASE_DIR="${PROMPTS_BASE_DIR/#\~/$HOME}"
      PROMPTS="yes"
      ;;
    3)
      PROMPTS="skip"
      ;;
    *)
      PROMPTS_BASE_DIR="$default_base"
      PROMPTS="yes"
      ;;
  esac

  if [[ "$PROMPTS" == "yes" ]]; then
    success "Multi-AI templates: will install → $PROMPTS_BASE_DIR/"
  else
    info "Multi-AI templates: skipped"
  fi
}

# Download prompt templates, docs, and utility scripts into PROMPTS_BASE_DIR.
# Uses local files when running from a clone, remote download otherwise.
_download_prompts() {
  local base="$PROMPTS_BASE_DIR"
  local templates_dir="$base/templates"
  local docs_dir="$base/docs"
  local bin_dir="$base/bin"

  mkdir -p "$templates_dir" "$docs_dir" "$bin_dir"

  # Detect local clone
  local this_script="${BASH_SOURCE[0]:-}"
  local this_dir=""
  if [[ -n "$this_script" && "$this_script" != "-" ]]; then
    this_dir="$(cd "$(dirname "$this_script")" 2>/dev/null && pwd)"
  fi

  local use_local=false
  if [[ -n "$this_dir" && -d "$this_dir/docs/templates" ]]; then
    use_local=true
  fi

  # Prompt templates
  local tmpl
  for tmpl in brainstorm-prompt constitution-prompt prd-prompt research-prompt setup-claude-project setup-perplexity-space; do
    if $use_local; then
      cp "$this_dir/docs/templates/${tmpl}.md" "$templates_dir/${tmpl}.md" 2>/dev/null \
        && info "Copied: templates/${tmpl}.md" \
        || warn "Could not copy templates/${tmpl}.md"
    else
      curl -fsSL "$REPO_RAW_URL/docs/templates/${tmpl}.md" -o "$templates_dir/${tmpl}.md" 2>/dev/null \
        && info "Downloaded: templates/${tmpl}.md" \
        || warn "Could not download templates/${tmpl}.md"
    fi
  done

  # Multi-AI workflow guide
  if $use_local; then
    cp "$this_dir/docs/guides/multi-ai-workflow.md" "$docs_dir/multi-ai-workflow.md" 2>/dev/null \
      && info "Copied: docs/multi-ai-workflow.md" \
      || warn "Could not copy docs/guides/multi-ai-workflow.md"
  else
    curl -fsSL "$REPO_RAW_URL/docs/guides/multi-ai-workflow.md" -o "$docs_dir/multi-ai-workflow.md" 2>/dev/null \
      && info "Downloaded: docs/multi-ai-workflow.md" \
      || warn "Could not download docs/guides/multi-ai-workflow.md"
  fi

  # Utility scripts
  local scr
  for scr in export-spec import-spec; do
    if $use_local; then
      cp "$this_dir/scripts/${scr}.sh" "$bin_dir/${scr}.sh" 2>/dev/null \
        && info "Copied: bin/${scr}.sh" \
        || warn "Could not copy bin/${scr}.sh"
    else
      curl -fsSL "$REPO_RAW_URL/scripts/${scr}.sh" -o "$bin_dir/${scr}.sh" 2>/dev/null \
        && info "Downloaded: bin/${scr}.sh" \
        || warn "Could not download bin/${scr}.sh"
    fi
    chmod +x "$bin_dir/${scr}.sh" 2>/dev/null || true
  done

  success "Multi-AI templates installed: $base/"
}

# ==============================================================================
# Step 7: choose_agent_teams
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
# Step 8: choose_satori
# ==============================================================================

choose_satori() {
  printf "\n${BRIGHT_GREEN}── Satori MCP Gateway${RESET}\n\n"
  printf "  Satori routes tool calls to downstream MCP servers and captures session context.\n\n"
  ask "Install Satori? [y/N]:"
  local choice
  read -r choice </dev/tty
  case "$choice" in
    [yY]|[yY][eE][sS]) SATORI="yes"; success "Satori: will install" ;;
    *)                  SATORI="no";  info    "Satori: skipped" ;;
  esac
}

_write_satori_mcp_config() {
  local abs_path="$1"
  local settings_file

  if [[ -f "$SETTINGS_FILE" ]]; then
    settings_file="$SETTINGS_FILE"
  elif [[ -f "$HOME/.claude/settings.json" ]]; then
    settings_file="$HOME/.claude/settings.json"
  else
    warn "No Claude Code settings.json found — create one and add Satori manually:"
    printf "  ${DIM}{ \"mcpServers\": { \"satori\": { \"command\": \"node\", \"args\": [\"$abs_path\"] } } }${RESET}\n"
    return
  fi

  python3 - "$settings_file" "$abs_path" << 'PYEOF'
import json, sys
settings_file, abs_path = sys.argv[1], sys.argv[2]
with open(settings_file) as f:
    data = json.load(f)
data.setdefault("mcpServers", {})["satori"] = {
    "command": "node",
    "args": [abs_path]
}
with open(settings_file, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print("  Satori MCP entry written to " + settings_file)
PYEOF
}

# ==============================================================================
# Step 10: choose_statusline
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
# Step 11: confirm_summary
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
  printf "  %-22s %s  (written to %s)\n" "Docs base:" "$SPECS_DIR_NAME" "$toml_dir"

  if [[ "$PROMPTS" == "yes" ]]; then
    printf "  %-22s %s\n" "Multi-AI templates:" "$PROMPTS_BASE_DIR/"
  else
    printf "  %-22s %s\n" "Multi-AI templates:" "(skipped)"
  fi

  if [[ "$AGENT_TEAMS" == "yes" ]]; then
    printf "  %-22s %s\n" "Agent Teams:" "enabled"
  else
    printf "  %-22s %s\n" "Agent Teams:" "(skipped)"
  fi

  if [[ "$SATORI" == "yes" ]]; then
    printf "  %-22s %s\n" "Satori:" "install + build"
  else
    printf "  %-22s %s\n" "Satori:" "(skipped)"
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
# Step 12: do_install
# ==============================================================================

do_install() {
  printf "\n${BRIGHT_GREEN}── Installing${RESET}\n\n"

  # --- Detect local clone ------------------------------------------------------
  local this_script="${BASH_SOURCE[0]:-}"
  local this_dir=""
  if [[ -n "$this_script" && "$this_script" != "-" ]]; then
    this_dir="$(cd "$(dirname "$this_script")" 2>/dev/null && pwd)"
  fi
  local use_local_plugins=false
  if [[ -n "$this_dir" && -d "$this_dir/plugins" ]]; then
    use_local_plugins=true
  fi

  # --- Marketplace + plugins (always global) ----------------------------------
  if $use_local_plugins; then
    info "Local clone detected — installing plugins from local cache"
  else
    info "Configuring marketplace..."
    if claude plugin marketplace add "$MARKETPLACE" >/dev/null 2>&1; then
      success "Marketplace added"
    elif claude plugin marketplace update "$MARKETPLACE" >/dev/null 2>&1; then
      success "Marketplace updated"
    else
      success "Marketplace configured"
    fi
  fi

  # CLAUDE_HOME: where Claude stores settings and plugins
  local claude_home="$HOME/.claude"
  local plugins_cache="$claude_home/plugins/cache"
  local installed_json="$claude_home/plugins/installed_plugins.json"

  for plugin in $PLUGINS; do
    # Strip @marketplace suffix to get plugin name (e.g. tcs-start)
    local plugin_name="${plugin%@*}"
    local marketplace_name="${plugin#*@}"
    info "Installing $plugin_name..."
    if $use_local_plugins && [[ -d "$this_dir/plugins/$plugin_name" ]]; then
      # Read version from plugin.json
      local plugin_src="$this_dir/plugins/$plugin_name"
      local version
      version=$(jq -r '.version // "local"' "$plugin_src/.claude-plugin/plugin.json" 2>/dev/null || echo "local")

      # Copy into cache: ~/.claude/plugins/cache/<marketplace>/<name>/<version>/
      local cache_dest="$plugins_cache/$marketplace_name/$plugin_name/$version"
      mkdir -p "$cache_dest"
      cp -r "$plugin_src/." "$cache_dest/"
      rm -f "$cache_dest/.orphaned_at"

      # Register in installed_plugins.json
      if [[ ! -f "$installed_json" ]]; then
        echo '{"version":2,"plugins":{}}' > "$installed_json"
      fi
      local now; now=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
      local tmp; tmp=$(mktemp)
      jq --arg key "${plugin_name}@${marketplace_name}" \
         --arg path "$cache_dest" \
         --arg ver "$version" \
         --arg ts "$now" \
         '.plugins[$key] = [{"scope":"user","installPath":$path,"version":$ver,"installedAt":$ts,"lastUpdated":$ts}]' \
         "$installed_json" > "$tmp" && mv "$tmp" "$installed_json"

      # Add to enabledPlugins in settings.json
      local stmp; stmp=$(mktemp)
      jq --arg key "${plugin_name}@${marketplace_name}" \
         '.enabledPlugins = (.enabledPlugins // {}) + {($key): true}' \
         "$SETTINGS_FILE" > "$stmp" && mv "$stmp" "$SETTINGS_FILE"

      success "Plugin: $plugin_name (local, v$version)"
    else
      if claude plugin install "$plugin" >/dev/null 2>&1; then
        success "Plugin: $plugin"
      elif claude plugin update "$plugin" >/dev/null 2>&1; then
        success "Plugin: $plugin (updated)"
      else
        error "Failed to install $plugin"
        exit 2
      fi
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

  # Compute relative paths for prompts/bin (relative to toml_dir when possible)
  local prompts_rel=""
  local bin_rel=""
  if [[ "$PROMPTS" == "yes" ]]; then
    local rel="${PROMPTS_BASE_DIR#$toml_dir/}"
    if [[ "$rel" != "$PROMPTS_BASE_DIR" ]]; then
      prompts_rel="${rel}/templates"
      bin_rel="${rel}/bin"
    else
      prompts_rel="$PROMPTS_BASE_DIR/templates"
      bin_rel="$PROMPTS_BASE_DIR/bin"
    fi
  fi

  {
    printf '# The Custom Startup — Configuration\n'
    printf '# Generated by install.sh — edit freely.\n\n'
    printf '[tcs]\n'
    printf 'docs_base = "%s"\n' "$SPECS_DIR_NAME"
    if [[ "$PROMPTS" == "yes" ]]; then
      printf '\n[paths]\n'
      printf 'prompts_dir = "%s"\n' "$prompts_rel"
      printf 'bin_dir     = "%s"\n' "$bin_rel"
    fi
  } > "$toml_file"

  success "startup.toml written: $toml_file"

  # --- Multi-AI Templates -----------------------------------------------------
  if [[ "$PROMPTS" == "yes" ]]; then
    info "Installing Multi-AI templates..."
    _download_prompts
  fi

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

  # --- Satori -----------------------------------------------------------------
  if [[ "$SATORI" == "yes" ]]; then
    info "Initializing Satori submodule..."
    git submodule update --init modules/satori 2>/dev/null || true

    info "Building Satori..."
    local satori_dir
    if [[ -n "$this_dir" && -d "$this_dir/modules/satori" ]]; then
      satori_dir="$this_dir/modules/satori"
    else
      satori_dir="$(pwd)/modules/satori"
    fi

    if [[ ! -d "$satori_dir" ]]; then
      warn "Satori directory not found at $satori_dir — skipping"
    else
      (cd "$satori_dir" && npm install --silent && npm run build --silent) || {
        warn "Satori build failed — skipping MCP config"
        return
      }

      local satori_abs
      satori_abs="$(cd "$satori_dir" && pwd)/dist/src/index.js"

      info "Writing Satori MCP config entry..."
      _write_satori_mcp_config "$satori_abs"
      success "Satori installed: $satori_abs"

      # Context mode opt-in (only if Satori is present and built)
      if [[ -f "$satori_dir/scripts/install-hooks.sh" ]]; then
        printf "\n"
        ask "Enable context mode (session capture + memory hooks)? [y/N]:"
        local ctx_choice
        read -r ctx_choice </dev/tty
        case "$ctx_choice" in
          [yY]|[yY][eE][sS])
            info "Registering Satori hooks..."
            SATORI_HOOKS_SETTINGS="$SETTINGS_FILE" \
              bash "$satori_dir/scripts/install-hooks.sh" || warn "Hook registration failed — run install-hooks.sh manually"
            success "Context mode hooks registered"

            # Append [context] block to satori.toml if absent
            local toml_file
            if [[ "$TARGET" == "global" ]]; then
              toml_file="$HOME/.claude/satori.toml"
            else
              toml_file="$INSTALL_DIR/.claude/satori.toml"
            fi
            mkdir -p "$(dirname "$toml_file")"
            if [[ ! -f "$toml_file" ]] || ! grep -q '^\[context\]' "$toml_file" 2>/dev/null; then
              {
                printf '\n[context]\n'
                printf 'db_path                  = ".satori/db.sqlite"\n'
                printf 'session_guide_max_bytes  = 2048\n'
                printf 'retain_days              = 30\n'
              } >> "$toml_file"
              success "Context config written: $toml_file"
            else
              info "Context config already present in $toml_file"
            fi
            ;;
          *)
            info "Context mode: skipped"
            ;;
        esac
      fi
    fi
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
  choose_prompts
  choose_agent_teams
  choose_satori
  choose_statusline
  confirm_summary
  do_install
  print_completion
}

main "$@"
