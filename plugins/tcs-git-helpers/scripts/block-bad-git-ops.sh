#!/usr/bin/env bash
# scripts/block-bad-git-ops.sh — PreToolUse:Bash dispatcher
#
# Reads the PreToolUse:Bash hook envelope from stdin, regex-matches the
# tool_input.command against the 19 destructive / state-sensitive patterns
# from PRD §M7 + M1 (push-to-closed-PR) + M2 (branch-from-unfinished) +
# M3 (resume-squash-merged), and emits a single cascading-denial
# permissionDecision JSON to stdout when one or more rules fire.
#
# Spec refs:
#   - SDD §Implementation Examples — block-bad-git-ops dispatcher skeleton
#                                    (this file is a faithful adaptation,
#                                    with two intentional deviations
#                                    documented in the team-lead report)
#   - SDD §Runtime View Primary Flow — push-to-closed-PR sequence
#   - SDD §Quality Requirements — denial ≤15 lines (EC1); non-push p99 ≤80ms;
#                                 push p99 ≤5000ms with timeout
#   - PRD M1 / M2 / M3 / M7 / M12 acceptance criteria
#   - PRD EC2 — cascading denial (ALL matched rules in one response)
#
# Constraints (CON-1, CON-3, CON-4, CON-9):
#   - bash 3.2 macOS-compat (no `declare -A`, no `mapfile`, no `${var,,}`)
#   - POSIX ERE only: `[[:space:]]+` not `\s+`; `[[:>:]]` not `\b`
#   - No coreutils-timeout dep — gh fail-open relies on `_get_pr_state`'s
#     internal timeout (Phase 1 lib; degrades gracefully if `timeout(1)`
#     missing — see report finding)
#   - gh fail-open: any non-OPEN/CLOSED/MERGED/NO_PR state allows the push
#                   with stderr warning (CON-4)
#
# Field-of-fire deviations from SDD skeleton:
#   1. Drop `set -e` (kept `set -uo pipefail`): the dispatcher runs many
#      pattern matchers that intentionally return 1 on no-match. Under
#      `set -e`, the trailing test in `cmd1 && cmd2` would abort. We rely
#      on every helper returning 0 and the script reaching the aggregate
#      check at the bottom.
#   2. Lazy state init: SDD calls `_get_branch_state` upfront (which calls
#      `gh` via `_get_pr_state`). That breaks the ≤80ms p99 budget for
#      non-push patterns (CON-2 / Quality Requirements). We do a
#      lightweight inline `.git/*` bypass check at the top, and defer
#      `_get_branch_state` until an M1/M2 path actually fires.

set -uo pipefail

# ---------------------------------------------------------------------------
# Read hook envelope (stdin JSON) — fail-open on malformed input
# ---------------------------------------------------------------------------
#
# `|| true` on each jq pipeline keeps a malformed-stdin parse error from
# tripping the assignment's command-substitution exit status. Defense-in-
# depth on top of `set -uo pipefail` (we deliberately drop -e), and mirrors
# the T2.3 / T2.2 review-fix pattern (`fix(tcs-git-helpers): T2.3 jq
# fail-open on malformed stdin`). A non-zero hook exit would unconditionally
# block every Bash tool call — that's a fail-CLOSED bug, the opposite of
# what we want for a defensive matcher.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || true)
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)
[ -z "$CMD" ] && exit 0

# ---------------------------------------------------------------------------
# Source libs (Phase 1 deliverables)
# ---------------------------------------------------------------------------

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" && pwd)" || exit 0
# shellcheck source=./lib/git_state.sh disable=SC1091
. "$_LIB_DIR/git_state.sh"
# shellcheck source=./lib/pattern_match.sh disable=SC1091
. "$_LIB_DIR/pattern_match.sh"
# shellcheck source=./lib/cache.sh disable=SC1091
. "$_LIB_DIR/cache.sh"
# shellcheck source=./lib/audit_log.sh disable=SC1091
. "$_LIB_DIR/audit_log.sh"
# shellcheck source=./lib/override.sh disable=SC1091
. "$_LIB_DIR/override.sh"

# Hook identity. NOTE: not currently emitted into the audit JSONL because
# override.sh's internal `_audit_log` call only sets env_var/master and
# does not accept a hook= override (Phase 1 lib design). Surfaced as a
# finding to team-lead; if/when the lib gains a richer signature, this
# constant becomes a `_audit_log hook=$_HOOK_NAME …` argument here.
# shellcheck disable=SC2034  # reserved for richer audit (see comment)
_HOOK_NAME="block-bad-git-ops"

# ---------------------------------------------------------------------------
# Lightweight bypass check (no gh — performance-critical path)
# ---------------------------------------------------------------------------
#
# CON-7 / SDD §Hook Decision Matrix: skip ALL hook checks while a multi-step
# git operation is mid-flight. Direct `.git/*` file probes only — far cheaper
# than `_get_branch_state` (which also queries gh).

_check_bypass_state() {
  local git_dir bypass_msg=""
  git_dir=$(git -C "$PWD" rev-parse --git-dir 2>/dev/null) || return 1
  case "$git_dir" in
    /*) ;;
    *)  git_dir="$PWD/$git_dir" ;;
  esac

  if [ -d "$git_dir/rebase-merge" ] || [ -d "$git_dir/rebase-apply" ]; then
    bypass_msg="rebase-in-progress"
  elif [ -f "$git_dir/MERGE_HEAD" ]; then
    bypass_msg="merge-in-progress"
  elif [ -f "$git_dir/CHERRY_PICK_HEAD" ]; then
    bypass_msg="cherry-pick-in-progress"
  elif [ -f "$git_dir/BISECT_LOG" ]; then
    bypass_msg="bisect-in-progress"
  elif ! git -C "$PWD" symbolic-ref --quiet --short HEAD >/dev/null 2>&1; then
    bypass_msg="detached-HEAD"
  fi

  if [ -n "$bypass_msg" ]; then
    printf 'tcs-git-helpers: bypass: %s\n' "$bypass_msg" >&2
    return 0
  fi
  return 1
}

if _check_bypass_state; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Cascading-denial accumulator + helpers
# ---------------------------------------------------------------------------

DENY_REASONS=()
_STATE_INITIALIZED=0

# Lazily populate BRANCH_NAME / BRANCH_STATE / BRANCH_AHEAD / PR_STATE etc.
# Only the M1 push and M2 branch-create paths need this; M7 destructive
# patterns and M3 resume-merged use cheaper helpers.
_ensure_branch_state() {
  if [ "${_STATE_INITIALIZED:-0}" = "1" ]; then
    return 0
  fi
  _get_branch_state 2>/dev/null || true
  _STATE_INITIALIZED=1
  return 0
}

# Append a denial reason to the cascading-denial accumulator. Always 0.
_record_deny() {
  local rule="$1" msg="$2"
  DENY_REASONS+=("[${rule}] ${msg} (override: CLAUDE_ALLOW_${rule}=1)")
  return 0
}

# Pattern-match dispatcher entry: if no override is set, accumulate the
# denial; if an override is set, override.sh consumes it (audit + sentinel)
# and we silently allow. ALWAYS returns 0 so set -e wouldn't abort even if
# the pattern dispatch chain were rewritten to use it.
_maybe_deny() {
  local rule="$1" msg="$2"
  if _check_and_consume_override "$rule"; then
    return 0
  fi
  _record_deny "$rule" "$msg"
  return 0
}

# Variant for git config core.hooksPath: allowed silently when the
# /tcs-git-helpers:git-setup skill has set the sentinel env-var; otherwise
# fall through to standard override / deny semantics.
_maybe_check_setup_sentinel() {
  local rule="$1" msg="$2"
  if [ "${TCS_GIT_HELPERS_SETUP_ACTIVE:-0}" = "1" ]; then
    return 0
  fi
  if _check_and_consume_override "$rule"; then
    return 0
  fi
  _record_deny "$rule" "$msg"
  return 0
}

# Emit the final cascading-denial JSON to stdout. Uses jq when available
# for safe escaping; falls back to manual escape otherwise.
_emit_permission_decision_deny() {
  local n=${#DENY_REASONS[@]} i body
  body="tcs-git-helpers DENIED: ${n} rule(s) matched"
  for ((i = 0; i < n; i++)); do
    body="${body}"$'\n'"  - ${DENY_REASONS[$i]}"
  done
  local plugin_root="${CLAUDE_PLUGIN_ROOT:-tcs-git-helpers}"
  body="${body}"$'\n'"References: ${plugin_root}/references/destructive-ops.md, ${plugin_root}/references/force-push-safety.md, ${plugin_root}/references/sandbox-and-git-config.md"
  body="${body}"$'\n'"Master override: CLAUDE_ALLOW_GIT_BAD_OPS=1 (loud warn; granular preferred)"

  # Cap at 15 lines per SDD §Quality Requirements / EC1.
  body=$(printf '%s\n' "$body" | head -n 15)

  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$body" | jq -Rsc '
      {hookSpecificOutput:
        {hookEventName:"PreToolUse",
         permissionDecision:"deny",
         permissionDecisionReason:.}}'
    return 0
  fi

  # Fallback: hand-escape JSON string. Order matters: backslashes first.
  local esc="${body//\\/\\\\}"
  esc="${esc//\"/\\\"}"
  esc="${esc//$'\n'/\\n}"
  esc="${esc//$'\r'/\\r}"
  esc="${esc//$'\t'/\\t}"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$esc"
  return 0
}

# ---------------------------------------------------------------------------
# M1 helper: _is_ahead_of_merged — 4-path ancestor check (ADR-1 / ADR-8)
# ---------------------------------------------------------------------------
#
# Determines whether the current HEAD has diverged past a known merged SHA
# (e.g., the merge_commit recorded in the PR-state cache from T1.1).
#
# Arguments: <branch> <merged_sha>
#   <branch>     — informational; not used by git calls (HEAD is the test subject)
#   <merged_sha> — SHA of the commit at which the PR was merged into the base branch
#
# Return values (per SDD §Interface Specifications):
#   0 — HEAD is strictly ahead of merged_sha (allow push; emits ADR-8 stderr note)
#   1 — deny: HEAD == merged_sha (ghost-branch), merged_sha not ancestor, or
#             merged_sha absent from local object store (conservative fallback)
#   2 — SHA argument was empty; caller treats this as deny
#
# Constraints:
#   - bash 3.2 / CON-1: no associative arrays, no ${var,,}, no mapfile
#   - Only uses: git rev-parse HEAD, git merge-base --is-ancestor, string compare
#   - ADR-1: git merge-base --is-ancestor is the canonical ancestor test
#   - ADR-8: stderr note wording is locked; do NOT paraphrase
#   - Stdout: NEVER written — would corrupt the permissionDecision JSON caller emits
_is_ahead_of_merged() {
  local merged_sha="$2"

  if [ -z "$merged_sha" ]; then
    return 2
  fi

  local head_sha
  head_sha=$(git -C "$PWD" rev-parse HEAD 2>/dev/null) || return 1

  if [ "$head_sha" = "$merged_sha" ]; then
    return 1
  fi

  if git -C "$PWD" merge-base --is-ancestor "$merged_sha" HEAD 2>/dev/null; then
    printf 'tcs-git-helpers: PR was merged; HEAD is ahead by new commits. A new PR will be required for this push.\n' >&2
    return 0
  fi

  return 1
}

# ---------------------------------------------------------------------------
# M1: push-to-closed-PR — gh fail-open, 60s cache (CON-4)
# ---------------------------------------------------------------------------

_check_push_to_closed_pr() {
  local rule="PUSH_TO_CLOSED_PR"
  local branch state pr_out number

  _ensure_branch_state
  branch="${BRANCH_NAME:-}"
  if [ -z "$branch" ] || [ "$branch" = "<detached>" ]; then
    return 0
  fi

  # Try the 60s push-state cache before going to gh.
  # _read_pr_state_cache emits two stdout lines when merge_commit is cached:
  #   line 1 — state (MERGED/CLOSED/OPEN/etc.)
  #   line 2 — merge_commit SHA (only present when cached)
  # Extract line 1 for the case dispatch; line 2 for the ahead-check.
  local _raw merged_sha
  _raw=$(_read_pr_state_cache "$branch" 2>/dev/null) || _raw=""
  state=$(printf '%s\n' "$_raw" | sed -n '1p')
  merged_sha=$(printf '%s\n' "$_raw" | sed -n '2p')

  if [ -z "$state" ]; then
    # _get_branch_state already populated PR_STATE via _get_pr_state.
    # Reuse that to avoid a second gh call.
    if [ -n "${PR_STATE:-}" ] && [ "${PR_STATE}" != "UNKNOWN" ]; then
      state="$PR_STATE"
      number="${PR_NUMBER:-0}"
    else
      if ! command -v gh >/dev/null 2>&1; then
        printf 'tcs-git-helpers: gh missing — push allowed (fail-open)\n' >&2
        return 0
      fi
      pr_out=$(_get_pr_state "$branch" 2>/dev/null)
      state=$(printf '%s\n' "$pr_out" | sed -n '1p')
      number=$(printf '%s\n' "$pr_out" | sed -n '2p')
      [ -z "$state" ] && state="UNKNOWN"
      [ -z "$number" ] && number=0
    fi
    _write_pr_state_cache "$branch" "$state" "$number" 2>/dev/null || true
  fi

  case "$state" in
    CLOSED|MERGED)
      # M1: attempt ahead-check before override or deny (ADR-8).
      # Resolve merge_commit SHA if not already cached.
      if [ -z "$merged_sha" ] && [ "$state" = "MERGED" ]; then
        if command -v gh >/dev/null 2>&1; then
          merged_sha=$(gh pr view "$branch" \
            --json mergeCommit \
            --jq '.mergeCommit.oid // empty' 2>/dev/null) || merged_sha=""
          if [ -n "$merged_sha" ]; then
            # Preserve any existing pr_number on this entry — _write_pr_state_cache
            # replaces .branch_state[$branch] wholesale, so passing "0" here would
            # silently drop the `number` field a prior write captured (the typical
            # cache-hit reentry into this branch hits exactly that condition).
            local _existing_number=0
            local _pr_state_file
            _pr_state_file="$(_pr_state_path 2>/dev/null)" || _pr_state_file=""
            if [ -n "$_pr_state_file" ] && [ -r "$_pr_state_file" ] \
                && command -v jq >/dev/null 2>&1; then
              _existing_number=$(jq -r --arg b "$branch" \
                '.branch_state[$b].number // 0' \
                "$_pr_state_file" 2>/dev/null) || _existing_number=0
            fi
            _write_pr_state_cache "$branch" "$state" "$_existing_number" "$merged_sha" \
              2>/dev/null || true
          fi
        fi
      fi

      # Ahead-check: return 0 (allow) when HEAD has new commits past the merge.
      # _is_ahead_of_merged emits the ADR-8 stderr note on return 0.
      # Return 2 (empty SHA) or 1 (not-ahead) → fall through to override/deny.
      if _is_ahead_of_merged "$branch" "$merged_sha"; then
        return 0
      fi

      # Not ahead, or SHA unavailable — fall through to override then deny.
      if _check_and_consume_override "$rule"; then
        return 0
      fi
      _record_deny "$rule" \
        "PR for branch '${branch}' is ${state}. See ${CLAUDE_PLUGIN_ROOT:-tcs-git-helpers}/references/squash-merge-trap.md"
      ;;
    UNKNOWN)
      printf 'tcs-git-helpers: gh state UNKNOWN — push allowed (fail-open)\n' >&2
      ;;
    OPEN|DRAFT|NO_PR|*)
      :
      ;;
  esac
  return 0
}

# ---------------------------------------------------------------------------
# M2: branch-from-unfinished-work guard
# ---------------------------------------------------------------------------

_check_branch_creation_from_unfinished() {
  local rule="BRANCH_FROM_UNFINISHED"
  local default conditions="" ahead

  _ensure_branch_state
  default=$(_detect_default_branch 2>/dev/null) || default="main"

  # M2 Rule 6: branching off the default branch (clean tree) is the desired
  # pattern. Allow silently.
  if [ "${BRANCH_NAME:-}" = "$default" ] && [ "${BRANCH_STATE:-}" != "dirty" ]; then
    return 0
  fi

  # Compute ahead count vs origin/<default> directly. The lib's BRANCH_AHEAD
  # is computed against `@{u}` (upstream), which is unset for never-pushed
  # branches — and M2 spec is "ahead of origin/<default>", not "ahead of
  # upstream". Fall through to 0 if origin/<default> is missing locally.
  ahead=$(git -C "$PWD" rev-list --count "origin/${default}..HEAD" 2>/dev/null) || ahead=0
  case "$ahead" in
    ''|*[!0-9]*) ahead=0 ;;
  esac

  if [ "${BRANCH_STATE:-}" = "dirty" ]; then
    conditions="${conditions}working tree dirty; "
  fi
  if [ "$ahead" -gt 0 ] && [ "${PR_STATE:-}" = "NO_PR" ]; then
    conditions="${conditions}branch '${BRANCH_NAME:-?}' is ${ahead} commit(s) ahead of origin/${default} with no PR; "
  fi

  if [ -z "$conditions" ]; then
    return 0
  fi

  if _check_and_consume_override "$rule"; then
    return 0
  fi
  _record_deny "$rule" "Refuse to create new branch: ${conditions}"
  return 0
}

# ---------------------------------------------------------------------------
# M3: resume squash-merged branch (cherry primary + ancestor cross-check)
# ---------------------------------------------------------------------------

_check_resume_squash_merged() {
  local rule="RESUME_MERGED_BRANCH"
  local target="" default

  # Re-extract the target branch via the same pattern. Substring match
  # against full $CMD allows compound forms (`cd foo && git checkout x`).
  if [[ "$CMD" =~ git[[:space:]]+(checkout|switch)[[:space:]]+([^-.[:space:]][^[:space:]]*)$ ]]; then
    target="${BASH_REMATCH[2]}"
  fi
  [ -z "$target" ] && return 0

  default=$(_detect_default_branch 2>/dev/null) || default="main"
  if [ "$target" = "$default" ]; then
    return 0
  fi

  # Branch must exist locally for `git cherry`/`merge-base` to evaluate;
  # if not (typo, remote-only ref), let git itself report the error.
  if ! git -C "$PWD" rev-parse --verify --quiet "$target" >/dev/null 2>&1; then
    return 0
  fi

  # _is_branch_dangerously_merged: 0 → DANGEROUS (squash-merged orphan);
  # 1 → safe (merge-commit ancestor or unmerged); 2 → git error → bail.
  if _is_branch_dangerously_merged "$target" "$default" 2>/dev/null; then
    if _check_and_consume_override "$rule"; then
      return 0
    fi
    _record_deny "$rule" \
      "Branch '${target}' was squash-merged. See ${CLAUDE_PLUGIN_ROOT:-tcs-git-helpers}/references/squash-merge-trap.md"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Pattern dispatch table
# ---------------------------------------------------------------------------
# Each line is `_match_command "$CMD" "$PATTERN" && _<handler> ARGS`.
# Returning 0 from the handler is required so set -uo doesn't blow up on
# the next line (and so cascading-denial accumulation continues).

# === M7 destructive ops ===
_match_command "$CMD" "$PATTERN_RESET_HARD"          && _maybe_deny RESET_HARD            "git reset --hard destroys working tree + index"
_match_command "$CMD" "$PATTERN_CLEAN_FORCE"         && _maybe_deny CLEAN_FORCE           "git clean -f deletes untracked files (use -n to dry-run first)"
_match_command "$CMD" "$PATTERN_CHECKOUT_DOT"        && _maybe_deny DESTRUCTIVE_CHECKOUT  "git checkout . discards working-tree changes silently"
_match_command "$CMD" "$PATTERN_CHECKOUT_PATH"       && _maybe_deny DESTRUCTIVE_CHECKOUT  "git checkout -- <path> discards path changes"
_match_command "$CMD" "$PATTERN_RESTORE_DESTRUCTIVE" && _maybe_deny DESTRUCTIVE_RESTORE   "git restore --worktree --source / --staged destroys changes"
_match_command "$CMD" "$PATTERN_BRANCH_FORCE_DELETE" && _maybe_deny FORCE_BRANCH_DELETE   "git branch -D force-deletes; use -d (safe) or recover via reflog"
_match_command "$CMD" "$PATTERN_STASH_DESTROY"       && _maybe_deny STASH_DESTROY         "git stash drop/clear destroys stash; use pop"
_match_command "$CMD" "$PATTERN_REFLOG_EXPIRE"       && _maybe_deny REFLOG_EXPIRE         "git reflog expire kills the recovery net"
# NO_VERIFY uses _strip_quoted to prevent `.*` in PATTERN_NO_VERIFY from
# matching `-n` / `--no-verify` text INSIDE a `git commit -m "..."` message
# body (v2.2.1 false-positive fix). Scope is intentionally narrow: only this
# pattern bridges from argv into a typically-quoted body. See pattern_match.sh.
_match_command "$(_strip_quoted "$CMD")" "$PATTERN_NO_VERIFY" \
                                                     && _maybe_deny NO_VERIFY             "--no-verify bypasses .githooks/ — defeats the purpose"

# === Push variants (M1 closed-PR + M7 destructive push forms) ===
_match_command "$CMD" "$PATTERN_PUSH"                && _check_push_to_closed_pr
_match_command "$CMD" "$PATTERN_PUSH_FORCE"          && _maybe_deny FORCE_PUSH            "use --force-with-lease, not --force"
_match_command "$CMD" "$PATTERN_PUSH_DELETE_FLAG"    && _maybe_deny REMOTE_BRANCH_DELETE  "git push --delete removes remote branch"
_match_command "$CMD" "$PATTERN_PUSH_COLON_DELETE"   && _maybe_deny REMOTE_BRANCH_DELETE  "git push <remote> :<branch> deletes remote branch"
_match_command "$CMD" "$PATTERN_GH_REF_DELETE_A"     && _maybe_deny REMOTE_BRANCH_DELETE  "gh api DELETE on git/refs removes remote ref"
_match_command "$CMD" "$PATTERN_GH_REF_DELETE_B"     && _maybe_deny REMOTE_BRANCH_DELETE  "gh api DELETE on git/refs removes remote ref"

# === Branch creation / resume (M2, M3) ===
_match_command "$CMD" "$PATTERN_BRANCH_CREATE"       && _check_branch_creation_from_unfinished
_match_command "$CMD" "$PATTERN_BRANCH_RESUME"       && _check_resume_squash_merged

# === core.hooksPath subversion ===
_match_command "$CMD" "$PATTERN_HOOKSPATH_INLINE"    && _maybe_deny HOOKSPATH_OVERRIDE    "git -c core.hooksPath=… disables .githooks/"
# Read-only --get/--get-all/--get-regexp forms short-circuit before the write check.
# `git config --get core.hooksPath` and friends mutate nothing, so they should
# never trigger the sentinel-gated denial.
_match_command "$CMD" "$PATTERN_HOOKSPATH_CONFIG_READ" || \
  { _match_command "$CMD" "$PATTERN_HOOKSPATH_CONFIG" && _maybe_check_setup_sentinel HOOKSPATH_OVERRIDE  "git config core.hooksPath only allowed during /tcs-git-helpers:git-setup (set TCS_GIT_HELPERS_SETUP_ACTIVE=1)"; }

# ---------------------------------------------------------------------------
# Aggregate decision — emit cascading denial if anything matched
# ---------------------------------------------------------------------------

if [ "${#DENY_REASONS[@]}" -gt 0 ]; then
  _emit_permission_decision_deny
fi

exit 0
