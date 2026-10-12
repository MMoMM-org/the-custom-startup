#!/bin/bash
#
# scripts/observability/e2e_probe.sh
#
# Spec 021 (observability v2), T5.2: an end-to-end probe of the recorder
# against REAL headless Claude Code sessions, not against hand-written
# payloads. The unit suites prove what each adapter does with the payload
# shape we believe the harness sends; only a real session proves the harness
# still sends it, that the registration `setup.sh install` writes actually
# fires, and that what lands in events.jsonl is what the report reads.
#
# Usage:  scripts/observability/e2e_probe.sh [--keep]
#   --keep   leave the scratch directory in place and print its path
#   env CLAUDE_BIN    the claude executable (default: `command -v claude`)
#   env PROBE_MODEL   the model for every run (default: haiku, the cheapest)
#
# Exit: 0 every check passed; 1 a check failed; 2 a precondition failed
# (missing tool, install refused); 3 `claude` could not run or authenticate
# (NEEDS_CONTEXT: nothing here works around auth).
#
# WHAT IT NEVER TOUCHES. The real $HOME is used only so `claude` finds its
# auth and installed plugins. The bundle goes into a scratch home through
# `setup.sh install --home`, and because that registration names the literal
# "$HOME/.claude/observability/..." (ADR-2), which at run time would resolve to
# the REAL home's bundle, the scratch repo's commands are rewritten to the
# scratch bundle's absolute paths (README, "Registering the hooks": a plain
# absolute path is a valid registration) and checked afterwards. Records go to
# a scratch CLAUDE_OBSERVABILITY_DATA; recording is switched on by the env
# block `install` writes into the scratch repo's settings.local.json, as the
# README documents. Everything lives under one `mktemp -d`, removed on exit.
#
# Four headless runs (`claude -p`), run from inside the scratch repo:
#   R1 typed     `/tcs-workflow:verify check nothing <nonce>`        F1 AC1/AC3
#   R2 unknown   `/nonexistent-skill`                                F1 AC4
#   R3 main      Skill tool, git stash, git stash pop, override reset --hard
#   R4 dispatch  a named and an unnamed general-purpose subagent, each running
#                `git status` and `git commit --allow-empty -m <msg>`
# The commit message carries a nonce instead of the task text's literal "x":
# a one-letter message cannot be searched for in the privacy scan.
#
# Model behaviour is not deterministic: a model may retry a command, so the
# checks accept extra records of the asserted shape, never a wrong field.
#
# bash 3.2 compatible; no runtime dependency beyond claude, jq, git, python3.

set -uo pipefail

_PROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_PROBE_DIR/../.." && pwd)"
_SETUP_SH="$_REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/setup.sh"
_REPORT_PY="$_PROBE_DIR/report.py"
MODEL="${PROBE_MODEL:-haiku}"
KEEP=0
FAILURES=0
RUNS=0

_say() { printf '%s\n' "$*"; }
_die() { _say "ABORT: $2" >&2; exit "$1"; }

# _check <name> <0|1> [evidence...]  records one verdict and prints the
# evidence lines (record lines, report lines) under it either way.
_check() {
  local name="$1" ok="$2"; shift 2
  if [ "$ok" = "0" ]; then _say "PASS  $name"; else _say "FAIL  $name"; FAILURES=$((FAILURES + 1)); fi
  local arg line
  for arg in "$@"; do
    while IFS= read -r line; do
      [ -n "$line" ] && printf '        %s\n' "$line"
    done <<EOF
$arg
EOF
  done
  return 0
}

_parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --keep) KEEP=1 ;;
      -h|--help) sed -n '13,18p' "${BASH_SOURCE[0]}"; exit 0 ;;
      *) _die 2 "unknown argument: $1" ;;
    esac
    shift
  done
}

_preflight() {
  local tool
  CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || true)}"
  [ -x "$CLAUDE_BIN" ] || _die 2 "claude not found (set CLAUDE_BIN)"
  for tool in jq git python3; do
    command -v "$tool" >/dev/null 2>&1 || _die 2 "$tool not found"
  done
  [ -r "$_SETUP_SH" ] || _die 2 "cannot read $_SETUP_SH"
  [ -r "$_REPORT_PY" ] || _die 2 "cannot read $_REPORT_PY"
}

_cleanup() {
  [ -n "${SCRATCH:-}" ] && [ -d "$SCRATCH" ] || return 0
  if [ "$KEEP" = "1" ]; then _say "Scratch kept at: $SCRATCH"; return 0; fi
  rm -rf "$SCRATCH"
}

# --- scratch state ----------------------------------------------------------

_make_scratch() {
  SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/obs-e2e.XXXXXX")" || _die 2 "mktemp failed"
  trap _cleanup EXIT
  SCRATCH_REAL="$(cd -P "$SCRATCH" && pwd)"
  NONCE="n${RANDOM}${RANDOM}x$$"
  # A unique basename, so the real data dir it would map to is ours alone.
  REPO="$SCRATCH/obs-e2e-repo-${SCRATCH##*.}"
  S_HOME="$SCRATCH/home"
  DATA="$SCRATCH/data"
  EVENTS="$DATA/observability/events.jsonl"
  REAL_DATA="$HOME/.claude/plugins/data/observability-${REPO##*/}"
  mkdir -p "$REPO" "$S_HOME" "$DATA" "$SCRATCH/prompts" || _die 2 "cannot create scratch tree"
  : >"$SCRATCH/start.stamp"
}

_make_repo() {
  git -C "$REPO" -c init.defaultBranch=probe init -q || _die 2 "git init failed"
  git -C "$REPO" config user.name "e2e probe"
  git -C "$REPO" config user.email "e2e-probe@example.invalid"
  printf '%s\n' '.claude/settings.local.json*' '.claude/*.lock' '.claude/*.bak' >"$REPO/.gitignore"
  printf 'one\n' >"$REPO/tracked.txt"
  git -C "$REPO" add .gitignore tracked.txt || _die 2 "git add failed"
  git -C "$REPO" commit -q -m init || _die 2 "initial commit failed"
  # Dirty, so `git stash` has something to stash and `stash pop` succeeds.
  printf 'two\n' >"$REPO/tracked.txt"
}

_install_bundle() {
  if ! bash "$_SETUP_SH" install --target "$REPO" --home "$S_HOME" --yes >"$SCRATCH/install.log" 2>&1; then
    cat "$SCRATCH/install.log" >&2
    _die 2 "setup.sh install failed"
  fi
  grep -q 'ADDED:' "$SCRATCH/install.log" || { cat "$SCRATCH/install.log" >&2; _die 2 "install registered nothing"; }
}

# _repoint_registration  rewrites "$HOME/.claude/observability/<script>" to
# the scratch bundle's absolute path, keeping the file's owner-only mode.
_repoint_registration() {
  local settings="$REPO/.claude/settings.local.json" bundle="$S_HOME/.claude/observability"
  local rewritten
  rewritten="$(jq --arg b "$bundle" '.hooks |= with_entries(.value |= map(.hooks |= map(
      .command |= sub("\\$HOME/\\.claude/observability"; $b))))' "$settings")" || _die 2 "cannot rewrite $settings"
  printf '%s\n' "$rewritten" >"$settings"
}

_check_registration() {
  local settings="$REPO/.claude/settings.local.json" bundle="$S_HOME/.claude/observability"
  local cmds outside enabled
  cmds="$(jq -r '.hooks[][].hooks[].command' "$settings")"
  outside="$(printf '%s\n' "$cmds" | grep -v "^\"$bundle/" || true)"
  enabled="$(jq -r '.env.CLAUDE_OBSERVABILITY_ENABLED // ""' "$settings")"
  [ -z "$outside" ] && [ "$(printf '%s\n' "$cmds" | wc -l | tr -d ' ')" = "4" ]
  rc=$?; _check "registration: all 4 commands point into the scratch home" "$rc" "$cmds"
  [ "$enabled" = "1" ]
  rc=$?; _check "registration: env CLAUDE_OBSERVABILITY_ENABLED=1 from install" "$rc"
  [ -z "$outside" ] || _die 2 "a registered command points outside the scratch home; not running claude"
}

# --- headless runs ----------------------------------------------------------

# _run <label> <prompt-file> [claude args...]  sets SID to the run's session.
# A run that yields no session id is an environment problem (network,
# keychain, auth), reported as NEEDS_CONTEXT with claude's own words.
_run() {
  local label="$1" prompt="$2" out; shift 2
  RUNS=$((RUNS + 1))
  out="$(cd "$REPO" && env -u CLAUDE_OBSERVABILITY_ENABLED -u CLAUDE_OBSERVABILITY_DETAIL \
      -u CLAUDE_PROJECT_DIR CLAUDE_OBSERVABILITY_DATA="$DATA" \
      "$CLAUDE_BIN" -p --model "$MODEL" --output-format json "$@" <"$prompt" 2>"$SCRATCH/$label.err")"
  printf '%s\n' "$out" >"$SCRATCH/$label.out"
  SID="$(printf '%s' "$out" | jq -r '.session_id // empty' 2>/dev/null)"
  if [ -z "$SID" ]; then
    _say "NEEDS_CONTEXT: claude run $label produced no session. stdout/stderr:" >&2
    cat "$SCRATCH/$label.out" "$SCRATCH/$label.err" >&2
    exit 3
  fi
  _say "run $label: session $SID ($(printf '%s' "$out" | jq -r '.subtype // "?"'))"
}

_write_prompts() {
  local p="$SCRATCH/prompts" msg="probe-msg-$NONCE"
  printf '/tcs-workflow:verify check nothing %s\n' "$NONCE" >"$p/r1"
  printf '/nonexistent-skill\n' >"$p/r2"
  cat >"$p/r3" <<EOF
Automated observability test $NONCE. Do exactly these steps in order, one tool call each, nothing else:
1. Call the Skill tool with skill "tcs-workflow:verify" and no args. When it returns, do NOT follow its instructions; go straight to step 2.
2. Use the Bash tool to run exactly: git stash
3. Use the Bash tool to run exactly: git stash pop
4. Use the Bash tool to run exactly: CLAUDE_ALLOW_RESET_HARD=1 git reset --hard
Then reply with the single word finished.
EOF
  cat >"$p/r4" <<EOF
Automated observability test $NONCE. Use the Agent tool exactly twice, both calls in one single message, with these exact parameters:
Call 1: subagent_type "general-purpose", name "probe-named", description "probe named", prompt "Use the Bash tool to run exactly \`git status\`, then use the Bash tool to run exactly \`git commit --allow-empty -m "$msg"\`. Run nothing else. Then reply with the single word done."
Call 2: subagent_type "general-purpose", no name parameter at all, description "probe unnamed", prompt identical to call 1.
Do not run any tool yourself other than these two Agent calls. When both return, reply with the single word finished.
EOF
}

_run_all() {
  _write_prompts
  local p="$SCRATCH/prompts" no_tools=(--max-turns 1 --disallowedTools Bash Skill Agent)
  _run r1 "$p/r1" "${no_tools[@]}"; SID_R1="$SID"
  _run r2 "$p/r2" "${no_tools[@]}"; SID_R2="$SID"
  _run r3 "$p/r3" --allowedTools Skill "Bash(git stash)" "Bash(git stash pop)" \
    "Bash(CLAUDE_ALLOW_RESET_HARD=1 git reset --hard)"; SID_R3="$SID"
  _run r4 "$p/r4" --allowedTools Agent "Bash(git status)" "Bash(git commit *)"; SID_R4="$SID"
}

# --- record checks ----------------------------------------------------------

# _recs <session> <jq-select>  prints the matching records, one per line.
_recs() { jq -c --arg s "$1" "select(.session == \$s) | select($2)" "$EVENTS" 2>/dev/null; }
_count() { _recs "$1" "$2" | grep -c . ; }

_check_typed() {
  local typed bad
  typed="$(_recs "$SID_R1" '.kind == "skill"')"
  bad="$(_recs "$SID_R1" '.kind == "skill" and (.skill != "tcs-workflow:verify" or .route != "typed"
      or .args_present != "yes" or (.source // "") == "")')"
  [ "$(printf '%s' "$typed" | grep -c .)" = "1" ] && [ -z "$bad" ]
  rc=$?; _check "S1 typed skill: one record, tcs-workflow:verify, route typed, args_present yes, source" "$rc" "$typed"
}

_check_tool_skill() {
  local recs
  recs="$(_recs "$SID_R3" '.kind == "skill"')"
  [ -n "$(_recs "$SID_R3" '.kind == "skill" and .skill == "tcs-workflow:verify" and .route == "tool"')" ] \
    && [ -z "$(_recs "$SID_R3" '.kind == "skill" and .route != "tool"')" ]
  rc=$?; _check "S2 model-called skill: route tool" "$rc" "$recs"
}

_check_dispatch() {
  local recs named unnamed
  recs="$(_recs "$SID_R4" '.kind == "dispatch"')"
  named="$(_count "$SID_R4" '.kind == "dispatch" and .subagent_type == "general-purpose" and .name == "probe-named" and .caller == "main"')"
  unnamed="$(_count "$SID_R4" '.kind == "dispatch" and .subagent_type == "general-purpose" and .name == "" and .caller == "main"')"
  [ "$(printf '%s' "$recs" | grep -c .)" = "2" ] && [ "$named" = "1" ] && [ "$unnamed" = "1" ]
  rc=$?; _check "S3 dispatch: two records, general-purpose, one named probe-named, one with empty name" "$rc" "$recs"
}

# Every git record of R4 is a subagent commit; both dispatched agents (their
# ids taken from the SubagentStart records) committed; no `status` record.
_check_subagent_git() {
  local recs ids id bad missing=""
  recs="$(_recs "$SID_R4" '.kind == "git"')"
  bad="$(_recs "$SID_R4" '.kind == "git" and (.subcommand != "commit" or .caller != "subagent"
      or .caller_agent_type != "general-purpose" or (.caller_agent_id // "") == "")')"
  ids="$(_recs "$SID_R4" '.kind == "agent"' | jq -r '.agent_id')"
  for id in $ids; do
    [ -n "$(_recs "$SID_R4" ".kind == \"git\" and .caller_agent_id == \"$id\"")" ] || missing="$missing $id"
  done
  [ -n "$recs" ] && [ -z "$bad" ] && [ -z "$missing" ] && [ "$(printf '%s\n' "$ids" | grep -c .)" = "2" ]
  rc=$?; _check "S3 git: commit only (no status), caller subagent with type and id, one per dispatched agent" "$rc" "$recs"
}

_check_reset() {
  local recs bad
  recs="$(_recs "$SID_R3" '.kind == "git" and .subcommand == "reset"')"
  bad="$(_recs "$SID_R3" '.kind == "git" and .subcommand == "reset" and (.flags != "--hard" or .caller != "main"
      or .overrides != "CLAUDE_ALLOW_RESET_HARD" or .override_first != "CLAUDE_ALLOW_RESET_HARD")')"
  [ -n "$recs" ] && [ -z "$bad" ]
  rc=$?; _check "S4 reset: flags --hard, caller main, overrides and override_first CLAUDE_ALLOW_RESET_HARD" "$rc" "$recs"
}

_check_stash() {
  local recs
  recs="$(_recs "$SID_R3" '.kind == "git" and .subcommand == "stash"')"
  [ -n "$(_recs "$SID_R3" '.kind == "git" and .subcommand == "stash" and .action == "pop" and .caller == "main"')" ] \
    && [ -n "$(_recs "$SID_R3" '.kind == "git" and .subcommand == "stash" and .action == ""')" ]
  rc=$?; _check "S5 stash: plain stash with empty action, then action pop" "$rc" "$recs"
}

_check_unknown() {
  local recs
  recs="$(_recs "$SID_R2" '.kind == "skill"')"
  [ -z "$recs" ] && [ -n "$(_recs "$SID_R2" 'true')" ]
  rc=$?; _check "S6 /nonexistent-skill: no skill record (session itself did record)" "$rc" "$recs"
}

# --- privacy, isolation, protection -----------------------------------------

_check_privacy() {
  local needle hits="" all
  for needle in "$NONCE" "probe-msg" "check nothing" "probe named" "probe unnamed" "Automated observability" \
      "$SCRATCH" "$SCRATCH_REAL" "$S_HOME" "CLAUDE_ALLOW_RESET_HARD=" "=1"; do
    grep -qF -- "$needle" "$EVENTS" && hits="$hits [${needle##*/}]"
  done
  all="$(grep -c . "$EVENTS")"
  [ -z "$hits" ] && [ "$all" -gt 0 ]
  rc=$?; _check "S7 privacy: none of nonce, message, args, descriptions, prompt, scratch paths, =1 in $all records" "$rc" \
    ${hits:+"leaked (needle basename shown):$hits"}
}

# shellcheck disable=SC2012  # the mode string is the point; names are ours
_mode_of() { ls -ld "$1" 2>/dev/null | cut -c1-10; }

_check_isolation() {
  local modes
  modes="$(_mode_of "$DATA/observability") $(_mode_of "$EVENTS")"
  [ "$modes" = "drwx------ -rw-------" ]
  rc=$?; _check "F6 protection: record dir 0700, events.jsonl 0600" "$rc" "$modes"
  [ ! -e "$REAL_DATA" ]
  rc=$?; _check "isolation: nothing written to the real data dir for this repo" "$rc" "${REAL_DATA/#$HOME/~}"
  local touched=""
  [ -d "$HOME/.claude/observability" ] && touched="$(find "$HOME/.claude/observability" -newer "$SCRATCH/start.stamp" 2>/dev/null)"
  [ -z "$touched" ]
  rc=$?; _check "isolation: the real home's bundle is untouched" "$rc" "$touched"
}

# --- report -----------------------------------------------------------------

# _git_triples  flattens the report's git section into "session|caller|line".
_git_triples() {
  awk '/^Git operations/ {g=1; next} g && /^[^ ]/ {g=0}
       g && /^  session / {s=$2; sub(/:$/, "", s); next}
       g && /^    [^ ]/ {c=$0; sub(/^ +/, "", c); sub(/:$/, "", c); next}
       g && /^      / {l=$0; sub(/^ +/, "", l); print s "|" c "|" l}' "$SCRATCH/report.txt"
}

_check_report() {
  python3 "$_REPORT_PY" --events "$EVENTS" --repo-root "$_REPO_ROOT" >"$SCRATCH/report.txt" 2>&1
  rc=$?; _check "S8 report: report.py exits 0" "$rc"
  local route triples
  route="$(grep -E '^  tcs-workflow:verify \[skill\]: tool=[1-9][0-9]*, typed=1$' "$SCRATCH/report.txt")"
  rc=$?; _check "S8 report: tcs-workflow:verify counted with both routes, typed=1" "$rc" "$route"
  grep -A3 'not found in this inventory at all' "$SCRATCH/report.txt" | grep -q '^  general-purpose \[agent\]$' \
    && ! grep -q 'uncreditable' "$SCRATCH/report.txt"
  rc=$?; _check "S8 report: dispatched general-purpose credited as built-in, nothing uncreditable" "$rc"
  triples="$(_git_triples)"
  _check_report_git "$triples"
}

_check_report_git() {
  local triples="$1" sub_commits main_reset
  sub_commits="$(printf '%s\n' "$triples" | grep -c "^$SID_R4|general-purpose [^|]*|commit -- flags: --allow-empty -m")"
  main_reset="$(printf '%s\n' "$triples" | grep "^$SID_R3|main|reset -- flags: --hard; overrides: CLAUDE_ALLOW_RESET_HARD (first position)")"
  [ "$sub_commits" = "2" ] && [ -n "$main_reset" ] \
    && ! printf '%s\n' "$triples" | grep -q "^$SID_R4|main|"
  rc=$?; _check "S8 report: commit under both subagent callers, reset under main" "$rc" "$triples"
}

_check_no_leftovers() {
  local procs
  procs="$(pgrep -fl -- "$SCRATCH" 2>/dev/null || true)"
  [ -z "$procs" ]
  rc=$?; _check "no process left referencing the scratch dir" "$rc" "$procs"
}

_manual_step() {
  cat <<'EOF'

MANUAL STEP (not automated; record the result in the PR):
  1. In a repository registered with `observability-setup install`, start an
     INTERACTIVE `claude` session (not -p) and ask it to dispatch one named
     subagent, e.g.: "Use the Agent tool with subagent_type general-purpose
     and name probe-166 to run `git status` and reply done."
  2. In that repo's events.jsonl, look for the session's two new records:
       kind: dispatch  subagent_type general-purpose, name probe-166
       kind: agent     agent_type probe-166  (SubagentStart carries the SPAWN
                       NAME interactively; headless runs carry the type)
  3. Run scripts/observability/report.py: general-purpose is credited through
     the dispatch, and probe-166 must NOT appear under "uncreditable" -- the
     report dedupes the agent record against the dispatch name.
EOF
}

main() {
  _parse_args "$@"
  _preflight
  _make_scratch
  _say "e2e probe: model $MODEL, scratch $SCRATCH"
  _make_repo
  _install_bundle
  _repoint_registration
  _check_registration
  _run_all
  [ -s "$EVENTS" ] || _die 1 "no events.jsonl was written at all -- the registration did not fire"
  _check_typed; _check_tool_skill; _check_dispatch; _check_subagent_git
  _check_reset; _check_stash; _check_unknown; _check_privacy; _check_isolation
  _check_report; _check_no_leftovers
  _say ""
  _say "claude runs: $RUNS (model $MODEL); failures: $FAILURES"
  _manual_step
  [ "$FAILURES" = "0" ]
}

# Sourced (the offline test of these checks), define only.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
