#!/usr/bin/env bash
#
# plugins/tcs-helper/scripts/observability/log_agent.sh
#
# spec 018 (observability of what loads and fires), T2.3: the SubagentStart
# adapter. Phase 1 established from the shipped CLI binary that
# `claude_code.subagent.spawn` telemetry is dead code (its only guard,
# `vj()`, is hard-coded `false`). This hook payload is therefore the ONLY
# place agent identity can come from -- there is no fallback and nothing to
# cross-check against (see docs/XDD/specs/018-.../plan/phase-2.md, T2.3).
#
# Scope: read a SubagentStart hook payload from stdin, extract agent
# identity and parentage, and call the writer once. Nothing else belongs
# here -- SDD/Solution Strategy: "adapters are thin by contract: read stdin
# once, extract two or three scalars, call the writer."
#
# Conventions inherited from logwrite.sh (which this file sources):
#   - Pure bash 3.2: no `declare -A`, no `mapfile`, no `${var^^}` (CON-1).
#   - CON-5: this script's own exit status is always 0 -- a hook adapter
#     invoked by a `set -euo pipefail` caller must never abort it, and its
#     own stdout must stay empty (CON-4: a hook's stdout is parsed as JSON).
#   - CON-7: `_observability_write` already forks `git rev-parse` (and
#     `date`) once per record; this adapter adds no fork of its own -- its
#     own stdin read is fork-free (see below). It deliberately does NOT pass
#     the writer's reserved `_observability_toplevel=` pair: this adapter
#     redacts no paths and so has no toplevel of its own, and resolving one
#     just to hand it over would ADD the fork that pair exists to remove.
#     Letting the writer resolve it keeps the count at exactly one.
#   - LC_ALL=C is not re-exported here: logwrite.sh exports it, and nothing
#     this script does before sourcing it is locale-sensitive. See
#     log_instructions.sh for the reasoning; all three adapters share it.
#
# ---------------------------------------------------------------------------
# PAYLOAD KEYS -- verification status, read this before touching them.
#
# AGENT_PAYLOAD_KEY_TYPE ("agent_type") and AGENT_PAYLOAD_KEY_ID ("agent_id")
# are CONFIRMED against the official Claude Code hooks documentation
# (https://code.claude.com/docs/en/hooks, checked 2026-09-07 via WebFetch,
# since the 7-day-cached copy in docs/ai/external/claude/hooks.md predates
# this hook event and does not mention it at all). The docs state: "When
# running with --agent or inside a subagent, two additional fields are
# included: `agent_id`: Unique identifier for the subagent ... `agent_type`:
# Agent name (for example, "Explore" or "security-reviewer")". This matches
# the SDD's own Interface Specifications field list for SubagentStart
# (`fields: [session_id, cwd, agent_id, agent_type]`).
#
# There is no parent-agent field, at T2.4 confirmed unobtainable rather than
# merely undocumented -- three independent lines agree: (1) the shipped CLI
# binary's only `parent_agent_id` string sits inside
# `claude_code.subagent.spawn`, telemetry T1.4 already proved dead
# (`vj()` hard-coded `false`); (2) the official hooks docs list only
# `agent_id`/`agent_type` for a subagent, identifying the CURRENT agent
# only; (3) a real nested dispatch, captured live (a `general-purpose`
# subagent that itself dispatched an `Explore` subagent five seconds
# later), produced a `SubagentStart` payload for the nested one with no
# parent-shaped field at all. Nested dispatches are therefore linked by
# `session` plus timestamp ordering in the record, not by a parent field --
# there is nothing to extract.
# ---------------------------------------------------------------------------
AGENT_PAYLOAD_KEY_TYPE="agent_type"
AGENT_PAYLOAD_KEY_ID="agent_id"

_LOG_AGENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _LOG_AGENT_SCRIPT_DIR=""
# shellcheck disable=SC1091
if [ -z "$_LOG_AGENT_SCRIPT_DIR" ] || ! . "$_LOG_AGENT_SCRIPT_DIR/logwrite.sh" 2>/dev/null; then
  # Cannot even load the writer: nothing to record with, but this must still
  # never fail loudly (CON-4/CON-5) -- drain stdin first so the harness's own
  # write of the payload never lands on a closed pipe, then get out of the
  # way. The drain is a `cat` fork, but only on this already-broken path;
  # the success path below stays fork-free. Same form in all three adapters.
  cat >/dev/null 2>&1
  exit 0
fi

# Read the whole hook payload in one shot, fork-free (CON-7): `read -d ''`
# reads to EOF and reports non-zero when no NUL delimiter was found, which
# is always, for a JSON payload -- the `|| true` is what makes that expected
# outcome, not a real failure. Matches log_skill.sh's own stdin read
# exactly. (Corrects an earlier version of this comment, which forked
# `cat` here on the mistaken claim that bash 3.2's `read` builtin can only
# read stdin one line at a time -- `read -r -d ''` reads the whole stream
# regardless of embedded newlines, so that fork was never necessary.)
_payload=""
IFS= read -r -d '' _payload || true

_session_id="$(_observability_field "$_payload" session_id)" || _session_id=""
_agent_type="$(_observability_field "$_payload" "$AGENT_PAYLOAD_KEY_TYPE")" || _agent_type=""
_agent_id="$(_observability_field "$_payload" "$AGENT_PAYLOAD_KEY_ID")" || _agent_id=""

# agent_type and agent_id are the record's required fields (SDD/Application
# Data Models: both plain `string`, no `?`) -- always passed through, even
# empty, so a payload missing one still yields a well-formed record rather
# than no record at all. There is no parent field to extract (see the
# header comment above) -- nested dispatches are linked by session plus
# timestamp ordering, not by a parent_agent field in the record.
_observability_write kind=agent session="$_session_id" \
  agent_type="$_agent_type" agent_id="$_agent_id" || true

exit 0
