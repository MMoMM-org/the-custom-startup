#!/usr/bin/env bash
# write-mode.test.sh — string-match assertions for modes/write.md
# Bash 3.2 compatible.
#
# These tests verify that the modes/write.md file:
#   - exists and is non-trivial (>100 lines)
#   - documents a prerequisites section
#   - documents invocation /claude-docs write <page> with example page names
#   - references reference/conventions.md as the section-structure source
#   - documents section-structure proposal then confirmation (propose + confirm)
#   - documents per-section drafting (section 1 / first section / one section at a time)
#   - documents AskUserQuestion for missing source-of-truth + no-fabrication rule
#   - documents preservation of prior approved sections during iteration
#   - documents the 3-iteration "can anything be removed?" rule
#   - documents non-existent-page handling (plan-mode route OR clear error)
#   - documents the no-fabrication contract
#   - documents the discover → document → review pattern (or in-house equivalent)
#
# Usage: bash tests/write-mode.test.sh
# Exit: 0 if all assertions pass; non-zero with failure count otherwise.
#
# Note: set -e is intentionally omitted (matching plan-mode.test.sh style) —
# individual test assertions must not short-circuit the full suite on failure.

set -uo pipefail

# ---------------------------------------------------------------------------
# Locate files
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
WRITE_MODE="$SKILL_ROOT/modes/write.md"

if [ ! -f "$WRITE_MODE" ]; then
  printf 'FATAL: modes/write.md not found: %s\n' "$WRITE_MODE" >&2
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
  if grep -qFe "$needle" < "$WRITE_MODE"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle")"
  fi
}

assert_icontains() {
  # Case-insensitive search for when word-form may vary
  local label="$1" needle="$2"
  if grep -qi "$needle" < "$WRITE_MODE"; then
    pass "$label"
  else
    fail "$label" "expected to contain (case-insensitive): $(printf '%q' "$needle")"
  fi
}

assert_line_count_gt() {
  local label="$1" min="$2"
  local actual
  actual="$(wc -l < "$WRITE_MODE" | tr -d ' ')"
  if [ "$actual" -gt "$min" ]; then
    pass "$label"
  else
    fail "$label" "expected >$min lines, got $actual"
  fi
}

# ---------------------------------------------------------------------------
# A1: File exists and is non-trivial (>100 lines)
# ---------------------------------------------------------------------------
assert_line_count_gt "A1: modes/write.md has >100 lines" 100

# ---------------------------------------------------------------------------
# A2: Documents a prerequisites section
# ---------------------------------------------------------------------------
assert_contains "A2: prerequisites section present" "Prerequisites"

# ---------------------------------------------------------------------------
# A3: Documents invocation /claude-docs write <page> with example page names
#     At least one of: installation, configuration, usage, troubleshooting
# ---------------------------------------------------------------------------
assert_contains "A3: invocation /claude-docs write documented" "/claude-docs write"
# At least one concrete page name example must appear
if grep -qFe "installation" < "$WRITE_MODE" || \
   grep -qFe "configuration" < "$WRITE_MODE" || \
   grep -qFe "usage" < "$WRITE_MODE" || \
   grep -qFe "troubleshooting" < "$WRITE_MODE"; then
  pass "A3: at least one example page name present (installation/configuration/usage/troubleshooting)"
else
  fail "A3: at least one example page name present" "none of installation|configuration|usage|troubleshooting found"
fi

# ---------------------------------------------------------------------------
# A4: References reference/conventions.md as the section-structure source
# ---------------------------------------------------------------------------
assert_contains "A4: reference/conventions.md referenced" "reference/conventions.md"

# ---------------------------------------------------------------------------
# A5: Documents section-structure proposal then confirmation
#     Both 'propose' AND 'confirm' must appear
# ---------------------------------------------------------------------------
assert_contains "A5: propose documented" "propose"
assert_contains "A5: 'confirm before drafting' gate present" "confirm before drafting"

# ---------------------------------------------------------------------------
# A6: Documents per-section drafting
#     At least one of: "section 1", "first section", "one section at a time"
# ---------------------------------------------------------------------------
if grep -qFe "section 1" < "$WRITE_MODE" || \
   grep -qFe "first section" < "$WRITE_MODE" || \
   grep -qFe "one section at a time" < "$WRITE_MODE"; then
  pass "A6: per-section drafting documented (section 1 / first section / one section at a time)"
else
  fail "A6: per-section drafting documented" "none of 'section 1'|'first section'|'one section at a time' found"
fi

# ---------------------------------------------------------------------------
# A7: Documents AskUserQuestion for missing source-of-truth + no-fabrication
#     Both 'AskUserQuestion' AND a no-fabrication phrase must appear
# ---------------------------------------------------------------------------
assert_contains "A7: AskUserQuestion referenced for missing info" "AskUserQuestion"
# no-fabrication: accept "do not fabricate", "never fabricate", "NEVER fabricate", or "no fabrication"
if grep -qFe "do not fabricate" < "$WRITE_MODE" || \
   grep -qFe "never fabricate" < "$WRITE_MODE" || \
   grep -qFe "NEVER fabricate" < "$WRITE_MODE" || \
   grep -qFe "no fabrication" < "$WRITE_MODE" || \
   grep -qFe "No fabrication" < "$WRITE_MODE"; then
  pass "A7: no-fabrication rule documented"
else
  fail "A7: no-fabrication rule documented" "none of 'do not fabricate'|'never fabricate'|'NEVER fabricate'|'no fabrication' found"
fi

# ---------------------------------------------------------------------------
# A8: Documents preservation of prior approved sections during iteration
#     Both "preserve" (or "preserved") AND "approved" must appear
# ---------------------------------------------------------------------------
if grep -qFe "preserve" < "$WRITE_MODE" || grep -qFe "preserved" < "$WRITE_MODE"; then
  pass "A8: preserve/preserved documented"
else
  fail "A8: preserve/preserved documented" "neither 'preserve' nor 'preserved' found"
fi
assert_contains "A8: approved documented" "approved"

# ---------------------------------------------------------------------------
# A9: Documents the 3-iteration "can anything be removed?" rule
#     Both a count ("3" or "three") AND "remove" must appear
# ---------------------------------------------------------------------------
assert_contains "A9: '3 iterations' rule present" "3 iterations"
assert_contains "A9: remove mentioned for iteration gate" "remove"

# ---------------------------------------------------------------------------
# A10: Documents non-existent-page handling
#      Either "plan mode" (route to plan) OR a clear error reference for missing page
# ---------------------------------------------------------------------------
if grep -qFe "plan mode" < "$WRITE_MODE" || \
   grep -qFe "does not exist" < "$WRITE_MODE" || \
   grep -qFe "not found" < "$WRITE_MODE" || \
   grep -qFe "missing" < "$WRITE_MODE"; then
  pass "A10: non-existent-page handling documented (plan mode route or error)"
else
  fail "A10: non-existent-page handling documented" "none of 'plan mode'|'does not exist'|'not found'|'missing' found"
fi

# ---------------------------------------------------------------------------
# A11: Documents the no-fabrication contract (dedicated section or callout)
#      The word "fabricate" must appear (any case)
# ---------------------------------------------------------------------------
assert_icontains "A11: fabricate appears (no-fabrication contract)" "fabricate"

# ---------------------------------------------------------------------------
# A12: Documents the discover → document → review pattern
#      Accept: all three words present; OR an explicit in-house equivalent
# ---------------------------------------------------------------------------
DISCOVER_OK=false
DOCUMENT_OK=false
REVIEW_OK=false
grep -qFe "discover" < "$WRITE_MODE" && DISCOVER_OK=true
grep -qFe "document" < "$WRITE_MODE" && DOCUMENT_OK=true
grep -qFe "review" < "$WRITE_MODE" && REVIEW_OK=true

if [ "$DISCOVER_OK" = "true" ] && [ "$DOCUMENT_OK" = "true" ] && [ "$REVIEW_OK" = "true" ]; then
  pass "A12: discover → document → review pattern documented (all three words present)"
else
  fail "A12: discover → document → review pattern" \
    "missing: discover=$DISCOVER_OK document=$DOCUMENT_OK review=$REVIEW_OK"
fi

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
