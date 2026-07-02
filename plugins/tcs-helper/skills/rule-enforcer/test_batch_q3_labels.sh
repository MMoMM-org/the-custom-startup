#!/usr/bin/env bash
# test_batch_q3_labels.sh — label-drift guard for rule-enforcer batch mode (spec 016, ADR-4).
#
# Batch mode's B5 step looks up mechanisms by matching an inferred Q3 label against the
# "## Q3 = <label>" section headings in mechanism-matrix.md (the SSOT). The set of labels
# batch mode may emit is declared in reference/extraction-heuristics.md inside a
# <!-- Q3-LABELS-START -->...<!-- Q3-LABELS-END --> block. If those two drift apart, the
# lookup silently returns "mechanism not found". This test fails loudly on any drift.
#
# bash 3.2 compatible (repo guardrail): no mapfile, no process substitution, no associative arrays.

set -eu

here="$(cd "$(dirname "$0")" && pwd)"
matrix="$here/reference/mechanism-matrix.md"
heur="$here/reference/extraction-heuristics.md"

fail=0

for f in "$matrix" "$heur"; do
  if [ ! -f "$f" ]; then
    echo "FAIL: missing required file: $f" >&2
    exit 1
  fi
done

# Extract the declared Q3 labels (lines between the markers, excluding the marker lines).
labels="$(sed -n '/<!-- Q3-LABELS-START -->/,/<!-- Q3-LABELS-END -->/p' "$heur" \
  | grep -v 'Q3-LABELS-START' | grep -v 'Q3-LABELS-END')"

if [ -z "$labels" ]; then
  echo "FAIL: no Q3 labels found between markers in $heur" >&2
  exit 1
fi

count=0
# Read line-by-line (bash 3.2 safe). Each non-empty label must exist as a matrix heading.
while IFS= read -r label; do
  [ -z "$label" ] && continue
  count=$((count + 1))
  if ! grep -qF "## Q3 = ${label}" "$matrix"; then
    echo "FAIL: Q3 label not found as a matrix heading: '${label}'" >&2
    fail=1
  fi
done <<EOF
$labels
EOF

# Guard against silent truncation: the matrix defines exactly 7 Q3 buckets.
matrix_count="$(grep -c '^## Q3 = ' "$matrix")"
if [ "$count" -ne "$matrix_count" ]; then
  echo "FAIL: label count mismatch — heuristics declares ${count}, matrix defines ${matrix_count}" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "test_batch_q3_labels: FAILED" >&2
  exit 1
fi

echo "test_batch_q3_labels: OK (${count} Q3 labels aligned with matrix headings)"
exit 0
