#!/usr/bin/env bash
#
# docs/XDD/specs/018-observability-load-and-fire-log/gate-t36.sh
#
# The two T3.6 gates that cannot run in the session that prepares them:
# SDD-AC-17 (a hook duration from the real harness path) and SDD-AC-5's
# session caveat (does $CLAUDE_CODE_SESSION_ID reach a harness-spawned hook,
# and does its value equal the payload's session_id).
#
# WHY THIS IS A COMMITTED SCRIPT AND NOT A LIST OF COMMANDS IN A NOTE:
# T3.6's own evidence map closed SDD-AC-20 as un-reproducible, because the
# T1.4 spike's artifacts lived in a /tmp scratchpad that no longer exists --
# in a different uid namespace, from a container. The gate that replaces a
# handwritten checklist should not repeat that mistake, so it lives in the
# spec directory next to the criteria it checks.
#
# PRECONDITIONS
#   1. timed-wrapper.sh is registered on InstructionsLoaded in
#      .claude/settings.json (see plan/phase-3.md, 2026-09-08 block).
#   2. This session was LAUNCHED as: CLAUDE_OBSERVABILITY_ENABLED=1 claude
#      Recording is read from the launch environment; it cannot be switched
#      on mid-session, and a hook registration cannot be changed mid-session
#      either. Both are why this needs its own session at all.
#
# Reports; never asserts. A blank result is itself an answer here (see the
# session-caveat section), so an exit status would have to lie about one of
# the two outcomes.

set -u

REC="${CLAUDE_OBSERVABILITY_DATA:-$HOME/.claude/plugins/data/observability-the-custom-startup}"
case "$REC" in
  */observability) EVENTS="$REC/events.jsonl" ;;
  *)               EVENTS="$REC/observability/events.jsonl" ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO_ROOT="."

printf 'record: %s\n' "$EVENTS"
if [ ! -f "$EVENTS" ]; then
  printf '\nNo record file. Either recording was not enabled at launch, or nothing has\n'
  printf 'been recorded yet. Run selfcheck.sh (with the Bash sandbox DISABLED -- it denies\n'
  printf 'writes under ~/.claude/plugins and reports a false "cannot record") before\n'
  printf 'concluding anything from this.\n'
  exit 0
fi
printf 'records: %s\n' "$(wc -l < "$EVENTS" | tr -d ' ')"

# ---------------------------------------------------------------------------
# SDD-AC-17 -- a hook record produced by the real harness hook path.
# ---------------------------------------------------------------------------
printf '\n=== SDD-AC-17: kind:hook records from the harness path ===\n'
hooks="$(jq -c 'select(.kind=="hook")' "$EVENTS" 2>/dev/null)"
if [ -z "$hooks" ]; then
  printf 'NONE. The wrapper is not registered, or this session predates the registration.\n'
  printf 'Check .claude/settings.json before reading this as a finding.\n'
else
  printf '%s\n' "$hooks"
  printf '\n-- as the report renders it --\n'
  python3 "$REPO_ROOT/scripts/observability/report.py" 2>/dev/null \
    | grep -A 8 'Hook durations' || printf '(report showed no hook-duration section)\n'
fi

# ---------------------------------------------------------------------------
# SDD-AC-5's session caveat. Two halves: does the variable REACH a
# harness-spawned hook, and does its VALUE equal the payload's session_id.
# ---------------------------------------------------------------------------
printf '\n=== SDD-AC-5: the session caveat ===\n'
hook_sessions="$(jq -r 'select(.kind=="hook") | .session' "$EVENTS" 2>/dev/null | sort -u)"
adapter_sessions="$(jq -r 'select(.kind=="instruction") | .session' "$EVENTS" 2>/dev/null | sort -u)"

printf 'hook records    (from $CLAUDE_CODE_SESSION_ID): %s\n' "${hook_sessions:-<none>}"
printf 'adapter records (from the payload)            : %s\n' "${adapter_sessions:-<none>}"

if [ -z "$hook_sessions" ]; then
  printf '\nVERDICT: cannot answer -- no hook records. See above.\n'
elif [ "$hook_sessions" = "" ] || printf '%s' "$hook_sessions" | grep -q '^$'; then
  printf '\nVERDICT: the variable does NOT reach a harness-spawned hook. That is a real\n'
  printf 'result, not a failure: the field is left empty rather than guessed, so a hook\n'
  printf 'record simply does not join across kinds instead of joining to the WRONG session.\n'
elif printf '%s' "$adapter_sessions" | grep -qxF "$hook_sessions"; then
  printf '\nVERDICT: CONFIRMED, both halves. The variable reaches a harness-spawned hook\n'
  printf 'and its value equals the payload-sourced id. The caveat can be lifted in\n'
  printf 'solution.md (SDD-AC-5 row and the record-shape comment) and in the scripts README.\n'
else
  printf '\nVERDICT: the variable reaches the hook but its value DIFFERS from the payload id.\n'
  printf 'This is the worst case and the reason the caveat existed: hook records would join\n'
  printf 'to nothing, silently. Record both values above before changing anything.\n'
fi

# ---------------------------------------------------------------------------
# The privacy gate's matcher scan, which was vacuous on 2026-09-08 because no
# kind:hook record existed yet. It has still never really run.
# ---------------------------------------------------------------------------
printf '\n=== Privacy gate: the matcher scan (never yet run non-vacuously) ===\n'
matchers="$(jq -r 'select(.kind=="hook") | .matcher' "$EVENTS" 2>/dev/null | sort -u)"
if [ -z "$matchers" ]; then
  printf '(still vacuous -- no hook records)\n'
else
  printf 'matcher values present:\n'
  printf '%s\n' "$matchers" | sed 's/^$/  <empty -- expected for InstructionsLoaded>/; s/^\([^ ]\)/  \1/'
  printf '\nRead these by eye: a matcher is operator-typed, so it is the one hook field that\n'
  printf 'could carry a command string. Anything resembling a command line is a gate FAILURE.\n'
fi

printf '\n=== Full emitted key set (read against solution.md Quality Requirements/Privacy) ===\n'
jq -r 'keys[]' "$EVENTS" 2>/dev/null | sort -u | tr '\n' ' '
printf '\n\nAfter recording the results above: REMOVE the wrapper from .claude/settings.json.\n'
printf '%s\n' "The PRD's Won't-Have list forbids a permanently installed timing layer,"
printf '%s\n' "switched off or not. The original command line is in plan/phase-3.md."
