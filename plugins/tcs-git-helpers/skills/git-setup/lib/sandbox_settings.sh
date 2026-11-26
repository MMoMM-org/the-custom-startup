#!/usr/bin/env bash
# tcs-git-helpers: v2.4.0
# skills/git-setup/lib/sandbox_settings.sh — merge the sandbox-compatible git
# settings template into the target repo's .claude/settings.json (#303).
#
# Usage:
#   sandbox_settings.sh --diff    print the change, write nothing
#   sandbox_settings.sh --apply   write the merged file
#
# The merge only adds: every array in the template is unioned into the same
# path of the existing file, order kept, duplicates dropped. Keys the template
# does not name are left as they are, so a re-run is a no-op.
#
# Output: one status line first, then (for --diff) a unified diff.
#   UP-TO-DATE <path>   the file already holds every template entry
#   PENDING <path>      --diff: the entries the diff shows are missing
#   WRITTEN <path>      --apply: the merged file was written
#
# Exit: 0 success, 1 error (not a repo, template missing, invalid JSON,
#       write refused).
#
# .claude/settings.json is a sandbox-protected path: --apply must run
# outside the Bash sandbox, after the user confirmed the --diff output.
#
# Constraints: bash 3.2, shellcheck-clean, needs jq.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
TEMPLATE="$PLUGIN_ROOT/templates/claude-settings/sandbox-git.json"

_err() { printf '[tcs-git-helpers:git-setup] ERROR: %s\n' "$1" >&2; exit 1; }

MODE="${1:-}"
case "$MODE" in
  --diff|--apply) ;;
  *) _err "usage: sandbox_settings.sh --diff | --apply" ;;
esac

command -v jq >/dev/null 2>&1 || _err "jq not found"
[ -f "$TEMPLATE" ] || _err "settings template not found: $TEMPLATE"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || _err "not inside a git repository"

TARGET="$ROOT/.claude/settings.json"
CURRENT='{}'
if [ -f "$TARGET" ]; then
  CURRENT="$(jq -e 'if type == "object" then . else error("not an object") end' "$TARGET" 2>/dev/null)" \
    || _err "$TARGET is not a JSON object; fix it by hand first"
fi

# Union each template array into the same path; a scalar or object already at
# that path is an error rather than something to overwrite.
MERGED="$(jq -n --argjson cur "$CURRENT" --slurpfile tpl "$TEMPLATE" '
  $tpl[0] as $t
  | reduce ($t | paths(type == "array")) as $p ($cur;
      (getpath($p) // []) as $have
      | if ($have | type) != "array"
        then error("\($p | join(".")) is not an array")
        else setpath($p; $have + (($t | getpath($p)) - $have))
        end)
' 2>&1)" || _err "cannot merge into $TARGET: $MERGED"

if [ "$(printf '%s' "$CURRENT" | jq -S .)" = "$(printf '%s' "$MERGED" | jq -S .)" ]; then
  printf 'UP-TO-DATE %s\n' "$TARGET"
  exit 0
fi

if [ "$MODE" = "--diff" ]; then
  printf 'PENDING %s\n' "$TARGET"
  # Files, not <(…): the sandbox denies /dev/fd, which process substitution
  # needs. mktemp needs a template there too.
  OLD="$(mktemp "${TMPDIR:-/tmp}/tcs-settings-old.XXXXXX")" || _err "cannot create a temp file"
  NEW="$(mktemp "${TMPDIR:-/tmp}/tcs-settings-new.XXXXXX")" || { rm -f "$OLD"; _err "cannot create a temp file"; }
  printf '%s\n' "$CURRENT" | jq . > "$OLD"
  printf '%s\n' "$MERGED" | jq . > "$NEW"
  diff -u --label "a/.claude/settings.json" --label "b/.claude/settings.json" "$OLD" "$NEW" || true
  rm -f "$OLD" "$NEW"
  exit 0
fi

mkdir -p "$ROOT/.claude" || _err "cannot create $ROOT/.claude (run outside the Bash sandbox)"
TMP="$(mktemp "$ROOT/.claude/.settings.json.XXXXXX" 2>/dev/null)" \
  || _err "cannot write in $ROOT/.claude (run outside the Bash sandbox)"
# mktemp creates the file 0600; a settings file is normally world-readable.
if ! { printf '%s\n' "$MERGED" | jq . > "$TMP" && chmod 0644 "$TMP" && mv "$TMP" "$TARGET"; }; then
  rm -f "$TMP"
  _err "cannot write $TARGET (run outside the Bash sandbox)"
fi
printf 'WRITTEN %s\n' "$TARGET"
