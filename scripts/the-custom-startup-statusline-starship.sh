#!/bin/bash
#
# The Custom Startup — Starship Statusline Bridge
#
# Reads Claude Code JSON, exports fields as env vars, then calls `starship prompt`.
# Your existing ~/.config/starship.toml serves double duty — add the env_var modules
# documented below (or in a separate STARSHIP_CONFIG) for Claude-specific data.
#
# See docs/statusline-starship-reddit.md for full setup guide.
#
# Dependencies: starship, jq
# Input:        JSON from Claude Code via stdin
# Output:       Starship prompt output (raw ANSI, no shell escape wrappers)
#
# Quick setup:
#   1. Make executable: chmod +x the-custom-startup-statusline-starship.sh
#   2. Add env_var modules to ~/.config/starship.toml (see below or docs/)
#   3. Point Claude Code at this script in ~/.claude/settings.json:
#        { "statusLine": { "type": "command", "command": "/path/to/this/script" } }
#
# Starship modules to add to starship.toml:
# ─────────────────────────────────────────
#   [env_var.CLAUDE_MODEL]
#   variable = "CLAUDE_MODEL"
#   format   = "[\\[$env_value\\]]($style) "
#   style    = "bold cyan"
#
#   [env_var.CLAUDE_CONTEXT]
#   variable = "CLAUDE_CONTEXT"
#   format   = "[$env_value]($style) "
#   style    = "yellow"
#
#   [env_var.CLAUDE_SESSION]
#   variable = "CLAUDE_SESSION"
#   format   = "[$env_value]($style) "
#   style    = "purple"
#
#   [env_var.CLAUDE_COST]
#   variable = "CLAUDE_COST"
#   format   = "[$env_value]($style) "
#   style    = "green"
#
#   [env_var.CLAUDE_DURATION]
#   variable = "CLAUDE_DURATION"
#   format   = "[$env_value]($style)"
#   style    = "dimmed white"
#
# Add to your format string (append at end):
#   format = """...$all${env_var.CLAUDE_MODEL}${env_var.CLAUDE_CONTEXT}${env_var.CLAUDE_SESSION}${env_var.CLAUDE_COST}${env_var.CLAUDE_DURATION}"""
#
# Optional: use a separate starship config for a different statusline layout:
#   Set STARSHIP_CONFIG_FILE below to point at a dedicated config.

# Path to a dedicated starship config for the statusline (leave empty to use default)
STARSHIP_CONFIG_FILE=""

# ==============================================================================
# Read input
# ==============================================================================

input=$(cat)

# ==============================================================================
# Extract fields from Claude Code JSON
# ==============================================================================

export CLAUDE_MODEL
CLAUDE_MODEL=$(echo "$input" | jq -r '.model.display_name // "?"')

# Context window percentage (integer)
export CLAUDE_CONTEXT
CLAUDE_CONTEXT=$(printf '%s%%' "$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)")

# Session name (prefers /rename name, falls back to first 8 chars of session ID)
export CLAUDE_SESSION
CLAUDE_SESSION=$(echo "$input" | jq -r '.session_name // empty // (.session_id // "" | .[0:8])')

# Session cost
export CLAUDE_COST
CLAUDE_COST=$(printf '$%.2f' "$(echo "$input" | jq -r '.cost.total_cost_usd // 0')")

# Session duration
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
MINS=$(( DURATION_MS / 60000 ))
SECS=$(( (DURATION_MS % 60000) / 1000 ))
export CLAUDE_DURATION
if [[ "$MINS" -gt 0 ]]; then
  CLAUDE_DURATION="${MINS}m ${SECS}s"
else
  CLAUDE_DURATION="${SECS}s"
fi

# Lines changed
ADDED=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
REMOVED=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
export CLAUDE_LINES
CLAUDE_LINES="+${ADDED}/-${REMOVED}"

# ==============================================================================
# Invoke starship
# ==============================================================================

# STARSHIP_SHELL= suppresses shell-specific prompt escape wrappers (%{...%} / \[...\])
# Claude Code needs raw ANSI output, not shell prompt sequences.

if [[ -n "$STARSHIP_CONFIG_FILE" ]]; then
  STARSHIP_SHELL= STARSHIP_CONFIG="$STARSHIP_CONFIG_FILE" starship prompt
else
  STARSHIP_SHELL= starship prompt
fi
