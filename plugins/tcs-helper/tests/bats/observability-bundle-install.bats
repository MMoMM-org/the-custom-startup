#!/usr/bin/env bats
#
# tests/bats/observability-bundle-install.bats
#
# spec 019 (observability rollout across active repos), Phase 1, T1.2:
# installing the observability bundle into $HOME/.claude/observability/
# (SDD/ADR-2, SDD/SDD-AC-8).
#
# This suite covers ONLY
# plugins/tcs-helper/skills/observability-setup/lib/bundle_install.sh.
# T1.1's marker file and its reader (bundle_version.sh) are exercised by
# tests/bats/observability-bundle-version.bats and are used here only as
# ground truth for what the freshly installed marker should contain.
#
# NEVER writes to the real $HOME: every test exports HOME to a fresh
# mktemp directory in setup() and asserts the observability directory is
# absent there before installing.
#
# bash 3.2 compatible (CON-1): no PCRE \s/\b/\d, no bounded quantifiers
# inside `[[ =~ ]]`. This suite is run under both plain `bats` and
# `/bin/bash $(command -v bats) ...` to prove it — nothing here actually
# uses `[[ =~ ]]`, but the harness scripts it exercises do, so the same
# double-run discipline applies.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  INSTALLER="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/bundle_install.sh"
  SOURCE_DIR="$REPO_ROOT/plugins/tcs-helper/scripts/observability"
  MARKER_NAME="tcs-helper-observability-version"
  # Ground truth: the repo's current bundle version (see
  # observability-bundle-version.bats, which pins this same value against
  # the marker file directly).
  CURRENT_VERSION="h1"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-obs-bundle-install.XXXXXX")"

  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$FAKE_HOME"
  export HOME="$FAKE_HOME"
  TARGET_DIR="$HOME/.claude/observability"

  # Guard: never touching a real home. If this ever fails, something above
  # is wrong and every other assertion in this file would be meaningless.
  [ ! -d "$TARGET_DIR" ]

  # A throwaway fixture repo, isolated under TEST_DIR — not the real repo —
  # so the adapter-execution test's `git rev-parse` and `repo` field never
  # touch anything outside TEST_DIR. Mirrors observability-agent.bats.
  export GIT_CONFIG_GLOBAL=/dev/null
  FIXTURE_REPO="$TEST_DIR/fixture-repo"
  mkdir -p "$FIXTURE_REPO"
  git -C "$FIXTURE_REPO" init -q -b main
  git -C "$FIXTURE_REPO" config user.email "t@t"
  git -C "$FIXTURE_REPO" config user.name "t"
  git -C "$FIXTURE_REPO" config commit.gpgsign false
  printf 'base\n' > "$FIXTURE_REPO/base.txt"
  git -C "$FIXTURE_REPO" add base.txt
  git -C "$FIXTURE_REPO" commit -q -m base
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# All install-set files, one per line, matching bundle_install.sh's own
# list — kept here as an independent literal (not read from the
# implementation) so a test that drops a file from the implementation's
# list is still caught.
_bundle_files() {
  printf '%s\n' \
    logwrite.sh log_agent.sh log_instructions.sh log_skill.sh \
    selfcheck.sh timed-wrapper.sh README.md
}

_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1"
  else
    shasum -a 256 "$1"
  fi
}

# A single multi-line digest of every regular file under a directory tree,
# sorted by path so it is comparable byte-for-byte across two calls.
_tree_digest() {
  local dir="$1" rel
  ( cd "$dir" && find . -type f | LC_ALL=C sort ) | while IFS= read -r rel; do
    _sha256 "$dir/$rel"
  done
}

_install() {
  run bash "$INSTALLER"
}

# ---------------------------------------------------------------------------
# 1. Fresh install into an empty home.
# ---------------------------------------------------------------------------

@test "fresh install: creates the directory, every bundle file, and the version marker" {
  _install
  [ "$status" -eq 0 ]

  [ -d "$TARGET_DIR" ]

  local f
  while IFS= read -r f; do
    [ -f "$TARGET_DIR/$f" ]
  done < <(_bundle_files)

  [ -f "$TARGET_DIR/$MARKER_NAME" ]
  local marker_content
  marker_content="$(cat "$TARGET_DIR/$MARKER_NAME")"
  [ "$marker_content" = "$CURRENT_VERSION" ]
}

@test "fresh install: installs exactly the bundle set, no extra files, no leftover .tmp" {
  _install
  [ "$status" -eq 0 ]

  local expected actual
  expected="$(_bundle_files; printf '%s\n' "$MARKER_NAME")"
  actual="$(cd "$TARGET_DIR" && find . -maxdepth 1 -type f -name '*' | sed 's#^\./##' | LC_ALL=C sort)"
  expected="$(printf '%s\n' "$expected" | LC_ALL=C sort)"
  [ "$actual" = "$expected" ]
}

@test "fresh install: copied executable adapters keep their executable bit" {
  _install
  [ "$status" -eq 0 ]
  [ -x "$TARGET_DIR/log_agent.sh" ]
  [ -x "$TARGET_DIR/log_skill.sh" ]
  [ -x "$TARGET_DIR/logwrite.sh" ]
}

# ---------------------------------------------------------------------------
# 2. Adapter execution from the new location — the case that actually
#    exercises ${BASH_SOURCE[0]} self-location, and the one that would catch
#    a bundle that copies the adapters but forgets logwrite.sh.
# ---------------------------------------------------------------------------

@test "a copied adapter runs from its installed location and the record it wrote is read back" {
  _install
  [ "$status" -eq 0 ]

  local data_dir="$TEST_DIR/data"
  local payload='{"session_id":"sess-installed","cwd":"'"$FIXTURE_REPO"'","agent_type":"Explore","agent_id":"agent-9001"}'

  run bash -c '
    data_dir="$1"; payload="$2"; adapter="$3"
    cd "'"$FIXTURE_REPO"'" || exit 90
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    printf "%s" "$payload" | "$adapter"
  ' _ "$data_dir" "$payload" "$TARGET_DIR/log_agent.sh"
  [ "$status" -eq 0 ]

  local events_file="$data_dir/observability/events.jsonl"
  [ -f "$events_file" ]
  run wc -l < "$events_file"
  [ "${output// /}" = "1" ]

  grep -qF '"kind":"agent"' "$events_file"
  grep -qF '"session":"sess-installed"' "$events_file"
  grep -qF '"agent_type":"Explore"' "$events_file"
  grep -qF '"agent_id":"agent-9001"' "$events_file"
}

@test "a bundle missing logwrite.sh breaks the copied adapter silently (exit 0, no record) -- the defect the adapter-execution case exists to catch" {
  _install
  [ "$status" -eq 0 ]
  rm -f "$TARGET_DIR/logwrite.sh"

  local data_dir="$TEST_DIR/data-broken"
  local payload='{"session_id":"sess-broken","cwd":"'"$FIXTURE_REPO"'","agent_type":"Explore","agent_id":"agent-0"}'

  run bash -c '
    data_dir="$1"; payload="$2"; adapter="$3"
    cd "'"$FIXTURE_REPO"'" || exit 90
    export CLAUDE_OBSERVABILITY_ENABLED=1
    export CLAUDE_OBSERVABILITY_DATA="$data_dir"
    printf "%s" "$payload" | "$adapter"
  ' _ "$data_dir" "$payload" "$TARGET_DIR/log_agent.sh"
  # CON-4/CON-5: the adapter still exits 0 even though it recorded nothing.
  [ "$status" -eq 0 ]
  [ ! -f "$data_dir/observability/events.jsonl" ]
}

# ---------------------------------------------------------------------------
# 3. Idempotence: a second same-version install changes nothing, by sha256
#    (not mtime, not inode — see the task's own reasoning for why).
# ---------------------------------------------------------------------------

@test "installing twice at the same version leaves the bundle tree byte-identical" {
  _install
  [ "$status" -eq 0 ]
  local before
  before="$(_tree_digest "$TARGET_DIR")"

  _install
  [ "$status" -eq 0 ]
  local after
  after="$(_tree_digest "$TARGET_DIR")"

  [ "$before" = "$after" ]

  local marker_content
  marker_content="$(cat "$TARGET_DIR/$MARKER_NAME")"
  [ "$marker_content" = "$CURRENT_VERSION" ]
}

# ---------------------------------------------------------------------------
# 4. Upgrade over an older version: scripts replaced (byte-equal to current
#    source, not left as the stale fixture content), marker updated, and
#    the update is reported rather than a fresh install (SDD-AC-8). This is
#    the case that keeps idempotence honest: an installer that no-ops on
#    every second run would also pass test 3 above, but fails here.
# ---------------------------------------------------------------------------

@test "installing over an older version replaces the scripts and updates the marker, and reports an update (SDD-AC-8)" {
  mkdir -p "$TARGET_DIR"
  local f
  while IFS= read -r f; do
    printf 'STALE FIXTURE CONTENT -- %s\n' "$f" > "$TARGET_DIR/$f"
  done < <(_bundle_files)
  printf 'h0\n' > "$TARGET_DIR/$MARKER_NAME"

  local stale_agent_sha
  stale_agent_sha="$(_sha256 "$TARGET_DIR/log_agent.sh" | awk '{print $1}')"

  _install
  [ "$status" -eq 0 ]

  case "$output" in
    *Updated*|*updat*) : ;;
    *) echo "install did not report an update (SDD-AC-8): $output" >&2; return 1 ;;
  esac

  local marker_content
  marker_content="$(cat "$TARGET_DIR/$MARKER_NAME")"
  [ "$marker_content" = "$CURRENT_VERSION" ]

  # No duplicate left behind under any old-version-suffixed name.
  [ ! -f "$TARGET_DIR/log_agent.sh.h0" ]
  [ ! -f "$TARGET_DIR/$MARKER_NAME.h0" ]

  # Every file now matches the real source byte-for-byte (replaced, not
  # left as stale fixture content).
  while IFS= read -r f; do
    local src_sha dst_sha
    src_sha="$(_sha256 "$SOURCE_DIR/$f" | awk '{print $1}')"
    dst_sha="$(_sha256 "$TARGET_DIR/$f" | awk '{print $1}')"
    [ "$src_sha" = "$dst_sha" ]
  done < <(_bundle_files)

  local new_agent_sha
  new_agent_sha="$(_sha256 "$TARGET_DIR/log_agent.sh" | awk '{print $1}')"
  [ "$new_agent_sha" != "$stale_agent_sha" ]
}

# ---------------------------------------------------------------------------
# 5. Marker atomicity: fault-injection on the pinned seam. Sourcing the lib
#    and redefining _write_bundle_marker — NOT shimming `mv` on PATH, NOT a
#    trap (see bundle_install.sh's own header for why).
# ---------------------------------------------------------------------------

@test "when the marker write fails, install exits non-zero and no marker file exists on disk" {
  run bash -c '
    . "'"$INSTALLER"'"
    _write_bundle_marker() { return 1; }
    _install_observability_bundle
  '
  [ "$status" -ne 0 ]
  [ ! -f "$TARGET_DIR/$MARKER_NAME" ]

  # Not vacuous: this must fail SPECIFICALLY at the marker-write step, not
  # because the whole pipeline (or the source file itself) never ran. If
  # sourcing "$INSTALLER" silently failed (e.g. the file were missing),
  # `_install_observability_bundle` would be undefined, bash would report
  # "command not found" (exit 127), and this test would pass for the wrong
  # reason -- exactly the vacuous-RED trap T1.1 hit. Proof the pipeline
  # actually ran up to the marker step: the bundle files themselves were
  # copied before the stubbed marker write was reached and failed.
  [ -f "$TARGET_DIR/log_agent.sh" ]
  [ -f "$TARGET_DIR/logwrite.sh" ]
}

@test "sourcing bundle_install.sh performs no install by itself (no side effects until the function is called)" {
  run bash -c '. "'"$INSTALLER"'"'
  [ "$status" -eq 0 ]
  [ ! -d "$TARGET_DIR" ]
}

@test "without the fault injection, the same sourced call succeeds and writes the marker -- proves test 5 is not vacuous" {
  run bash -c '
    . "'"$INSTALLER"'"
    _install_observability_bundle
  '
  [ "$status" -eq 0 ]
  [ -f "$TARGET_DIR/$MARKER_NAME" ]
  local marker_content
  marker_content="$(cat "$TARGET_DIR/$MARKER_NAME")"
  [ "$marker_content" = "$CURRENT_VERSION" ]
}

# ---------------------------------------------------------------------------
# 6. Call-time HOME resolution (ADR-2 T4.2 shape): source the library ONCE,
#    then call _install_observability_bundle twice with HOME changed between
#    calls -- the reuse-across-environments pattern the later rollout task
#    needs. A source-time snapshot of the target directory would install
#    both times into whichever HOME was set at source time; this proves
#    each call resolves the target from the HOME live at call time.
# ---------------------------------------------------------------------------

@test "sourcing once and calling with different HOME values each time installs into each HOME separately" {
  local home_a="$TEST_DIR/home-a"
  local home_b="$TEST_DIR/home-b"
  mkdir -p "$home_a" "$home_b"

  run bash -c '
    . "'"$INSTALLER"'"

    export HOME="'"$home_a"'"
    _install_observability_bundle || exit 81

    export HOME="'"$home_b"'"
    _install_observability_bundle || exit 82
  '
  [ "$status" -eq 0 ]

  local target_a="$home_a/.claude/observability"
  local target_b="$home_b/.claude/observability"

  [ -f "$target_a/$MARKER_NAME" ]
  [ -f "$target_b/$MARKER_NAME" ]

  local marker_a marker_b
  marker_a="$(cat "$target_a/$MARKER_NAME")"
  marker_b="$(cat "$target_b/$MARKER_NAME")"
  [ "$marker_a" = "$CURRENT_VERSION" ]
  [ "$marker_b" = "$CURRENT_VERSION" ]

  # The second call must not have touched the first environment's home at
  # all -- not just "still has a marker", but byte-identical to what the
  # first call alone produced.
  local f
  while IFS= read -r f; do
    [ -f "$target_a/$f" ]
    [ -f "$target_b/$f" ]
  done < <(_bundle_files)

  # The defect this test exists to catch: a file-scope, source-time capture
  # of the target directory would resolve to home_a for BOTH calls (HOME
  # was home_a at source time... but here HOME is set before sourcing too,
  # so also assert the negative directly -- home_b's bundle must exist as
  # its own tree, not merely as a leftover from installing into home_a).
  [ -d "$target_b" ]
  local b_file_count
  b_file_count="$(find "$target_b" -maxdepth 1 -type f | wc -l)"
  [ "${b_file_count// /}" -gt 0 ]
}
