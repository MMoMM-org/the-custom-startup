#!/usr/bin/env bash
# configuration-template.test.sh — assertions for T3.4 configuration template + golden file
# Bash 3.2 compatible.
#
# Tests:
#   a. templates/configuration-template.md exists
#   b. Template documents the four columns (Name, Type, Default, Description)
#   c. Template documents the three markers and the verbatim-preservation rule
#   d. Template includes a header section / intro paragraph placeholder
#   e. Golden file expected-configuration.md is non-empty and has four column headers
#   f. Golden file preserves all three markers from sample-settings.tsv verbatim
#
# Usage: bash tests/configuration-template.test.sh
# Exit: 0 if all assertions pass; non-zero with failure count otherwise.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate files
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE="$SKILL_ROOT/templates/configuration-template.md"
GOLDEN="$SCRIPT_DIR/fixtures/configuration/expected-configuration.md"

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

assert_file_exists() {
  local label="$1" path="$2"
  if [ -f "$path" ]; then
    pass "$label"
  else
    fail "$label" "file not found: $path"
  fi
}

assert_file_nonempty() {
  local label="$1" path="$2"
  if [ -s "$path" ]; then
    pass "$label"
  else
    fail "$label" "file is empty or missing: $path"
  fi
}

assert_file_contains() {
  local label="$1" needle="$2" path="$3"
  if grep -qF "$needle" "$path" 2>/dev/null; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle") in $path"
  fi
}

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass "$label"
  else
    fail "$label" "expected=$(printf '%q' "$expected") got=$(printf '%q' "$actual")"
  fi
}

# ---------------------------------------------------------------------------
# Assertion (a): template file exists
# ---------------------------------------------------------------------------
printf '\n--- (a) Template file exists ---\n'
assert_file_exists "a: templates/configuration-template.md exists" "$TEMPLATE"

# ---------------------------------------------------------------------------
# Assertion (b): template documents the four columns
# ---------------------------------------------------------------------------
printf '\n--- (b) Template documents four columns ---\n'
assert_file_contains "b: column Name documented"        "Name"        "$TEMPLATE"
assert_file_contains "b: column Type documented"        "Type"        "$TEMPLATE"
assert_file_contains "b: column Default documented"     "Default"     "$TEMPLATE"
assert_file_contains "b: column Description documented" "Description" "$TEMPLATE"

# ---------------------------------------------------------------------------
# Assertion (c): template documents the three markers + verbatim-preservation rule
# ---------------------------------------------------------------------------
printf '\n--- (c) Template documents three markers and verbatim-preservation rule ---\n'
assert_file_contains "c: [NEEDS DESCRIPTION] marker documented" "[NEEDS DESCRIPTION]" "$TEMPLATE"
assert_file_contains "c: [NEEDS REVIEW] marker documented"      "[NEEDS REVIEW]"      "$TEMPLATE"
assert_file_contains "c: [NEEDS DEFAULT] marker documented"     "[NEEDS DEFAULT]"     "$TEMPLATE"
assert_file_contains "c: verbatim rule documented"              "verbatim"            "$TEMPLATE"

# ---------------------------------------------------------------------------
# Assertion (d): template includes header section / intro paragraph placeholder
# ---------------------------------------------------------------------------
printf '\n--- (d) Template includes header / intro section ---\n'
assert_file_contains "d: template has H1 Configuration heading" "# Configuration" "$TEMPLATE"
assert_file_contains "d: template references intro section" "intro" "$TEMPLATE"

# ---------------------------------------------------------------------------
# Assertion (e): golden file is non-empty and has all four column headers
# ---------------------------------------------------------------------------
printf '\n--- (e) Golden file non-empty + four column headers ---\n'
assert_file_nonempty "e: expected-configuration.md is non-empty" "$GOLDEN"
assert_file_contains "e: golden has Name column header"        "| Name"        "$GOLDEN"
assert_file_contains "e: golden has Type column header"        "| Type"        "$GOLDEN"
assert_file_contains "e: golden has Default column header"     "| Default"     "$GOLDEN"
assert_file_contains "e: golden has Description column header" "| Description" "$GOLDEN"

# Assert column order: Name comes before Type comes before Default comes before Description
# We check by looking for the header row pattern in sequence.
if grep -qF "| Name | Type | Default | Description |" "$GOLDEN" 2>/dev/null; then
  pass "e: column order is Name → Type → Default → Description"
else
  fail "e: column order is Name → Type → Default → Description" \
    "header row not found with expected order in $GOLDEN"
fi

# ---------------------------------------------------------------------------
# Assertion (f): golden file preserves all three markers verbatim
# ---------------------------------------------------------------------------
printf '\n--- (f) Golden file preserves all three markers verbatim ---\n'
assert_file_contains "f: golden preserves [NEEDS DESCRIPTION]" "[NEEDS DESCRIPTION]" "$GOLDEN"
assert_file_contains "f: golden preserves [NEEDS REVIEW]"      "[NEEDS REVIEW]"      "$GOLDEN"
assert_file_contains "f: golden preserves [NEEDS DEFAULT]"     "[NEEDS DEFAULT]"     "$GOLDEN"

# ---------------------------------------------------------------------------
# Assertion (g): golden file data rows match TSV (count + per-name cells)
# ---------------------------------------------------------------------------
printf '\n--- (g) Golden file data rows match TSV ---\n'
row_count=$(grep -c '^| \`' "$GOLDEN" || true)
assert_eq "g: golden has 4 data rows" "4" "$row_count"
for name in apiKey timeout retryPolicy logLevel; do
  assert_file_contains "g: golden has \`$name\` cell" "| \`$name\` " "$GOLDEN"
done

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
