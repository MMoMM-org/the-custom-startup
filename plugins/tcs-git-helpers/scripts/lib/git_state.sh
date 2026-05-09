#!/usr/bin/env bash
# scripts/lib/git_state.sh — branch / PR / working-tree state queries
#
# Sourced by hook scripts. Exposes (BranchState per SDD §Application Data Models):
#   _get_branch_state              — populates BRANCH_NAME, BRANCH_STATE, BRANCH_AHEAD,
#                                    BRANCH_BEHIND, PR_STATE, PR_NUMBER, DETACHED_HEAD,
#                                    REBASE_IN_PROGRESS, MERGE_IN_PROGRESS,
#                                    CHERRY_PICK_IN_PROGRESS, BISECT_IN_PROGRESS
#   _is_branch_squash_merged       — 0 if `git cherry` output is all `-`; else 1; 2 on git error
#   _is_branch_dangerously_merged  — 0 if branch tip is orphan from default AND patches applied;
#                                    1 if branch tip IS ancestor of default (merge-commit / safe);
#                                    2 on git error
#   _bypass_state_check            — 0 if any *_IN_PROGRESS flag or DETACHED_HEAD set
#   _detect_default_branch         — echoes "main"/"master"/whatever via origin/HEAD chain
#   _get_pr_state <branch>         — echoes "<STATE>\n<NUMBER>"; fail-open per CON-4
#   git_safe                       — git wrapper filtering known harmless `.git/config` warnings
#
# Constraints (CON-1 / CON-9 / SDD §Worktree Behavior):
#   - bash 3.2-compat: no `declare -A`, no `mapfile`/`readarray`, no `${var,,}`.
#   - Regex uses POSIX ERE only: `[[:space:]]+` not `\s+`; word bounds `[[:<:]]`/`[[:>:]]` not `\b`.
#   - All git invocations use `git -C "$PWD"` (or accept a path arg) for worktree-correctness.
# shellcheck shell=bash

# Idempotent guard — sourcing twice in the same process is a no-op.
if [ -n "${_TCS_GIT_STATE_LOADED:-}" ]; then
  # shellcheck disable=SC2317  # `exit` is reachable when this file is *executed*
  return 0 2>/dev/null || exit 0
fi
_TCS_GIT_STATE_LOADED=1

# Global state vars populated by _get_branch_state. Declared here so callers can
# reference them safely under `set -u` after a successful _get_branch_state call.
# shellcheck disable=SC2034
BRANCH_NAME=""
# shellcheck disable=SC2034
BRANCH_STATE=""
# shellcheck disable=SC2034
BRANCH_AHEAD=0
# shellcheck disable=SC2034
BRANCH_BEHIND=0
# shellcheck disable=SC2034
PR_STATE="UNKNOWN"
# shellcheck disable=SC2034
PR_NUMBER=0
# shellcheck disable=SC2034
DETACHED_HEAD=0
# shellcheck disable=SC2034
REBASE_IN_PROGRESS=0
# shellcheck disable=SC2034
MERGE_IN_PROGRESS=0
# shellcheck disable=SC2034
CHERRY_PICK_IN_PROGRESS=0
# shellcheck disable=SC2034
BISECT_IN_PROGRESS=0

# git_safe: wrap `git` and filter harmless `.git/config` write/lock warnings emitted
# under Claude's sandbox (CON-7). Exit code is git's; stdout is git's; stderr passes
# through except for the matching warning lines.
#
# Implementation note: a process-substitution form (`2> >(grep ...)`) is simpler
# but interacts poorly with bats's `run` helper — the proc-sub can race the test
# harness's exit-code capture. The temp-file form below is deterministic and
# bash 3.2-compatible. Cost: one mktemp per git call; negligible for hooks.
git_safe() {
  local err_file rc=0
  err_file=$(mktemp 2>/dev/null) || err_file="${TMPDIR:-/tmp}/git_safe.$$.$RANDOM"
  git -C "$PWD" "$@" 2>"$err_file" || rc=$?
  if [ -s "$err_file" ]; then
    grep -E -v \
      'could not (write|lock) config file .*\.git/config|warning: could not lock config file .*\.git/config' \
      "$err_file" >&2 || true
  fi
  rm -f "$err_file"
  return "$rc"
}

# _detect_default_branch: resolve the default branch name via origin/HEAD chain.
# Falls back to local refs (main → master) so detection works in repos without
# an `origin` remote configured (e.g. fresh clones, fixture repos).
_detect_default_branch() {
  local default
  default=$(git -C "$PWD" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)
  if [ -n "$default" ]; then
    # `symbolic-ref --short` strips the `refs/remotes/` prefix but keeps the
    # remote name; drop the leading `origin/` to return just the branch.
    printf '%s\n' "${default#origin/}"
    return 0
  fi
  if git -C "$PWD" show-ref --verify --quiet refs/remotes/origin/main 2>/dev/null; then
    printf 'main\n'
    return 0
  fi
  if git -C "$PWD" show-ref --verify --quiet refs/remotes/origin/master 2>/dev/null; then
    printf 'master\n'
    return 0
  fi
  if git -C "$PWD" show-ref --verify --quiet refs/heads/main 2>/dev/null; then
    printf 'main\n'
    return 0
  fi
  if git -C "$PWD" show-ref --verify --quiet refs/heads/master 2>/dev/null; then
    printf 'master\n'
    return 0
  fi
  # Last resort: assume "main" (modern default).
  printf 'main\n'
  return 0
}

# _is_branch_squash_merged <branch> [<default>] — ADR-9 primary squash detector.
# Per SDD §Implementation Examples: a branch is squash-merged iff `git cherry`
# emits only `-` lines (every patch is already applied to the upstream).
# Returns:
#   0 — all `-`        → squash- or rebase-merged
#   1 — empty/mixed/+  → unmerged or partially merged
#   2 — git failed
_is_branch_squash_merged() {
  local branch="$1"
  local default="${2:-}"
  if [ -z "$default" ]; then
    default=$(_detect_default_branch)
  fi

  local lines
  lines=$(git -C "$PWD" cherry "origin/$default" "$branch" 2>/dev/null) || return 2

  if [ -z "$lines" ]; then
    return 1
  fi

  local plus_count minus_count
  plus_count=$(printf '%s\n' "$lines" | grep -c '^+ ')
  minus_count=$(printf '%s\n' "$lines" | grep -c '^- ')

  if [ "$plus_count" = "0" ] && [ "$minus_count" -gt 0 ]; then
    return 0
  fi
  return 1
}

# _is_branch_dangerously_merged <branch> [<default>] — squash-merge trap detector.
# Returns:
#   0 — branch tip is orphan from default AND patches are applied → DANGEROUS
#   1 — branch tip IS ancestor of default → SAFE (merge-commit, or branch fully
#                                                  linearised; checkout safe)
#   2 — git failed
_is_branch_dangerously_merged() {
  local branch="$1"
  local default="${2:-}"
  if [ -z "$default" ]; then
    default=$(_detect_default_branch)
  fi

  local branch_tip
  branch_tip=$(git -C "$PWD" rev-parse "$branch" 2>/dev/null) || return 2

  if git -C "$PWD" merge-base --is-ancestor "$branch_tip" "origin/$default" 2>/dev/null; then
    return 1
  fi

  _is_branch_squash_merged "$branch" "$default"
}

# _get_pr_state <branch> — fail-open PR state lookup via `gh` (CON-4).
# Emits two stdout lines: STATE then NUMBER. Never blocks the hook on failure;
# missing gh / jq, network errors, auth errors all yield UNKNOWN/0.
_get_pr_state() {
  local branch="$1"
  if ! command -v gh >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    printf 'UNKNOWN\n0\n'
    return 0
  fi

  local out rc
  if command -v timeout >/dev/null 2>&1; then
    out=$(timeout 5 gh pr list --head "$branch" --state all \
            --json state,number --limit 1 2>/dev/null)
    rc=$?
  else
    out=$(gh pr list --head "$branch" --state all \
            --json state,number --limit 1 2>/dev/null)
    rc=$?
  fi

  if [ "$rc" -ne 0 ]; then
    printf 'UNKNOWN\n0\n'
    return 0
  fi

  if [ -z "$out" ] || [ "$out" = "[]" ]; then
    printf 'NO_PR\n0\n'
    return 0
  fi

  local state number
  state=$(printf '%s' "$out" | jq -r '.[0].state // "UNKNOWN"' 2>/dev/null)
  number=$(printf '%s' "$out" | jq -r '.[0].number // 0' 2>/dev/null)
  printf '%s\n%s\n' "${state:-UNKNOWN}" "${number:-0}"
  return 0
}

# _get_branch_state — populate the BranchState globals (see header).
# Returns 0 on success; 1 if not in a git repo.
_get_branch_state() {
  local git_dir
  git_dir=$(git -C "$PWD" rev-parse --git-dir 2>/dev/null) || return 1
  if [ -z "$git_dir" ]; then
    return 1
  fi
  # Resolve to absolute path so the *_IN_PROGRESS file checks work whether or
  # not the caller has cd'd elsewhere.
  case "$git_dir" in
    /*) ;;
    *)  git_dir="$PWD/$git_dir" ;;
  esac

  # Branch name + detached HEAD detection. `symbolic-ref` exits non-zero on
  # detached HEAD; `|| true` keeps callers under `set -e` from aborting.
  local symbolic
  symbolic=$(git -C "$PWD" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
  if [ -z "$symbolic" ]; then
    BRANCH_NAME="<detached>"
    DETACHED_HEAD=1
  else
    BRANCH_NAME="$symbolic"
    DETACHED_HEAD=0
  fi

  # In-progress operation flags via .git/* state files.
  REBASE_IN_PROGRESS=0
  if [ -d "$git_dir/rebase-merge" ] || [ -d "$git_dir/rebase-apply" ]; then
    REBASE_IN_PROGRESS=1
  fi
  MERGE_IN_PROGRESS=0
  if [ -f "$git_dir/MERGE_HEAD" ]; then
    MERGE_IN_PROGRESS=1
  fi
  CHERRY_PICK_IN_PROGRESS=0
  if [ -f "$git_dir/CHERRY_PICK_HEAD" ]; then
    CHERRY_PICK_IN_PROGRESS=1
  fi
  BISECT_IN_PROGRESS=0
  if [ -f "$git_dir/BISECT_LOG" ]; then
    BISECT_IN_PROGRESS=1
  fi

  # Ahead/behind vs upstream. Empty if no upstream is configured (or detached
  # HEAD) → leave at 0/0. `|| true` is required: under `set -e` the failing
  # rev-list would abort _get_branch_state when called from a strict caller.
  BRANCH_AHEAD=0
  BRANCH_BEHIND=0
  local counts
  counts=$(git -C "$PWD" rev-list --left-right --count '@{u}...HEAD' 2>/dev/null || true)
  if [ -n "$counts" ]; then
    # shellcheck disable=SC2034  # consumed by hook callers via sourced env
    BRANCH_BEHIND=$(printf '%s' "$counts" | awk '{print $1+0}')
    # shellcheck disable=SC2034
    BRANCH_AHEAD=$(printf '%s' "$counts" | awk '{print $2+0}')
  fi

  # Working-tree state heuristic. Hooks override this with finer-grained labels
  # (e.g., "merged-squash") after consulting _is_branch_dangerously_merged.
  local porcelain
  porcelain=$(git -C "$PWD" status --porcelain 2>/dev/null || true)
  # shellcheck disable=SC2034  # BRANCH_STATE consumed by hook callers
  if [ "$REBASE_IN_PROGRESS" = "1" ] \
     || [ "$MERGE_IN_PROGRESS" = "1" ] \
     || [ "$CHERRY_PICK_IN_PROGRESS" = "1" ] \
     || [ "$BISECT_IN_PROGRESS" = "1" ]; then
    BRANCH_STATE="unfinished"
  elif [ -n "$porcelain" ]; then
    BRANCH_STATE="dirty"
  else
    BRANCH_STATE="clean"
  fi

  # PR state — fail-open. Skip when detached: there's no branch ref to query.
  PR_STATE="UNKNOWN"
  PR_NUMBER=0
  if [ "$DETACHED_HEAD" = "0" ] && [ -n "$BRANCH_NAME" ]; then
    local pr_out
    pr_out=$(_get_pr_state "$BRANCH_NAME" 2>/dev/null)
    if [ -n "$pr_out" ]; then
      PR_STATE=$(printf '%s\n' "$pr_out" | sed -n '1p')
      PR_NUMBER=$(printf '%s\n' "$pr_out" | sed -n '2p')
      [ -z "$PR_STATE" ] && PR_STATE="UNKNOWN"
      [ -z "$PR_NUMBER" ] && PR_NUMBER=0
    fi
  fi

  return 0
}

# _bypass_state_check — return 0 (skip checks) if any in-progress operation or
# detached HEAD is active. Caller must have run _get_branch_state first.
_bypass_state_check() {
  if [ "${DETACHED_HEAD:-0}" = "1" ] \
     || [ "${REBASE_IN_PROGRESS:-0}" = "1" ] \
     || [ "${MERGE_IN_PROGRESS:-0}" = "1" ] \
     || [ "${CHERRY_PICK_IN_PROGRESS:-0}" = "1" ] \
     || [ "${BISECT_IN_PROGRESS:-0}" = "1" ]; then
    return 0
  fi
  return 1
}
