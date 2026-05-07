#!/usr/bin/env bash
# extract-detection.test.sh — pressure tests for scripts/detect-source.sh
# Bash 3.2 compatible.
#
# Usage: bash tests/extract-detection.test.sh
# Exit: 0 if all scenarios pass; non-zero with failure count otherwise.

set -uo pipefail

# ---------------------------------------------------------------------------
# Locate script and fixtures
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
DETECTOR="$SKILL_ROOT/scripts/detect-source.sh"
FIXTURES="$SCRIPT_DIR/fixtures/extract"

if [ ! -f "$DETECTOR" ]; then
  printf 'FATAL: detect-source.sh not found: %s\n' "$DETECTOR" >&2
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
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $(printf '%q' "$needle")"
  fi
}

assert_not_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    fail "$label" "expected NOT to contain: $(printf '%q' "$needle")"
  else
    pass "$label"
  fi
}

assert_line_count() {
  local label="$1" expected="$2" output="$3"
  local actual
  if [ -z "$output" ]; then
    actual=0
  else
    actual="$(printf '%s\n' "$output" | grep -c '' || true)"
  fi
  if [ "$actual" -eq "$expected" ]; then
    pass "$label"
  else
    fail "$label" "expected $expected lines, got $actual"
  fi
}

assert_exit_zero() {
  local label="$1" code="$2"
  if [ "$code" -eq 0 ]; then
    pass "$label"
  else
    fail "$label" "exit code was $code (expected 0)"
  fi
}

# Run detector on a fixture dir, capturing stdout and exit code.
# Sets DETECTOR_STDOUT, DETECTOR_EXIT.
_run_detector() {
  local dir="$1"
  DETECTOR_EXIT=0
  DETECTOR_STDOUT="$(bash "$DETECTOR" "$dir" 2>/dev/null)" || DETECTOR_EXIT=$?
}

# ---------------------------------------------------------------------------
# Scenario 1: single-ts/ → one typescript line pointing at settings.ts
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: single-ts/ → typescript line ---\n'

  _run_detector "$FIXTURES/single-ts"

  assert_exit_zero "S1: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S1: exactly one line" 1 "$DETECTOR_STDOUT"
  assert_contains "S1: type is typescript" "typescript	" "$DETECTOR_STDOUT"
  assert_contains "S1: path contains settings.ts" "settings.ts" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 2: single-jsonschema/ → one jsonschema line pointing at schema.json
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: single-jsonschema/ → jsonschema line ---\n'

  if ! command -v jq >/dev/null 2>&1; then
    printf 'SKIP  S2: jq not available\n'
    return
  fi

  _run_detector "$FIXTURES/single-jsonschema"

  assert_exit_zero "S2: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S2: exactly one line" 1 "$DETECTOR_STDOUT"
  assert_contains "S2: type is jsonschema" "jsonschema	" "$DETECTOR_STDOUT"
  assert_contains "S2: path contains schema.json" "schema.json" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 3: single-pydantic/ → one pydantic line pointing at config.py
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: single-pydantic/ → pydantic line ---\n'

  _run_detector "$FIXTURES/single-pydantic"

  assert_exit_zero "S3: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S3: exactly one line" 1 "$DETECTOR_STDOUT"
  assert_contains "S3: type is pydantic" "pydantic	" "$DETECTOR_STDOUT"
  assert_contains "S3: path contains config.py" "config.py" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 4: multi-source/ → two lines (typescript + pydantic)
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- Scenario 4: multi-source/ → two lines (typescript + pydantic) ---\n'

  _run_detector "$FIXTURES/multi-source"

  assert_exit_zero "S4: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S4: exactly two lines" 2 "$DETECTOR_STDOUT"
  assert_contains "S4: typescript line present" "typescript	" "$DETECTOR_STDOUT"
  assert_contains "S4: pydantic line present" "pydantic	" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 5: no-source/ → zero lines (README only)
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: no-source/ → zero lines ---\n'

  _run_detector "$FIXTURES/no-source"

  assert_exit_zero "S5: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S5: zero lines" 0 "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 6: with-manifest-only/ → zero lines (manifests excluded)
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- Scenario 6: with-manifest-only/ → zero lines (manifests excluded) ---\n'

  _run_detector "$FIXTURES/with-manifest-only"

  assert_exit_zero "S6: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S6: zero lines" 0 "$DETECTOR_STDOUT"
  assert_not_contains "S6: manifest.json not emitted" "manifest.json" "$DETECTOR_STDOUT"
  assert_not_contains "S6: plugin.json not emitted" "plugin.json" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 7: with-manifest-and-source/ → one line (typescript only, manifest excluded)
# ---------------------------------------------------------------------------
scenario_7() {
  printf '\n--- Scenario 7: with-manifest-and-source/ → one typescript line (manifest excluded) ---\n'

  _run_detector "$FIXTURES/with-manifest-and-source"

  assert_exit_zero "S7: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S7: exactly one line" 1 "$DETECTOR_STDOUT"
  assert_contains "S7: typescript line present" "typescript	" "$DETECTOR_STDOUT"
  assert_not_contains "S7: plugin.json not emitted" "plugin.json" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 8: re-run-existing/ → one typescript line (docs/configuration.md ignored)
# ---------------------------------------------------------------------------
scenario_8() {
  printf '\n--- Scenario 8: re-run-existing/ → one typescript line ---\n'

  _run_detector "$FIXTURES/re-run-existing"

  assert_exit_zero "S8: exit code is 0" "$DETECTOR_EXIT"
  assert_line_count "S8: exactly one line" 1 "$DETECTOR_STDOUT"
  assert_contains "S8: typescript line present" "typescript	" "$DETECTOR_STDOUT"
  assert_not_contains "S8: configuration.md not emitted" "configuration.md" "$DETECTOR_STDOUT"
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------
scenario_1
scenario_2
scenario_3
scenario_4
scenario_5
scenario_6
scenario_7
scenario_8

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
