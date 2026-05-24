#!/usr/bin/env bash
# tcs-git-helpers: v2.0.1
# skills/git-setup/lib/detect_conflicts.sh — Conflict detection for setup.
#
# Examines the current repo (cwd or git toplevel) for hook-tooling collisions
# and prints a human-readable summary. Exit code signals the action the skill
# should take next:
#
#   0  No conflicts; safe to install (clean repo OR existing matching version)
#   2  ABORT — Husky/lefthook/pre-commit/simple-git-hooks/custom-hooksPath
#   3  CONFLICT — existing .githooks/ without a tcs-git-helpers marker, or
#      older marker (skill should run per-file diff / --update flow)
#   4  WARN — non-.sample files in .git/hooks/, submodules, or other soft
#      conditions; setup may proceed after user confirmation
#
# Spec refs:
#   - integration §5 Conflict-Detection Signatures
#   - PRD M10 AC2 (Husky/lefthook/pre-commit/simple-git-hooks abort)
#   - PRD M10 AC3 (.git/hooks/ non-.sample warn+confirm)
#   - PRD M10 AC6 (submodules listed; not recursed)
#   - ADR-10 (abort policy)
#
# Constraints:
#   - bash 3.2 (no associative arrays; no \s\b regex)
#   - shellcheck-clean
#   - No network; reads only from filesystem and `git config`

set -euo pipefail

_repo_root() {
  if git rev-parse --show-toplevel 2>/dev/null; then
    return 0
  fi
  printf '%s' "$PWD"
}

_emit() {
  # $1 = severity tag, $2 = message
  printf '[tcs-git-helpers:git-setup] %s: %s\n' "$1" "$2"
}

ROOT="$(_repo_root)"
cd "$ROOT" 2>/dev/null || true

# Read the expected version from .claude-plugin/plugin.json so the detector
# stays in sync with the plugin's own version when minor/major bumps happen.
# Falls back to a literal if the manifest can't be read.
_read_plugin_version() {
  local manifest="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}/.claude-plugin/plugin.json"
  if [ ! -f "$manifest" ]; then
    printf '0.0.0'
    return 0
  fi
  grep -E '"version"[[:space:]]*:' "$manifest" \
    | head -1 \
    | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
}
WANT_VERSION="v$(_read_plugin_version)"

# Highest-severity exit so far; bash arithmetic max.
STATUS=0
_bump() {
  # $1 = candidate exit code; we keep the higher (= more severe)
  if [ "$1" -gt "$STATUS" ]; then
    STATUS="$1"
  fi
}

# --- 1. Husky --------------------------------------------------------------
if [ -d ".husky" ]; then
  # v8/v9 ships a .husky/_/ runtime; check for non-_ files too.
  _emit "ABORT" "Husky detected (.husky/ directory present)."
  _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
  _bump 2
fi

if [ -f "package.json" ]; then
  # v8/v9: "husky" key OR "prepare":"husky install"
  # v4:    "husky": {"hooks": {…}}
  if grep -qE '"husky"[[:space:]]*:' package.json; then
    _emit "ABORT" "Husky detected (package.json \"husky\" key)."
    _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
    _bump 2
  elif grep -qE '"prepare"[[:space:]]*:[[:space:]]*"husky' package.json; then
    _emit "ABORT" "Husky detected (package.json \"prepare\":\"husky install\")."
    _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
    _bump 2
  fi

  # simple-git-hooks: "simple-git-hooks" key
  if grep -qE '"simple-git-hooks"[[:space:]]*:' package.json; then
    _emit "ABORT" "simple-git-hooks detected (package.json key)."
    _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
    _bump 2
  fi
fi

# --- 2. lefthook -----------------------------------------------------------
for f in lefthook.yml lefthook.yaml .lefthook.yml; do
  if [ -f "$f" ]; then
    _emit "ABORT" "lefthook detected ($f)."
    _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
    _bump 2
    break
  fi
done

# --- 3. pre-commit (Python framework) -------------------------------------
PCF=""
[ -f ".pre-commit-config.yaml" ] && PCF=".pre-commit-config.yaml"
[ -z "$PCF" ] && [ -f ".pre-commit-config.yml" ] && PCF=".pre-commit-config.yml"
if [ -n "$PCF" ]; then
  _emit "ABORT" "pre-commit framework detected ($PCF)."
  _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
  _bump 2
fi

# --- 4. Custom core.hooksPath (≠ .githooks) -------------------------------
HOOKS_PATH="$(git config --get core.hooksPath 2>/dev/null || true)"
if [ -n "$HOOKS_PATH" ] && [ "$HOOKS_PATH" != ".githooks" ]; then
  # Normalize: VS Code (and other tools) may set hooksPath to the absolute
  # path of git's own default hooks directory (e.g. /repo/.git/hooks), which
  # is functionally equivalent to unset. Detect this by canonicalizing both
  # HOOKS_PATH and <repo-root>/.git/hooks via python3 realpath (bash 3.2-safe;
  # avoids GNU coreutils dep; python3 is ubiquitous on macOS/Linux).
  if command -v python3 >/dev/null 2>&1; then
    _resolved_hooks="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$HOOKS_PATH" 2>/dev/null || true)"
    _git_default_hooks="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$ROOT/.git/hooks" 2>/dev/null || true)"
    if [ -n "$_resolved_hooks" ] && [ "$_resolved_hooks" = "$_git_default_hooks" ]; then
      _emit "INFO" "custom hooksPath resolves to git default (.git/hooks); treating as default-equivalent"
      HOOKS_PATH=""
    fi
    unset _resolved_hooks _git_default_hooks
  fi
  if [ -n "$HOOKS_PATH" ]; then
    _emit "ABORT" "core.hooksPath is set to '$HOOKS_PATH' (not '.githooks')."
    _emit "REF"   "See plugins/tcs-git-helpers/references/migrating-from-husky.md"
    _bump 2
  fi
fi

# --- 5. Existing .githooks/ marker check ----------------------------------
if [ -d ".githooks" ]; then
  # Look for the version banner on line 1-3 of any standard hook file.
  # Accept both `v<semver>` (canonical, install_files.sh from v2.2.2 onward)
  # and bare `<semver>` (legacy banners written by v2.0.0..v2.2.1 installs).
  # Comparison below normalizes the leading v? before equality.
  marker_line=""
  for h in .githooks/pre-commit .githooks/commit-msg .githooks/pre-push .githooks/post-merge; do
    if [ -f "$h" ]; then
      marker_line="$(head -3 "$h" 2>/dev/null | grep -E '^#[[:space:]]*tcs-git-helpers:[[:space:]]*v?[0-9]' | head -1 || true)"
      [ -n "$marker_line" ] && break
    fi
  done

  if [ -z "$marker_line" ]; then
    # Existing .githooks/ without marker → CONFLICT (per-file diff prompt).
    _emit "CONFLICT" "Existing .githooks/ found with no tcs-git-helpers version marker."
    _emit "INFO"     "Skill will switch to per-file diff mode; no overwrite without confirmation."
    _bump 3
  else
    # Extract raw banner value, then normalize by stripping whitespace and a
    # single leading 'v'. WANT_VERSION carries the 'v' prefix for display, so
    # we strip it on both sides to compare like-for-like.
    found_version_raw="${marker_line##*:}"
    found_version_raw="$(printf '%s' "$found_version_raw" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    found_version_norm="${found_version_raw#v}"
    want_version_norm="${WANT_VERSION#v}"
    if [ "$found_version_norm" = "$want_version_norm" ]; then
      _emit "OK" "Existing .githooks/ already at matching version $WANT_VERSION (up to date)."
      # status stays 0 (or whatever was set by other checks)
    else
      _emit "OUTDATED" "Existing .githooks/ at $found_version_raw (does not match expected $WANT_VERSION); update mode recommended."
      _bump 3
    fi
  fi
fi

# --- 6. Non-.sample files in .git/hooks/ ----------------------------------
if [ -d ".git/hooks" ]; then
  non_sample=""
  for f in .git/hooks/*; do
    [ -e "$f" ] || continue
    case "$f" in
      *.sample) continue ;;
    esac
    if [ -f "$f" ]; then
      non_sample="$non_sample $f"
    fi
  done
  if [ -n "$non_sample" ]; then
    _emit "WARN" "Non-.sample hook files in .git/hooks/ (won't fire under core.hooksPath but will linger):${non_sample}"
    _bump 4
  fi
fi

# --- 7. Submodules ---------------------------------------------------------
if [ -f ".gitmodules" ]; then
  _emit "INFO" "Submodules detected (.gitmodules present); setup does NOT recurse into them."
  while IFS= read -r line; do
    case "$line" in
      *"path = "*)
        sub="${line##*path = }"
        _emit "INFO" "  submodule: $sub"
        ;;
    esac
  done < .gitmodules
  # Submodules alone aren't a hard-warn; only bump if user wants explicit warn.
fi

exit "$STATUS"
