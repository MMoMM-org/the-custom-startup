#!/usr/bin/env bats
#
# tests/bats/observability-registration-matrix.bats
#
# spec 019 (observability rollout across active repos), Phase 2, T2.6 --
# "Phase Validation" found Phase 2's acceptance criterion "Setup and removal
# are correct across every fixture in the matrix" unverified: the fixture
# matrix (fixtures/observability-settings/build.sh) is consumed by
# observability-settings-fixtures.bats (T2.1, asserts properties OF the
# fixtures) and observability-detect.bats (T2.2, detection only). Nothing
# had ever run registration.py -- the actual setup/removal editor -- against
# it. The editor's own 52-test pytest suite (tests/tcs-helper/
# test_observability_registration.py) covers the same shapes by hand,
# built inline, never through this matrix.
#
# This file is that missing third consumer. It runs registration.py's CLI
# (the same subprocess-invocation shape test_observability_registration.py
# uses: `python3 registration.py --settings <path> [--remove]`) against
# EVERY fixture and pins today's behaviour -- not a wish, not what the
# fixture names imply, but what setup and removal actually do.
#
# TWO REAL FINDINGS FALL OUT OF RUNNING IT FOR REAL, both pinned below with
# their own commentary rather than "fixed" here (out of scope for this task
# -- see CONSTRAINTS in the task this file was written under):
#
#   1. already-configured-observability: setup alone does NOT migrate the
#      legacy settings.json registration; it adds a SECOND, independent
#      registration to settings.local.json, leaving six hooks firing where
#      three should. This is the editor's contract (ADR-1 scope), not a
#      defect -- see that test below.
#
#   2. foreign-plus-ours-current / foreign-plus-ours-older: build.sh
#      concatenates a `"hooks": {...}` block from _foreign_hooks_json with a
#      SECOND `"hooks": {...}` block from _ours_hooks_json at the same
#      object nesting level, joined by a literal comma. The raw fixture
#      TEXT contains two top-level "hooks" keys. json.loads (used by both
#      registration.py and Python's own json module generally) resolves
#      duplicate object keys last-wins, so the parsed document only ever
#      has the "ours" hooks -- the foreign PreToolUse/Bash entry is
#      structurally invisible to any JSON-based consumer, including
#      registration.py. observability-settings-fixtures.bats' fixture-6/7
#      tests do not catch this because they assert via grep -F over the raw
#      text (finds the substring) and _assert_json_valid (parses without
#      raising), never round-tripping through json.load and re-checking
#      which keys survived. See the two tests below for what this means in
#      practice for setup and removal.
#
# bash 3.2 compatible (CON-1): no `[[ =~ ]]` with PCRE classes or bounded
# quantifiers. Every substring assertion goes through _assert_contains /
# _assert_not_contains (grep -F, a plain command -- trips `set -e`
# correctly at any position, unlike a bare `[[ ]]` used as a non-final
# statement; see docs/ai/memory/active.md and observability-detect.bats'
# header for the measured reason). `timeout` is not used anywhere (absent
# on macOS).

bats_require_minimum_version 1.5.0

setup_file() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../../../.." && pwd)"
  BUILD_SH="$REPO_ROOT/plugins/tcs-helper/tests/fixtures/observability-settings/build.sh"
  REGISTRATION_PY="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/registration.py"
  export REPO_ROOT BUILD_SH REGISTRATION_PY

  # Isolate fixture-build git invocations from the operator's real
  # global/system git config -- same as the sibling fixture-consuming files.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  # macOS exports TMPDIR with a trailing slash; strip it so fixture/work
  # paths never carry a "//" (same normalization as the sibling files).
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done

  FIXTURES_PARENT="$(mktemp -d "$tmpbase/tcs-obs-registration-fixtures.XXXXXX")"
  FIXTURES_DIR="$("$BUILD_SH" "$FIXTURES_PARENT/fixtures")"
  export FIXTURES_PARENT FIXTURES_DIR

  # Every test below works on its OWN copy of a fixture (registration.py
  # mutates the target in place) -- this is that copy's parent, cleaned up
  # once for the whole file rather than per test.
  WORK_PARENT="$(mktemp -d "$tmpbase/tcs-obs-registration-work.XXXXXX")"
  export WORK_PARENT
}

teardown_file() {
  if [ -n "${FIXTURES_PARENT:-}" ] && [ -d "$FIXTURES_PARENT" ]; then
    chmod -R u+rwX "$FIXTURES_PARENT" 2>/dev/null || true
    rm -rf "$FIXTURES_PARENT"
  fi
  if [ -n "${WORK_PARENT:-}" ] && [ -d "$WORK_PARENT" ]; then
    chmod -R u+rwX "$WORK_PARENT" 2>/dev/null || true
    rm -rf "$WORK_PARENT"
  fi
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# _assert_contains/_assert_not_contains -- fixed-string via grep -F (a plain
# command, so it trips `set -e` correctly at any position in a test body --
# see the header note; a bare `[[ ]]` does not).
_assert_contains() {
  printf '%s' "$1" | grep -qF "$2"
}

_assert_not_contains() {
  ! printf '%s' "$1" | grep -qF "$2"
}

# _copy_fixture <fixture-name> <work-name> -- fresh, independent copy of a
# built fixture directory, since registration.py mutates its target in
# place and every test needs to start from the untouched fixture.
_copy_fixture() {
  local fixture="$1" workname="$2"
  local dest="$WORK_PARENT/$workname"
  rm -rf "$dest"
  cp -pR "$FIXTURES_DIR/$fixture" "$dest"
  printf '%s\n' "$dest"
}

# _run_setup <settings-path> -- invokes the editor exactly as
# test_observability_registration.py does: subprocess, `python3
# registration.py --settings <path>`. Never a real settings file.
_run_setup() {
  run python3 "$REGISTRATION_PY" --settings "$1"
}

_run_remove() {
  run python3 "$REGISTRATION_PY" --settings "$1" --remove
}

# _assert_bytes_equal/_assert_bytes_differ -- byte-for-byte comparison via
# cmp -s (POSIX, present on both macOS and Linux runners). Plain commands,
# same set -e reasoning as the grep helpers above.
_assert_bytes_equal() {
  cmp -s "$1" "$2"
}

_assert_bytes_differ() {
  ! cmp -s "$1" "$2"
}

# _assert_json_equal <file-a> <file-b> -- parsed-document equality, for the
# fixtures where a round trip preserves the DATA but not the exact bytes
# (json.dumps(indent=2) reflows any hand-written compact/single-line JSON,
# even in content this feature never touched).
_assert_json_equal() {
  python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    a = json.load(f)
with open(sys.argv[2], encoding="utf-8") as f:
    b = json.load(f)
sys.exit(0 if a == b else 1)
' "$1" "$2"
}

# ---------------------------------------------------------------------------
# Matrix completeness -- fails loudly if build.sh's fixture count drifts
# without this file being updated to match (13 per the T2.1 header count).
# ---------------------------------------------------------------------------

@test "the matrix builds exactly 13 target fixtures" {
  local count
  count="$(find "$FIXTURES_DIR" -mindepth 1 -maxdepth 1 -type d ! -name '*.home' | wc -l | tr -d ' ')"
  [ "$count" -eq 13 ]
}

# ---------------------------------------------------------------------------
# 1. absent -- no settings file, no .claude/ directory at all
# ---------------------------------------------------------------------------

@test "absent: setup creates and registers; removal leaves an empty-object file behind, not absence" {
  local dir target
  dir="$(_copy_fixture absent absent)"
  target="$dir/.claude/settings.local.json"
  [ ! -e "$target" ]

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"
  [ -f "$target" ]
  run grep -c -F '$HOME/.claude/observability/' "$target"
  [ "$output" -eq 3 ]

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  # registration.py has no path to delete the settings file itself -- only
  # to prune keys inside it (remove_registration's only effect is on the
  # in-memory dict; write_settings always writes SOMETHING). So "restore
  # to pre-setup state" here means an existing "{}\n" file, not the
  # absence the fixture started with.
  [ -f "$target" ]
  run cat "$target"
  [ "$output" = "{}" ]
}

# ---------------------------------------------------------------------------
# 2. empty-object -- "{}\n"
# ---------------------------------------------------------------------------

@test "empty-object: setup registers; removal restores byte-identical pre-setup content" {
  local dir target original
  dir="$(_copy_fixture empty-object empty-object)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/empty-object.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  # "{}\n" is exactly what json.dumps({}, indent=2) + "\n" produces too, so
  # this is the one case where the byte-identical contract actually holds.
  _assert_bytes_equal "$original" "$target"
}

# ---------------------------------------------------------------------------
# 3. foreign-only -- foreign hooks, zero entries in our namespace
# ---------------------------------------------------------------------------

@test "foreign-only: setup adds ours alongside the foreign entry; removal restores the same DATA, reformatted (not byte-identical)" {
  local dir target original
  dir="$(_copy_fixture foreign-only foreign-only)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/foreign-only.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"
  _assert_contains "$(cat "$target")" "/opt/foreign-audit/hook.sh"
  run grep -c -F '$HOME/.claude/observability/' "$target"
  [ "$output" -eq 3 ]

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  # The foreign entry survives structurally (same parsed document)...
  _assert_json_equal "$original" "$target"
  # ...but not byte-for-byte: write_settings always re-serializes the WHOLE
  # document with json.dumps(indent=2), so the fixture's hand-written
  # single-line array/object style gets reflowed to one-key-per-line, even
  # for content this feature never touched. Pinned deliberately, not a bug
  # -- the module doc's own stated defaults (json.dumps(indent=2)) only
  # promise byte-stability for content IT wrote, never for a foreign
  # neighbour's formatting.
  _assert_bytes_differ "$original" "$target"
}

# ---------------------------------------------------------------------------
# 4 & 5. foreign-plus-ours-current / foreign-plus-ours-older
#
# See the file header's finding #2: both fixtures' raw JSON text has a
# duplicate top-level "hooks" key (one from _foreign_hooks_json, one from
# _ours_hooks_json). json.loads resolves that last-wins, so the DOCUMENT
# registration.py actually reads only ever contains the "ours" hooks -- the
# foreign PreToolUse/Bash entry is invisible once parsed, even though it is
# still present as raw text (which is why grep -F over the file still finds
# it, and why observability-settings-fixtures.bats' fixture tests, which
# never round-trip through json.load, don't catch this).
# ---------------------------------------------------------------------------

@test "foreign-plus-ours-current: setup is a no-op ('already configured'); the file is byte-identical to before" {
  local dir target original
  dir="$(_copy_fixture foreign-plus-ours-current foreign-plus-ours-current)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/foreign-plus-ours-current.orig"
  cp -p "$target" "$original"

  # add_registration sees data['hooks'] already equal to what command_for()
  # produces today -- because the duplicate key means that IS the whole of
  # "hooks" as parsed -- so status is 'none': nothing written.
  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "already configured:"
  _assert_bytes_equal "$original" "$target"

  # Removal prunes everything in the parsed document: 'env' held only our
  # switch, and 'hooks' (the shadowed, ours-only version) held only our
  # three entries -- so both containers empty out and get deleted, leaving
  # "{}". This is NOT a loss of the foreign entry by removal: that entry
  # was already unreachable through any JSON parse before removal ever ran.
  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  run cat "$target"
  [ "$output" = "{}" ]
}

@test "foreign-plus-ours-older: byte-identical to foreign-plus-ours-current (ADR-5: the command string is opaque to bundle version), same no-op/removal behaviour" {
  local dir target original current_target
  dir="$(_copy_fixture foreign-plus-ours-older foreign-plus-ours-older)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/foreign-plus-ours-older.orig"
  cp -p "$target" "$original"
  current_target="$FIXTURES_DIR/foreign-plus-ours-current/.claude/settings.local.json"
  _assert_bytes_equal "$original" "$current_target"

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "already configured:"
  _assert_bytes_equal "$original" "$target"

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  run cat "$target"
  [ "$output" = "{}" ]
}

# ---------------------------------------------------------------------------
# 6. malformed -- unparseable JSON
# ---------------------------------------------------------------------------

@test "malformed: setup and removal both refuse identically, leaving the file untouched either way" {
  local dir target original
  dir="$(_copy_fixture malformed malformed)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/malformed.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 1 ]
  _assert_contains "$output" "cannot parse"
  _assert_contains "$output" "as JSON"
  _assert_bytes_equal "$original" "$target"

  # load_settings() runs before the --remove branch is ever consulted, so
  # removal fails the exact same way, for the exact same reason -- there is
  # no direction-dependent behaviour here at all.
  _run_remove "$target"
  [ "$status" -eq 1 ]
  _assert_contains "$output" "cannot parse"
  _assert_bytes_equal "$original" "$target"
}

# ---------------------------------------------------------------------------
# 7. non-ascii -- valid JSON, non-ASCII bytes in foreign content
# ---------------------------------------------------------------------------

@test "non-ascii: setup preserves the raw non-ASCII bytes (ensure_ascii=False); removal restores the same DATA, reformatted" {
  local dir target original
  dir="$(_copy_fixture non-ascii non-ascii)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/non-ascii.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"
  # SDD-AC-10 / the module docstring's stated default: ensure_ascii=False,
  # so these bytes must survive literally, not as \uXXXX escapes -- a
  # substring match on the literal UTF-8 text is itself the proof: had
  # json.dump used its true default, these two greps would find nothing,
  # since the source characters would have been rewritten as escape
  # sequences that share none of these bytes.
  _assert_contains "$(cat "$target")" "Café"
  _assert_contains "$(cat "$target")" "日本語"

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  _assert_json_equal "$original" "$target"
  _assert_bytes_differ "$original" "$target"
  _assert_contains "$(cat "$target")" "Café"
  _assert_contains "$(cat "$target")" "日本語"
}

# ---------------------------------------------------------------------------
# 8. same-event-names-populated -- foreign entries under OUR event names
# ---------------------------------------------------------------------------

@test "same-event-names-populated: setup appends ours beside each foreign entry (same event, different matcher); removal restores the same DATA, reformatted" {
  local dir target original
  dir="$(_copy_fixture same-event-names-populated same-event-names-populated)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/same-event-names-populated.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"
  _assert_contains "$(cat "$target")" "/opt/foreign-audit/on-load.sh"
  _assert_contains "$(cat "$target")" "/opt/foreign-audit/hook.sh"
  _assert_contains "$(cat "$target")" "/opt/foreign-audit/on-subagent.sh"
  run grep -c -F '$HOME/.claude/observability/' "$target"
  [ "$output" -eq 3 ]

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  _assert_json_equal "$original" "$target"
  _assert_bytes_differ "$original" "$target"
}

# ---------------------------------------------------------------------------
# 9. write-path-not-ignored -- settings.local.json absent, like "absent",
# but distinguished by its .gitignore (a detect.sh concern, not the
# editor's -- registration.py has no git awareness at all, confirmed here).
# ---------------------------------------------------------------------------

@test "write-path-not-ignored: registration.py is git-blind -- setup and removal behave exactly as on 'absent'" {
  local dir target
  dir="$(_copy_fixture write-path-not-ignored write-path-not-ignored)"
  target="$dir/.claude/settings.local.json"
  [ ! -e "$target" ]

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"
  [ -f "$target" ]

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  run cat "$target"
  [ "$output" = "{}" ]
}

# ---------------------------------------------------------------------------
# 10. already-configured-observability -- THE finding. This repo's own
# real, hand-made LEGACY state: settings.json (not settings.local.json)
# carries our three hooks pointed at an in-repo script path.
#
# WHOSE JOB THE MIGRATION IS: detect.sh classifies this target LEGACY and
# (per T2.2) prints "setup will migrate this to $HOME/.claude/observability/"
# -- a promise made on setup's behalf. registration.py never reads
# settings.json at all (ADR-1: it edits settings.local.json only, proving
# ownership by the $HOME/.claude/observability/ namespace per ADR-5, which
# settings.json's in-repo command path can never satisfy). So running setup
# alone cannot keep that promise -- only T4.1, which will compose detection
# with the editor, can. This test pins that gap as today's real contract:
# when T4.1 lands and teaches setup to migrate the legacy registration
# instead of layering a second one beside it, THIS test is the one that
# has to change.
# ---------------------------------------------------------------------------

@test "already-configured-observability: setup adds a SECOND registration beside the untouched legacy one -- six hooks fire, not three (T4.1's migration, not this editor's)" {
  local dir legacy target original_target original_legacy
  dir="$(_copy_fixture already-configured-observability already-configured-observability)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  original_target="$WORK_PARENT/already-configured.local.orig"
  original_legacy="$WORK_PARENT/already-configured.legacy.orig"
  cp -p "$target" "$original_target"
  cp -p "$legacy" "$original_legacy"

  # Before setup: 3 hooks total, all in the legacy file.
  run grep -c -F '"type": "command"' "$legacy"
  [ "$output" -eq 3 ]
  run grep -c -F '"type": "command"' "$target"
  [ "$output" -eq 0 ]

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"

  # settings.json is never a target of this CLI invocation -- it is
  # untouched, byte-for-byte, because registration.py was never told about
  # it.
  _assert_bytes_equal "$original_legacy" "$legacy"

  # settings.local.json now carries its OWN full set of 3 ours-entries,
  # pointed at $HOME/.claude/observability/, alongside the untouched
  # "permissions" key.
  run grep -c -F '$HOME/.claude/observability/' "$target"
  [ "$output" -eq 3 ]
  _assert_contains "$(cat "$target")" '"allow"'
  _assert_contains "$(cat "$target")" "Bash(git:*)"

  # The net effect across BOTH files: six hooks now fire where three
  # should -- three legacy (in-repo path) plus three new (namespace path).
  # This is the number the task that produced this file measured by hand;
  # this test is what makes that number regression-proof.
  local total
  total="$(cat "$legacy" "$target" | grep -c -F '"type": "command"')"
  [ "$total" -eq 6 ]

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  # settings.json (legacy) is STILL untouched -- removal only ever acts on
  # the --settings path it is given, same as setup.
  _assert_bytes_equal "$original_legacy" "$legacy"
  # settings.local.json returns to the same DATA (permissions only),
  # reformatted rather than byte-identical -- same reflow reasoning as
  # foreign-only above.
  _assert_json_equal "$original_target" "$target"
  _assert_bytes_differ "$original_target" "$target"
}

# ---------------------------------------------------------------------------
# 11. not-a-repository -- plain directory, no .git/. registration.py has no
# git awareness (see write-path-not-ignored above) so this is identical to
# "absent" in every way that matters to the editor; the ".git/"-ness is
# entirely detect.sh's gate.
# ---------------------------------------------------------------------------

@test "not-a-repository: setup and removal behave exactly as on 'absent' -- the editor never checks for .git/" {
  local dir target
  dir="$(_copy_fixture not-a-repository not-a-repository)"
  target="$dir/.claude/settings.local.json"
  [ ! -e "$target" ]
  [ ! -d "$dir/.git" ]

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"
  [ -f "$target" ]

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  run cat "$target"
  [ "$output" = "{}" ]
}

# ---------------------------------------------------------------------------
# 12. ignored-file-but-not-backup -- "{}\n", same content as empty-object,
# distinguished only by its .gitignore (again, a detect.sh concern).
# ---------------------------------------------------------------------------

@test "ignored-file-but-not-backup: setup registers; removal restores byte-identical pre-setup content" {
  local dir target original
  dir="$(_copy_fixture ignored-file-but-not-backup ignored-file-but-not-backup)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/ignored-file-but-not-backup.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "registered observability hooks in"

  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"
  _assert_bytes_equal "$original" "$target"
}

# ---------------------------------------------------------------------------
# 13. valid-json-wrong-shape -- parses cleanly, "hooks" is a string not an
# object. Setup and removal are NOT symmetric here, unlike malformed/ above
# -- pinned as its own finding.
# ---------------------------------------------------------------------------

@test "valid-json-wrong-shape: setup refuses loudly (ValueError, exit 1); removal succeeds silently and reports 'nothing to remove' without ever inspecting the shape" {
  local dir target original
  dir="$(_copy_fixture valid-json-wrong-shape valid-json-wrong-shape)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/valid-json-wrong-shape.orig"
  cp -p "$target" "$original"

  _run_setup "$target"
  [ "$status" -eq 1 ]
  _assert_contains "$output" '"hooks" is not an object'
  _assert_bytes_equal "$original" "$target"

  # remove_registration() only ever checks `isinstance(hooks, dict)` and
  # silently skips the branch when that is false -- unlike add_registration,
  # it never raises on a malformed "hooks" shape. So the SAME file that
  # setup refused with a diagnosis is, for removal, indistinguishable from
  # a target with nothing of ours to remove at all: exit 0, no complaint
  # about the wrong shape, file untouched. Pinned as today's behaviour, not
  # endorsed as correct -- a maintainer relying on removal to surface shape
  # problems would not be told about this one.
  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "nothing to remove:"
  _assert_not_contains "$output" "not an object"
  _assert_bytes_equal "$original" "$target"
}

# ---------------------------------------------------------------------------
# Sidecar-file hygiene across the matrix -- backup_path/lock_path/temp_path
# (written_paths()) must never survive a completed setup+removal cycle,
# in ANY fixture, whether or not either step wrote.
# ---------------------------------------------------------------------------

@test "no .tcs-observability.bak / .lock / .tmp sidecar file survives a full setup+removal cycle, on any fixture" {
  local fixture dir target
  for fixture in absent empty-object foreign-only foreign-plus-ours-current \
                 foreign-plus-ours-older malformed non-ascii \
                 same-event-names-populated write-path-not-ignored \
                 already-configured-observability not-a-repository \
                 ignored-file-but-not-backup valid-json-wrong-shape; do
    dir="$(_copy_fixture "$fixture" "hygiene-$fixture")"
    target="$dir/.claude/settings.local.json"
    _run_setup "$target"
    _run_remove "$target"
    run find "$dir" -name '*.tcs-observability.*'
    [ "$status" -eq 0 ]
    [ -z "$output" ]
  done
}
