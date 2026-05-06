#!/usr/bin/env bash
# skeleton-structure.test.sh — structural inspection tests for T4.1 skeleton templates
# Bash 3.2 compatible.
#
# Verifies that each of the four skeleton templates:
#   1. Exists at the expected path.
#   2. Mentions every minimum page (installation, configuration, usage, troubleshooting).
#   3. Mentions docs/README.md (the index page requirement).
#   4. Contains type-specific extras:
#        tcs-plugin: "components" or "per-component reference"
#        python: "first command" or "quickstart"
#
# By-inspection tests — no executable output is parsed; assertions are
# plain grep checks on the Markdown content.
#
# Usage: bash tests/skeleton-structure.test.sh
# Exit: 0 if all checks pass; non-zero (fail count) otherwise.

set -uo pipefail

# ---------------------------------------------------------------------------
# Locate templates directory
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATES="$SKILL_ROOT/templates"

# ---------------------------------------------------------------------------
# Test harness (matches existing tests/ style)
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf 'PASS  %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf 'FAIL  %s — %s\n' "$1" "$2"
}

assert_file_exists() {
  local label="$1" path="$2"
  if [ -f "$path" ]; then
    pass "$label"
  else
    fail "$label" "file not found: $path"
  fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qiF "$needle"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle")"
  fi
}

# ---------------------------------------------------------------------------
# Helper: read a template file into a variable (Bash 3.2: no process sub)
# ---------------------------------------------------------------------------
read_template() {
  local path="$1"
  if [ -f "$path" ]; then
    # shellcheck disable=SC2155
    local content
    content="$(cat "$path")"
    printf '%s' "$content"
  else
    printf ''
  fi
}

# ---------------------------------------------------------------------------
# Shared: minimum page assertions (all four skeletons must pass these)
# ---------------------------------------------------------------------------
assert_minimum_pages() {
  local type="$1" content="$2"

  assert_contains "[$type] mentions installation" "installation" "$content"
  assert_contains "[$type] mentions configuration" "configuration" "$content"
  assert_contains "[$type] mentions usage" "usage" "$content"
  assert_contains "[$type] mentions troubleshooting" "troubleshooting" "$content"
}

assert_readme_index() {
  local type="$1" content="$2"

  assert_contains "[$type] mentions docs/README.md" "docs/README.md" "$content"
}

# ---------------------------------------------------------------------------
# Scenario: skeleton-obsidian.md
# ---------------------------------------------------------------------------
scenario_obsidian() {
  printf '\n--- Scenario: skeleton-obsidian.md ---\n'

  local path="$TEMPLATES/skeleton-obsidian.md"
  assert_file_exists "[obsidian] file exists" "$path"

  local content
  content="$(read_template "$path")"

  assert_minimum_pages "obsidian" "$content"
  assert_readme_index  "obsidian" "$content"

  # Obsidian-specific extras: settings reference or commands reference
  if printf '%s\n' "$content" | grep -qiF "settings reference" ||
     printf '%s\n' "$content" | grep -qiF "commands reference"; then
    pass "[obsidian] mentions settings reference or commands reference"
  else
    fail "[obsidian] mentions settings reference or commands reference" \
         "neither 'settings reference' nor 'commands reference' found"
  fi
}

# ---------------------------------------------------------------------------
# Scenario: skeleton-python.md
# ---------------------------------------------------------------------------
scenario_python() {
  printf '\n--- Scenario: skeleton-python.md ---\n'

  local path="$TEMPLATES/skeleton-python.md"
  assert_file_exists "[python] file exists" "$path"

  local content
  content="$(read_template "$path")"

  assert_minimum_pages "python" "$content"
  assert_readme_index  "python" "$content"

  # Python-specific extra: "first command" or "quickstart"
  if printf '%s\n' "$content" | grep -qiF "first command" ||
     printf '%s\n' "$content" | grep -qiF "quickstart"; then
    pass "[python] mentions first command or quickstart"
  else
    fail "[python] mentions first command or quickstart" \
         "neither 'first command' nor 'quickstart' found"
  fi
}

# ---------------------------------------------------------------------------
# Scenario: skeleton-tcs-plugin.md
# ---------------------------------------------------------------------------
scenario_tcs_plugin() {
  printf '\n--- Scenario: skeleton-tcs-plugin.md ---\n'

  local path="$TEMPLATES/skeleton-tcs-plugin.md"
  assert_file_exists "[tcs-plugin] file exists" "$path"

  local content
  content="$(read_template "$path")"

  assert_minimum_pages "tcs-plugin" "$content"
  assert_readme_index  "tcs-plugin" "$content"

  # TCS-plugin-specific extra: "components" or "per-component reference"
  if printf '%s\n' "$content" | grep -qiF "per-component reference" ||
     printf '%s\n' "$content" | grep -qiF "components"; then
    pass "[tcs-plugin] mentions per-component reference or components"
  else
    fail "[tcs-plugin] mentions per-component reference or components" \
         "neither 'per-component reference' nor 'components' found"
  fi
}

# ---------------------------------------------------------------------------
# Scenario: skeleton-generic.md
# ---------------------------------------------------------------------------
scenario_generic() {
  printf '\n--- Scenario: skeleton-generic.md ---\n'

  local path="$TEMPLATES/skeleton-generic.md"
  assert_file_exists "[generic] file exists" "$path"

  local content
  content="$(read_template "$path")"

  assert_minimum_pages "generic" "$content"
  assert_readme_index  "generic" "$content"
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------
scenario_obsidian
scenario_python
scenario_tcs_plugin
scenario_generic

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n========================================\n'
printf 'Results: %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
printf '========================================\n'

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit "$FAIL_COUNT"
fi
exit 0
