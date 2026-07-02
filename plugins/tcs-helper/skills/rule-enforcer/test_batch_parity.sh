#!/usr/bin/env bash
# test_batch_parity.sh — T2.3 parity test (spec 016, Phase 2).
#
# Proves that batch mode's B5 matrix lookup produces the SAME mechanism the
# interactive flow documents in reference/examples.md, for each worked case.
#
# Each worked case documents a rule -> Q3 (bare label) + Q4 (Block/Auto-fix/Nudge)
# -> a mechanism. Interactive Step 6 and batch B5 resolve that mechanism the SAME
# way: locate the "## Q3 = <bare label>" section in reference/mechanism-matrix.md,
# then read the table row whose first column matches Q4. This test performs that
# exact lookup and asserts the result equals what examples.md documents for the
# case. A mismatch, an unknown Q3 label, or a missing Q4 row fails loudly.
#
# The (Q3,Q4) -> mechanism mapping lives ONLY in mechanism-matrix.md: this test
# READS the mechanism from the matrix (never hard-codes it independently) and
# READS the documented mechanism from examples.md, then compares the two by name.
#
# bash 3.2 compatible (repo guardrail): no mapfile, no `declare -A`, no process
# substitution.

set -eu

here="$(cd "$(dirname "$0")" && pwd)"
matrix="$here/reference/mechanism-matrix.md"
examples="$here/reference/examples.md"

pass=0
fail=0

check() {
  # $1 = description, $2 = result (0 = pass, anything else = fail)
  if [ "$2" = "0" ]; then
    echo "PASS: $1"
    pass=$((pass + 1))
  else
    echo "FAIL: $1"
    fail=$((fail + 1))
  fi
}

for f in "$matrix" "$examples"; do
  if [ ! -f "$f" ]; then
    echo "FAIL: missing required file: $f" >&2
    exit 1
  fi
done

# Same lookup batch B5 performs: inside the "## Q3 = <label>" section of the
# matrix, print the mechanism cell of the table row whose Q4 column equals <q4>.
lookup_matrix_mechanism() {
  awk -v label="$1" -v q4="$2" '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    /^## / {
      inside = ($0 == "## Q3 = " label) ? 1 : 0
      next
    }
    inside == 1 && /^\|/ {
      n = split($0, cell, "|")
      if (trim(cell[2]) == q4) { print trim(cell[3]); exit }
    }
  ' "$matrix"
}

# What examples.md documents as the mechanism for a given "### Example N: ..." heading.
lookup_examples_mechanism() {
  awk -v h="$1" '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    /^### / { inside = ($0 == h) ? 1 : 0; next }
    inside == 1 && /^\*\*Mechanism\*\*:/ {
      sub(/^\*\*Mechanism\*\*:[ \t]*/, "")
      print trim($0); exit
    }
  ' "$examples"
}

# The mechanism "name" is the head of the cell, before any parenthetical qualifier.
# The matrix uses generic descriptive parentheticals; examples.md uses concrete
# instance parentheticals. Both agree on the head, which is the mechanism identity.
head_of() {
  printf '%s' "${1%% (*}"
}

# assert_parity CASE  EXAMPLE_HEADING  Q3_LABEL  Q4  EXPECTED_NAME
#
# EXPECTED_NAME is the mechanism name read from examples.md (encoded here as the
# per-case anchor). The test then (a) confirms examples.md still documents that
# name, and (b) confirms the matrix lookup for (Q3,Q4) yields that same name —
# proving batch B5 == interactive Step 6.
assert_parity() {
  casename="$1"
  heading="$2"
  label="$3"
  q4="$4"
  expected="$5"

  # 1. Q3 bare label must be a real matrix heading.
  if ! grep -qF "## Q3 = ${label}" "$matrix"; then
    check "${casename}: Q3 label '${label}' is a matrix heading" 1
    return
  fi
  check "${casename}: Q3 label '${label}' is a matrix heading" 0

  # 2. The Q4 row must exist in that section, yielding a mechanism.
  matrix_mech="$(lookup_matrix_mechanism "$label" "$q4")"
  if [ -z "$matrix_mech" ]; then
    check "${casename}: Q4 row '${q4}' present under '## Q3 = ${label}'" 1
    return
  fi
  check "${casename}: Q4 row '${q4}' present under '## Q3 = ${label}'" 0
  matrix_name="$(head_of "$matrix_mech")"

  # 3. examples.md must document a mechanism for this case.
  ex_mech="$(lookup_examples_mechanism "$heading")"
  if [ -z "$ex_mech" ]; then
    check "${casename}: examples.md documents a Mechanism" 1
    return
  fi
  check "${casename}: examples.md documents a Mechanism" 0
  ex_name="$(head_of "$ex_mech")"

  # 4. examples.md-documented name must match the encoded expectation (grounding).
  if [ "$ex_name" = "$expected" ]; then
    check "${casename}: examples.md mechanism '${ex_name}' == expected '${expected}'" 0
  else
    check "${casename}: examples.md mechanism '${ex_name}' == expected '${expected}'" 1
  fi

  # 5. THE PARITY CLAIM: matrix lookup name == examples.md documented name.
  if [ "$matrix_name" = "$ex_name" ]; then
    check "${casename}: matrix B5 mechanism '${matrix_name}' == interactive/examples.md '${ex_name}'" 0
  else
    check "${casename}: matrix B5 mechanism '${matrix_name}' == interactive/examples.md '${ex_name}' (matrix cell: '${matrix_mech}')" 1
  fi
}

echo "== rule-enforcer batch/interactive parity (T2.3) =="

# --- The four matrix-resolved worked cases (examples 1-4) ---------------------
assert_parity \
  "Example 1 (marketplace bump)" \
  "### Example 1: Missing marketplace.json bump after plugin changes" \
  "PR/merge to main" "Auto-fix" "CI workflow"

assert_parity \
  "Example 2 (CHANGELOG/README)" \
  "### Example 2: Missing CHANGELOG/README update after shipping a feature" \
  "Local git push" "Nudge" "git pre-push hook"

assert_parity \
  "Example 3 (skill-author)" \
  "### Example 3: Forgetting to run skill-author after editing skills/" \
  "After Claude calls a tool" "Nudge" "Claude PostToolUse hook"

assert_parity \
  "Example 4 (break-system-packages)" \
  "### Example 4: Using --break-system-packages instead of venv on macOS" \
  "Before Claude calls a tool" "Block" "Claude PreToolUse hook"

# --- The Q1 short-circuit case (example 5) ------------------------------------
# Example 5 short-circuits at Q1 (Q3/Q4 skipped), so NO matrix lookup happens —
# batch mode must mirror interactive by NOT resolving through the matrix. Verify
# the documented short-circuit rather than a matrix cell.
ex5_heading="### Example 5: Forgetting the syntax for a specific CLI flag"
if grep -A 12 "^${ex5_heading}$" "$examples" | grep -q "skipped"; then
  check "Example 5 (CLI flag syntax): documents Q1 short-circuit (Q3/Q4 skipped, no matrix lookup)" 0
else
  check "Example 5 (CLI flag syntax): documents Q1 short-circuit (Q3/Q4 skipped, no matrix lookup)" 1
fi
ex5_mech="$(lookup_examples_mechanism "$ex5_heading")"
case "$ex5_mech" in
  "Not a rule"*)
    check "Example 5 (CLI flag syntax): mechanism is the 'Not a rule' fallback, not a matrix mechanism" 0
    ;;
  *)
    check "Example 5 (CLI flag syntax): mechanism is the 'Not a rule' fallback, not a matrix mechanism (got '${ex5_mech}')" 1
    ;;
esac

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
