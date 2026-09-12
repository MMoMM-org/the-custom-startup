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
  # "precisely what and where" -- the event name is half of "where", and it
  # is the half that tells the operator which of their hooks to look at.
  _assert_contains "$output" "InstructionsLoaded"
  _assert_contains "$output" "PreToolUse"
  _assert_contains "$output" "SubagentStart"
  # The STOP line must route the reader to the line that names them rather
  # than restate a claim of its own. Pinned because a message that asserts
  # blindly reads identically to one that checked.
  _assert_contains "$output" "the CONFLICT line above names each event and command"
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

# T4.4 (SDD-AC-6 evidence gap): the settings and backup paths above already
# had a refusal test each; the lock and temp sidecars registration.py also
# declares in written_paths() did not. Same shape as the backup case, one
# fixture per path, so a run over the wrong sidecar or a loop that stops
# checking early is caught the same way.
@test "a target that ignores the settings file and backup but not the lock path is refused, naming the lock path" {
  local home dir target original
  home="$(_new_home lock-not-ignored)"
  dir="$(_copy_fixture ignored-file-and-backup-but-not-lock lock-not-ignored)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/lock-not-ignored.orig"
  cp -p "$target" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" ".tcs-observability.lock"
  _assert_bytes_equal "$original" "$target"
  _assert_no_lock "$dir"
}

@test "a target that ignores the settings file, backup and lock but not the temp path is refused, naming the temp path" {
  local home dir target original
  home="$(_new_home temp-not-ignored)"
  dir="$(_copy_fixture ignored-through-lock-but-not-temp temp-not-ignored)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/temp-not-ignored.orig"
  cp -p "$target" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" ".tcs-observability.tmp"
  _assert_bytes_equal "$original" "$target"
  _assert_no_lock "$dir"
}

# A drift guard alongside the four hand-written cases above, not instead of
# them: the two explicit tests read cleanly on their own when one fails, but
# neither one notices a FIFTH path added to written_paths() later -- nothing
# would fail, and nothing would say a case is missing. This test reads the
# declaration itself, the same way setup.sh's own _written_paths() does, and
# proves every path it names has its own working refusal, so a future fifth
# path is swept in without anyone remembering to add a sixth hand-written
# test for it.
@test "every path written_paths() declares triggers its own ignore refusal" {
  local home dir target repo_root paths_file path other

  home="$(_new_home written-paths-sweep)"
  dir="$(_copy_fixture absent written-paths-sweep)"
  # rev-parse, not $dir itself -- setup.sh computes its own REPO_ROOT the
  # same way, and $TMPDIR is a symlink on macOS (/tmp -> /private/tmp), so
  # a target built from the unresolved $dir would not share a prefix with
  # the resolved paths registration.py hands back below.
  repo_root="$(git -C "$dir" rev-parse --show-toplevel)"
  target="$repo_root/.claude/settings.local.json"

  paths_file="$WORK_PARENT/written-paths-sweep.paths"
  python3 - "$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib" "$target" \
    > "$paths_file" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
import registration

for path in registration.written_paths(sys.argv[2]):
    print(path)
PY

  while IFS= read -r path; do
    [ -n "$path" ] || continue

    # Ignore every OTHER declared path by exact name; leave this one out.
    : > "$dir/.gitignore"
    while IFS= read -r other; do
      [ -n "$other" ] || continue
      [ "$other" = "$path" ] && continue
      printf '%s\n' "${other#"$repo_root"/}" >> "$dir/.gitignore"
    done < "$paths_file"
    git -C "$dir" add .gitignore
    git -C "$dir" -c user.name=fixture -c user.email=fixture@tcs.invalid \
      commit -q -m "chore: ignore every declared path but one"

    _run_setup "$home" install "$dir" --yes
    [ "$status" -ne 0 ]
    # The literal ABORT wording is "does not ignore", not "ignored" -- a
    # sibling test's "ignored" check happens to pass only because its own
    # WORK-NAME contains that substring, which this test's work-name does
    # not, so it is asserted on the real message text instead.
    _assert_contains "$output" "does not ignore"
    _assert_contains "$output" "${path#"$repo_root"/}"
  done < "$paths_file"
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
  # The CONTENTION wording specifically. A fix that made the two lock
  # failures share one message would still pass a bare "lock" check.
  _assert_contains "$output" "another observability setup run holds the lock"
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

@test "a foreign entry under an event we do not register leaves the target installable" {
  local home dir target total
  home="$(_new_home install-beside-foreign)"
  dir="$(_copy_fixture non-ascii install-beside-foreign)"
  target="$dir/.claude/settings.local.json"

  # Ruling (aa) reverses what this test used to assert. This fixture's only
  # hook is under `Notification`, which this feature never registers, so
  # nothing overlaps and the install must proceed. It used to be refused
  # because the CONFLICT test discarded the event name and treated any
  # foreign command anywhere as an occupation of our events.
  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_not_contains "$output" "STOP"

  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]

  # The half worth keeping: the foreign entry survives a run that actually
  # wrote, which is a real preservation assertion rather than one made true
  # by the install being refused. Its non-ASCII bytes survive too.
  _assert_contains "$(cat "$target")" "/opt/Café-Tools/notify.sh"
  _assert_contains "$(cat "$target")" "Équipe-Café-日本語"
  total="$(grep -c -F '"type": "command"' "$target" || true)"
  [ "$total" -eq 4 ]
  _assert_no_lock "$dir"
}

@test "a foreign entry under one of our events with a different matcher still stops install" {
  local home dir target original
  home="$(_new_home foreign-other-matcher)"
  dir="$(_copy_fixture foreign-only foreign-other-matcher)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/foreign-other-matcher.orig"
  cp -p "$target" "$original"

  # This fixture's foreign hook is PreToolUse with matcher `Bash`; we register
  # PreToolUse with matcher `Skill`, so the two would never fire on the same
  # tool call. The stop is DELIBERATELY event-level anyway: deciding
  # non-overlap from matcher strings means evaluating an unanchored JavaScript
  # regular expression against the tool name, and a wrong answer in the
  # permissive direction installs beside a hook that does fire alongside ours.
  # SDD-AC-4 is worded at the event level, and a CONFLICT costs a
  # conversation rather than a wrong write.
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

# ---------------------------------------------------------------------------
# Partial legacy shapes at the command level -- maintainer ruling (x).
# ---------------------------------------------------------------------------

# _rewrite_shared <repo> -- rewrite the target's shared settings.json with the
# python on stdin.
_rewrite_shared() {
  python3 - "$1/.claude/settings.json"
}

@test "install on a partially legacy target migrates it and leaves no live legacy hook" {
  local home dir legacy target
  home="$(_new_home partial-install)"
  dir="$(_copy_fixture already-configured-observability partial-install)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # One of the trio replaced by a non-string command: two real legacy hooks
  # remain, and before ruling (x) this target read CLEAN and got a full
  # registration added beside them -- six-ish hooks where three belong.
  _rewrite_shared "$dir" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["hooks"]["PreToolUse"] = [{"matcher": "", "hooks": [{"type": "command", "command": 123}]}]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_contains "$output" "MIGRATED"

  # No legacy hook survives, and the standard registration is in place once.
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  _assert_no_lock "$dir"
}

@test "remove on a partially legacy target takes out what is there and names it" {
  local home dir legacy
  home="$(_new_home partial-remove)"
  dir="$(_copy_fixture already-configured-observability partial-remove)"
  legacy="$dir/.claude/settings.json"

  _rewrite_shared "$dir" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
del d["hooks"]["SubagentStart"]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY

  _run_setup "$home" remove "$dir" --yes
  [ "$status" -eq 0 ]
  # Captured BEFORE the greps below: `run` overwrites $output, so asserting
  # against it after a `run grep` reads grep's output, not the command's.
  local report="$output"

  # Nothing legacy left firing -- the false-success shape ruling (u) closes,
  # reached here through the partial-shape door instead.
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]
  # The report names the two events it actually removed, not a flat three.
  _assert_contains "$report" "InstructionsLoaded"
  _assert_contains "$report" "PreToolUse"
  _assert_not_contains "$report" "removed legacy observability hooks (InstructionsLoaded, PreToolUse, SubagentStart)"
  _assert_no_lock "$dir"
}

@test "a migration never deletes a third party's hook that merely shares a script name" {
  local home dir legacy
  home="$(_new_home third-party-survives)"
  dir="$(_copy_fixture already-configured-observability third-party-survives)"
  legacy="$dir/.claude/settings.json"

  # Two real legacy entries plus a third party's own log_skill.sh under the
  # third event. Basename matching claims that entry as ours and deletes it.
  _rewrite_shared "$dir" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["hooks"]["PreToolUse"] = [{"matcher": "", "hooks": [
    {"type": "command", "command": "\"/opt/other-tool/log_skill.sh\""}]}]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PY

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  _assert_contains "$(cat "$legacy")" "/opt/other-tool/log_skill.sh"
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]
  _assert_no_lock "$dir"
}

@test "a target left by a partial migration takes the plain install path, not the migration path" {
  local home dir legacy target
  home="$(_new_home post-partial)"
  dir="$(_copy_fixture already-configured-observability post-partial)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # Exactly what the PARTIAL MIGRATION path leaves: shared fully stripped,
  # local carrying no registration. "One or more" must not catch zero, or the
  # two paths collide and setup reports a migration that removed nothing.
  _rewrite_shared "$dir" <<'PY'
import json, sys
json.dump({}, open(sys.argv[1], "w", encoding="utf-8"), indent=2)
PY

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  _assert_not_contains "$output" "MIGRATED"
  _assert_contains "$output" "ADDED"
  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  run cat "$legacy"
  [ "$output" = "{}" ]
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# A target that is BOTH legacy and already locally registered.
#
# detect.sh checks the shared file first and returns LEGACY before the OURS
# branch runs, so this compound state classifies LEGACY. The local half of
# the migration is then a genuine no-op -- registration.py says "already
# configured" -- and the legacy branch used to announce ADDED regardless.
# A status line asserting something that did not happen is this task's
# central defect class, and nothing in the suite built this fixture.
# ---------------------------------------------------------------------------

@test "install on a target that is legacy AND already registered does not claim it added anything" {
  local home dir legacy target original report
  home="$(_new_home compound-legacy)"
  dir="$(_copy_fixture already-configured-observability compound-legacy)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # The local half is built through registration.py's own helpers, so it is
  # byte-for-byte what command_for() produces today rather than a hand copy
  # that drifts the first time the command string changes.
  python3 - "$target" "$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib" <<'PY'
import json
import sys

sys.path.insert(0, sys.argv[2])
import registration

document = {"permissions": {"allow": ["Bash(git:*)"]}}
registration.add_registration(document)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(document, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  original="$WORK_PARENT/compound-legacy.local.orig"
  cp -p "$target" "$original"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]
  report="$output"

  # The shared half genuinely happened, so MIGRATED is true...
  _assert_contains "$report" "MIGRATED"
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]

  # ...and the local half did not, so ADDED must not be claimed.
  _assert_not_contains "$report" "ADDED"
  _assert_contains "$report" "already configured"
  _assert_bytes_equal "$original" "$target"
  _assert_no_lock "$dir"
}

@test "install --plan with --yes does not tell the user to re-run with a flag they already passed" {
  local home dir
  home="$(_new_home plan-wording)"
  dir="$(_copy_fixture absent plan-wording)"

  _run_setup "$home" install "$dir" --yes --plan
  [ "$status" -eq 0 ]
  _assert_contains "$output" "no file was written and no bundle installed"
  _assert_not_contains "$output" "Re-run with --yes"
  _assert_contains "$output" "Drop --plan"
}

@test "install without --yes still tells the user to re-run with --yes" {
  local home dir
  home="$(_new_home plan-wording-noyes)"
  dir="$(_copy_fixture absent plan-wording-noyes)"

  _run_setup "$home" install "$dir"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "Re-run with --yes"
  _assert_not_contains "$output" "Drop --plan"
}

@test "a refusal names the repo-relative path even when the repository path holds a glob metacharacter" {
  local home globdir dir
  home="$(_new_home globpath)"
  # A bracket in the repository path. `${path#$REPO_ROOT/}` is a pattern
  # match, not a literal strip, so an unquoted REPO_ROOT containing [ ? or *
  # fails to match and `rel` stays absolute -- which lands verbatim in the
  # refusal message the operator reads.
  globdir="$WORK_PARENT/glob[1]"
  rm -rf "$globdir"
  mkdir -p "$globdir"
  cp -pR "$FIXTURES_DIR/ignored-file-but-not-backup" "$globdir/repo"
  dir="$globdir/repo"

  _run_setup "$home" install "$dir" --yes
  [ "$status" -ne 0 ]
  _assert_contains "$output" "does not ignore .claude/settings.local.json.tcs-observability.bak"
  _assert_not_contains "$output" "does not ignore /"
  _assert_no_lock "$dir"
}

# ---------------------------------------------------------------------------
# The lock failing to be CREATED is not the lock being HELD.
#
# Found by T4.2 against a real target: a repository whose .claude/ this
# process could not write produced "another observability setup run holds the
# lock ...", with no lock file present and no other run in existence. The
# refusal was right -- nothing is written either way -- but the diagnosis sent
# the operator looking for a concurrent process that was never there.
# ---------------------------------------------------------------------------

@test "a lock that cannot be created reports the write restriction, not contention" {
  local home dir target
  home="$(_new_home lock-uncreatable)"
  dir="$(_copy_fixture absent lock-uncreatable)"
  target="$dir/.claude/settings.local.json"

  mkdir -p "$dir/.claude"
  chmod 500 "$dir/.claude"

  # Running as root makes chmod cosmetic and the failure unobservable. CI does
  # not run as root, but a container shell often does, and a test that silently
  # proves nothing is worse than one that says so.
  if echo canary > "$dir/.claude/canary" 2>/dev/null; then
    chmod 700 "$dir/.claude"
    skip "the write-protected directory is writable anyway (running as root?)"
  fi

  _run_setup_env "$home" "TCS_OBSERVABILITY_LOCK_TIMEOUT=0" install "$dir" --yes
  local report="$status|$output"
  chmod 700 "$dir/.claude"

  [ "${report%%|*}" -ne 0 ]
  # Names the real problem...
  _assert_contains "$output" "could not create the lock file"
  _assert_contains "$output" "$target.tcs-observability.lock"
  # The errno is what makes the message actionable, so pin that it survived
  # rather than falling back. Asserted as the ABSENCE of the fallback text
  # rather than the presence of "Permission denied", which is the shell's
  # wording and would tie this test to a locale.
  _assert_not_contains "$output" "no further detail"
  # ...and does NOT invent a concurrent run.
  _assert_not_contains "$output" "another observability setup run"
  _assert_not_contains "$output" "held by a live process"

  # The refusal itself was already correct and stays correct.
  [ ! -e "$target" ]
  _assert_no_lock "$dir"
  [ ! -e "$home/.claude/observability" ]
}

@test "a lock that cannot be created leaves no sidecar behind" {
  local home dir
  home="$(_new_home lock-uncreatable-sidecars)"
  dir="$(_copy_fixture absent lock-uncreatable-sidecars)"

  mkdir -p "$dir/.claude"
  chmod 500 "$dir/.claude"
  if echo canary > "$dir/.claude/canary" 2>/dev/null; then
    chmod 700 "$dir/.claude"
    skip "the write-protected directory is writable anyway (running as root?)"
  fi

  _run_setup_env "$home" "TCS_OBSERVABILITY_LOCK_TIMEOUT=0" install "$dir" --yes
  chmod 700 "$dir/.claude"
  [ "$status" -ne 0 ]

  run find "$dir/.claude" -name '*.tcs-observability.*'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  _assert_git_clean "$dir"
}

# ---------------------------------------------------------------------------
# T4.4 ruling (ac): AC-3, AC-9 and AC-11 are worded "when setup runs" but
# were tested only against registration.py directly. These three close the
# letter through the real entry point.
# ---------------------------------------------------------------------------

@test "unrelated top-level keys in local settings survive a real install byte-for-byte (SDD-AC-3)" {
  local home dir target
  home="$(_new_home ac3-command-level)"
  dir="$(_copy_fixture absent ac3-command-level)"
  target="$dir/.claude/settings.local.json"

  _write_local "$dir" '{
  "permissions": { "allow": ["Bash(ls:*)"], "deny": [] },
  "model": "claude-opus-5",
  "statusLine": { "type": "command", "command": "my-statusline.sh" },
  "env": { "SOMETHING_ELSE": "keep me" }
}'

  _run_setup "$home" install "$dir" --yes
  [ "$status" -eq 0 ]

  run python3 - "$target" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    data = json.load(handle)

assert data['permissions'] == {'allow': ['Bash(ls:*)'], 'deny': []}, data.get('permissions')
assert data['model'] == 'claude-opus-5', data.get('model')
assert data['statusLine'] == {'type': 'command', 'command': 'my-statusline.sh'}, data.get('statusLine')
# ours is added BESIDE the existing env key, not instead of it.
assert data['env']['SOMETHING_ELSE'] == 'keep me', data.get('env')
assert data['env']['CLAUDE_OBSERVABILITY_ENABLED'] == '1', data.get('env')
PY
  [ "$status" -eq 0 ]
}

# T4.4 ruling (ac): the library test (test_observability_registration.py)
# patches os.replace to raise -- a seam this command-level test cannot use.
# What it uses instead is the same real-filesystem technique the residual-I/O
# tests above rely on (a directory where the settings file belongs makes
# os.replace fail with no code seam at all), one step further: `chflags uchg`
# makes the destination itself immutable, so shutil.copy2 (a read plus a NEW
# file) and the temp-write (also a new file) both still succeed -- only the
# final `os.replace(temp, path)`, which has to remove the immutable
# destination, fails. That is the exact window SDD-AC-9 is about: backup
# already taken, temp already written, only the rename fails.
@test "an interrupted write through the real entry point leaves the original intact with a backup, and reports failure (SDD-AC-9)" {
  local home dir target original
  home="$(_new_home ac9-command-level)"
  dir="$(_copy_fixture empty-object ac9-command-level)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/ac9-command-level.orig"
  cp -p "$target" "$original"

  chflags uchg "$target"

  # Running as root can bypass the immutable flag, the same hazard the
  # write-protected-directory tests above guard against for chmod.
  if printf 'canary\n' >> "$target" 2>/dev/null; then
    chflags nouchg "$target"
    cp -p "$original" "$target"
    skip "the immutable file is writable anyway (running as root?)"
  fi

  _run_setup "$home" install "$dir" --yes
  # copy2 (write_settings' backup step) preserves st_flags on macOS, so the
  # immutable flag lands on the BACKUP too -- clear it on both before any
  # assertion that could abort the body, or teardown_file's rm -rf fails on
  # a file this test made immutable, not on anything setup.sh left behind.
  chflags nouchg "$target"
  chflags nouchg "$target.tcs-observability.bak" 2>/dev/null || true

  [ "$status" -ne 0 ]
  _assert_contains "$output" "ABORT"
  _assert_contains "$output" "the registration edit failed"
  _assert_contains "$output" "failed to write"
  _assert_bytes_equal "$original" "$target"

  local backup="$target.tcs-observability.bak"
  [ -e "$backup" ]
  _assert_bytes_equal "$original" "$backup"
  [ ! -e "$target.tcs-observability.tmp" ]
  _assert_no_lock "$dir"
}

# T4.4 ruling (ac): the library test races two subprocesses directly against
# registration.py; this is the same shape one level up, against setup.sh
# itself, which takes its own lock BEFORE calling registration.py at all
# (`--lock-held-by-caller`) -- so what serializes here is the command, not
# just the module underneath it.
@test "two concurrent real setup.sh runs against one target serialize, and no observed state is torn (SDD-AC-11)" {
  local home dir target observations
  home="$(_new_home ac11-command-level)"
  dir="$(_copy_fixture empty-object ac11-command-level)"
  target="$dir/.claude/settings.local.json"

  env HOME="$home" GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null TCS_OBSERVABILITY_LOCK_TIMEOUT=20 \
    bash "$SETUP_SH" install --target "$dir" --yes \
    > "$WORK_PARENT/ac11-command-level.out1" 2>&1 &
  local p1=$!
  env HOME="$home" GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.excludesFile \
    GIT_CONFIG_VALUE_0=/dev/null TCS_OBSERVABILITY_LOCK_TIMEOUT=20 \
    bash "$SETUP_SH" install --target "$dir" --yes \
    > "$WORK_PARENT/ac11-command-level.out2" 2>&1 &
  local p2=$!

  # At least one observation is required rather than assumed -- the same
  # posture the library's own version of this test takes -- because a poll
  # loop that races two fast subprocesses can miss the window entirely and
  # would otherwise prove nothing while still going green.
  observations=0
  while kill -0 "$p1" 2>/dev/null || kill -0 "$p2" 2>/dev/null; do
    if [ -f "$target" ]; then
      if python3 -c "
import json, sys
json.load(open(sys.argv[1], encoding='utf-8'))
" "$target" 2>/dev/null; then
        observations=$((observations + 1))
      else
        # A partial write was observed: fail loudly rather than let the
        # loop exit quietly and the later assertions paper over it.
        echo "a partial/unparseable document was observed mid-run" >&2
        observations=-1
        break
      fi
    fi
  done

  wait "$p1"; local rc1=$?
  wait "$p2"; local rc2=$?

  [ "$rc1" -eq 0 ]
  [ "$rc2" -eq 0 ]
  [ "$observations" -ge 0 ]
  [ "$observations" -gt 0 ]

  run _count_our_hooks "$target"
  [ "$output" -eq 3 ]
  _assert_no_lock "$dir"
}
