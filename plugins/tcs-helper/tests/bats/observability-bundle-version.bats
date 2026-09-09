#!/usr/bin/env bats
#
# tests/bats/observability-bundle-version.bats
#
# spec 019 (observability rollout across active repos), Phase 1, T1.1 — "the
# bundle and its versioning". Adopts the spec-012 pattern (SDD/ADR-3): a
# version marker beside the observability bundle's sources, in the same
# `h<N>` convention as plugins/tcs-git-helpers/templates/githooks/
# tcs-git-helpers-version, deliberately not the plugin's semver
# (plugins/tcs-git-helpers/README.md:34).
#
# This suite covers only T1.1: the marker file and the helper that reads it.
# Installing the bundle into $HOME/.claude/observability/ is T1.2's job
# (plugins/tcs-helper/skills/observability-setup/lib/bundle_install.sh) and
# is not exercised here.
#
# bash 3.2 compatible (CON-1): PCRE \s/\b/\d and bounded quantifiers
# `^.{m,n}$` inside `[[ =~ ]]` silently match nothing under bash 3.2's regex
# engine. This suite is run under both plain `bats` and
# `/bin/bash $(command -v bats) ...` to prove it.

bats_require_minimum_version 1.5.0

setup() {
  # Derived via git, not a fixed relative-path count — robust to this file
  # moving and to being invoked from any cwd (same rationale as
  # observability-writer.bats's setup()).
  REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  MARKER="$REPO_ROOT/plugins/tcs-helper/templates/observability/tcs-helper-observability-version"
  HELPER="$REPO_ROOT/plugins/tcs-helper/skills/observability-setup/lib/bundle_version.sh"
  GIT_HELPERS_MARKER="$REPO_ROOT/plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version"

  # macOS exports TMPDIR with a trailing slash; strip it so fixture paths
  # never carry a "//" (same normalization as observability-writer.bats).
  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-obs-bundle-version.XXXXXX")"
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && chmod -R u+rwX "$TEST_DIR" 2>/dev/null
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# ---------------------------------------------------------------------------
# 1. The marker file itself: exists, single `h<N>` line, nothing else.
# ---------------------------------------------------------------------------

# Every byte of "$1" is an ASCII digit (0x30-0x39), as a hex byte string.
# A guard rather than a bare [[ ]]: a non-final bare [[ ]] in a bats body
# does not trip set -e, so the assertion would silently never fail.
_assert_ascii_digit_bytes() {
  local bytes="$1" label="$2"
  case "$bytes" in
    "") echo "$label has no version digits between the h and the newline" >&2; return 1 ;;
  esac
  local rest="$bytes"
  while [ -n "$rest" ]; do
    case "$rest" in
      3[0-9]*) rest="${rest#??}" ;;
      *) echo "$label contains a non-digit byte: $bytes" >&2; return 1 ;;
    esac
  done
  return 0
}

@test "marker: the template version file exists and contains a single h<N> line, starting at h1" {
  [ -f "$MARKER" ]

  run wc -l < "$MARKER"
  [ "${output// /}" = "1" ]

  local content
  content="$(cat "$MARKER")"
  case "$content" in
    h[[:digit:]]*) : ;;
    *) echo "marker is not of the form h<N>: $content" >&2; return 1 ;;
  esac
  [ "$content" = "h1" ]
}

@test "marker: byte format matches the tcs-git-helpers-version convention exactly (h<N> + trailing newline, nothing else)" {
  [ -f "$GIT_HELPERS_MARKER" ]

  # Same shape check applied to both files: h<N>, single trailing newline,
  # no other bytes. Not a byte-for-byte diff (the digits legitimately
  # differ — h1 vs h6) but the same convention, which is the stated success
  # criterion ("one convention covers both").
  run od -An -tx1 "$MARKER"
  local ours="${output//[$'\n ']/}"
  run od -An -tx1 "$GIT_HELPERS_MARKER"
  local theirs="${output//[$'\n ']/}"

  # Starts with 'h' (0x68), ends with a newline (0x0a).
  case "$ours" in 68*) : ;; *) echo "marker does not start with 'h': $ours" >&2; return 1 ;; esac
  case "$ours" in *0a) : ;; *) echo "marker does not end with a newline: $ours" >&2; return 1 ;; esac
  case "$theirs" in 68*) : ;; *) echo "git-helpers marker does not start with 'h': $theirs" >&2; return 1 ;; esac
  case "$theirs" in *0a) : ;; *) echo "git-helpers marker does not end with a newline: $theirs" >&2; return 1 ;; esac

  # Every byte between the leading 'h' and the trailing newline is an ASCII
  # digit (0x30-0x39) in both files.
  local mid="${ours#68}"
  mid="${mid%0a}"
  _assert_ascii_digit_bytes "$mid" "marker" || return 1
  mid="${theirs#68}"
  mid="${mid%0a}"
  _assert_ascii_digit_bytes "$mid" "git-helpers marker" || return 1
}

# ---------------------------------------------------------------------------
# 2. The read helper: valid marker.
# ---------------------------------------------------------------------------

@test "helper: reads the marker and returns its version verbatim on stdout, exit 0" {
  run bash -c ". '$HELPER' && _read_observability_bundle_version '$MARKER'"
  [ "$status" -eq 0 ]
  [ "$output" = "h1" ]
}

@test "helper: with no argument, resolves the bundle's own template marker by default" {
  run bash -c ". '$HELPER' && _read_observability_bundle_version"
  [ "$status" -eq 0 ]
  [ "$output" = "h1" ]
}

# ---------------------------------------------------------------------------
# 3. Absent marker: clear, non-empty stderr error; never an empty stdout
#    string (the specific failure this task guards against — an empty
#    return would later compare equal to everything in a drift check).
# ---------------------------------------------------------------------------

@test "helper: an absent marker file yields a non-empty stderr error, non-zero exit, and empty stdout" {
  local missing="$TEST_DIR/does-not-exist-version"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$missing'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

# ---------------------------------------------------------------------------
# 4. Malformed marker: several distinct malformed shapes, each rejected with
#    a non-empty, non-zero, empty-stdout error.
# ---------------------------------------------------------------------------

@test "helper: an empty marker file is malformed, not accepted" {
  local bad="$TEST_DIR/empty-version"
  : > "$bad"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

@test "helper: a marker with more than one line is malformed" {
  local bad="$TEST_DIR/multiline-version"
  printf 'h1\nextra\n' > "$bad"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

@test "helper: a semver-style marker (not h<N>) is malformed" {
  local bad="$TEST_DIR/semver-version"
  printf '1.2.3\n' > "$bad"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

@test "helper: trailing garbage after the digits is malformed" {
  local bad="$TEST_DIR/trailing-version"
  printf 'h1x\n' > "$bad"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

@test "helper: 'h' with no digits is malformed" {
  local bad="$TEST_DIR/nodigits-version"
  printf 'h\n' > "$bad"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

@test "helper: trailing whitespace after the version is malformed" {
  local bad="$TEST_DIR/trailingws-version"
  printf 'h1 \n' > "$bad"
  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
  [ -n "$stderr" ]
}

# ---------------------------------------------------------------------------
# 5. Absent vs malformed: distinguishable error text, not the same message
#    reused for both — a caller needs to tell "nothing installed yet" apart
#    from "something is broken".
# ---------------------------------------------------------------------------

@test "helper: absent and malformed errors are textually distinguishable from each other" {
  local missing="$TEST_DIR/still-missing-version"
  local bad="$TEST_DIR/still-malformed-version"
  printf 'nope\n' > "$bad"

  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$missing'"
  [ "$status" -ne 0 ]
  local missing_err="$stderr"

  run --separate-stderr bash -c ". '$HELPER' && _read_observability_bundle_version '$bad'"
  [ "$status" -ne 0 ]
  local malformed_err="$stderr"

  [ -n "$missing_err" ]
  [ -n "$malformed_err" ]
  [ "$missing_err" != "$malformed_err" ]

  # Not just "different strings" — anchored to the qualitatively distinct
  # words a human (or a drift-check caller deciding "install" vs "repair")
  # would grep for.
  case "$missing_err" in
    *"not found"*) : ;;
    *) echo "absent-marker error does not say 'not found': $missing_err" >&2; return 1 ;;
  esac
  case "$malformed_err" in
    *malformed*) : ;;
    *) echo "malformed-marker error does not say 'malformed': $malformed_err" >&2; return 1 ;;
  esac
  case "$missing_err" in
    *malformed*) echo "absent-marker error wrongly says 'malformed': $missing_err" >&2; return 1 ;;
  esac
  case "$malformed_err" in
    *"not found"*) echo "malformed-marker error wrongly says 'not found': $malformed_err" >&2; return 1 ;;
  esac
}
