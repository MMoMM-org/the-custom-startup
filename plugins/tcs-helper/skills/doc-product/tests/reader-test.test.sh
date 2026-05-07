#!/usr/bin/env bash
# reader-test.test.sh — pressure tests for reader-test.sh
# Bash 3.2 compatible.
#
# Strategy: a stub claude binary is written to a tempdir and prepended to PATH.
# STUB_MODE env var controls stub behaviour:
#   happy       — returns well-formed found:yes JSON
#   bad         — returns well-formed found:no JSON with unclear items
#   malformed   — returns non-JSON text
#   hang        — sleeps indefinitely (triggers timeout)
#   rate-limit  — exits 1 with stderr message
#
# REPO_ROOT_OVERRIDE and PERSONAS_FILE are set per-scenario to inject fixture data.
#
# Usage: bash tests/reader-test.test.sh
# Exit: 0 if all 6 scenarios pass; non-zero with failure count otherwise.

# SC2030/SC2031: subshell-local env var modifications are intentional — each
# scenario isolates PATH/STUB_MODE/REPO_ROOT_OVERRIDE in its own $() subshell.
# SC2329: shellcheck cannot trace assert_eq/assert_contains invocations through
# scenario functions; they are called directly.
# shellcheck disable=SC2030,SC2031,SC2329
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
READER_TEST="${SKILL_ROOT}/scripts/reader-test.sh"
FIXTURES="${SCRIPT_DIR}/fixtures"
PERSONAS_FIXTURE="${FIXTURES}/reader-test-personas.md"

if [ ! -f "$READER_TEST" ]; then
  printf 'FATAL: reader-test.sh not found at %s\n' "$READER_TEST" >&2
  exit 1
fi

if [ ! -f "$PERSONAS_FIXTURE" ]; then
  printf 'FATAL: fixture not found: %s\n' "$PERSONAS_FIXTURE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Sandbox-safe tempdir creation (matches lib-personas.test.sh pattern)
# mktemp -d is avoided because the macOS Claude Code sandbox blocks it even
# when TMPDIR is set to an allowed path. Manual mkdir under a known-writable
# base is used instead.
# ---------------------------------------------------------------------------
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="/tmp"
  fi
  local d="${base}/reader-test-$$-${RANDOM}"
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

assert_exit_zero() {
  local label="$1" code="$2"
  if [ "$code" -eq 0 ]; then
    pass "$label"
  else
    fail "$label" "expected exit 0, got $code"
  fi
}

assert_exit_nonzero() {
  local label="$1" code="$2"
  if [ "$code" -ne 0 ]; then
    pass "$label"
  else
    fail "$label" "expected non-zero exit, got 0"
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

assert_json_field() {
  local label="$1" field="$2" expected="$3" json="$4"
  local actual
  actual="$(printf '%s\n' "$json" | jq -r "$field" 2>/dev/null || true)"
  if [ "$expected" = "$actual" ]; then
    pass "$label"
  else
    fail "$label" "jq $field: expected=$(printf '%q' "$expected") got=$(printf '%q' "$actual")"
  fi
}

# ---------------------------------------------------------------------------
# Stub claude writer
# Writes a stub claude binary to a given dir.
# STUB_MODE controls output (read at runtime by the stub).
# ---------------------------------------------------------------------------
_write_stub_claude() {
  local bin_dir="$1"
  cat > "${bin_dir}/claude" <<'STUB'
#!/usr/bin/env bash
# Stub claude binary — driven by STUB_MODE env var
# Ignores all args; prints canned output based on STUB_MODE.
case "${STUB_MODE:-happy}" in
  happy)
    printf '{"found":"yes","answer":"Install by running the setup script.","unclear":[],"guessed":[],"page_used":"README.md"}\n'
    exit 0
    ;;
  bad)
    printf '{"found":"no","answer":"The document does not describe this.","unclear":["how to install","what OS is supported"],"guessed":[],"page_used":null}\n'
    exit 0
    ;;
  malformed)
    printf 'this is not json\n'
    exit 0
    ;;
  hang)
    # exec replaces the shell process so SIGKILL hits sleep directly.
    # Without exec, killing the stub leaves the sleep grandchild alive,
    # keeping the $() stdout pipe open and blocking the test.
    exec sleep 300
    ;;
  rate-limit)
    printf 'rate limit exceeded\n' >&2
    exit 1
    ;;
  *)
    printf 'unknown STUB_MODE: %s\n' "${STUB_MODE}" >&2
    exit 1
    ;;
esac
STUB
  chmod +x "${bin_dir}/claude"
}

# ---------------------------------------------------------------------------
# Set up a fixture repo root with README.md (missing.md intentionally absent)
# ---------------------------------------------------------------------------
_setup_fixture_repo() {
  local repo="$1"
  mkdir -p "${repo}"
  printf 'Install by running the setup script: ./setup.sh\n' > "${repo}/README.md"
  # missing.md is intentionally NOT created — used to test "page not found" path
}

# ---------------------------------------------------------------------------
# Scenario 1: Happy path — stub returns found:yes, exit 0
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: Happy path — found:yes, exit 0 ---\n'

  local tmpdir stub_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  stub_dir="${tmpdir}/bin"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$stub_dir"
  _setup_fixture_repo "$repo_dir"
  _write_stub_claude "$stub_dir"

  local output exit_code
  exit_code=0
  output="$(
    export PATH="${stub_dir}:${PATH}"
    export STUB_MODE=happy
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    bash "$READER_TEST" test-reader what-is-it
  )" || exit_code=$?

  assert_exit_zero "S1: exit code is 0" "$exit_code"
  assert_json_field "S1: found == yes" ".found" "yes" "$output"

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Scenario 2: Known-bad doc — stub returns found:no with unclear items, exit 0
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: Known-bad doc — found:no with unclear, exit 0 ---\n'

  local tmpdir stub_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  stub_dir="${tmpdir}/bin"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$stub_dir"
  _setup_fixture_repo "$repo_dir"
  _write_stub_claude "$stub_dir"

  local output exit_code
  exit_code=0
  output="$(
    export PATH="${stub_dir}:${PATH}"
    export STUB_MODE=bad
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    bash "$READER_TEST" test-reader what-is-it
  )" || exit_code=$?

  assert_exit_zero "S2: exit code is 0" "$exit_code"
  assert_json_field "S2: found == no" ".found" "no" "$output"

  local unclear_count
  unclear_count="$(printf '%s\n' "$output" | jq '.unclear | length' 2>/dev/null || true)"
  if [ "${unclear_count:-0}" -gt 0 ]; then
    pass "S2: unclear array is non-empty"
  else
    fail "S2: unclear array is non-empty" "got length=${unclear_count}"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Scenario 3: claude not on PATH — exit non-zero, stderr has setup message
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: claude not on PATH — exit non-zero, setup message in stderr ---\n'

  local tmpdir repo_dir
  tmpdir="$(_make_tmpdir)"
  repo_dir="${tmpdir}/repo"
  _setup_fixture_repo "$repo_dir"

  local stderr_out exit_code
  exit_code=0
  stderr_out="$(
    export PATH="/usr/bin:/bin"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    bash "$READER_TEST" test-reader what-is-it 2>&1
  )" || exit_code=$?

  assert_exit_nonzero "S3: exit code is non-zero" "$exit_code"
  assert_contains "S3: stderr mentions claude CLI" \
    "review mode requires the" "$stderr_out"
  assert_contains "S3: stderr mentions npm install" \
    "npm install -g @anthropic-ai/claude-code" "$stderr_out"

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Scenario 4: claude rate-limit / invocation failure — exit 0, error field set
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- Scenario 4: claude rate-limit / failure — exit 0, error:timeout_or_invocation_failure ---\n'

  local tmpdir stub_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  stub_dir="${tmpdir}/bin"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$stub_dir"
  _setup_fixture_repo "$repo_dir"
  _write_stub_claude "$stub_dir"

  local output exit_code
  exit_code=0
  output="$(
    export PATH="${stub_dir}:${PATH}"
    export STUB_MODE=rate-limit
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    bash "$READER_TEST" test-reader what-is-it
  )" || exit_code=$?

  assert_exit_zero "S4: exit code is 0 (infra error, not config error)" "$exit_code"
  assert_json_field "S4: error == timeout_or_invocation_failure" \
    ".error" "timeout_or_invocation_failure" "$output"

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Scenario 5: Malformed JSON from claude — exit 0, error:unparseable_response
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: Malformed JSON from claude — exit 0, error:unparseable_response ---\n'

  local tmpdir stub_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  stub_dir="${tmpdir}/bin"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$stub_dir"
  _setup_fixture_repo "$repo_dir"
  _write_stub_claude "$stub_dir"

  local output exit_code
  exit_code=0
  output="$(
    export PATH="${stub_dir}:${PATH}"
    export STUB_MODE=malformed
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    bash "$READER_TEST" test-reader what-is-it
  )" || exit_code=$?

  assert_exit_zero "S5: exit code is 0" "$exit_code"
  assert_json_field "S5: error == unparseable_response" \
    ".error" "unparseable_response" "$output"

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Scenario 6: Multi-page corpus — dry-run verifies delimiter structure
# The fixture question pages: [README.md, missing.md]
# README.md exists in fixture repo; missing.md does not.
# Expected: prompt has BEGIN/END for both, "(page not found in repo)" for missing.md
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- Scenario 6: Multi-page corpus — delimiters and missing page surfaced ---\n'

  local tmpdir repo_dir
  tmpdir="$(_make_tmpdir)"
  repo_dir="${tmpdir}/repo"
  _setup_fixture_repo "$repo_dir"

  local prompt_out exit_code
  exit_code=0
  prompt_out="$(
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    bash "$READER_TEST" test-reader what-is-it --dry-run
  )" || exit_code=$?

  assert_exit_zero "S6: dry-run exits 0" "$exit_code"
  assert_contains "S6: BEGIN PAGE README.md present" \
    "===== BEGIN PAGE: README.md =====" "$prompt_out"
  assert_contains "S6: END PAGE README.md present" \
    "===== END PAGE: README.md =====" "$prompt_out"
  assert_contains "S6: BEGIN PAGE missing.md present" \
    "===== BEGIN PAGE: missing.md =====" "$prompt_out"
  assert_contains "S6: END PAGE missing.md present" \
    "===== END PAGE: missing.md =====" "$prompt_out"
  assert_contains "S6: missing page not silently dropped" \
    "(page not found in repo)" "$prompt_out"

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# Scenario 7: Timeout — stub hangs, READER_TEST_TIMEOUT=1 triggers alarm/kill
# Exercises the Perl-fallback _run_with_timeout path (active on macOS without
# GNU coreutils). READER_TEST_TIMEOUT=1 keeps wall-clock time to ~1s.
# Expected: exit 0, JSON with .error == "timeout_or_invocation_failure".
# ---------------------------------------------------------------------------
scenario_7() {
  printf '\n--- Scenario 7: Timeout — hang stub + 1s timeout → infra error JSON ---\n'

  local tmpdir stub_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  stub_dir="${tmpdir}/bin"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$stub_dir"
  _setup_fixture_repo "$repo_dir"
  _write_stub_claude "$stub_dir"

  local output exit_code
  exit_code=0
  output="$(
    export PATH="${stub_dir}:${PATH}"
    export STUB_MODE=hang
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export READER_TEST_TIMEOUT=1
    bash "$READER_TEST" test-reader what-is-it
  )" || exit_code=$?

  assert_exit_zero "S7: exit code is 0 (timeout is infra error)" "$exit_code"
  assert_json_field "S7: found == no" ".found" "no" "$output"
  assert_json_field "S7: error == timeout_or_invocation_failure" \
    ".error" "timeout_or_invocation_failure" "$output"

  rm -rf "$tmpdir"
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
