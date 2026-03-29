#!/bin/bash
# get-specs-dir.sh — resolve the configured specs directory
#
# Reads [tcs] docs_base from startup.toml and appends /specs.
#
# Fallback chain (first match wins):
#   1. docs_base from .claude/startup.toml in current working directory
#   2. docs_base from ~/.claude/startup.toml
#   3. docs/XDD/specs             (if directory exists)
#   4. the-custom-startup/specs   (legacy, if directory exists)
#   5. .start/specs               (legacy, if directory exists)
#   6. docs/XDD/specs             (default — always returns something)
#
# Usage: scripts/get-specs-dir.sh
# Output: path string, no trailing slash, to stdout
# Exit: always 0

set -euo pipefail

# Extract docs_base from [tcs] section of a TOML file.
# Usage: _read_docs_base <toml_file>
# Prints the value and returns 0 on success, returns 1 if not found.
_read_docs_base() {
  local toml_file="$1"
  if [ ! -f "$toml_file" ]; then
    return 1
  fi
  local val
  val=$(sed -n '/^\[tcs\]/,/^\[/p' "$toml_file" \
    | grep '^docs_base[[:space:]]*=' \
    | head -1 \
    | sed 's/docs_base[[:space:]]*=[[:space:]]*//' \
    | tr -d '"'"'")
  if [ -n "$val" ]; then
    printf '%s' "$val"
    return 0
  fi
  return 1
}

main() {
  local docs_base=""

  # 1. Project-local .claude/startup.toml
  docs_base=$(_read_docs_base "$PWD/.claude/startup.toml") && {
    printf '%s\n' "$docs_base/specs"
    return 0
  }

  # 2. Global ~/.claude/startup.toml
  docs_base=$(_read_docs_base "$HOME/.claude/startup.toml") && {
    printf '%s\n' "$docs_base/specs"
    return 0
  }

  # 3. docs/XDD/specs (current default)
  if [ -d "$PWD/docs/XDD/specs" ]; then
    printf '%s\n' "docs/XDD/specs"
    return 0
  fi

  # 4. the-custom-startup/specs (legacy)
  if [ -d "$PWD/the-custom-startup/specs" ]; then
    printf '%s\n' "the-custom-startup/specs"
    return 0
  fi

  # 5. .start/specs (legacy)
  if [ -d "$PWD/.start/specs" ]; then
    printf '%s\n' ".start/specs"
    return 0
  fi

  # 6. Default
  printf '%s\n' "docs/XDD/specs"
  return 0
}

main
