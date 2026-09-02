#!/usr/bin/env bats
#
# tests/bats/githooks_post_merge.bats
#
# Coverage for templates/githooks/post-merge
# Test count: 11
#
# Spec references:
#   - PRD M6 AC1-AC3 — stale-branch surfacing after merge
#   - SDD §Repo-side .githooks/ Templates — post-merge
#   - SDD §Cache Schemas (TSV+JSON dual-write)
#   - ADR-4 — atomic dual-write (TSV+JSON via .tmp → mv)
#   - research/performance.md §3 — single batched gh call mandate
#
# Constraints exercised:
#   - bash 3.2 compatible (no associative arrays, no mapfile)
#   - Single batched gh call — never one per branch
#   - exit 0 always — never blocks a merge
#   - Suggestions on stderr, never stdout
#   - Worktree branches excluded from stale list (M6 AC3)
#   - mktemp: always "${TMPDIR:-/tmp}/...XXXXXX"
#   - GIT_CONFIG_GLOBAL=/dev/null + git -C "$tmpdir" (no parent-repo pollution)
#   - jq + set -uo pipefail: all jq calls use 2>/dev/null || true

bats_require_minimum_version 1.5.0

load 'lib/helpers'

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"
  HOOK="$PLUGIN_ROOT/templates/githooks/post-merge"
  export TESTS_DIR PLUGIN_ROOT FIXTURE_DIR HOOK
}

# Return current time in milliseconds (integer).
# macOS BSD date does not support %3N; use perl Time::HiRes.
_now_ms() {
  perl -MTime::HiRes -e 'printf "%d\n", Time::HiRes::time()*1000'
}

setup() {
  # Sandbox CLAUDE_PLUGIN_DATA so we don't pollute the real data dir.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-post-merge.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  CACHE_DIR="$CLAUDE_PLUGIN_DATA/cache"
  mkdir -p "$CACHE_DIR"

  # Scratch repo with a few local branches for most tests.
  REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-post-merge-repo.XXXXXX")"
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

  # Create the three stale branches that the stale-3-branches stub matches.
  git -C "$REPO" branch "feat/stale-a"
  git -C "$REPO" branch "fix/stale-b"
  git -C "$REPO" branch "chore/stale-c"

  # Resolve canonical path (macOS /tmp -> /private/tmp symlink).
  REPO_CANONICAL="$(cd "$REPO" && git rev-parse --show-toplevel 2>/dev/null)"
  export REPO_CANONICAL

  # Prepend gh stub so tests never call real GitHub.
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH

  # Default scenario (no-op: empty pr-list → no stale branches).
  GH_STUB_SCENARIO="default"
  export GH_STUB_SCENARIO

  # Point CLAUDE_PLUGIN_ROOT to the plugin root so the hook can source lib/cache.sh.
  CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  export CLAUDE_PLUGIN_ROOT
}

teardown() {
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
  if [ -n "${REPO:-}" ] && [ -d "$REPO" ]; then
    chmod -R u+rwX "$REPO" 2>/dev/null || true
    rm -rf "$REPO"
  fi
}

# Compute the repo hash the same way cache.sh._repo_hash does.
_repo_hash() {
  printf '%s' "${REPO_CANONICAL:-$REPO}" | shasum 2>/dev/null | head -c 12
}

# ---------------------------------------------------------------------------
# Test 1: single batched gh call even with many branches
#
# A counting stub writes to a counter file on each invocation.
# Assert counter == 1 (one call) for a 50-branch scenario.
# ---------------------------------------------------------------------------

@test "test_single_batched_gh_call" {
  # Build a 50-branch fixture repo.
  LARGE_REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-post-merge-large.XXXXXX")"

  git -C "$LARGE_REPO" init -q -b main
  git -C "$LARGE_REPO" config commit.gpgsign false
  git -C "$LARGE_REPO" config tag.gpgsign false
  git -C "$LARGE_REPO" config user.name "$GIT_AUTHOR_NAME"
  git -C "$LARGE_REPO" config user.email "$GIT_AUTHOR_EMAIL"

  printf 'initial\n' > "$LARGE_REPO/README.md"
  git -C "$LARGE_REPO" add README.md
  git -C "$LARGE_REPO" commit -q -m "feat: initial"

  local i
  for i in $(seq -w 1 50); do
    git -C "$LARGE_REPO" branch "feat/branch-${i}"
  done

  # Counting stub: replaces gh with a script that increments a counter file
  # and returns an empty merged-PR list.
  local stub_dir
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-gh-counting.XXXXXX")"
  local counter_file="$stub_dir/call_count"
  printf '0' > "$counter_file"

  cat > "$stub_dir/gh" <<'GHSTUB'
#!/bin/bash
counter_file="${GH_CALL_COUNTER_FILE:-/dev/null}"
count=$(cat "$counter_file" 2>/dev/null || printf '0')
printf '%d' $((count + 1)) > "$counter_file"
# Return valid empty array for any pr list call
printf '[]\n'
exit 0
GHSTUB
  chmod +x "$stub_dir/gh"

  GH_CALL_COUNTER_FILE="$counter_file"
  export GH_CALL_COUNTER_FILE

  run bash -c "
    PATH='$stub_dir:$PATH'
    GH_CALL_COUNTER_FILE='$counter_file'
    export GH_CALL_COUNTER_FILE
    cd '$LARGE_REPO' && bash '$HOOK'
  "
  [ "$status" -eq 0 ]

  local count
  count="$(cat "$counter_file")"
  # Exactly 1 gh call, never one-per-branch.
  [ "$count" -eq 1 ]

  rm -rf "$LARGE_REPO" "$stub_dir"
}

# ---------------------------------------------------------------------------
# Test 2: stderr suggestion list when stale branches exist
#
# gh returns 3 merged PRs whose headRefName matches local branches.
# stderr must contain branch names + PR numbers.
# ---------------------------------------------------------------------------

@test "test_stderr_suggestion_when_stale_branches_exist" {
  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  run bash -c "cd '$REPO' && bash '$HOOK'"

  # Exit 0 — never blocks.
  [ "$status" -eq 0 ]

  # All three stale branch names must appear in stderr (captured in $output by bats).
  echo "$output" | grep -q "feat/stale-a"
  echo "$output" | grep -q "fix/stale-b"
  echo "$output" | grep -q "chore/stale-c"

  # PR numbers must appear.
  echo "$output" | grep -q "38"
  echo "$output" | grep -q "40"
  echo "$output" | grep -q "42"
}

# ---------------------------------------------------------------------------
# Test 3: no stdout output even when stale branches found
#
# Suggestions go to stderr ONLY. stdout must be empty.
# ---------------------------------------------------------------------------

@test "test_no_stdout_output" {
  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  # Capture only stdout via process substitution; redirect hook stderr to /dev/null.
  stdout_out="$(cd "$REPO" && bash "$HOOK" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

# ---------------------------------------------------------------------------
# Test 4: exit zero when stale branches exist — never blocks a merge
# ---------------------------------------------------------------------------

@test "test_exit_zero_when_stale_branches_exist" {
  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  run bash -c "cd '$REPO' && bash '$HOOK'"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Test 5: atomic TSV + JSON cache write via lib/cache.sh
#
# CLAUDE_PLUGIN_ROOT is set (via setup) so lib/cache.sh is sourceable.
# After hook runs with stale branches: both .tsv and .json exist; both
# contain matching branch data; no .tmp files remain.
#
# This test exercises the lib/cache.sh._write_stale_cache code path.
# It must fail if lib/cache.sh is not loadable (CLAUDE_PLUGIN_ROOT unset
# or lib absent) — confirmed by test_no_cache_write_in_standalone_mode.
# ---------------------------------------------------------------------------

@test "test_atomic_tsv_and_json_cache_write" {
  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  # Verify precondition: lib/cache.sh must be reachable via CLAUDE_PLUGIN_ROOT.
  [ -f "${CLAUDE_PLUGIN_ROOT}/scripts/lib/cache.sh" ]

  run bash -c "cd '$REPO' && bash '$HOOK'"
  [ "$status" -eq 0 ]

  local hash
  hash="$(_repo_hash)"
  local tsv="$CACHE_DIR/${hash}-stale-cache.tsv"
  local json="$CACHE_DIR/${hash}-stale-cache.json"

  # Both files must exist (written by lib/cache.sh._write_stale_cache).
  [ -f "$tsv" ]
  [ -f "$json" ]

  # TSV must contain branch names (tab-delimited data rows).
  grep -q "feat/stale-a" "$tsv"
  grep -q "fix/stale-b" "$tsv"

  # JSON must contain stale_branches array with matching entries.
  grep -q "feat/stale-a" "$json"
  grep -q "fix/stale-b" "$json"

  # No .tmp files left over (atomic mv completed).
  local tmp_count
  tmp_count="$(find "$CACHE_DIR" -name '*.tmp' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$tmp_count" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Test 6: degraded mode — gh unavailable → exit 0, one structured stderr line
#
# PATH excludes gh entirely. The hook must not block the merge (exit 0) and
# must say why it did nothing, in the structured single-line format — see SDD
# §Error Handling Table and PRD AC-F5.1 ("every guard path emits exactly one
# stderr line"). Same contract as the post-merge case in
# hooks-runtime-contract.bats.
# ---------------------------------------------------------------------------

@test "test_degraded_mode_gh_unavailable" {
  # Build a PATH holding only what the hook needs to reach its gh check.
  #
  # The previous approach subtracted `dirname $(command -v gh)` from the real
  # PATH, which assumes gh lives in exactly one PATH directory. On a GitHub
  # runner it does not — removing one copy leaves another, `command -v gh`
  # succeeds, and the hook falls through to the *unauthenticated* branch and
  # emits "gh CLI unauthenticated" instead of degrading silently.
  local no_gh_path
  no_gh_path="$(_minimal_path bash git dirname)"

  run bash -c "
    PATH='$no_gh_path'
    export PATH
    cd '$REPO' && bash '$HOOK' 2>&1
  "

  [ "$status" -eq 0 ]

  # Exactly one structured line, naming the guard and the missing tool.
  local line_count
  line_count="$(printf '%s\n' "$output" | grep -c '^tcs-git-helpers:' 2>/dev/null || true)"
  [ "$line_count" -eq 1 ]
  [[ "$output" == *"gh"* ]]
  [[ "$output" == *"skipped"* ]]
}

# ---------------------------------------------------------------------------
# Test 7: degraded mode — CLAUDE_PLUGIN_DATA unset
#
# Hook still emits stderr suggestion but skips cache write.
# ---------------------------------------------------------------------------

@test "test_degraded_mode_no_plugin_data" {
  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  run bash -c "
    unset CLAUDE_PLUGIN_DATA
    cd '$REPO' && bash '$HOOK'
  "

  # Must still exit 0.
  [ "$status" -eq 0 ]

  # Suggestion must still appear on stderr (output in bats is combined).
  echo "$output" | grep -q "feat/stale-a"

  # No cache files should have been written anywhere (CLAUDE_PLUGIN_DATA was unset).
  # The cache.sh fallback is ${HOME}/.claude/plugin-data — check that dir is clean.
  local default_cache="${HOME}/.claude/plugin-data/cache"
  if [ -d "$default_cache" ]; then
    local hash
    hash="$(_repo_hash)"
    # These specific test-repo files must not exist.
    [ ! -f "$default_cache/${hash}-stale-cache.tsv" ]
    [ ! -f "$default_cache/${hash}-stale-cache.json" ]
  fi
}

# ---------------------------------------------------------------------------
# Test 8: worktree branches excluded from stale list (M6 AC3)
#
# Create a branch checked out in a separate worktree. gh reports it as merged.
# Hook must NOT include it in the stale/suggestion list.
# ---------------------------------------------------------------------------

@test "test_excludes_worktree_branches" {
  # Create an additional branch that will be in the worktree.
  git -C "$REPO" branch "feat/in-worktree"

  # Add a worktree checked out on feat/in-worktree.
  local wt_dir
  wt_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-worktree.XXXXXX")"
  git -C "$REPO" worktree add "$wt_dir" "feat/in-worktree" -q

  # Also keep feat/stale-a as a plain local branch (not in a worktree).
  # Scenario: stale-3-branches reports feat/stale-a, fix/stale-b, chore/stale-c
  # plus feat/not-local (not a local branch, so filtered by cross-ref).
  # We want to add feat/in-worktree to that merged list too.
  local stub_dir
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-gh-wt.XXXXXX")"
  cat > "$stub_dir/gh" <<'GHSTUB'
#!/bin/bash
printf '[
  {"number":38,"headRefName":"feat/stale-a","mergedAt":"2026-04-12T10:00:00Z"},
  {"number":55,"headRefName":"feat/in-worktree","mergedAt":"2026-04-18T12:00:00Z"}
]\n'
exit 0
GHSTUB
  chmod +x "$stub_dir/gh"

  run bash -c "
    PATH='$stub_dir:$PATH'
    export PATH
    cd '$REPO' && bash '$HOOK'
  "

  [ "$status" -eq 0 ]

  # feat/stale-a should appear (it's stale, not in a worktree).
  echo "$output" | grep -q "feat/stale-a"

  # feat/in-worktree must be excluded — AC3.
  if echo "$output" | grep -q "feat/in-worktree"; then
    echo "ERROR: worktree branch appeared in stale list" >&2
    return 1
  fi

  # Cleanup.
  git -C "$REPO" worktree remove "$wt_dir" --force 2>/dev/null || true
  rm -rf "$wt_dir" "$stub_dir"
}

# ---------------------------------------------------------------------------
# Test 9: version marker on line 2
# ---------------------------------------------------------------------------

@test "test_version_marker_line_2" {
  local line2
  line2="$(sed -n '2p' "$HOOK")"
  # Source template carries the v__TCS_GIT_HELPERS_VERSION__ placeholder, which
  # install_files.sh substitutes with the concrete version at install time.
  # Accept either the placeholder or a concrete vN.N.N marker.
  echo "$line2" | grep -qE '^# tcs-git-helpers: v(__TCS_GIT_HELPERS_VERSION__|[0-9]+\.[0-9]+\.[0-9]+)'
}

# ---------------------------------------------------------------------------
# Test 10: performance — p99 under 10s on 50-branch fixture
#
# gh call is stubbed (returns empty array instantly).
# Measures bash + jq + cache-write cost for 100 invocations.
# ---------------------------------------------------------------------------

@test "test_perf_p99_under_10s_50_branch" {
  # Build a 50-branch repo.
  local large_repo
  large_repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-post-merge-perf.XXXXXX")"

  git -C "$large_repo" init -q -b main
  git -C "$large_repo" config commit.gpgsign false
  git -C "$large_repo" config tag.gpgsign false
  git -C "$large_repo" config user.name "$GIT_AUTHOR_NAME"
  git -C "$large_repo" config user.email "$GIT_AUTHOR_EMAIL"

  printf 'initial\n' > "$large_repo/README.md"
  git -C "$large_repo" add README.md
  git -C "$large_repo" commit -q -m "feat: initial"

  local i
  for i in $(seq -w 1 50); do
    git -C "$large_repo" branch "feat/branch-${i}"
  done

  # Fast stub: returns empty merged list instantly.
  local fast_stub_dir
  fast_stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-gh-fast.XXXXXX")"
  cat > "$fast_stub_dir/gh" <<'GHSTUB'
#!/bin/bash
printf '[]\n'
exit 0
GHSTUB
  chmod +x "$fast_stub_dir/gh"

  local times_file
  times_file="$(mktemp "${TMPDIR:-/tmp}/tcs-perf-times.XXXXXX")"

  local n=100
  for i in $(seq 1 $n); do
    local t0 t1 elapsed
    t0="$(_now_ms)"
    bash -c "
      PATH='$fast_stub_dir:$PATH'
      export CLAUDE_PLUGIN_DATA='$CLAUDE_PLUGIN_DATA'
      cd '$large_repo' && bash '$HOOK' 2>/dev/null
    "
    t1="$(_now_ms)"
    elapsed=$(( t1 - t0 ))
    printf '%d\n' "$elapsed" >> "$times_file"
  done

  # Compute p99 (sort numerically, pick 99th percentile of 100 samples = index 98, 0-based).
  local p99
  p99="$(sort -n "$times_file" | awk 'NR==99{print}')"

  rm -f "$times_file"
  rm -rf "$large_repo" "$fast_stub_dir"

  # p99 must be under 10000ms.
  [ "$p99" -lt "$(_perf_budget 10000)" ]
}

# ---------------------------------------------------------------------------
# Test 11: no per-branch gh loop — explicit counter assertion
#
# Even with 50 branches, gh is called exactly once.
# This is separate from test_single_batched_gh_call to serve as a
# unit-isolated check.
# ---------------------------------------------------------------------------

@test "test_no_per_branch_gh_loop" {
  local large_repo
  large_repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-post-merge-loop.XXXXXX")"

  git -C "$large_repo" init -q -b main
  git -C "$large_repo" config commit.gpgsign false
  git -C "$large_repo" config tag.gpgsign false
  git -C "$large_repo" config user.name "$GIT_AUTHOR_NAME"
  git -C "$large_repo" config user.email "$GIT_AUTHOR_EMAIL"

  printf 'initial\n' > "$large_repo/README.md"
  git -C "$large_repo" add README.md
  git -C "$large_repo" commit -q -m "feat: initial"

  local i
  for i in $(seq -w 1 50); do
    git -C "$large_repo" branch "feat/branch-${i}"
  done

  local counter_dir
  counter_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-gh-counter2.XXXXXX")"
  local counter_file="$counter_dir/count"
  printf '0' > "$counter_file"

  cat > "$counter_dir/gh" <<GHSTUB2
#!/bin/bash
c=\$(cat "$counter_file" 2>/dev/null || printf '0')
printf '%d' \$((c + 1)) > "$counter_file"
printf '[]\n'
exit 0
GHSTUB2
  chmod +x "$counter_dir/gh"

  run bash -c "
    PATH='$counter_dir:$PATH'
    export PATH
    cd '$large_repo' && bash '$HOOK'
  "

  [ "$status" -eq 0 ]

  local final_count
  final_count="$(cat "$counter_file")"
  [ "$final_count" -eq 1 ]

  rm -rf "$large_repo" "$counter_dir"
}
