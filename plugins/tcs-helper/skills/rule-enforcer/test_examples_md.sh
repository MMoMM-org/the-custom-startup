#!/usr/bin/env bash
# test_examples_md.sh — T2.5 validation: reference/examples.md content assertions
# RED before examples.md exists; GREEN after.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXAMPLES_FILE="$SCRIPT_DIR/reference/examples.md"

pass=0
fail=0

check() {
  local desc="$1"
  local result="$2"
  if [ "$result" = "0" ]; then
    echo "PASS: $desc"
    pass=$((pass + 1))
  else
    echo "FAIL: $desc"
    fail=$((fail + 1))
  fi
}

# A1: File exists
if [ -f "$EXAMPLES_FILE" ]; then
  check "examples.md exists" 0
else
  check "examples.md exists" 1
fi

# A2: At least 5 H3 sections matching "### Example"
h3_count=$(grep -c "^### Example" "$EXAMPLES_FILE" 2>/dev/null || echo 0)
if [ "$h3_count" -ge 5 ]; then
  check "at least 5 '### Example' H3 sections (found $h3_count)" 0
else
  check "at least 5 '### Example' H3 sections (found $h3_count)" 1
fi

# A3: Each of Q1 Q2 Q3 Q4 Mechanism appear at least 5 times (once per example)
for keyword in "Q1" "Q2" "Q3" "Q4" "Mechanism"; do
  count=$(grep -c "$keyword" "$EXAMPLES_FILE" 2>/dev/null || echo 0)
  if [ "$count" -ge 5 ]; then
    check "keyword '$keyword' appears >= 5 times (found $count)" 0
  else
    check "keyword '$keyword' appears >= 5 times (found $count)" 1
  fi
done

# A4: Example 1 mechanism references CI workflow
if grep -A 20 "^### Example 1" "$EXAMPLES_FILE" 2>/dev/null | grep -qi "CI workflow"; then
  check "Example 1 mechanism mentions CI workflow" 0
else
  check "Example 1 mechanism mentions CI workflow" 1
fi

# A5: Example 2 mechanism references pre-push
if grep -A 20 "^### Example 2" "$EXAMPLES_FILE" 2>/dev/null | grep -qi "pre-push"; then
  check "Example 2 mechanism mentions pre-push" 0
else
  check "Example 2 mechanism mentions pre-push" 1
fi

# A6: Example 3 mechanism references PostToolUse
if grep -A 20 "^### Example 3" "$EXAMPLES_FILE" 2>/dev/null | grep -qi "PostToolUse"; then
  check "Example 3 mechanism mentions PostToolUse" 0
else
  check "Example 3 mechanism mentions PostToolUse" 1
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
