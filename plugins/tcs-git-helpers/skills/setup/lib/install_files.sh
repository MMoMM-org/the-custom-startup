#!/usr/bin/env bash
# tcs-git-helpers: v1.0.0
# skills/setup/lib/install_files.sh — Copy templates into target repo.
#
# Performs the actual filesystem writes for /tcs-git-helpers:setup:
#   1. Copies templates/githooks/{pre-commit,pre-push,commit-msg,post-merge}
#      to <repo>/.githooks/ (preserving the version banner).
#   2. Copies .config.example and exclude-paths.example.
#   3. chmod +x on hook scripts.
#   4. Sets `core.hooksPath = .githooks` in repo's .git/config.
#   5. Does NOT auto-commit (M10 AC5).
#
# All file writes happen INSIDE a subshell that exports
# TCS_GIT_HELPERS_SETUP_ACTIVE=1 (ADR-11). The subshell exit ensures the
# sentinel does not leak into the parent shell — verified by bats C26.
#
# Spec refs:
#   - PRD M10 AC1 (clean repo install: .githooks/* + version markers + core.hooksPath + summary)
#   - PRD M10 AC5 (no auto-commit)
#   - SDD §Skills — /tcs-git-helpers:setup workflow step 4
#   - ADR-11 (TCS_GIT_HELPERS_SETUP_ACTIVE subshell sentinel)
#
# Constraints:
#   - bash 3.2; no associative arrays
#   - shellcheck-clean
#   - Must succeed even when invoked outside the Claude Code hook environment
#     (so hooks like protect-git-internals.sh would deny the writes — that hook
#     only runs under Claude Code's PreToolUse pipeline, not from raw bash).

set -euo pipefail

# Plugin root: $CLAUDE_PLUGIN_ROOT when invoked under Claude Code, otherwise
# resolved relative to this file (plugins/tcs-git-helpers/skills/setup/lib/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

TEMPLATES="$PLUGIN_ROOT/templates/githooks"
HOOK_FILES="pre-commit pre-push commit-msg post-merge"
EXAMPLE_FILES=".config.example exclude-paths.example"

_repo_root() {
  if git rev-parse --show-toplevel 2>/dev/null; then
    return 0
  fi
  printf '[tcs-git-helpers:setup] ERROR: not inside a git repository\n' >&2
  return 1
}

ROOT="$(_repo_root)"
[ -d "$TEMPLATES" ] || {
  printf '[tcs-git-helpers:setup] ERROR: templates dir not found: %s\n' "$TEMPLATES" >&2
  exit 1
}

# --- Subshell-bounded sentinel block (ADR-11) ------------------------------
# Everything that touches .githooks/* or .git/config goes inside `(...)`.
# Subshell exit drops TCS_GIT_HELPERS_SETUP_ACTIVE — verified by bats C26.
(
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1

  mkdir -p "$ROOT/.githooks"

  # Copy hook scripts.
  for h in $HOOK_FILES; do
    src="$TEMPLATES/$h"
    dst="$ROOT/.githooks/$h"
    if [ -f "$src" ]; then
      cp "$src" "$dst"
      chmod +x "$dst"
    fi
  done

  # Copy *.example files (kept as -example, not renamed).
  for ex in $EXAMPLE_FILES; do
    src="$TEMPLATES/$ex"
    dst="$ROOT/.githooks/$ex"
    if [ -f "$src" ]; then
      cp "$src" "$dst"
    fi
  done

  # Set core.hooksPath atomically via git config.
  ( cd "$ROOT" && git config core.hooksPath ".githooks" )
)
# --- End subshell ---------------------------------------------------------

printf '[tcs-git-helpers:setup] Installed .githooks/* into %s\n' "$ROOT"
printf '[tcs-git-helpers:setup] core.hooksPath=.githooks (per-repo)\n'
# shellcheck disable=SC2016 # backticks are intentional prose
printf '[tcs-git-helpers:setup] Setup did NOT auto-commit. Review with `git status` and commit when ready.\n'
