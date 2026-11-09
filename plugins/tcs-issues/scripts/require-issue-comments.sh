#!/bin/bash
# scripts/require-issue-comments.sh — PreToolUse:Bash guard.
#
# Denies a `gh issue view` that reads an issue's text without its comments.
# An issue's title and body go stale; the comments say what was already done,
# decided or found. Reading only the body has twice led to recommending work
# that comments showed was finished.
#
# Denied:  `gh issue view N` with neither --json nor --comments nor --web;
#          `--json <fields>` where the fields include body but not comments.
# Allowed: --comments, --web, a --json read without body (state, labels, ...),
#          and every other command.
#
# Fails open: malformed stdin, a missing jq or a non-Bash tool exits 0 with no
# output. bash 3.2 compatible: grep -E with POSIX classes, no `\s` or `\b`.

set -uo pipefail

INPUT=$(cat)

# Fast path: no `issue` and `view` in the payload means nothing to check.
case "$INPUT" in *issue*view*) ;; *) exit 0 ;; esac

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null) || TOOL=""
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null) || CMD=""
[ -n "$CMD" ] || exit 0

ISSUE_VIEW='(^|[^[:alnum:]_-])gh([[:space:]]+[^[:space:]|;&]+)*[[:space:]]+issue[[:space:]]+view([^[:alnum:]_-]|$)'
printf '%s\n' "$CMD" | grep -Eq -- "$ISSUE_VIEW" || exit 0

_has_flag() {
  printf '%s\n' "$CMD" | grep -Eq -- "(^|[[:space:]])$1([[:space:]=]|$)"
}

_reads_text_without_comments() {
  _has_flag '--comments' && return 1
  _has_flag '--web' && return 1
  if ! _has_flag '--json'; then
    return 0
  fi
  local fields
  while IFS= read -r fields; do
    fields="${fields#--json}"
    fields="${fields#[=[:space:]]}"
    fields="${fields#"${fields%%[![:space:]]*}"}"
    fields=$(printf '%s' "$fields" | tr -d "\"'")
    case ",$fields," in
      *,comments,*) ;;
      *,body,*) return 0 ;;
    esac
  done <<EOF
$(printf '%s\n' "$CMD" | grep -Eo -- '--json([[:space:]]+|=)[^[:space:];|&)]+')
EOF
  return 1
}

_reads_text_without_comments || exit 0

REASON='This reads a GitHub issue without its comments. Comments record what was already done, decided or found, so the title and body alone can be stale. Add --comments, or include comments in --json (e.g. --json title,body,comments). A status-only read such as --json state is not blocked.'

if command -v jq >/dev/null 2>&1; then
  jq -n --arg r "$REASON" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
fi
exit 0
