#!/usr/bin/env bash
#
# tests/bats/lib/helpers.bash
#
# Shared bats helper functions used by block-bad-git-ops.bats and
# integration-m1-m2.bats. Load with:
#
#   load 'lib/helpers'
#
# Requires: jq, git, shasum (standard on macOS and most Linux distros).
# bash 3.2 compatible (no associative arrays, no mapfile).

# Build a tool_input JSON envelope and pipe it to the hook.
# $1 = bash command string. Returns the hook's stdout/stderr/exit via $output etc.
_run_hook_with_cmd() {
  local cmd="$1"
  local input
  input=$(jq -n --arg c "$cmd" '{tool_name:"Bash", tool_input:{command:$c}}')
  printf '%s' "$input" | bash "$HOOK"
}

# Run the hook and assert: exit 0, stdout contains a deny JSON, deny reason
# mentions the supplied rule name AND a `references/` link (per SDD/PRD —
# every deny carries rule + reference + override hint). Use
# `run --separate-stderr` outside if you need stderr separately.
_assert_deny_for_rule() {
  local rule="$1"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"deny"'* ]] \
    || { echo "expected deny JSON, got: $output" >&2; return 1; }
  [[ "$output" == *"$rule"* ]] \
    || { echo "expected rule $rule in reason, got: $output" >&2; return 1; }
  [[ "$output" == *"references/"* ]] \
    || { echo "expected reference-doc link in reason, got: $output" >&2; return 1; }
  return 0
}

# Run the hook and assert: exit 0, NO deny JSON on stdout (allow path).
_assert_allow() {
  [ "$status" -eq 0 ]
  if [[ "$output" == *'"permissionDecision":"deny"'* ]]; then
    echo "expected ALLOW (no deny JSON), got: $output" >&2
    return 1
  fi
  return 0
}

# Seed the PR-state cache with a fresh entry for <branch> in <repo>.
# Usage: _seed_pr_cache <repo_path> <branch> <state> [<merge_commit>]
_seed_pr_cache() {
  local repo_path="$1"
  local branch="$2"
  local state="$3"
  local merge_commit="${4:-}"

  # Derive repo hash identical to cache.sh: SHA1 prefix of repo top-level path.
  # Must use git rev-parse --show-toplevel to resolve symlinks (e.g. /tmp →
  # /private/tmp on macOS) so the hash matches what the hook computes at runtime.
  local resolved_path
  resolved_path="$(git -C "$repo_path" rev-parse --show-toplevel 2>/dev/null)" \
    || resolved_path="$repo_path"

  local hash
  hash="$(printf '%s' "$resolved_path" | shasum 2>/dev/null | head -c 12)"

  local cache_dir="$CLAUDE_PLUGIN_DATA/cache"
  local f="$cache_dir/${hash}-pr-state.json"
  mkdir -p "$cache_dir"

  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # Build the cache JSON, optionally including merge_commit.
  if [ -n "$merge_commit" ]; then
    jq -n \
      --arg branch "$branch" \
      --arg state "$state" \
      --arg now "$now_iso" \
      --arg mc "$merge_commit" \
      '{
        version: 1,
        updated_iso: $now,
        branch_state: {
          ($branch): { state: $state, checked_iso: $now, merge_commit: $mc }
        }
      }' > "$f"
  else
    jq -n \
      --arg branch "$branch" \
      --arg state "$state" \
      --arg now "$now_iso" \
      '{
        version: 1,
        updated_iso: $now,
        branch_state: {
          ($branch): { state: $state, checked_iso: $now }
        }
      }' > "$f"
  fi
}

# Build a minimal git repo on a named branch with N commits.
# Prints repo path on stdout. Caller owns cleanup.
# Usage: _build_ahead_repo <branch_name> <n_commits_after_base>
_build_ahead_repo() {
  local branch="$1"
  local extra_commits="${2:-0}"
  local repo
  repo="$(mktemp -d "${TMPDIR:-/tmp}/tcs-t13.XXXXXX")"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t"
  git -C "$repo" config user.name "t"
  git -C "$repo" config commit.gpgsign false
  printf 'base\n' > "$repo/base.txt"
  git -C "$repo" add base.txt
  git -C "$repo" commit -q -m "base"
  git -C "$repo" checkout -q -b "$branch"
  local i=0
  while [ "$i" -lt "$extra_commits" ]; do
    printf 'extra %s\n' "$i" > "$repo/extra${i}.txt"
    git -C "$repo" add "extra${i}.txt"
    git -C "$repo" commit -q -m "extra $i"
    i=$((i + 1))
  done
  printf '%s\n' "$repo"
}

# Print a PATH consisting of a single throwaway directory that contains
# symlinks to exactly the named tools and nothing else. Use it to simulate
# "<tool> is not installed" for `command -v` guards.
#
# Why not PATH=/bin? That only works on macOS, where /bin is a small directory
# holding bash and coreutils. On Linux /bin is a symlink to /usr/bin, so gh and
# jq are right there and the guard never fires — the test then fails for a
# reason that has nothing to do with the code under test.
#
# Usage: PATH="$(_minimal_path bash git dirname)"
# bash 3.2 compatible.
_minimal_path() {
  local dir tool src
  dir="$(mktemp -d "${BATS_TEST_TMPDIR:-${TMPDIR:-/tmp}}/minbin.XXXXXX")"
  for tool in "$@"; do
    src="$(command -v "$tool" 2>/dev/null)" || continue
    [ -n "$src" ] && ln -s "$src" "$dir/$tool"
  done
  printf '%s' "$dir"
}

# Scale a wall-clock budget by $TCS_PERF_SLACK (default 1).
#
# The budgets in this suite come from SDD requirements measured on a developer
# machine. A hosted CI runner is shared, noisy hardware, and the measurement
# harness itself (a `perl` invocation per iteration) costs milliseconds — so
# asserting the raw number there measures the runner as much as the code. That
# is not hypothetical: on macos-latest the nudge hook clocked p99=56ms against
# a 50ms budget, a 12% overshoot with no regression behind it, while ubuntu
# passed the same assertion by luck rather than by margin.
#
# CI sets TCS_PERF_SLACK=4, which still fails a real regression (a 50ms hook
# that becomes a 2s hook) while tolerating the noise floor. Locally the factor
# is 1, so `./scripts/dev/test.sh` enforces the specified budget exactly.
#
# Usage: [ "$p99" -lt "$(_perf_budget 150)" ]
# bash 3.2 compatible.
_perf_budget() {
  local budget="$1"
  local slack="${TCS_PERF_SLACK:-1}"
  case "$slack" in
    ''|*[!0-9]*) slack=1 ;;
  esac
  [ "$slack" -lt 1 ] && slack=1
  printf '%d' $((budget * slack))
}
