#!/usr/bin/env bash
# parse-ts-settings.test.sh — pressure tests for parse-ts-settings.sh
# Bash 3.2 compatible.
#
# Temp dirs: created under /tmp/claude-501 (sandbox-safe path).
# mktemp -d is avoided because macOS sandboxes block it even with TMPDIR set.
#
# Usage: bash tests/parse-ts-settings.test.sh
# Exit: 0 if all scenarios pass; non-zero with failure count otherwise.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate script and fixtures
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
PARSER="$SKILL_ROOT/scripts/parse-ts-settings.sh"
FIXTURES="$SCRIPT_DIR/fixtures/ts-settings"

if [ ! -f "$PARSER" ]; then
  printf 'FATAL: parser not found: %s\n' "$PARSER" >&2
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

assert_exit_zero() {
  local label="$1" code="$2"
  if [ "$code" -eq 0 ]; then
    pass "$label"
  else
    fail "$label" "exit code was $code (expected 0)"
  fi
}

assert_exit_nonzero() {
  local label="$1" code="$2"
  if [ "$code" -ne 0 ]; then
    pass "$label"
  else
    fail "$label" "exit code was 0 (expected non-zero)"
  fi
}

# Run parser, capturing stdout and stderr separately.
# Sets PARSER_STDOUT, PARSER_STDERR, PARSER_EXIT.
_run_parser() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="/tmp"
  fi
  local tmpout="${base}/parse-ts-test-out-$$-${RANDOM}"
  local tmperr="${base}/parse-ts-test-err-$$-${RANDOM}"
  mkdir -p "$base"

  PARSER_EXIT=0
  bash "$PARSER" "$@" >"$tmpout" 2>"$tmperr" || PARSER_EXIT=$?
  PARSER_STDOUT="$(cat "$tmpout")"
  PARSER_STDERR="$(cat "$tmperr")"
  rm -f "$tmpout" "$tmperr"
}

# ---------------------------------------------------------------------------
# Scenario 1: Single interface with JSDoc — full TSV output
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: Single interface with JSDoc primitives → full TSV ---\n'

  _run_parser "$FIXTURES/single-interface.ts"

  assert_exit_zero "S1: exit code is 0" "$PARSER_EXIT"

  # Header line present
  assert_contains "S1: TSV header present" \
    "name	type	default	description" "$PARSER_STDOUT"

  # 'host' field — no default, has JSDoc
  assert_contains "S1: host name column" \
    "host	" "$PARSER_STDOUT"
  assert_contains "S1: host type is string" \
    "	string	" "$PARSER_STDOUT"
  assert_contains "S1: host description from JSDoc" \
    "The hostname of the server to connect to." "$PARSER_STDOUT"

  # 'port' field — default = 3000
  assert_contains "S1: port default is 3000" \
    "	3000	" "$PARSER_STDOUT"

  # 'verbose' field — default = false
  assert_contains "S1: verbose default is false" \
    "	false	" "$PARSER_STDOUT"

  # 'maxRetries' field — no default → empty default column
  local max_line
  max_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^maxRetries	' || true)"
  assert_not_contains "S1: maxRetries default column is empty" \
    "[NEEDS" "$max_line"

  # Verify 5 data rows (5 fields in single-interface.ts)
  local data_rows
  data_rows="$(printf '%s\n' "$PARSER_STDOUT" | grep -v '^name	' | grep -c '	' || true)"
  assert_eq "S1: 5 data rows" "5" "$data_rows"
}

# ---------------------------------------------------------------------------
# Scenario 2: No JSDoc → description is [NEEDS DESCRIPTION]
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: No JSDoc → [NEEDS DESCRIPTION] ---\n'

  _run_parser "$FIXTURES/no-jsdoc.ts"

  assert_exit_zero "S2: exit code is 0" "$PARSER_EXIT"
  assert_contains "S2: header present" "name	type	default	description" "$PARSER_STDOUT"

  # All three fields must have [NEEDS DESCRIPTION]
  local needs_desc_count
  needs_desc_count="$(printf '%s\n' "$PARSER_STDOUT" | grep -c '\[NEEDS DESCRIPTION\]' || true)"
  assert_eq "S2: all 3 fields get [NEEDS DESCRIPTION]" "3" "$needs_desc_count"

  # Never fabricated — must not contain human-looking descriptions
  assert_not_contains "S2: no fabricated description for host" \
    "hostname" "$PARSER_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 3: Union types emitted literally
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: Union types emitted literally ---\n'

  _run_parser "$FIXTURES/union-type.ts"

  assert_exit_zero "S3: exit code is 0" "$PARSER_EXIT"

  # logLevel: string | number
  assert_contains "S3: logLevel type is literal union" \
    "string | number" "$PARSER_STDOUT"

  # mode: "tcp" | "udp" | "ws"
  assert_contains "S3: mode type is literal string union" \
    '"tcp" | "udp" | "ws"' "$PARSER_STDOUT"

  # threshold: number | null with default 0
  assert_contains "S3: threshold union with default" \
    "	0	" "$PARSER_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 4: Multiple interfaces — Settings selected by default; others listed on stderr
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- Scenario 4: Multiple interfaces → Settings selected; all listed on stderr ---\n'

  _run_parser "$FIXTURES/multi-interface.ts"

  assert_exit_zero "S4: exit code is 0" "$PARSER_EXIT"

  # Should output Settings fields only (apiKey, requestTimeout)
  assert_contains "S4: apiKey field present" "apiKey	" "$PARSER_STDOUT"
  assert_contains "S4: requestTimeout field present" "requestTimeout	" "$PARSER_STDOUT"

  # InternalState fields must NOT appear in stdout
  assert_not_contains "S4: initialised NOT in stdout" "initialised" "$PARSER_STDOUT"
  assert_not_contains "S4: connectionCount NOT in stdout" "connectionCount" "$PARSER_STDOUT"

  # Both interface names listed on stderr
  assert_contains "S4: Settings listed on stderr" "Settings" "$PARSER_STDERR"
  assert_contains "S4: InternalState listed on stderr" "InternalState" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 4b: TS_INTERFACE_NAME override selects a non-default interface
# ---------------------------------------------------------------------------
scenario_4b() {
  printf '\n--- Scenario 4b: TS_INTERFACE_NAME=InternalState → selects non-default interface ---\n'

  TS_INTERFACE_NAME=InternalState _run_parser "$FIXTURES/multi-interface.ts"

  assert_exit_zero "S4b: exit code is 0" "$PARSER_EXIT"

  # Should output InternalState fields only
  assert_contains "S4b: initialised field present" "initialised	" "$PARSER_STDOUT"
  assert_contains "S4b: connectionCount field present" "connectionCount	" "$PARSER_STDOUT"

  # Settings fields must NOT appear
  assert_not_contains "S4b: apiKey NOT in stdout" "apiKey" "$PARSER_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 5: Complex/generic/mapped/intersection types → [NEEDS REVIEW] on stdout + stderr
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: Generics/mapped/intersection → [NEEDS REVIEW] ---\n'

  _run_parser "$FIXTURES/complex-types.ts"

  assert_exit_zero "S5: exit code is 0" "$PARSER_EXIT"

  # 'name' field (simple string) must parse fine — no [NEEDS REVIEW]
  local name_line
  name_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^name	' || true)"
  assert_not_contains "S5: name field parses cleanly" "[NEEDS REVIEW]" "$name_line"

  # Map<string, number> → [NEEDS REVIEW]
  local cache_line
  cache_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^cache	' || true)"
  assert_contains "S5: cache (generic) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$cache_line"

  # Intersection type → [NEEDS REVIEW]
  local config_line
  config_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^config	' || true)"
  assert_contains "S5: config (intersection) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$config_line"

  # Array<string> → [NEEDS REVIEW]
  local tags_line
  tags_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^tags	' || true)"
  assert_contains "S5: tags (Array generic) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$tags_line"

  # Plain string[] → NOT [NEEDS REVIEW]
  local labels_line
  labels_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^labels	' || true)"
  assert_not_contains "S5: labels (string[]) parses cleanly" "[NEEDS REVIEW]" "$labels_line"

  # Stderr should list NEEDS REVIEW hints
  assert_contains "S5: stderr has [NEEDS REVIEW] hint for cache" \
    "[NEEDS REVIEW]" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 6: Missing file → non-zero exit with error message
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- Scenario 6: Missing file → non-zero exit ---\n'

  _run_parser "/nonexistent/path/settings.ts"

  assert_exit_nonzero "S6: non-zero exit for missing file" "$PARSER_EXIT"
  assert_contains "S6: error message mentions file" "/nonexistent/path/settings.ts" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 7: File with no interface block → non-zero exit
# ---------------------------------------------------------------------------
scenario_7() {
  printf '\n--- Scenario 7: No interface block → non-zero exit ---\n'

  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="/tmp"
  fi
  local tmpfile="${base}/parse-ts-test-nointerface-$$-${RANDOM}.ts"
  printf 'export type Foo = string;\nconst x = 1;\n' > "$tmpfile"

  _run_parser "$tmpfile"
  rm -f "$tmpfile"

  assert_exit_nonzero "S7: non-zero exit for no interface block" "$PARSER_EXIT"
  assert_contains "S7: error message mentions no interface" "interface" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------
scenario_1
scenario_2
scenario_3
scenario_4
scenario_4b
scenario_5
scenario_6
scenario_7

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
