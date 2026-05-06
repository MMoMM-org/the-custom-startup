#!/usr/bin/env bash
# extract-mode.test.sh — string-match assertions for modes/extract.md
# Bash 3.2 compatible.
#
# These tests verify that the modes/extract.md file:
#   - exists and is non-trivial (>100 lines)
#   - documents prerequisites
#   - references detect-source.sh
#   - documents the dispatch table
#   - documents multi-source / no-source AskUserQuestion flows
#   - documents diff logic
#   - documents manifest-ignore rule
#   - documents NEVER auto-overwriting docs/configuration.md
#   - references templates/configuration-template.md
#   - documents marker preservation
#
# Usage: bash tests/extract-mode.test.sh
# Exit: 0 if all assertions pass; non-zero with failure count otherwise.

set -uo pipefail

# ---------------------------------------------------------------------------
# Locate files
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
EXTRACT_MODE="$SKILL_ROOT/modes/extract.md"

if [ ! -f "$EXTRACT_MODE" ]; then
  printf 'FATAL: modes/extract.md not found: %s\n' "$EXTRACT_MODE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Test harness
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

assert_contains() {
  local label="$1" needle="$2"
  if grep -qFe "$needle" < "$EXTRACT_MODE"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle")"
  fi
}

assert_line_count_gt() {
  local label="$1" min="$2"
  local actual
  actual="$(wc -l < "$EXTRACT_MODE" | tr -d ' ')"
  if [ "$actual" -gt "$min" ]; then
    pass "$label"
  else
    fail "$label" "expected >$min lines, got $actual"
  fi
}

# ---------------------------------------------------------------------------
# A1: File exists and is non-trivial (>100 lines)
# ---------------------------------------------------------------------------
assert_line_count_gt "A1: modes/extract.md has >100 lines" 100

# ---------------------------------------------------------------------------
# A2: Documents prerequisites (parser scripts, branch check)
# ---------------------------------------------------------------------------
assert_contains "A2: prerequisites section present" "Prerequisites"
assert_contains "A2: references parse-ts-settings.sh" "parse-ts-settings.sh"
assert_contains "A2: references parse-jsonschema.sh" "parse-jsonschema.sh"
assert_contains "A2: references parse-pydantic.sh" "parse-pydantic.sh"

# ---------------------------------------------------------------------------
# A3: References detect-source.sh for source detection
# ---------------------------------------------------------------------------
assert_contains "A3: references detect-source.sh" "detect-source.sh"

# ---------------------------------------------------------------------------
# A4: Documents dispatch table (typescript → parse-ts-settings.sh etc.)
# ---------------------------------------------------------------------------
assert_contains "A4: dispatch typescript → parse-ts-settings" "typescript"
assert_contains "A4: dispatch jsonschema → parse-jsonschema" "jsonschema"
assert_contains "A4: dispatch pydantic → parse-pydantic" "pydantic"

# ---------------------------------------------------------------------------
# A5: Documents multi-source AskUserQuestion flow
# ---------------------------------------------------------------------------
assert_contains "A5: AskUserQuestion for multi-source" "AskUserQuestion"
assert_contains "A5: multi-source described" "2+"

# ---------------------------------------------------------------------------
# A6: Documents no-source AskUserQuestion flow
# ---------------------------------------------------------------------------
assert_contains "A6: no-source (0 sources) flow described" "0 source"

# ---------------------------------------------------------------------------
# A7: Documents diff logic (git diff --no-index or equivalent)
# ---------------------------------------------------------------------------
assert_contains "A7: git diff mentioned" "git diff"
assert_contains "A7: --no-index flag mentioned" "--no-index"

# ---------------------------------------------------------------------------
# A8: Documents manifest-ignore rule with explicit file names
# ---------------------------------------------------------------------------
assert_contains "A8: manifest.json explicitly named" "manifest.json"
assert_contains "A8: plugin.json explicitly named" "plugin.json"

# ---------------------------------------------------------------------------
# A9: Documents NEVER auto-overwriting docs/configuration.md
# ---------------------------------------------------------------------------
assert_contains "A9: no silent overwrite stated" "overwrite"
assert_contains "A9: docs/configuration.md referenced" "docs/configuration.md"

# ---------------------------------------------------------------------------
# A10: References templates/configuration-template.md for rendering
# ---------------------------------------------------------------------------
assert_contains "A10: references configuration-template.md" "configuration-template.md"

# ---------------------------------------------------------------------------
# A11: Documents marker preservation (NEEDS DESCRIPTION / NEEDS REVIEW / NEEDS DEFAULT)
# ---------------------------------------------------------------------------
assert_contains "A11: NEEDS DESCRIPTION marker documented" "[NEEDS DESCRIPTION]"
assert_contains "A11: NEEDS REVIEW marker documented" "[NEEDS REVIEW]"
assert_contains "A11: NEEDS DEFAULT marker documented" "[NEEDS DEFAULT]"
assert_contains "A11: verbatim preservation mentioned" "verbatim"

# ---------------------------------------------------------------------------
# A12: v1 manifest behaviour is its own section
# ---------------------------------------------------------------------------
assert_contains "A12: v1 manifest section present" "v1"

# ---------------------------------------------------------------------------
# A13: Source detection section references REPO_ROOT
# ---------------------------------------------------------------------------
assert_contains "A13: REPO_ROOT variable referenced" "REPO_ROOT"

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
