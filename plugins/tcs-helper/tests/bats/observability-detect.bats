#!/usr/bin/env bats
#
# tests/bats/observability-detect.bats
#
# spec 019 (observability rollout across active repos), Phase 2, T2.2 --
# detect.sh classifies a target before this feature writes into it.
#
# Consumes T2.1's fixture matrix (fixtures/observability-settings/build.sh)
# and asserts, per fixture, the exact labelled state line and exit code
# detect.sh produces -- never directory existence alone.
#
# bash 3.2 compatible (CON-1): no `[[ =~ ]]` with PCRE classes or bounded
# quantifiers anywhere below.
#
# CRITICAL, newly measured: a bare `[[ "$x" == *pattern* ]]` used as a
# standalone statement does NOT trip bash's `set -e` when false, UNLESS it
# is the test body's last statement -- verified directly (bash -c 'set -e;
# [[ a == b ]]; echo reached' prints "reached"; the POSIX `[ ]`/`test` form
# does not have this hole). Every non-final bare `[[ ]]` substring check in
# this file would therefore pass silently no matter what detect.sh printed
# -- the exact vacuous-RED shape this task's own instructions warn about,
# generalising the existing `! cmd`-last-statement note in
# docs/ai/memory/active.md to `[[ ]]` itself. So every substring assertion
# below goes through _assert_contains/_assert_not_contains (grep -F, a
# plain command, which DOES trip set -e correctly regardless of position —
# verified the same way), and every exit-code check uses `[ ]`.

bats_require_minimum_version 1.5.0

setup_file() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../../../.." && pwd)"
  BUILD_SH="$REPO_ROOT/plugins/tcs-helper/tests/fixtures/observability-settings/build.sh"
  DETECT_SH="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/detect.sh"
  export REPO_ROOT BUILD_SH DETECT_SH

  # Isolate every git invocation this file makes (fixture build AND
  # detect.sh's own check-ignore calls) from the operator's real
  # global/system git config -- same as observability-settings-fixtures.bats.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  # macOS exports TMPDIR with a trailing slash; strip it so fixture paths
  # never carry a "//" (same normalization as observability-writer.bats /
  # observability-settings-fixtures.bats).
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done

  FIXTURES_PARENT="$(mktemp -d "$tmpbase/tcs-obs-detect-fixtures.XXXXXX")"
  FIXTURES_DIR="$("$BUILD_SH" "$FIXTURES_PARENT/fixtures")"
  export FIXTURES_PARENT FIXTURES_DIR
}

teardown_file() {
  if [ -n "${FIXTURES_PARENT:-}" ] && [ -d "$FIXTURES_PARENT" ]; then
    chmod -R u+rwX "$FIXTURES_PARENT" 2>/dev/null || true
    rm -rf "$FIXTURES_PARENT"
  fi
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# _run_detect <target_dir> [<env VAR=value> ...]
#
# Neutralises the developer's personal global git-ignore rule purely from
# the environment (plan/phase-2.md T2.2 -- measured on this machine:
# ~/.config/git/ignore contains **/.claude/settings.local.json, which would
# otherwise make write-path-not-ignored read as ignored). Production
# detect.sh calls PLAIN `git check-ignore`; this override lives ONLY in the
# test environment, never in detect.sh itself.
_run_detect() {
  local target="$1"
  shift
  run env \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null \
    "$@" \
    bash "$DETECT_SH" "$target"
}

# _assert_contains <haystack> <needle> -- fixed-string, via grep -F (a
# plain command, so it trips `set -e` correctly at any position -- see the
# header note; a bare `[[ ]]` does not).
_assert_contains() {
  # `--` so a needle that starts with a dash is a pattern, not an option.
  printf '%s' "$1" | grep -qF -- "$2"
}

# _assert_not_contains <haystack> <needle> -- the `!` lives INSIDE this
# helper's own body, not as a bare statement in the test; calling the
# helper (whose own return status is what matters to the caller) trips
# `set -e` correctly, unlike `! cmd` typed directly in the test body noted
# in docs/ai/memory/active.md.
_assert_not_contains() {
  ! printf '%s' "$1" | grep -qF -- "$2"
}

# _mtime <path> -- portable mtime (GNU stat first, BSD stat as the fallback).
# A helper rather than the shim inline: it appeared six times in one test,
# which is six chances for the copies to drift apart on a later edit.
#
# GNU-first, and the value is captured before the fallback is considered --
# both deliberate, because the obvious BSD-first one-liner
# (`stat -f %m "$1" 2>/dev/null || stat -c %Y "$1"`) is broken on Linux in a
# way that passes locally and fails only under load. GNU `stat -f` does not
# mean "format", it means FILESYSTEM: `stat -f %m file` prints a whole
# filesystem report to STDOUT and then exits non-zero, so the `||` fires and
# the real mtime is appended to that report rather than replacing it. The
# compared value then contains the filesystem's free-block counts, which
# change between two calls on a busy machine -- so a test asserting "this
# file was not touched" fails because the disk filled slightly, and the
# failure is invisible on macOS and on an idle Linux box.
# Recorded trap, docs/ai/memory/active.md: "a `|| fallback` inside `$( )`
# appends to partial output, not replaces it -- assign whole values".
_mtime() {
  local m
  m="$(stat -c %Y "$1" 2>/dev/null)" || m="$(stat -f %m "$1")"
  printf '%s' "$m"
}

# _count_state_lines <text> -- number of lines matching one of the six
# labelled state lines this script ever emits (never INFO).
_count_state_lines() {
  printf '%s\n' "$1" | grep -cE '^\[tcs-helper:observability-setup\] (CLEAN|CONFLICT|LEGACY|OURS-CURRENT|OURS-OLD|ABORT):'
}

# ---------------------------------------------------------------------------
# Gate 1: not a repository
# ---------------------------------------------------------------------------

@test "not-a-repository: ABORT, exit 2, nothing else runs" {
  _run_detect "$FIXTURES_DIR/not-a-repository"
  [ "$status" -eq 2 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "not inside a git repository"
  # Only one state line -- no CONFLICT/LEGACY/OURS line leaked past the gate.
  local lines
  lines="$(_count_state_lines "$output")"
  [ "$lines" -eq 1 ]
}

# ---------------------------------------------------------------------------
# Gate 2: write path not ignored by version control
# ---------------------------------------------------------------------------

@test "write-path-not-ignored: ABORT, exit 2, gate stops before any content read" {
  local repo="$FIXTURES_DIR/write-path-not-ignored"
  _run_detect "$repo"
  [ "$status" -eq 2 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "not ignored"
  # Never a content classification alongside the abort for the same target.
  _assert_not_contains "$output" "CLEAN"
  _assert_not_contains "$output" "CONFLICT"
  _assert_not_contains "$output" "LEGACY"
  _assert_not_contains "$output" "OURS"
}

@test "ignored-file-but-not-backup passes the gate (ignored by exact filename, not a directory rule)" {
  local repo="$FIXTURES_DIR/ignored-file-but-not-backup"
  _run_detect "$repo"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
}

# ---------------------------------------------------------------------------
# CLEAN
# ---------------------------------------------------------------------------

@test "absent: CLEAN, exit 0" {
  _run_detect "$FIXTURES_DIR/absent"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
}

@test "empty-object: CLEAN, exit 0" {
  _run_detect "$FIXTURES_DIR/empty-object"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
}

# ---------------------------------------------------------------------------
# CONFLICT -- foreign entries, named in the message
# ---------------------------------------------------------------------------

@test "foreign-only: CONFLICT, exit 3, names the foreign command" {
  _run_detect "$FIXTURES_DIR/foreign-only"
  [ "$status" -eq 3 ]
  _assert_contains "$output" "CONFLICT"
  _assert_contains "$output" "/opt/foreign-audit/hook.sh"
}

@test "same-event-names-populated: CONFLICT, names all three foreign commands, no OURS/LEGACY" {
  _run_detect "$FIXTURES_DIR/same-event-names-populated"
  [ "$status" -eq 3 ]
  _assert_contains "$output" "CONFLICT"
  _assert_contains "$output" "/opt/foreign-audit/on-load.sh"
  _assert_contains "$output" "/opt/foreign-audit/hook.sh"
  _assert_contains "$output" "/opt/foreign-audit/on-subagent.sh"
  _assert_not_contains "$output" "OURS"
  _assert_not_contains "$output" "LEGACY"
}

@test "non-ascii: CONFLICT, exit 3, and the non-ASCII bytes survive into the message uncorrupted" {
  _run_detect "$FIXTURES_DIR/non-ascii"
  [ "$status" -eq 3 ]
  _assert_contains "$output" "CONFLICT"
  _assert_contains "$output" "Café"
}

# ---------------------------------------------------------------------------
# OURS-CURRENT / OURS-OLD -- not observable from the settings file alone;
# depends on the paired <scenario>.home marker (ADR-5 / plan T2.2).
# ---------------------------------------------------------------------------

@test "foreign-plus-ours-current: OURS-CURRENT, exit 0" {
  local repo="$FIXTURES_DIR/foreign-plus-ours-current"
  local home="$FIXTURES_DIR/foreign-plus-ours-current.home"
  _run_detect "$repo" "_BUNDLE_INSTALL_TARGET_DIR=$home/.claude/observability"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "OURS-CURRENT"
  _assert_not_contains "$output" "OURS-OLD"
}

@test "foreign-plus-ours-older: OURS-OLD, exit 4" {
  local repo="$FIXTURES_DIR/foreign-plus-ours-older"
  local home="$FIXTURES_DIR/foreign-plus-ours-older.home"
  _run_detect "$repo" "_BUNDLE_INSTALL_TARGET_DIR=$home/.claude/observability"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "OURS-OLD"
  _assert_not_contains "$output" "OURS-CURRENT"
}

@test "foreign-plus-ours-current classified against the OLDER home reports OURS-OLD (proves the version comes from \$HOME, not the settings file)" {
  local repo="$FIXTURES_DIR/foreign-plus-ours-current"
  local older_home="$FIXTURES_DIR/foreign-plus-ours-older.home"
  _run_detect "$repo" "_BUNDLE_INSTALL_TARGET_DIR=$older_home/.claude/observability"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "OURS-OLD"
}

# ---------------------------------------------------------------------------
# LEGACY -- this repository's own real, hand-made state
# ---------------------------------------------------------------------------

@test "already-configured-observability: LEGACY, exit 4, never CLEAN and never a bare CONFLICT" {
  _run_detect "$FIXTURES_DIR/already-configured-observability"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "LEGACY"
  _assert_not_contains "$output" "CLEAN"
  _assert_not_contains "$output" "CONFLICT"
  _assert_not_contains "$output" "OURS"
}

# ---------------------------------------------------------------------------
# ABORT -- unparseable / wrong shape, each with a diagnosis (never a
# traceback reaching the user)
# ---------------------------------------------------------------------------

@test "malformed: ABORT, exit 2, diagnosis mentions JSON" {
  _run_detect "$FIXTURES_DIR/malformed"
  [ "$status" -eq 2 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "JSON"
}

@test "valid-json-wrong-shape: ABORT, exit 2, diagnosis names the offending key -- not a traceback" {
  _run_detect "$FIXTURES_DIR/valid-json-wrong-shape"
  [ "$status" -eq 2 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "hooks"
  _assert_not_contains "$output" "Traceback"
  _assert_not_contains "$output" "TypeError"
  _assert_not_contains "$output" "KeyError"
}

# ---------------------------------------------------------------------------
# Never writes anything -- and the read-only assertion exercises the real
# read paths (settings.local.json, settings.json, and the home marker),
# guarded with a write canary rather than an EUID check (this repo lives on
# a mounted volume, where chmod 555 may not bite).
# ---------------------------------------------------------------------------

@test "detect.sh creates no new file in an ORDINARY (writable) target" {
  # Complements the write-protected test below: a write guarded only by
  # `|| true` would fail silently under write-protection and could hide
  # behind that test alone -- catch it here, where nothing blocks a write
  # that detect.sh should not be attempting in the first place.
  local repo="$FIXTURES_PARENT/writable-canary-target"
  rm -rf "$repo"
  cp -pR "$FIXTURES_DIR/foreign-plus-ours-current" "$repo"

  local before after
  before="$(find "$repo" -type f | sort)"
  _run_detect "$repo" "_BUNDLE_INSTALL_TARGET_DIR=$FIXTURES_DIR/foreign-plus-ours-current.home/.claude/observability"
  [ "$status" -eq 0 ]
  after="$(find "$repo" -type f | sort)"
  [ "$before" = "$after" ]

  rm -rf "$repo"
}

@test "detect.sh writes nothing, even on a target exercising all three read paths" {
  local src="$FIXTURES_DIR/foreign-plus-ours-current"
  local src_home="$FIXTURES_DIR/foreign-plus-ours-current.home"
  local protected="$FIXTURES_PARENT/write-protected-target"
  local protected_home="$FIXTURES_PARENT/write-protected-home"

  rm -rf "$protected" "$protected_home"
  cp -pR "$src" "$protected"
  cp -pR "$src_home" "$protected_home"

  # Snapshot mtimes of every file detect.sh might touch, before locking down
  # write access.
  # The fixture ships settings.local.json and the marker, but NO
  # settings.json -- so load(shared_path) used to return at os.path.isfile()
  # without ever opening a file, leaving the shared read path unexercised.
  # That is the phase-1 defect the pin names, so the file is added here.
  # It is added in the test rather than in build.sh on purpose: T2.1 asserts
  # fixtures 4 and 5 are byte-identical, and giving one of them an extra file
  # would break that identity.
  # Its content is foreign and deliberately NOT the legacy shape, so the
  # classification stays OURS-CURRENT -- which also means the marker under
  # the overridden home must still be read to tell CURRENT from OLD.
  local shared_settings="$protected/.claude/settings.json"
  cat > "$shared_settings" <<'SHAREDJSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/unrelated-third-party.sh"
          }
        ]
      }
    ]
  }
}
SHAREDJSON
  # Keep it no newer than the fixture tree, or the structural "nothing was
  # created" find below would report this very file.
  touch -r "$FIXTURES_DIR" "$shared_settings"

  local local_settings="$protected/.claude/settings.local.json"
  local marker="$protected_home/.claude/observability/tcs-helper-observability-version"
  [ -f "$local_settings" ]
  [ -f "$shared_settings" ]
  [ -f "$marker" ]
  local before_local before_shared before_marker
  before_local="$(_mtime "$local_settings")"
  before_shared="$(_mtime "$shared_settings")"
  before_marker="$(_mtime "$marker")"

  chmod -R a-w "$protected" "$protected_home"

  if echo "canary" > "$protected/.claude/test-write" 2>/dev/null; then
    chmod -R u+w "$protected" "$protected_home"
    rm -rf "$protected" "$protected_home"
    skip "write-protected directory is actually writable (running as root, or chmod does not bite on this volume?)"
  fi

  _run_detect "$protected" "_BUNDLE_INSTALL_TARGET_DIR=$protected_home/.claude/observability"
  local detect_status="$status" detect_output="$output"

  chmod -R u+w "$protected" "$protected_home"

  # The write-protection did not block detection from doing its job: a real
  # classification came back, not a permission error masquerading as ABORT.
  [ "$detect_status" -eq 0 ]
  _assert_contains "$detect_output" "OURS-CURRENT"

  local after_local after_shared after_marker
  after_local="$(_mtime "$local_settings")"
  after_shared="$(_mtime "$shared_settings")"
  after_marker="$(_mtime "$marker")"
  [ "$before_local" = "$after_local" ]
  [ "$before_shared" = "$after_shared" ]
  [ "$before_marker" = "$after_marker" ]

  # No file was created inside the target either (backup, temp, canary, or
  # otherwise) -- structural check, not just "the two files above are
  # untouched".
  run find "$protected" -newer "$FIXTURES_DIR" -type f
  [ "$status" -eq 0 ]
  [ -z "$output" ]

  rm -rf "$protected" "$protected_home"
}

# ---------------------------------------------------------------------------
# set -u safety: the documented default form (no argument) must not abort
# under set -u.
# ---------------------------------------------------------------------------

@test "under write protection the shared settings.json is genuinely read, not silently skipped" {
  # The test above proves all three paths are present and readable. It cannot
  # prove the shared one was actually opened: if open() failed on it, load()
  # returns (None, err), legacy_events(None) is empty, and the classification
  # falls through to OURS-CURRENT -- the same answer as a successful read.
  #
  # This target's settings.json carries the legacy shape, which only changes
  # the answer if the file is opened AND parsed. A skipped or failed read
  # reports something other than LEGACY, so the assertion below has teeth.
  local protected="$FIXTURES_PARENT/write-protected-legacy"
  rm -rf "$protected"
  cp -pR "$FIXTURES_DIR/already-configured-observability" "$protected"

  [ -f "$protected/.claude/settings.json" ]

  chmod -R a-w "$protected"

  if echo "canary" > "$protected/.claude/test-write" 2>/dev/null; then
    chmod -R u+w "$protected"
    rm -rf "$protected"
    skip "write-protected directory is actually writable (running as root, or chmod does not bite on this volume?)"
  fi

  _run_detect "$protected"
  local detect_status="$status" detect_output="$output"

  chmod -R u+w "$protected"

  [ "$detect_status" -eq 4 ]
  _assert_contains "$detect_output" "LEGACY"
  _assert_not_contains "$detect_output" "OURS-CURRENT"
  _assert_not_contains "$detect_output" "cannot read"

  run find "$protected" -newer "$FIXTURES_DIR" -type f
  [ "$status" -eq 0 ]
  [ -z "$output" ]

  rm -rf "$protected"
}

@test "a missing sibling library aborts with a state line, not a silent exit 1" {
  # Unguarded under `set -e`, sourcing drift_check.sh killed the script with
  # exit 1 and no output whatsoever -- violating both "exactly one state line
  # per run" and the documented 0/2/3/4 exit range, leaving T4.1's caller with
  # nothing to branch on. Reachable in practice: this repo's own documented
  # workflow hand-copies skill directories between two locations.
  local orphan="$FIXTURES_PARENT/orphan-lib"
  rm -rf "$orphan"
  mkdir -p "$orphan"
  cp "$DETECT_SH" "$orphan/detect.sh"

  run env \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null \
    bash "$orphan/detect.sh" "$FIXTURES_DIR/absent"

  [ "$status" -eq 2 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "drift_check.sh"
  [ "$(_count_state_lines "$output")" -eq 1 ]

  rm -rf "$orphan"
}

@test "an unreadable settings file reports that it cannot be read, not that it is invalid JSON" {
  # load() distinguished OSError from JSONDecodeError internally, but both
  # arrived on the bash side as ABORT_MALFORMED and were reported as "is not
  # valid JSON" -- sending whoever debugs it looking for a syntax error in a
  # file they cannot open.
  local target="$FIXTURES_PARENT/unreadable-settings"
  rm -rf "$target"
  cp -pR "$FIXTURES_DIR/foreign-only" "$target"
  local settings="$target/.claude/settings.local.json"
  [ -f "$settings" ]

  chmod 000 "$settings"
  if cat "$settings" >/dev/null 2>&1; then
    chmod u+rw "$settings"
    rm -rf "$target"
    skip "unreadable file is still readable (running as root, or chmod does not bite on this volume?)"
  fi

  _run_detect "$target"
  local detect_status="$status" detect_output="$output"

  chmod u+rw "$settings"
  rm -rf "$target"

  [ "$detect_status" -eq 2 ]
  _assert_contains "$detect_output" "ABORT"
  _assert_contains "$detect_output" "cannot be read"
  _assert_not_contains "$detect_output" "is not valid JSON"
  [ "$(_count_state_lines "$detect_output")" -eq 1 ]
}

@test "detect.sh with no argument (documented default = cwd) runs cleanly under set -u" {
  run env \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null \
    bash -c 'set -u; cd "$1" && bash "$2"' -- "$FIXTURES_DIR/absent" "$DETECT_SH"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
}

@test "detect.sh sourced under /bin/bash (bash 3.2) with set -u and no argument does not abort on \${1:-}" {
  run /bin/bash -c 'set -u; cd "$1" && bash "$2"' -- "$FIXTURES_DIR/absent" "$DETECT_SH"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
}

# ---------------------------------------------------------------------------
# One labelled STATE line per target, everywhere -- never two.
# ---------------------------------------------------------------------------

@test "every classification emits exactly one state line" {
  local fixture
  for fixture in absent empty-object foreign-only same-event-names-populated \
                 non-ascii malformed valid-json-wrong-shape \
                 already-configured-observability not-a-repository \
                 ignored-file-but-not-backup write-path-not-ignored; do
    _run_detect "$FIXTURES_DIR/$fixture"
    local lines
    lines="$(_count_state_lines "$output")"
    [ "$lines" -eq 1 ]
  done
}

# ---------------------------------------------------------------------------
# PARTIAL LEGACY SHAPES -- maintainer ruling (x), 2026-09-11.
#
# is_legacy required all three events to match, so any partial shape came back
# CLEAN. That is the dangerous direction: install then adds a full
# registration beside still-live legacy hooks and the target records twice,
# which is the state the migration exists to prevent, and remove reports
# success while those hooks keep firing. One or more legacy entries now
# classifies LEGACY; zero still classifies CLEAN.
#
# Lowering the threshold from three to one forces a second change. Matching
# used to be `command.endswith("log_skill.sh")`, which a third party's own
# log_skill.sh satisfies -- harmless-ish when all three had to match, and a
# licence to delete someone else's hook the moment one match is enough. The
# match is now the legacy NAMESPACE (ADR-5's rule applied to the legacy
# shape), which is what makes one-is-enough safe.
# ---------------------------------------------------------------------------

# _shared_variant <name> -- a copy of already-configured-observability whose
# shared settings.json is rewritten by the python on stdin. Prints the path.
_shared_variant() {
  local dest="$FIXTURES_PARENT/variant-$1"
  rm -rf "$dest"
  cp -pR "$FIXTURES_DIR/already-configured-observability" "$dest"
  python3 - "$dest/.claude/settings.json"
  printf '%s\n' "$dest"
}

@test "partial legacy: a non-string command replacing one of the trio still classifies LEGACY" {
  local dir
  dir="$(_shared_variant nonstring <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["hooks"]["PreToolUse"] = [{"matcher": "", "hooks": [{"type": "command", "command": 123}]}]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  _run_detect "$dir"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "LEGACY"
  _assert_not_contains "$output" "CLEAN"
}

@test "partial legacy: one event simply absent still classifies LEGACY, and names what it found" {
  local dir
  dir="$(_shared_variant absent-event <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
del d["hooks"]["SubagentStart"]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  _run_detect "$dir"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "LEGACY"
  # The message names the events actually found rather than implying three.
  _assert_contains "$output" "InstructionsLoaded"
  _assert_contains "$output" "PreToolUse"
  _assert_not_contains "$output" "SubagentStart"
}

@test "partial legacy: a single legacy entry is enough to classify LEGACY" {
  local dir
  dir="$(_shared_variant only-one <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
for ev in ("PreToolUse", "SubagentStart"):
    del d["hooks"][ev]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  _run_detect "$dir"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "LEGACY"
  _assert_contains "$output" "InstructionsLoaded"
}

@test "partial legacy: legacy hooks without the env flag still classify LEGACY" {
  local dir
  dir="$(_shared_variant no-env <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
del d["env"]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  # The env flag was a GATE, so removing it by hand turned three live legacy
  # hooks into a CLEAN target -- another door to the same double-recording
  # room. With ownership proven by the namespace, the flag corroborates and
  # no longer gates.
  _run_detect "$dir"
  [ "$status" -eq 4 ]
  _assert_contains "$output" "LEGACY"
}

@test "zero legacy entries still classify CLEAN -- a fully stripped shared file is not a partial one" {
  local dir
  dir="$(_shared_variant stripped <<'PY'
import json, sys
p = sys.argv[1]
json.dump({}, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  # This is exactly the state a PARTIAL MIGRATION leaves behind. There is
  # nothing legacy left to migrate, so LEGACY would be a lie and would send
  # setup down a migration path with nothing to remove.
  _run_detect "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
  _assert_not_contains "$output" "LEGACY"
}

@test "the env flag alone, with no hooks at all, classifies CLEAN" {
  local dir
  dir="$(_shared_variant env-only <<'PY'
import json, sys
p = sys.argv[1]
json.dump({"env": {"CLAUDE_OBSERVABILITY_ENABLED": "1"}}, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  _run_detect "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
  _assert_not_contains "$output" "LEGACY"
}

@test "a third party's own log_skill.sh is never mistaken for a legacy entry" {
  local dir
  dir="$(_shared_variant third-party <<'PY'
import json, sys
p = sys.argv[1]
json.dump({
    "env": {"CLAUDE_OBSERVABILITY_ENABLED": "1"},
    "hooks": {"PreToolUse": [{"matcher": "", "hooks": [
        {"type": "command", "command": "\"/opt/other-tool/log_skill.sh\""}]}]},
}, open(p, "w", encoding="utf-8"), indent=2)
PY
)"
  # Matching on the script BASENAME would claim this, and once one match is
  # enough that claim becomes a deletion. Ownership is the namespace.
  _run_detect "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "CLEAN"
  _assert_not_contains "$output" "LEGACY"
}
