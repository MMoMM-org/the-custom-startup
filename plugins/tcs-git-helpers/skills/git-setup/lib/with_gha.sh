#!/usr/bin/env bash
# tcs-git-helpers: v1.0.0
# skills/git-setup/lib/with_gha.sh — Install the PR-title-check GitHub Actions
# workflow into the target repo's .github/workflows/.
#
# Spec refs:
#   - PRD §Feature S2 (--with-gha; idempotent re-install)
#   - SDD §GitHub Actions Templates
#   - templates/github-actions/pr-title-check.yml (T5.7)
#
# Constraints:
#   - bash 3.2
#   - shellcheck-clean
#   - Does NOT auto-commit (consistent with M10 AC5)
#   - Refuses to overwrite an existing workflow without explicit confirmation
#     (test mode auto-skips the prompt via TCS_GHA_FORCE=1)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

TEMPLATE_SRC="$PLUGIN_ROOT/templates/github-actions/pr-title-check.yml"

_repo_root() {
  if git rev-parse --show-toplevel 2>/dev/null; then
    return 0
  fi
  printf '[tcs-git-helpers:git-setup] ERROR: not inside a git repository\n' >&2
  return 1
}

ROOT="$(_repo_root)"

[ -f "$TEMPLATE_SRC" ] || {
  printf '[tcs-git-helpers:git-setup] ERROR: GHA template not found: %s\n' "$TEMPLATE_SRC" >&2
  exit 1
}

DST_DIR="$ROOT/.github/workflows"
DST="$DST_DIR/pr-title-check.yml"

mkdir -p "$DST_DIR"

if [ -f "$DST" ] && [ "${TCS_GHA_FORCE:-0}" != "1" ]; then
  # Idempotent: if existing file already comes from this plugin, overwrite
  # silently (template versioned). Otherwise warn and leave alone.
  if head -3 "$DST" | grep -q 'tcs-git-helpers'; then
    cp "$TEMPLATE_SRC" "$DST"
    printf '[tcs-git-helpers:git-setup] Refreshed existing GHA workflow at %s\n' "$DST"
  else
    printf '[tcs-git-helpers:git-setup] WARN: %s exists and is not from tcs-git-helpers; not overwriting.\n' "$DST" >&2
    printf '[tcs-git-helpers:git-setup] WARN: Re-run with TCS_GHA_FORCE=1 to overwrite, or remove the file first.\n' >&2
    exit 0
  fi
else
  cp "$TEMPLATE_SRC" "$DST"
  printf '[tcs-git-helpers:git-setup] Installed GHA workflow at %s\n' "$DST"
fi

# shellcheck disable=SC2016 # backticks are intentional prose
printf '[tcs-git-helpers:git-setup] Setup did NOT auto-commit. Review with `git status` and commit when ready.\n'
