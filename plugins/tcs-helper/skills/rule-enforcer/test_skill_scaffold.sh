#!/usr/bin/env bash
# Structural assertion for rule-enforcer SKILL.md scaffold (T2.1)
# Usage: bash test_skill_scaffold.sh
# Exits 0 when all assertions pass, 1 on first failure.

set -uo pipefail

SKILL_FILE="$(dirname "$0")/SKILL.md"
PASS=0
FAIL=0
ERRORS=()

assert_check() {
  local description="$1"
  shift
  if "$@" 2>/dev/null; then
    echo "  PASS: $description"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $description"
    ERRORS+=("$description")
    FAIL=$((FAIL + 1))
  fi
}

echo "=== rule-enforcer SKILL.md structural assertions ==="
echo ""

# A1: File exists
assert_check "SKILL.md exists" test -f "$SKILL_FILE"

# A2: Frontmatter fence present (opening ---)
assert_check "Frontmatter opening --- present" grep -q "^---$" "$SKILL_FILE"

# A3: name: rule-enforcer
assert_check "Frontmatter name: rule-enforcer" grep -q "^name: rule-enforcer$" "$SKILL_FILE"

# A4: description field present (non-empty)
assert_check "Frontmatter description present (non-empty)" grep -qE "^description: .+" "$SKILL_FILE"

# A5: user-invocable: true
assert_check "Frontmatter user-invocable: true" grep -q "^user-invocable: true$" "$SKILL_FILE"

# A6: argument-hint present with expected value
assert_check 'Frontmatter argument-hint: "[rule description]"' grep -q 'argument-hint: "\[rule description\]"' "$SKILL_FILE"

# A7: ## Persona section
assert_check "## Persona section present" grep -q "^## Persona$" "$SKILL_FILE"

# A8: ## Interface section
assert_check "## Interface section present" grep -q "^## Interface$" "$SKILL_FILE"

# A9: ## Constraints section
assert_check "## Constraints section present" grep -q "^## Constraints$" "$SKILL_FILE"

# A10: ## Workflow section
assert_check "## Workflow section present" grep -q "^## Workflow$" "$SKILL_FILE"

# A11: Active skill announcement
assert_check "Active skill announcement: **Active skill: tcs-helper:rule-enforcer**" \
  grep -q "^\*\*Active skill: tcs-helper:rule-enforcer\*\*$" "$SKILL_FILE"

# A12: TriageState type defined in Interface
assert_check "TriageState type present in Interface" grep -q "TriageState" "$SKILL_FILE"

# A13: 8 workflow steps (numbered ### headings)
STEP_COUNT=$(grep -cE "^### [0-9]+\." "$SKILL_FILE" 2>/dev/null || echo 0)
assert_check "At least 8 numbered workflow steps (### N.) — found: $STEP_COUNT" test "$STEP_COUNT" -ge 8

# A14: Always/Never constraint lists
assert_check "**Always:** constraint list present" grep -q "^\*\*Always:\*\*$" "$SKILL_FILE"
assert_check "**Never:** constraint list present" grep -q "^\*\*Never:\*\*$" "$SKILL_FILE"

# A15: Line count within budget (hard ceiling: 120)
LINE_COUNT=$(wc -l < "$SKILL_FILE" 2>/dev/null || echo 0)
assert_check "SKILL.md line count within 120-line ceiling — found: $LINE_COUNT" test "$LINE_COUNT" -le 120

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo ""
  echo "Failed assertions:"
  for err in "${ERRORS[@]}"; do
    echo "  - $err"
  done
  exit 1
fi

exit 0
