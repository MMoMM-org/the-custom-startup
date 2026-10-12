#!/bin/bash
#
# plugins/tcs-helper/scripts/observability/log_tool.sh
#
# spec 021 (observability v2), T2.1: the single `PreToolUse` adapter for the
# tools worth recording. One process per tool call, dispatched on tool_name:
#   Skill -> kind=skill    route=tool          (F1 AC2)
#   Agent -> kind=dispatch                      (F2, ADR-8)
#   Bash  -> kind=git      one record per non-read-only git call (F3, ADR-9)
#   other -> nothing
#
# ORDER OF OPERATIONS IS THE PERFORMANCE BUDGET (ADR-1, ADR-6, CON-7). This
# runs on every Bash call, so a non-git Bash payload must leave before the
# first `source` and before any fork beyond the one `cat`:
#   1. disabled        -> drain stdin, exit
#   2. $(cat)          -> one fork; never `read -d ''` (62 ms at 200 KB, ADR-6)
#   3. tool_name test  -> `case` on the raw payload
#   4. Bash only       -> substring test for "git" on the text AFTER the
#                         `"command":"` key (cwd/transcript_path may contain
#                         "github"); no "git" there -> exit, nothing sourced
#   5. only now        -> source logwrite.sh, extract, write
#   6. git path only   -> source git_ops.sh (guarded), decode, parse; only
#                         when the parse yields a record: one `git rev-parse
#                         --show-toplevel`, shared by every record of the
#                         payload via `_observability_toplevel=` (CON-7)
#
# FIELD OCCURRENCE (`_observability_field` takes the FIRST `"key":"` hit and is
# linear for any key position, so a 200 KB prompt costs nothing extra):
#   - A key is matched with its leading quote, so `"name":"` does not hit
#     `"tool_name":"` and `"agent_type":"` does not hit `"subagent_type":"`.
#   - Text inside prompt/description arrives JSON-escaped (`\"k\":\"`), which
#     cannot match `"k":"`, so free text cannot forge a field.
#   - `agent_id`/`agent_type` exist only at the TOP LEVEL, and only inside a
#     subagent; tool_input of an Agent call carries `subagent_type`, never
#     `agent_type`, so the first (only) hit is the caller's. `agent_id`
#     presence is what decides caller=subagent.
#   - `name`, `subagent_type` and `skill` exist only inside tool_input.
#   - `tool_use_id` and `session_id` exist only at the top level.
#   No key this adapter reads appears at both levels, so there is no first/last ambiguity.
#
# Never recorded: tool_input.prompt, args (CON-13). tool_input.description is
# written only as `detail:description` (detail mode).
#
# CON-4/CON-5: nothing on stdout or stderr, always exit 0. Deliberately no
# `set -e`/`set -u`.

if [ "${CLAUDE_OBSERVABILITY_ENABLED:-}" != "1" ]; then cat >/dev/null 2>&1; exit 0; fi
_payload="$(cat 2>/dev/null)" || _payload=""

case "$_payload" in
  *'"tool_name":"Bash"'*)
    # Test the command value, not the whole payload (see header, step 4).
    _cmd_tail="${_payload#*\"command\":\"}"
    case "$_cmd_tail" in *git*) ;; *) exit 0 ;; esac
    _kind=git ;;
  *'"tool_name":"Skill"'*) _kind=skill ;;
  *'"tool_name":"Agent"'*) _kind=dispatch ;;
  *) exit 0 ;;
esac

case "${BASH_SOURCE[0]}" in */*) _log_tool_dir="${BASH_SOURCE[0]%/*}" ;; *) _log_tool_dir="." ;; esac
# shellcheck source=./logwrite.sh
. "$_log_tool_dir/logwrite.sh" >/dev/null 2>&1 || exit 0

# _log_tool_caller  sets the array `_caller` to the caller fields of a
# dispatch or git record: caller=main, or caller=subagent with the payload's
# agent_type and agent_id (see FIELD OCCURRENCE above).
_log_tool_caller() {
  local agent_id agent_type
  agent_id="$(_observability_field "$_payload" agent_id)" || agent_id=""
  _caller=(caller=main)
  if [ -n "$agent_id" ]; then
    agent_type="$(_observability_field "$_payload" agent_type)" || agent_type=""
    _caller=(caller=subagent caller_agent_type="$agent_type" caller_agent_id="$agent_id")
  fi
}

# _log_tool_git  writes one kind=git record per line _git_ops_parse prints
# (subcommand TAB action TAB flags TAB overrides TAB override_first). Every
# field is a name from the parser (CON-13); empty fields are written as ""
# so every git record has one shape. git_ops.sh missing, unreadable or
# defining nothing (a half-updated bundle) means no git record and no
# output: the skill and dispatch paths never source it.
_log_tool_git() {
  [ -f "$_log_tool_dir/git_ops.sh" ] || return 0
  # shellcheck source=./git_ops.sh
  . "$_log_tool_dir/git_ops.sh" >/dev/null 2>&1 || return 0
  declare -F _git_ops_command _git_ops_parse >/dev/null 2>&1 || return 0

  local cmd lines line rest sub action flags overrides first top use_id
  local TAB=$'\t' NL=$'\n'
  cmd="$(_git_ops_command "$_payload" 2>/dev/null)" || cmd=""
  [ -n "$cmd" ] || return 0
  lines="$(_git_ops_parse "$cmd" 2>/dev/null)" || lines=""
  [ -n "$lines" ] || return 0

  # Once per payload, not per record, and only when there is a record.
  top="$(git rev-parse --show-toplevel 2>/dev/null)" || top=""
  use_id="$(_observability_field "$_payload" tool_use_id)" || use_id=""
  _log_tool_caller

  rest="$lines$NL"
  while [ -n "$rest" ]; do
    line="${rest%%"$NL"*}"
    rest="${rest#*"$NL"}"
    [ -n "$line" ] || continue
    # Split by hand: with IFS=TAB `read` would merge empty fields.
    sub="${line%%"$TAB"*}";       line="${line#*"$TAB"}"
    action="${line%%"$TAB"*}";    line="${line#*"$TAB"}"
    flags="${line%%"$TAB"*}";     line="${line#*"$TAB"}"
    overrides="${line%%"$TAB"*}"; first="${line#*"$TAB"}"
    _observability_write kind=git session="$_session" "_observability_toplevel=$top" \
      subcommand="$sub" action="$action" flags="$flags" overrides="$overrides" \
      override_first="$first" "${_caller[@]}" tool_use_id="$use_id" >/dev/null 2>&1
  done
  return 0
}

_session="$(_observability_field "$_payload" session_id)" || _session=""

case "$_kind" in
  git)
    _log_tool_git
    ;;
  skill)
    _skill="$(_observability_field "$_payload" skill)" || _skill=""
    # An empty skill name (malformed payload) would only add a junk row.
    [ -n "$_skill" ] && _observability_write kind=skill session="$_session" skill="$_skill" route=tool >/dev/null 2>&1
    ;;
  dispatch)
    _sub_type="$(_observability_field "$_payload" subagent_type)" || _sub_type=""
    _name="$(_observability_field "$_payload" name)" || _name=""
    _use_id="$(_observability_field "$_payload" tool_use_id)" || _use_id=""
    _desc="$(_observability_field "$_payload" description)" || _desc=""
    _log_tool_caller
    _observability_write kind=dispatch session="$_session" \
      subagent_type="$_sub_type" name="$_name" tool_use_id="$_use_id" \
      "${_caller[@]}" "detail:description=$_desc" >/dev/null 2>&1
    ;;
esac

exit 0
