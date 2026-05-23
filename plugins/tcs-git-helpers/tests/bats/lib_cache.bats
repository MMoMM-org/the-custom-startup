#!/usr/bin/env bats
#
# tests/bats/lib_cache.bats
#
# Test suite for scripts/lib/cache.sh — cache layer + PID-file lock.
#
# Spec references:
#   - SDD §Cache Schemas (TSV + JSON sibling, lock file format)
#   - SDD §Data Storage Changes (atomic mv writes; <repo-hash> derivation)
#   - ADR-4 (hybrid TSV+comment-header for SessionStart, JSON sibling for skill)
#
# Constraints exercised here:
#   - bash 3.2 compatible (no flock)
#   - Stub ${CLAUDE_PLUGIN_DATA} via mktemp -d in setup
#   - PID-file lock with kill -0 liveness; 5-min stale TTL
#   - Atomic writes (.tmp + mv)
#   - Reads of missing/corrupt files return empty (no crash)

setup() {
  # macOS mktemp ignores $TMPDIR by default; pass it explicitly so the
  # sandbox-writable path is honored.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-cache-bats.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  LIB="$PLUGIN_ROOT/scripts/lib/cache.sh"

  # Sandbox a tiny git repo so _repo_hash has something to hash.
  REPO="$CLAUDE_PLUGIN_DATA/repo"
  mkdir -p "$REPO"
  (
    cd "$REPO" || exit 1
    git init -q
    git config user.email "t@t"
    git config user.name "t"
    : > a
    git add a
    git commit -q -m init
  )
  cd "$REPO" || return 1
}

teardown() {
  # Best-effort cleanup; tests own the temp dir.
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

# ----------------------------------------------------------------------
# Sourcing
# ----------------------------------------------------------------------

@test "lib loads without errors" {
  source "$LIB"
}

# ----------------------------------------------------------------------
# _repo_hash
# ----------------------------------------------------------------------

@test "_repo_hash returns 12-char SHA1 prefix" {
  source "$LIB"
  local h
  h="$(_repo_hash)"
  [ "${#h}" -eq 12 ]
  [[ "$h" =~ ^[0-9a-f]{12}$ ]]
}

@test "_repo_hash is deterministic for same repo path" {
  source "$LIB"
  local a b
  a="$(_repo_hash)"
  b="$(_repo_hash)"
  [ "$a" = "$b" ]
}

@test "_repo_hash differs across repos" {
  source "$LIB"
  local h1 h2
  h1="$(_repo_hash)"
  local repo2="$CLAUDE_PLUGIN_DATA/repo2"
  mkdir -p "$repo2"
  (
    cd "$repo2" || exit 1
    git init -q
    git config user.email "t@t"
    git config user.name "t"
  )
  cd "$repo2" || return 1
  h2="$(_repo_hash)"
  [ "$h1" != "$h2" ]
}

@test "_repo_hash accepts explicit path argument" {
  source "$LIB"
  local h
  h="$(_repo_hash "/tmp/some/explicit/path")"
  [ "${#h}" -eq 12 ]
}

# ----------------------------------------------------------------------
# Stale-branch TSV / JSON cache
# ----------------------------------------------------------------------

@test "_read_stale_cache_tsv returns empty for missing file (no crash)" {
  source "$LIB"
  run _read_stale_cache_tsv
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_write_stale_cache writes TSV with comment header" {
  source "$LIB"
  printf 'feat/old-thing\t38\t2026-04-12T10:00:00Z\nfix/another-thing\t40\t2026-04-15T09:00:00Z\n' \
    | _write_stale_cache "2026-05-09T14:23:11Z" "$REPO" "main"

  local hash tsv
  hash="$(_repo_hash)"
  tsv="$CLAUDE_PLUGIN_DATA/cache/${hash}-stale-cache.tsv"
  [ -f "$tsv" ]
  grep -q '^# tcs-git-helpers stale cache v1' "$tsv"
  grep -q '^# updated_iso=2026-05-09T14:23:11Z' "$tsv"
  grep -q "^# repo_path=$REPO" "$tsv"
  grep -q '^# default_branch=main' "$tsv"
  # Two data rows
  [ "$(grep -cv '^#' "$tsv")" -eq 2 ]
}

@test "_write_stale_cache writes JSON sibling with version 1" {
  source "$LIB"
  printf 'feat/x\t1\t2026-04-12T10:00:00Z\n' \
    | _write_stale_cache "2026-05-09T14:23:11Z" "$REPO" "master"

  local hash json
  hash="$(_repo_hash)"
  json="$CLAUDE_PLUGIN_DATA/cache/${hash}-stale-cache.json"
  [ -f "$json" ]
  grep -q '"version":[[:space:]]*1' "$json"
  grep -q '"default_branch":[[:space:]]*"master"' "$json"
  grep -q '"name":"feat/x"' "$json"
  grep -q '"pr_number":1' "$json"
  # If jq is available, validate full JSON.
  if command -v jq >/dev/null 2>&1; then
    jq -e . "$json" >/dev/null
  fi
}

@test "TSV body is parseable with head/grep -v/wc -l" {
  source "$LIB"
  printf 'a\t1\t2026-04-01T00:00:00Z\nb\t2\t2026-04-02T00:00:00Z\nc\t3\t2026-04-03T00:00:00Z\n' \
    | _write_stale_cache "2026-05-09T14:23:11Z" "$REPO" "main"

  local hash tsv count
  hash="$(_repo_hash)"
  tsv="$CLAUDE_PLUGIN_DATA/cache/${hash}-stale-cache.tsv"
  # Header readable via head
  head -1 "$tsv" | grep -q '^# tcs-git-helpers stale cache v1'
  # Body line count via grep -v + wc -l
  count="$(grep -v '^#' "$tsv" | wc -l | tr -d ' ')"
  [ "$count" = "3" ]
}

@test "_read_stale_cache_tsv returns body lines (no comments) after write" {
  source "$LIB"
  printf 'feat/a\t1\t2026-04-01T00:00:00Z\n' \
    | _write_stale_cache "2026-05-09T14:23:11Z" "$REPO" "main"

  run _read_stale_cache_tsv
  [ "$status" -eq 0 ]
  [[ "$output" == *"feat/a"* ]]
  # No comment lines leak into body
  ! [[ "$output" == *"#"* ]]
}

@test "_write_stale_cache atomic: no .tmp file remains afterward" {
  source "$LIB"
  printf 'a\t1\t2026-04-01T00:00:00Z\n' \
    | _write_stale_cache "2026-05-09T14:23:11Z" "$REPO" "main"
  ! ls "$CLAUDE_PLUGIN_DATA/cache/"*.tmp >/dev/null 2>&1
}

@test "_write_stale_cache handles empty body gracefully" {
  source "$LIB"
  : | _write_stale_cache "2026-05-09T14:23:11Z" "$REPO" "main"

  local hash tsv json
  hash="$(_repo_hash)"
  tsv="$CLAUDE_PLUGIN_DATA/cache/${hash}-stale-cache.tsv"
  json="$CLAUDE_PLUGIN_DATA/cache/${hash}-stale-cache.json"
  [ -f "$tsv" ]
  [ -f "$json" ]
  # No body rows
  [ "$(grep -cv '^#' "$tsv")" -eq 0 ]
  # JSON has empty stale_branches array
  if command -v jq >/dev/null 2>&1; then
    jq -e . "$json" >/dev/null
    [ "$(jq '.stale_branches | length' "$json")" = "0" ]
  fi
}

@test "corrupt TSV cache returns empty (no crash)" {
  source "$LIB"
  local hash tsv
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  tsv="$CLAUDE_PLUGIN_DATA/cache/${hash}-stale-cache.tsv"
  # Write garbage bytes (no header, control chars)
  printf 'NOT TSV\x01\x02BINARY\nincomplete' > "$tsv"
  run _read_stale_cache_tsv
  # Must not crash, must exit 0
  [ "$status" -eq 0 ]
}

# ----------------------------------------------------------------------
# PR state cache (60s TTL)
# ----------------------------------------------------------------------

@test "_read_pr_state_cache empty on missing file (no crash)" {
  source "$LIB"
  run _read_pr_state_cache "feat/anything"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_write_pr_state_cache + _read_pr_state_cache round-trip" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed; round-trip via jq path skipped"
  fi
  source "$LIB"
  _write_pr_state_cache "feat/foo" "OPEN" "42"
  run _read_pr_state_cache "feat/foo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OPEN"* ]]
}

@test "_write_pr_state_cache atomic: no .tmp file remains" {
  source "$LIB"
  _write_pr_state_cache "feat/foo" "OPEN" "42"
  ! ls "$CLAUDE_PLUGIN_DATA/cache/"*.tmp >/dev/null 2>&1
}

@test "corrupt PR-state JSON returns empty (no crash)" {
  source "$LIB"
  local hash json
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  json="$CLAUDE_PLUGIN_DATA/cache/${hash}-pr-state.json"
  printf '{"oh no, broken' > "$json"
  run _read_pr_state_cache "feat/foo"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ----------------------------------------------------------------------
# PID-file lock (no flock; kill -0 liveness; 5min stale TTL)
# ----------------------------------------------------------------------

@test "_acquire_lock then _release_lock" {
  source "$LIB"
  _acquire_lock
  local hash lock
  hash="$(_repo_hash)"
  lock="$CLAUDE_PLUGIN_DATA/cache/${hash}.lock"
  [ -f "$lock" ]
  # Lock content is PID:TIMESTAMP
  local content pid
  content="$(cat "$lock")"
  pid="${content%%:*}"
  [ "$pid" = "$$" ]
  _release_lock
  [ ! -f "$lock" ]
}

@test "stale lock auto-reclaims when timestamp >5min old" {
  source "$LIB"
  local hash lock
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  lock="$CLAUDE_PLUGIN_DATA/cache/${hash}.lock"
  # PID 1 is always alive on POSIX; only timestamp is stale (>5 min ago).
  local stale_ts=$(( $(date +%s) - 600 ))
  printf '1:%s\n' "$stale_ts" > "$lock"

  # Sanity: planted lock exists and is owned by PID 1 (the precondition we
  # are testing reclaim against).
  [ -f "$lock" ]
  local planted planted_pid
  planted="$(cat "$lock")"
  planted_pid="${planted%%:*}"
  [ "$planted_pid" = "1" ]

  # Use a SHORT timeout so a regression that breaks reclaim fails in 1s,
  # not by silently polling until a longer default timeout elapses.
  run _acquire_lock 1
  [ "$status" -eq 0 ]

  # New lock should belong to us (current shell)
  local content pid
  content="$(cat "$lock")"
  pid="${content%%:*}"
  [ "$pid" = "$$" ]
  _release_lock
}

@test "stale lock auto-reclaims when PID is dead" {
  source "$LIB"
  local hash lock
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  lock="$CLAUDE_PLUGIN_DATA/cache/${hash}.lock"
  # PID 999999 is essentially guaranteed not to exist; timestamp fresh.
  local now
  now="$(date +%s)"
  printf '999999:%s\n' "$now" > "$lock"

  _acquire_lock
  local content pid
  content="$(cat "$lock")"
  pid="${content%%:*}"
  [ "$pid" = "$$" ]
  _release_lock
}

@test "malformed lock file (no colon) is reclaimed" {
  source "$LIB"
  local hash lock
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  lock="$CLAUDE_PLUGIN_DATA/cache/${hash}.lock"
  printf 'gibberish\n' > "$lock"

  # Sanity: precondition file exists and is malformed (no colon).
  [ -f "$lock" ]
  local planted
  planted="$(cat "$lock")"
  [[ "$planted" != *":"* ]]

  # Short timeout so a reclaim regression fails fast (1s) rather than
  # silently waiting on the malformed file until the default 10s expires.
  run _acquire_lock 1
  [ "$status" -eq 0 ]

  # Verify the resulting lock is owned by us, not the leftover gibberish.
  local content pid
  content="$(cat "$lock")"
  pid="${content%%:*}"
  [ "$pid" = "$$" ]
  _release_lock
}

@test "concurrent write blocks and then succeeds in serial" {
  source "$LIB"

  # Hold the lock in this shell.
  _acquire_lock

  local flag="$CLAUDE_PLUGIN_DATA/bg.flag"

  # Background contender attempts to acquire (timeout 5s); writes flag on success.
  (
    source "$LIB"
    if _acquire_lock 5; then
      printf 'BG-ACQUIRED\n' > "$flag"
      _release_lock
    fi
  ) &
  local bg=$!

  # Give the background a moment to enter its acquire loop.
  sleep 0.3
  # Background must NOT have acquired yet — flag absent.
  [ ! -f "$flag" ]

  # Release; background should now succeed.
  _release_lock
  wait "$bg"

  [ -f "$flag" ]
  grep -q 'BG-ACQUIRED' "$flag"
}

@test "_release_lock is a no-op when lock file is missing" {
  source "$LIB"
  run _release_lock
  [ "$status" -eq 0 ]
}

@test "_release_lock does not delete lock owned by another PID" {
  source "$LIB"
  local hash lock
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  lock="$CLAUDE_PLUGIN_DATA/cache/${hash}.lock"
  # Different (live) PID — use 1 (init/launchd).
  printf '1:%s\n' "$(date +%s)" > "$lock"
  _release_lock
  [ -f "$lock" ]
  # Cleanup
  rm -f "$lock"
}

# ----------------------------------------------------------------------
# PR state cache — merge_commit field (T1.1 — spec 014)
# SDD §Data Storage Changes: extended branch_state entry
# ----------------------------------------------------------------------

@test "_write_pr_state_cache accepts optional merge_commit arg and persists it" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed"
  fi
  source "$LIB"
  _write_pr_state_cache "feat/merged-branch" "MERGED" "99" "abc1234567890"

  local hash json
  hash="$(_repo_hash)"
  json="$CLAUDE_PLUGIN_DATA/cache/${hash}-pr-state.json"
  [ -f "$json" ]
  local mc
  mc="$(jq -r '.branch_state["feat/merged-branch"].merge_commit // empty' "$json")"
  [ "$mc" = "abc1234567890" ]
}

@test "_read_pr_state_cache emits two stdout lines when merge_commit is present" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed"
  fi
  source "$LIB"
  _write_pr_state_cache "feat/merged-branch" "MERGED" "99" "abc1234567890"
  run _read_pr_state_cache "feat/merged-branch"
  [ "$status" -eq 0 ]
  # Line 1: state
  local line1 line2
  line1="$(printf '%s\n' "$output" | sed -n '1p')"
  line2="$(printf '%s\n' "$output" | sed -n '2p')"
  [ "$line1" = "MERGED" ]
  [ "$line2" = "abc1234567890" ]
}

@test "_read_pr_state_cache emits one stdout line when merge_commit is absent" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed"
  fi
  source "$LIB"
  _write_pr_state_cache "feat/open-branch" "OPEN" "55"
  run _read_pr_state_cache "feat/open-branch"
  [ "$status" -eq 0 ]
  # Exactly one non-empty line
  local line_count
  line_count="$(printf '%s\n' "$output" | grep -c '[^[:space:]]')"
  [ "$line_count" -eq 1 ]
  [ "$output" = "OPEN" ]
}

@test "_read_pr_state_cache: legacy cache entry without merge_commit succeeds (one line)" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed"
  fi
  source "$LIB"
  # Write a legacy-format entry manually — no merge_commit field.
  local hash json
  hash="$(_repo_hash)"
  mkdir -p "$CLAUDE_PLUGIN_DATA/cache"
  json="$CLAUDE_PLUGIN_DATA/cache/${hash}-pr-state.json"
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{"version":1,"updated_iso":"%s","branch_state":{"feat/legacy":{"state":"MERGED","checked_iso":"%s","number":7}}}' \
    "$now_iso" "$now_iso" > "$json"

  run _read_pr_state_cache "feat/legacy"
  [ "$status" -eq 0 ]
  # Must produce exactly one line (state only — no merge_commit line)
  local line_count
  line_count="$(printf '%s\n' "$output" | grep -c '[^[:space:]]')"
  [ "$line_count" -eq 1 ]
  [ "$output" = "MERGED" ]
}

@test "_write_pr_state_cache merge_commit atomic: no .tmp file remains" {
  source "$LIB"
  _write_pr_state_cache "feat/merged-branch" "MERGED" "99" "abc1234567890"
  ! ls "$CLAUDE_PLUGIN_DATA/cache/"*.tmp >/dev/null 2>&1
}

@test "_write_pr_state_cache: merge_commit field omitted when arg is empty" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed"
  fi
  source "$LIB"
  _write_pr_state_cache "feat/open-branch" "OPEN" "10" ""

  local hash json
  hash="$(_repo_hash)"
  json="$CLAUDE_PLUGIN_DATA/cache/${hash}-pr-state.json"
  local mc
  mc="$(jq -r '.branch_state["feat/open-branch"].merge_commit // empty' "$json")"
  [ -z "$mc" ]
}

@test "block-bad-git-ops caller: reads only line 1 (state) — unaffected by merge_commit" {
  if ! command -v jq >/dev/null 2>&1; then
    skip "jq not installed"
  fi
  source "$LIB"
  local branch="feat/merged-branch"
  _write_pr_state_cache "$branch" "MERGED" "99" "abc1234567890"
  # Simulate block-bad-git-ops.sh line 229 verbatim (post-W1-fix):
  local _raw state matched
  _raw=$(_read_pr_state_cache "$branch" 2>/dev/null) || _raw=""
  state=$(printf '%s\n' "$_raw" | sed -n '1p')
  # Real case dispatch — falls through to no-match if state is "MERGED\n<sha>"
  case "$state" in
    CLOSED|MERGED) matched=yes ;;
    *)             matched=no  ;;
  esac
  [ "$matched" = "yes" ]
}
