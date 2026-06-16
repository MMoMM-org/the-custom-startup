#!/usr/bin/env bash
# tcs-git-helpers: v2.0.0
# skills/git-setup/lib/install_files.sh — Copy templates into target repo.
#
# Performs the actual filesystem writes for /tcs-git-helpers:git-setup:
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
#   - SDD §Skills — /tcs-git-helpers:git-setup workflow step 4
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
# resolved relative to this file (plugins/tcs-git-helpers/skills/git-setup/lib/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

TEMPLATES="$PLUGIN_ROOT/templates/githooks"
HOOK_FILES="pre-commit pre-push commit-msg post-merge"
EXAMPLE_FILES=".config.example exclude-paths.example"

# Read the plugin's semantic version from .claude-plugin/plugin.json so the
# version banner stamped into installed hooks always matches plugin.json. This
# removes the manual-sync trap where a plugin minor/major bump leaves stale
# `# tcs-git-helpers: vX.Y.Z` markers in users' repos and makes the conflict
# detector report OUTDATED falsely. Substituted into the placeholder
# `__TCS_GIT_HELPERS_VERSION__` in each template at install time.
_read_plugin_version() {
  local manifest="$PLUGIN_ROOT/.claude-plugin/plugin.json"
  if [ ! -f "$manifest" ]; then
    printf '0.0.0'
    return 0
  fi
  grep -E '"version"[[:space:]]*:' "$manifest" \
    | head -1 \
    | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
}
PLUGIN_VERSION="$(_read_plugin_version)"

# Read the hook bundle version from templates/githooks/tcs-git-helpers-version.
# Trimmed via tr to strip any trailing newline or whitespace.
_read_hook_bundle_version() {
  local version_file="$TEMPLATES/tcs-git-helpers-version"
  if [ ! -f "$version_file" ]; then
    printf 'unknown'
    return 0
  fi
  tr -d '[:space:]' < "$version_file"
}
HOOK_BUNDLE_VERSION="$(_read_hook_bundle_version)"

_repo_root() {
  if git rev-parse --show-toplevel 2>/dev/null; then
    return 0
  fi
  printf '[tcs-git-helpers:git-setup] ERROR: not inside a git repository\n' >&2
  return 1
}

ROOT="$(_repo_root)"
[ -d "$TEMPLATES" ] || {
  printf '[tcs-git-helpers:git-setup] ERROR: templates dir not found: %s\n' "$TEMPLATES" >&2
  exit 1
}

# --- Subshell-bounded sentinel block (ADR-11) ------------------------------
# Everything that touches .githooks/* or .git/config goes inside `(...)`.
# Subshell exit drops TCS_GIT_HELPERS_SETUP_ACTIVE — verified by bats C26.
(
  export TCS_GIT_HELPERS_SETUP_ACTIVE=1

  mkdir -p "$ROOT/.githooks"

  # Ensure the runtime lock is never committed. .githooks/.setup.lock is
  # per-machine state written by lib/lock.sh; committing it would falsely
  # serialize other clones and leave a dead-PID lock in history. A self-
  # contained .githooks/.gitignore travels with the bundle and covers every
  # collaborator. Idempotent: only add the rule if it is not already present.
  if [ ! -f "$ROOT/.githooks/.gitignore" ]; then
    printf '%s\n' ".setup.lock" > "$ROOT/.githooks/.gitignore"
  elif ! grep -qxF ".setup.lock" "$ROOT/.githooks/.gitignore"; then
    printf '%s\n' ".setup.lock" >> "$ROOT/.githooks/.gitignore"
  fi

  # Copy hook scripts, substituting both version placeholders so the installed
  # banners always reflect plugin.json and the bundle version file.
  for h in $HOOK_FILES; do
    src="$TEMPLATES/$h"
    dst="$ROOT/.githooks/$h"
    if [ -f "$src" ]; then
      sed \
        -e "s/__TCS_GIT_HELPERS_VERSION__/${PLUGIN_VERSION}/g" \
        -e "s/__HOOK_BUNDLE_VERSION__/${HOOK_BUNDLE_VERSION}/g" \
        "$src" > "$dst"
      chmod +x "$dst"
    fi
  done

  # Copy lib-bundle.sh verbatim (byte-equal; substitution must NOT apply).
  if [ -f "$TEMPLATES/lib-bundle.sh" ]; then
    cp "$TEMPLATES/lib-bundle.sh" "$ROOT/.githooks/lib-bundle.sh"
  fi

  # Copy lib-config-parser.sh verbatim (byte-equal; substitution must NOT apply).
  # Installed as lib-config-parser.sh so hooks can source it without any
  # env-var dependency (CON-2 + ADR-1 sibling layout).
  if [ -f "$TEMPLATES/lib-config-parser.sh" ]; then
    cp "$TEMPLATES/lib-config-parser.sh" "$ROOT/.githooks/lib-config-parser.sh"
  fi

  # Write tcs-git-helpers-version atomically (.tmp -> mv).
  printf '%s\n' "$HOOK_BUNDLE_VERSION" > "$ROOT/.githooks/tcs-git-helpers-version.tmp"
  mv "$ROOT/.githooks/tcs-git-helpers-version.tmp" "$ROOT/.githooks/tcs-git-helpers-version"

  # Copy *.example files (kept as -example, not renamed). Same substitution.
  for ex in $EXAMPLE_FILES; do
    src="$TEMPLATES/$ex"
    dst="$ROOT/.githooks/$ex"
    if [ -f "$src" ]; then
      sed "s/__TCS_GIT_HELPERS_VERSION__/${PLUGIN_VERSION}/g" "$src" > "$dst"
    fi
  done

  # Set core.hooksPath atomically via git config.
  ( cd "$ROOT" && git config core.hooksPath ".githooks" )
)
# --- End subshell ---------------------------------------------------------

printf '[tcs-git-helpers:git-setup] Installed .githooks/* into %s\n' "$ROOT"
printf '[tcs-git-helpers:git-setup] core.hooksPath=.githooks (per-repo)\n'
# shellcheck disable=SC2016 # backticks are intentional prose
printf '[tcs-git-helpers:git-setup] Setup did NOT auto-commit. Review with `git status` and commit when ready.\n'
