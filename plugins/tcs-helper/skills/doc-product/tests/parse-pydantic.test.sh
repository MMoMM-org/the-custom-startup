#!/usr/bin/env bash
# parse-pydantic.test.sh — pressure tests for parse-pydantic.sh
# Bash 3.2 compatible.
#
# Scenarios:
#   S1  Pydantic v2 BaseModel + Field(default=, description=) → TSV
#   S2  Pydantic v1-shape BaseModel (plain annotations + class defaults) → TSV
#   S3  @dataclass with Google-style docstring → TSV
#   S4  @dataclass with no docstring → [NEEDS DESCRIPTION] in all description cells
#   S5  python3 not on PATH → ADR-5 error format, exit 2
#   S6  pydantic import unavailable but file imports pydantic → exit 4, no traceback
#
# For S1/S2 (Pydantic-dependent): if pydantic is not installed in python3, the
# scenario is SKIPPED with a clear message. Exit 0 when all non-skipped pass.
#
# Temp dirs: created under /tmp/claude-501 (sandbox-safe).
# mktemp -d avoided — macOS sandbox blocks it even with TMPDIR set.
#
# Usage:  bash tests/parse-pydantic.test.sh
# Exit:   0 all (non-skipped) pass;  non-zero = failure count

# SC2030/SC2031: subshell-local PATH overrides are intentional.
# SC2329: harness calls are made indirectly but counted correctly.
# shellcheck disable=SC2030,SC2031,SC2329
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
PARSER="${SKILL_ROOT}/scripts/parse-pydantic.sh"
FIXTURES="${SCRIPT_DIR}/fixtures/pydantic"

if [ ! -f "$PARSER" ]; then
  printf 'FATAL: parse-pydantic.sh not found at %s\n' "$PARSER" >&2
  exit 1
fi

if [ ! -d "$FIXTURES" ]; then
  printf 'FATAL: fixtures directory not found: %s\n' "$FIXTURES" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Sandbox-safe tempdir creation
# ---------------------------------------------------------------------------
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="/tmp"
  fi
  local d="${base}/parse-pydantic-test-$$-${RANDOM}"
  mkdir -p "$d"
  printf '%s\n' "$d"
}

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf 'PASS  %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf 'FAIL  %s — %s\n' "$1" "$2"
}

skip() {
  SKIP_COUNT=$((SKIP_COUNT + 1))
  printf 'SKIP  %s — %s\n' "$1" "$2"
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
    fail "$label" "must NOT contain: $(printf '%q' "$needle")"
  else
    pass "$label"
  fi
}

# ---------------------------------------------------------------------------
# Pydantic availability probe (run once; used by S1/S2 guards)
# ---------------------------------------------------------------------------
PYDANTIC_AVAILABLE=0
if python3 -c 'import pydantic' 2>/dev/null; then
  PYDANTIC_AVAILABLE=1
fi

# ---------------------------------------------------------------------------
# Scenario 1: Pydantic v2 BaseModel + Field(default=, description=) → TSV
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- Scenario 1: Pydantic v2 BaseModel → TSV ---\n'

  if [ "$PYDANTIC_AVAILABLE" -eq 0 ]; then
    skip "S1: pydantic v2 parse" "pydantic not installed — install with pip install pydantic"
    return 0
  fi

  local stdout stderr exit_code s1_tmpdir s1_stderr_file
  exit_code=0
  s1_tmpdir="$(_make_tmpdir)"
  s1_stderr_file="${s1_tmpdir}/stderr"
  stdout="$(bash "$PARSER" "${FIXTURES}/pydantic-v2.py" AppConfig 2>"$s1_stderr_file")" || exit_code=$?
  stderr="$(cat "$s1_stderr_file" 2>/dev/null || true)"
  rm -rf "$s1_tmpdir"

  assert_eq "S1: exit code 0" "0" "$exit_code"

  # Header row
  assert_contains "S1: header present" "name	type	default	description" "$stdout"

  # host field
  assert_contains "S1: host row present" "host" "$stdout"
  assert_contains "S1: host default=localhost" "localhost" "$stdout"
  assert_contains "S1: host description" "Hostname to bind" "$stdout"

  # port field
  assert_contains "S1: port row present" "port" "$stdout"
  assert_contains "S1: port default=8080" "8080" "$stdout"
  assert_contains "S1: port description" "TCP port" "$stdout"
}

# ---------------------------------------------------------------------------
# Scenario 2: Pydantic v1-shape BaseModel (plain annotations + class defaults) → TSV
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- Scenario 2: Pydantic v1-shape BaseModel → TSV ---\n'

  if [ "$PYDANTIC_AVAILABLE" -eq 0 ]; then
    skip "S2: pydantic v1-shape parse" "pydantic not installed — install with pip install pydantic"
    return 0
  fi

  local stdout exit_code
  exit_code=0
  stdout="$(bash "$PARSER" "${FIXTURES}/pydantic-v1-shape.py" ServerConfig 2>/dev/null)" || exit_code=$?

  assert_eq "S2: exit code 0" "0" "$exit_code"

  # Header row
  assert_contains "S2: header present" "name	type	default	description" "$stdout"

  # host row
  assert_contains "S2: host present" "host" "$stdout"
  assert_contains "S2: host default" "0.0.0.0" "$stdout"

  # port row
  assert_contains "S2: port present" "port" "$stdout"
  assert_contains "S2: port default=9000" "9000" "$stdout"

  # No description in source → [NEEDS DESCRIPTION]
  assert_contains "S2: missing description marker" "[NEEDS DESCRIPTION]" "$stdout"
}

# ---------------------------------------------------------------------------
# Scenario 3: @dataclass with Google-style docstring → TSV
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- Scenario 3: @dataclass with Google-style docstring → TSV ---\n'

  local stdout exit_code
  exit_code=0
  stdout="$(bash "$PARSER" "${FIXTURES}/dataclass.py" DatabaseConfig 2>/dev/null)" || exit_code=$?

  assert_eq "S3: exit code 0" "0" "$exit_code"

  # Header row
  assert_contains "S3: header present" "name	type	default	description" "$stdout"

  # url field — description extracted from Attributes section
  assert_contains "S3: url present" "url" "$stdout"
  assert_contains "S3: url default" "sqlite:///app.db" "$stdout"
  assert_contains "S3: url description" "Connection URL" "$stdout"

  # pool_size field
  assert_contains "S3: pool_size present" "pool_size" "$stdout"
  assert_contains "S3: pool_size description" "Number of connections" "$stdout"

  # timeout field
  assert_contains "S3: timeout present" "timeout" "$stdout"
  assert_contains "S3: timeout description" "Query timeout" "$stdout"
}

# ---------------------------------------------------------------------------
# Scenario 4: @dataclass with no docstring → [NEEDS DESCRIPTION] for all fields
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- Scenario 4: @dataclass no docstring → [NEEDS DESCRIPTION] ---\n'

  local stdout exit_code
  exit_code=0
  stdout="$(bash "$PARSER" "${FIXTURES}/dataclass-no-desc.py" CacheConfig 2>/dev/null)" || exit_code=$?

  assert_eq "S4: exit code 0" "0" "$exit_code"

  # All fields should have [NEEDS DESCRIPTION]
  assert_contains "S4: header present" "name	type	default	description" "$stdout"
  assert_contains "S4: backend present" "backend" "$stdout"
  assert_contains "S4: ttl present" "ttl" "$stdout"
  assert_contains "S4: max_size present" "max_size" "$stdout"

  # Count [NEEDS DESCRIPTION] — must be at least 3 (one per field)
  local nd_count
  nd_count="$(printf '%s\n' "$stdout" | grep -c '\[NEEDS DESCRIPTION\]' || true)"
  if [ "$nd_count" -ge 3 ]; then
    pass "S4: all 3 fields have [NEEDS DESCRIPTION]"
  else
    fail "S4: all 3 fields have [NEEDS DESCRIPTION]" \
      "expected >=3 [NEEDS DESCRIPTION] markers, got ${nd_count}"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 5: python3 not on PATH → ADR-5 error format, exit 2
#
# Strategy: build a minimal stub PATH directory that contains bash (symlink)
# but no python3, so command -v python3 fails inside the parser while the
# shell itself still runs. Using PATH=/var/empty would kill bash too.
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- Scenario 5: python3 not on PATH → ADR-5 missing-dep error ---\n'

  local stubdir
  stubdir="$(_make_tmpdir)"

  # Provide bash so the script shebang / set -euo pipefail works
  ln -sf "$(command -v bash)" "${stubdir}/bash"

  local stderr exit_code
  exit_code=0
  stderr="$(PATH="${stubdir}" bash "$PARSER" "${FIXTURES}/dataclass.py" 2>&1 >/dev/null)" \
    || exit_code=$?

  rm -rf "$stubdir"

  assert_eq "S5: exit code 2" "2" "$exit_code"
  assert_contains "S5: error names python3" "python3" "$stderr"
  assert_contains "S5: error says 'not found'" "not found" "$stderr"
  assert_contains "S5: reason line present" "reason:" "$stderr"
  assert_contains "S5: reason mentions pydantic/dataclass" "Pydantic / dataclass" "$stderr"
  assert_contains "S5: install line present" "install:" "$stderr"
  assert_contains "S5: brew install command" "brew install python3" "$stderr"
  assert_contains "S5: apt-get install command" "apt-get install python3" "$stderr"
}

# ---------------------------------------------------------------------------
# Scenario 6: pydantic import unavailable but file imports pydantic → exit 4, no traceback
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- Scenario 6: pydantic module unavailable → actionable error, exit 4 ---\n'

  # We need python3 on PATH for this scenario, but we need pydantic to be
  # unavailable in Python's import path. Strategy: create a temporary directory
  # with a conftest that blocks pydantic import, then set PYTHONPATH to only
  # that directory. This forces `import pydantic` to fail regardless of whether
  # the system has pydantic.
  local tmpdir
  tmpdir="$(_make_tmpdir)"

  # Write a fake pydantic package that raises ImportError on import
  mkdir -p "${tmpdir}/pydantic"
  printf 'raise ImportError("forced unavailable by test")\n' \
    > "${tmpdir}/pydantic/__init__.py"

  local stderr exit_code
  exit_code=0
  stderr="$(PYTHONPATH="${tmpdir}" bash "$PARSER" "${FIXTURES}/pydantic-v2.py" 2>&1 >/dev/null)" \
    || exit_code=$?

  # Clean up
  rm -rf "$tmpdir"

  assert_eq "S6: exit code 4" "4" "$exit_code"
  assert_contains "S6: error mentions pydantic unavailable" "Pydantic module unavailable" "$stderr"
  assert_contains "S6: reason line present" "reason:" "$stderr"
  assert_contains "S6: pip install hint" "pip install pydantic" "$stderr"

  # No Python traceback should leak to stderr
  assert_not_contains "S6: no Traceback in stderr" "Traceback (most recent call last)" "$stderr"
  assert_not_contains "S6: no File reference in stderr" 'File "' "$stderr"
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
printf 'Results: %d passed, %d failed, %d skipped\n' "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT"
printf '========================================\n'

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit "$FAIL_COUNT"
fi
exit 0
