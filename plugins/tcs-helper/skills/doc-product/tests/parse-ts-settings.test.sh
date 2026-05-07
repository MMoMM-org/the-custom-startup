#!/usr/bin/env bash
# parse-ts-settings.test.sh — pressure tests for parse-ts-settings.sh
# Bash 3.2 compatible.
#
# Temp dirs: created under $TMPDIR (sandbox-safe).
#
# Usage: bash tests/parse-ts-settings.test.sh
# Exit: 0 if all scenarios pass; non-zero with failure count otherwise.
#
# Fixture validity note: all .ts fixtures in tests/fixtures/ts-settings/ are
# valid TypeScript (no TS1246 / TS1128 errors). Validate with:
#   tsc --noEmit --strict --target ES2020 --lib ES2020 <fixture.ts>
# using the TypeScript compiler from any nearby Node project
# (e.g. obsidian-archivist/node_modules/.bin/tsc).

set -uo pipefail

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

assert_exit_code() {
  local label="$1" expected_code="$2" actual_code="$3"
  if [ "$actual_code" -eq "$expected_code" ]; then
    pass "$label"
  else
    fail "$label" "exit code was $actual_code (expected $expected_code)"
  fi
}

# Run parser, capturing stdout and stderr separately.
# Sets PARSER_STDOUT, PARSER_STDERR, PARSER_EXIT.
_run_parser() {
  local tmpout tmperr
  tmpout="$(mktemp "${TMPDIR:-/tmp}/parse-ts-test-out.XXXXXX")"
  tmperr="$(mktemp "${TMPDIR:-/tmp}/parse-ts-test-err.XXXXXX")"

  PARSER_EXIT=0
  bash "$PARSER" "$@" >"$tmpout" 2>"$tmperr" || PARSER_EXIT=$?
  PARSER_STDOUT="$(cat "$tmpout")"
  PARSER_STDERR="$(cat "$tmperr")"
  rm -f "$tmpout" "$tmperr"
}

# ---------------------------------------------------------------------------
# Scenario 1: paired-simple.ts — paired interface+const → full TSV
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: paired-simple.ts — paired interface+const → full TSV ---\n'

  _run_parser "$FIXTURES/paired-simple.ts"

  assert_exit_zero "S1: exit code is 0" "$PARSER_EXIT"

  assert_contains "S1: TSV header present" \
    "name	type	default	description" "$PARSER_STDOUT"

  # foo field
  assert_contains "S1: foo name column" "foo	" "$PARSER_STDOUT"
  assert_contains "S1: foo type is string" "	string	" "$PARSER_STDOUT"
  assert_contains "S1: foo default is hello" "	'hello'	" "$PARSER_STDOUT"
  assert_contains "S1: foo description from JSDoc" "Description for foo." "$PARSER_STDOUT"

  # bar field
  assert_contains "S1: bar name column" "bar	" "$PARSER_STDOUT"
  assert_contains "S1: bar type is number" "	number	" "$PARSER_STDOUT"
  assert_contains "S1: bar default is 5" "	5	" "$PARSER_STDOUT"
  assert_contains "S1: bar description from JSDoc" "Description for bar." "$PARSER_STDOUT"

  # Neither field should have [NEEDS DEFAULT] or [NEEDS DESCRIPTION]
  assert_not_contains "S1: no NEEDS DEFAULT markers" "[NEEDS DEFAULT]" "$PARSER_STDOUT"
  assert_not_contains "S1: no NEEDS DESCRIPTION markers" "[NEEDS DESCRIPTION]" "$PARSER_STDOUT"

  # Exactly 2 data rows (header + 2 fields)
  local data_rows
  data_rows="$(printf '%s\n' "$PARSER_STDOUT" | grep -v '^name	' | grep -c '	' || true)"
  assert_eq "S1: 2 data rows" "2" "$data_rows"
}

# ---------------------------------------------------------------------------
# Scenario 2: missing-default.ts — const missing one field → [NEEDS DEFAULT]
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: missing-default.ts — const missing one field → [NEEDS DEFAULT] ---\n'

  _run_parser "$FIXTURES/missing-default.ts"

  assert_exit_zero "S2: exit code is 0" "$PARSER_EXIT"

  # host and port have defaults
  assert_contains "S2: host default is localhost" "	'localhost'	" "$PARSER_STDOUT"
  assert_contains "S2: port default is 8080" "	8080	" "$PARSER_STDOUT"

  # timeout has no default in const
  local timeout_line
  timeout_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^timeout	' || true)"
  assert_contains "S2: timeout default is [NEEDS DEFAULT]" "[NEEDS DEFAULT]" "$timeout_line"

  # Exactly 3 data rows
  local data_rows
  data_rows="$(printf '%s\n' "$PARSER_STDOUT" | grep -v '^name	' | grep -c '	' || true)"
  assert_eq "S2: 3 data rows" "3" "$data_rows"

  # Exactly 1 [NEEDS DEFAULT] marker
  local needs_default_count
  needs_default_count="$(printf '%s\n' "$PARSER_STDOUT" | grep -c '\[NEEDS DEFAULT\]' || true)"
  assert_eq "S2: exactly 1 [NEEDS DEFAULT] marker" "1" "$needs_default_count"
}

# ---------------------------------------------------------------------------
# Scenario 3: no-jsdoc.ts — no JSDoc → [NEEDS DESCRIPTION] for all fields
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: no-jsdoc.ts — no JSDoc → [NEEDS DESCRIPTION] for all fields ---\n'

  _run_parser "$FIXTURES/no-jsdoc.ts"

  assert_exit_zero "S3: exit code is 0" "$PARSER_EXIT"
  assert_contains "S3: header present" "name	type	default	description" "$PARSER_STDOUT"

  # All 4 fields have [NEEDS DESCRIPTION]
  local needs_desc_count
  needs_desc_count="$(printf '%s\n' "$PARSER_STDOUT" | grep -c '\[NEEDS DESCRIPTION\]' || true)"
  assert_eq "S3: all 4 fields get [NEEDS DESCRIPTION]" "4" "$needs_desc_count"

  # Const defaults are present
  assert_contains "S3: host default from const" "	'localhost'	" "$PARSER_STDOUT"
  assert_contains "S3: port default from const" "	8080	" "$PARSER_STDOUT"
  assert_contains "S3: verbose default from const" "	false	" "$PARSER_STDOUT"
  assert_contains "S3: tags default from const" "	[]	" "$PARSER_STDOUT"

  # tags is a plain array; should not have [NEEDS REVIEW]
  local tags_line
  tags_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^tags	' || true)"
  assert_not_contains "S3: tags plain array not [NEEDS REVIEW]" "[NEEDS REVIEW]" "$tags_line"

  # No fabricated descriptions
  assert_not_contains "S3: no fabricated description text" "hostname" "$PARSER_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 4: union-type.ts — union types emitted literally; defaults from const
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- Scenario 4: union-type.ts — union types emitted literally ---\n'

  _run_parser "$FIXTURES/union-type.ts"

  assert_exit_zero "S4: exit code is 0" "$PARSER_EXIT"

  # logLevel: string | number
  assert_contains "S4: logLevel type is literal union" \
    "string | number" "$PARSER_STDOUT"
  # Default from const
  assert_contains "S4: logLevel default from const" \
    "	'info'	" "$PARSER_STDOUT"

  # mode: 'small' | 'medium' | 'large'
  assert_contains "S4: mode type captures literal union" \
    "'small' | 'medium' | 'large'" "$PARSER_STDOUT"
  # Default from const
  assert_contains "S4: mode default from const" \
    "	'medium'	" "$PARSER_STDOUT"

  # threshold: number | null — not [NEEDS REVIEW]
  local threshold_line
  threshold_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^threshold	' || true)"
  assert_not_contains "S4: threshold union not [NEEDS REVIEW]" "[NEEDS REVIEW]" "$threshold_line"
  assert_contains "S4: threshold default from const" "	0	" "$PARSER_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 5: multi-interface.ts — Settings selected by default; both listed on stderr
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: multi-interface.ts — Settings selected by default ---\n'

  _run_parser "$FIXTURES/multi-interface.ts"

  assert_exit_zero "S5: exit code is 0" "$PARSER_EXIT"

  # Settings fields present
  assert_contains "S5: apiKey field present" "apiKey	" "$PARSER_STDOUT"
  assert_contains "S5: requestTimeout field present" "requestTimeout	" "$PARSER_STDOUT"

  # Defaults from DEFAULT_SETTINGS const
  assert_contains "S5: apiKey default from const" "	''	" "$PARSER_STDOUT"
  assert_contains "S5: requestTimeout default from const" "	5000	" "$PARSER_STDOUT"

  # InternalState fields NOT in stdout
  assert_not_contains "S5: initialised NOT in stdout" "initialised" "$PARSER_STDOUT"
  assert_not_contains "S5: connectionCount NOT in stdout" "connectionCount" "$PARSER_STDOUT"

  # Both interface names listed on stderr (prefixed format)
  assert_contains "S5: Settings listed on stderr" "Settings" "$PARSER_STDERR"
  assert_contains "S5: InternalState listed on stderr" "InternalState" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 5b: TS_INTERFACE_NAME=InternalState override
# ---------------------------------------------------------------------------
scenario_5b() {
  printf '\n--- Scenario 5b: TS_INTERFACE_NAME=InternalState → selects non-default interface ---\n'

  TS_INTERFACE_NAME=InternalState _run_parser "$FIXTURES/multi-interface.ts"

  assert_exit_zero "S5b: exit code is 0" "$PARSER_EXIT"

  assert_contains "S5b: initialised field present" "initialised	" "$PARSER_STDOUT"
  assert_contains "S5b: connectionCount field present" "connectionCount	" "$PARSER_STDOUT"

  # Defaults from DEFAULT_INTERNAL_STATE const
  assert_contains "S5b: initialised default from const" "	false	" "$PARSER_STDOUT"
  assert_contains "S5b: connectionCount default from const" "	0	" "$PARSER_STDOUT"

  # Settings fields NOT in stdout
  assert_not_contains "S5b: apiKey NOT in stdout" "apiKey" "$PARSER_STDOUT"

  # Both interfaces still listed on stderr
  assert_contains "S5b: Settings listed on stderr" "Settings" "$PARSER_STDERR"
  assert_contains "S5b: InternalState listed on stderr" "InternalState" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 6: no-const.ts — interface only, no DEFAULT_* const → all [NEEDS DEFAULT]
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- Scenario 6: no-const.ts — no DEFAULT_* const → all [NEEDS DEFAULT] ---\n'

  _run_parser "$FIXTURES/no-const.ts"

  assert_exit_zero "S6: exit code is 0" "$PARSER_EXIT"

  assert_contains "S6: header present" "name	type	default	description" "$PARSER_STDOUT"

  # All 3 fields get [NEEDS DEFAULT]
  local needs_default_count
  needs_default_count="$(printf '%s\n' "$PARSER_STDOUT" | grep -c '\[NEEDS DEFAULT\]' || true)"
  assert_eq "S6: all 3 fields get [NEEDS DEFAULT]" "3" "$needs_default_count"

  # JSDoc descriptions still appear
  assert_contains "S6: host description present" "The server host." "$PARSER_STDOUT"
  assert_contains "S6: port description present" "The server port." "$PARSER_STDOUT"
  assert_contains "S6: debug description present" "Enable debug logging." "$PARSER_STDOUT"
}

# ---------------------------------------------------------------------------
# Scenario 7: unparseable.ts — generics/keyof/intersection → [NEEDS REVIEW]
# ---------------------------------------------------------------------------
scenario_7() {
  printf '\n--- Scenario 7: unparseable.ts — generics/keyof/intersection → [NEEDS REVIEW] ---\n'

  _run_parser "$FIXTURES/unparseable.ts"

  assert_exit_zero "S7: exit code is 0" "$PARSER_EXIT"

  # 'name' field (simple string) must parse cleanly
  local name_line
  name_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^name	' || true)"
  assert_not_contains "S7: name field parses cleanly" "[NEEDS REVIEW]" "$name_line"
  assert_contains "S7: name type is string" "	string	" "$name_line"

  # 'metadata: Record<string, unknown>' → [NEEDS REVIEW]
  local metadata_line
  metadata_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^metadata	' || true)"
  assert_contains "S7: metadata (generic) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$metadata_line"

  # 'sortKey: keyof Foo' → [NEEDS REVIEW]
  local sortkey_line
  sortkey_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^sortKey	' || true)"
  assert_contains "S7: sortKey (keyof) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$sortkey_line"

  # 'config: BaseConfig & ExtendedConfig' → [NEEDS REVIEW]
  local config_line
  config_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^config	' || true)"
  assert_contains "S7: config (intersection) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$config_line"

  # 'mappedProp: { [K in MappedKeys]: string }' → [NEEDS REVIEW]
  local mapped_line
  mapped_line="$(printf '%s\n' "$PARSER_STDOUT" | grep '^mappedProp	' || true)"
  assert_contains "S7: mappedProp (mapped type) gets [NEEDS REVIEW]" "[NEEDS REVIEW]" "$mapped_line"

  # stderr lists the unparseable fields' original type expressions
  assert_contains "S7: stderr lists [NEEDS REVIEW] hints" "[NEEDS REVIEW]" "$PARSER_STDERR"
  assert_contains "S7: stderr mentions metadata" "metadata" "$PARSER_STDERR"
  assert_contains "S7: stderr mentions sortKey or keyof" "sortKey" "$PARSER_STDERR"
  assert_contains "S7: stderr mentions config intersection" "config" "$PARSER_STDERR"
  assert_contains "S7: stderr mentions mappedProp or mapped type" "mappedProp" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 8: Missing file → exit 1
# ---------------------------------------------------------------------------
scenario_8() {
  printf '\n--- Scenario 8: Missing file → exit 1 ---\n'

  _run_parser "/nonexistent/path/settings.ts"

  assert_exit_code "S8: exit code is 1" "1" "$PARSER_EXIT"
  assert_contains "S8: error message mentions file" "/nonexistent/path/settings.ts" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Scenario 9: File with no interface block → exit 2
# ---------------------------------------------------------------------------
scenario_9() {
  printf '\n--- Scenario 9: No interface block → exit 2 ---\n'

  local tmpfile
  tmpfile="$(mktemp "${TMPDIR:-/tmp}/parse-ts-test-nointerface.XXXXXX.ts")"
  printf 'export type Foo = string;\nconst x = 1;\n' > "$tmpfile"

  _run_parser "$tmpfile"
  rm -f "$tmpfile"

  assert_exit_code "S9: exit code is 2" "2" "$PARSER_EXIT"
  assert_contains "S9: error message mentions interface" "interface" "$PARSER_STDERR"
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------
scenario_1
scenario_2
scenario_3
scenario_4
scenario_5
scenario_5b
scenario_6
scenario_7
scenario_8
scenario_9

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
