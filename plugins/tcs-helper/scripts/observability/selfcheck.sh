#!/usr/bin/env bash
#
# plugins/tcs-helper/scripts/observability/selfcheck.sh
#
# spec 018 (observability of what loads and fires), T2.4: answers one
# question honestly -- "is this actually recording?" -- for a human running
# it by hand.
#
# HUMAN-FACING ONLY, NOT A HOOK. This is not registered in .claude/settings.json
# or any hooks.json, is not one of the three events T2.4 registers
# (InstructionsLoaded, PreToolUse/Skill, SubagentStart), and nothing in this
# spec ever pipes a hook payload into it. That decision is deliberate, not an
# oversight: registering it AS a hook would need an event to fire it on, and
# no event in this design corresponds to "someone wants to know the recording
# state right now" -- it is a question asked on demand, not a reaction to
# something the harness does. Consequences of that decision:
#   - CON-4 (a hook's stdout is parsed as JSON) does not apply here. This
#     script prints human-readable lines to stdout ON PURPOSE -- that IS its
#     product.
#   - CON-5 (a hook's exit status must never change) does not apply either.
#     Exit status is used for something: 0 when recording is off (by choice)
#     or confirmed working, 1 when it is ON but a genuine round-trip proves
#     it cannot actually record -- so `selfcheck.sh || alert` is a usable
#     health check, not just a print statement.
# If a future revision ever wants this invoked automatically from a hook
# event, that is a different script (or a `--quiet`/machine-readable mode of
# this one) built to CON-4/CON-5's contract from the start -- not a relaxation
# of the contract here.
#
# WHY IT CANNOT TRUST THE WRITER'S EXIT STATUS OR STREAMS
# ---------------------------------------------------------------------------
# _observability_write (logwrite.sh) is fail-open BY DESIGN (CON-5): it always
# returns 0, never writes to stdout or stderr, and leaves no sentinel of its
# own failures -- a full disk, an unwritable directory, a broken rotation
# chain all look identical to success from the caller's side. A selfcheck
# that asked "did the writer return 0?" or "does the directory exist?" would
# be green in exactly the cases it exists to catch. The only honest answer is
# a ROUND TRIP: write a known probe value, then independently read the file
# back and confirm that exact value landed. This script writes the required
# `kind: state` record (SDD/Application Data Models) as that probe -- it is
# not a throwaway value invented for the check, it is the actual deliverable
# SDD-AC-1 asks for, carrying a nonce inside `note` so the read-back can
# confirm THIS run's write landed, not some earlier one's.
#
# STATES THIS SCRIPT MUST TELL APART (see the file's own tests for the
# assertions that pin each one):
#   - recording off                    -> say so; absence is not a fault
#   - recording on, nothing logged yet -> say so; empty is not "not recording"
#   - recording on, has prior entries  -> report the last-write time as
#                                          information, not as a verdict
#   - recording on, directory unwritable -> say it cannot record; never claim
#                                            it can just because the directory
#                                            or the writer returned 0
#
# "nothing logged yet" / "has prior entries" is judged from the log's state
# BEFORE this run's own probe write -- so running selfcheck twice in a row
# does not turn "nothing logged yet" into "has entries" merely because the
# first invocation left its own record behind. The probe write happens either
# way (it is this run's own state record); only the REPORTED verdict looks at
# what existed a moment earlier.
#
# Conventions inherited from logwrite.sh (which this file sources), same as
# every adapter in this spec:
#   - Pure bash 3.2: no `declare -A`, no `mapfile` (CON-1).
#   - No `set -u`: the reasoning in log_skill.sh's header applies verbatim --
#     this script is EXECUTED as its own process, not sourced, so `local`
#     scoping buys nothing, and `set -u` turns a stray unbound reference into
#     exactly the kind of loud, non-zero failure a diagnostic tool must not
#     inflict on itself while trying to report calmly.
#   - LC_ALL=C is not re-exported here: logwrite.sh exports it, and nothing
#     this script does before sourcing it is locale-sensitive.
#   - logwrite.sh is sourced by path relative to THIS file (not
#     CLAUDE_PLUGIN_ROOT), for the same reason the three adapters do: a
#     script invoked by hand, or from a repo's own .claude/settings.json, has
#     no guarantee that variable is set.

_selfcheck_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _selfcheck_dir=""
if [ -z "$_selfcheck_dir" ] || ! . "$_selfcheck_dir/logwrite.sh" 2>/dev/null; then
  printf 'observability selfcheck: could not load logwrite.sh -- nothing to report\n'
  exit 1
fi

# ---------------------------------------------------------------------------
# Portable file line count; 0 if the file is missing or empty. Forks `wc`,
# which is fine here -- this is an on-demand diagnostic, not a hot hook path
# (CON-7 does not bind this file).
# ---------------------------------------------------------------------------
_selfcheck_line_count() {
  local f="$1" n
  [ -f "$f" ] || { printf '0'; return 0; }
  n="$(wc -l <"$f" 2>/dev/null)" || n=0
  n="${n//[[:space:]]/}"
  case "$n" in
    ''|*[!0-9]*) printf '0' ;;
    *) printf '%s' "$n" ;;
  esac
}

# The `ts` field of a JSONL file's last line, or empty if there is no last
# line or it carries none. Reuses the writer's own field extractor rather
# than a second hand-rolled parser.
_selfcheck_last_ts() {
  local f="$1" last
  [ -f "$f" ] || { printf ''; return 0; }
  last="$(tail -n 1 "$f" 2>/dev/null)" || last=""
  [ -n "$last" ] || { printf ''; return 0; }
  _observability_field "$last" ts
}

_enabled=0
[ "${CLAUDE_OBSERVABILITY_ENABLED:-}" = "1" ] && _enabled=1

_detail=0
if _observability_detail_enabled; then _detail=1; fi

# Resolve the record path. _observability_data_dir does no filesystem writes
# of its own (no mkdir) -- it only computes a string -- so calling it here,
# even while recording is off, cannot be the side effect test 1 forbids.
_toplevel="$(git rev-parse --show-toplevel 2>/dev/null)" || _toplevel=""
_data_dir="$(_observability_data_dir "$_toplevel" 2>/dev/null)" || _data_dir=""
if [ -z "$_data_dir" ]; then
  # Outside a git repository: same $PWD-basename fallback _observability_write
  # itself falls back to, so the path reported here is the path a real write
  # would actually use.
  _data_dir="$HOME/.claude/plugins/data/observability-${PWD##*/}"
fi
_events_dir="$_data_dir/observability"
_events_file="$_events_dir/events.jsonl"

printf 'enabled: %s\n' "$([ "$_enabled" -eq 1 ] && printf yes || printf no)"
printf 'detail: %s\n' "$([ "$_detail" -eq 1 ] && printf yes || printf no)"
printf 'record path: %s\n' "$_events_file"

if [ "$_enabled" -ne 1 ]; then
  # Off is a choice, not a fault -- say so plainly and stop. No mkdir, no
  # stat, no probe write: nothing below this line has run, so nothing below
  # this line can have created anything.
  printf 'status: not recording (CLAUDE_OBSERVABILITY_ENABLED is unset)\n'
  exit 0
fi

# Snapshot what existed BEFORE this run's own probe write, so the verdict
# below describes genuine prior activity, not this check's own footprint.
_pre_count="$(_selfcheck_line_count "$_events_file")"
_pre_last_ts="$(_selfcheck_last_ts "$_events_file")"

# The round-trip probe. A nonce makes the read-back specific to THIS run's
# write, not merely "a line exists" (which could be true from an unrelated
# concurrent writer, or a stale entry left by an earlier selfcheck run).
_nonce="selfcheck-$$-${RANDOM:-0}-${RANDOM:-0}"
_observability_write kind=state \
  enabled="$_enabled" \
  detail="$_detail" \
  note="selfcheck probe $_nonce"

_round_trip_ok=0
if [ -f "$_events_file" ] && grep -qF -- "$_nonce" "$_events_file" 2>/dev/null; then
  _round_trip_ok=1
fi

if [ "$_round_trip_ok" -ne 1 ]; then
  # The writer returned 0 regardless (CON-5) -- that tells us nothing. The
  # read-back is what tells us the write never actually landed.
  printf 'status: cannot record -- wrote a probe record and could not read it back from %s (directory likely unwritable)\n' "$_events_file"
  printf 'entries: %s\n' "$_pre_count"
  exit 1
fi

if [ "$_pre_count" -eq 0 ]; then
  printf 'status: recording -- nothing had been logged before this check (probe write confirmed by round-trip)\n'
else
  printf 'status: recording (probe write confirmed by round-trip)\n'
  printf 'last write before this check: %s\n' "$_pre_last_ts"
fi
printf 'entries: %s\n' "$(_selfcheck_line_count "$_events_file")"

exit 0
