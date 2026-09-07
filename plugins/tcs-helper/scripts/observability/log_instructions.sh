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
#
# LC_ALL=C is NOT re-exported here. logwrite.sh exports it at the top of the
# file, so it is in effect from the moment the source below succeeds, and
# nothing this script does BEFORE that point is locale-sensitive (`dirname`,
# `cd`, `pwd`) — nor does the failure path (drain stdin, exit) touch a number
# or a collation order. A second export would be a second place for the
# setting to drift from the one that actually governs the write path. All
# three adapters follow this rule.

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
# _observability_redact_path call below AND into _observability_write, via
# the writer's reserved `_observability_toplevel=` pair (see that function's
# header). Before that pair existed, the writer resolved the toplevel again,
# independently, on every call — two forks of the same command per recorded
# event, on a hook that fires once per instruction file loaded. Passing it
# even when EMPTY is deliberate and part of the contract: empty means
# "outside a repo, already determined", not "not supplied", so the writer
# does not fork to re-check.
_toplevel="$(git rev-parse --show-toplevel 2>/dev/null)" || _toplevel=""

_session="$(_observability_field "$_payload" session_id)" || _session=""
_file_path="$(_observability_field "$_payload" file_path)" || _file_path=""
_memory_type="$(_observability_field "$_payload" memory_type)" || _memory_type=""
_load_reason="$(_observability_field "$_payload" load_reason)" || _load_reason=""
_trigger_file_path="$(_observability_field "$_payload" trigger_file_path)" || _trigger_file_path=""
_parent_file_path="$(_observability_field "$_payload" parent_file_path)" || _parent_file_path=""

# No fallback here on purpose. The README's "eager: session_start (default)
# and compact" describes what the REAL harness does at its emission sites —
# load_reason is verified always present there — not a license for this
# adapter to invent a value when a payload lacks the field. A payload
# missing load_reason entirely is an anomaly (a harness version drift, a
# malformed payload), and fabricating "session_start" would make that
# anomaly permanently indistinguishable from a genuine session-start load
# once it reaches report.py — exactly the "records wrong things" failure
# this design exists to avoid. Left as extracted: empty when absent, which
# `reason=$_load_reason` below still WRITES (the schema has no `?` on
# `reason`), just with an empty value the report can flag as unknown.

_path="$(_observability_redact_path "$_file_path" "$_toplevel")" || _path=""

# A record with no usable path carries no information: PRD F4's "configured
# vs. loaded" denominator would be inflated by a phantom load that never
# named a file. This can happen on an empty or malformed payload (no test
# in this suite constructs one deliberately outside this guard's own
# tests) — an anomaly, not a real instruction load. Same posture as
# `bytes` and `reason` above: write nothing rather than something the
# report cannot tell apart from a genuine event. Checked on `_path`, not
# `_file_path`, so the one legitimate empty-looking case — the toplevel
# itself, which `_observability_redact_path` reduces to "." — is never
# mistaken for "no path": "." is non-empty.
if [ -z "$_path" ]; then
  exit 0
fi

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
  "_observability_toplevel=$_toplevel"
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
