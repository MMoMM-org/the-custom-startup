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
  MARKER_FILE="$REPO_ROOT/plugins/tcs-helper/templates/observability/tcs-helper-observability-version"
  export REPO_ROOT BUILD_SH DETECT_SH MARKER_FILE

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
  printf '%s' "$1" | grep -qF "$2"
}

# _assert_not_contains <haystack> <needle> -- the `!` lives INSIDE this
# helper's own body, not as a bare statement in the test; calling the
# helper (whose own return status is what matters to the caller) trips
# `set -e` correctly, unlike `! cmd` typed directly in the test body noted
# in docs/ai/memory/active.md.
_assert_not_contains() {
  ! printf '%s' "$1" | grep -qF "$2"
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
  local local_settings="$protected/.claude/settings.local.json"
  local marker="$protected_home/.claude/observability/tcs-helper-observability-version"
  [ -f "$local_settings" ]
  [ -f "$marker" ]
  local before_local before_marker
  before_local="$(stat -f %m "$local_settings" 2>/dev/null || stat -c %Y "$local_settings")"
  before_marker="$(stat -f %m "$marker" 2>/dev/null || stat -c %Y "$marker")"

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

  local after_local after_marker
  after_local="$(stat -f %m "$local_settings" 2>/dev/null || stat -c %Y "$local_settings")"
  after_marker="$(stat -f %m "$marker" 2>/dev/null || stat -c %Y "$marker")"
  [ "$before_local" = "$after_local" ]
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
