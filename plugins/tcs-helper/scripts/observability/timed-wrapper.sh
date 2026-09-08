#!/usr/bin/env bash
#
# plugins/tcs-helper/scripts/observability/timed-wrapper.sh
#
# spec 018 (observability of what loads and fires), phase 3, T3.5: the
# per-hook attribution mechanism ADR-7 settled on. T1.4 (README, "the ADR-7
# verification spike") measured six hook configurations against the
# harness's own `hook_execution_complete` telemetry and found per-hook
# attribution NOT expressible as configuration: arrangement B registered two
# entries under two DISTINCT matcher strings and the harness still collapsed
# them into one measurement group (`num_hooks=2`); arrangement F showed
# hooks in a group run in PARALLEL, so subtraction cannot recover a single
# hook's duration from the group total either. The skip condition on this
# task ("if T1.4 found per-command matchers do produce separate measurement
# groups") does not apply -- this wrapper is the mechanism, not a fallback.
#
# USAGE (fixed CLI shape; nothing else parses hook identity):
#   timed-wrapper.sh --event <hook_event> --matcher <matcher> -- <cmd> [args...]
#
# This script is meant to be installed AS the hook command in place of the
# real one, e.g. in a repo's own (gitignored) .claude/settings.json:
#   ".../timed-wrapper.sh --event PreToolUse --matcher Skill -- /abs/path/to/real-hook.sh"
# It is a targeted-investigation tool (PRD F7, requirements.md's Won't-Have
# posture on Feature 6): installed for a deliberate measurement, then
# removed. It is never registered by default.
#
# ---------------------------------------------------------------------------
# HAZARD 1 -- never read stdin.
# ---------------------------------------------------------------------------
# A hook's JSON payload arrives on stdin. If this wrapper consumed any of it
# to discover the event name or anything else, every wrapped hook would get
# an empty payload -- silently, in every session, for as long as the
# wrapper stayed installed. `hook_event` and `matcher` therefore come ONLY
# from the --event/--matcher flags above; this file contains no `read`, no
# `cat` of stdin, nothing that touches file descriptor 0 at all. Stdin flows
# from this process's own stdin straight into the wrapped command's stdin,
# untouched, because neither `time "$@"` below nor the command substitution
# around it ever redirects fd 0.
#
# ---------------------------------------------------------------------------
# HAZARD 2 -- timing without polluting the hook protocol.
# ---------------------------------------------------------------------------
# CON-4: the harness parses a hook's STDOUT as JSON. CON-5: a hook's exit
# status (including exit 2, which BLOCKS the tool call) must never change
# because of a recording failure. The bash `time` builtin is the only timer
# ADR-5 measured near enough to the CON-7 budget (~0 ms extra, vs. `jq`'s
# ~21 ms and `date +%s%N`'s ~0.37 ms x2 AND its BSD/macOS breakage) -- but
# `time` writes its report to STDERR, which would otherwise land on the
# wrapped command's own stderr and corrupt it.
#
# The fix is fd juggling: duplicate the wrapper's real stdout/stderr onto
# fd 3/4, point the WRAPPED COMMAND's own stdout/stderr at those (1>&3
# 2>&4), and let `time`'s report -- which bypasses the command's own
# redirections entirely and is written by the shell itself -- fall through
# the group's `2>&1` into the command substitution that captures it. The
# wrapped command's real output never enters that pipe at all, so it stays
# byte-identical, binary content and trailing-newline behaviour included.
#
# ONE DEVIATION FROM THE OBVIOUS FORM, MEASURED, NOT ASSUMED: a form of
#     _t=$( { time "$@" 1>&3 2>&4; } 2>&1 ) 3>&1 4>&2
# -- redirections trailing the OUTER assignment -- looks like it should open
# fd 3/4 before the command substitution runs. It does not, on this bash
# (5.2.15): a bare `VAR=$(...)` is executed by expanding the right-hand side
# FIRST (word expansion, which is where the command substitution's subshell
# actually forks and runs) and only afterwards applying the assignment's own
# redirections -- so fd 3/4 are opened AFTER the subshell that would have
# used them has already finished, and "$@" inside sees "3: Bad file
# descriptor". Confirmed with `_t=$(echo x 1>&3) 3>&1`: fails with exactly
# that error. The form below instead opens fd 3/4 in THIS shell with a
# plain `exec` before the substitution runs (so they are real, already-open
# descriptors by the time the subshell inherits them), then closes them
# again with a second `exec` immediately after. Verified directly, including
# for exit 2: `_status=$?` read right after the assignment reports the
# WRAPPED COMMAND's own status in every case (0, 1, 2), because `time
# pipeline`'s own exit status IS the pipeline's exit status (bash manual),
# and the assignment's `$?` is the command substitution's exit status, which
# in turn is the exit status of the last command run inside it -- the
# `{ time ...; } 2>&1` group.
#
# Do NOT add `set -e` here: a hook exiting 2 is normal, correct behaviour
# (it BLOCKS the tool call, on purpose), and `set -e` would abort this
# script -- losing the record write and the correct exit propagation -- on
# exactly the case this wrapper exists to pass through faithfully.
#
# ---------------------------------------------------------------------------
# COST DISCIPLINE (CON-7, PRD F3 "off costs nothing")
# ---------------------------------------------------------------------------
# When recording is disabled, this script does not source logwrite.sh, does
# not set TIMEFORMAT, does not fork a subshell for `time`, and does not fork
# `git` -- it `exec`s the wrapped command directly, replacing this process's
# own image. That makes the disabled path AS CHEAP AS invoking the real hook
# directly (no wrapper fork at all survives), and it is why stdin/stdout/
# stderr/exit-status transparency in that path is not merely "close to
# identical" but structurally guaranteed: there is no wrapper process left
# to differ from the real hook in any way once `exec` has run.
#
# The same posture applies when logwrite.sh cannot be sourced (T3.5's Test
# list: "the wrapper still runs the hook correctly when logwrite.sh cannot
# be sourced at all") -- a wrapper that cannot log must still run the hook,
# so it falls back to the same `exec` path rather than attempting the timed
# form with nothing to write the result to.
#
# Only when recording is genuinely possible (enabled AND the writer loaded)
# does this script pay the cost of `time` + the fd juggling + one
# `_observability_write` call -- and even then, CON-5 applies: the write
# happens AFTER `_status` is captured, and this script's own `exit` uses
# that saved variable, never the write call's own (irrelevant, always-0)
# return status -- so nothing in the logging path can change what is
# finally returned, printed, or written to stderr.
#
# bash 3.2 / BSD userland (CON-1): no `${var,,}`, no associative arrays, no
# `printf '%()T'`. This file does not need bash 3.2's `[[ =~ ]]` at all
# (that construct's PCRE gaps -- \s, \b -- are a non-issue here), but the
# argument parser below still avoids it on principle, matching the rest of
# this spec's adapters.
#
# CON-3: LC_ALL=C must be exported BEFORE `time` ever formats a duration --
# a comma-decimal locale corrupts `TIMEFORMAT`'s output exactly the way this
# repo's own memory records for `printf '%.0f'`. logwrite.sh exports it, so
# sourcing that file (which happens before the timed run, never after) is
# what makes this true; the exec-only paths never format a number at all,
# so they do not need it.

_timed_wrapper_event=""
_timed_wrapper_matcher=""

while [ $# -gt 0 ]; do
  case "$1" in
    --event)
      # `shift 2` is a no-op in bash when only one positional parameter
      # remains (it leaves $@ untouched and returns non-zero, which this
      # loop does not otherwise check) -- so a `--event` with no following
      # value would leave $1 == "--event" forever and spin the loop. Detect
      # the missing value explicitly rather than defaulting it via
      # `${2:-}`, which is what let this hang in the first place: consume
      # the flag itself and stop, so the "nothing to run" check below (fail
      # open, CON-5) is what handles it -- never fall through to executing
      # the flag as if it were the command.
      [ $# -ge 2 ] || { shift; break; }
      _timed_wrapper_event="$2"
      shift 2
      ;;
    --matcher)
      # Same guard, same reasoning. Note `--matcher ""` (an explicit empty
      # string as $2) is the legitimate, expected case for real adapters and
      # must keep working: `$# -ge 2` is true there because the empty value
      # is still a positional parameter, so only a genuinely MISSING value
      # (flag is the last remaining arg) takes this branch.
      [ $# -ge 2 ] || { shift; break; }
      _timed_wrapper_matcher="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      # Anything unexpected before `--` is treated as the start of the
      # wrapped command, defensively -- this wrapper's job is to run that
      # command no matter how it was misconfigured, not to validate its own
      # invocation (CON-5's fail-open posture, applied to argv as well as
      # to stdin/stdout).
      break
      ;;
  esac
done

# Nothing to run: fail open by doing nothing and exiting 0 rather than
# hanging or erroring -- there is no hook here to be transparent to.
if [ $# -eq 0 ]; then
  exit 0
fi

# Disabled: the cheapest and most transparent path there is -- replace this
# process with the real hook entirely. See the COST DISCIPLINE note above.
if [ "${CLAUDE_OBSERVABILITY_ENABLED:-}" != "1" ]; then
  exec "$@"
fi

# Enabled, but can we actually log? Resolve this script's own directory
# (never CLAUDE_PLUGIN_ROOT -- a repo's own .claude/settings.json entry gets
# none at invocation time, matching every other adapter in this spec) and
# try to source the writer. Fail open on any failure of that resolution:
# a wrapper that cannot log must still run the hook, so this drops straight
# through to the same `exec` path the disabled branch uses.
_timed_wrapper_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _timed_wrapper_dir=""
if [ -z "$_timed_wrapper_dir" ] || ! . "$_timed_wrapper_dir/logwrite.sh" 2>/dev/null; then
  exec "$@"
fi

# Convert `time`'s TIMEFORMAT='%3R' output -- decimal SECONDS with EXACTLY
# three fraction digits, e.g. "0.504", "12.345", "0.000" -- into an integer
# MILLISECONDS string, e.g. "504", "12345", "0". The record's field is named
# `ms` (README, report.py both read it as milliseconds); writing raw `%3R`
# seconds straight into it understated every duration by 1000x -- a 500 ms
# hook read back as "0.5 ms", comfortably inside CON-7's 1 ms budget when it
# was 500x over it. Fixed here, in the wrapper, so the record on disk is
# honest and every reader (including a human looking at the raw JSON) sees
# the truth, rather than papering over it by having a reader multiply.
#
# Pure parameter expansion and arithmetic -- no awk/bc/python/date -- CON-7
# forbids a fork in the hook path. `10#` forces base-10 arithmetic so a
# leading zero (e.g. frac "004") is never misread as octal.
#
# Fails safe rather than fabricate: prints nothing and returns 1 for
# anything that is not EXACTLY `<digits>.<3 digits>` -- an empty/unset
# value, a comma-decimal value (CON-3 is supposed to prevent this upstream,
# but this function does not trust that and rejects it too), or any other
# unexpected `time` output. The caller below omits the `ms=` field entirely
# on failure rather than writing a wrong or fabricated number -- this
# phase's established "absent, never fabricated" posture (T2.1's dropped
# default, `bytes`/`reason` in log_instructions.sh), and report.py already
# treats a record with no `ms` key as unmeasurable, never as zero.
_timed_wrapper_secs_to_ms() {
  local secs="$1" int frac

  case "$secs" in
    *[!0-9.]*) return 1 ;;   # anything other than a digit or a dot
  esac
  case "$secs" in
    *.*) ;;                  # must contain exactly the one decimal point
    *) return 1 ;;
  esac

  int="${secs%%.*}"
  frac="${secs#*.}"

  case "$frac" in
    [0-9][0-9][0-9]) ;;      # exactly 3 digits -- %3R's own guarantee; also
                             # rejects a second dot (leaves a non-digit char
                             # here) and anything %3R would never produce
    *) return 1 ;;
  esac
  case "$int" in
    ''|*[!0-9]*) return 1 ;;
  esac

  echo "$(( 10#$int * 1000 + 10#$frac ))"
}

# From here on, LC_ALL=C is in effect (logwrite.sh exports it above) --
# before TIMEFORMAT is ever used to format anything (CON-3).
TIMEFORMAT='%3R'

# Open fd 3/4 as private duplicates of THIS shell's real stdout/stderr
# before the command substitution below ever forks, so the wrapped
# command's own output -- redirected inside that subshell to 1>&3 2>&4 --
# reaches real, already-open descriptors rather than ones that do not exist
# yet (see the header comment's measured explanation of why the more
# obvious trailing-redirection form does not work here).
exec 3>&1 4>&2
_timed_wrapper_secs=$( { time "$@" 1>&3 2>&4; } 2>&1 )
_timed_wrapper_status=$?
exec 3>&- 4>&-

_timed_wrapper_ms="$(_timed_wrapper_secs_to_ms "$_timed_wrapper_secs")" || _timed_wrapper_ms=""

# CON-5: the write happens strictly AFTER the status above was captured,
# and this script's own `exit` (bottom of file) uses that saved variable,
# never anything this call might itself return -- so nothing in the
# logging path, including a total failure to write, can change what is
# finally returned. `_observability_write` is fail-open by its own contract
# (logwrite.sh) and never touches stdout or stderr either.
#
# SESSION CAVEAT (SDD-AC-5, T3.5): the `session` field is taken from
# $CLAUDE_CODE_SESSION_ID, an environment variable set by the harness.
# UNVERIFIED: that this variable reaches a harness-spawned hook (memory
# records CLAUDE_PLUGIN_ROOT does NOT; CLAUDECODE does — propagation is
# variable), and that its value equals the payload's session_id. Both are
# confirmed in T3.6 against a live session. When unset, field is empty.
_timed_wrapper_args=(
  kind=hook
  hook_event="$_timed_wrapper_event"
  matcher="$_timed_wrapper_matcher"
  session="${CLAUDE_CODE_SESSION_ID:-}"
)
# `ms` is omitted entirely -- never written as an empty string or a
# fabricated 0 -- when `_timed_wrapper_secs_to_ms` above could not parse
# `time`'s own output. Same "absent, never fabricated" posture `bytes` and
# `reason` already follow in log_instructions.sh; report.py's `_parse_ms`
# already treats a record with no `ms` key as unmeasurable.
if [ -n "$_timed_wrapper_ms" ]; then
  _timed_wrapper_args[${#_timed_wrapper_args[@]}]="ms=$_timed_wrapper_ms"
fi
_timed_wrapper_args[${#_timed_wrapper_args[@]}]="exit=$_timed_wrapper_status"
_timed_wrapper_args[${#_timed_wrapper_args[@]}]="scope_note=single"

_observability_write "${_timed_wrapper_args[@]}"

exit "$_timed_wrapper_status"
