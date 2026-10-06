#!/usr/bin/env bats
# Tests for scripts/lib/drift_check.sh
# Spec: SDD §Internal API Changes / function: drift_check_hook_bundle

bats_require_minimum_version 1.5.0

setup() {
  PLUGIN_ROOT="$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)"
  LIB="$PLUGIN_ROOT/scripts/lib/drift_check.sh"

  # Create temporary repo structure
  REPO_TMP="${TMPDIR:-/tmp}/drift-check-test-$$"
  mkdir -p "$REPO_TMP"
  GITHOOKS_DIR="$REPO_TMP/.githooks"
  mkdir -p "$GITHOOKS_DIR"

  # Source the library under test
  # shellcheck source=/dev/null
  source "$LIB"
}

teardown() {
  rm -rf "$REPO_TMP"
}

# ---------- MISSING case: .githooks/tcs-git-helpers-version does not exist ----------

@test "returns MISSING when .githooks/tcs-git-helpers-version does not exist" {
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

# ---------- OK case: installed version matches expected ----------

@test "returns OK when installed version matches expected" {
  echo "h7" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ---------- DRIFT case: installed version differs from expected ----------

@test "returns DRIFT:<installed> when versions differ (h1 vs h7)" {
  echo "h1" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h1" ]
}

@test "returns DRIFT:<installed> when versions differ (h5 vs h7)" {
  echo "h5" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h5" ]
}

# ---------- Whitespace handling: trailing newlines and spaces ----------

@test "strips trailing newline before comparing" {
  printf "h7\n" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

@test "strips trailing whitespace (spaces and tabs)" {
  printf "h7  \t  \n" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

@test "strips CRLF line endings" {
  printf "h7\r\n" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ---------- Exit code: always 0 ----------

@test "exit code is 0 when MISSING" {
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
}

@test "exit code is 0 when OK" {
  echo "h7" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
}

@test "exit code is 0 when DRIFT" {
  echo "h1" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
}

# ---------- No stderr output ----------

@test "does not write to stderr" {
  echo "h7" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run --separate-stderr drift_check_hook_bundle "$REPO_TMP" "h7"
  [ -z "$stderr" ] || [ "$stderr" = "" ]
}

@test "does not write to stderr on MISSING" {
  run --separate-stderr drift_check_hook_bundle "$REPO_TMP" "h7"
  [ -z "$stderr" ] || [ "$stderr" = "" ]
}

@test "does not write to stderr on DRIFT" {
  echo "h1" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run --separate-stderr drift_check_hook_bundle "$REPO_TMP" "h7"
  [ -z "$stderr" ] || [ "$stderr" = "" ]
}

# ---------- Multi-line file: uses only first line ----------

@test "uses only first line when multiple lines present" {
  printf "h7\nh8\nh9\n" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ---------- Spec 020 T4.1: drift_check_bundle takes a marker directory ----------

@test "bundle: MISSING in a custom marker dir" {
  run drift_check_bundle "$REPO_TMP" "1.0" "tcs-patterns-version" ".tcs-patterns"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

@test "bundle: OK in a custom marker dir" {
  mkdir -p "$REPO_TMP/.tcs-patterns"
  echo "1.0" > "$REPO_TMP/.tcs-patterns/tcs-patterns-version"
  run drift_check_bundle "$REPO_TMP" "1.0" "tcs-patterns-version" ".tcs-patterns"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

@test "bundle: DRIFT:<installed> in a custom marker dir" {
  mkdir -p "$REPO_TMP/.tcs-patterns"
  echo "0.9" > "$REPO_TMP/.tcs-patterns/tcs-patterns-version"
  run drift_check_bundle "$REPO_TMP" "1.0" "tcs-patterns-version" ".tcs-patterns"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:0.9" ]
}

@test "bundle: a marker in .githooks is not read when marker_dir points elsewhere" {
  echo "h7" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_bundle "$REPO_TMP" "h7" "tcs-git-helpers-version" ".tcs-patterns"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

@test "bundle: a marker in the custom dir is not read by the default dir" {
  mkdir -p "$REPO_TMP/.tcs-patterns"
  echo "h7" > "$REPO_TMP/.tcs-patterns/tcs-git-helpers-version"
  run drift_check_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

@test "bundle: default marker_dir equals the hook-bundle wrapper's output" {
  echo "h1" > "$GITHOOKS_DIR/tcs-git-helpers-version"
  run drift_check_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h1" ]
  run drift_check_hook_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h1" ]
}

# ---------- locale: classification is ASCII-whitespace-only in any caller locale ----------

@test "bundle: under a UTF-8 locale a non-breaking space is kept, not stripped" {
  printf 'h7\xc2\xa0\n' > "$GITHOOKS_DIR/tcs-git-helpers-version"
  LC_ALL=en_US.UTF-8 run drift_check_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'DRIFT:h7\xc2\xa0')" ]
}

@test "bundle: under a UTF-8 locale an invalid byte gives DRIFT, exit 0, no stderr" {
  printf 'h\xff7\n' > "$GITHOOKS_DIR/tcs-git-helpers-version"
  LC_ALL=en_US.UTF-8 run --separate-stderr drift_check_bundle "$REPO_TMP" "h7"
  [ "$status" -eq 0 ]
  [ "$output" = "$(printf 'DRIFT:h\xff7')" ]
  [ -z "$stderr" ]
}
