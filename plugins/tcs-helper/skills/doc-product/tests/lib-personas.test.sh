#!/usr/bin/env bash
# lib-personas.test.sh — pressure tests for lib-personas.sh
# Bash 3.2 compatible.
#
# REPO_ROOT_OVERRIDE: export this to a temp dir to bypass git rev-parse.
# The test runner sets this automatically per scenario via a temp dir
# containing a minimal .claude/doc-personas.md (or not).
#
# Temp dirs: created under /tmp/claude-501 (sandbox-safe path).
# mktemp -d is avoided because macOS sandboxes block it even with TMPDIR set.
#
# Usage: bash tests/lib-personas.test.sh
# Exit: 0 if all scenarios pass; non-zero with failure count otherwise.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate library and skill root
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
LIB="$SKILL_ROOT/scripts/lib-personas.sh"
FIXTURES="$SCRIPT_DIR/fixtures"
DEFAULT_PERSONAS="$SKILL_ROOT/templates/personas-default.md"

if [ ! -f "$LIB" ]; then
  printf 'FATAL: library not found: %s\n' "$LIB" >&2
  exit 1
fi

# Sandbox-safe temp dir creation. Uses /tmp/claude-501 as base (always writable
# in this environment). Falls back to /tmp if base does not exist.
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="/tmp"
  fi
  local d="${base}/lib-personas-test-$$-${RANDOM}"
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

# ---------------------------------------------------------------------------
# Scenario 1: No override file — use defaults verbatim
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: No override file → defaults verbatim ---\n'

  local tmpdir
  tmpdir="$(_make_tmpdir)"
  export REPO_ROOT_OVERRIDE="$tmpdir"

  # shellcheck disable=SC1090,SC1091
  source "$LIB"

  local active_file
  active_file="$(resolve_personas_file)"
  assert_eq "S1: resolve_personas_file returns default path" \
    "$DEFAULT_PERSONAS" "$active_file"

  local ids count
  ids="$(list_persona_ids "$active_file")"
  count="$(printf '%s\n' "$ids" | grep -c '.' || true)"
  assert_eq "S1: default has 4 personas" "4" "$count"

  assert_contains "S1: first-time-installer present" "first-time-installer" "$ids"
  assert_contains "S1: config-explorer present"      "config-explorer"      "$ids"
  assert_contains "S1: troubleshooter present"       "troubleshooter"       "$ids"
  assert_contains "S1: migrator present"             "migrator"             "$ids"

  rm -rf "$tmpdir"
  unset REPO_ROOT_OVERRIDE
}

# ---------------------------------------------------------------------------
# Scenario 2: Override-replace fixture (3 personas, no extends:)
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: Override-replace (no extends:) → replace entirely ---\n'

  local tmpdir
  tmpdir="$(_make_tmpdir)"
  mkdir -p "$tmpdir/.claude"
  cp "$FIXTURES/override-replace.md" "$tmpdir/.claude/doc-personas.md"
  export REPO_ROOT_OVERRIDE="$tmpdir"

  # shellcheck disable=SC1090,SC1091
  source "$LIB"

  if personas_extends_defaults; then
    fail "S2: personas_extends_defaults returns false for replace fixture" \
      "returned true, expected false"
  else
    pass "S2: personas_extends_defaults returns false for replace fixture"
  fi

  local result ids count result_file
  result="$(resolve_active_persona_set)"
  # Write to a temp file so list_persona_ids (from the library) can parse it.
  # This avoids re-implementing the awk persona-id extractor inline.
  result_file="$(_make_tmpdir)/resolved.yaml"
  printf '%s\n' "$result" > "$result_file"
  ids="$(list_persona_ids "$result_file")"
  count="$(printf '%s\n' "$ids" | grep -c '.' || true)"
  assert_eq "S2: resolve_active_persona_set emits 3 personas" "3" "$count"

  assert_contains "S2: new-user persona present"    "new-user"    "$ids"
  assert_contains "S2: power-user persona present"  "power-user"  "$ids"
  assert_contains "S2: contributor persona present" "contributor" "$ids"

  if printf '%s\n' "$ids" | grep -qxF "first-time-installer"; then
    fail "S2: first-time-installer absent from replace result" \
      "default persona leaked into replace output"
  else
    pass "S2: first-time-installer absent from replace result"
  fi

  rm -rf "$tmpdir"
  unset REPO_ROOT_OVERRIDE
}

# ---------------------------------------------------------------------------
# Scenario 3: Override-extends fixture (extends: defaults + overrides migrator + adds api-consumer)
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: Override-extends → defaults merged with override ---\n'

  local tmpdir
  tmpdir="$(_make_tmpdir)"
  mkdir -p "$tmpdir/.claude"
  cp "$FIXTURES/override-extends.md" "$tmpdir/.claude/doc-personas.md"
  export REPO_ROOT_OVERRIDE="$tmpdir"

  # shellcheck disable=SC1090,SC1091
  source "$LIB"

  if personas_extends_defaults; then
    pass "S3: personas_extends_defaults returns true for extends fixture"
  else
    fail "S3: personas_extends_defaults returns true for extends fixture" \
      "returned false, expected true"
  fi

  local result ids count result_file
  result="$(resolve_active_persona_set)"
  result_file="$(_make_tmpdir)/resolved.yaml"
  printf '%s\n' "$result" > "$result_file"
  ids="$(list_persona_ids "$result_file")"
  count="$(printf '%s\n' "$ids" | grep -c '.' || true)"
  assert_eq "S3: result has 5 personas (4 defaults + 1 new)" "5" "$count"

  assert_contains "S3: first-time-installer present" "first-time-installer" "$ids"
  assert_contains "S3: config-explorer present"      "config-explorer"      "$ids"
  assert_contains "S3: troubleshooter present"       "troubleshooter"       "$ids"
  assert_contains "S3: migrator present (replaced)"  "migrator"             "$ids"
  assert_contains "S3: api-consumer present (new)"   "api-consumer"         "$ids"

  # Verify migrator required flag was replaced (override sets it to true)
  local migrator_req merged_file
  merged_file="$(_make_tmpdir)/merged.yaml"
  printf '%s\n' "$result" > "$merged_file"
  migrator_req="$(get_persona_required "migrator" "$merged_file")"
  assert_eq "S3: migrator required is true (override applied)" "true" "$migrator_req"
  rm -f "$merged_file"

  rm -rf "$tmpdir"
  unset REPO_ROOT_OVERRIDE
}

# ---------------------------------------------------------------------------
# Scenario 4a: Malformed — zero questions
# ---------------------------------------------------------------------------
scenario_4a() {
  printf '\n--- Scenario 4a: Malformed — zero questions → non-zero exit with message ---\n'

  local stderr_out exit_code
  exit_code=0
  stderr_out="$(validate_personas_file "$FIXTURES/malformed-zero-questions.md" 2>&1)" \
    || exit_code=$?

  if [ "$exit_code" -ne 0 ]; then
    pass "S4a: validate_personas_file exits non-zero for zero-questions persona"
  else
    fail "S4a: validate_personas_file exits non-zero for zero-questions persona" \
      "exited 0 unexpectedly"
  fi

  assert_contains "S4a: error message names the persona" \
    "empty-persona" "$stderr_out"
  assert_contains "S4a: error message mentions zero questions" \
    "zero questions" "$stderr_out"
}

# ---------------------------------------------------------------------------
# Scenario 4b: Malformed — missing required field (description)
# ---------------------------------------------------------------------------
scenario_4b() {
  printf '\n--- Scenario 4b: Malformed — missing description field → non-zero exit with message ---\n'

  local stderr_out exit_code
  exit_code=0
  stderr_out="$(validate_personas_file "$FIXTURES/malformed-missing-field.md" 2>&1)" \
    || exit_code=$?

  if [ "$exit_code" -ne 0 ]; then
    pass "S4b: validate_personas_file exits non-zero for missing description"
  else
    fail "S4b: validate_personas_file exits non-zero for missing description" \
      "exited 0 unexpectedly"
  fi

  assert_contains "S4b: error message names the persona" \
    "no-description-persona" "$stderr_out"
  assert_contains "S4b: error message names the missing field" \
    "description" "$stderr_out"
}

# ---------------------------------------------------------------------------
# Scenario 4c: Malformed — no questions: key at all (distinct from zero-questions)
# Expects: exit non-zero, "no questions list" in stderr, "zero questions" absent.
# ---------------------------------------------------------------------------
scenario_4c() {
  printf '\n--- Scenario 4c: Malformed — no questions: key → only "no questions list" error ---\n'

  local stderr_out exit_code
  exit_code=0
  stderr_out="$(validate_personas_file "$FIXTURES/malformed-no-questions-key.md" 2>&1)" \
    || exit_code=$?

  if [ "$exit_code" -ne 0 ]; then
    pass "S4c: validate_personas_file exits non-zero for missing questions key"
  else
    fail "S4c: validate_personas_file exits non-zero for missing questions key" \
      "exited 0 unexpectedly"
  fi

  assert_contains "S4c: error message names the persona" \
    "no-questions-key-persona" "$stderr_out"
  assert_contains "S4c: error reports no questions list" \
    "no questions list" "$stderr_out"

  # The "zero questions" message must NOT appear — it is redundant when the key is absent.
  if printf '%s\n' "$stderr_out" | grep -qF "zero questions"; then
    fail "S4c: spurious zero-questions error absent" \
      "got both errors; expected only 'no questions list'"
  else
    pass "S4c: spurious zero-questions error absent"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 5: awk portability — no {n} interval regexes in the parser.
# mawk (the default awk on Debian/Ubuntu) silently ignores POSIX {n} interval
# expressions, so any /^[[:space:]]{2}.../ pattern matches nothing there. That
# produced an empty work plan and a vacuous PASS in review mode. The parser
# must use literal-space anchors instead. This is a static guard: it catches a
# regression on ANY platform, including macOS where intervals happen to work.
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: parser is free of {n} interval regexes (mawk-portable) ---\n'

  # grep -c prints "0" and exits 1 when there are no matches; `|| true` keeps
  # that "0" as the only output (a fallback printf would double it).
  local interval_count
  interval_count="$(grep -c '\[\[:space:\]\]{[0-9]' "$LIB" 2>/dev/null || true)"
  assert_eq "S5: zero [[:space:]]{n} interval patterns in lib-personas.sh" \
    "0" "${interval_count:-0}"
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------

# shellcheck disable=SC1090,SC1091
source "$LIB"

scenario_1
scenario_2
scenario_3
scenario_4a
scenario_4b
scenario_4c
scenario_5

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
