#!/usr/bin/env bash
#
# plugins/tcs-helper/scripts/observability/log_expansion.sh
#
# spec 021 (observability v2), phase 2, T2.3: `UserPromptExpansion` adapter
# (ADR-7). A skill the user TYPES (`/tcs-issues:issue ...`) never reaches
# `PreToolUse:Skill`; the only hook that sees it is this event. Reads the
# payload once from stdin and, only for `expansion_type: slash_command`,
# appends one `kind: skill` record with `route: typed`.
#
# Record fields (SDD/Application Data Models, kind = skill, typed route):
#   skill:        command_name, qualified for plugins ("tcs-issues:issue")
#   route:        typed
#   args_present: yes | no   -- whether command_args was non-empty; NEVER the text (CON-13)
#   source:       command_source ("plugin", "projectSettings", ...)
#
# `command_args` and `prompt` (the whole expanded prompt) are never read into
# a variable that reaches the writer. The payload is compact JSON (no space
# after the colon), the same assumption `_observability_field` makes.
# args_present comes from a `case` glob on the raw payload: `"command_args":""` is empty, `"command_args":"` followed
# by anything else is non-empty, absent is "no". A JSON-escaped occurrence
# inside the prompt text reads `\"command_args\":\"`, which neither glob
# matches, so the flat scan stays correct.
#
# THE READ IS `$(cat)`, NOT `IFS= read -r -d ''` (ADR-6): the read builtin
# costs ~62 ms at 200 KB, and this payload carries the whole expanded prompt.
# Do not copy that line from log_skill.sh.
#
# CON-4/CON-5: no stdout/stderr, always exit 0. CON-9: a payload that has
# drifted (no command_name, other expansion_type) records nothing. Flat
# top-level script, no `set -u`, for the same reason as log_skill.sh.

_log_expansion_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)" || _log_expansion_dir=""
# shellcheck source=./logwrite.sh
if [ -z "$_log_expansion_dir" ] || ! . "$_log_expansion_dir/logwrite.sh" 2>/dev/null; then
  cat >/dev/null 2>&1
  exit 0
fi

_payload="$(cat 2>/dev/null)" || _payload=""

# mcp_prompt (and any future type) is not a typed skill: record nothing.
_expansion_type="$(_observability_field "$_payload" expansion_type)" || _expansion_type=""
[ "$_expansion_type" = "slash_command" ] || exit 0

_command_name="$(_observability_field "$_payload" command_name)" || _command_name=""
[ -n "$_command_name" ] || exit 0

_session_id="$(_observability_field "$_payload" session_id)" || _session_id=""
_source="$(_observability_field "$_payload" command_source)" || _source=""

case "$_payload" in
  *'"command_args":""'*) _args_present="no" ;;
  *'"command_args":"'*)  _args_present="yes" ;;
  *)                     _args_present="no" ;;
esac

_observability_write kind=skill session="$_session_id" skill="$_command_name" \
  route=typed args_present="$_args_present" source="$_source"

exit 0
