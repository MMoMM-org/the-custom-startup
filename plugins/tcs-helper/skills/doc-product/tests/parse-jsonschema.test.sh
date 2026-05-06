#!/usr/bin/env bash
# parse-jsonschema.test.sh — pressure tests for parse-jsonschema.sh
# Bash 3.2 compatible.
#
# Strategy:
#   - Fixture JSON Schema files live under tests/fixtures/jsonschema/.
#   - Missing-jq scenario: stub PATH dir containing bash but not jq.
#   - Sandbox-safe temp dirs under /tmp/claude-501 (mktemp -d avoided per harness pattern).
#
# Usage: bash tests/parse-jsonschema.test.sh
# Exit: 0 if all scenarios pass; non-zero with failure count otherwise.
#
# SC2030: subshell-local PATH modification in scenario_4 is intentional.
# SC2329: shellcheck cannot trace assert_eq/assert_contains through scenario
#         functions; they are invoked indirectly.
# shellcheck disable=SC2030,SC2329
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
PARSER="${SKILL_ROOT}/scripts/parse-jsonschema.sh"
FIXTURES="${SCRIPT_DIR}/fixtures/jsonschema"

if [ ! -f "$PARSER" ]; then
  printf 'FATAL: parser not found: %s\n' "$PARSER" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Sandbox-safe tempdir creation — matches existing harness pattern.
# mktemp -d is avoided because the macOS Claude Code sandbox blocks it.
# ---------------------------------------------------------------------------
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="/tmp"
  fi
  local d="${base}/parse-jsonschema-test-$$-${RANDOM}"
  mkdir -p "$d"
  printf '%s\n' "$d"
}

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

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass "$label"
  else
    fail "$label" "expected=$(printf '%q' "$expected") got=$(printf '%q' "$actual")"
  fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $needle"
  fi
}

assert_exit_code() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass "$label"
  else
    fail "$label" "expected exit $expected, got $actual"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 1: Happy path — properties / default / description → TSV rows
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: Happy path — properties with defaults and descriptions ---\n'

  local output exit_code
  exit_code=0
  output="$(bash "$PARSER" "${FIXTURES}/happy-path.json")" || exit_code=$?

  assert_exit_code "S1: exits 0" "0" "$exit_code"

  # Header row
  assert_contains "S1: TSV header present" "name	type	default	description" "$output"

  # port field
  assert_contains "S1: port row present" "port	integer	3000	The port the server listens on." "$output"

  # logLevel field — default is a JSON string so it should be quoted
  assert_contains "S1: logLevel row present" "logLevel	string	\"info\"	Logging verbosity level." "$output"

  # debug field — boolean false
  assert_contains "S1: debug row present" "debug	boolean	false	Enable debug output." "$output"
}

# ---------------------------------------------------------------------------
# Scenario 2: Missing description → [NEEDS DESCRIPTION]
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: Missing description → [NEEDS DESCRIPTION] marker ---\n'

  local output exit_code
  exit_code=0
  output="$(bash "$PARSER" "${FIXTURES}/missing-description.json")" || exit_code=$?

  assert_exit_code "S2: exits 0 even with missing description" "0" "$exit_code"

  # timeout has a description
  assert_contains "S2: timeout description present" "Request timeout in seconds." "$output"

  # retries has no description → marker
  assert_contains "S2: retries gets [NEEDS DESCRIPTION]" "[NEEDS DESCRIPTION]" "$output"
}

# ---------------------------------------------------------------------------
# Scenario 3: Enum constraint → type column format
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: enum field → type column captures enum values ---\n'

  local output exit_code
  exit_code=0
  output="$(bash "$PARSER" "${FIXTURES}/enum-field.json")" || exit_code=$?

  assert_exit_code "S3: exits 0" "0" "$exit_code"

  # size has no "type" key, only enum → type derived from enum values
  assert_contains "S3: size type column has enum prefix" 'enum: "small" | "medium" | "large"' "$output"

  # mode has both "type":"string" and "enum" → enum takes precedence
  assert_contains "S3: mode type column has enum prefix" 'enum: "light" | "dark"' "$output"
}

# ---------------------------------------------------------------------------
# Scenario 4: jq not on PATH → exit 2, ADR-5 error on stderr
#
# Strategy: build a stub PATH directory that contains bash (symlinked to the
# real bash) but NOT jq.  PATH="/var/empty" would also hide bash in this
# sandboxed environment (exit 127), so we use a controlled stub dir instead.
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- Scenario 4: jq not on PATH → ADR-5 missing-dependency error ---\n'

  # Build a stub dir: bash present, jq absent.
  local stub_dir
  stub_dir="$(_make_tmpdir)"
  ln -sf "$(command -v bash)" "${stub_dir}/bash"
  # Deliberately do NOT link jq.

  local stderr_out exit_code
  exit_code=0
  # SC2030: intentional subshell variable modification.
  # shellcheck disable=SC2030
  stderr_out="$(PATH="$stub_dir" bash "$PARSER" "${FIXTURES}/happy-path.json" 2>&1 >/dev/null)" \
    || exit_code=$?

  rm -rf "$stub_dir"

  assert_exit_code "S4: exits 2 when jq missing" "2" "$exit_code"

  assert_contains "S4: error line names jq"          "error: jq not found"                                                 "$stderr_out"
  assert_contains "S4: reason line explains why"     "reason: parsing JSON Schema requires jq for safe field extraction"   "$stderr_out"
  assert_contains "S4: install line gives brew cmd"  "brew install jq"                                                     "$stderr_out"
  assert_contains "S4: install line gives apt cmd"   "apt-get install jq"                                                  "$stderr_out"
}

# ---------------------------------------------------------------------------
# Scenario 5: Schema without top-level properties → exit 3, descriptive error
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: Schema has no top-level properties → exit 3, error on stderr ---\n'

  local stderr_out exit_code
  exit_code=0
  stderr_out="$(bash "$PARSER" "${FIXTURES}/no-properties.json" 2>&1 >/dev/null)" \
    || exit_code=$?

  assert_exit_code "S5: exits 3 for missing properties" "3" "$exit_code"

  assert_contains "S5: error mentions properties key" \
    'error: schema has no top-level "properties" object — cannot extract settings' \
    "$stderr_out"
}

# ---------------------------------------------------------------------------
# Scenario 6: File not found → exit 1, error on stderr
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- Scenario 6: File not found → exit 1 ---\n'

  local tmpdir stderr_out exit_code
  tmpdir="$(_make_tmpdir)"
  exit_code=0
  stderr_out="$(bash "$PARSER" "${tmpdir}/nonexistent.json" 2>&1 >/dev/null)" \
    || exit_code=$?
  rm -rf "$tmpdir"

  assert_exit_code "S6: exits 1 for missing file" "1" "$exit_code"
  assert_contains "S6: error names the file" "error: file not found:" "$stderr_out"
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
