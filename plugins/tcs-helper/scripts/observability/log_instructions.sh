#!/usr/bin/env bash
#
# plugins/tcs-helper/scripts/observability/log_instructions.sh
#
# Adapter for the InstructionsLoaded hook event (spec 018, T2.1). Registered
# directly as a hook command in this repo's own .claude/settings.json (T2.4),
# so — unlike logwrite.sh, which this file sources — it is EXECUTED, not
# sourced: the harness spawns it as its own process, payload JSON on stdin,
# once per instruction file loaded.
#
# Thin by contract (plan/phase-2.md "Key Decisions"): read stdin once,
# extract a handful of scalars, hand them to the writer. Any analysis beyond
# that belongs in report.py, offline, where it costs nothing on the hot
# path.
#
# CON-4/CON-5: this process must never write to stdout (a hook's stdout is
# parsed as JSON by the harness) and must always exit 0, so that a caller
# invoking it under `set -e` is never aborted by a recording failure. Every
# extraction below is guarded accordingly; the final `exit 0` is the
# backstop.
#
# logwrite.sh is sourced by PATH RELATIVE TO THIS FILE, not via
# CLAUDE_PLUGIN_ROOT: a hook this repo registers in its own
# .claude/settings.json gets no CLAUDE_PLUGIN_ROOT at invocation time (that
# variable reaches only hooks a plugin registers via its own hooks.json —
# see solution.md's ADR-1 premise correction). Resolving our own directory
# keeps this script correct regardless of $PWD or $CLAUDE_PROJECT_DIR at
# call time.

export LC_ALL=C

_log_instructions_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _log_instructions_dir=""
if [ -z "$_log_instructions_dir" ] || ! . "$_log_instructions_dir/logwrite.sh" 2>/dev/null; then
  # Cannot even load the writer: nothing to record with, but this must still
  # never fail loudly (CON-4/CON-5) — drain stdin so the harness never sees
  # a broken pipe, then get out of the way.
  cat >/dev/null 2>&1
  exit 0
fi

# Gate BEFORE forking anything else. _observability_write re-checks this
# itself, but checking here too means a disabled session forks neither git
# nor stat for a hook event that will not be recorded at all (PRD F3: off
# must cost nothing).
if [ "${CLAUDE_OBSERVABILITY_ENABLED:-}" != "1" ]; then
  cat >/dev/null 2>&1
  exit 0
fi

_payload="$(cat)" || _payload=""

# Resolve the repo toplevel ONCE (CON-7) and thread it into every
# _observability_redact_path call below, exactly as _observability_write
# does internally for its own `repo` field. See this task's report for the
# one fork this adapter cannot avoid without changing logwrite.sh itself
# (out of scope here): _observability_write resolves the toplevel AGAIN,
# independently, on every call — that is a second, unavoidable-from-here
# fork of the same command.
_toplevel="$(git rev-parse --show-toplevel 2>/dev/null)" || _toplevel=""

_session="$(_observability_field "$_payload" session_id)" || _session=""
_file_path="$(_observability_field "$_payload" file_path)" || _file_path=""
_memory_type="$(_observability_field "$_payload" memory_type)" || _memory_type=""
_load_reason="$(_observability_field "$_payload" load_reason)" || _load_reason=""
_trigger_file_path="$(_observability_field "$_payload" trigger_file_path)" || _trigger_file_path=""
_parent_file_path="$(_observability_field "$_payload" parent_file_path)" || _parent_file_path=""

# Eager loads at session start: the SDD documents session_start as the
# default reason (README, "eager: session_start (default) and compact") —
# applied here only when the payload omits the field entirely, never
# overriding a value the payload actually carries.
[ -n "$_load_reason" ] || _load_reason="session_start"

_path="$(_observability_redact_path "$_file_path" "$_toplevel")" || _path=""

# bytes: stat the loaded file's ORIGINAL path, before redaction — the
# record only ever gets the resulting number, never the path used to
# obtain it. A file that cannot be stat'ed (missing, permission denied, a
# race with something else deleting it) leaves `_bytes` empty, which below
# means the field is omitted entirely, not written as 0 or "" (SDD-AC-14).
# BSD needs -f%z, GNU needs -c%s; mirror logwrite.sh's own
# _observability_size rather than assuming one — see that function's
# comment for why both are tried.
_bytes=""
if _stat_out="$(stat -f%z "$_file_path" 2>/dev/null)"; then
  _bytes="$_stat_out"
elif _stat_out="$(stat -c%s "$_file_path" 2>/dev/null)"; then
  _bytes="$_stat_out"
fi

_args=(
  kind=instruction
  "session=$_session"
  "path=$_path"
  "scope=$_memory_type"
  "reason=$_load_reason"
)

# `parent` and `trigger` are populated only for the one reason each is
# documented under (SDD/Application Data Models) — gated on the reason
# actually extracted from the payload, not merely on whether the
# corresponding *_file_path field happens to be present.
case "$_load_reason" in
  include)
    _parent="$(_observability_redact_path "$_parent_file_path" "$_toplevel")" || _parent=""
    _args[${#_args[@]}]="parent=$_parent"
    ;;
  path_glob_match)
    _trigger="$(_observability_redact_path "$_trigger_file_path" "$_toplevel")" || _trigger=""
    _args[${#_args[@]}]="trigger=$_trigger"
    ;;
esac

if [ -n "$_bytes" ]; then
  _args[${#_args[@]}]="bytes=$_bytes"
fi

_observability_write "${_args[@]}"

exit 0
