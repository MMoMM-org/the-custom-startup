#!/usr/bin/env bats
# Tests for scripts/session-start-brief.sh.
#
# v2.2.2 rewrite: the brief is no longer a plain-text line. SessionStart
# stdout goes only to Claude's context, so the script now emits a JSON
# hook response with two channels:
#   - systemMessage          : user-visible TUI notice
#   - hookSpecificOutput.additionalContext : Claude-only context
# When nothing is actionable, the script exits 0 silently (no stdout).
#
# Coverage:
#   1.  Silent on idle (feat branch, hooks current, no stale)
#   2.  Silent on idle when cache file missing
#   3.  Main branch idle → additionalContext nudge only, no systemMessage
#   4.  Drift hint → both channels carry the suggestion
#   5.  Setup hint when .githooks/ absent → both channels
#   6.  Cleanup hint when stale-count > 0 → both channels
#   7.  Main + cleanup → systemMessage has hint, additionalContext has hint + nudge
#   8.  JSON output parses cleanly
#   9.  No gh invocations (sentinel stub)
#  10.  Performance p99 < 300ms (500ms on CI) over 100 invocations
#
# Constraints:
#   - bash 3.2 compatible (no declare -A, no mapfile)
#   - POSIX ERE patterns only
#   - No jq dependency

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
  git -C "$ORIGIN" symbolic-ref HEAD refs/heads/main 2>/dev/null || true

  git -C "$TEST_REPO" init -q 2>/dev/null || git -C "$TEST_REPO" init >/dev/null 2>&1
  git -C "$TEST_REPO" config commit.gpgsign false
  git -C "$TEST_REPO" config tag.gpgsign false
  git -C "$TEST_REPO" config user.name "bats"
  git -C "$TEST_REPO" config user.email "b@a.ts"

  printf 'init\n' > "$TEST_REPO/init.txt"
  git -C "$TEST_REPO" add init.txt
  git -C "$TEST_REPO" commit -q -m "feat: init"
  git -C "$TEST_REPO" checkout -B main >/dev/null 2>&1 || true
  git -C "$TEST_REPO" remote add origin "$ORIGIN"
  git -C "$TEST_REPO" push -q -u origin main 2>/dev/null \
    || git -C "$TEST_REPO" push -q -u origin HEAD:main 2>/dev/null || true
  git -C "$TEST_REPO" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main 2>/dev/null || true

  # Create and switch to feat branch — most tests run from a feature branch.
  git -C "$TEST_REPO" checkout -q -b feat/foo 2>/dev/null || true
  git -C "$TEST_REPO" push -q -u origin feat/foo 2>/dev/null || true

  # Repo hash matches lib/cache.sh _repo_hash exactly (printf '%s' on the
  # real-path show-toplevel, no trailing newline).
  _real_top="$(git -C "$TEST_REPO" rev-parse --show-toplevel 2>/dev/null)"
  REPO_HASH="$(printf '%s' "$_real_top" | shasum 2>/dev/null | head -c 12)"
  export REPO_HASH
  export CACHE_DIR
}

teardown() {
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

# Write a stale-cache TSV file. Args: $1=updated_iso, $2+=rows.
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

# Install fake .githooks/ with hooks bannered at a given version. The
# drift-check in section 8b of session-start-brief.sh reads the first
# tcs-git-helpers banner line out of pre-commit / pre-push / commit-msg /
# post-merge, so we only need to write those files with the banner.
_install_githooks_at() {
  local v="$1"
  mkdir -p "$TEST_REPO/.githooks"
  local h
  for h in pre-commit pre-push commit-msg post-merge; do
    {
      printf '#!/bin/bash\n'
      printf '# tcs-git-helpers: %s\n' "$v"
      printf 'exit 0\n'
    } > "$TEST_REPO/.githooks/$h"
    chmod +x "$TEST_REPO/.githooks/$h"
  done
}

# Install .githooks/ at the plugin.json current version → silences drift_seg.
_install_githooks_current() {
  local v
  v="$(grep -E '"version"[[:space:]]*:' "$PLUGIN_ROOT/.claude-plugin/plugin.json" \
       | head -1 \
       | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  _install_githooks_at "$v"
}

# Run the hook in the test repo dir.
_run_hook() {
  run --separate-stderr bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$HOOK"
}

# ----------------------------------------------------------------------
# Test 1: Silent on idle (feat branch, hooks current, no stale)
# ----------------------------------------------------------------------

@test "silent on idle: feat branch + current githooks + no stale" {
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"  # empty cache, no stale rows

  _run_hook

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

# ----------------------------------------------------------------------
# Test 2: Silent on idle when cache file is missing entirely
# ----------------------------------------------------------------------

@test "silent on idle: cache file absent, fail-open" {
  _install_githooks_current
  local tsv_path="$CACHE_DIR/${REPO_HASH}-stale-cache.tsv"
  [ ! -f "$tsv_path" ]

  _run_hook

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

# ----------------------------------------------------------------------
# Test 3: Main branch idle — additionalContext nudge only, no systemMessage
# ----------------------------------------------------------------------

@test "main branch idle: additionalContext has nudge, no systemMessage" {
  git -C "$TEST_REPO" checkout -q main 2>/dev/null || true
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  # No systemMessage field present → user sees nothing.
  ! printf '%s' "$output" | grep -q '"systemMessage"'
  # additionalContext present and contains the protected-branch nudge.
  printf '%s' "$output" | grep -q '"additionalContext"'
  printf '%s' "$output" | grep -q "protected branch"
  printf '%s' "$output" | grep -q "do not create or edit"
  printf '%s' "$output" | grep -q "main"
}

# ----------------------------------------------------------------------
# Test 4: Drift hint surfaces in both channels
# ----------------------------------------------------------------------

@test "drift hint surfaces in systemMessage and additionalContext" {
  _install_githooks_at "2.0.0"   # forces drift vs current plugin.json
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q '"additionalContext"'
  printf '%s' "$output" | grep -q "hooks v2.0.0"
  printf '%s' "$output" | grep -q "run /tcs-git-helpers:git-setup --update"
}

# ----------------------------------------------------------------------
# Test 5: Setup hint surfaces when .githooks/ absent
# ----------------------------------------------------------------------

@test "setup hint surfaces when .githooks/ absent" {
  [ ! -d "$TEST_REPO/.githooks" ]
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q "run /tcs-git-helpers:git-setup"
}

# ----------------------------------------------------------------------
# Test 6: Cleanup hint surfaces when stale-count > 0
# ----------------------------------------------------------------------

@test "cleanup hint surfaces when stale-count > 0" {
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q "run /tcs-git-helpers:git-audit --cleanup"
}

# ----------------------------------------------------------------------
# Test 7: Main + cleanup — systemMessage has hint, additionalContext has hint + nudge
# ----------------------------------------------------------------------

@test "main + cleanup: systemMessage has hint, additionalContext has hint + nudge" {
  git -C "$TEST_REPO" checkout -q main 2>/dev/null || true
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q '"additionalContext"'
  # Cleanup hint must appear in both fields (count the occurrences ≥ 2).
  local count
  count="$(printf '%s' "$output" | grep -o "run /tcs-git-helpers:git-audit --cleanup" | wc -l | tr -d '[:space:]')"
  [ "$count" -ge 2 ]
  # Nudge appears only in additionalContext, so just count ≥ 1.
  printf '%s' "$output" | grep -q "protected branch"
}

# ----------------------------------------------------------------------
# Test 8: JSON output parses cleanly
# ----------------------------------------------------------------------

@test "JSON output is syntactically valid when emitted" {
  _install_githooks_at "2.0.0"   # ensure something is emitted
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  # Validate via python3 if present, else jq, else skip.
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$output" | python3 -c 'import json,sys;json.loads(sys.stdin.read())'
  elif command -v jq >/dev/null 2>&1; then
    printf '%s' "$output" | jq -e . >/dev/null
  else
    skip "Neither python3 nor jq available to validate JSON"
  fi
}

# ----------------------------------------------------------------------
# Test 9: No gh invocations (sentinel stub)
# ----------------------------------------------------------------------

@test "hook makes NO gh invocations (sentinel stub exits 99)" {
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

  run --separate-stderr bash -c \
    'export PATH="$1:$PATH"; export GH_SENTINEL_FILE="$2"; cd "$3" && exec "$4"' \
    _ "$stub_dir" "$sentinel" "$TEST_REPO" "$HOOK"

  [ "$status" -eq 0 ]
  [ ! -f "$sentinel" ]

  rm -rf "$stub_dir"
}

# ----------------------------------------------------------------------
# Test 10: Performance p99 under 300ms (500ms on CI)
# ----------------------------------------------------------------------

@test "performance p99 under 300ms (100 invocations)" {
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z"

  local ceiling_ms
  if [ "${CI:-}" = "true" ]; then
    ceiling_ms=500
  else
    ceiling_ms=300
  fi

  local n=100
  local tmp_times
  tmp_times="$(mktemp "${TMPDIR:-/tmp}/tcs-ssb-perf.XXXXXX")"

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

  local p99
  p99="$(sort -n "$tmp_times" | awk 'NR==99{print; exit}')"
  rm -f "$tmp_times"

  case "${p99:-}" in
    ''|*[!0-9]*) skip "Could not parse timing data; skipping perf assertion" ;;
  esac

  if [ "$p99" -ge "$ceiling_ms" ]; then
    printf 'FAIL: p99=%dms exceeds ceiling=%dms\n' "$p99" "$ceiling_ms" >&2
    return 1
  fi
}
