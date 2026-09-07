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

set -uo pipefail

_log_skill_main() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)" || return 0
  # shellcheck source=./logwrite.sh
  . "$script_dir/logwrite.sh" 2>/dev/null || return 0

  # Slurp stdin once, fork-free (CON-7): `read -d ''` reads to EOF and
  # reports non-zero when no NUL delimiter was found, which is always, for
  # a JSON payload — the `|| true` is what makes that expected outcome, not
  # a real failure.
  local payload=""
  IFS= read -r -d '' payload || true

  local tool_name=""
  tool_name="$(_observability_field "$payload" tool_name)" || tool_name=""
  [ "$tool_name" = "Skill" ] || return 0

  local session_id="" skill_name=""
  session_id="$(_observability_field "$payload" session_id)" || session_id=""
  skill_name="$(_observability_field "$payload" "$_OBSERVABILITY_SKILL_KEY")" || skill_name=""

  _observability_write kind=skill session="$session_id" skill="$skill_name"
  return 0
}

_log_skill_main
exit 0
