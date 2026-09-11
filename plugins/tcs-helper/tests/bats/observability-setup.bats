#!/usr/bin/env bats
#
# tests/bats/observability-setup.bats
#
# spec 019 (observability rollout across active repos), Phase 4, T4.1 --
# the verb dispatcher `lib/setup.sh`, which is the command a person invokes.
#
# EVERY assertion in this file goes through setup.sh. detect.sh and
# registration.py are never called directly from here, deliberately: T4.1
# step 4 requires the command be "exercised through its real entry point,
# not by calling its libraries directly", and the defect class this file
# exists to catch lives in the TRANSLATION setup.sh performs -- detect.sh's
# severity channel into a command-level exit status -- not in either
# library's own behaviour. Their own suites (observability-detect.bats,
# observability-registration-matrix.bats, tests/tcs-helper/
# test_observability_registration.py) cover them directly and stay the place
# to assert library behaviour.
#
# THE MAPPING THIS FILE PINS ROW BY ROW. detect.sh's header states that "the
# exit code carries SEVERITY ONLY -- state and severity are two separate
# channels", and it exits 2 for FOUR semantically different ABORT states:
# not-a-repository, unparseable, valid-json-wrong-shape and
# write-path-not-ignored. The SDD assigns those different command-level
# outcomes (non-repo -> exit 0; unparseable -> exit non-zero), so the
# dispatcher cannot map severity alone. It resolves this by ORDERING, not by
# reading ABORT prose: setup.sh resolves the toplevel itself, before the lock
# and before detect.sh, so a non-repository never reaches detection and every
# remaining exit 2 is a genuine refusal.
#
#   setup.sh's own toplevel resolution fails  -> STOP,   exit 0
#   detect exit 0, CLEAN / OURS-CURRENT       -> proceed, exit 0
#   detect exit 4, OURS-OLD / LEGACY          -> proceed, exit 0
#   detect exit 3, CONFLICT                   -> STOP,   exit 0
#   detect exit 2, any ABORT                  -> ABORT,  exit non-zero
#
# The unparseable-vs-non-repository pair below is the assertion that catches
# a dispatcher mapping "any ABORT -> 0": such a dispatcher passes every other
# test in this file.
#
# bash 3.2 compatible (CON-1): no `[[ =~ ]]` with PCRE classes or bounded
# quantifiers. Every substring assertion goes through _assert_contains /
# _assert_not_contains (grep -F, a plain command -- trips `set -e` correctly
# at any position in a test body, unlike a bare `[[ ]]` used as a non-final
# statement; see docs/ai/memory/active.md). `timeout` is never used (absent
# on macOS).
#
# NEVER AGAINST A REAL REPOSITORY, AND NEVER AGAINST A REAL $HOME: every
# target is a throwaway copy of a build.sh fixture under $TMPDIR, and every
# invocation runs with HOME pointed at a per-test temporary directory, so
# the bundle install (Runtime View step 6) can never touch the operator's
# own ~/.claude/.

bats_require_minimum_version 1.5.0

setup_file() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../../../.." && pwd)"
  BUILD_SH="$REPO_ROOT/plugins/tcs-helper/tests/fixtures/observability-settings/build.sh"
  SETUP_SH="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/setup.sh"
  MARKER_FILE="$REPO_ROOT/plugins/tcs-helper/templates/observability/tcs-helper-observability-version"
  export REPO_ROOT BUILD_SH SETUP_SH MARKER_FILE

  # The plugin's own current bundle version -- read, never hardcoded, so a
  # marker bump does not silently turn the drift assertions green.
  CURRENT_BUNDLE_VERSION="$(cat "$MARKER_FILE")"
  export CURRENT_BUNDLE_VERSION

  # Isolate every git invocation (fixture build AND setup.sh's own
  # rev-parse/check-ignore) from the operator's real global/system config.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  # macOS exports TMPDIR with a trailing slash; strip it so no fixture path
  # carries a "//" (same normalization as the sibling fixture consumers).
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done

  FIXTURES_PARENT="$(mktemp -d "$tmpbase/tcs-obs-setup-fixtures.XXXXXX")"
  FIXTURES_DIR="$("$BUILD_SH" "$FIXTURES_PARENT/fixtures")"
  WORK_PARENT="$(mktemp -d "$tmpbase/tcs-obs-setup-work.XXXXXX")"
  export FIXTURES_PARENT FIXTURES_DIR WORK_PARENT
}

teardown_file() {
  local d
  for d in "${FIXTURES_PARENT:-}" "${WORK_PARENT:-}"; do
    if [ -n "$d" ] && [ -d "$d" ]; then
      chmod -R u+rwX "$d" 2>/dev/null || true
      rm -rf "$d"
    fi
  done
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_assert_contains() {
  printf '%s' "$1" | grep -qF -- "$2"
}

_assert_not_contains() {
  ! printf '%s' "$1" | grep -qF -- "$2"
}

_assert_bytes_equal() {
  cmp -s "$1" "$2"
}

_assert_bytes_differ() {
  ! cmp -s "$1" "$2"
}

# _copy_fixture <fixture-name> <work-name> -- a fresh, independent copy,
# since setup.sh mutates its target in place.
_copy_fixture() {
  local fixture="$1" workname="$2"
  local dest="$WORK_PARENT/$workname"
  rm -rf "$dest"
  cp -pR "$FIXTURES_DIR/$fixture" "$dest"
  printf '%s\n' "$dest"
}

# _new_home <work-name> -- a private $HOME for one test, so the bundle
# install lands somewhere disposable and two tests never share a marker.
_new_home() {
  local home="$WORK_PARENT/$1.home"
  rm -rf "$home"
  mkdir -p "$home"
  printf '%s\n' "$home"
}

# _home_with_bundle_version <work-name> <version> -- a private $HOME that
# already carries an installed bundle marker at <version>, for the drift
# assertions.
_home_with_bundle_version() {
  local home; home="$(_new_home "$1")"
  mkdir -p "$home/.claude/observability"
  printf '%s\n' "$2" > "$home/.claude/observability/tcs-helper-observability-version"
  printf '%s\n' "$home"
}

# _run_setup <home> <verb> <target> [args...]
#
# The ONLY way this file reaches the feature. The check-ignore override
# neutralises the DEVELOPER's personal global ignore rule (this machine's
# ~/.config/git/ignore carries **/.claude/settings.local.json, which would
# otherwise make write-path-not-ignored read as ignored) purely from the
# environment -- production code calls plain `git check-ignore`, exactly as
# observability-detect.bats documents.
_run_setup() {
  local home="$1" verb="$2" target="$3"
  shift 3
  run env \
    HOME="$home" \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null \
    bash "$SETUP_SH" "$verb" --target "$target" "$@"
}

# _run_setup_env <home> <extra env assignment> <verb> <target> [args...]
_run_setup_env() {
  local home="$1" extra="$2" verb="$3" target="$4"
  shift 4
  run env \
    HOME="$home" \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null \
    "$extra" \
    bash "$SETUP_SH" "$verb" --target "$target" "$@"
}

# _count_our_hooks <file> -- how many entries in the file point into our
# $HOME namespace. 0 on an absent file rather than an error.
_count_our_hooks() {
  if [ ! -f "$1" ]; then printf '0'; return 0; fi
  grep -c -F '$HOME/.claude/observability/' "$1" || true
}

# _assert_git_clean <repo> -- the property T4.2 and T4.4 check, and a
# stronger one than "the settings file does not exist": nothing this command
# did is visible to version control. The excludesFile override is deliberate
# -- without it the DEVELOPER's personal global ignore could mask a file this
# feature left behind, which is the opposite of what this assertion is for.
_assert_git_clean() {
  run git -c core.excludesFile=/dev/null -C "$1" status --porcelain
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# _assert_no_lock <repo> -- no run may leave the per-target lock behind, on
# ANY exit path. `trap _on_exit EXIT` is what guarantees it, and it fires the
# same on an abort, a refusal and a plan run as on a success. Until this
# helper only the two success-path cases touched the lock at all, so a trap
# that stopped firing would have left every failure path holding one and
# nothing would have gone red -- the same shape as every other defect this
# spec has turned up.
_assert_no_lock() {
  [ ! -e "$1/.claude/settings.local.json.tcs-observability.lock" ]
}

# _write_local <repo> <json> -- put a hand-built document in the target's
# local settings file, creating .claude/ if the fixture has none.
_write_local() {
  mkdir -p "$1/.claude"
  printf '%s\n' "$2" > "$1/.claude/settings.local.json"
}

# _make_record <dir> -- a record file where _observability_data_dir would
# put one, for the three-state liveness assertions.
_make_record() {
  mkdir -p "$1/observability"
  printf '%s\n' '{"kind":"skill","repo":"fixture"}' > "$1/observability/events.jsonl"
}

# ---------------------------------------------------------------------------
# Usage / dispatch
# ---------------------------------------------------------------------------

@test "an unknown verb is refused with a usage message and a non-zero status" {
  local home; home="$(_new_home unknown-verb)"
  local dir; dir="$(_copy_fixture absent unknown-verb)"
  _run_setup "$home" frobnicate "$dir"
  [ "$status" -ne 0 ]
  _assert_contains "$output" "install"
  _assert_contains "$output" "remove"
  _assert_contains "$output" "status"
}

@test "a missing --target is refused with a non-zero status" {
  local home; home="$(_new_home missing-target)"
  run env HOME="$home" bash "$SETUP_SH" install
  [ "$status" -ne 0 ]
  _assert_contains "$output" "--target"
}

# ---------------------------------------------------------------------------
# Journey 1 -- install
# ---------------------------------------------------------------------------

@test "install on a clean target registers, names the entries it added, and exits 0" {
  local home dir target
  home="$(_new_home install-clean)"
  dir="$(_copy_fixture absent install-clean)"
  target="$dir/.claude/settings.local.json"
  [ ! -e "$target" ]

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  # F1: the report names which entries were added.
  _assert_contains "$output" "InstructionsLoaded"
  _assert_contains "$output" "PreToolUse"
  _assert_contains "$output" "SubagentStart"
  _assert_contains "$output" "CLAUDE_OBSERVABILITY_ENABLED"

  [ -f "$target" ]
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
}

@test "install writes the bundle and its version marker into the resolved HOME" {
  local home dir
  home="$(_new_home install-bundle)"
  dir="$(_copy_fixture absent install-bundle)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  [ -f "$home/.claude/observability/logwrite.sh" ]
  [ -f "$home/.claude/observability/log_skill.sh" ]
  [ -f "$home/.claude/observability/tcs-helper-observability-version" ]
  run cat "$home/.claude/observability/tcs-helper-observability-version"
  [ "$output" = "$CURRENT_BUNDLE_VERSION" ]
}

@test "the install summary names how to undo the change" {
  local home dir
  home="$(_new_home install-undo)"
  dir="$(_copy_fixture absent install-undo)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  # PRD F1: "the report of what changed includes how to undo it".
  _assert_contains "$output" "remove --target"
}

@test "re-running install changes nothing and reports the target as already configured" {
  local home dir target before
  home="$(_new_home install-idempotent)"
  dir="$(_copy_fixture absent install-idempotent)"
  target="$dir/.claude/settings.local.json"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  before="$WORK_PARENT/install-idempotent.after-first"
  cp -p "$target" "$before"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "already configured"
  # ...and does NOT claim it added anything. A report that names the three
  # entries on every run is indistinguishable from one that named them
  # because they were actually written, which is the whole point of F1.
  _assert_not_contains "$output" "ADDED"
  _assert_bytes_equal "$before" "$target"
}

@test "the first run against a clean target does not report itself as a foreign install" {
  local home dir
  home="$(_new_home no-self-conflict)"
  dir="$(_copy_fixture absent no-self-conflict)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_not_contains "$output" "CONFLICT"
  _assert_not_contains "$output" "Foreign hook entries"
}

# ---------------------------------------------------------------------------
# The plan step -- and "declining at the confirmation", pinned at the layer
# that is testable. Ruling (r) keeps the literal interactive confirm in
# SKILL.md prose, which bats cannot exercise; the dispatcher's no-write path
# is its mechanical equivalent, so a decline IS "no --yes".
# ---------------------------------------------------------------------------

@test "install without --yes reports the plan and writes nothing (the decline path)" {
  local home dir target
  home="$(_new_home plan-no-yes)"
  dir="$(_copy_fixture absent plan-no-yes)"
  target="$dir/.claude/settings.local.json"

  _run_setup "$home" install "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "PLAN"
  # Nothing anywhere: not the settings file, not the bundle.
  [ ! -e "$target" ]
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "install --plan reports the plan and writes nothing even when --yes is given" {
  local home dir target
  home="$(_new_home plan-explicit)"
  dir="$(_copy_fixture absent plan-explicit)"
  target="$dir/.claude/settings.local.json"

  _run_setup "$home" install "$dir" --yes --plan
  [ "$status" -eq 0 ]
  _assert_contains "$output" "PLAN"
  [ ! -e "$target" ]
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "the plan names the settings file it would change and the bundle directory it would install" {
  local home dir
  home="$(_new_home plan-names)"
  dir="$(_copy_fixture absent plan-names)"

  _run_setup "$home" install "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" ".claude/settings.local.json"
  _assert_contains "$output" "$home/.claude/observability"
}

@test "remove without --yes reports the plan and writes nothing" {
  local home dir target after_install
  home="$(_new_home remove-plan)"
  dir="$(_copy_fixture absent remove-plan)"
  target="$dir/.claude/settings.local.json"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  after_install="$WORK_PARENT/remove-plan.after-install"
  cp -p "$target" "$after_install"

  _run_setup "$home" remove "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "PLAN"
  _assert_bytes_equal "$after_install" "$target"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# Journey 2 -- the foreign-entry stop. SDD-AC-4.
# ---------------------------------------------------------------------------

@test "a foreign entry under one of our event names stops install, unchanged, at exit 0" {
  local home dir target original
  home="$(_new_home foreign-stop)"
  dir="$(_copy_fixture same-event-names-populated foreign-stop)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/foreign-stop.orig"
  cp -p "$target" "$original"

  _run_setup "$home" install "$dir" --yes
  # detect.sh signals CONFLICT with severity 3; the command must map that
  # to 0 -- foreign content is a stop condition, not a failure.
  [ "$status" -eq 0 ]
  _assert_bytes_equal "$original" "$target"
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "the foreign-entry stop reports precisely what it found and where" {
  local home dir
  home="$(_new_home foreign-report)"
  dir="$(_copy_fixture same-event-names-populated foreign-report)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "/opt/foreign-audit/hook.sh"
  _assert_contains "$output" ".claude/settings.local.json"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# The exit-code mapping's two ABORT-severity halves, asserted as a PAIR.
# Both come back from detect.sh as exit 2; the SDD gives them opposite
# command-level statuses. A dispatcher that maps severity alone gets one of
# these wrong no matter which way it guesses.
# ---------------------------------------------------------------------------

@test "a target that is not a repository is reported, writes nothing, and exits 0" {
  local home dir
  home="$(_new_home non-repo)"
  dir="$(_copy_fixture not-a-repository non-repo)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "not"
  _assert_contains "$output" "repository"
  [ ! -e "$dir/.claude" ]
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "an unparseable settings file is reported as unreadable, writes nothing, and exits NON-ZERO" {
  local home dir target original
  home="$(_new_home unparseable)"
  dir="$(_copy_fixture malformed unparseable)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/unparseable.orig"
  cp -p "$target" "$original"

  _run_setup "$home" install "$dir" --yes
  # THE assertion that catches "any ABORT -> exit 0": this one is a genuine
  # refusal and the non-repository case above is not.
  [ "$status" -ne 0 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "not valid JSON"
  _assert_bytes_equal "$original" "$target"
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "a valid-JSON-wrong-shape settings file is refused with a non-zero status and nothing written" {
  local home dir target original
  home="$(_new_home wrong-shape)"
  dir="$(_copy_fixture valid-json-wrong-shape wrong-shape)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/wrong-shape.orig"
  cp -p "$target" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "unexpected shape"
  _assert_bytes_equal "$original" "$target"
  _assert_no_lock "$dir"
}

@test "a write path version control does not ignore is refused with a non-zero status" {
  local home dir
  home="$(_new_home not-ignored)"
  dir="$(_copy_fixture write-path-not-ignored not-ignored)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "ignored"
  [ ! -e "$dir/.claude/settings.local.json" ]
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "a target that ignores the settings file but not its backup is refused, naming the backup path" {
  local home dir target original
  home="$(_new_home backup-not-ignored)"
  dir="$(_copy_fixture ignored-file-but-not-backup backup-not-ignored)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/backup-not-ignored.orig"
  cp -p "$target" "$original"

  # detect.sh passes this target -- it gates the settings path alone. The
  # command's step 4 covers every path registration.py can write, which is
  # what keeps a committable .bak out of a repository we do not own.
  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" ".tcs-observability.bak"
  _assert_bytes_equal "$original" "$target"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# The lock, taken before detection (Runtime View step 2).
# ---------------------------------------------------------------------------

@test "a lock held by a live process stops the run without writing and without removing the lock" {
  local home dir target lock
  home="$(_new_home locked)"
  dir="$(_copy_fixture absent locked)"
  target="$dir/.claude/settings.local.json"
  lock="$target.tcs-observability.lock"

  mkdir -p "$dir/.claude"
  # $$ is this bats process: a genuinely live owner, so the run must not
  # reclaim it. A zero wait keeps the test fast without a `timeout` binary.
  printf '%s:%s\n' "$$" "$(date +%s)" > "$lock"

  _run_setup_env "$home" "TCS_OBSERVABILITY_LOCK_TIMEOUT=0" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "lock"
  [ ! -e "$target" ]
  [ -f "$lock" ]
  run cat "$lock"
  _assert_contains "$output" "$$"
}

@test "a completed install leaves no lock file behind" {
  local home dir target
  home="$(_new_home lock-released)"
  dir="$(_copy_fixture absent lock-released)"
  target="$dir/.claude/settings.local.json"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  [ ! -e "$target.tcs-observability.lock" ]
}

# ---------------------------------------------------------------------------
# Journey 3 -- remove. PRD F2.
# ---------------------------------------------------------------------------

@test "remove takes out the entries setup authored and reports which" {
  local home dir target
  home="$(_new_home remove-ours)"
  dir="$(_copy_fixture absent remove-ours)"
  target="$dir/.claude/settings.local.json"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "InstructionsLoaded"
  _assert_contains "$output" "PreToolUse"
  _assert_contains "$output" "SubagentStart"
  run _count_our_hooks "$target"
  [ "$output" -eq 0 ]
}

@test "remove leaves foreign entries standing" {
  local home dir target
  home="$(_new_home remove-foreign)"
  dir="$(_copy_fixture absent remove-foreign)"
  target="$dir/.claude/settings.local.json"

  # The foreign entry is added AFTER install, not before: detection refuses
  # to install into a target that already carries one (see the stop tests
  # above), so this is the only ordering in which removal can be asked to
  # step around foreign content at all.
  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  python3 - "$target" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["hooks"]["Notification"] = [
    {"matcher": "", "hooks": [{"type": "command", "command": "/opt/foreign-audit/hook.sh"}]}
]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]

  _assert_contains "$(cat "$target")" "/opt/foreign-audit/hook.sh"
  run _count_our_hooks "$target"
  [ "$output" -eq 0 ]
}

@test "remove where setup never ran changes nothing, says so, and is not an error" {
  local home dir target original
  home="$(_new_home remove-never-ran)"
  dir="$(_copy_fixture empty-object remove-never-ran)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/remove-never-ran.orig"
  cp -p "$target" "$original"

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "nothing to remove"
  _assert_bytes_equal "$original" "$target"
}

@test "remove never deletes existing records" {
  local home dir data
  home="$(_new_home remove-keeps-records)"
  dir="$(_copy_fixture absent remove-keeps-records)"
  data="$WORK_PARENT/remove-keeps-records.data"
  _make_record "$data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" install "$dir" --yes
  [ "$status" -eq 0 ]
  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" remove "$dir" --yes
  [ "$status" -eq 0 ]

  [ -f "$data/observability/events.jsonl" ]
  run cat "$data/observability/events.jsonl"
  _assert_contains "$output" '"kind":"skill"'
}

@test "remove on a non-repository is reported and writes nothing, at exit 0" {
  local home dir
  home="$(_new_home remove-non-repo)"
  dir="$(_copy_fixture not-a-repository remove-non-repo)"

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "repository"
  [ ! -e "$dir/.claude" ]
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# Journey 4 -- status, and the three states PRD F5 asks for.
# ---------------------------------------------------------------------------

@test "status reports a target where setup never ran as not configured" {
  local home dir data
  home="$(_new_home status-unconfigured)"
  dir="$(_copy_fixture absent status-unconfigured)"
  data="$WORK_PARENT/status-unconfigured.data"
  mkdir -p "$data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "not configured"
}

@test "status reports a configured target that has produced nothing as configured but silent" {
  local home dir data
  home="$(_new_home status-silent)"
  dir="$(_copy_fixture absent status-silent)"
  data="$WORK_PARENT/status-silent.data"
  mkdir -p "$data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" install "$dir" --yes
  [ "$status" -eq 0 ]

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "configured but silent"
  _assert_not_contains "$output" "not configured"
}

@test "status reports a configured target with records as recording" {
  local home dir data
  home="$(_new_home status-recording)"
  dir="$(_copy_fixture absent status-recording)"
  data="$WORK_PARENT/status-recording.data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" install "$dir" --yes
  [ "$status" -eq 0 ]
  _make_record "$data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "recording"
  _assert_not_contains "$output" "configured but silent"
  _assert_not_contains "$output" "not configured"
}

@test "status counts a rotated record as a record" {
  local home dir data
  home="$(_new_home status-rotated)"
  dir="$(_copy_fixture absent status-rotated)"
  data="$WORK_PARENT/status-rotated.data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" install "$dir" --yes
  [ "$status" -eq 0 ]
  mkdir -p "$data/observability"
  printf '%s\n' '{"kind":"skill"}' > "$data/observability/events.jsonl.1"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "recording"
  _assert_not_contains "$output" "configured but silent"
}

@test "a target with records but no registration is reported as not configured, never as recording" {
  local home dir data
  home="$(_new_home status-records-no-registration)"
  dir="$(_copy_fixture absent status-records-no-registration)"
  data="$WORK_PARENT/status-records-no-registration.data"
  _make_record "$data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "not configured"
}

@test "status writes nothing at all" {
  local home dir target original
  home="$(_new_home status-readonly)"
  dir="$(_copy_fixture foreign-only status-readonly)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/status-readonly.orig"
  cp -p "$target" "$original"

  _run_setup "$home" status "$dir"
  [ "$status" -eq 0 ]
  _assert_bytes_equal "$original" "$target"
  [ ! -e "$home/.claude/observability" ]
}

@test "status on a non-repository reports the reason and exits 0" {
  local home dir
  home="$(_new_home status-non-repo)"
  dir="$(_copy_fixture not-a-repository status-non-repo)"

  _run_setup "$home" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "repository"
}

# ---------------------------------------------------------------------------
# SDD-AC-15 -- drift reaches the verb a person actually runs.
# ---------------------------------------------------------------------------

@test "status reports drift when the installed bundle is behind the plugin's marker" {
  local home dir
  home="$(_home_with_bundle_version status-drift h0)"
  dir="$(_copy_fixture absent status-drift)"

  _run_setup "$home" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "DRIFT"
  _assert_contains "$output" "h0"
  _assert_contains "$output" "$CURRENT_BUNDLE_VERSION"
}

@test "status reports the bundle as missing when nothing is installed at the resolved HOME" {
  local home dir
  home="$(_new_home status-bundle-missing)"
  dir="$(_copy_fixture absent status-bundle-missing)"

  _run_setup "$home" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "MISSING"
}

@test "status reports no drift once install has put the current bundle in place" {
  local home dir
  home="$(_new_home status-no-drift)"
  dir="$(_copy_fixture absent status-no-drift)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  _run_setup "$home" status "$dir"
  [ "$status" -eq 0 ]
  _assert_not_contains "$output" "DRIFT"
  _assert_contains "$output" "$CURRENT_BUNDLE_VERSION"
}

# ---------------------------------------------------------------------------
# Foreign content survives an install that DOES write (the fixture carrying
# both a foreign entry and no registration of ours under a different event).
# ---------------------------------------------------------------------------

@test "a foreign entry under an event we do NOT register still stops install" {
  local home dir target original
  home="$(_new_home install-beside-foreign)"
  dir="$(_copy_fixture foreign-only install-beside-foreign)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/install-beside-foreign.orig"
  cp -p "$target" "$original"

  # detect.sh CONFLICT is broader than "a foreign entry under one of OUR
  # event names": ANY hook command in settings.local.json outside our
  # namespace classifies the target as CONFLICT. This fixture foreign entry
  # sits under PreToolUse with a Bash matcher, which we never claim, and the
  # target is still refused. Pinned because the command-level consequence is
  # easy to get wrong in the other direction -- an install that proceeded
  # here would be merging into a document another tool owns.
  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_bytes_equal "$original" "$target"
  run _count_our_hooks "$target"
  [ "$output" -eq 0 ]
  _assert_no_lock "$dir"
}

@test "install preserves non-ASCII bytes in content it did not author" {
  local home dir target
  home="$(_new_home install-non-ascii)"
  dir="$(_copy_fixture absent install-non-ascii)"
  target="$dir/.claude/settings.local.json"

  # Non-ASCII foreign content with NO foreign hook entry, so the target
  # classifies CLEAN and install actually writes -- build.sh non-ascii
  # fixture carries a foreign hook too, which would stop the run and make
  # this assertion vacuous.
  mkdir -p "$dir/.claude"
  printf '%s\n' '{ "env": { "TEAM_LABEL": "Équipe-Café-日本語" } }' > "$target"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  # json.dump defaults to ensure_ascii=True, which would rewrite these bytes
  # as backslash-u escapes: the document would still parse equal while the
  # operator bytes had changed (SDD-AC-10).
  _assert_contains "$(cat "$target")" "Équipe-Café-日本語"
}

# ---------------------------------------------------------------------------
# The legacy migration -- ruling (s). install on a LEGACY classification
# removes the in-repo registration from .claude/settings.json and adds the
# standard one to .claude/settings.local.json as ONE operation, so recording
# is never simultaneously double and never silently off.
# ---------------------------------------------------------------------------

@test "install on a legacy target migrates it: three hooks fire afterwards, not six" {
  local home dir legacy target total
  home="$(_new_home legacy-migrate)"
  dir="$(_copy_fixture already-configured-observability legacy-migrate)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # Before: three legacy hooks in settings.json, none of ours anywhere.
  run grep -c -F '"type": "command"' "$legacy"
  [ "$output" -eq 3 ]

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  # After: exactly three command hooks across BOTH files, all of them ours.
  total="$(cat "$legacy" "$target" | grep -c -F '"type": "command"' || true)"
  [ "$total" -eq 3 ]
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]
}

@test "the legacy migration reports both halves and does not present itself as a plain install" {
  local home dir
  home="$(_new_home legacy-report)"
  dir="$(_copy_fixture already-configured-observability legacy-report)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  # Not detect.sh own LEGACY line, which says only that a migration WILL
  # happen -- the command own report that both halves DID happen.
  _assert_contains "$output" "MIGRATED"
  _assert_contains "$output" "removed the legacy in-repo registration from"
  _assert_contains "$output" ".claude/settings.json"
  _assert_contains "$output" "ADDED"
  _assert_contains "$output" ".claude/settings.local.json"
  _assert_contains "$output" "UNDO"
}

@test "the legacy migration leaves foreign content in the shared settings file untouched" {
  local home dir legacy target
  home="$(_new_home legacy-foreign)"
  dir="$(_copy_fixture already-configured-observability legacy-foreign)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # A foreign entry under one of our own event names, in the shared file --
  # the migration must step around it exactly as removal does locally.
  python3 - "$legacy" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["hooks"]["PreToolUse"].append(
    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/opt/foreign-audit/hook.sh"}]}
)
data["permissions"] = {"allow": ["Bash(git:*)"]}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$(cat "$legacy")" "/opt/foreign-audit/hook.sh"
  _assert_contains "$(cat "$legacy")" "Bash(git:*)"
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  # The foreign entry is the ONLY command hook left in the shared file: the
  # three legacy ones are gone. Without this, "the foreign entry survives"
  # would also be true of a run that did nothing at all.
  run grep -c -F '"type": "command"' "$legacy"
  [ "$output" -eq 1 ]
}

@test "install --plan on a legacy target changes neither settings file" {
  local home dir legacy target orig_legacy orig_target
  home="$(_new_home legacy-plan)"
  dir="$(_copy_fixture already-configured-observability legacy-plan)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  orig_legacy="$WORK_PARENT/legacy-plan.shared.orig"
  orig_target="$WORK_PARENT/legacy-plan.local.orig"
  cp -p "$legacy" "$orig_legacy"
  cp -p "$target" "$orig_target"

  _run_setup "$home" install "$dir" --plan
  [ "$status" -eq 0 ]
  _assert_contains "$output" "PLAN: would remove the legacy in-repo registration from"
  _assert_not_contains "$output" "MIGRATED"
  _assert_bytes_equal "$orig_legacy" "$legacy"
  _assert_bytes_equal "$orig_target" "$target"
}

@test "removal on an un-migrated legacy target takes the legacy entries out too" {
  local home dir legacy
  home="$(_new_home legacy-remove)"
  dir="$(_copy_fixture already-configured-observability legacy-remove)"
  legacy="$dir/.claude/settings.json"

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]
  # The unrelated content of the shared file survives.
  _assert_contains "$(cat "$dir/.claude/settings.local.json")" "Bash(git:*)"
}

@test "status after the legacy migration reports the target as configured, not legacy" {
  local home dir data
  home="$(_new_home legacy-status)"
  dir="$(_copy_fixture already-configured-observability legacy-status)"
  data="$WORK_PARENT/legacy-status.data"
  mkdir -p "$data"

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" install "$dir" --yes
  [ "$status" -eq 0 ]

  _run_setup_env "$home" "CLAUDE_OBSERVABILITY_DATA=$data" status "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "configured but silent"
  # The detect.sh state LABEL, not the word anywhere in the output: the work
  # directory this fixture is copied into has "legacy" in its own name, and
  # the TARGET line prints that path.
  _assert_not_contains "$output" "] LEGACY:"
  _assert_contains "$output" "] OURS-CURRENT:"
}

@test "a legacy target whose shared settings file is not ignored by version control is refused" {
  local home dir legacy original
  home="$(_new_home legacy-not-ignored)"
  dir="$(_copy_fixture already-configured-observability legacy-not-ignored)"
  legacy="$dir/.claude/settings.json"
  original="$WORK_PARENT/legacy-not-ignored.orig"
  cp -p "$legacy" "$original"

  # Narrow the ignore rule so the LOCAL file and its sidecars stay covered
  # and only the shared file the migration would rewrite is committable --
  # otherwise the refusal could come from the backup-path check instead and
  # this test would pass without exercising the shared file at all.
  printf '%s\n' '.claude/settings.local.json*' > "$dir/.gitignore"
  git -C "$dir" add .gitignore
  git -C "$dir" -c user.name=fixture -c user.email=fixture@tcs.invalid commit -q -m "chore: narrow ignore"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "ignored"
  _assert_bytes_equal "$original" "$legacy"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# The shape gate, and the asymmetry a spec-compliance review found in it.
#
# detect.sh validated the top-level shape and "hooks" but not "env", so a
# target whose "env" is a non-object passed the gate -- and on a LEGACY
# target that meant the migration began, completed its write to the shared
# file, and only THEN hit add_registration raising on "env". The target was
# left legacy-removed and nothing-re-added, i.e. not recording, while the
# command said the originals were intact.
#
# Two fixes, pinned separately: detect.sh now rejects the shape (below), and
# registration.py validates the local document before it writes anything to
# the shared one (observability-registration-matrix.bats, which reaches the
# editor directly and so still exercises the ordering even with the gate
# closed).
# ---------------------------------------------------------------------------

@test "a legacy target whose local env is a non-object is refused before anything is written" {
  local home dir legacy original
  home="$(_new_home badenv-legacy)"
  dir="$(_copy_fixture already-configured-observability badenv-legacy)"
  legacy="$dir/.claude/settings.json"
  original="$WORK_PARENT/badenv-legacy.shared.orig"
  cp -p "$legacy" "$original"
  _write_local "$dir" '{ "env": "not-an-object" }'
  local local_original="$WORK_PARENT/badenv-legacy.local.orig"
  cp -p "$dir/.claude/settings.local.json" "$local_original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]

  # THE assertion: the shared file is untouched, byte for byte. Before the
  # reorder it was "{}" here, with its real content only in the .bak.
  _assert_bytes_equal "$original" "$legacy"
  # No backup, because nothing was written to make one for.
  [ ! -e "$legacy.tcs-observability.bak" ]
  # The local file is untouched too -- this run refuses, it does not repair.
  _assert_bytes_equal "$local_original" "$dir/.claude/settings.local.json"

  # The claim is now the true one, stated positively rather than only as the
  # absence of the false one.
  _assert_contains "$output" "nothing was written"
  _assert_not_contains "$output" "The original files are intact"
  _assert_no_lock "$dir"
}

@test "a local settings file whose env is a non-object is refused with nothing written" {
  local home dir original
  home="$(_new_home badenv-clean)"
  dir="$(_copy_fixture absent badenv-clean)"
  _write_local "$dir" '{ "env": "not-an-object" }'
  original="$WORK_PARENT/badenv-clean.orig"
  cp -p "$dir/.claude/settings.local.json" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "unexpected shape"
  _assert_bytes_equal "$original" "$dir/.claude/settings.local.json"
  [ ! -e "$home/.claude/observability" ]
  _assert_no_lock "$dir"
}

@test "a local settings file holding a non-object hook is refused with nothing written" {
  local home dir original
  home="$(_new_home badhook-element)"
  dir="$(_copy_fixture absent badhook-element)"
  _write_local "$dir" '{ "hooks": { "PreToolUse": [ { "matcher": "Skill", "hooks": [ "not-a-dict" ] } ] } }'
  original="$WORK_PARENT/badhook-element.orig"
  cp -p "$dir/.claude/settings.local.json" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "unexpected shape"
  _assert_bytes_equal "$original" "$dir/.claude/settings.local.json"
  _assert_no_lock "$dir"
}

@test "a local settings file whose hook command is not a string is refused with a diagnosis, never a traceback" {
  local home dir original
  home="$(_new_home badcommand-type)"
  dir="$(_copy_fixture absent badcommand-type)"
  _write_local "$dir" '{ "hooks": { "PreToolUse": [ { "matcher": "Skill", "hooks": [ { "type": "command", "command": 123 } ] } ] } }'
  original="$WORK_PARENT/badcommand-type.orig"
  cp -p "$dir/.claude/settings.local.json" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "unexpected shape"
  # registration.py's own docstring promises a diagnosis rather than a
  # traceback; this shape used to reach `NAMESPACE in 123` and raise a
  # TypeError that nothing caught.
  _assert_not_contains "$output" "Traceback"
  _assert_bytes_equal "$original" "$dir/.claude/settings.local.json"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# What a plan run actually leaves behind.
#
# The lock is taken before detection on purpose, and acquiring it creates the
# target's .claude/ directory -- so "nothing was written" overstated the case.
# The claim is corrected and the assertion that matters is added: version
# control sees nothing. That is the property T4.2 and T4.4 check, and it is
# stronger than asserting one path does not exist.
# ---------------------------------------------------------------------------

@test "a plan run leaves version control seeing nothing in the target" {
  local home dir
  home="$(_new_home plan-git-clean)"
  dir="$(_copy_fixture absent plan-git-clean)"

  _run_setup "$home" install "$dir" --yes --plan
  [ "$status" -eq 0 ]
  _assert_git_clean "$dir"
}

@test "a run without --yes leaves version control seeing nothing in the target" {
  local home dir
  home="$(_new_home noyes-git-clean)"
  dir="$(_copy_fixture absent noyes-git-clean)"

  _run_setup "$home" install "$dir"
  [ "$status" -eq 0 ]
  _assert_git_clean "$dir"
}

@test "an applied install leaves version control seeing nothing in the target" {
  local home dir
  home="$(_new_home install-git-clean)"
  dir="$(_copy_fixture absent install-git-clean)"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_git_clean "$dir"
}

@test "the plan step does not claim that nothing at all was written" {
  local home dir
  home="$(_new_home plan-claim)"
  dir="$(_copy_fixture absent plan-claim)"

  _run_setup "$home" install "$dir"
  [ "$status" -eq 0 ]
  # Acquiring the lock creates .claude/, so the old wording was not quite
  # true. The corrected claim names what it can actually vouch for.
  _assert_not_contains "$output" "nothing was written"
  _assert_contains "$output" "no file was written and no bundle installed"
}

@test "a migration that fails after writing the shared file says so, and does not claim the originals are intact" {
  local home dir legacy target original
  home="$(_new_home partial-migration)"
  dir="$(_copy_fixture already-configured-observability partial-migration)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/partial-migration.shared.orig"
  cp -p "$legacy" "$original"

  # The residual failure the reordering cannot remove: the shared write lands
  # and the LOCAL write then fails on I/O rather than on shape. Injected
  # through the filesystem -- a directory where the settings file belongs
  # makes os.replace fail at the last step of write_settings. detect.sh sees
  # a non-file as an absent file, so this target still classifies LEGACY and
  # the migration genuinely begins.
  rm -f "$target"
  mkdir -p "$target"
  printf 'x\n' > "$target/occupied"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]

  # The shared file DID change. The command must not say otherwise.
  _assert_bytes_differ "$original" "$legacy"
  _assert_not_contains "$output" "The original files are intact"
  # ...and it relays the detail that tells the operator what to do.
  _assert_contains "$output" "PARTIAL MIGRATION"
  _assert_contains "$output" "This target is NOT recording"
  _assert_contains "$output" "$legacy.tcs-observability.bak"
  _assert_bytes_equal "$original" "$legacy.tcs-observability.bak"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# strict=True covers the LOCAL document only, so a malformed hook in the
# SHARED file reaches remove_legacy_registration unscreened. That is
# deliberate -- raising there would turn an unrelated malformation elsewhere
# in settings.json into "not legacy", a classification change rather than a
# gate -- and it puts the weight on the type guards in hook_is_legacy and
# is_ours instead. This is the test that holds them to it.
# ---------------------------------------------------------------------------

@test "removal on a legacy target steps over a non-string command in the shared file and still takes the legacy entries out" {
  local home dir legacy target
  home="$(_new_home legacy-shared-nonstring)"
  dir="$(_copy_fixture already-configured-observability legacy-shared-nonstring)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # A hook whose "command" is an int, sitting beside the legacy trio under an
  # event we do register. Nothing screens it before the removal walk reaches
  # it, and `NAMESPACE in 123` raises TypeError without the guard.
  python3 - "$legacy" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["hooks"]["PreToolUse"].append(
    {"matcher": "", "hooks": [{"type": "command", "command": 123}]}
)
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_not_contains "$output" "Traceback"

  # Every legacy entry is gone -- no under-removal reported as success, which
  # is the shape ruling (u) exists to close.
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]

  # ...and the malformed entry is untouched. A non-string command is not ours.
  _assert_contains "$(cat "$legacy")" '"command": 123'
  run _count_our_hooks "$target"
  [ "$output" -eq 0 ]
  _assert_no_lock "$dir"
}

@test "install on a legacy target steps over a non-string command in the shared file and still migrates" {
  local home dir legacy target total
  home="$(_new_home legacy-shared-nonstring-install)"
  dir="$(_copy_fixture already-configured-observability legacy-shared-nonstring-install)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  python3 - "$legacy" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["hooks"]["Notification"] = [
    {"matcher": "", "hooks": [{"type": "command", "command": 123}]}
]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_not_contains "$output" "Traceback"
  _assert_contains "$output" "MIGRATED"

  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]
  _assert_contains "$(cat "$legacy")" '"command": 123'
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  _assert_no_lock "$dir"
}
