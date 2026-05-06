#!/usr/bin/env bash
# run-review.test.sh — pressure tests for run-review.sh (T2.5)
# Bash 3.2 compatible.
#
# Pressure scenarios:
#   S1: Known-good docs (all required questions → found:yes) → PASS, exit 0
#   S2: Known-bad docs (one required question → found:no) → FAIL, exit 1, gap named
#   S3: --page scoping → only questions whose pages intersect run; unrelated absent
#   S4: READER_TEST_PARALLEL=2 → max concurrent subprocesses never exceeds 2
#   S5: claude CLI missing → exit 2, setup message, no subprocess called
#   S6: Non-interactive FAIL signal → exit 1, outcome=FAIL in JSON
#   S7: Infra-only run (all tuples error) → outcome=PASS, exit 0 (Fixture-4 rule)
#
# Strategy: a stub reader-test.sh is placed on PATH (via READER_TEST env var override
# is not available in run-review.sh, so instead we write a stub reader-test.sh to a
# tempdir/scripts/ and set SKILL_ROOT_OVERRIDE, OR we write the stub directly to the
# scripts path in a temp skill root that mirrors the real layout).
#
# Simpler approach: run-review.sh sources lib-personas.sh from $SCRIPT_DIR.
# We create a temp skill root with:
#   scripts/run-review.sh  → symlink or copy of real script
#   scripts/lib-personas.sh → symlink or copy of real lib
#   scripts/reader-test.sh → our stub (replaces the real one in the temp tree)
# Then invoke: bash <tmproot>/scripts/run-review.sh
# PERSONAS_FILE is set to our fixture.
#
# SC2030/SC2031: subshell env var isolation is intentional.
# SC2329: assert_* called from scenario functions, shellcheck cannot trace.
# shellcheck disable=SC2030,SC2031,SC2329

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
REAL_RUN_REVIEW="${SKILL_ROOT}/scripts/run-review.sh"
REAL_LIB="${SKILL_ROOT}/scripts/lib-personas.sh"
PERSONAS_FIXTURE="${SCRIPT_DIR}/fixtures/run-review-personas.md"

if [ ! -f "$REAL_RUN_REVIEW" ]; then
  printf 'FATAL: run-review.sh not found at %s\n' "$REAL_RUN_REVIEW" >&2
  exit 1
fi
if [ ! -f "$PERSONAS_FIXTURE" ]; then
  printf 'FATAL: fixture not found: %s\n' "$PERSONAS_FIXTURE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Sandbox-safe tempdir (matches reader-test.test.sh pattern)
# ---------------------------------------------------------------------------
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="${TMPDIR:-/tmp}"
  fi
  local d="${base}/run-review-test-$$-${RANDOM}"
  mkdir -p "$d"
  printf '%s\n' "$d"
}

# ---------------------------------------------------------------------------
# Build a temp skill tree with a given stub reader-test.sh
# Returns the path to the temp run-review.sh (in a scripts/ subdir).
# Caller sets PERSONAS_FILE and REPO_ROOT_OVERRIDE when invoking.
# ---------------------------------------------------------------------------
_build_temp_skill() {
  local tmpdir="$1"
  local stub_content="$2"

  mkdir -p "${tmpdir}/scripts"

  # Copy the real run-review.sh and lib-personas.sh
  cp "$REAL_RUN_REVIEW" "${tmpdir}/scripts/run-review.sh"
  cp "$REAL_LIB" "${tmpdir}/scripts/lib-personas.sh"

  # Write the stub reader-test.sh
  printf '%s\n' "$stub_content" > "${tmpdir}/scripts/reader-test.sh"
  chmod +x "${tmpdir}/scripts/reader-test.sh"
}

# ---------------------------------------------------------------------------
# Fixture repo: docs/installation.md and docs/configuration.md
# ---------------------------------------------------------------------------
_setup_fixture_repo() {
  local repo="$1"
  mkdir -p "${repo}/docs"
  printf 'Install by running: ./setup.sh\n' > "${repo}/docs/installation.md"
  printf 'Main config: set TIMEOUT=30 in config.yaml\n' > "${repo}/docs/configuration.md"
}

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0

pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf 'PASS  %s\n' "$1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); printf 'FAIL  %s — %s\n' "$1" "$2"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then pass "$label"
  else fail "$label" "expected=$(printf '%q' "$expected") got=$(printf '%q' "$actual")"; fi
}

assert_exit_zero() {
  local label="$1" code="$2"
  if [ "$code" -eq 0 ]; then pass "$label"
  else fail "$label" "expected exit 0, got $code"; fi
}

assert_exit_one() {
  local label="$1" code="$2"
  if [ "$code" -eq 1 ]; then pass "$label"
  else fail "$label" "expected exit 1, got $code"; fi
}

assert_exit_nonzero() {
  local label="$1" code="$2"
  if [ "$code" -ne 0 ]; then pass "$label"
  else fail "$label" "expected non-zero exit, got 0"; fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then pass "$label"
  else fail "$label" "expected to contain: $needle"; fi
}

assert_not_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    fail "$label" "expected NOT to contain: $needle"
  else
    pass "$label"
  fi
}

assert_json_field() {
  local label="$1" field="$2" expected="$3" json="$4"
  local actual
  actual="$(printf '%s\n' "$json" | jq -r "$field" 2>/dev/null || true)"
  if [ "$expected" = "$actual" ]; then pass "$label"
  else fail "$label" "jq $field: expected=$(printf '%q' "$expected") got=$(printf '%q' "$actual")"; fi
}

# ---------------------------------------------------------------------------
# Stub content builders
# ---------------------------------------------------------------------------

# Stub that always returns found:yes (happy path)
_stub_happy() {
  cat <<'STUB'
#!/usr/bin/env bash
# Stub reader-test.sh — always returns found:yes
printf '{"found":"yes","answer":"Found the answer.","unclear":[],"guessed":[],"page_used":"docs/installation.md"}\n'
exit 0
STUB
}

# Stub that returns found:no for p1/q1, found:yes for everything else
_stub_fail_p1_q1() {
  cat <<'STUB'
#!/usr/bin/env bash
# Stub reader-test.sh — returns found:no for p1 q1, found:yes otherwise
PERSONA_ID="${1:-}"
QUESTION_ID="${2:-}"
if [ "$PERSONA_ID" = "p1" ] && [ "$QUESTION_ID" = "q1" ]; then
  printf '{"found":"no","answer":"Not described.","unclear":["how to install"],"guessed":[],"page_used":null}\n'
else
  printf '{"found":"yes","answer":"Found the answer.","unclear":[],"guessed":[],"page_used":"docs/installation.md"}\n'
fi
exit 0
STUB
}

# Stub that records concurrent invocations for concurrency test.
# Each invocation appends "START <pid>" then sleeps then appends "STOP <pid>"
# to a shared events file. Post-run, _peak_concurrency scans that file and
# computes the maximum overlap — no read-modify-write race.
_stub_concurrency() {
  local lock_dir="$1"
  cat <<STUB
#!/usr/bin/env bash
# Stub reader-test.sh — concurrency event recorder (no TOCTOU)
EVENTS_FILE="${lock_dir}/events"
printf 'START %s\n' "\$\$" >> "\$EVENTS_FILE"
sleep 0.15
printf 'STOP %s\n' "\$\$" >> "\$EVENTS_FILE"
printf '{"found":"yes","answer":"ok","unclear":[],"guessed":[],"page_used":"docs/installation.md"}\n'
exit 0
STUB
}

# _peak_concurrency <events_file>
# Reads START/STOP records (one per line) and returns the maximum number
# of START records that appear before their matching STOP — i.e. peak overlap.
# Uses pure awk; no external sort needed.
_peak_concurrency() {
  local events_file="$1"
  [ -f "$events_file" ] || { printf '0\n'; return; }
  awk '
    /^START / { active++; if (active > peak) peak = active }
    /^STOP /  { if (active > 0) active-- }
    END { print (peak ? peak : 0) }
  ' "$events_file"
}

# ---------------------------------------------------------------------------
# S1: Known-good docs → PASS, exit 0, all tuples present
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- S1: Known-good docs — all required questions found:yes → PASS ---\n'

  local tmpdir skill_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$skill_dir" "$repo_dir"
  _setup_fixture_repo "$repo_dir"
  _build_temp_skill "$skill_dir" "$(_stub_happy)"

  local output exit_code
  exit_code=0
  output="$(
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    bash "${skill_dir}/scripts/run-review.sh"
  )" || exit_code=$?

  assert_exit_zero "S1: exit code is 0" "$exit_code"
  assert_json_field "S1: outcome is PASS" ".outcome" "PASS" "$output"

  local tuple_count
  tuple_count="$(printf '%s\n' "$output" | jq '.tuples | length' 2>/dev/null || true)"
  if [ "${tuple_count:-0}" -ge 3 ]; then
    pass "S1: all 3 tuples present in aggregate"
  else
    fail "S1: all 3 tuples present in aggregate" "got ${tuple_count} tuples"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# S2: Known-bad docs → FAIL, exit 1, failing tuple named in output
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- S2: Known-bad docs — p1/q1 found:no → FAIL, gap named ---\n'

  local tmpdir skill_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$skill_dir" "$repo_dir"
  _setup_fixture_repo "$repo_dir"
  _build_temp_skill "$skill_dir" "$(_stub_fail_p1_q1)"

  local output exit_code
  exit_code=0
  output="$(
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    bash "${skill_dir}/scripts/run-review.sh"
  )" || exit_code=$?

  assert_exit_one "S2: exit code is 1 (FAIL)" "$exit_code"
  assert_json_field "S2: outcome is FAIL" ".outcome" "FAIL" "$output"

  # The failing tuple p1/q1 must be in the tuples array
  local fail_tuple_found
  fail_tuple_found="$(printf '%s\n' "$output" | jq -r '[.tuples[] | select(.persona_id=="p1" and .question_id=="q1" and .found=="no")] | length' 2>/dev/null || true)"
  if [ "${fail_tuple_found:-0}" -ge 1 ]; then
    pass "S2: failing tuple p1/q1 named in output"
  else
    fail "S2: failing tuple p1/q1 named in output" "not found in tuples"
  fi

  # Other tuples should still be PASS
  local pass_count
  pass_count="$(printf '%s\n' "$output" | jq -r '[.tuples[] | select(.found=="yes")] | length' 2>/dev/null || true)"
  if [ "${pass_count:-0}" -ge 2 ]; then
    pass "S2: other tuples still pass"
  else
    fail "S2: other tuples still pass" "expected >=2 pass tuples, got ${pass_count}"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# S3: --page scoping → only q1 and q3 run (both on docs/installation.md)
#     q2 (docs/configuration.md only) must be absent
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- S3: --page scoping → only installation.md questions run ---\n'

  local tmpdir skill_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$skill_dir" "$repo_dir"
  _setup_fixture_repo "$repo_dir"
  _build_temp_skill "$skill_dir" "$(_stub_happy)"

  local output exit_code
  exit_code=0
  output="$(
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    bash "${skill_dir}/scripts/run-review.sh" --page docs/installation.md
  )" || exit_code=$?

  # q1 and q3 are on docs/installation.md → should run
  # q2 is on docs/configuration.md only → should NOT run
  local tuple_count
  tuple_count="$(printf '%s\n' "$output" | jq '.tuples | length' 2>/dev/null || true)"
  if [ "${tuple_count:-0}" -eq 2 ]; then
    pass "S3: exactly 2 tuples ran (q1 and q3)"
  else
    fail "S3: exactly 2 tuples ran (q1 and q3)" "got ${tuple_count} tuples"
  fi

  # q2 must be absent
  local q2_present
  q2_present="$(printf '%s\n' "$output" | jq -r '[.tuples[] | select(.question_id=="q2")] | length' 2>/dev/null || true)"
  if [ "${q2_present:-0}" -eq 0 ]; then
    pass "S3: q2 (configuration.md only) absent from results"
  else
    fail "S3: q2 (configuration.md only) absent from results" "q2 appeared in output"
  fi

  # q1 must be present
  local q1_present
  q1_present="$(printf '%s\n' "$output" | jq -r '[.tuples[] | select(.question_id=="q1")] | length' 2>/dev/null || true)"
  if [ "${q1_present:-0}" -eq 1 ]; then
    pass "S3: q1 present"
  else
    fail "S3: q1 present" "q1 not found in output"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# S4: READER_TEST_PARALLEL=2 → max concurrent never exceeds 2
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- S4: READER_TEST_PARALLEL=2 → max concurrent ≤ 2 ---\n'

  local tmpdir skill_dir repo_dir lock_dir
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  lock_dir="${tmpdir}/lock"
  mkdir -p "$skill_dir" "$repo_dir" "$lock_dir"
  _setup_fixture_repo "$repo_dir"
  _build_temp_skill "$skill_dir" "$(_stub_concurrency "$lock_dir")"

  local output exit_code
  exit_code=0
  output="$(
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    export READER_TEST_PARALLEL=2
    bash "${skill_dir}/scripts/run-review.sh"
  )" || exit_code=$?

  local max_concurrent
  max_concurrent="$(_peak_concurrency "${lock_dir}/events")"

  if [ "${max_concurrent:-0}" -le 2 ]; then
    pass "S4: max concurrent ≤ 2 (observed: ${max_concurrent})"
  else
    fail "S4: max concurrent ≤ 2 (observed: ${max_concurrent})" "exceeded limit"
  fi

  # Ensure the run still completed with all tuples
  local tuple_count
  tuple_count="$(printf '%s\n' "$output" | jq '.tuples | length' 2>/dev/null || true)"
  if [ "${tuple_count:-0}" -ge 3 ]; then
    pass "S4: all 3 tuples completed despite concurrency limit"
  else
    fail "S4: all 3 tuples completed despite concurrency limit" "got ${tuple_count} tuples"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# S5: claude CLI missing → exit non-zero, setup message, no subprocess called
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- S5: claude CLI missing → exit non-zero, setup message ---\n'

  local tmpdir skill_dir repo_dir invocation_log controlled_bin
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  invocation_log="${tmpdir}/invocations.log"
  controlled_bin="${tmpdir}/bin"
  mkdir -p "$skill_dir" "$repo_dir" "$controlled_bin"
  _setup_fixture_repo "$repo_dir"

  # Stub reader-test.sh that logs when called (proves it was NOT called before prereq failure)
  local stub_content
  stub_content="$(cat <<STUB
#!/usr/bin/env bash
printf 'STUB_INVOKED\n' >> '${invocation_log}'
printf '{"found":"yes","answer":"ok","unclear":[],"guessed":[],"page_used":"docs/installation.md"}\n'
exit 0
STUB
)"
  _build_temp_skill "$skill_dir" "$stub_content"

  # Build a PATH that retains all system tools but shadows claude with a non-existent entry.
  # Strategy: prepend controlled_bin (which has NO claude binary) before the real PATH.
  # Any directory in PATH that contains the real claude binary is removed from PATH.
  local real_claude_dir=""
  local claude_bin
  claude_bin="$(command -v claude 2>/dev/null || true)"
  if [ -n "$claude_bin" ]; then
    # Resolve symlinks to get the actual binary dir to strip from PATH
    real_claude_dir="$(dirname "$claude_bin")"
  fi

  local no_claude_path
  no_claude_path="$(printf '%s' "${PATH}" | tr ':' '\n' | \
    grep -v "^${real_claude_dir}$" | tr '\n' ':' | sed 's/:$//')"
  # Prepend controlled_bin (empty — no claude there either) to guarantee precedence
  no_claude_path="${controlled_bin}:${no_claude_path}"

  local stderr_out exit_code
  exit_code=0
  stderr_out="$(
    export PATH="${no_claude_path}"
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    bash "${skill_dir}/scripts/run-review.sh" 2>&1
  )" || exit_code=$?

  assert_exit_nonzero "S5: exit code is non-zero" "$exit_code"
  assert_contains "S5: setup message mentions claude CLI" \
    "review mode requires the" "$stderr_out"
  assert_contains "S5: setup message mentions npm install" \
    "npm install -g @anthropic-ai/claude-code" "$stderr_out"

  # Verify reader-test stub was NOT called
  if [ ! -f "$invocation_log" ]; then
    pass "S5: no subprocess (reader-test) was called before prereq failure"
  else
    fail "S5: no subprocess (reader-test) was called before prereq failure" \
      "invocation log exists — stub was called"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# S6: Non-interactive FAIL signal → exit 1 AND outcome=FAIL in JSON
# (Extends S2: verifies both the exit code and the JSON outcome field)
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- S6: Non-interactive FAIL signal → exit 1, outcome=FAIL in JSON ---\n'

  local tmpdir skill_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$skill_dir" "$repo_dir"
  _setup_fixture_repo "$repo_dir"
  _build_temp_skill "$skill_dir" "$(_stub_fail_p1_q1)"

  local output exit_code
  exit_code=0
  output="$(
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    bash "${skill_dir}/scripts/run-review.sh"
  )" || exit_code=$?

  # Non-interactive signal: exit code 1
  assert_exit_one "S6: exit code is 1 (FAIL signal for non-interactive callers)" "$exit_code"

  # JSON outcome field
  assert_json_field "S6: outcome field is FAIL in JSON" ".outcome" "FAIL" "$output"

  # The failing required tuple must be identifiable in the JSON (renderable gap report)
  local req_fails
  req_fails="$(printf '%s\n' "$output" | jq -r \
    '[.tuples[] | select(.persona_required==true and .question_required==true and (.found=="no" or .found=="partial") and (.error==null or .error==""))] | length' \
    2>/dev/null || true)"
  if [ "${req_fails:-0}" -ge 1 ]; then
    pass "S6: required-fail tuples present and renderable in JSON"
  else
    fail "S6: required-fail tuples present and renderable in JSON" \
      "no required-fail tuples found (got ${req_fails})"
  fi

  rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# S7: Fixture-4 rule — all tuples produce infra errors → outcome=PASS, exit 0
# Verifies that infra errors do NOT contribute to FAIL.
# Strategy: stub reader-test.sh exits 1 unconditionally; run-review.sh wraps
# that as an invocation_error JSON envelope (infra error, not a gap).
# ---------------------------------------------------------------------------
scenario_7() {
  printf '\n--- S7: Infra-only run (all reader-test calls fail) → PASS, exit 0 ---\n'

  local tmpdir skill_dir repo_dir
  tmpdir="$(_make_tmpdir)"
  skill_dir="${tmpdir}/skill"
  repo_dir="${tmpdir}/repo"
  mkdir -p "$skill_dir" "$repo_dir"
  _setup_fixture_repo "$repo_dir"

  # Stub that exits 1 unconditionally — simulates claude invocation failure.
  # run-review.sh catches non-zero exit from reader-test and writes an
  # invocation_error JSON envelope (the infra-error branch at lines ~292-294).
  _build_temp_skill "$skill_dir" "$(cat <<'STUB'
#!/usr/bin/env bash
# Stub reader-test.sh — always exits 1 (simulates claude failure)
exit 1
STUB
)"

  local output exit_code
  exit_code=0
  output="$(
    export PERSONAS_FILE="$PERSONAS_FIXTURE"
    export REPO_ROOT_OVERRIDE="$repo_dir"
    bash "${skill_dir}/scripts/run-review.sh"
  )" || exit_code=$?

  # Fixture-4 rule: infra errors alone must not produce FAIL
  assert_exit_zero "S7: exit code is 0 (infra-only → PASS)" "$exit_code"
  assert_json_field "S7: outcome is PASS (not FAIL)" ".outcome" "PASS" "$output"

  # Every tuple must have an error field set
  local tuple_count error_count
  tuple_count="$(printf '%s\n' "$output" | jq '.tuples | length' 2>/dev/null || true)"
  error_count="$(printf '%s\n' "$output" | \
    jq '[.tuples[] | select(.error != null and .error != "")] | length' 2>/dev/null || true)"

  if [ "${tuple_count:-0}" -ge 1 ] && [ "$error_count" = "$tuple_count" ]; then
    pass "S7: every tuple has .error set (all are infra errors)"
  else
    fail "S7: every tuple has .error set (all are infra errors)" \
      "tuples=${tuple_count} with error=${error_count}"
  fi

  # No tuple's infra error should flip outcome to FAIL — the gate must distinguish
  local fail_count
  fail_count="$(printf '%s\n' "$output" | \
    jq '[.tuples[] | select(.error == null or .error == "") | select(.found == "no" or .found == "partial")] | length' \
    2>/dev/null || true)"
  if [ "${fail_count:-0}" -eq 0 ]; then
    pass "S7: no clean (non-error) fail tuples contributed to outcome"
  else
    fail "S7: no clean (non-error) fail tuples contributed to outcome" \
      "found ${fail_count} clean fail tuples"
  fi

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
