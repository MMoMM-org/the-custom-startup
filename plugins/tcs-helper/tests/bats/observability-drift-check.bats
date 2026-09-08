#!/usr/bin/env bats
#
# tests/bats/observability-drift-check.bats
#
# spec 019 (observability rollout across active repos), Phase 1, T1.3:
# drift detection for the installed observability bundle
# (plugins/tcs-helper/skills/observability-setup/lib/drift_check.sh).
#
# This suite covers ONLY drift_check.sh's comparator,
# _drift_check_observability_bundle. It reuses T1.2's
# bundle_install.sh (for _bundle_install_target_dir and
# $_BUNDLE_INSTALL_MARKER_NAME) and T1.1's marker format (h<N>) as ground
# truth, but does not re-test either of those files' own behaviour —
# see observability-bundle-install.bats and
# observability-bundle-version.bats for that coverage.
#
# The three-state contract mirrored here (OK / MISSING / DRIFT:<installed>)
# is defined by plugins/tcs-git-helpers/scripts/lib/drift_check.sh:25-41 —
# see drift_check.sh's own header for why it is duplicated rather than
# sourced across the plugin boundary.
#
# NEVER writes to the real $HOME: every test exports HOME to a fresh
# mktemp directory in setup().
#
# bash 3.2 compatible (CON-1): this suite is run under both plain `bats`
# and `/bin/bash $(command -v bats) ...` to prove it.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  HELPER="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/drift_check.sh"
  MARKER_NAME="tcs-helper-observability-version"
  EXPECTED_VERSION="h1"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-obs-drift-check.XXXXXX")"

  FAKE_HOME="$TEST_DIR/home"
  mkdir -p "$FAKE_HOME"
  export HOME="$FAKE_HOME"
  TARGET_DIR="$HOME/.claude/observability"

  # Guard: never touching a real home.
  [ ! -d "$TARGET_DIR" ]
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# 1. OK: installed marker matches expected version.
# ---------------------------------------------------------------------------

@test "OK: an installed marker matching the expected version reports OK" {
  mkdir -p "$TARGET_DIR"
  printf 'h1\n' > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ---------------------------------------------------------------------------
# 2. DRIFT: an older installed version names both versions, and the shape
#    is exactly "DRIFT:<installed>" — nothing else appended.
# ---------------------------------------------------------------------------

@test "DRIFT: an older installed version reports DRIFT:<installed-version> naming the stale version" {
  mkdir -p "$TARGET_DIR"
  printf 'h0\n' > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h0" ]
}

@test "DRIFT: a newer installed version also reports DRIFT, not OK" {
  mkdir -p "$TARGET_DIR"
  printf 'h99\n' > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h99" ]
}

# ---------------------------------------------------------------------------
# 3. Malformed installed marker: reports DRIFT:<raw content>, per the
#    maintainer ruling that garbage is not the expected version and the
#    remedy (reinstall) is identical to the stale case. Asserted
#    explicitly so it reads as a decision, not an oversight.
# ---------------------------------------------------------------------------

@test "DRIFT: a malformed installed marker (not h<N>) reports DRIFT:<raw content>, not a fourth state" {
  mkdir -p "$TARGET_DIR"
  printf 'not-a-version\n' > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:not-a-version" ]
}

@test "DRIFT: an empty installed marker reports DRIFT: with nothing after the colon" {
  mkdir -p "$TARGET_DIR"
  : > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:" ]
}

@test "DRIFT: a multi-line installed marker reports DRIFT using only the first line, whitespace stripped" {
  mkdir -p "$TARGET_DIR"
  printf 'h0\nextra garbage\n' > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h0" ]
}

# ---------------------------------------------------------------------------
# 4. MISSING: no bundle installed at all, distinguished from DRIFT — no
#    colon anywhere in the output.
# ---------------------------------------------------------------------------

@test "MISSING: no installed marker at all reports MISSING, distinguished from DRIFT (no colon)" {
  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
  [[ "$output" != *:* ]]
}

@test "MISSING: an existing target directory with no marker file still reports MISSING" {
  mkdir -p "$TARGET_DIR"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

# ---------------------------------------------------------------------------
# 5. Default marker path resolution: with no explicit marker_path, the
#    comparator resolves the real installed location via
#    _bundle_install_target_dir() + $_BUNDLE_INSTALL_MARKER_NAME (T1.2),
#    not a hardcoded path.
# ---------------------------------------------------------------------------

@test "default path: resolves the installed marker via _bundle_install_target_dir(), not a hardcoded path" {
  mkdir -p "$TARGET_DIR"
  printf 'h1\n' > "$TARGET_DIR/$MARKER_NAME"

  run bash -c ". '$HELPER' && _bundle_install_target_dir"
  [ "$status" -eq 0 ]
  [ "$output" = "$TARGET_DIR" ]

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

@test "explicit marker_path argument overrides the default resolution" {
  local other_marker="$TEST_DIR/elsewhere-version"
  printf 'h1\n' > "$other_marker"

  # Nothing at the default location at all.
  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION' '$other_marker'"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ---------------------------------------------------------------------------
# 6. Read-only: exercises a path that actually reads a marker (not just the
#    MISSING branch, which opens no file), inside a write-protected
#    directory, and asserts a successful result plus that no write occurred.
# ---------------------------------------------------------------------------

@test "read-only: succeeds against a valid marker inside a write-protected directory, and writes nothing" {
  mkdir -p "$TARGET_DIR"
  printf 'h1\n' > "$TARGET_DIR/$MARKER_NAME"

  local before_listing
  before_listing="$(ls -la "$TARGET_DIR")"

  chmod 555 "$TARGET_DIR"

  # Prove the protection is actually in place, rather than assuming it —
  # this repo lives on a mounted volume (/Volumes/Moon), where chmod
  # semantics can diverge from expectations even for a non-root user, not
  # just when running as root.
  if echo "canary" > "$TARGET_DIR/test-write" 2>/dev/null; then
    skip "write-protected directory is actually writable (running as root, or a permissive filesystem)"
  fi
  rm -f "$TARGET_DIR/test-write"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"

  chmod u+rwx "$TARGET_DIR"

  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]

  local after_listing
  after_listing="$(ls -la "$TARGET_DIR")"
  [ "$before_listing" = "$after_listing" ]
}

@test "read-only: DRIFT case also succeeds against a write-protected directory" {
  mkdir -p "$TARGET_DIR"
  printf 'h0\n' > "$TARGET_DIR/$MARKER_NAME"

  chmod 555 "$TARGET_DIR"

  # See the OK-case test above for why this proves the protection directly
  # rather than assuming EUID != 0 implies it.
  if echo "canary" > "$TARGET_DIR/test-write" 2>/dev/null; then
    skip "write-protected directory is actually writable (running as root, or a permissive filesystem)"
  fi
  rm -f "$TARGET_DIR/test-write"

  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"

  chmod u+rwx "$TARGET_DIR"

  [ "$status" -eq 0 ]
  [ "$output" = "DRIFT:h0" ]
}

# ---------------------------------------------------------------------------
# 7. Exit code is always 0, across all four scenarios above (OK / DRIFT /
#    malformed-DRIFT / MISSING) — the check never fails closed.
# ---------------------------------------------------------------------------

@test "exit code is always 0 regardless of outcome" {
  # MISSING
  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]

  # OK
  mkdir -p "$TARGET_DIR"
  printf 'h1\n' > "$TARGET_DIR/$MARKER_NAME"
  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]

  # DRIFT
  printf 'h0\n' > "$TARGET_DIR/$MARKER_NAME"
  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]

  # malformed DRIFT
  printf 'garbage\n' > "$TARGET_DIR/$MARKER_NAME"
  run bash -c ". '$HELPER' && _drift_check_observability_bundle '$EXPECTED_VERSION'"
  [ "$status" -eq 0 ]
}
