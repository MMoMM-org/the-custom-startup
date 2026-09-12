#!/usr/bin/env bash
# skills/observability-setup/lib/setup.sh — the verb dispatcher: one command
# with three verbs, not three commands.
#
# spec 019 (observability rollout across active repos), Phase 4, T4.1,
# maintainer ruling (r): the SDD's Directory Map lists only SKILL.md and
# lib/, following git-setup, where markdown orchestrates libraries in prose.
# But T4.1 step 4 requires the command be exercised "through its real entry
# point, not by calling its libraries directly", and bats cannot exercise a
# Markdown file. Both hold only if a dispatcher exists, so this is it.
# SKILL.md keeps what a script cannot own — the confirmation at Runtime View
# step 5 and the narration at step 8 — and calls this for everything
# mechanical.
#
# Usage:
#   setup.sh install --target <path> [--yes] [--plan]
#   setup.sh remove  --target <path> [--yes] [--plan]
#   setup.sh status  --target <path>
#
# --yes is the non-interactive confirmation. WITHOUT it, install and remove
# report the plan and write nothing — that no-write path is the mechanical
# equivalent of a user declining at SKILL.md's confirmation prompt, and is
# what the bats suite asserts in place of a prompt it cannot drive. --plan
# forces the same no-write path even when --yes is given.
#
# ---------------------------------------------------------------------------
# THE EXIT-CODE MAPPING, AND WHY IT IS SOLVED BY ORDERING
# ---------------------------------------------------------------------------
# detect.sh's header is explicit that "the exit code carries SEVERITY ONLY —
# state and severity are two separate channels". It exits 2 for FOUR
# semantically different ABORT states: not-a-repository, unparseable,
# valid-json-wrong-shape and write-path-not-ignored. The SDD's Error
# Handling table gives two of those OPPOSITE command-level outcomes:
#
#     Target is not a repository   -> report, write nothing, exit 0
#     Settings file is unparseable -> write nothing, report,  exit non-zero
#
# So this dispatcher cannot map severity alone — and it must not disambiguate
# by reading ABORT message prose either, which would couple the command to
# wording detect.sh is free to improve. It disambiguates by ORDERING, which
# Runtime View step 1 already requires: setup.sh resolves the target's
# toplevel ITSELF, before the lock and before detect.sh. A non-repository is
# refused there and detect.sh is never reached, so every exit 2 that does
# come back is a genuine refusal.
#
#   detect.sh result                 label            setup.sh exit
#   ------------------------------------------------------------------
#   (never reached: not a repo)      —                0   STOP
#   exit 0  clean                    CLEAN            0   proceed
#   exit 0  ours, current bundle     OURS-CURRENT     0   already configured
#   exit 4  ours, older bundle       OURS-OLD         0   proceed (refresh)
#   exit 4  legacy in-repo shape     LEGACY           0   proceed (migrate)
#   exit 3  foreign entries          CONFLICT         0   STOP, change nothing
#   exit 2  unparseable              ABORT            1   refuse
#   exit 2  valid json, wrong shape  ABORT            1   refuse
#   exit 2  write path not ignored   ABORT            1   refuse
#   any other exit                   —                1   refuse
#
# CONFLICT is exit 0 deliberately: foreign content is a stop condition, not a
# failure, and anything checking status codes must not read it as one. The
# same reasoning gives the non-repository case exit 0.
#
# ---------------------------------------------------------------------------
# WHY THE IGNORE CHECK PRECEDES THE LOCK, THOUGH THE RUNTIME VIEW NUMBERS IT 4
# ---------------------------------------------------------------------------
# Runtime View step 2 takes the lock before detection so two concurrent runs
# serialize across the whole detect->write sequence (the ordering git-setup
# establishes at SKILL.md:96). That still holds here. What comes even earlier
# is the version-control check — because THE LOCK FILE IS ITSELF ONE OF THE
# PATHS THIS FEATURE WRITES INTO THE TARGET (registration.written_paths()
# lists it beside the settings file, its backup and its temp file). Creating
# it in a repository where it is committable is the exact harm step 4 exists
# to prevent, so the check cannot come after the thing it guards. Detection
# re-checks the settings path on its own account; that redundancy keeps
# detect.sh usable standalone and costs one `git check-ignore`.
#
# The check covers EVERY path in written_paths(), not just the settings file
# detect.sh gates. The `ignored-file-but-not-backup` fixture is why: a
# repository that ignores `.claude/settings.local.json` by exact name and not
# `.claude/` wholesale passes detection and would still receive a committable
# `.bak`.
#
# ---------------------------------------------------------------------------
# THE LOCK
# ---------------------------------------------------------------------------
# Held by THIS process for the whole sequence, at the same path and in the
# same `<pid>:<epoch>` format lock.py and git-setup's lock.sh use, so a
# direct `registration.py` run and a `setup.sh` run contend correctly with
# each other. registration.py is invoked with --lock-held-by-caller so it
# does not deadlock against a lock this process already owns. Acquire and
# release happen in one process, so the owner PID is alive throughout — the
# reason this is shell here rather than a lock.py call per step, which would
# leave a dead-PID owner between subprocesses and be reclaimable by a
# concurrent run.
#
# bash 3.2 (CON-1): no associative arrays, no ${var^^}, no `[[ =~ ]]` with
# PCRE classes or bounded quantifiers. JSON is never parsed here — that is
# registration.py's and detect.sh's job.
#
# Never writes outside the resolved $HOME bundle directory and the target's
# own .claude/ directory.

set -euo pipefail

_SETUP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _SETUP_LIB_DIR=""

_emit() {
  # $1 = label, $2 = message. Same one-line convention as detect.sh.
  printf '[tcs-helper:observability-setup] %s: %s\n' "$1" "$2"
}

if [ -z "$_SETUP_LIB_DIR" ]; then
  _emit "ABORT" "cannot resolve this script's own directory, so its sibling libraries cannot be loaded."
  exit 1
fi

# drift_check.sh sources bundle_install.sh, which sources bundle_version.sh.
# One source line pulls in _bundle_install_target_dir,
# _BUNDLE_INSTALL_MARKER_NAME, _BUNDLE_INSTALL_SOURCE_DIR,
# _install_observability_bundle, _read_observability_bundle_version and
# _drift_check_observability_bundle. Guarded, and its stderr not suppressed,
# for the reason detect.sh records at its own source site: unguarded under
# `set -e` a missing sibling kills the script with no output at all.
if [ ! -r "$_SETUP_LIB_DIR/drift_check.sh" ]; then
  _emit "ABORT" "cannot read $_SETUP_LIB_DIR/drift_check.sh -- this skill's lib/ directory is incomplete."
  exit 1
fi
# shellcheck source=./drift_check.sh
# shellcheck disable=SC1091
if ! . "$_SETUP_LIB_DIR/drift_check.sh"; then
  _emit "ABORT" "failed to load $_SETUP_LIB_DIR/drift_check.sh -- this skill's lib/ directory looks damaged."
  exit 1
fi

_DETECT_SH="$_SETUP_LIB_DIR/detect.sh"
_REGISTRATION_PY="$_SETUP_LIB_DIR/registration.py"

# The record-path formula is NOT re-derived here. logwrite.sh is the WRITER —
# the source of truth report.py and sources.py both mirror — it lives inside
# this plugin (so the skill still works installed into any repository, which
# importing scripts/observability/sources.py would not), and it is designed
# to be sourced. Its resolver takes the pre-resolved toplevel as $1 precisely
# so a caller that already forked git does not fork again (CON-7), which is
# this dispatcher's situation after step 1. Located through the path
# bundle_install.sh already resolves, rather than a second relative path of
# our own.
_LOGWRITE_SH=""
if [ -n "${_BUNDLE_INSTALL_SOURCE_DIR:-}" ] && [ -r "$_BUNDLE_INSTALL_SOURCE_DIR/logwrite.sh" ]; then
  _LOGWRITE_SH="$_BUNDLE_INSTALL_SOURCE_DIR/logwrite.sh"
  # shellcheck source=../../../scripts/observability/logwrite.sh
  # shellcheck disable=SC1091
  . "$_LOGWRITE_SH"
fi

# ---------------------------------------------------------------------------
# Usage and argument parsing
# ---------------------------------------------------------------------------

_usage() {
  cat <<'USAGE'
Usage: setup.sh <verb> --target <path> [--yes] [--plan]

Verbs:
  install   register observability recording in the target repository
  remove    take this feature's registration back out of the target
  status    report the target's registration, bundle and recording state

Options:
  --target <path>   the repository (or a subdirectory of one) to act on
  --yes             apply the change; without it, install and remove report
                    the plan and write nothing
  --plan            report the plan and write nothing, even with --yes
USAGE
}

VERB="${1:-}"
if [ -z "$VERB" ]; then
  _usage >&2
  _emit "ABORT" "no verb given" >&2
  exit 2
fi
shift

case "$VERB" in
  install|remove|status) ;;
  -h|--help)
    _usage
    exit 0
    ;;
  *)
    _usage >&2
    _emit "ABORT" "unknown verb: $VERB" >&2
    exit 2
    ;;
esac

TARGET=""
ASSUME_YES=0
PLAN_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      if [ $# -lt 2 ]; then
        _emit "ABORT" "--target needs a path" >&2
        exit 2
      fi
      TARGET="$2"
      shift 2
      ;;
    --target=*)
      TARGET="${1#--target=}"
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --plan)
      PLAN_ONLY=1
      shift
      ;;
    *)
      _usage >&2
      _emit "ABORT" "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$TARGET" ]; then
  _usage >&2
  _emit "ABORT" "--target is required" >&2
  exit 2
fi

# status is read-only in every mode, so neither flag applies to it. install
# and remove write only when told to.
APPLY=0
if [ "$ASSUME_YES" -eq 1 ] && [ "$PLAN_ONLY" -eq 0 ]; then
  APPLY=1
fi

# ---------------------------------------------------------------------------
# Runtime View step 1 — resolve the toplevel, before the lock and before
# detection. A target that is not a repository is refused HERE, which is what
# lets every detect.sh exit 2 below mean "refusal" (see the header).
# ---------------------------------------------------------------------------

REPO_ROOT="$(git -C "$TARGET" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  _emit "STOP" "Target is not inside a git repository, so nothing was written: $TARGET"
  exit 0
fi

LOCAL_SETTINGS="$REPO_ROOT/.claude/settings.local.json"
SHARED_SETTINGS="$REPO_ROOT/.claude/settings.json"
LOCK_FILE="$LOCAL_SETTINGS.tcs-observability.lock"
BUNDLE_DIR="$(_bundle_install_target_dir)"

_emit "TARGET" "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Runtime View step 4 (hoisted — see the header): every path this feature can
# write into the target must be ignored by version control.
# ---------------------------------------------------------------------------

# _written_paths <settings_path> — the declaration registration.py keeps, read
# from the module itself rather than restated here, so a path added to
# write_settings without being added to written_paths() cannot slip past this
# check by being unknown to it.
#
# bash 3.2 heredoc traps (measured, documented at detect.sh:178-191): assign
# via UNQUOTED VAR=$(...) and never write a backslash-escaped single quote in
# the python body.
_written_paths() {
  local settings="$1" out
  out=$(python3 - "$_SETUP_LIB_DIR" "$settings" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
import registration

for path in registration.written_paths(sys.argv[2]):
    print(path)
PY
) || return 1
  printf '%s\n' "$out"
}

# _verify_paths_ignored <settings_path> <what> — refuses if any path this
# feature could write for <settings_path> is reachable by version control.
# Prints the offending path; returns 1.
_verify_paths_ignored() {
  local settings="$1" what="$2"
  local paths path rel
  if ! paths="$(_written_paths "$settings")"; then
    _emit "ABORT" "could not determine which paths setup would write for $settings"
    return 1
  fi
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    # Quoted on purpose: the # operator takes a PATTERN, not a literal, so
    # an unquoted $REPO_ROOT containing [ ? or * fails to match and `rel`
    # stays absolute -- which then lands verbatim in the refusal message the
    # operator reads. shellcheck SC2295.
    rel="${path#"$REPO_ROOT"/}"
    # Plain check-ignore, deliberately — the same posture detect.sh
    # documents: a personal global ignore rule is real for users, and
    # suppressing it here would make this check lie about whether a file is
    # actually safe to write.
    if ! git -C "$REPO_ROOT" check-ignore -q -- "$rel" 2>/dev/null; then
      _emit "ABORT" "Refusing to write: version control does not ignore $rel, which setup would create for the $what settings file. A change this feature makes must never be committable in a repository it does not own."
      return 1
    fi
  done <<EOF
$paths
EOF
  return 0
}

if ! _verify_paths_ignored "$LOCAL_SETTINGS" "local"; then
  exit 1
fi

# ---------------------------------------------------------------------------
# Runtime View step 2 — the lock, before detection.
# ---------------------------------------------------------------------------

_LOCK_HELD=0

# Why _lock_acquire failed, for the caller's message. "contention" means a
# lock file is there and its owner is alive; "create" means the file could not
# be made at all. set -u safety: both are assigned here, not only on failure.
_LOCK_FAIL_REASON=""
_LOCK_FAIL_DETAIL=""

_lock_owner_pid() {
  # Prints the pid from a `<pid>:<epoch>` lock line, or nothing if the file
  # is absent, empty or unparseable.
  local text pid stamp
  text="$(head -n 1 "$1" 2>/dev/null || true)"
  pid="${text%%:*}"
  stamp="${text#*:}"
  stamp="${stamp%%[!0-9]*}"
  case "$pid" in
    ''|*[!0-9]*) return 0 ;;
  esac
  case "$stamp" in
    ''|*[!0-9]*) return 0 ;;
  esac
  printf '%s %s' "$pid" "$stamp"
}

_lock_file_age() {
  local m now
  # GNU first, BSD as the fallback, and the value assigned WHOLE: `stat -f`
  # means "filesystem" on GNU, prints a whole report to stdout and then
  # exits non-zero, so a `||`-appended fallback yields report+mtime rather
  # than mtime (docs/ai/memory/active.md).
  m="$(stat -c %Y "$1" 2>/dev/null)" || m="$(stat -f %m "$1" 2>/dev/null)" || m=""
  if [ -z "$m" ]; then
    printf '0'
    return 0
  fi
  now="$(date +%s)"
  printf '%s' "$(( now - m ))"
}

# _lock_acquire — poll until the lock is ours or the bounded wait expires.
# Mirrors lock.py, which mirrors git-setup's lock.sh: a stale lock is REMOVED
# and the next poll race-creates cleanly, so two contenders that both saw the
# same stale lock cannot both succeed.
_lock_acquire() {
  local timeout ttl grace attempts=0 start now owner pid stamp stale
  local create_error=""
  timeout="${TCS_OBSERVABILITY_LOCK_TIMEOUT:-10}"
  ttl="${TCS_OBSERVABILITY_LOCK_TTL:-300}"
  grace=2
  case "$timeout" in *[!0-9]*) timeout=10 ;; esac
  case "$ttl" in *[!0-9]*) ttl=300 ;; esac
  start="$(date +%s)"

  mkdir -p "$(dirname "$LOCK_FILE")" 2>/dev/null || true

  while :; do
    # `set -o noclobber` in a subshell is the shell's O_CREAT|O_EXCL: a
    # `[ -e ]` test followed by a write is a race, and a race here means two
    # runs inside one settings file. $$ is this script's pid even inside the
    # subshell, so the recorded owner is alive for the whole sequence.
    # stderr is CAPTURED rather than discarded: it is the only place the
    # reason for a failed creation exists, and telling a write restriction
    # apart from contention is the difference between an operator fixing a
    # permission and hunting a process that does not exist (found by T4.2
    # against a real target).
    if create_error="$( ( set -o noclobber; printf '%s:%s\n' "$$" "$(date +%s)" > "$LOCK_FILE" ) 2>&1 )"; then
      _LOCK_HELD=1
      return 0
    fi

    owner="$(_lock_owner_pid "$LOCK_FILE")"
    stale=0
    if [ -z "$owner" ]; then
      # Empty or unparseable, and NOT necessarily abandoned: creating the
      # file IS the acquisition and the pid line lands on the next
      # statement, so a live lock reads as empty for a moment. Reclaiming
      # that would put two runs inside one settings file (lock.py's
      # LOCK_GRACE, same reasoning and same two seconds).
      if [ "$(_lock_file_age "$LOCK_FILE")" -gt "$grace" ]; then
        stale=1
      fi
    else
      pid="${owner%% *}"
      stamp="${owner##* }"
      now="$(date +%s)"
      if [ "$(( now - stamp ))" -gt "$ttl" ]; then
        stale=1
      elif ! kill -0 "$pid" 2>/dev/null; then
        stale=1
      fi
    fi

    if [ "$stale" -eq 1 ]; then
      rm -f "$LOCK_FILE" 2>/dev/null || true
    fi

    attempts=$(( attempts + 1 ))
    # At least two attempts: reclaiming a stale lock takes one pass to
    # remove it and one to create it, so a zero timeout must not turn a
    # reclaimable lock into a spurious contention report.
    now="$(date +%s)"
    if [ "$attempts" -ge 2 ] && [ "$(( now - start ))" -ge "$timeout" ]; then
      # WHY THIS IS DECIDED FROM THE ATTEMPT AND NOT FROM A PRE-CHECK.
      # Testing whether the directory is writable and then acquiring opens a
      # window where the answer changes between the two, and the check would
      # have to run on the happy path as well -- paying for a diagnosis
      # nobody needs. The creation attempt is already the probe: noclobber
      # refuses with EEXIST when a lock is present and with EACCES/EPERM/
      # ENOENT when the file could not be made. Whether the lock file is
      # there NOW separates those two, and it is consulted only after the
      # decision to give up has been made, so a race here can change the
      # WORDING and never the outcome.
      #
      # The one shape this does not separate is an unwritable directory that
      # ALSO holds a lock: it reports contention, which is true as far as it
      # goes -- a lock is there and this run cannot have it -- while the
      # deeper cause is the permission. Named here rather than left as a
      # surprise.
      if [ -e "$LOCK_FILE" ]; then
        _LOCK_FAIL_REASON="contention"
      else
        _LOCK_FAIL_REASON="create"
        # Just the errno: the path is already in the caller's message, and
        # the shell prefixes its own "bash: line N: <path>: " to it.
        _LOCK_FAIL_DETAIL="${create_error##*: }"
      fi
      return 1
    fi
    sleep 0.1
  done
}

# Idempotent, and never removes a lock a LIVE foreign process holds.
_lock_release() {
  local owner pid
  [ -f "$LOCK_FILE" ] || return 0
  owner="$(_lock_owner_pid "$LOCK_FILE")"
  if [ -z "$owner" ]; then
    [ "$_LOCK_HELD" -eq 1 ] && rm -f "$LOCK_FILE" 2>/dev/null || true
    return 0
  fi
  pid="${owner%% *}"
  if [ "$pid" = "$$" ] || ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$LOCK_FILE" 2>/dev/null || true
  fi
  return 0
}

_on_exit() {
  # Runtime View step 9. On EVERY exit path, including an interrupted run:
  # git-setup's SKILL.md:174 makes the same point about leaving a dead-PID
  # lock behind.
  if [ "$_LOCK_HELD" -eq 1 ]; then
    _lock_release
  fi
}

# status never takes the lock: it writes nothing, and taking a lock would
# mean creating .claude/ in a target it only reads.
if [ "$VERB" != "status" ]; then
  trap _on_exit EXIT
  if ! _lock_acquire; then
    case "$_LOCK_FAIL_REASON" in
      create)
        _emit "ABORT" "could not create the lock file $LOCK_FILE (${_LOCK_FAIL_DETAIL:-no further detail}). No lock file is present and no other run is involved: this is a write restriction on that directory, or a missing parent. Nothing was written."
        ;;
      *)
        _emit "ABORT" "another observability setup run holds the lock $LOCK_FILE -- nothing was written. A lock held by a live process is never force-removed."
        ;;
    esac
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Runtime View step 3 — detect, read-only, and classify.
# ---------------------------------------------------------------------------

DETECT_OUTPUT=""
DETECT_STATUS=0
set +e
DETECT_OUTPUT="$(bash "$_DETECT_SH" "$REPO_ROOT" 2>&1)"
DETECT_STATUS=$?
set -e

printf '%s\n' "$DETECT_OUTPUT"

# The LABEL is the state channel detect.sh documents; the message after it is
# prose this dispatcher never branches on.
DETECT_LABEL="$(printf '%s\n' "$DETECT_OUTPUT" \
  | grep -E '^\[tcs-helper:observability-setup\] (CLEAN|CONFLICT|LEGACY|OURS-CURRENT|OURS-OLD|ABORT):' \
  | tail -n 1 \
  | sed -e 's/^\[tcs-helper:observability-setup\] //' -e 's/:.*$//')" || DETECT_LABEL=""

case "$DETECT_STATUS" in
  0|3|4) ;;
  *)
    # Every ABORT that reaches here is a refusal: the one ABORT state that is
    # NOT (not-a-repository) was already handled at step 1 and never gets
    # this far.
    _emit "ABORT" "Detection refused this target, so nothing was written. See the line above."
    exit 1
    ;;
esac

IS_OURS=0
case "$DETECT_LABEL" in
  OURS-CURRENT|OURS-OLD|LEGACY) IS_OURS=1 ;;
esac

# ---------------------------------------------------------------------------
# status — read-only, and the only verb that answers PRD F5's three states.
# ---------------------------------------------------------------------------

if [ "$VERB" = "status" ]; then
  # The drift comparator does NOT fetch the expected version itself (T1.3):
  # the two-line pattern below is bundle_install.sh:167 and is followed
  # rather than reinvented.
  EXPECTED_VERSION="$(_read_observability_bundle_version 2>/dev/null)" || EXPECTED_VERSION=""
  if [ -z "$EXPECTED_VERSION" ]; then
    _emit "ABORT" "could not read this plugin's own observability bundle version marker"
    exit 1
  fi
  DRIFT_RESULT="$(_drift_check_observability_bundle "$EXPECTED_VERSION")"
  case "$DRIFT_RESULT" in
    OK)
      _emit "BUNDLE" "installed at $BUNDLE_DIR, current ($EXPECTED_VERSION)."
      ;;
    MISSING)
      _emit "BUNDLE" "MISSING -- no bundle is installed at $BUNDLE_DIR (expected $EXPECTED_VERSION). Run: install --target $REPO_ROOT --yes"
      ;;
    DRIFT:*)
      _emit "BUNDLE" "DRIFT -- installed ${DRIFT_RESULT#DRIFT:} at $BUNDLE_DIR, expected $EXPECTED_VERSION. Run: install --target $REPO_ROOT --yes"
      ;;
    *)
      _emit "ABORT" "Unexpected drift-check result: $DRIFT_RESULT"
      exit 1
      ;;
  esac

  # The third state PRD F5 asks for needs BOTH channels. detect.sh reads the
  # target's settings and never looks for records; the record path knows
  # about records and nothing about registrations. Neither alone can tell
  # "configured but produced nothing" from "never configured".
  RECORD_PRESENT=0
  DATA_DIR=""
  if [ -n "$_LOGWRITE_SH" ]; then
    DATA_DIR="$(_observability_data_dir "$REPO_ROOT")" || DATA_DIR=""
  fi
  if [ -n "$DATA_DIR" ]; then
    RECORD_BASE="$DATA_DIR/observability/events.jsonl"
    # A record counts as present if the base file OR any rotated generation
    # survives -- the same concept as sources.py:_record_present, which
    # mirrors report.py's rotation_chain.
    for _suffix in "" ".1" ".2" ".3"; do
      if [ -f "$RECORD_BASE$_suffix" ]; then
        RECORD_PRESENT=1
        break
      fi
    done
    _emit "RECORDS" "$RECORD_BASE"
  else
    _emit "RECORDS" "could not resolve a record location for this target."
  fi

  if [ "$IS_OURS" -eq 0 ]; then
    _emit "STATUS" "not configured -- this feature has never registered here."
  elif [ "$RECORD_PRESENT" -eq 1 ]; then
    _emit "STATUS" "recording."
  else
    _emit "STATUS" "configured but silent -- registered here, and no record exists yet."
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# The foreign-entry stop (SDD-AC-4). Severity 3 from detection, exit 0 from
# the command: foreign content is a stop condition, not a failure.
# ---------------------------------------------------------------------------

if [ "$DETECT_LABEL" = "CONFLICT" ]; then
  _emit "STOP" "Foreign hook entries occupy the event names this feature registers, in $LOCAL_SETTINGS. Nothing was changed. Remove or relocate them and re-run, or leave this target unconfigured."
  exit 0
fi

IS_LEGACY=0
if [ "$DETECT_LABEL" = "LEGACY" ]; then
  IS_LEGACY=1
fi

# A legacy migration rewrites the SHARED settings file too, so that file's
# written-paths set has to clear the same version-control bar as the local
# one -- and before anything is planned against it, not after.
if [ "$IS_LEGACY" -eq 1 ]; then
  if ! _verify_paths_ignored "$SHARED_SETTINGS" "shared"; then
    exit 1
  fi
fi

_REGISTERED_EVENTS="InstructionsLoaded, PreToolUse, SubagentStart"
_ENV_SWITCH="CLAUDE_OBSERVABILITY_ENABLED"
_UNDO_HINT="bash $_SETUP_LIB_DIR/setup.sh remove --target $REPO_ROOT --yes"

# ---------------------------------------------------------------------------
# Runtime View step 5 — report the plan. Without --yes (or with --plan) this
# is where the run ends, having written nothing.
# ---------------------------------------------------------------------------

if [ "$VERB" = "install" ]; then
  _emit "PLAN" "would install the observability bundle into $BUNDLE_DIR"
  if [ "$IS_LEGACY" -eq 1 ]; then
    _emit "PLAN" "would remove the legacy in-repo registration from $SHARED_SETTINGS"
    _emit "PLAN" "would add hooks $_REGISTERED_EVENTS and env $_ENV_SWITCH to $LOCAL_SETTINGS"
  elif [ "$DETECT_LABEL" = "OURS-CURRENT" ]; then
    _emit "PLAN" "would leave $LOCAL_SETTINGS unchanged -- its registration is already current"
  else
    _emit "PLAN" "would add hooks $_REGISTERED_EVENTS and env $_ENV_SWITCH to $LOCAL_SETTINGS"
  fi
else
  if [ "$IS_LEGACY" -eq 1 ]; then
    _emit "PLAN" "would remove the legacy in-repo registration from $SHARED_SETTINGS"
  fi
  _emit "PLAN" "would remove hooks $_REGISTERED_EVENTS and env $_ENV_SWITCH from $LOCAL_SETTINGS"
fi

if [ "$APPLY" -eq 0 ]; then
  # Name the flag that is actually in the way. Telling someone who passed
  # --yes --plan to "re-run with --yes" asks them to do what they already did.
  if [ "$PLAN_ONLY" -eq 1 ]; then
    _emit "PLAN" "no file was written and no bundle installed. Drop --plan to apply."
  else
    _emit "PLAN" "no file was written and no bundle installed. Re-run with --yes to apply."
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# Runtime View steps 6 and 7 — install the bundle, then merge the settings.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# REPORTING WHAT HAPPENED, NOT WHAT THE BRANCH ASSUMED WOULD HAPPEN.
#
# Every line below that names an entry is branched on what registration.py
# actually said it did. The legacy install branch used to announce ADDED
# unconditionally, and a target that is BOTH legacy and already locally
# registered -- detect.sh returns LEGACY before it ever reaches the OURS
# check, so the compound state is real -- made that a false claim: the local
# half is a genuine no-op there and the settings file comes back
# byte-identical. Same defect class as this task's central one, so it gets
# the same treatment everywhere rather than a patch at the one site.
# ---------------------------------------------------------------------------

# _report_local_add <registration output> -- name the three entries only when
# the local half actually changed something.
_report_local_add() {
  case "$1" in
    *"already configured"*)
      _emit "INFO" "already configured -- nothing was changed in $LOCAL_SETTINGS."
      ;;
    *)
      _emit "ADDED" "hooks $_REGISTERED_EVENTS and env $_ENV_SWITCH in $LOCAL_SETTINGS"
      ;;
  esac
}

# _report_shared_strip <registration output> <label> <message> -- claim the
# shared half only when registration.py reported removing something.
#
# Unreachable today through this dispatcher: setup.sh passes a legacy flag
# only on a LEGACY classification, and detect.sh and registration.py agree on
# what that shape is. It is here because they are PAIRED DEFINITIONS kept in
# step by hand (LEGACY_SCRIPTS and LEGACY_NAMESPACE live in both), and the
# first thing a drift between them would produce is exactly this: a confident
# report of a removal that did not happen. No test constructs it, because
# constructing it means forcing the drift this guard exists to survive.
_report_shared_strip() {
  case "$1" in
    *"no legacy registration found"*)
      _emit "INFO" "no legacy registration was present in $SHARED_SETTINGS after all -- nothing was removed from it."
      ;;
    *)
      _emit "$2" "$3"
      ;;
  esac
}

_run_registration() {
  # registration.py holds its own lock by default; this process already owns
  # that lock across the whole sequence, so the child is told not to take it
  # again. Every invocation from here passes the flag.
  python3 "$_REGISTRATION_PY" --lock-held-by-caller "$@"
}

if [ "$VERB" = "install" ]; then
  # Step 6 first: the registration's commands point INTO the bundle, so a
  # settings file that referenced a bundle not yet on disk would name hooks
  # that fail open (exit 0, silent) and look like "ran, recorded nothing".
  if ! _install_observability_bundle; then
    _emit "ABORT" "the bundle install failed, so the registration was not touched."
    exit 1
  fi

  if [ "$IS_LEGACY" -eq 1 ]; then
    # Ruling (s): ONE operation, so recording is never simultaneously double
    # and never silently off. registration.py performs both halves inside a
    # single invocation, under the lock this process already holds -- the
    # removal from the shared file first, the standard registration second.
    # The order is deliberate and documented at the site that implements it:
    # the intermediate state is "not registered", which `status` reports
    # honestly; the reverse order's intermediate state records everything
    # twice while looking healthy.
    if ! REG_OUTPUT="$(_run_registration --settings "$LOCAL_SETTINGS" --migrate-legacy "$SHARED_SETTINGS" 2>&1)"; then
      printf '%s\n' "$REG_OUTPUT"
      _emit "ABORT" "the legacy migration failed. The lines above state exactly which files were changed, where each backup sits, and how to restore them."
      exit 1
    fi
    printf '%s\n' "$REG_OUTPUT"
    _report_shared_strip "$REG_OUTPUT" "MIGRATED" "removed the legacy in-repo registration from $SHARED_SETTINGS"
    _report_local_add "$REG_OUTPUT"
    _emit "UNDO" "$_UNDO_HINT"
    exit 0
  fi

  if ! REG_OUTPUT="$(_run_registration --settings "$LOCAL_SETTINGS" 2>&1)"; then
    printf '%s\n' "$REG_OUTPUT"
    _emit "ABORT" "the registration edit failed. The lines above state what was and was not written."
    exit 1
  fi
  printf '%s\n' "$REG_OUTPUT"

  _report_local_add "$REG_OUTPUT"
  _emit "UNDO" "$_UNDO_HINT"
  exit 0
fi

# remove ------------------------------------------------------------------
# Removal never touches the bundle at $HOME (other targets may still use it)
# and never touches a record: registration.py's remove path has no route to
# anything but the settings document it is given (PRD F2 -- stopping
# recording never deletes what was recorded).

if [ "$IS_LEGACY" -eq 1 ]; then
  # An un-migrated legacy target has its three LIVE hooks in the shared file.
  # Removing only the local registration would report success while all three
  # kept firing -- "off" to whoever asked, and on in fact. That is the same
  # silent-failure shape this whole spec exists to catch, so removal takes the
  # legacy entries too.
  if ! REG_OUTPUT="$(_run_registration --settings "$LOCAL_SETTINGS" --remove --remove-legacy "$SHARED_SETTINGS" 2>&1)"; then
    printf '%s\n' "$REG_OUTPUT"
    _emit "ABORT" "the removal failed. The lines above state exactly which files were changed, where each backup sits, and how to restore them."
    exit 1
  fi
  printf '%s\n' "$REG_OUTPUT"
  _report_shared_strip "$REG_OUTPUT" "REMOVED" "the legacy in-repo registration from $SHARED_SETTINGS"
else
  if ! REG_OUTPUT="$(_run_registration --settings "$LOCAL_SETTINGS" --remove 2>&1)"; then
    printf '%s\n' "$REG_OUTPUT"
    _emit "ABORT" "the removal failed. The lines above state what was and was not written."
    exit 1
  fi
  printf '%s\n' "$REG_OUTPUT"
fi

case "$REG_OUTPUT" in
  *"nothing to remove"*)
    _emit "INFO" "nothing to remove -- this feature had not registered in $LOCAL_SETTINGS."
    ;;
  *)
    _emit "REMOVED" "hooks $_REGISTERED_EVENTS and env $_ENV_SWITCH from $LOCAL_SETTINGS"
    ;;
esac
_emit "INFO" "Records already written are untouched. Re-enable with: bash $_SETUP_LIB_DIR/setup.sh install --target $REPO_ROOT --yes"
exit 0
