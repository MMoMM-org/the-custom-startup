#!/usr/bin/env bash
# conventions-structure.test.sh — structural inspection tests for T4.4 reference/conventions.md
# Bash 3.2 compatible.
#
# Verifies that reference/conventions.md:
#   1. Exists at the expected path.
#   2. Mentions all four minimum page types as headings or strong identifiers:
#      installation, configuration, usage, troubleshooting (case-insensitive).
#   3. Contains the phrase "must include" (case-insensitive) at least once per
#      page type — proving the checklist requirement is honoured.
#   4. Contains the literal phrase "How do I verify it works?" — the spec example
#      for the installation must-include checklist.
#   5. Contains at least four unordered Markdown list lines ("- ") — evidence of
#      the recommended section list per page type.
#
# By-inspection tests — no executable output is parsed; assertions are
# plain grep checks on the Markdown content.
#
# Usage: bash tests/conventions-structure.test.sh
# Exit: 0 if all checks pass; non-zero (fail count) otherwise.

set -uo pipefail
# set -e intentionally omitted — non-zero exits from grep/assert must not abort the harness.

# ---------------------------------------------------------------------------
# Locate reference directory
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
CONVENTIONS="$SKILL_ROOT/reference/conventions.md"

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
  # -i: case-insensitive match — headings may be capitalised.
  if printf '%s\n' "$haystack" | grep -qiF "$needle"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle")"
  fi
}

# assert_contains_literal performs a case-SENSITIVE fixed-string match.
assert_contains_literal() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    pass "$label"
  else
    fail "$label" "expected to contain literally: $(printf '%q' "$needle")"
  fi
}

# assert_min_count_of checks that a pattern appears at least N times.
# Uses -i for case-insensitive matching (consistent with assert_contains).
# Uses -e to avoid treating the needle as a flag (handles "- " safely).
assert_min_count_of() {
  local label="$1" needle="$2" min="$3" haystack="$4"
  local count
  count="$(printf '%s\n' "$haystack" | grep -icFe "$needle" || true)"
  if [ "$count" -ge "$min" ]; then
    pass "$label"
  else
    fail "$label" "expected at least $min occurrences of $(printf '%q' "$needle"), found $count"
  fi
}

# ---------------------------------------------------------------------------
# Helper: read a file into a variable (Bash 3.2: no process sub)
# ---------------------------------------------------------------------------
read_file() {
  local path="$1"
  if [ -f "$path" ]; then
    local content
    content="$(cat "$path")"
    printf '%s' "$content"
  else
    printf ''
  fi
}

# ---------------------------------------------------------------------------
# Scenario 1: File exists
# ---------------------------------------------------------------------------
scenario_file_exists() {
  printf '\n--- Scenario: file exists ---\n'
  assert_file_exists "conventions.md exists at reference/conventions.md" "$CONVENTIONS"
}

# ---------------------------------------------------------------------------
# Scenario 2: All four page types are named
# ---------------------------------------------------------------------------
scenario_page_types() {
  printf '\n--- Scenario: four minimum page types present ---\n'
  local content
  content="$(read_file "$CONVENTIONS")"

  assert_contains "[page-types] mentions installation"    "installation"    "$content"
  assert_contains "[page-types] mentions configuration"   "configuration"   "$content"
  assert_contains "[page-types] mentions usage"           "usage"           "$content"
  assert_contains "[page-types] mentions troubleshooting" "troubleshooting" "$content"
}

# ---------------------------------------------------------------------------
# Scenario 3: Each page type block contains "must include"
# (proven by at least 4 occurrences — one per page type)
# ---------------------------------------------------------------------------
scenario_must_include() {
  printf '\n--- Scenario: must include checklist present (at least 4 occurrences) ---\n'
  local content
  content="$(read_file "$CONVENTIONS")"

  assert_min_count_of \
    "[must-include] appears at least 4 times (one per page type)" \
    "must include" \
    4 \
    "$content"
}

# ---------------------------------------------------------------------------
# Scenario 4: Spec example phrase is present (case-sensitive, exact)
# ---------------------------------------------------------------------------
scenario_verify_phrase() {
  printf '\n--- Scenario: spec example phrase present ---\n'
  local content
  content="$(read_file "$CONVENTIONS")"

  assert_contains_literal \
    "[installation] contains 'How do I verify it works?'" \
    "How do I verify it works?" \
    "$content"
}

# ---------------------------------------------------------------------------
# Scenario 5: Unordered list lines present (at least 4 "- " lines)
# ---------------------------------------------------------------------------
scenario_list_lines() {
  printf '\n--- Scenario: unordered list lines present (at least 4) ---\n'
  local content
  content="$(read_file "$CONVENTIONS")"

  assert_min_count_of \
    "[list-lines] at least 4 unordered list items (\"- \")" \
    "- " \
    4 \
    "$content"
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------
scenario_file_exists
scenario_page_types
scenario_must_include
scenario_verify_phrase
scenario_list_lines

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
