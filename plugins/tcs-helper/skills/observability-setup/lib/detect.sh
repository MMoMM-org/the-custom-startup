#!/usr/bin/env bash
# skills/observability-setup/lib/detect.sh — classify a target before this
# feature touches it.
#
# spec 019 (observability rollout across active repos), Phase 2, T2.2.
#
# Usage: detect.sh [<target_dir>]
#   target_dir: repository (or subdirectory of one) to classify. Defaults to
#   the current directory (documented default — see the set -u test below).
#
# Prints exactly ONE labelled state line to stdout per run:
#   [tcs-helper:observability-setup] <LABEL>: <message>
# following the convention of
# plugins/tcs-git-helpers/skills/git-setup/lib/detect_conflicts.sh:37-40
# (_emit "<LABEL>" "<message>"). Zero or more additional INFO lines may
# precede it. The exit code carries SEVERITY ONLY — state and severity are
# two separate channels (maintainer ruling, plan/phase-2.md T2.2):
#
#   state                    label          exit
#   --------------------------------------------
#   clean (absent/empty)     CLEAN            0
#   ours-current             OURS-CURRENT     0
#   ours-old                 OURS-OLD         4
#   legacy in-repo           LEGACY           4
#   foreign-only             CONFLICT         3
#   not-a-repository         ABORT            2
#   unparseable              ABORT            2
#   valid-json-wrong-shape   ABORT            2
#   write-path-not-ignored   ABORT            2
#
# LEGACY and OURS-OLD are WARN, not ABORT, deliberately: both mean "action
# available, nothing broken" — the maintainer-approved migration of this
# repository's own legacy registration runs through setup, and an abort
# there would force that migration to be a manual two-step.
#
# GATE ORDERING (one labelled line per target — never both ABORT and a
# content classification for the same target):
#   1. Not a repository            -> ABORT, exit 2, stop.
#   2. Write path not ignored by   -> ABORT, exit 2, stop — WITHOUT reading
#      version control                the settings content at all.
#   3. Only a target passing both gates is classified, from its content.
#
# WHY THE GATE COMES BEFORE ANY CONTENT READ: the write path
# (.claude/settings.local.json) is deliberately untracked (ADR-1), so a
# repository the maintainer does not own could have version control
# disabled for it entirely, or a broken/absent ignore rule. Reading the
# file's content first and reporting on it would still be safe by itself,
# but ordering it AFTER the gate means an aborted target never gets a
# second, contradictory finding — see plan/phase-2.md T2.2 (a target must
# never come back as both ABORT and, say, OURS-OLD).
#
# git check-ignore semantics, deliberately unmodified: production calls
# PLAIN `git check-ignore` (no -c core.excludesFile override here) because a
# personal global ignore rule is real for users, and suppressing it would
# make detection lie about whether a file is actually safe to write. Tests
# neutralise the *developer's* personal global ignore purely from the
# environment (GIT_CONFIG_COUNT / GIT_CONFIG_KEY_0 / GIT_CONFIG_VALUE_0 —
# see observability-detect.bats) rather than by changing this script.
#
# THE LEGACY SHAPE (this repository's own real, hand-made state, measured
# 2026-09-08 — plan/phase-2.md T2.1/T2.2): hooks registered in
# .claude/settings.json (NOT settings.local.json) under our three event
# names, pointing at $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/
# observability/<adapter>.sh rather than $HOME/.claude/observability/. It is
# OURS but in the wrong file and the wrong namespace: reporting it CLEAN
# would let setup add a second registration beside a live one (double-
# recording in the repository the whole collection period depends on);
# reporting it a bare CONFLICT would name our own scripts as a third
# party's. So it gets its own label, checked independently of whatever
# settings.local.json holds.
#
# OURS-CURRENT vs OURS-OLD IS NOT OBSERVABLE FROM THE SETTINGS FILE AT ALL:
# ADR-5 makes the registration command string version-opaque on purpose (a
# namespace prefix survives a version change), so both states carry byte-
# identical JSON in settings.local.json. The version lives only in the
# bundle marker under the resolved $HOME. This script reads that marker
# through Phase 1's _bundle_install_target_dir() / _drift_check_
# observability_bundle() (sourced from drift_check.sh, which itself sources
# bundle_install.sh) — never by composing "$HOME/.claude/observability" a
# second time here, so a caller that sets _BUNDLE_INSTALL_TARGET_DIR (or a
# test $HOME override) is honoured automatically.
#
# bash 3.2 (CON-1): no `[[ =~ ]]` with PCRE classes or bounded quantifiers
# anywhere below. JSON parsing and structural classification (is "hooks" an
# object? does an entry's command point inside our namespace?) is delegated
# to python3 — already this project's convention for JSON (build.sh's
# fixtures, observability-settings-fixtures.bats) — never re-implemented as
# shell regex.
#
# set -u safety: every optional positional read below uses ${VAR:-...}.
#
# Never writes anything, anywhere: only `git rev-parse`, `git check-ignore`
# and file reads (this script's own, and python3's read-only json.load).

set -euo pipefail

_emit() {
  # $1 = label, $2 = message
  printf '[tcs-helper:observability-setup] %s: %s\n' "$1" "$2"
}

_DETECT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _DETECT_LIB_DIR=""

# Pulls in _bundle_install_target_dir(), _BUNDLE_INSTALL_MARKER_NAME,
# _read_observability_bundle_version() (via bundle_install.sh's own source
# of bundle_version.sh) and _drift_check_observability_bundle(). Sourcing
# only drift_check.sh is deliberate — it already sources bundle_install.sh
# itself, so sourcing both here would just re-run the same resolution twice.
# shellcheck source=./drift_check.sh
# shellcheck disable=SC1091
#
# Guarded, and its stderr NOT suppressed. Unguarded under `set -e` this line
# killed the script with exit 1 and no output at all -- no state line, and an
# exit code outside the documented 0/2/3/4 range, so T4.1's caller would have
# had nothing to branch on and nothing to show. Not hypothetical: this repo's
# own documented workflow hand-copies skill directories between the plugin
# cache and the marketplace source, and a partial copy produces exactly this.
if [ -z "$_DETECT_LIB_DIR" ]; then
  _emit "ABORT" "cannot resolve this script's own directory, so its sibling libraries cannot be loaded."
  exit 2
fi
if [ ! -r "$_DETECT_LIB_DIR/drift_check.sh" ]; then
  _emit "ABORT" "cannot read $_DETECT_LIB_DIR/drift_check.sh -- this skill's lib/ directory is incomplete."
  exit 2
fi
if ! . "$_DETECT_LIB_DIR/drift_check.sh"; then
  _emit "ABORT" "failed to load $_DETECT_LIB_DIR/drift_check.sh -- this skill's lib/ directory looks damaged."
  exit 2
fi

TARGET_DIR="${1:-.}"

# --- 1. Not a repository -----------------------------------------------
REPO_ROOT="$(git -C "$TARGET_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  _emit "ABORT" "Target is not inside a git repository: $TARGET_DIR"
  exit 2
fi

WRITE_PATH_REL=".claude/settings.local.json"

# --- 2. Write-path gate: must be ignored by version control -------------
# Plain check-ignore (see header) — no override applied here.
if ! git -C "$REPO_ROOT" check-ignore -q -- "$WRITE_PATH_REL" 2>/dev/null; then
  _emit "ABORT" "Write path is not ignored by version control: $WRITE_PATH_REL"
  exit 2
fi

# INFO only: which kind of ignore rule this target relies on. Not part of
# the state channel — a target relying on a personal global ignore alone is
# more fragile than one carrying its own .gitignore rule (plan/phase-2.md
# T2.2), so name which one was found.
# `git check-ignore -v` names its source RELATIVE to the repo (".gitignore",
# ".git/info/exclude") when the rule is repo-owned, and by an ABSOLUTE path
# (the resolved core.excludesFile / XDG global ignore) when it is not —
# measured directly: a repo-owned .gitignore rule prints " .gitignore:1:...",
# a global excludesFile rule prints its full path. So the leading "/" is
# the whole test; no path-prefix comparison against $REPO_ROOT is needed
# (and would be wrong besides, since the repo-relative form never repeats
# $REPO_ROOT).
IGNORE_VERBOSE="$(git -C "$REPO_ROOT" check-ignore -v -- "$WRITE_PATH_REL" 2>/dev/null || true)"
IGNORE_SOURCE="${IGNORE_VERBOSE%%$'\t'*}"
IGNORE_SOURCE="${IGNORE_SOURCE%%:*}"
case "$IGNORE_SOURCE" in
  /*)
    _emit "INFO" "Write path ignored by a global/user-level rule (${IGNORE_SOURCE:-unknown source}), not the repository's own ignore file"
    ;;
  *)
    _emit "INFO" "Write path ignored by the repository's own ${IGNORE_SOURCE:-ignore file}"
    ;;
esac

# --- 3. Classify from content --------------------------------------------
# Only a target that passed both gates above reaches this point.
LOCAL_SETTINGS="$REPO_ROOT/.claude/settings.local.json"
SHARED_SETTINGS="$REPO_ROOT/.claude/settings.json"

# CON-1 gotcha, newly measured, two distinct traps in the same shape:
#   1. A heredoc nested inside a DOUBLE-QUOTED command substitution
#      ("$(...)") breaks under bash 3.2 if the heredoc body contains ANY
#      single quote at all -- including a plain apostrophe inside a #
#      comment, which is not even python-parsed as a string. Fix: assign
#      via unquoted VAR=$(...) instead of VAR="$(...)"; an assignment's RHS
#      is not subject to word splitting either way, so dropping the quotes
#      costs nothing.
#   2. Even unquoted, a BACKSLASH-ESCAPED single quote (\') inside the
#      heredoc body still breaks it. Fix: never write \' in the python
#      below -- rephrase to avoid the contraction instead.
# Both produce the same symptom: "unexpected EOF while looking for
# matching `''" (or `"'), pointing at a line deep inside the heredoc that
# is, on its face, fully quoted and therefore should be inert to bash.
CLASSIFY_OUTPUT=$(python3 - "$LOCAL_SETTINGS" "$SHARED_SETTINGS" <<'PY'
import json
import os
import sys

OUR_NAMESPACE = "$HOME/.claude/observability/"
# Event name -> the adapter script this feature's own bundle installs for
# it. Used ONLY to recognise the legacy in-repo shape (settings.json,
# scripts under $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability
# rather than $HOME/.claude/observability) — never to decide "ours" in
# settings.local.json, where ownership is proven by path namespace alone
# (ADR-5).
#
# DEFINED TWICE, AND THE TWO MUST CHANGE TOGETHER: registration.py carries
# the same mapping under the same name, because it is what performs the
# migration this classification exists to trigger, and this copy lives
# inside a heredoc a shell script wraps — there is no module here to import
# from. See registration.py's LEGACY_SCRIPTS for the full reasoning; the
# same treatment CON-6 gets between report.py and sources.py.
LEGACY_SCRIPTS = {
    "InstructionsLoaded": "log_instructions.sh",
    "PreToolUse": "log_skill.sh",
    "SubagentStart": "log_agent.sh",
}

# The in-repo path the legacy registration points at. Matching used to be the
# script BASENAME alone, which a third party's own log_skill.sh satisfies --
# measured, and it already cost one: a shared file carrying two real legacy
# entries plus an unrelated /opt/other-tool/log_skill.sh matched all three
# events, classified LEGACY, and the migration DELETED the third party's hook.
# Ownership is the namespace (ADR-5), here as everywhere else.
LEGACY_NAMESPACE = "plugins/tcs-helper/scripts/observability/"


class WrongShape(Exception):
    pass


def load(path):
    """Returns (data, error). data is None if the file is absent, unreadable,
    or fails to parse. error is None, or a (kind, message) pair where kind is
    "unreadable" or "malformed" -- kept apart because "not valid JSON" is a
    wrong diagnosis for a permission error, and sends whoever is debugging it
    looking for a syntax problem in a file they cannot even open."""
    if not path or not os.path.isfile(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return None, ("unreadable", "cannot read %s: %s" % (path, exc))
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, ("malformed", "not valid JSON: %s" % exc)


def hook_commands(hooks, strict=False):
    """Walks a parsed "hooks" object, returning [(event, command), ...].
    Raises WrongShape with a diagnosis the moment the structure departs
    from event -> [ {hooks: [ {command: ...}, ... ]}, ... ] -- this is what
    turns a valid-json-wrong-shape file into a diagnosis instead of an
    unhandled TypeError/KeyError reaching the user.

    strict=True adds the two checks registration.py makes and this walk used
    only to skip over: a non-object element inside an entry hooks array, and
    a "command" that is present but not a string. Skipping them here while
    the editor raises on them is the asymmetry that let a target pass the
    gate and then fail mid-write. strict is used for the LOCAL settings file
    only -- is_legacy below calls this on the SHARED file to recognise a
    shape, and raising there would turn an unrelated malformation elsewhere
    in that file into "not legacy", which is a classification change rather
    than a gate."""
    commands = []
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            raise WrongShape(
                '"hooks.%s" is not an array (found %s)' % (event, type(groups).__name__)
            )
        for group in groups:
            if not isinstance(group, dict):
                raise WrongShape('"hooks.%s" has a non-object entry' % event)
            entry_hooks = group.get("hooks", [])
            if not isinstance(entry_hooks, list):
                raise WrongShape(
                    '"hooks.%s" hook-group "hooks" value is not an array (found %s)'
                    % (event, type(entry_hooks).__name__)
                )
            for one in entry_hooks:
                if strict and not isinstance(one, dict):
                    raise WrongShape(
                        '"hooks.%s" contains a non-object hook in its "hooks" array' % event
                    )
                if strict and isinstance(one, dict):
                    command = one.get("command")
                    if command is not None and not isinstance(command, str):
                        raise WrongShape(
                            '"hooks.%s" contains a hook whose "command" is not a string (found %s)'
                            % (event, type(command).__name__)
                        )
                if isinstance(one, dict) and isinstance(one.get("command"), str):
                    commands.append((event, one["command"]))
    return commands


def legacy_events(shared_data):
    """The event names carrying a legacy in-repo registration, sorted.

    ONE OR MORE IS ENOUGH -- maintainer ruling (x), 2026-09-11. This returned
    a boolean gated on all three events matching, so every partial shape came
    back CLEAN: one event absent, one replaced by a malformed hook, one
    pointing elsewhere, or the env flag removed by hand. Install then added a
    full registration beside still-live legacy hooks and the target recorded
    twice -- the state the migration exists to prevent -- while remove
    reported success and those hooks kept firing. Four doors to one room,
    measured rather than reasoned about.

    ZERO IS STILL CLEAN, deliberately: a shared file a partial migration has
    already stripped has nothing left to migrate, and calling it LEGACY would
    send setup down a migration path with nothing to remove.

    THE ENV FLAG NO LONGER GATES. It was corroboration for a weak match, and
    with ownership proven by LEGACY_NAMESPACE it adds nothing but another way
    for a live legacy registration to read as CLEAN.
    """
    if not isinstance(shared_data, dict):
        return []
    shared_hooks = shared_data.get("hooks", {})
    if not isinstance(shared_hooks, dict):
        return []
    try:
        shared_commands = hook_commands(shared_hooks)
    except WrongShape:
        return []
    matched_events = set()
    for event, cmd in shared_commands:
        if OUR_NAMESPACE in cmd:
            continue  # points at $HOME already -- that would be "ours", not legacy
        if LEGACY_NAMESPACE not in cmd:
            continue  # not in our namespace, so not ours to touch
        expected_script = LEGACY_SCRIPTS.get(event)
        # The command string is shell-quoted (wrapped in literal double
        # quotes so the path survives a space), so it ends with `.sh"`, not
        # `.sh` -- strip a single trailing '"' before comparing.
        if expected_script and cmd.rstrip('"').endswith(expected_script):
            matched_events.add(event)
    return sorted(matched_events)


def main():
    local_path, shared_path = sys.argv[1], sys.argv[2]

    local_data, local_err = load(local_path)
    if local_err:
        kind, message = local_err
        token = "ABORT_UNREADABLE" if kind == "unreadable" else "ABORT_MALFORMED"
        print(token + "|" + message)
        return

    if local_data is None:
        local_data = {}
    if not isinstance(local_data, dict):
        print(
            "ABORT_WRONGSHAPE|top-level value is not an object (found %s)"
            % type(local_data).__name__
        )
        return

    # registration.py merges the env switch into local_data["env"] and
    # raises if it is not an object. This gate validated the top-level shape
    # and "hooks" but never "env", so such a target was classified as safe to
    # act on and the editor refused it mid-operation. Mirrors the "hooks"
    # check immediately below; absent is fine, since the editor creates it.
    local_env = local_data.get("env")
    if local_env is not None and not isinstance(local_env, dict):
        print(
            'ABORT_WRONGSHAPE|"env" is not an object (found %s)'
            % type(local_env).__name__
        )
        return

    local_hooks = local_data.get("hooks", {})
    if local_hooks is None:
        local_hooks = {}
    if not isinstance(local_hooks, dict):
        print(
            'ABORT_WRONGSHAPE|"hooks" is not an object (found %s)'
            % type(local_hooks).__name__
        )
        return

    try:
        local_commands = hook_commands(local_hooks, strict=True)
    except WrongShape as exc:
        print("ABORT_WRONGSHAPE|%s" % exc)
        return

    shared_data, _shared_err = load(shared_path)
    # A malformed/unreadable settings.json is not one of this task's ABORT
    # states (only settings.local.json's shape is gated that way) -- treat
    # it as "no legacy shape found" rather than aborting on the shared file.
    found = legacy_events(shared_data)
    if found:
        print("LEGACY|" + ", ".join(found))
        return

    ours = [cmd for _, cmd in local_commands if OUR_NAMESPACE in cmd]
    if ours:
        print("OURS")
        return

    foreign = sorted({cmd for _, cmd in local_commands if OUR_NAMESPACE not in cmd})
    if foreign:
        print("CONFLICT|" + ", ".join(foreign))
        return

    print("CLEAN")


try:
    main()
except Exception as exc:  # noqa: BLE001 -- last-resort diagnosis, never a traceback
    print("ABORT_WRONGSHAPE|unexpected error while classifying: %s" % exc)
PY
)

case "$CLASSIFY_OUTPUT" in
  ABORT_UNREADABLE\|*)
    _emit "ABORT" "$WRITE_PATH_REL cannot be read (${CLASSIFY_OUTPUT#ABORT_UNREADABLE|})"
    exit 2
    ;;
  ABORT_MALFORMED\|*)
    _emit "ABORT" "$WRITE_PATH_REL is not valid JSON (${CLASSIFY_OUTPUT#ABORT_MALFORMED|})"
    exit 2
    ;;
  ABORT_WRONGSHAPE\|*)
    _emit "ABORT" "$WRITE_PATH_REL has an unexpected shape (${CLASSIFY_OUTPUT#ABORT_WRONGSHAPE|})"
    exit 2
    ;;
  LEGACY\|*)
    _emit "LEGACY" "Observability hooks already registered in .claude/settings.json under the legacy in-repo namespace (plugins/tcs-helper/scripts/observability/) for: ${CLASSIFY_OUTPUT#LEGACY|}; setup will migrate these to \$HOME/.claude/observability/."
    exit 4
    ;;
  OURS)
    EXPECTED_VERSION="$(_read_observability_bundle_version 2>/dev/null || true)"
    if [ -z "$EXPECTED_VERSION" ]; then
      _emit "ABORT" "Could not read this plugin's own observability bundle version marker"
      exit 2
    fi
    DRIFT_RESULT="$(_drift_check_observability_bundle "$EXPECTED_VERSION")"
    case "$DRIFT_RESULT" in
      OK)
        _emit "OURS-CURRENT" "Observability hooks registered under \$HOME/.claude/observability/ at the current bundle version ($EXPECTED_VERSION)."
        exit 0
        ;;
      MISSING)
        _emit "OURS-OLD" "Observability hooks registered under \$HOME/.claude/observability/, but no bundle marker is installed at the resolved home; treat as out of date."
        exit 4
        ;;
      DRIFT:*)
        _emit "OURS-OLD" "Observability hooks registered under \$HOME/.claude/observability/ at an older bundle version (${DRIFT_RESULT#DRIFT:}, expected $EXPECTED_VERSION)."
        exit 4
        ;;
      *)
        _emit "ABORT" "Unexpected drift-check result: $DRIFT_RESULT"
        exit 2
        ;;
    esac
    ;;
  CONFLICT\|*)
    _emit "CONFLICT" "Foreign hook entries found in $WRITE_PATH_REL: ${CLASSIFY_OUTPUT#CONFLICT|}"
    exit 3
    ;;
  CLEAN)
    _emit "CLEAN" "No observability registration and no foreign hook entries in $WRITE_PATH_REL."
    exit 0
    ;;
  *)
    _emit "ABORT" "Unexpected classification output: $CLASSIFY_OUTPUT"
    exit 2
    ;;
esac
