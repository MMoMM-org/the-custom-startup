#!/usr/bin/env bats
#
# tests/bats/observability-settings-fixtures.bats
#
# spec 019 (observability rollout across active repos), Phase 2, T2.1 --
# "the fixture matrix". One sanity test per fixture built by
# fixtures/observability-settings/build.sh, so a broken fixture fails loudly
# here instead of silently weakening every later test (T2.2/T2.3/T2.5) that
# builds on it.
#
# Each test asserts the fixture's OBSERVABLE CHARACTERISTIC -- never
# directory existence alone (that is exactly the weak pattern
# skill_git_setup.bats:251-299 was cited as a cautionary example of, per
# plan/phase-2.md T2.1) -- and NEVER calls detect.sh or the merge: this task
# runs before both exist, and reaching for them here would reintroduce the
# backwards dependency the plan reordered T2.1 to remove. Every assertion
# reads file content directly.
#
# bash 3.2 compatible (CON-1): no `[[ =~ ]]` with PCRE classes or bounded
# quantifiers anywhere below; pattern checks go through grep/python3 instead.

bats_require_minimum_version 1.5.0

setup_file() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../../../.." && pwd)"
  BUILD_SH="$REPO_ROOT/plugins/tcs-helper/tests/fixtures/observability-settings/build.sh"
  MARKER_FILE="$REPO_ROOT/plugins/tcs-helper/templates/observability/tcs-helper-observability-version"
  export REPO_ROOT BUILD_SH MARKER_FILE

  # Isolate every git invocation in this file (build AND consumption, e.g.
  # check-ignore below) from the operator's real global/system git config.
  # Without this, `check-ignore` picked up this machine's real
  # ~/.config/git/ignore and produced a false "ignored" result for
  # write-path-not-ignored -- caught by this suite's own GREEN run.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  # macOS exports TMPDIR with a trailing slash; strip it so fixture paths
  # never carry a "//" (same normalization as observability-writer.bats).
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done

  FIXTURES_PARENT="$(mktemp -d "$tmpbase/tcs-obs-settings-fixtures.XXXXXX")"
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

_assert_is_repo() {
  # $1 = repo dir. `git log` succeeding is the T2.1-mandated proof that a
  # failed `git init` did not leak the fixture build onto the parent repo's
  # branch (docs/ai/memory/active.md).
  run git -C "$1" log --oneline
  [ "$status" -eq 0 ]
}

_assert_json_valid() {
  # $1 = file path.
  run python3 -c "import json; json.load(open(\"$1\"))"
  [ "$status" -eq 0 ]
}

_assert_json_invalid() {
  # $1 = file path. The malformed/ fixture: this must raise.
  run python3 -c "import json; json.load(open(\"$1\"))"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 1. absent -- no settings file at all
# ---------------------------------------------------------------------------

@test "fixture: absent has a repo with no .claude/ directory at all" {
  local repo="$FIXTURES_DIR/absent"
  _assert_is_repo "$repo"
  [ ! -e "$repo/.claude" ]
}

# ---------------------------------------------------------------------------
# 2. empty-object -- {}
# ---------------------------------------------------------------------------

@test "fixture: empty-object settings.local.json parses to an empty object" {
  local repo="$FIXTURES_DIR/empty-object"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  [ -f "$file" ]
  _assert_json_valid "$file"
  run python3 -c "import json; d = json.load(open(\"$file\")); raise SystemExit(0 if d == {} else 1)"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 3. foreign-only -- hooks present, none in our namespace
# ---------------------------------------------------------------------------

@test "fixture: foreign-only has a foreign hook entry and zero entries in our namespace" {
  local repo="$FIXTURES_DIR/foreign-only"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$file"

  run grep -F "/opt/foreign-audit/hook.sh" "$file"
  [ "$status" -eq 0 ]

  run grep -F '$HOME/.claude/observability/' "$file"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 4/5. foreign-plus-ours-current / foreign-plus-ours-older
#
# ADR-5 keeps the registration command opaque to bundle version, so both
# fixtures ship the SAME registration JSON (foreign entry + our three hook
# entries + env switch). What actually distinguishes "current" from "older"
# is the bundle version marker in the paired $HOME fixture, read from
# $HOME/.claude/observability/tcs-helper-observability-version -- so these
# two tests assert the repo content is right, then assert the paired home's
# marker is the one that makes this scenario "current" vs "older".
# ---------------------------------------------------------------------------

@test "fixture: foreign-plus-ours-current has foreign + all 3 ours entries, and a home bundle at the current version" {
  local repo="$FIXTURES_DIR/foreign-plus-ours-current"
  local home="$FIXTURES_DIR/foreign-plus-ours-current.home"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$file"

  run grep -F "/opt/foreign-audit/hook.sh" "$file"
  [ "$status" -eq 0 ]

  run grep -c -F '$HOME/.claude/observability/' "$file"
  [ "$output" -eq 3 ]

  local marker="$home/.claude/observability/tcs-helper-observability-version"
  [ -f "$marker" ]
  local expected
  expected="$(cat "$MARKER_FILE")"
  [ "$(cat "$marker")" = "$expected" ]
}

@test "fixture: foreign-plus-ours-older has foreign + all 3 ours entries, and a home bundle at an older version" {
  local repo="$FIXTURES_DIR/foreign-plus-ours-older"
  local home="$FIXTURES_DIR/foreign-plus-ours-older.home"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$file"

  run grep -F "/opt/foreign-audit/hook.sh" "$file"
  [ "$status" -eq 0 ]

  run grep -c -F '$HOME/.claude/observability/' "$file"
  [ "$output" -eq 3 ]

  local marker="$home/.claude/observability/tcs-helper-observability-version"
  [ -f "$marker" ]
  [ "$(cat "$marker")" = "h0" ]

  # The two fixtures' registration JSON must be byte-identical -- that is
  # the whole point of ADR-5. Verify it here rather than merely asserting
  # it in a comment.
  local current_repo="$FIXTURES_DIR/foreign-plus-ours-current"
  diff -q "$file" "$current_repo/.claude/settings.local.json"
}

# ---------------------------------------------------------------------------
# 6. malformed -- unparseable
# ---------------------------------------------------------------------------

@test "fixture: malformed settings.local.json fails to parse as JSON" {
  local repo="$FIXTURES_DIR/malformed"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  [ -f "$file" ]
  _assert_json_invalid "$file"
}

# ---------------------------------------------------------------------------
# 7. non-ascii -- valid JSON, non-ASCII values in foreign content
# ---------------------------------------------------------------------------

@test "fixture: non-ascii settings.local.json is valid JSON carrying raw non-ASCII bytes" {
  local repo="$FIXTURES_DIR/non-ascii"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$file"

  # Raw UTF-8 in the file, not an escaped \uXXXX sequence -- proves the
  # fixture itself is a genuine non-ASCII byte stream for T2.3's
  # ensure_ascii=False assertion to exercise later.
  run grep -F "Café" "$file"
  [ "$status" -eq 0 ]
  run grep -F "日本語" "$file"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 8. same-event-names-populated -- foreign entries under OUR event names
# ---------------------------------------------------------------------------

@test "fixture: same-event-names-populated has foreign entries under our event names and zero ours entries" {
  local repo="$FIXTURES_DIR/same-event-names-populated"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$file"

  # Pin each event key to the specific foreign command that sits under it --
  # a grep for unlinked substrings would still pass if the fixture's
  # commands were scrambled across event keys, even though that linkage is
  # the entire point of this fixture (T2.3 must prove a foreign entry under
  # OUR event name survives a merge).
  run python3 -c "import json; d = json.load(open(\"$file\")); h = d[\"hooks\"]; ok = (h[\"InstructionsLoaded\"][0][\"hooks\"][0][\"command\"] == \"/opt/foreign-audit/on-load.sh\" and h[\"PreToolUse\"][0][\"hooks\"][0][\"command\"] == \"/opt/foreign-audit/hook.sh\" and h[\"SubagentStart\"][0][\"hooks\"][0][\"command\"] == \"/opt/foreign-audit/on-subagent.sh\" and \"\$HOME/.claude/observability/\" not in json.dumps(h)); raise SystemExit(0 if ok else 1)"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 9. write-path-not-ignored
# ---------------------------------------------------------------------------

@test "fixture: write-path-not-ignored does NOT gitignore .claude/settings.local.json" {
  local repo="$FIXTURES_DIR/write-path-not-ignored"
  _assert_is_repo "$repo"

  run git -c core.excludesFile=/dev/null -C "$repo" check-ignore ".claude/settings.local.json"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 10. already-configured-observability -- the shipping repo's real state
# ---------------------------------------------------------------------------

@test "fixture: already-configured-observability reproduces this repo's legacy hand-made state" {
  local repo="$FIXTURES_DIR/already-configured-observability"
  local shared="$repo/.claude/settings.json"
  local local_file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$shared"
  _assert_json_valid "$local_file"

  # The legacy entries live in settings.json, pointing at an in-repo path --
  # NOT $HOME/.claude/observability/ (that collision with ADR-5 is the
  # whole reason this fixture exists).
  run grep -F "CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability" "$shared"
  [ "$status" -eq 0 ]
  run grep -F '$HOME/.claude/observability/' "$shared"
  [ "$status" -ne 0 ]

  # settings.local.json holds no hooks at all -- a detector reading only
  # that file would (wrongly) call this repo clean.
  run grep -F '"hooks"' "$local_file"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 11. not-a-repository
# ---------------------------------------------------------------------------

@test "fixture: not-a-repository is a plain directory with no .git/" {
  local dir="$FIXTURES_DIR/not-a-repository"
  [ -d "$dir" ]
  run git -C "$dir" rev-parse --git-dir
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 12. ignored-file-but-not-backup
# ---------------------------------------------------------------------------

@test "fixture: ignored-file-but-not-backup ignores the settings file by exact name but not its .bak sibling" {
  local repo="$FIXTURES_DIR/ignored-file-but-not-backup"
  _assert_is_repo "$repo"
  _assert_json_valid "$repo/.claude/settings.local.json"

  run git -c core.excludesFile=/dev/null -C "$repo" check-ignore ".claude/settings.local.json"
  [ "$status" -eq 0 ]

  run git -c core.excludesFile=/dev/null -C "$repo" check-ignore ".claude/settings.local.json.tcs-observability.bak"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# 13. valid-json-wrong-shape
# ---------------------------------------------------------------------------

@test "fixture: valid-json-wrong-shape parses cleanly but hooks is the wrong type" {
  local repo="$FIXTURES_DIR/valid-json-wrong-shape"
  local file="$repo/.claude/settings.local.json"
  _assert_is_repo "$repo"
  _assert_json_valid "$file"

  run python3 -c "import json; d = json.load(open(\"$file\")); raise SystemExit(0 if isinstance(d[\"hooks\"], str) else 1)"
  [ "$status" -eq 0 ]
}
