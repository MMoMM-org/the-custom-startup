#!/usr/bin/env bats
#
# tests/bats/lib-bundle.bats
#
# Test suite for templates/githooks/lib-bundle.sh
#
# Spec references:
#   - SDD §Implementation Examples / hook resolves its data dir without env vars
#   - SDD §ADR-6 — structured single-line stderr messages
#   - SDD §Building Block View — data dir path that nudge-hook.sh also writes to
#   - SDD §Constraints CON-7, CON-8, CON-9
#
# Constraints exercised:
#   - Bash 3.2 compatible (no declare -A, no mapfile, no flock)
#   - STDOUT silent — all diagnostics go to stderr only
#   - Safe to source under set -uo pipefail (no unbound variable errors)
#   - _resolve_data_dir returns non-zero when not inside a git repo

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  LIB="$PLUGIN_ROOT/templates/githooks/lib-bundle.sh"
  export TESTS_DIR PLUGIN_ROOT LIB

  # Sandbox: always use BATS_TEST_TMPDIR when available (sandbox-writable).
  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/lib-bundle.XXXXXX")"
  fi
  export TEST_DIR

  # Isolate git identity so tests don't depend on global config.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="bats"
  export GIT_AUTHOR_EMAIL="bats@tcs.invalid"
  export GIT_COMMITTER_NAME="bats"
  export GIT_COMMITTER_EMAIL="bats@tcs.invalid"

  # Unset plugin env vars so tests start from a known baseline.
  unset CLAUDE_PLUGIN_DATA CLAUDE_PLUGIN_ROOT 2>/dev/null || true
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# Build a minimal git repo in $1 with one commit.
_make_git_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q
  git -C "$dir" config user.email "bats@tcs.invalid"
  git -C "$dir" config user.name "bats"
  touch "$dir/.keep"
  git -C "$dir" add .keep
  git -C "$dir" commit -q -m "init"
}

# ---------------------------------------------------------------------------
# Sourcing guard: library must load cleanly
# ---------------------------------------------------------------------------

@test "lib-bundle.sh can be sourced without errors" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  run bash -c "set -uo pipefail; source \"$LIB\""
  [ "$status" -eq 0 ]
}

@test "lib-bundle.sh can be sourced under set -uo pipefail without unbound-variable errors" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  # Run in a subprocess that has CLAUDE_PLUGIN_DATA and CLAUDE_PLUGIN_ROOT
  # explicitly absent (not merely unset) so that ${VAR:-} expansion is tested.
  run env -u CLAUDE_PLUGIN_DATA -u CLAUDE_PLUGIN_ROOT \
    bash -c "set -uo pipefail; source \"$LIB\""
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# _resolve_data_dir: default path (no env vars)
# ---------------------------------------------------------------------------

@test "_resolve_data_dir returns HOME-based path when CLAUDE_PLUGIN_DATA unset" {
  _make_git_repo "$TEST_DIR/myrepo"
  cd "$TEST_DIR/myrepo"
  run env -u CLAUDE_PLUGIN_DATA \
    bash -c "source \"$LIB\"; _resolve_data_dir"
  [ "$status" -eq 0 ]
  # Path must contain tcs-git-helpers- prefix + repo basename
  [[ "$output" == "${HOME}/.claude/plugins/data/tcs-git-helpers-myrepo/cache" ]]
}

@test "_resolve_data_dir path contains the repo basename" {
  _make_git_repo "$TEST_DIR/project-alpha"
  cd "$TEST_DIR/project-alpha"
  run env -u CLAUDE_PLUGIN_DATA \
    bash -c "source \"$LIB\"; _resolve_data_dir"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tcs-git-helpers-project-alpha/cache" ]]
}

@test "_resolve_data_dir path format matches nudge-hook.sh cache dir convention" {
  # Validate that the default path is exactly:
  #   ${HOME}/.claude/plugins/data/tcs-git-helpers-<basename>/cache
  # This is the path that nudge-hook.sh resolves to (SDD Building Block View).
  _make_git_repo "$TEST_DIR/the-custom-startup"
  cd "$TEST_DIR/the-custom-startup"
  run env -u CLAUDE_PLUGIN_DATA \
    bash -c "source \"$LIB\"; _resolve_data_dir"
  [ "$status" -eq 0 ]
  local expected="${HOME}/.claude/plugins/data/tcs-git-helpers-the-custom-startup/cache"
  [ "$output" = "$expected" ]
}

# ---------------------------------------------------------------------------
# _resolve_data_dir: CLAUDE_PLUGIN_DATA override
# ---------------------------------------------------------------------------

@test "_resolve_data_dir respects explicit CLAUDE_PLUGIN_DATA override" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  local custom_dir="$TEST_DIR/custom-plugin-data"
  run bash -c "
    export CLAUDE_PLUGIN_DATA=\"$custom_dir\"
    source \"$LIB\"
    _resolve_data_dir
  "
  [ "$status" -eq 0 ]
  [ "$output" = "${custom_dir}/cache" ]
}

@test "_resolve_data_dir override does not append repo name when CLAUDE_PLUGIN_DATA set" {
  _make_git_repo "$TEST_DIR/some-project"
  cd "$TEST_DIR/some-project"
  local override="$TEST_DIR/override-data"
  run bash -c "
    export CLAUDE_PLUGIN_DATA=\"$override\"
    source \"$LIB\"
    _resolve_data_dir
  "
  [ "$status" -eq 0 ]
  # Must be exactly override/cache — not override/tcs-git-helpers-some-project/cache
  [ "$output" = "${override}/cache" ]
}

# ---------------------------------------------------------------------------
# _resolve_data_dir: not inside a git repo
# ---------------------------------------------------------------------------

@test "_resolve_data_dir exits non-zero when not inside a git repo" {
  local non_repo="$TEST_DIR/not-a-repo"
  mkdir -p "$non_repo"
  # Isolate from any parent git repo by redirecting GIT_DIR to non-existent path.
  run bash -c "
    unset CLAUDE_PLUGIN_DATA 2>/dev/null || true
    export GIT_DIR=\"$non_repo/.git-nonexistent\"
    export GIT_WORK_TREE=\"$non_repo\"
    cd \"$non_repo\"
    source \"$LIB\"
    _resolve_data_dir
  "
  [ "$status" -ne 0 ]
}

@test "_resolve_data_dir writes nothing to stdout when git repo is missing" {
  local non_repo="$TEST_DIR/no-git"
  mkdir -p "$non_repo"
  run bash -c "
    unset CLAUDE_PLUGIN_DATA 2>/dev/null || true
    export GIT_DIR=\"$non_repo/.git-absent\"
    export GIT_WORK_TREE=\"$non_repo\"
    cd \"$non_repo\"
    source \"$LIB\"
    _resolve_data_dir
  "
  # stdout must be empty on failure
  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# _emit_skip: stderr format (ADR-6)
# ---------------------------------------------------------------------------

@test "_emit_skip writes to stderr in the structured format" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  # run captures stdout in $output; stderr is discarded by default.
  # We redirect stderr to stdout to capture it.
  run bash -c "
    source \"$LIB\"
    _emit_skip 'cache-write' 'gh CLI not installed' 'Install gh to enable cleanup hints' 2>&1
  "
  [ "$status" -eq 0 ]
  [ "$output" = "tcs-git-helpers: cache-write skipped — gh CLI not installed. Install gh to enable cleanup hints." ]
}

@test "_emit_skip writes nothing to stdout" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  # Capture only stdout (stderr goes to /dev/null).
  run bash -c "
    source \"$LIB\"
    _emit_skip 'stale-refresh' 'no auth' 'Run gh auth login' 2>/dev/null
  "
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_emit_skip format: action field is preserved verbatim" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  run bash -c "
    source \"$LIB\"
    _emit_skip 'post-merge-cache' 'jq not found' 'Install jq' 2>&1
  "
  [[ "$output" == "tcs-git-helpers: post-merge-cache skipped"* ]]
}

@test "_emit_skip format: contains em-dash separator" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  run bash -c "
    source \"$LIB\"
    _emit_skip 'refresh' 'network error' 'Retry later' 2>&1
  "
  [[ "$output" == *" — "* ]]
}

@test "_emit_skip format: ends with a period" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  run bash -c "
    source \"$LIB\"
    _emit_skip 'cache-update' 'disk full' 'Free up space' 2>&1
  "
  [[ "$output" == *"." ]]
}

@test "_emit_skip: suggestion field is included in output" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  run bash -c "
    source \"$LIB\"
    _emit_skip 'hook-run' 'not in git repo' 'Ensure hook is installed in a git repository' 2>&1
  "
  [[ "$output" == *"Ensure hook is installed in a git repository"* ]]
}

@test "_emit_skip exits 0" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"
  run bash -c "
    source \"$LIB\"
    _emit_skip 'any-action' 'any-reason' 'any-suggestion' 2>/dev/null
  "
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# _guard_gh: absence check
# ---------------------------------------------------------------------------

@test "_guard_gh returns non-zero and emits structured skip line when gh is absent" {
  # Use PATH=/bin so bash is reachable but gh (typically in /usr/local/bin or
  # /opt/homebrew/bin) is not.
  run env -i HOME="$HOME" PATH="/bin" \
    /bin/bash -c "source \"$LIB\"; _guard_gh 'my-action' 2>&1"
  [ "$status" -ne 0 ]
  [[ "$output" == "tcs-git-helpers: my-action skipped — gh CLI not installed."* ]]
}

@test "_guard_jq returns non-zero and emits structured skip line when jq is absent" {
  # Use PATH=/bin only so bash is reachable but jq (in /usr/bin or
  # /opt/homebrew/bin) is not.
  run env -i HOME="$HOME" PATH="/bin" \
    /bin/bash -c "source \"$LIB\"; _guard_jq 'my-action' 2>&1"
  [ "$status" -ne 0 ]
  [[ "$output" == "tcs-git-helpers: my-action skipped — jq not installed."* ]]
}

# ---------------------------------------------------------------------------
# _write_stale_cache: atomic TSV+JSON dual-write
# ---------------------------------------------------------------------------

@test "_write_stale_cache writes TSV and JSON files under the resolved data dir" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local data_dir="$TEST_DIR/cache-out"
  local repo_path
  repo_path="$(git rev-parse --show-toplevel)"
  local repo_hash
  repo_hash="$(printf '%s' "$repo_path" | shasum | head -c 12)"
  local updated_iso="2026-05-13T12:00:00Z"

  run bash -c "
    export CLAUDE_PLUGIN_DATA='$TEST_DIR'
    source \"$LIB\"
    printf 'feat/stale-a\t38\t2026-04-12T10:00:00Z\nfix/stale-b\t40\t2026-04-15T09:00:00Z\n' \
      | _write_stale_cache '$updated_iso' '$repo_path' 'main'
  "
  [ "$status" -eq 0 ]

  # Both files must exist.
  local cache_dir="$TEST_DIR/cache"
  [ -f "$cache_dir/${repo_hash}-stale-cache.tsv" ]
  [ -f "$cache_dir/${repo_hash}-stale-cache.json" ]
}

@test "_write_stale_cache TSV contains input branch names verbatim" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local repo_path
  repo_path="$(git rev-parse --show-toplevel)"
  local repo_hash
  repo_hash="$(printf '%s' "$repo_path" | shasum | head -c 12)"

  run bash -c "
    export CLAUDE_PLUGIN_DATA='$TEST_DIR'
    source \"$LIB\"
    printf 'feat/my-branch\t99\t2026-01-01T00:00:00Z\n' \
      | _write_stale_cache '2026-05-13T12:00:00Z' '$repo_path' 'main'
  "
  [ "$status" -eq 0 ]

  grep -q "feat/my-branch" "$TEST_DIR/cache/${repo_hash}-stale-cache.tsv"
}

@test "_write_stale_cache JSON is valid and contains entries array" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local repo_path
  repo_path="$(git rev-parse --show-toplevel)"
  local repo_hash
  repo_hash="$(printf '%s' "$repo_path" | shasum | head -c 12)"

  run bash -c "
    export CLAUDE_PLUGIN_DATA='$TEST_DIR'
    source \"$LIB\"
    printf 'feat/alpha\t1\t2026-04-01T00:00:00Z\n' \
      | _write_stale_cache '2026-05-13T12:00:00Z' '$repo_path' 'main'
  "
  [ "$status" -eq 0 ]

  local json_file="$TEST_DIR/cache/${repo_hash}-stale-cache.json"
  # Must be valid JSON.
  run jq -e . "$json_file"
  [ "$status" -eq 0 ]

  # Must contain entries array.
  run jq -e '.entries | type == "array"' "$json_file"
  [ "$status" -eq 0 ]

  # Entry must have correct name.
  run jq -r '.entries[0].name' "$json_file"
  [ "$output" = "feat/alpha" ]
}

@test "_write_stale_cache JSON version field is 1" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local repo_path
  repo_path="$(git rev-parse --show-toplevel)"
  local repo_hash
  repo_hash="$(printf '%s' "$repo_path" | shasum | head -c 12)"

  run bash -c "
    export CLAUDE_PLUGIN_DATA='$TEST_DIR'
    source \"$LIB\"
    printf 'x\t1\t2026-01-01T00:00:00Z\n' \
      | _write_stale_cache '2026-05-13T12:00:00Z' '$repo_path' 'main'
  "
  [ "$status" -eq 0 ]

  run jq '.version' "$TEST_DIR/cache/${repo_hash}-stale-cache.json"
  [ "$output" = "1" ]
}

@test "_write_stale_cache writes atomically via .tmp+mv (no partial writes)" {
  # Verify no .tmp file is left behind after a successful write.
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local repo_path
  repo_path="$(git rev-parse --show-toplevel)"
  local repo_hash
  repo_hash="$(printf '%s' "$repo_path" | shasum | head -c 12)"

  run bash -c "
    export CLAUDE_PLUGIN_DATA='$TEST_DIR'
    source \"$LIB\"
    printf 'feat/x\t1\t2026-01-01T00:00:00Z\n' \
      | _write_stale_cache '2026-05-13T12:00:00Z' '$repo_path' 'main'
  "
  [ "$status" -eq 0 ]

  # No .tmp remnant files.
  local tmp_count
  tmp_count="$(find "$TEST_DIR/cache" -name '*.tmp' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$tmp_count" -eq 0 ]
}

@test "_write_stale_cache exits 0 even when cache dir creation fails" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local repo_path
  repo_path="$(git rev-parse --show-toplevel)"

  # Create a non-writable file at the cache dir path to make mkdir fail.
  local custom_data="$TEST_DIR/ro-data"
  mkdir -p "$custom_data"
  touch "$custom_data/cache"
  chmod 444 "$custom_data/cache"

  run bash -c "
    export CLAUDE_PLUGIN_DATA='$custom_data'
    source \"$LIB\"
    printf 'feat/x\t1\t2026-01-01T00:00:00Z\n' \
      | _write_stale_cache '2026-05-13T12:00:00Z' '$repo_path' 'main'
  "
  # Must exit 0 — cache failure must never block a merge.
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# _emit_stale_json: JSON output format
# ---------------------------------------------------------------------------

@test "_emit_stale_json produces valid JSON with correct version and entries" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local tsv_rows="feat/stale-a	38	2026-04-12T10:00:00Z
fix/stale-b	40	2026-04-15T09:00:00Z"

  run bash -c "
    source \"$LIB\"
    _emit_stale_json '$tsv_rows' '2026-05-13T12:00:00Z' 'main'
  "
  [ "$status" -eq 0 ]

  # Output must be valid JSON.
  printf '%s\n' "$output" | jq -e . >/dev/null

  # version must be 1.
  local version
  version="$(printf '%s\n' "$output" | jq '.version')"
  [ "$version" = "1" ]

  # entries must have both branches.
  local count
  count="$(printf '%s\n' "$output" | jq '.entries | length')"
  [ "$count" = "2" ]
}

@test "_emit_stale_json entries contain name and pr_number fields" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  # Write TSV data to a temp file to avoid quoting issues with tabs.
  local tsv_file="$TEST_DIR/input.tsv"
  printf 'my-branch\t42\t2026-03-01T00:00:00Z\n' > "$tsv_file"
  local tsv_rows
  tsv_rows="$(cat "$tsv_file")"

  local json_out
  json_out="$(bash -c "source \"$LIB\"; _emit_stale_json \"\$1\" '2026-05-13T12:00:00Z' 'main'" -- "$tsv_rows")"

  # name must match.
  local name
  name="$(printf '%s\n' "$json_out" | jq -r '.entries[0].name')"
  [ "$name" = "my-branch" ]

  # pr_number must be 42.
  local pr_number
  pr_number="$(printf '%s\n' "$json_out" | jq '.entries[0].pr_number')"
  [ "$pr_number" = "42" ]
}

@test "_emit_stale_json: empty TSV produces entries: []" {
  _make_git_repo "$TEST_DIR/repo"
  cd "$TEST_DIR/repo"

  local json_out
  json_out="$(bash -c "source \"$LIB\"; _emit_stale_json '' '2026-05-13T12:00:00Z' 'main'")"

  local count
  count="$(printf '%s\n' "$json_out" | jq '.entries | length')"
  [ "$count" = "0" ]
}
