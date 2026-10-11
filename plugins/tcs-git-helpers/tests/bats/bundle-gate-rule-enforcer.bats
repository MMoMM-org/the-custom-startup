#!/usr/bin/env bats
#
# tests/bats/bundle-gate-rule-enforcer.bats
#
# The rule-enforcer pre-push bundle in scripts/ci/check-hook-bundle-version.sh
# (#174). The bundle had a marker and no gate row, and its template changed
# twice without a bump, so the drift check called stale installs current.
#
# The fixture tests build a throwaway git repo (never this repo's history).
# The last test reads this repo's tree: every *-version marker a plugin ships
# must have a row, so a new bundle cannot repeat the gap.

bats_require_minimum_version 1.5.0

load 'lib/helpers'

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"
  GATE_SCRIPT="$PLUGIN_ROOT/scripts/ci/check-hook-bundle-version.sh"
  export TESTS_DIR PLUGIN_ROOT REPO_ROOT GATE_SCRIPT

  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/bundle-gate-rule-enforcer.XXXXXX")"
  fi
  export TEST_DIR

  # Isolate git identity/config so a failed `git init` cannot fall back to
  # this repo's real .git/ and leak fixture commits onto the working branch.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="bats-ci"
  export GIT_AUTHOR_EMAIL="bats-ci@tcs.invalid"
  export GIT_COMMITTER_NAME="bats-ci"
  export GIT_COMMITTER_EMAIL="bats-ci@tcs.invalid"
  export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
  export GIT_COMMITTER_DATE="2026-01-01T00:00:00+0000"
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

RE_DIR="plugins/tcs-helper/templates/githooks"
RE_MARKER="plugins/tcs-helper/templates/githooks/tcs-helper-rule-enforcer-version"

_init_repo() {
  local repo="$TEST_DIR/repo"
  mkdir -p "$repo/$RE_DIR"
  git -C "$repo" init -q
  printf '#!/bin/bash\n# pre-push v1\n' > "$repo/$RE_DIR/pre-push-rule-enforcer.sh.j2"
  printf 'h1\n' > "$repo/$RE_MARKER"
  git -C "$repo" add .
  git -C "$repo" commit -q -m "baseline"
}

_head_sha() {
  git -C "$TEST_DIR/repo" rev-parse HEAD
}

_commit_all() {
  git -C "$TEST_DIR/repo" add .
  git -C "$TEST_DIR/repo" commit -q -m "$1"
}

@test "rule-enforcer .sh.j2 template changed without marker bump — exit non-zero, names both" {
  _init_repo
  local base_sha head_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# pre-push v2\n' > "$TEST_DIR/repo/$RE_DIR/pre-push-rule-enforcer.sh.j2"
  _commit_all "template v2, no marker bump"
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
  _has "$output" "$RE_DIR/pre-push-rule-enforcer.sh.j2"
  _has "$output" "$RE_MARKER"
}

@test "rule-enforcer template changed WITH marker bump — exit 0" {
  _init_repo
  local base_sha head_sha
  base_sha="$(_head_sha)"

  printf '#!/bin/bash\n# pre-push v2\n' > "$TEST_DIR/repo/$RE_DIR/pre-push-rule-enforcer.sh.j2"
  printf 'h2\n' > "$TEST_DIR/repo/$RE_MARKER"
  _commit_all "template v2 + marker bump"
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -eq 0 ]
}

@test "rule-enforcer: a new file of any extension in the template dir is gated" {
  _init_repo
  local base_sha head_sha
  base_sha="$(_head_sha)"

  printf 'helper\n' > "$TEST_DIR/repo/$RE_DIR/lib-rule-enforcer"
  _commit_all "new extensionless file, no marker bump"
  head_sha="$(_head_sha)"

  run bash "$GATE_SCRIPT" "${base_sha}..${head_sha}" "$TEST_DIR/repo"
  [ "$status" -ne 0 ]
  _has "$output" "$RE_DIR/lib-rule-enforcer"
}

@test "every *-version marker a plugin ships has a row in the gate table" {
  local markers marker missing=""
  markers="$(cd "$REPO_ROOT" && git ls-files 'plugins/*/templates/*-version' 'plugins/*/templates/**/*-version')"
  [ -n "$markers" ]

  while IFS= read -r marker; do
    [ -z "$marker" ] && continue
    grep -qF -- "|${marker}|" "$GATE_SCRIPT" || missing="${missing} ${marker}"
  done <<EOF
$markers
EOF

  [ -z "$missing" ] || { printf 'markers without a gate row:%s\n' "$missing" >&2; return 1; }
}
