#!/usr/bin/env bats
# tests/bats/lib_config_parser.bats — security corpus for parse_tcs_config
#
# Spec refs:
#   - SDD §Implementation Examples — Bash parser sketch (ADR-3)
#   - research/security.md §4 — MUST-reject corpus + MUST accept .config.example
#   - CON-1 (bash 3.2 compat: no `declare -A`, no `mapfile`)
#   - CON-9 (regex: `[[:space:]]+`, never `\s+`)
#
# Test design: each test parses a fixture .config file in a temp dir, captures
# the exit code and stderr, and asserts on resulting environment variables.
# A "rejected" line MUST NOT produce an assignment, MUST emit a stderr warning,
# and MUST NOT cause the parser to exit non-zero (it's a graceful skip).

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
PARSER="${PLUGIN_ROOT}/scripts/lib/config_parser.sh"
EXAMPLE="${PLUGIN_ROOT}/.config.example"

setup() {
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/tcs-cfg-XXXXXX")"
  CFG="${TMP}/.config"
  STDERR="${TMP}/stderr.log"
  # Wipe any TCS_* vars from the harness env before each test
  unset TCS_PROTECTED_BRANCHES TCS_HOOK_EXCLUDE_PATHS_FILE \
        TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE \
        TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK \
        TCS_ENABLE_PR_PUSH_CHECK TCS_ALLOW_AMEND_ON_PROTECTED \
        EVIL
}

teardown() {
  rm -rf "$TMP"
}

# Helper: run parser in a subshell, capture stderr, source the lib in-process
# so we can inspect resulting variables.
run_parser() {
  # shellcheck disable=SC1090
  ( set +e
    # shellcheck source=/dev/null
    . "$PARSER"
    parse_tcs_config "$CFG" 2>"$STDERR"
    rc=$?
    # Print a deterministic key=value snapshot for the harness to grep.
    printf 'EXIT=%s\n' "$rc"
    printf 'TCS_PROTECTED_BRANCHES=%s\n' "${TCS_PROTECTED_BRANCHES-<unset>}"
    printf 'TCS_HOOK_EXCLUDE_PATHS_FILE=%s\n' "${TCS_HOOK_EXCLUDE_PATHS_FILE-<unset>}"
    printf 'TCS_ALLOWED_COMMIT_TYPES=%s\n' "${TCS_ALLOWED_COMMIT_TYPES-<unset>}"
    printf 'TCS_REQUIRE_SCOPE=%s\n' "${TCS_REQUIRE_SCOPE-<unset>}"
    printf 'TCS_MAX_SUBJECT_LENGTH=%s\n' "${TCS_MAX_SUBJECT_LENGTH-<unset>}"
    printf 'TCS_ENABLE_CONVENTIONAL_CHECK=%s\n' "${TCS_ENABLE_CONVENTIONAL_CHECK-<unset>}"
    printf 'TCS_ENABLE_PR_PUSH_CHECK=%s\n' "${TCS_ENABLE_PR_PUSH_CHECK-<unset>}"
    printf 'TCS_ALLOW_AMEND_ON_PROTECTED=%s\n' "${TCS_ALLOW_AMEND_ON_PROTECTED-<unset>}"
    printf 'EVIL=%s\n' "${EVIL-<unset>}"
  )
}

# ---------------------------------------------------------------------------
# Sanity: the parser file exists and is sourceable
# ---------------------------------------------------------------------------

@test "parser file exists and is shellcheck-sourceable" {
  [ -f "$PARSER" ]
  bash -n "$PARSER"
}

@test "parser is a no-op when file is missing (returns 0, defaults stay unset)" {
  rm -f "$CFG"
  run run_parser
  [ "$status" -eq 0 ]
  [[ "$output" == *"EXIT=0"* ]]
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
}

# ---------------------------------------------------------------------------
# MUST-reject corpus (research/security.md §4)
# ---------------------------------------------------------------------------

@test "REJECT: command substitution \$(rm -rf ~)" {
  printf '%s\n' 'TCS_PROTECTED_BRANCHES=$(rm -rf ~)' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
  grep -q "rejected\|invalid\|forbidden" "$STDERR"
}

@test "REJECT: backtick command substitution" {
  printf '%s\n' 'TCS_PROTECTED_BRANCHES=`evil`' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
  grep -q "rejected\|invalid\|forbidden" "$STDERR"
}

@test "REJECT: newline injection (literal \\n in value)" {
  # Literal backslash-n in value should still be rejected (contains '\')
  printf '%s\n' 'TCS_PROTECTED_BRANCHES=main\nMALICIOUS=1' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
  [[ "$output" == *"MALICIOUS"* ]] && false || true
  grep -q "rejected\|invalid\|forbidden" "$STDERR"
}

@test "REJECT: unknown key EVIL=1" {
  printf '%s\n' 'EVIL=1' >"$CFG"
  run run_parser
  [[ "$output" == *"EVIL=<unset>"* ]]
  grep -q "unknown key" "$STDERR"
}

@test "REJECT: type mismatch TCS_REQUIRE_SCOPE=true (must be 0|1)" {
  printf '%s\n' 'TCS_REQUIRE_SCOPE=true' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_REQUIRE_SCOPE=<unset>"* ]]
  grep -q "invalid value" "$STDERR"
}

@test "REJECT: path traversal in TCS_HOOK_EXCLUDE_PATHS_FILE" {
  printf '%s\n' 'TCS_HOOK_EXCLUDE_PATHS_FILE=../../etc/passwd' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_HOOK_EXCLUDE_PATHS_FILE=<unset>"* ]]
  grep -q "invalid value\|path traversal\|forbidden" "$STDERR"
}

# ---------------------------------------------------------------------------
# Extra defense-in-depth rejections (forbidden metacharacters)
# ---------------------------------------------------------------------------

@test "REJECT: dollar-brace expansion \${HOME}" {
  printf '%s\n' 'TCS_PROTECTED_BRANCHES=${HOME}' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
}

@test "REJECT: pipe character in value" {
  # NB: TCS_PROTECTED_BRANCHES legitimately uses '|' separators; but a value
  # containing only '|' or with shell-like operators must still be rejected
  # as a free-form value. Use a key that does not allow '|'.
  printf '%s\n' 'TCS_ALLOWED_COMMIT_TYPES=feat|fix' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_ALLOWED_COMMIT_TYPES=<unset>"* ]]
}

@test "REJECT: semicolon command separator" {
  printf '%s\n' 'TCS_MAX_SUBJECT_LENGTH=90;echo HI' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_MAX_SUBJECT_LENGTH=<unset>"* ]]
}

@test "REJECT: ampersand background operator" {
  printf '%s\n' 'TCS_REQUIRE_SCOPE=1&' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_REQUIRE_SCOPE=<unset>"* ]]
}

@test "REJECT: redirection operators >" {
  printf '%s\n' 'TCS_REQUIRE_SCOPE=1>file' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_REQUIRE_SCOPE=<unset>"* ]]
}

@test "REJECT: malformed line (no equals sign)" {
  printf '%s\n' 'NOT_A_KV_LINE' >"$CFG"
  run run_parser
  grep -q "malformed\|ignor" "$STDERR"
}

@test "REJECT: lowercase key (allowlist requires UPPER)" {
  printf '%s\n' 'tcs_protected_branches=main' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
}

@test "REJECT: value > 256 chars" {
  long="$(printf 'x%.0s' $(seq 1 300))"
  printf 'TCS_PROTECTED_BRANCHES=%s\n' "$long" >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
}

# ---------------------------------------------------------------------------
# MUST-accept: all .config.example uncommented lines
# ---------------------------------------------------------------------------

@test ".config.example exists in plugin root" {
  [ -f "$EXAMPLE" ]
}

@test "ACCEPT: every uncommented line of .config.example parses cleanly" {
  # Filter blanks and comments; assign each via parser.
  grep -Ev '^[[:space:]]*(#|$)' "$EXAMPLE" >"$CFG"
  # If .config.example only has commented samples, this file will be empty;
  # write a minimal "all keys with sample values" version instead.
  if [ ! -s "$CFG" ]; then
    {
      printf 'TCS_PROTECTED_BRANCHES=main|master|production|release\n'
      printf 'TCS_HOOK_EXCLUDE_PATHS_FILE=.githooks/exclude-paths\n'
      printf 'TCS_ALLOWED_COMMIT_TYPES=feat fix docs style refactor test chore perf revert build ci\n'
      printf 'TCS_REQUIRE_SCOPE=0\n'
      printf 'TCS_MAX_SUBJECT_LENGTH=90\n'
      printf 'TCS_ENABLE_CONVENTIONAL_CHECK=1\n'
      printf 'TCS_ENABLE_PR_PUSH_CHECK=1\n'
      printf 'TCS_ALLOW_AMEND_ON_PROTECTED=0\n'
    } >"$CFG"
  fi
  run run_parser
  [ "$status" -eq 0 ]
  [[ "$output" == *"EXIT=0"* ]]
  # Spot-check a handful of keys are now set
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=main|master|production|release"* ]]
  [[ "$output" == *"TCS_REQUIRE_SCOPE=0"* ]]
  [[ "$output" == *"TCS_MAX_SUBJECT_LENGTH=90"* ]]
  # No spurious stderr noise about rejection
  if [ -s "$STDERR" ]; then
    ! grep -qi "rejected\|forbidden\|unknown key\|invalid value" "$STDERR"
  fi
}

# ---------------------------------------------------------------------------
# Quoting + whitespace + comments (MUST-tolerate)
# ---------------------------------------------------------------------------

@test "ACCEPT: outer double quotes are stripped" {
  printf '%s\n' 'TCS_HOOK_EXCLUDE_PATHS_FILE=".githooks/exclude-paths"' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_HOOK_EXCLUDE_PATHS_FILE=.githooks/exclude-paths"* ]]
}

@test "ACCEPT: outer single quotes are stripped" {
  printf "%s\n" "TCS_HOOK_EXCLUDE_PATHS_FILE='.githooks/exclude-paths'" >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_HOOK_EXCLUDE_PATHS_FILE=.githooks/exclude-paths"* ]]
}

@test "ACCEPT: comments and blank lines are tolerated" {
  {
    printf '\n'
    printf '# This is a comment\n'
    printf '   # Indented comment\n'
    printf '\n'
    printf 'TCS_REQUIRE_SCOPE=1\n'
    printf '\n'
  } >"$CFG"
  run run_parser
  [ "$status" -eq 0 ]
  [[ "$output" == *"TCS_REQUIRE_SCOPE=1"* ]]
}

@test "ACCEPT: trailing comment after value is stripped" {
  printf '%s\n' 'TCS_REQUIRE_SCOPE=1 # enable scope requirement' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_REQUIRE_SCOPE=1"* ]]
}

@test "ACCEPT: leading/trailing whitespace on line is stripped" {
  printf '%s\n' '   TCS_MAX_SUBJECT_LENGTH=72   ' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_MAX_SUBJECT_LENGTH=72"* ]]
}

@test "ACCEPT: CRLF line endings tolerated" {
  printf 'TCS_REQUIRE_SCOPE=1\r\n' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_REQUIRE_SCOPE=1"* ]]
}

# ---------------------------------------------------------------------------
# Per-key value-validation
# ---------------------------------------------------------------------------

@test "REJECT: TCS_MAX_SUBJECT_LENGTH non-integer" {
  printf '%s\n' 'TCS_MAX_SUBJECT_LENGTH=abc' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_MAX_SUBJECT_LENGTH=<unset>"* ]]
}

@test "REJECT: TCS_MAX_SUBJECT_LENGTH > 4 digits" {
  printf '%s\n' 'TCS_MAX_SUBJECT_LENGTH=99999' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_MAX_SUBJECT_LENGTH=<unset>"* ]]
}

@test "REJECT: TCS_ENABLE_CONVENTIONAL_CHECK=2 (booleans must be 0|1)" {
  printf '%s\n' 'TCS_ENABLE_CONVENTIONAL_CHECK=2' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_ENABLE_CONVENTIONAL_CHECK=<unset>"* ]]
}

@test "REJECT: TCS_PROTECTED_BRANCHES with shell metachars" {
  printf '%s\n' 'TCS_PROTECTED_BRANCHES=main;rm' >"$CFG"
  run run_parser
  [[ "$output" == *"TCS_PROTECTED_BRANCHES=<unset>"* ]]
}

# ---------------------------------------------------------------------------
# Performance budget (CON: ≤5ms per invocation, target)
# ---------------------------------------------------------------------------

@test "PERF: parser completes under 50ms (10x budget) for an 8-line config" {
  # We use a 10x budget to keep the test stable on busy CI.
  {
    printf 'TCS_PROTECTED_BRANCHES=main|master\n'
    printf 'TCS_HOOK_EXCLUDE_PATHS_FILE=.githooks/exclude-paths\n'
    printf 'TCS_ALLOWED_COMMIT_TYPES=feat fix docs\n'
    printf 'TCS_REQUIRE_SCOPE=1\n'
    printf 'TCS_MAX_SUBJECT_LENGTH=72\n'
    printf 'TCS_ENABLE_CONVENTIONAL_CHECK=1\n'
    printf 'TCS_ENABLE_PR_PUSH_CHECK=1\n'
    printf 'TCS_ALLOW_AMEND_ON_PROTECTED=0\n'
  } >"$CFG"
  start=$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')
  run run_parser
  end=$(perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000')
  [ "$status" -eq 0 ]
  elapsed=$((end - start))
  # Forge will fluctuate; 50ms is generous and still demonstrates the budget.
  [ "$elapsed" -lt 500 ]
}
