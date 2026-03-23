#!/bin/bash
# find-agents.sh — Discover all installed Claude Code agents
#
# Searches:
#   1. ~/.claude/agents/           (personal agents, flat .md files)
#   2. ~/.claude/plugins/cache/*/*/*/agents/**/*.md  (plugin agents: marketplace/name/version/)
#
# Output: one line per agent, tab-separated: name<TAB>description
# Exit 0 always.

set -euo pipefail

# ── YAML helpers ─────────────────────────────────────────────────────────────

extract_frontmatter() {
  local file="$1"
  # awk: print lines strictly between first and second --- fences
  awk '
    /^---$/ { count++; next }
    count == 1 { print }
    count >= 2 { exit }
  ' "$file" | head -30
}

get_field() {
  local frontmatter="$1"
  local field="$2"
  printf '%s\n' "$frontmatter" \
    | grep "^${field}:" \
    | head -1 \
    | sed "s/^${field}:[ ]*//" \
    | tr -d "\"'"
}

# ── Deduplication state ───────────────────────────────────────────────────────

SEEN_NAMES=$(mktemp)
trap 'rm -f "$SEEN_NAMES"' EXIT

# ── Agent processor ───────────────────────────────────────────────────────────

process_file() {
  local file="$1"

  # Must be a regular file ending in .md
  [ -f "$file" ] || return 0

  local frontmatter
  frontmatter=$(extract_frontmatter "$file")

  local name description

  name=$(get_field "$frontmatter" "name")
  description=$(get_field "$frontmatter" "description")

  # Derive name from filename if not in frontmatter
  if [ -z "$name" ]; then
    name=$(basename "$file" .md)
  fi

  # Skip if both are empty
  if [ -z "$name" ] && [ -z "$description" ]; then
    return 0
  fi

  # Deduplicate: first occurrence wins
  if grep -qx "$name" "$SEEN_NAMES" 2>/dev/null; then
    return 0
  fi

  printf '%s\n' "$name" >> "$SEEN_NAMES"
  printf '%s\t%s\n' "$name" "$description"
}

# ── Search location 1: personal agents ───────────────────────────────────────

PERSONAL_DIR="$HOME/.claude/agents"

if [ -d "$PERSONAL_DIR" ]; then
  find "$PERSONAL_DIR" -maxdepth 1 -name "*.md" -type f \
    | sort \
    | while read -r file; do
        process_file "$file"
      done
fi

# ── Search location 2: plugin cache agents ────────────────────────────────────

PLUGIN_CACHE="$HOME/.claude/plugins/cache"

if [ -d "$PLUGIN_CACHE" ]; then
  find "$PLUGIN_CACHE" -path "*/agents/*.md" -type f \
    | sort \
    | while read -r file; do
        process_file "$file"
      done
fi

exit 0
