#!/bin/bash
#
# plugins/tcs-helper/scripts/observability/log_tool.sh
#
# spec 021 (observability v2), T2.1: the single `PreToolUse` adapter for the
# tools worth recording. One process per tool call, dispatched on tool_name:
#   Skill -> kind=skill    route=tool          (F1 AC2)
#   Agent -> kind=dispatch                      (F2, ADR-8)
#   Bash  -> kind=git      hand-off to T2.2     (git_ops.sh; not written here)
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
#
# FIELD OCCURRENCE (`_log_tool_field`, below, reads a key linearly around large text;
# `_observability_field` is quadratic behind it):
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
#   No key this adapter reads appears at both levels, so first and last hit coincide.
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

_log_tool_dir="${BASH_SOURCE[0]%/*}"
case "${BASH_SOURCE[0]}" in */*) ;; *) _log_tool_dir="." ;; esac
# shellcheck source=./logwrite.sh
. "$_log_tool_dir/logwrite.sh" >/dev/null 2>&1 || exit 0

# Field read that stays linear around a large free-text value.
# `_observability_field` uses `${p#*"key":"}` (first hit), which is quadratic
# in the text BEFORE the key: measured 41 s for a key behind a 200 KB Agent
# `prompt`. `${p##*"key":"}` (last hit) is fast for a key behind the text but
# quadratic for a key in front of it (38 s). So: cut the payload at the first
# `"prompt":"` (a linear `%%` strip) and read keys that sit in front of it with
# the first-hit form on that short head; read the rest with the last-hit form
# on the whole payload. Last == only occurrence for every key this adapter
# reads (see FIELD OCCURRENCE above), and free text cannot forge a match
# because its quotes arrive escaped.
_log_tool_field() {
  local _p="$1" _k="\"$2\":\"" _head _b
  case "$_p" in *"$_k"*) ;; *) return 0 ;; esac
  _head="${_p%%\"prompt\":\"*}"
  case "$_head" in
    *"$_k"*) _b="${_head#*"$_k"}" ;;
    *) _b="${_p##*"$_k"}" ;;
  esac
  printf '%s' "${_b%%\"*}"
}

# T2.2 hand-off: parse the command and write git records. Not implemented in
# T2.1; the function exists so T2.2 replaces one clearly marked point.
_log_tool_git() { return 0; }

_session="$(_log_tool_field "$_payload" session_id)" || _session=""

case "$_kind" in
  git)
    _log_tool_git
    ;;
  skill)
    _skill="$(_log_tool_field "$_payload" skill)" || _skill=""
    _observability_write kind=skill session="$_session" skill="$_skill" route=tool >/dev/null 2>&1
    ;;
  dispatch)
    _sub_type="$(_log_tool_field "$_payload" subagent_type)" || _sub_type=""
    _name="$(_log_tool_field "$_payload" name)" || _name=""
    _use_id="$(_log_tool_field "$_payload" tool_use_id)" || _use_id=""
    _desc="$(_log_tool_field "$_payload" description)" || _desc=""
    _agent_id="$(_log_tool_field "$_payload" agent_id)" || _agent_id=""
    if [ -n "$_agent_id" ]; then
      _caller_type="$(_log_tool_field "$_payload" agent_type)" || _caller_type=""
      _observability_write kind=dispatch session="$_session" \
        subagent_type="$_sub_type" name="$_name" tool_use_id="$_use_id" \
        caller=subagent caller_agent_type="$_caller_type" caller_agent_id="$_agent_id" \
        "detail:description=$_desc" >/dev/null 2>&1
    else
      _observability_write kind=dispatch session="$_session" \
        subagent_type="$_sub_type" name="$_name" tool_use_id="$_use_id" \
        caller=main "detail:description=$_desc" >/dev/null 2>&1
    fi
    ;;
esac

exit 0
