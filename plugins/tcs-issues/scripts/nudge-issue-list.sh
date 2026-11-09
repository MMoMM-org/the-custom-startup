#!/bin/bash
# scripts/nudge-issue-list.sh — PostToolUse:Bash note after `gh issue list`.
#
# A listing shows titles, and a title is the part of an issue that goes stale
# first. Recommending from a listing has twice proposed work that the issue's
# comments showed was done. The note asks for a comment-inclusive read of an
# issue before recommending, planning or reporting its status. It never blocks.
#
# Fails open: malformed stdin, a missing jq or a non-Bash tool exits 0 with no
# output. bash 3.2 compatible: grep -E with POSIX classes only.

set -uo pipefail

INPUT=$(cat)
case "$INPUT" in *issue*list*) ;; *) exit 0 ;; esac

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null) || TOOL=""
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null) || CMD=""
[ -n "$CMD" ] || exit 0

ISSUE_LIST='(^|[^[:alnum:]_-])gh([[:space:]]+[^[:space:]|;&]+)*[[:space:]]+issue[[:space:]]+list([^[:alnum:]_-]|$)'
printf '%s\n' "$CMD" | grep -Eq -- "$ISSUE_LIST" || exit 0

NOTE='An issue listing shows titles only, and titles go stale first. Before recommending, planning or reporting status on any issue in this list, read it with its comments: gh issue view <N> --comments.'

jq -n --arg n "$NOTE" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $n}}'
exit 0
