#!/usr/bin/env bash
# plan-mode.test.sh — string-match assertions for modes/plan.md
# Bash 3.2 compatible.
#
# These tests verify that the modes/plan.md file:
#   - exists and is non-trivial (>100 lines)
#   - documents a prerequisites section
#   - references each of the 4 skeleton templates by filename
#   - documents repo-type detection (manifest.json, plugin.json, pyproject.toml)
#   - documents the unknown-manifest AskUserQuestion fallback
#   - documents diff logic with Keep / Replace / Merge choices
#   - documents propose-then-confirm workflow
#   - documents placeholder-only writes (placeholder + TODO)
#   - documents docs/README.md index creation
#   - documents that files are NEVER silently overwritten
#   - references the templates/ directory for skeleton location
#
# Usage: bash tests/plan-mode.test.sh
# Exit: 0 if all assertions pass; non-zero with failure count otherwise.
#
# Note: set -e is intentionally omitted (matching extract-mode.test.sh style) —
# individual test assertions must not short-circuit the full suite on failure.

set -uo pipefail

# ---------------------------------------------------------------------------
# Locate files
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
PLAN_MODE="$SKILL_ROOT/modes/plan.md"

if [ ! -f "$PLAN_MODE" ]; then
  printf 'FATAL: modes/plan.md not found: %s\n' "$PLAN_MODE" >&2
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
  if grep -qFe "$needle" < "$PLAN_MODE"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle")"
  fi
}

assert_line_count_gt() {
  local label="$1" min="$2"
  local actual
  actual="$(wc -l < "$PLAN_MODE" | tr -d ' ')"
  if [ "$actual" -gt "$min" ]; then
    pass "$label"
  else
    fail "$label" "expected >$min lines, got $actual"
  fi
}

# ---------------------------------------------------------------------------
# A1: File exists and is non-trivial (>100 lines)
# ---------------------------------------------------------------------------
assert_line_count_gt "A1: modes/plan.md has >100 lines" 100

# ---------------------------------------------------------------------------
# A2: Documents a prerequisites section
# ---------------------------------------------------------------------------
assert_contains "A2: prerequisites section present" "Prerequisites"

# ---------------------------------------------------------------------------
# A3: References each of the 4 skeleton templates by filename
# ---------------------------------------------------------------------------
assert_contains "A3: references skeleton-obsidian.md" "skeleton-obsidian.md"
assert_contains "A3: references skeleton-python.md" "skeleton-python.md"
assert_contains "A3: references skeleton-tcs-plugin.md" "skeleton-tcs-plugin.md"
assert_contains "A3: references skeleton-generic.md" "skeleton-generic.md"

# ---------------------------------------------------------------------------
# A4: Documents repo-type detection — known manifests named explicitly
# ---------------------------------------------------------------------------
assert_contains "A4: manifest.json named for detection" "manifest.json"
assert_contains "A4: plugin.json named for detection" "plugin.json"
assert_contains "A4: pyproject.toml named for detection" "pyproject.toml"

# ---------------------------------------------------------------------------
# A5: Documents the unknown-manifest fallback (AskUserQuestion + asks user)
# ---------------------------------------------------------------------------
assert_contains "A5: AskUserQuestion referenced for unknown manifest" "AskUserQuestion"
assert_contains "A5: asks user before proposing for unknown type" "ask"

# ---------------------------------------------------------------------------
# A6: Documents diff logic — Keep / Replace / Merge as per-page labels
# ---------------------------------------------------------------------------
assert_contains "A6: Keep choice documented" "Keep"
assert_contains "A6: Replace choice documented" "Replace"
assert_contains "A6: Merge choice documented" "Merge"

# ---------------------------------------------------------------------------
# A7: Documents propose-then-confirm (both words present)
# ---------------------------------------------------------------------------
assert_contains "A7: propose documented" "propose"
assert_contains "A7: confirm documented" "confirm"

# ---------------------------------------------------------------------------
# A8: Documents placeholder-only writes (both words present)
# ---------------------------------------------------------------------------
assert_contains "A8: placeholder documented" "placeholder"
assert_contains "A8: TODO documented" "TODO"

# ---------------------------------------------------------------------------
# A9: Documents docs/README.md index creation
# ---------------------------------------------------------------------------
assert_contains "A9: docs/README.md index documented" "docs/README.md"

# ---------------------------------------------------------------------------
# A10: Documents NEVER silently overwriting (never + overwrite)
# ---------------------------------------------------------------------------
assert_contains "A10: never overwrite stated" "never"
assert_contains "A10: overwrite mentioned" "overwrite"

# ---------------------------------------------------------------------------
# A11: References templates/ directory for skeleton location
# ---------------------------------------------------------------------------
assert_contains "A11: templates/ directory referenced" "templates/"

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
