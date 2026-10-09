#!/bin/bash
#
# scripts/ci/bump-and-push.sh
#
# Compute the version bumps main still owes, commit them, and push to main —
# retrying against a main that moved underneath us (issue #93).
#
# Two PRs merging seconds apart used to produce two concurrent auto-bump runs,
# each checked out at its own commit. Whichever pushed second lost a
# non-fast-forward, the job failed, and its bump was gone.
#
# Each attempt resets onto the current remote tip and recomputes the bump there.
# Recomputing rather than rebasing a prepared commit is what makes the retry
# correct — the version arithmetic has to read the manifests as they are now.
# Rebasing a "4.3.0 -> 4.3.1" edit onto a main that already says 4.3.1 either
# conflicts or lands a version that was already shipped.
#
# What is owed is derived from main's history, not from the push that started
# the run (issue #196), so it is recomputed on every attempt as well: a commit
# that landed between the fetch and a rejected push is included on the retry,
# and a run whose bump another run already made finds nothing left to do. A
# run that is lost entirely is caught up by the next one.
#
# Usage:
#   bump-and-push.sh [<remote>] [<branch>]
#
# Environment:
#   MAX_ATTEMPTS   push attempts before giving up (default 5)
#   DRY_RUN        set to 1 to skip the push (for local inspection)
#
# Exit codes:
#   0  — pushed, or nothing needed bumping
#   1  — bump script failed, or the push never succeeded
#
# Bash 3.2 compatible. shellcheck clean.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REMOTE="${1:-origin}"
BRANCH="${2:-main}"

MAX_ATTEMPTS="${MAX_ATTEMPTS:-5}"
DRY_RUN="${DRY_RUN:-0}"

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  git fetch --quiet "$REMOTE" "$BRANCH" || {
    printf 'bump-and-push: fetch from %s failed\n' "$REMOTE" >&2
    exit 1
  }

  git reset --quiet --hard "${REMOTE}/${BRANCH}" || {
    printf 'bump-and-push: could not reset onto %s/%s\n' "$REMOTE" "$BRANCH" >&2
    exit 1
  }

  if ! bash "${SCRIPT_DIR}/auto-bump-versions.sh"; then
    printf 'bump-and-push: auto-bump-versions.sh failed\n' >&2
    exit 1
  fi

  git add .claude-plugin/marketplace.json \
          'plugins/*/.claude-plugin/plugin.json' 2>/dev/null || true

  if git diff --cached --quiet; then
    printf 'No version bumps needed.\n'
    exit 0
  fi

  git commit --quiet -m "chore(release): auto-bump plugin versions [skip ci]" || {
    printf 'bump-and-push: commit failed\n' >&2
    exit 1
  }

  if [ "$DRY_RUN" = "1" ]; then
    printf 'DRY_RUN=1 — bump committed locally, not pushed.\n'
    exit 0
  fi

  if git push --quiet "$REMOTE" "HEAD:${BRANCH}"; then
    printf 'Pushed on attempt %s.\n' "$attempt"
    exit 0
  fi

  printf '%s/%s moved underneath us; recomputing (attempt %s of %s).\n' \
    "$REMOTE" "$BRANCH" "$attempt" "$MAX_ATTEMPTS" >&2
  attempt=$((attempt + 1))
  [ "$attempt" -le "$MAX_ATTEMPTS" ] && sleep "$attempt"
done

printf 'bump-and-push: could not push after %s attempts\n' "$MAX_ATTEMPTS" >&2
exit 1
