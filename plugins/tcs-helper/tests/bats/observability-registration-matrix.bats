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
#   1. already-configured-observability: a FLAGLESS setup invocation does
#      NOT migrate the legacy settings.json registration; it adds a SECOND,
#      independent registration to settings.local.json, leaving six hooks
#      firing where three should. When this file was written that was the
#      whole story and the test below pinned it as a gap awaiting T4.1.
#      T4.1 has since landed (spec 019 phase 4, maintainer ruling (s)) and
#      the story now has two halves, both pinned below: the flagless
#      invocation still layers -- ADR-1 keeps this editor to the one
#      --settings path it is given, and that is deliberate, not a defect --
#      while `--migrate-legacy <shared>` performs the cross-file migration
#      as one operation. lib/setup.sh passes that flag on a LEGACY
#      classification, and its own suite
#      (plugins/tcs-helper/tests/bats/observability-setup.bats) asserts the
#      command-level outcome; what this file pins is the editor's own
#      boundary between the two.
#
#   2. foreign-plus-ours-current / foreign-plus-ours-older -- FIXED at the
#      root by 64c0db3, after this file's first version caught it (build.sh
#      used to concatenate a `"hooks": {...}` block from _foreign_hooks_json
#      with a SECOND `"hooks": {...}` block from _ours_hooks_json at the
#      same object nesting level, joined by a literal comma; json.loads
#      resolves duplicate object keys last-wins, so the parsed document
#      only ever had the "ours" hooks and the foreign PreToolUse/Bash entry
#      these two fixtures exist to model was structurally invisible to any
#      JSON-based consumer, including registration.py, even though grep -F
#      over the raw text still found it). 64c0db3 replaced both builders
#      with a single _foreign_plus_ours_hooks_json() that puts the foreign
#      and ours PreToolUse entries in ONE "hooks" object, so the foreign
#      entry now survives a parse. The two tests below pin what setup and
#      removal do against the CORRECTED fixture: setup is still a no-op
#      ("already configured", byte-identical -- unaffected by the fix,
#      since add_registration only ever looked at whether ITS OWN entries
#      already matched); removal now leaves the foreign entry standing
#      instead of leaving "{}" -- and that is the fix working as intended,
#      not a behaviour change in remove_registration, which has never
#      touched a foreign entry (see
#      test_removal_deletes_only_our_entries_foreign_entry_survives in
#      tests/tcs-helper/test_observability_registration.py:468, covering
#      the identical case against a hand-built document since T2.4, green
#      throughout). The old "{}" result was correct for the input it was
#      given -- a fixture whose foreign entry had already been discarded
#      by ITS OWN duplicate-key defect before registration.py ever read
#      it. What changed between this file's two versions is the fixture,
#      not the editor.
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
  # `--` so a needle that starts with a dash is a pattern, not an option.
  printf '%s' "$1" | grep -qF -- "$2"
}

_assert_not_contains() {
  ! printf '%s' "$1" | grep -qF -- "$2"
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
# See the file header's finding #2: build.sh used to give both fixtures a
# duplicate top-level "hooks" key, which shadowed the foreign PreToolUse/
# Bash entry out of existence for any JSON parser -- fixed at the root by
# 64c0db3 (_foreign_plus_ours_hooks_json merges foreign and ours into ONE
# "hooks" object). What follows pins the CORRECTED fixture. Setup's half is
# unchanged from this file's first version, because add_registration was
# never looking at the foreign entry either way. Removal's half is not --
# it now has a real foreign entry to leave standing, and it does, exactly
# as test_removal_deletes_only_our_entries_foreign_entry_survives
# (tests/tcs-helper/test_observability_registration.py:468) has pinned
# against a hand-built document since T2.4. remove_registration's own
# behaviour never changed; only the fixture did.
#
# Both assertions below go through a JSON parse (_assert_json_equal against
# a literal expected document), not a raw-text grep -- a raw-text check is
# exactly what let the old duplicate-key defect hide from
# observability-settings-fixtures.bats for as long as it did.
# ---------------------------------------------------------------------------

@test "foreign-plus-ours-current: setup is a no-op ('already configured'); removal leaves the foreign entry standing and prunes only ours" {
  local dir target original expected
  dir="$(_copy_fixture foreign-plus-ours-current foreign-plus-ours-current)"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/foreign-plus-ours-current.orig"
  cp -p "$target" "$original"

  # add_registration sees data['hooks'] already carrying all three expected
  # ours-entries (now correctly alongside the foreign one, post-64c0db3) --
  # so status is 'none': nothing written.
  _run_setup "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "already configured:"
  _assert_bytes_equal "$original" "$target"

  # remove_registration prunes only what ADR-5 namespace membership marks
  # as ours: 'env' held only our switch (deleted entirely), and 'hooks.
  # PreToolUse' held both entries -- ours is stripped out, the foreign one
  # is kept, same as any other fixture with a real foreign neighbour
  # (foreign-only, same-event-names-populated above).
  _run_remove "$target"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed observability hooks from"

  expected="$WORK_PARENT/foreign-plus-ours-current.expected"
  cat > "$expected" <<'EOF'
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "/opt/foreign-audit/hook.sh" }]}
    ]
  }
}
EOF
  _assert_json_equal "$expected" "$target"
}

@test "foreign-plus-ours-older: byte-identical to foreign-plus-ours-current (ADR-5: the command string is opaque to bundle version), same no-op/removal behaviour" {
  local dir target original current_target expected
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

  expected="$WORK_PARENT/foreign-plus-ours-older.expected"
  cat > "$expected" <<'EOF'
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "/opt/foreign-audit/hook.sh" }]}
    ]
  }
}
EOF
  _assert_json_equal "$expected" "$target"
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
# -- a promise made on setup's behalf. A FLAGLESS invocation of this editor
# cannot keep it: ADR-1 scopes the editor to the single --settings path it is
# given, and ownership in that file is proven by the
# $HOME/.claude/observability/ namespace (ADR-5), which settings.json's
# in-repo command path can never satisfy.
#
# T4.1 kept the promise by giving the editor a second path explicitly rather
# than by widening what "ours" means: `--migrate-legacy <shared>` removes the
# legacy entries from the shared file and adds the standard registration to
# --settings inside ONE run, under one lock (ruling (s): recording must never
# be simultaneously double and never silently off). The two tests below pin
# both sides of that boundary -- what the editor does when told nothing, and
# what it does when told where the legacy file is.
# ---------------------------------------------------------------------------

@test "already-configured-observability: a flagless setup adds a SECOND registration beside the untouched legacy one -- six hooks fire, not three" {
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

@test "already-configured-observability: --migrate-legacy takes the legacy entries out as the standard ones go in -- three hooks fire, not six" {
  local dir legacy target total
  dir="$(_copy_fixture already-configured-observability already-configured-migrate)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  run grep -c -F '"type": "command"' "$legacy"
  [ "$output" -eq 3 ]

  run python3 "$REGISTRATION_PY" --settings "$target" --migrate-legacy "$legacy"
  [ "$status" -eq 0 ]
  _assert_contains "$output" "removed legacy observability hooks"
  _assert_contains "$output" "InstructionsLoaded"
  _assert_contains "$output" "PreToolUse"
  _assert_contains "$output" "SubagentStart"
  _assert_contains "$output" "registered observability hooks in"

  # THE number: three, where the flagless invocation above leaves six.
  total="$(cat "$legacy" "$target" | grep -c -F '"type": "command"' || true)"
  [ "$total" -eq 3 ]
  run grep -c -F '$HOME/.claude/observability/' "$target"
  [ "$output" -eq 3 ]
  run grep -c -F 'plugins/tcs-helper/scripts/observability' "$legacy"
  [ "$status" -ne 0 ]

  # Nothing of ours is left in the shared file: not the env switch, and not
  # an emptied "hooks" container either. This fixture's shared file held only
  # the legacy registration, so a complete removal leaves the empty document.
  run cat "$legacy"
  [ "$output" = "{}" ]

  # Content of the shared file this editor never authored is still there.
  _assert_contains "$(cat "$target")" "Bash(git:*)"

  # No backup outlives a completed migration, on either file.
  [ ! -e "$legacy.tcs-observability.bak" ]
}

@test "already-configured-observability: --migrate-legacy leaves a foreign entry in the shared file standing" {
  local dir legacy target
  dir="$(_copy_fixture already-configured-observability already-configured-migrate-foreign)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  python3 - "$legacy" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["hooks"]["PreToolUse"].append(
    {"matcher": "Bash", "hooks": [{"type": "command", "command": "/opt/foreign-audit/hook.sh"}]}
)
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  run python3 "$REGISTRATION_PY" --settings "$target" --migrate-legacy "$legacy"
  [ "$status" -eq 0 ]

  # The legacy trio is gone; the foreign entry sharing one of their event
  # names is not. Ownership in the SHARED file is the event name AND the
  # adapter script name together -- never the event name alone, which would
  # take a third party's hook out with ours.
  _assert_contains "$(cat "$legacy")" "/opt/foreign-audit/hook.sh"
  run grep -c -F '"type": "command"' "$legacy"
  [ "$output" -eq 1 ]
}

@test "already-configured-observability: --migrate-legacy leaves a shared entry that already points at the bundle alone" {
  local dir legacy target
  dir="$(_copy_fixture already-configured-observability already-configured-migrate-ns)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  # One of the three shared entries already points at $HOME/.claude/
  # observability/ -- a hand-migration someone did halfway. That entry is
  # OURS, not LEGACY, and the legacy sweep must not take it: ownership in the
  # shared file is the event name AND the in-repo script path together, and
  # dropping the namespace half of that test would make an already-migrated
  # entry look like one still to migrate.
  python3 - "$legacy" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
data["hooks"]["PreToolUse"] = [
    {"matcher": "Skill", "hooks": [
        {"type": "command", "command": '"$HOME/.claude/observability/log_skill.sh"'}]}
]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY

  run python3 "$REGISTRATION_PY" --settings "$target" --migrate-legacy "$legacy"
  [ "$status" -eq 0 ]

  # The two genuinely legacy entries are gone; the bundle-pointing one stays.
  run grep -c -F '"type": "command"' "$legacy"
  [ "$output" -eq 1 ]
  _assert_contains "$(cat "$legacy")" '$HOME/.claude/observability/log_skill.sh'
  _assert_not_contains "$(cat "$legacy")" "plugins/tcs-helper/scripts/observability"
}

@test "already-configured-observability: --remove --remove-legacy takes out both registrations" {
  local dir legacy target
  dir="$(_copy_fixture already-configured-observability already-configured-remove-legacy)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"

  run python3 "$REGISTRATION_PY" --settings "$target" --migrate-legacy "$legacy"
  [ "$status" -eq 0 ]

  run python3 "$REGISTRATION_PY" --settings "$target" --remove --remove-legacy "$legacy"
  [ "$status" -eq 0 ]

  run grep -c -F '"type": "command"' "$legacy"
  [ "$status" -ne 0 ]
  run grep -c -F '$HOME/.claude/observability/' "$target"
  [ "$status" -ne 0 ]
  _assert_contains "$(cat "$target")" "Bash(git:*)"
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

# ---------------------------------------------------------------------------
# The ordering inside a migration, pinned at the editor because that is where
# it lives. detect.sh now rejects a shape-invalid local file before setup.sh
# ever gets here, so these two reach registration.py directly -- which is
# exactly what makes them a test of the ORDER rather than of the gate. Move
# _strip_legacy back above the local load and validate, and the first one
# goes red.
# ---------------------------------------------------------------------------

@test "--migrate-legacy validates the local document BEFORE it writes to the shared one" {
  local dir legacy target original
  dir="$(_copy_fixture already-configured-observability migrate-order)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/migrate-order.shared.orig"
  cp -p "$legacy" "$original"
  printf '%s\n' '{ "env": "not-an-object" }' > "$target"

  run python3 "$REGISTRATION_PY" --settings "$target" --migrate-legacy "$legacy"
  [ "$status" -ne 0 ]

  # The shared file never moved. This is the whole assertion: the second half
  # cannot fail on shape after the first half has already written, because the
  # shape is checked first.
  _assert_bytes_equal "$original" "$legacy"
  [ ! -e "$legacy.tcs-observability.bak" ]
  _assert_contains "$output" "nothing was written"
}

@test "--migrate-legacy names both files and the restore command when the second half fails after the first wrote" {
  local dir legacy target original
  dir="$(_copy_fixture already-configured-observability migrate-partial)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/migrate-partial.shared.orig"
  cp -p "$legacy" "$original"

  # The residual case Fix 1 cannot remove: the shared write succeeds and the
  # LOCAL write then fails on I/O rather than on shape. Injected through the
  # filesystem rather than a code seam -- a directory where the settings file
  # belongs makes os.replace fail at the last step of write_settings, after
  # _strip_legacy has already completed.
  rm -f "$target"
  mkdir -p "$target"
  printf 'x\n' > "$target/occupied"

  run python3 "$REGISTRATION_PY" --settings "$target" --migrate-legacy "$legacy"
  [ "$status" -ne 0 ]

  # The shared file DID change -- and the report says so, names the backup,
  # and gives the command that puts it back. Recording is off until someone
  # acts, and the operator is told that rather than told the opposite.
  _assert_bytes_differ "$original" "$legacy"
  [ -f "$legacy.tcs-observability.bak" ]
  _assert_contains "$output" "PARTIAL MIGRATION"
  _assert_contains "$output" "This target is NOT recording"
  _assert_contains "$output" "$legacy.tcs-observability.bak"
  _assert_contains "$output" "cp -p"
  _assert_not_contains "$output" "Traceback"

  # The backup is a faithful copy of what the shared file held before.
  _assert_bytes_equal "$original" "$legacy.tcs-observability.bak"
}

@test "--remove survives a non-string command under an event we do not register" {
  local dir target
  dir="$(_copy_fixture absent remove-nonstring-command)"
  target="$dir/.claude/settings.local.json"
  mkdir -p "$dir/.claude"

  # remove_registration walks EVERY event in the document, not only the three
  # we register, so it reaches commands no validator has screened. A
  # non-string command here used to reach `NAMESPACE in 123` and raise a
  # TypeError that nothing caught.
  printf '%s\n' '{ "hooks": { "Notification": [ { "matcher": "", "hooks": [ { "type": "command", "command": 123 } ] } ] } }' > "$target"

  run python3 "$REGISTRATION_PY" --settings "$target" --remove
  [ "$status" -eq 0 ]
  _assert_contains "$output" "nothing to remove"
  _assert_not_contains "$output" "Traceback"
  # The foreign entry is untouched -- a non-string command is not ours.
  _assert_contains "$(cat "$target")" '"command": 123'
}

# ---------------------------------------------------------------------------
# The flag surface. --migrate-legacy is read only on the add path and
# --remove-legacy only on the remove path, so each combined with the wrong
# verb used to be accepted and silently ignored. lib/setup.sh is the only
# caller today and never does either; a future one deserves an error rather
# than silence.
# ---------------------------------------------------------------------------

@test "--migrate-legacy with --remove is refused rather than silently ignored" {
  local dir legacy target original
  dir="$(_copy_fixture already-configured-observability flags-migrate-remove)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/flags-migrate-remove.orig"
  cp -p "$legacy" "$original"

  run python3 "$REGISTRATION_PY" --settings "$target" --remove --migrate-legacy "$legacy"
  [ "$status" -ne 0 ]
  _assert_contains "$output" "--migrate-legacy"
  _assert_bytes_equal "$original" "$legacy"
}

@test "--remove-legacy without --remove is refused rather than silently ignored" {
  local dir legacy target original
  dir="$(_copy_fixture already-configured-observability flags-removelegacy-add)"
  legacy="$dir/.claude/settings.json"
  target="$dir/.claude/settings.local.json"
  original="$WORK_PARENT/flags-removelegacy-add.orig"
  cp -p "$legacy" "$original"

  run python3 "$REGISTRATION_PY" --settings "$target" --remove-legacy "$legacy"
  [ "$status" -ne 0 ]
  _assert_contains "$output" "--remove-legacy"
  _assert_bytes_equal "$original" "$legacy"
}
