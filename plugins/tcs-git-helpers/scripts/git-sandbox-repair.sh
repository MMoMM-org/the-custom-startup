#!/usr/bin/env bash
# tcs-git-helpers: v2.4.0
# scripts/git-sandbox-repair.sh — repair what a sandboxed git command left
# half done (#303).
#
# The Claude Code Bash sandbox denies writes to .git/config, so some git
# commands complete only partly and report no hard error: `git push -u`
# pushes but sets no upstream, a `git checkout -b` that sets tracking
# rewrites the tree but HEAD stays on the old branch. Run this OUTSIDE the
# sandbox, from the prompt:
#
#   ! bash ~/.claude/plugins/cache/the-custom-startup/tcs-git-helpers/*/scripts/git-sandbox-repair.sh
#
# What it does:
#   - current branch has no upstream and origin/<branch> exists
#       -> sets the upstream (a .git/config write, nothing else)
#   - the index matches another branch's tree, not HEAD's
#       -> reports it with the command that would fix it; never runs it
# It never resets, checks out, or moves a ref.
#
# Usage: git-sandbox-repair.sh [--dry-run]
#
# Output lines: OK, FIXED, WOULD-FIX, REPORT, INFO.
# Exit: 0 nothing left to do, 1 error, 2 a REPORT needs a human decision.
#
# Constraints: bash 3.2, shellcheck-clean.

set -euo pipefail

DRY_RUN=0
case "${1:-}" in
  "") ;;
  --dry-run) DRY_RUN=1 ;;
  *) printf 'usage: git-sandbox-repair.sh [--dry-run]\n' >&2; exit 1 ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 \
  || { printf 'ERROR: not inside a git repository\n' >&2; exit 1; }

STATUS=0

_report() { printf 'REPORT %s\n' "$1"; STATUS=2; }

BRANCH="$(git symbolic-ref --short -q HEAD 2>/dev/null || true)"
if [ -z "$BRANCH" ]; then
  printf 'INFO detached HEAD; upstream check skipped\n'
fi

# --- 1. HEAD left behind by an interrupted checkout -b / switch -c ----------
# The index was rewritten to the new branch's tree, HEAD was not. Compare the
# index tree against HEAD's and, if they differ, against every other branch
# tip. A match is a strong sign, but staged work can look the same, so this
# only reports.
HEAD_TREE="$(git rev-parse -q --verify 'HEAD^{tree}' 2>/dev/null || true)"
INDEX_TREE="$(git write-tree 2>/dev/null || true)"
if [ -n "$HEAD_TREE" ] && [ -n "$INDEX_TREE" ] && [ "$HEAD_TREE" != "$INDEX_TREE" ]; then
  MATCHES="$(git for-each-ref --format='%(refname:short) %(objectname)' refs/heads refs/remotes \
    | while read -r ref sha; do
        [ "$ref" = "$BRANCH" ] && continue
        # Not `case … in */HEAD)`: bash 3.2 ends the $( ) at that lone ")".
        [ "${ref%/HEAD}" != "$ref" ] && continue
        [ "$(git rev-parse -q --verify "$sha^{tree}" 2>/dev/null)" = "$INDEX_TREE" ] && printf '%s\n' "$ref"
      done || true)"
  # A pushed branch matches twice (local and origin/); name the local one.
  LOCAL=""
  for ref in $MATCHES; do
    git show-ref -q --verify "refs/heads/$ref" && LOCAL="$LOCAL $ref"
  done
  if [ -n "$LOCAL" ]; then
    for ref in $LOCAL; do
      _report "index matches branch '$ref' but HEAD is on '${BRANCH:-detached}'; if checkout -b $ref was interrupted: git symbolic-ref HEAD refs/heads/$ref"
    done
  else
    for ref in $MATCHES; do
      _report "index matches '$ref' but HEAD is on '${BRANCH:-detached}' and no local branch has that tree; check git status before switching"
    done
  fi
fi

# --- 2. upstream missing after push -u --------------------------------------
if [ -n "$BRANCH" ]; then
  if git rev-parse -q --verify '@{upstream}' >/dev/null 2>&1; then
    printf 'OK %s tracks %s\n' "$BRANCH" "$(git rev-parse --abbrev-ref '@{upstream}')"
  elif git show-ref -q --verify "refs/remotes/origin/$BRANCH"; then
    if [ "$DRY_RUN" = "1" ]; then
      printf 'WOULD-FIX set upstream of %s to origin/%s\n' "$BRANCH" "$BRANCH"
    elif git branch -q --set-upstream-to="origin/$BRANCH" "$BRANCH" 2>/dev/null; then
      printf 'FIXED upstream of %s set to origin/%s\n' "$BRANCH" "$BRANCH"
    else
      printf 'ERROR: could not set the upstream of %s; inside the Bash sandbox? run it with ! bash ...\n' "$BRANCH" >&2
      exit 1
    fi
  else
    printf 'INFO %s has no upstream and origin/%s does not exist (not pushed yet)\n' "$BRANCH" "$BRANCH"
  fi
fi

exit "$STATUS"
