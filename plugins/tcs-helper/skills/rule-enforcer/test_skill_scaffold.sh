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

# A15: Line count within budget (hard ceiling: 500)
LINE_COUNT=$(wc -l < "$SKILL_FILE" 2>/dev/null || echo 0)
assert_check "SKILL.md line count within 500-line budget — found: $LINE_COUNT" test "$LINE_COUNT" -le 500

# ── T2.3 additions ────────────────────────────────────────────────────────────

EXAMPLES_FILE="$(dirname "$0")/examples/output-example.md"

# A16: No remaining T2.3 placeholder comments
assert_check "SKILL.md has no remaining <!-- T2.3 will populate --> comments" \
  bash -c '! grep -q "T2.3 will populate" "$1"' _ "$SKILL_FILE"

# Helper: extract content lines from a step section (non-comment, non-empty, non-heading)
step_content_lines() {
  local step_num="$1"
  # Extract from the step heading to the next ### heading (or end of file)
  awk "/^### ${step_num}\\./{found=1; next} found && /^### /{exit} found" "$SKILL_FILE" \
    | grep -v "^[[:space:]]*$" \
    | grep -v "^<!--" \
    | grep -v "^###" \
    | wc -l | tr -d ' '
}

# A17: Step 1 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 1)
assert_check "Step 1 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A18: Step 2 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 2)
assert_check "Step 2 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A19: Step 3 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 3)
assert_check "Step 3 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A20: Step 4 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 4)
assert_check "Step 4 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A21: Step 5 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 5)
assert_check "Step 5 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A22: Step 6 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 6)
assert_check "Step 6 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A23: Step 7 has ≥ 3 lines of non-comment content
CNT=$(step_content_lines 7)
assert_check "Step 7 has ≥ 3 lines of non-comment content (found: $CNT)" test "$CNT" -ge 3

# A24: Step 2 mentions Q1 AND AskUserQuestion
assert_check "Step 2 mentions Q1 AND AskUserQuestion" \
  bash -c 'awk "/^### 2\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "Q1" && awk "/^### 2\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "AskUserQuestion"' _ "$SKILL_FILE"

# A25: Step 3 mentions Q2 AND AskUserQuestion
assert_check "Step 3 mentions Q2 AND AskUserQuestion" \
  bash -c 'awk "/^### 3\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "Q2" && awk "/^### 3\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "AskUserQuestion"' _ "$SKILL_FILE"

# A26: Step 4 mentions Q3 AND AskUserQuestion
assert_check "Step 4 mentions Q3 AND AskUserQuestion" \
  bash -c 'awk "/^### 4\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "Q3" && awk "/^### 4\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "AskUserQuestion"' _ "$SKILL_FILE"

# A27: Step 5 mentions Q4 AND AskUserQuestion
assert_check "Step 5 mentions Q4 AND AskUserQuestion" \
  bash -c 'awk "/^### 5\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "Q4" && awk "/^### 5\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "AskUserQuestion"' _ "$SKILL_FILE"

# A28: Step 6 mentions mechanism-matrix
assert_check "Step 6 mentions mechanism-matrix" \
  bash -c 'awk "/^### 6\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "mechanism-matrix"' _ "$SKILL_FILE"

# A29: Step 7 mentions AskUserQuestion
assert_check "Step 7 mentions AskUserQuestion" \
  bash -c 'awk "/^### 7\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "AskUserQuestion"' _ "$SKILL_FILE"

# A30: examples/output-example.md exists with ≥ 4 scenario headings
SCENARIO_COUNT=$(grep -cE "^(##|###) Scenario" "$EXAMPLES_FILE" 2>/dev/null || echo 0)
assert_check "examples/output-example.md exists with ≥ 4 scenario headings (found: $SCENARIO_COUNT)" \
  bash -c 'test -f "$1" && test "$(grep -cE "^(##|###) Scenario" "$1" 2>/dev/null || echo 0)" -ge 4' _ "$EXAMPLES_FILE"

# ── T2.4 additions ────────────────────────────────────────────────────────────

# A31: Step 8 has no remaining T2.4 placeholder
assert_check "Step 8 has no remaining <!-- T2.4 will populate --> placeholder" \
  bash -c '! grep -q "T2.4 will populate" "$1"' _ "$SKILL_FILE"

# A32: Step 8 mentions tcs-helper:skill-author
assert_check "Step 8 mentions tcs-helper:skill-author" \
  bash -c 'awk "/^### 8\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "tcs-helper:skill-author"' _ "$SKILL_FILE"

# A33: Step 8 mentions plugin-dev:hook-development
assert_check "Step 8 mentions plugin-dev:hook-development" \
  bash -c 'awk "/^### 8\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "plugin-dev:hook-development"' _ "$SKILL_FILE"

# A34: Step 8 mentions tcs-helper:memory-add
assert_check "Step 8 mentions tcs-helper:memory-add" \
  bash -c 'awk "/^### 8\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "tcs-helper:memory-add"' _ "$SKILL_FILE"

# A35: Step 8 mentions deferral to Phase 3 (CI / pre-push)
assert_check "Step 8 mentions deferral to Phase 3" \
  bash -c 'awk "/^### 8\./{found=1; next} found && /^### /{exit} found" "$1" | grep -q "Phase 3"' _ "$SKILL_FILE"

# A36: Step 8 has a fallback path (Install plugin or fallback or missing)
assert_check "Step 8 has a fallback path (Install plugin / fallback / missing)" \
  bash -c 'awk "/^### 8\./{found=1; next} found && /^### /{exit} found" "$1" | grep -qE "Install plugin|fallback|missing"' _ "$SKILL_FILE"

# A37: output-example.md has >= 7 scenario headings
SCENARIO_COUNT=$(grep -cE "^(##|###) Scenario" "$EXAMPLES_FILE" 2>/dev/null || echo 0)
assert_check "examples/output-example.md has ≥ 7 scenario headings (found: $SCENARIO_COUNT)" \
  bash -c 'test -f "$1" && test "$(grep -cE "^(##|###) Scenario" "$1" 2>/dev/null || echo 0)" -ge 7' _ "$EXAMPLES_FILE"

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
