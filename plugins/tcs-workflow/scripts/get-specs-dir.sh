#!/bin/bash
# get-specs-dir.sh — resolve the configured specs directory
#
# Fallback chain (first match wins):
#   1. specs_dir from .claude/startup.toml in current working directory
#   2. specs_dir from ~/.claude/startup.toml
#   3. docs/XDD/specs            (default)
#
# Usage: scripts/get-specs-dir.sh
# Output: path string, no trailing slash, to stdout
# Exit: always 0

set -euo pipefail

# Parse a key from a TOML file. Handles both bare and quoted values.
# Usage: _parse_toml_key <file> <key>
# Returns the value or empty string if not found.
_parse_toml_key() {
  local file="$1"
  local key="$2"
  grep "^${key}[[:space:]]*=" "$file" \
    | sed 's/[^=]*=[[:space:]]*//' \
    | tr -d '"'"'" \
    | head -1
}

# Try to read specs_dir from a given toml file.
# Usage: _read_specs_dir_from_toml <toml_file>
# Prints the value and returns 0 on success, returns 1 if not found.
_read_specs_dir_from_toml() {
  local toml_file="$1"
  if [ ! -f "$toml_file" ]; then
    return 1
  fi
  local val
  val=$(_parse_toml_key "$toml_file" "specs_dir")
  if [ -n "$val" ]; then
    printf '%s' "$val"
    return 0
  fi
  return 1
}

main() {
  local specs_dir=""

  # 1. Project-local .claude/startup.toml
  local local_toml="$PWD/.claude/startup.toml"
  specs_dir=$(_read_specs_dir_from_toml "$local_toml") && {
    printf '%s\n' "$specs_dir"
    return 0
  }

  # 2. Global ~/.claude/startup.toml
  local global_toml="$HOME/.claude/startup.toml"
  specs_dir=$(_read_specs_dir_from_toml "$global_toml") && {
    printf '%s\n' "$specs_dir"
    return 0
  }

  # 3. docs/XDD/specs (default — always return something)
  printf '%s\n' "docs/XDD/specs"
  return 0
}

main
