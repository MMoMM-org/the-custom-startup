#!/usr/bin/env bash
# pre-edit-branch-check.sh — PreToolUse hook for Edit/Write/NotebookEdit.
#
# Augments (does NOT replace) ~/.claude/hooks/block-main-edits.sh. Both hooks
# fire side-by-side; this one re-implements the user-global semantics for
# defense-in-depth (M11 AC3) and ADDS a squash-merge orphan-branch warning
# that the user-global hook cannot detect.
#
# Behavior:
#   - Tool gate: only fires for Write|Edit|NotebookEdit
#   - CLAUDE_ALLOW_MAIN_EDITS=1 → exit 0 (parity with user-global escape hatch)
#   - Gitignored paths exempt (parity with user-global)
#   - State bypass (rebase/merge/cherry-pick/bisect/detached HEAD) → exit 0
#     with stderr "bypass: state-X" line (M11 AC3 / SDD Hook Decision Matrix)
#   - main/master → deny (identical JSON shape + reason to user-global)
#   - Squash-merge orphan branch → stderr WARNING (NOT a deny; non-main edits
#     are recoverable; the warning surfaces the trap so the operator can
#     checkpoint before continuing on a stale branch)
#
# Spec refs:
#   - SDD §Building Block View — pre-edit-branch-check
#   - PRD M11 AC3 — coexistence with user-global hook
#
# Performance contract: ≤80ms p99. Local-git only. We deliberately do NOT
# call lib/git_state._get_branch_state because it triggers `gh pr list` (5s
# timeout). State-bypass is inlined; orphan detection uses
# _is_branch_dangerously_merged which is local-git-only (`git cherry` +
# `git merge-base --is-ancestor`).
# shellcheck shell=bash

set -euo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" && pwd)"
# shellcheck source=/dev/null
. "$_LIB_DIR/git_state.sh"
# shellcheck source=/dev/null
. "$_LIB_DIR/audit_log.sh"

INPUT=$(cat)
# Two separate jq reads — NOT a combined `@tsv` filter. jq's @tsv encodes
# embedded tabs/CRs/newlines/backslashes in field values as the literal
# 2-char escapes `\t`/`\r`/`\n`/`\\`, which a downstream bash split has no
# clean way to reverse without reintroducing escape-handling bugs. Two
# reads cost one extra fork (~10ms) but preserve every byte of file_path
# verbatim — important because file_path appears verbatim in the deny
# reason and is used as a `git check-ignore` argument.
#
# `2>/dev/null || true` keeps the hook fail-open under `set -euo pipefail`
# if jq is missing or stdin is malformed: empty TOOL/FILE_PATH falls through
# the case blocks to exit 0. Hook contract guarantees exit 0 always;
# blocking the user's edit because the hook itself crashed is worse than
# letting it through (defense-in-depth: the user-global hook still fires).
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || true)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || true)

# Only check editing tools; everything else is a fast-allow.
case "$TOOL" in
    Write|Edit|NotebookEdit) ;;
    *) exit 0 ;;
esac

# Env-var escape hatch (parity with user-global hook).
if [ "${CLAUDE_ALLOW_MAIN_EDITS:-0}" = "1" ]; then
    exit 0
fi

[ -z "$FILE_PATH" ] && exit 0

# Find the git repo containing the target file (not necessarily $PWD).
DIR=$(dirname "$FILE_PATH")
REPO_DIR=$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null || true)
[ -z "$REPO_DIR" ] && exit 0

# Gitignored paths bypass the branch check — they cannot reach main via a
# normal commit anyway.
if git -C "$REPO_DIR" check-ignore -q "$FILE_PATH" 2>/dev/null; then
    exit 0
fi

# Resolve git-dir for *_IN_PROGRESS flag-file probing.
GIT_DIR=$(git -C "$REPO_DIR" rev-parse --git-dir 2>/dev/null || true)
[ -z "$GIT_DIR" ] && exit 0
case "$GIT_DIR" in
    /*) ;;
    *)  GIT_DIR="$REPO_DIR/$GIT_DIR" ;;
esac

# State bypass — multi-step git operations are atomic from Claude's POV; the
# hook MUST NOT block on a half-finished rebase/merge/cherry-pick/bisect or
# during detached-HEAD work. Inlined to avoid the gh-touching code path in
# git_state._get_branch_state (perf contract: ≤80ms p99, local-git only).
BRANCH=$(git -C "$REPO_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
if [ -z "$BRANCH" ]; then
    echo "tcs-git-helpers: pre-edit-branch-check bypass: state-detached" >&2
    exit 0
fi
if [ -d "$GIT_DIR/rebase-merge" ] || [ -d "$GIT_DIR/rebase-apply" ]; then
    echo "tcs-git-helpers: pre-edit-branch-check bypass: state-rebase" >&2
    exit 0
fi
if [ -f "$GIT_DIR/MERGE_HEAD" ]; then
    echo "tcs-git-helpers: pre-edit-branch-check bypass: state-merge" >&2
    exit 0
fi
if [ -f "$GIT_DIR/CHERRY_PICK_HEAD" ]; then
    echo "tcs-git-helpers: pre-edit-branch-check bypass: state-cherry-pick" >&2
    exit 0
fi
if [ -f "$GIT_DIR/BISECT_LOG" ]; then
    echo "tcs-git-helpers: pre-edit-branch-check bypass: state-bisect" >&2
    exit 0
fi

# main/master deny — match user-global hook's JSON shape and reason text
# verbatim. Defense-in-depth: if the user-global hook is missing or a future
# refactor changes its name, this hook still enforces the rule.
case "$BRANCH" in
    main|master)
        REL_PATH="${FILE_PATH#"$REPO_DIR"/}"
        REASON="Refusing to ${TOOL} '${REL_PATH}' on '${BRANCH}'. Create a feature branch first (git checkout -b feat/<name>). Gitignored paths are exempt. Override for the whole session by relaunching Claude with CLAUDE_ALLOW_MAIN_EDITS=1."
        # `|| true` keeps fail-open under `set -e` if jq fails to emit. The
        # deny is dropped silently — Claude Code sees an exit-0 with no JSON
        # and allows the edit. The user-global block-main-edits.sh runs
        # alongside this hook and will still deny (M11 AC3 defense-in-depth),
        # so a silent drop here is recoverable. Blocking the edit because
        # OUR jq crashed would be a worse failure mode.
        jq -nc --arg reason "$REASON" '{
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                permissionDecision: "deny",
                permissionDecisionReason: $reason
            }
        }' 2>/dev/null || true
        exit 0
        ;;
esac

# Squash-merge orphan augmentation — the value-add over the user-global hook.
#
# `_is_branch_dangerously_merged` runs `git cherry` and `git merge-base
# --is-ancestor` (both local-git, no network). Returns 0 if the branch tip
# is orphaned from the default branch's history AND its patches have already
# been applied — the canonical squash-merge trap. Returns 1 (safe) or 2 (git
# error) otherwise; we only warn on 0.
#
# WARNING (not DENY): editing on a stale post-squash branch is recoverable.
# A nudge surfaces the trap so the operator can `git checkout main && git
# pull && git checkout -b feat/<name>` instead of compounding the orphan.
#
# git_state lib uses `git -C "$PWD"` for queries; cd into the repo first.
cd "$REPO_DIR"
if _is_branch_dangerously_merged "$BRANCH"; then
    echo "tcs-git-helpers: pre-edit-branch-check WARNING: branch '${BRANCH}' appears squash-merged into the default branch — its patches are upstream but its tip is orphaned. Editing here continues a stale branch; consider 'git checkout main && git pull && git checkout -b feat/<name>'. See references/squash-merge-trap.md." >&2
fi

exit 0
