#!/usr/bin/env bash
#
# plugins/tcs-helper/scripts/observability/log_skill.sh
#
# spec 018 (observability of what loads and fires), phase 2, T2.2:
# `PreToolUse` (matcher: `Skill`) adapter. Registered as a hook in
# `.claude/settings.json` (a separate task's file — not touched here). Reads
# the hook payload once from stdin and, only when the payload really is a
# `Skill` tool call, asks `logwrite.sh` to append one `kind: skill` record
# naming the skill (SDD-AC-16, PRD F5).
#
# Record shape for `kind = skill` (SDD/Application Data Models):
#   skill: string   # from tool_input
# on top of the four frozen fields (ts, kind, session, repo) that
# `_observability_write` always computes itself.
#
# THE KEY INSIDE tool_input — VERIFICATION STATUS
# ------------------------------------------------
# The SDD names the mechanism ("extracting the skill name from tool_input")
# but not the key. This was checked against evidence, not guessed: real
# session transcripts on this machine (~/.claude/projects/*/*.jsonl) contain
# dozens of `Skill` tool_use blocks across many unrelated repos, and every
# one has the same shape —
#   {"type":"tool_use","name":"Skill","input":{"skill":"<name>"[,"args":"..."]}}
# e.g. {"skill":"tcs-helper:context-bridge"},
#      {"skill":"tcs-workflow:xdd-prd"},
#      {"skill":"tcs-helper:skill-author","args":"..."}.
# A transcript's `tool_use.input` is the same object the harness sends as a
# `PreToolUse` hook's `tool_input` — both are documented as "the input the
# tool call carries" — so KEY = "skill" is treated here as CONFIRMED BY
# TRANSCRIPT EVIDENCE, not an unverified guess. It is still named as a
# constant below, not inlined, so a T2.4 run against a real session (which
# checks the actual hook payload directly, rather than the transcript's
# tool_use record) has exactly one line to correct if that direct check
# ever disagrees.
_OBSERVABILITY_SKILL_KEY="skill"

# Extraction reads the WHOLE raw payload, never a separately-extracted
# tool_input substring. SDD/Known Technical Issues is explicit that this
# adapter "extracts only the scalar it needs" from the nested object via the
# same flat string scan `_observability_field` already does everywhere else
# — it matches the first `"skill":"..."` byte sequence anywhere in the
# payload, nested or not, which is sufficient here because nothing else in
# a Skill payload is expected to carry a field literally named `skill`.
# Isolating `tool_input` first is not a step this adapter needs: a call
# `_observability_field "$payload" tool_input` would look for the literal
# sequence `"tool_input":"` (quote-delimited), which never matches a nested
# JSON OBJECT value — that call always yields empty, by construction, not by
# accident. Never extend this to walk the object (phase-2 Key Decisions;
# SDD/Known Technical Issues) — a real parser belongs offline, not here.
#
# CON-4/CON-5: this script writes nothing to stdout or stderr and always
# exits 0 — a hook's stdout is parsed as JSON (CON-4), and a hook's exit
# status must never change because recording failed, was skipped, or the
# payload was malformed (CON-5).
#
# bash 3.2 / BSD userland (CON-1); see logwrite.sh's header for the full
# list of constraints this file inherits by sourcing it.
#
# LC_ALL=C is not re-exported here: logwrite.sh exports it, and nothing this
# script does before sourcing it is locale-sensitive. See log_instructions.sh
# for the full reasoning — all three adapters follow the same rule.
#
# STRUCTURE: a flat top-level script, matching log_instructions.sh and
# log_agent.sh. This file previously wrapped its body in a function under
# `set -uo pipefail`. That is dropped deliberately, not for uniformity's own
# sake: `set -u` makes any unbound-variable reference exit the shell
# NON-ZERO with a message on stderr, which is precisely the pair of things
# CON-4/CON-5 say a hook adapter must never do — the very failure mode the
# `|| ...` guard on every line below exists to prevent. Without it an
# unbound name expands to empty, the guards absorb it, and the script still
# reaches `exit 0`. The function wrapper bought `local` scoping, which is
# worth nothing in a script that is EXECUTED as its own process rather than
# sourced.

_log_skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)" || _log_skill_dir=""
# shellcheck source=./logwrite.sh
if [ -z "$_log_skill_dir" ] || ! . "$_log_skill_dir/logwrite.sh" 2>/dev/null; then
  # Cannot even load the writer: nothing to record with, but this must still
  # never fail loudly (CON-4/CON-5) — drain stdin first so the harness's own
  # write of the payload never lands on a closed pipe, then get out of the
  # way. The drain is a `cat` fork, but only on this already-broken path;
  # the success path below stays fork-free.
  cat >/dev/null 2>&1
  exit 0
fi

# Slurp stdin once, fork-free (CON-7): `read -d ''` reads to EOF and
# reports non-zero when no NUL delimiter was found, which is always, for
# a JSON payload — the `|| true` is what makes that expected outcome, not
# a real failure.
_payload=""
IFS= read -r -d '' _payload || true

_tool_name="$(_observability_field "$_payload" tool_name)" || _tool_name=""
[ "$_tool_name" = "Skill" ] || exit 0

_session_id="$(_observability_field "$_payload" session_id)" || _session_id=""
_skill_name="$(_observability_field "$_payload" "$_OBSERVABILITY_SKILL_KEY")" || _skill_name=""

# No `_observability_toplevel=` pair here. This adapter redacts no paths, so
# it has no toplevel of its own to thread through — resolving one just to
# hand it over would ADD the fork the reserved pair exists to remove. Letting
# the writer resolve it keeps the count at exactly one per record.
_observability_write kind=skill session="$_session_id" skill="$_skill_name"

exit 0
