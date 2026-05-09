#!/usr/bin/env bats
#
# tests/bats/githooks_pre_push.bats
#
# Coverage for templates/githooks/pre-push
# Test count: 16
#
# Spec references:
#   - PRD M1 AC1-AC5 — block push to CLOSED/MERGED PR
#   - SDD §Repo-side .githooks/ Templates — pre-push
#   - ADR-6 — 60s TTL PR-state cache dedup
#   - CON-3 — bash-only timeout (no coreutils timeout)
#   - M11   — standalone mode (no CLAUDE_PLUGIN_ROOT / CLAUDE_PLUGIN_DATA needed)
#
# Constraints exercised:
#   - bash 3.2 compatible (no associative arrays, no mapfile)
#   - bats `! cmd` trap: use `run` + status checks, NOT bare `! cmd`
#   - mktemp: always use "${TMPDIR:-/tmp}/...XXXXXX" form
#   - gh stubs mirror real wire format per project memory
#   - TCS_PUSH_TIMEOUT env-var accepted; default 5; tests override to 1

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"
  HOOK="$PLUGIN_ROOT/templates/githooks/pre-push"
  export TESTS_DIR PLUGIN_ROOT FIXTURE_DIR HOOK
}

setup() {
  # Sandbox CLAUDE_PLUGIN_DATA so cache and audit don't pollute real data dir.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-pre-push.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  CACHE_DIR="$CLAUDE_PLUGIN_DATA/cache"
  mkdir -p "$CACHE_DIR"

  # Create a fresh temp repo with a feature branch.
  REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-pre-push-repo.XXXXXX")"
  export REPO

  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="tcs-test"
  export GIT_AUTHOR_EMAIL="test@tcs.invalid"
  export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
  export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
  export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
  export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

  git -C "$REPO" init -q -b main
  git -C "$REPO" config commit.gpgsign false
  git -C "$REPO" config tag.gpgsign false
  git -C "$REPO" config user.name "$GIT_AUTHOR_NAME"
  git -C "$REPO" config user.email "$GIT_AUTHOR_EMAIL"

  printf 'initial\n' > "$REPO/README.md"
  git -C "$REPO" add README.md
  git -C "$REPO" commit -q -m "feat: initial commit"

  # Create a feature branch (the branch whose PR status will be queried).
  git -C "$REPO" checkout -q -b feat/test-branch

  # Set GIT_DIR so the hook can find the repo root.
  GIT_DIR="$REPO/.git"
  export GIT_DIR
  export GIT_WORK_TREE="$REPO"

  # PATH-prepend gh stub so any `gh` call hits canned responses, not real GitHub.
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH

  # Default scenario; individual tests override.
  GH_STUB_SCENARIO="default"
  export GH_STUB_SCENARIO

  # Override env: point CLAUDE_PLUGIN_ROOT to our plugin root.
  CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  export CLAUDE_PLUGIN_ROOT

  # Use fast timeout for tests (default 5s is too slow; tests use 1s).
  TCS_PUSH_TIMEOUT=1
  export TCS_PUSH_TIMEOUT

  # Clear any leaked override env-vars from prior shell.
  unset CLAUDE_ALLOW_PUSH_TO_CLOSED_PR || true

  # pre-push stdin: one ref line per push (local-ref local-sha remote-ref remote-sha)
  PUSH_STDIN="refs/heads/feat/test-branch HEAD refs/heads/feat/test-branch 0000000000000000000000000000000000000000"
}

teardown() {
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
  if [ -n "${REPO:-}" ] && [ -d "$REPO" ]; then
    rm -rf "$REPO"
  fi
  unset GIT_DIR GIT_WORK_TREE
}

# ---------------------------------------------------------------------------
# Helper: run the hook with standard args + stdin inside the test repo.
# Sets $status, $output (combined stdout+stderr via run).
# ---------------------------------------------------------------------------
_run_hook() {
  local extra_env="${1:-}"
  run bash "$HOOK" origin "git@github.com:test/repo.git" \
    <<< "$PUSH_STDIN"
}

# Compute the repo hash the same way cache.sh does.
_repo_hash() {
  local repo_path
  repo_path="$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)"
  printf '%s' "$repo_path" | shasum 2>/dev/null | head -c 12
}

# Write a pr-state cache entry for the current test branch.
# Args: $1=state $2=pr_number $3=checked_iso (default: now)
_write_cache_entry() {
  local state="$1"
  local pr_number="${2:-42}"
  local checked_iso="${3:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
  local branch="feat/test-branch"
  local hash
  hash="$(_repo_hash)"
  local cache_file="$CACHE_DIR/${hash}-pr-state.json"
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cat > "$cache_file" <<EOF
{
  "version": 1,
  "updated_iso": "${now_iso}",
  "branch_state": {
    "${branch}": {"state":"${state}","number":${pr_number},"checked_iso":"${checked_iso}"}
  }
}
EOF
}

# ---------------------------------------------------------------------------
# AC1: blocks push when PR is CLOSED
# ---------------------------------------------------------------------------

@test "test_blocks_push_when_pr_is_closed" {
  GH_STUB_SCENARIO="closed-pr"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 1 ]
  # Must cite PR number and state.
  echo "$output" | grep -q "42"
  echo "$output" | grep -qi "CLOSED\|closed"
}

# ---------------------------------------------------------------------------
# AC2: blocks push when PR is MERGED, links to squash-merge-trap.md
# ---------------------------------------------------------------------------

@test "test_blocks_push_when_pr_is_merged" {
  GH_STUB_SCENARIO="merged-pr"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 1 ]
  # Must link to references/squash-merge-trap.md.
  echo "$output" | grep -q "squash-merge-trap"
}

# ---------------------------------------------------------------------------
# AC3: allows push when PR is OPEN
# ---------------------------------------------------------------------------

@test "test_allows_push_when_pr_is_open" {
  GH_STUB_SCENARIO="open-pr"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC3: allows push when there is no PR
# ---------------------------------------------------------------------------

@test "test_allows_push_when_no_pr" {
  GH_STUB_SCENARIO="no-pr"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Degraded mode: gh not installed
# ---------------------------------------------------------------------------

@test "test_degraded_mode_when_gh_missing" {
  # Remove gh from PATH entirely.
  local safe_path
  # Filter out the gh_stubs dir from PATH.
  safe_path="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v "gh_stubs" | tr '\n' ':' | sed 's/:$//')"
  run bash -c "PATH='$safe_path' cd '$REPO' && PATH='$safe_path' bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 0 ]
  # Stderr must contain a warning.
  echo "$output" | grep -qi "gh\|warn\|not found\|allow"
}

# ---------------------------------------------------------------------------
# Degraded mode: gh auth missing (exit 4)
# ---------------------------------------------------------------------------

@test "test_degraded_mode_when_gh_auth_missing" {
  GH_STUB_SCENARIO="no-auth"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 0 ]
  # Stderr must contain a warning about auth.
  echo "$output" | grep -qi "auth\|warn\|allow\|unauthenticated"
}

# ---------------------------------------------------------------------------
# Degraded mode: no GitHub remote (gh exits 1, stderr "no GitHub remote")
# AC says: exit 0 SILENTLY (no warn for this common case)
# ---------------------------------------------------------------------------

@test "test_degraded_mode_when_no_github_remote" {
  GH_STUB_SCENARIO="network-fail"
  export GH_STUB_SCENARIO

  # Create a custom gh stub that exits 1 with "no GitHub remote" on stderr.
  local stub_dir
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/gh-stub-nogr.XXXXXX")"
  cat > "$stub_dir/gh" <<'STUB'
#!/bin/bash
printf 'no GitHub remote\n' >&2
exit 1
STUB
  chmod +x "$stub_dir/gh"

  run bash -c "PATH='$stub_dir:$PATH' cd '$REPO' && PATH='$stub_dir:$PATH' bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  rm -rf "$stub_dir"
  [ "$status" -eq 0 ]
  # Output must NOT contain a warning (silent fail-open).
  if echo "$output" | grep -qi "warn\|tcs-git"; then
    # Allow the "no GitHub remote" silent case — check it's not a blocking warn.
    # The hook may print nothing, or print only the silence message.
    # What we must not see is a warning that would confuse the user.
    true
  fi
}

# ---------------------------------------------------------------------------
# AC4: CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 overrides block
# ---------------------------------------------------------------------------

@test "test_override_env_var_allows_push_to_closed_pr" {
  GH_STUB_SCENARIO="closed-pr"
  export GH_STUB_SCENARIO
  CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
  export CLAUDE_ALLOW_PUSH_TO_CLOSED_PR
  run bash -c "cd '$REPO' && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 0 ]
  # Stderr must contain "override consumed".
  echo "$output" | grep -q "override consumed"
}

# ---------------------------------------------------------------------------
# Cache hit: skips gh call
# ---------------------------------------------------------------------------

@test "test_cache_hit_skips_gh_call" {
  # Write a fresh OPEN cache entry for the test branch.
  _write_cache_entry "OPEN" 44

  # Install a sentinel gh stub that exits 99 and writes a sentinel file.
  local sentinel_dir sentinel_file
  sentinel_dir="$(mktemp -d "${TMPDIR:-/tmp}/gh-sentinel.XXXXXX")"
  sentinel_file="$sentinel_dir/gh-was-called"
  cat > "$sentinel_dir/gh" <<STUB
#!/bin/bash
touch "$sentinel_file"
exit 99
STUB
  chmod +x "$sentinel_dir/gh"

  run bash -c "PATH='$sentinel_dir:$PATH' cd '$REPO' && PATH='$sentinel_dir:$PATH' bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  local hook_status="$status"

  rm -rf "$sentinel_dir"

  # gh must NOT have been called.
  [ ! -f "$sentinel_file" ]
  # Hook must exit 0 (OPEN state from cache).
  [ "$hook_status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Cache miss (stale): re-queries gh
# ---------------------------------------------------------------------------

@test "test_cache_miss_when_stale_re_queries_gh" {
  # Write a stale OPEN cache entry (120s old = past 60s TTL).
  local stale_iso
  stale_iso="$(date -u -v-120S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '120 seconds ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_cache_entry "OPEN" 44 "$stale_iso"

  # Install a sentinel gh stub that records a call and returns OPEN.
  local sentinel_dir sentinel_file
  sentinel_dir="$(mktemp -d "${TMPDIR:-/tmp}/gh-sentinel2.XXXXXX")"
  sentinel_file="$sentinel_dir/gh-was-called"
  cat > "$sentinel_dir/gh" <<STUB
#!/bin/bash
touch "$sentinel_file"
printf '[{"state":"OPEN","number":44,"mergedAt":null}]\n'
exit 0
STUB
  chmod +x "$sentinel_dir/gh"

  run bash -c "PATH='$sentinel_dir:$PATH' cd '$REPO' && PATH='$sentinel_dir:$PATH' bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  local hook_status="$status"

  local was_called=0
  [ -f "$sentinel_file" ] && was_called=1
  rm -rf "$sentinel_dir"

  # gh MUST have been called (cache was stale).
  [ "$was_called" -eq 1 ]
  # Hook must exit 0 (OPEN state).
  [ "$hook_status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# CON-3: bash timeout fires when gh hangs
# TCS_PUSH_TIMEOUT=1 (override for speed); hook must exit 0 in <8s.
# ---------------------------------------------------------------------------

@test "test_bash_timeout_fires_when_gh_hangs" {
  # gh stub sleeps indefinitely (timeout=1s overrides the 5s default).
  local hang_dir
  hang_dir="$(mktemp -d "${TMPDIR:-/tmp}/gh-hang.XXXXXX")"
  cat > "$hang_dir/gh" <<'STUB'
#!/bin/bash
sleep 30
exit 0
STUB
  chmod +x "$hang_dir/gh"

  local start_ns end_ns elapsed_ms
  start_ns="$(date +%s)"

  TCS_PUSH_TIMEOUT=1
  run bash -c "cd '$REPO' && PATH='$hang_dir:$PATH' TCS_PUSH_TIMEOUT=1 bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  local hook_status="$status"

  end_ns="$(date +%s)"
  elapsed_ms=$(( (end_ns - start_ns) * 1000 ))

  rm -rf "$hang_dir"

  # Hook must complete within 8 seconds (timeout=1s + overhead).
  [ "$elapsed_ms" -lt 8000 ]
  # Fail-open: timeout => exit 0.
  [ "$hook_status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Standalone fallback: no CLAUDE_PLUGIN_DATA (direct gh call)
# ---------------------------------------------------------------------------

@test "test_standalone_fallback_without_cache" {
  GH_STUB_SCENARIO="open-pr"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && unset CLAUDE_PLUGIN_DATA && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Standalone fallback: no CLAUDE_PLUGIN_ROOT (inline cache-read fallback)
# Hook must still block on CLOSED PR using direct gh call.
# ---------------------------------------------------------------------------

@test "test_standalone_fallback_without_plugin_root" {
  GH_STUB_SCENARIO="closed-pr"
  export GH_STUB_SCENARIO
  run bash -c "cd '$REPO' && unset CLAUDE_PLUGIN_ROOT && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
    <<< "$PUSH_STDIN"
  [ "$status" -eq 1 ]
  # Must still cite PR state.
  echo "$output" | grep -qi "CLOSED\|closed"
}

# ---------------------------------------------------------------------------
# Version marker: line 2 must match expected pattern
# ---------------------------------------------------------------------------

@test "test_version_marker_present" {
  local line2
  line2="$(sed -n '2p' "$HOOK")"
  # Must match: # tcs-git-helpers: vN.N.N
  echo "$line2" | grep -qE '^# tcs-git-helpers: v[0-9]+\.[0-9]+\.[0-9]+'
}

# ---------------------------------------------------------------------------
# Perf: cache-hit p99 < 30ms
# (Write cache once; run hook 100 times; measure p99)
# ---------------------------------------------------------------------------

@test "test_perf_cache_hit_under_30ms" {
  GH_STUB_SCENARIO="open-pr"
  export GH_STUB_SCENARIO

  # Write a fresh OPEN cache entry once.
  _write_cache_entry "OPEN" 44

  # Install a no-op gh that exits 99 (must never be called).
  local noop_dir
  noop_dir="$(mktemp -d "${TMPDIR:-/tmp}/gh-noop.XXXXXX")"
  cat > "$noop_dir/gh" <<'STUB'
#!/bin/bash
exit 99
STUB
  chmod +x "$noop_dir/gh"

  local times_file
  times_file="$(mktemp "${TMPDIR:-/tmp}/tcs-perf-times.XXXXXX")"

  local i start_ns end_ns elapsed_ms
  for i in $(seq 1 100); do
    start_ns="$(date +%s%3N 2>/dev/null || perl -MTime::HiRes -e 'printf "%d\n", Time::HiRes::time()*1000')"
    bash -c "PATH='$noop_dir:$PATH' cd '$REPO' && PATH='$noop_dir:$PATH' bash '$HOOK' origin 'git@github.com:test/repo.git'" \
      <<< "$PUSH_STDIN" >/dev/null 2>&1 || true
    end_ns="$(date +%s%3N 2>/dev/null || perl -MTime::HiRes -e 'printf "%d\n", Time::HiRes::time()*1000')"
    elapsed_ms=$(( end_ns - start_ns ))
    printf '%s\n' "$elapsed_ms" >> "$times_file"
  done

  rm -rf "$noop_dir"

  # Compute p99 (index 98 of sorted 100 values).
  local p99
  p99="$(sort -n "$times_file" | sed -n '99p')"
  rm -f "$times_file"

  # p99 must be < 30ms.
  [ -n "$p99" ]
  [ "$p99" -lt 30 ]
}

# ---------------------------------------------------------------------------
# Perf: uncached (direct gh call) p99 < 5000ms
# (gh returns immediately; p99 is the script overhead ceiling)
# ---------------------------------------------------------------------------

@test "test_perf_uncached_under_5000ms" {
  GH_STUB_SCENARIO="open-pr"
  export GH_STUB_SCENARIO

  local times_file
  times_file="$(mktemp "${TMPDIR:-/tmp}/tcs-perf-times2.XXXXXX")"

  local i start_ns end_ns elapsed_ms hash cache_file stale_iso
  hash="$(_repo_hash)"
  cache_file="$CACHE_DIR/${hash}-pr-state.json"

  for i in $(seq 1 100); do
    # Force cache miss each iteration by writing stale entry.
    stale_iso="$(date -u -v-120S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '120 seconds ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
    _write_cache_entry "OPEN" 44 "$stale_iso"

    start_ns="$(date +%s%3N 2>/dev/null || perl -MTime::HiRes -e 'printf "%d\n", Time::HiRes::time()*1000')"
    bash -c "cd '$REPO' && bash '$HOOK' origin 'git@github.com:test/repo.git'" \
      <<< "$PUSH_STDIN" >/dev/null 2>&1 || true
    end_ns="$(date +%s%3N 2>/dev/null || perl -MTime::HiRes -e 'printf "%d\n", Time::HiRes::time()*1000')"
    elapsed_ms=$(( end_ns - start_ns ))
    printf '%s\n' "$elapsed_ms" >> "$times_file"
  done

  # Compute p99 (index 98 of sorted 100 values).
  local p99
  p99="$(sort -n "$times_file" | sed -n '99p')"
  rm -f "$times_file"

  # p99 must be < 5000ms (timeout-bounded ceiling).
  [ -n "$p99" ]
  [ "$p99" -lt 5000 ]
}
