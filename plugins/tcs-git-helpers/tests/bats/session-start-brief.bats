#!/usr/bin/env bats
# Tests for scripts/session-start-brief.sh (T3.2).
#
# Coverage:
#   1. Brief format matches SDD wireframe (branch, state, ahead/behind, stale-count)
#   2. Warning marker ⚠ on protected branch (main/master)
#   3. Dirty state with modified count
#   4. "up to date" when no ahead/behind
#   5. Staleness indicator when cache >24h old
#   6. Setup hint when .githooks/ absent
#   7. No gh invocations (sentinel stub)
#   8. Cache empty renders gracefully (0 stale-merged, no errors)
#   9. Performance p99 <300ms (or 500ms on CI) over 100 invocations
#  10. Cleanup suggestion when stale-count > 0
#
# Spec refs:
#   - SDD §Runtime View Tertiary Flow (session-start-brief)
#   - SDD §UI Visualization Brief Layout
#   - PRD M4 AC1–AC5
#   - ADR-4: TSV format with comment header
#
# Constraints:
#   - bash 3.2 compatible (no declare -A, no mapfile)
#   - POSIX ERE patterns only
#   - No jq dependency
#   - No gh invocations in hook

bats_require_minimum_version 1.5.0

# ----------------------------------------------------------------------
# Setup / teardown
# ----------------------------------------------------------------------

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/session-start-brief.sh"

  # Sandbox plugin data so cache writes don't affect the user's real data.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  CACHE_DIR="$CLAUDE_PLUGIN_DATA/cache"
  mkdir -p "$CACHE_DIR"

  # Build a synthetic fixture repo for this test (fresh per test).
  # We use inline repo-building rather than build.sh to control upstream state.
  TEST_REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb-repo.XXXXXX")"
  export TEST_REPO

  # Deterministic git identity.
  export GIT_AUTHOR_NAME="bats"
  export GIT_AUTHOR_EMAIL="b@a.ts"
  export GIT_COMMITTER_NAME="bats"
  export GIT_COMMITTER_EMAIL="b@a.ts"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  # Build a base repo with an origin so ahead/behind tracking works.
  ORIGIN="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb-origin.XXXXXX")"
  export ORIGIN
  git -C "$ORIGIN" init -q --bare 2>/dev/null \
    || { git -C "$ORIGIN" init --bare >/dev/null 2>&1; }
  # Try to force main as branch name for the bare repo.
  git -C "$ORIGIN" symbolic-ref HEAD refs/heads/main 2>/dev/null || true

  git -C "$TEST_REPO" init -q 2>/dev/null || git -C "$TEST_REPO" init >/dev/null 2>&1
  git -C "$TEST_REPO" config commit.gpgsign false
  git -C "$TEST_REPO" config tag.gpgsign false
  git -C "$TEST_REPO" config user.name "bats"
  git -C "$TEST_REPO" config user.email "b@a.ts"

  printf 'init\n' > "$TEST_REPO/init.txt"
  git -C "$TEST_REPO" add init.txt
  git -C "$TEST_REPO" commit -q -m "feat: init"
  # Try to set branch to main.
  git -C "$TEST_REPO" checkout -B main >/dev/null 2>&1 || true
  git -C "$TEST_REPO" remote add origin "$ORIGIN"
  git -C "$TEST_REPO" push -q -u origin main 2>/dev/null \
    || git -C "$TEST_REPO" push -q -u origin HEAD:main 2>/dev/null || true
  git -C "$TEST_REPO" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main 2>/dev/null || true

  # Create and switch to feat branch for most tests.
  git -C "$TEST_REPO" checkout -q -b feat/foo 2>/dev/null || true
  git -C "$TEST_REPO" push -q -u origin feat/foo 2>/dev/null || true

  # Compute repo hash (same as cache.sh: sha1 of repo top-level path)
  REPO_HASH="$(printf '%s' "$TEST_REPO" | shasum 2>/dev/null | head -c 12)"
  export REPO_HASH
  export CACHE_DIR

  # Remove installed .githooks dir by default — each test that needs it will add it.
  unset GITHOOKS_INSTALLED 2>/dev/null || true
}

teardown() {
  # Best-effort cleanup.
  if [ -n "${TEST_REPO:-}" ] && [ -d "$TEST_REPO" ]; then
    chmod -R u+w "$TEST_REPO" 2>/dev/null || true
    rm -rf "$TEST_REPO"
  fi
  if [ -n "${ORIGIN:-}" ] && [ -d "$ORIGIN" ]; then
    rm -rf "$ORIGIN"
  fi
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

# Write a stale-cache TSV file with the given updated_iso timestamp and rows.
# Args: $1=updated_iso, $2+=rows (each: "branch\tpr\tdate")
_write_test_cache() {
  local updated_iso="$1"
  shift
  local tsv_path="$CACHE_DIR/${REPO_HASH}-stale-cache.tsv"
  {
    printf '# tcs-git-helpers stale cache v1\n'
    printf '# updated_iso=%s\n' "$updated_iso"
    printf '# repo_path=%s\n' "$TEST_REPO"
    printf '# default_branch=main\n'
    for row in "$@"; do
      printf '%s\n' "$row"
    done
  } > "$tsv_path"
}

# Compute ISO timestamp N hours ago (UTC).
# Uses BSD date -v (macOS) with GNU date -d fallback.
_hours_ago_iso() {
  local hours="$1"
  local secs=$(( hours * 3600 ))
  local epoch
  epoch="$(date +%s)"
  epoch="$((epoch - secs))"
  # BSD/macOS: date -r <epoch>; GNU: date -d @<epoch>
  if date -r "$epoch" -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null; then
    return 0
  fi
  date -u -d "@$epoch" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null
}

# Run the hook in the test repo dir. Captures:
#   $status  — exit code
#   $output  — stdout (should be empty for this hook)
#   $stderr  — stderr (the brief)
_run_hook() {
  run --separate-stderr bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$HOOK"
}

# Helper: assert $stderr does NOT contain a pattern (safe mid-test assertion).
# Returns 1 if the pattern IS found (test failure).
_assert_no_match() {
  local pattern="$1"
  if printf '%s' "$stderr" | grep -q "$pattern"; then
    printf 'FAIL: stderr should NOT contain pattern: %s\n' "$pattern" >&2
    printf 'Actual stderr: %s\n' "$stderr" >&2
    return 1
  fi
  return 0
}

# ----------------------------------------------------------------------
# Test 1: Brief format matches SDD wireframe
# ----------------------------------------------------------------------

@test "brief format matches SDD wireframe (feat/foo • clean • 2 ahead • 3 stale-merged)" {
  # Make repo 2 ahead of upstream.
  printf 'change1\n' > "$TEST_REPO/c1.txt"
  git -C "$TEST_REPO" add c1.txt
  git -C "$TEST_REPO" commit -q -m "feat: c1"
  printf 'change2\n' > "$TEST_REPO/c2.txt"
  git -C "$TEST_REPO" add c2.txt
  git -C "$TEST_REPO" commit -q -m "feat: c2"

  # Write cache with 3 stale entries, updated now (no staleness).
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z" \
    "feat/more-old	41	2026-04-20T09:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  # Brief must contain: branch name, clean, ahead count, stale count.
  printf '%s' "$stderr" | grep -q "feat/foo"
  printf '%s' "$stderr" | grep -q "clean"
  printf '%s' "$stderr" | grep -q "2 ahead"
  printf '%s' "$stderr" | grep -q "3 stale-merged"
  # Must start with the prefix (no ⚠ for feat branch).
  printf '%s' "$stderr" | grep -q "^\[tcs-git-helpers\]"
}

# ----------------------------------------------------------------------
# Test 2: Warning marker on protected branch
# ----------------------------------------------------------------------

@test "warning marker ⚠ on protected branch (main)" {
  # Switch back to main.
  git -C "$TEST_REPO" checkout -q main 2>/dev/null || true

  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$stderr" | grep -q "^⚠ \[tcs-git-helpers\]"
  printf '%s' "$stderr" | grep -q "main"
}

# ----------------------------------------------------------------------
# Test 3: Dirty state with modified count
# ----------------------------------------------------------------------

@test "dirty state reports N modified count" {
  # Create 3 tracked modified files.
  printf 'orig\n' > "$TEST_REPO/f1.txt"
  printf 'orig\n' > "$TEST_REPO/f2.txt"
  printf 'orig\n' > "$TEST_REPO/f3.txt"
  git -C "$TEST_REPO" add f1.txt f2.txt f3.txt
  git -C "$TEST_REPO" commit -q -m "feat: add files"
  # Now modify them without committing.
  printf 'changed\n' > "$TEST_REPO/f1.txt"
  printf 'changed\n' > "$TEST_REPO/f2.txt"
  printf 'changed\n' > "$TEST_REPO/f3.txt"

  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$stderr" | grep -q "dirty (3 modified)"
}

# ----------------------------------------------------------------------
# Test 4: up to date when no ahead/behind
# ----------------------------------------------------------------------

@test "up to date when HEAD equals upstream" {
  # The feat/foo branch was pushed with no commits ahead — already up to date.
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$stderr" | grep -q "up to date"
}

# ----------------------------------------------------------------------
# Test 5: Staleness indicator when cache >24h old
# ----------------------------------------------------------------------

@test "staleness indicator when cache older than 24h" {
  # Write cache with updated_iso 26 hours ago.
  local stale_iso
  stale_iso="$(_hours_ago_iso 26)"
  _write_test_cache "$stale_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  # Must match pattern "(cache Nh old)" for N >= 24.
  printf '%s' "$stderr" | grep -qE "\(cache [0-9]+h old\)"
}

# ----------------------------------------------------------------------
# Test 6: Setup hint when .githooks/ absent
# ----------------------------------------------------------------------

@test "setup hint when .githooks/ absent" {
  # Confirm no .githooks exists in test repo.
  [ ! -d "$TEST_REPO/.githooks" ]

  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$stderr" | grep -q "run /tcs-git-helpers:setup"
}

# ----------------------------------------------------------------------
# Test 7: No gh invocations
# ----------------------------------------------------------------------

@test "hook makes NO gh invocations (sentinel stub exits 99)" {
  # Install a sentinel gh stub that records invocation and exits 99.
  local stub_dir
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb-ghstub.XXXXXX")"
  local sentinel="$stub_dir/gh-invoked"

  cat > "$stub_dir/gh" << 'STUB'
#!/bin/bash
# Sentinel: record invocation and exit 99 (hook must never call us).
printf 'gh-stub-sentinel invoked with: %s\n' "$*" >&2
touch "${GH_SENTINEL_FILE}"
exit 99
STUB
  chmod +x "$stub_dir/gh"

  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  # Run hook with sentinel gh on PATH.
  run --separate-stderr bash -c \
    'export PATH="$1:$PATH"; export GH_SENTINEL_FILE="$2"; cd "$3" && exec "$4"' \
    _ "$stub_dir" "$sentinel" "$TEST_REPO" "$HOOK"

  [ "$status" -eq 0 ]
  # Sentinel file must NOT exist — gh was never invoked.
  [ ! -f "$sentinel" ]

  rm -rf "$stub_dir"
}

# ----------------------------------------------------------------------
# Test 8: Cache empty renders gracefully
# ----------------------------------------------------------------------

@test "cache empty renders gracefully (0 stale-merged, exit 0)" {
  # No cache file at all — _read_stale_cache_tsv returns empty.
  local tsv_path="$CACHE_DIR/${REPO_HASH}-stale-cache.tsv"
  [ ! -f "$tsv_path" ]  # Confirm absent.

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$stderr" | grep -q "0 stale-merged"
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# Test 9: Performance p99 under 300ms (500ms on CI)
# ----------------------------------------------------------------------

@test "performance p99 under 300ms (100 invocations)" {
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z"

  # Determine the performance ceiling: 500ms on CI, 300ms locally.
  local ceiling_ms
  if [ "${CI:-}" = "true" ]; then
    ceiling_ms=500
  else
    ceiling_ms=300
  fi

  local n=100
  local tmp_times
  tmp_times="$(mktemp "${TMPDIR:-/tmp}/tcs-ssb-perf.XXXXXX")"

  # Measure each invocation using date +%s%3N (milliseconds since epoch).
  # gdate (coreutils) is more precise on macOS; fall back to GNU date.
  # Use gdate (GNU coreutils) on macOS for millisecond precision.
  # Fall back to perl -MTime::HiRes if gdate absent.
  # If neither is available, skip.
  local ms_cmd=""
  if command -v gdate >/dev/null 2>&1; then
    ms_cmd="gdate +%s%3N"
  elif command -v perl >/dev/null 2>&1; then
    ms_cmd="perl -MTime::HiRes=time -e 'printf \"%d\n\", time()*1000'"
  fi

  if [ -z "$ms_cmd" ]; then
    rm -f "$tmp_times"
    skip "Millisecond timing not available (no gdate, no perl)"
  fi

  local i t0 t1 elapsed_ms
  for i in $(seq 1 $n); do
    t0="$(eval "$ms_cmd" 2>/dev/null || echo 0)"
    bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$HOOK" >/dev/null 2>&1
    t1="$(eval "$ms_cmd" 2>/dev/null || echo 0)"
    elapsed_ms="$((t1 - t0))"
    printf '%s\n' "$elapsed_ms" >> "$tmp_times"
  done

  # Compute p99 (index 99 of sorted 100 values = position 99 in 1-indexed, i.e., the max).
  # With 100 samples, p99 = the 99th value when sorted ascending (1 sample above).
  local p99
  p99="$(sort -n "$tmp_times" | awk 'NR==99{print; exit}')"
  rm -f "$tmp_times"

  # Guard: if p99 is empty or non-numeric, timing failed — skip.
  case "${p99:-}" in
    ''|*[!0-9]*) skip "Could not parse timing data; skipping perf assertion" ;;
  esac

  if [ "$p99" -ge "$ceiling_ms" ]; then
    printf 'FAIL: p99=%dms exceeds ceiling=%dms\n' "$p99" "$ceiling_ms" >&2
    return 1
  fi
}

# ----------------------------------------------------------------------
# Test 10: Cleanup suggestion when stale-count > 0
# ----------------------------------------------------------------------

@test "cleanup suggestion appended when stale-count > 0" {
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$stderr" | grep -q "run /tcs-git-helpers:status --cleanup"
}
