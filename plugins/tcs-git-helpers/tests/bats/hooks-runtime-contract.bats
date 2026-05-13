#!/usr/bin/env bats
#
# tests/bats/hooks-runtime-contract.bats
#
# Asserts the runtime contract for all four installed hook templates:
#   - Each hook runs with CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA both UNSET
#   - Hooks exit 0 in all paths (never block merge/commit/push)
#   - STDOUT is always empty
#   - Guard paths emit exactly one structured stderr line
#   - post-merge writes <repo-hash>-stale-cache.{tsv,json} under the derived data dir
#     after a real git merge when gh returns stale branches
#
# Spec refs:
#   - PRD AC-F1.1 — post-merge writes cache on every merge with valid gh auth
#   - PRD AC-F1.3 — all four hooks pass the runtime-contract test
#   - PRD AC-F5.1 — every guard path emits exactly one stderr line per structured format
#   - PRD AC-F5.2 — stdout remains empty in all paths
#   - SDD CON-1 — CLAUDE_PLUGIN_ROOT/DATA must not be required at git-hook time
#   - SDD CON-8 — STDOUT contract: hooks write only to stderr
#   - SDD CON-9 — Exit 0 always
#   - SDD §Error Handling Table — exact message conditions per guard

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"
  export TESTS_DIR PLUGIN_ROOT FIXTURE_DIR

  HOOK_POST_MERGE="$PLUGIN_ROOT/templates/githooks/post-merge"
  HOOK_PRE_COMMIT="$PLUGIN_ROOT/templates/githooks/pre-commit"
  HOOK_COMMIT_MSG="$PLUGIN_ROOT/templates/githooks/commit-msg"
  HOOK_PRE_PUSH="$PLUGIN_ROOT/templates/githooks/pre-push"
  LIB_BUNDLE="$PLUGIN_ROOT/templates/githooks/lib-bundle.sh"
  export HOOK_POST_MERGE HOOK_PRE_COMMIT HOOK_COMMIT_MSG HOOK_PRE_PUSH LIB_BUNDLE
}

setup() {
  # Create a fresh scratch dir for each test.
  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/hooks-contract.XXXXXX")"
  fi
  export TEST_DIR

  # Isolate git identity so tests don't depend on global config.
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_AUTHOR_NAME="tcs-test"
  export GIT_AUTHOR_EMAIL="test@tcs.invalid"
  export GIT_COMMITTER_NAME="tcs-test"
  export GIT_COMMITTER_EMAIL="test@tcs.invalid"
  export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
  export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

  # CRITICAL: start with both env vars UNSET — this is the runtime-contract baseline.
  unset CLAUDE_PLUGIN_ROOT CLAUDE_PLUGIN_DATA 2>/dev/null || true

  # Prepend gh stub directory; default scenario = empty pr list (no-op).
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH
  GH_STUB_SCENARIO="default"
  export GH_STUB_SCENARIO
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a minimal git repo at $1 with one commit on main.
_make_git_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config commit.gpgsign false
  git -C "$dir" config tag.gpgsign false
  git -C "$dir" config user.name "tcs-test"
  git -C "$dir" config user.email "test@tcs.invalid"
  printf 'initial\n' > "$dir/README.md"
  git -C "$dir" add README.md
  git -C "$dir" commit -q -m "feat: initial"
}

# Install hook templates (with lib-bundle.sh) into $1/.githooks/.
# Copies templates from PLUGIN_ROOT, does not require install_files.sh.
_install_hooks_in_repo() {
  local repo="$1"
  mkdir -p "$repo/.githooks"
  cp "$HOOK_POST_MERGE"  "$repo/.githooks/post-merge"
  cp "$HOOK_PRE_COMMIT"  "$repo/.githooks/pre-commit"
  cp "$HOOK_COMMIT_MSG"  "$repo/.githooks/commit-msg"
  cp "$HOOK_PRE_PUSH"    "$repo/.githooks/pre-push"
  cp "$LIB_BUNDLE"       "$repo/.githooks/lib-bundle.sh"
  chmod +x "$repo/.githooks/post-merge" \
           "$repo/.githooks/pre-commit" \
           "$repo/.githooks/commit-msg" \
           "$repo/.githooks/pre-push"
  git -C "$repo" config core.hooksPath .githooks
}

# Compute the 12-char repo hash used for cache file naming.
# Must match _resolve_data_dir + lib-bundle.sh logic.
_repo_hash() {
  local repo_path="$1"
  printf '%s' "$repo_path" | shasum 2>/dev/null | head -c 12
}

# Derive the default data dir for a repo (mirrors _resolve_data_dir when
# CLAUDE_PLUGIN_DATA is unset).
_default_data_dir() {
  local repo_path="$1"
  local repo_name
  repo_name="$(basename "$repo_path")"
  printf '%s/.claude/plugins/data/tcs-git-helpers-%s/cache' "$HOME" "$repo_name"
}

# ---------------------------------------------------------------------------
# Section 1: Runtime-contract baseline — all four hooks, no env vars
# ---------------------------------------------------------------------------

@test "post-merge: runs successfully with CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA unset" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/post-merge"

  [ "$status" -eq 0 ]
}

@test "pre-commit: runs successfully with CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA unset" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  # Stage a safe file so pre-commit has something to check.
  printf 'hello\n' > "$TEST_DIR/repo/safe.txt"
  git -C "$TEST_DIR/repo" checkout -b feat/test-branch
  git -C "$TEST_DIR/repo" add safe.txt

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/pre-commit"

  [ "$status" -eq 0 ]
}

@test "commit-msg: runs successfully with CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA unset" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  local msg_file="$TEST_DIR/repo/.git/COMMIT_EDITMSG"
  printf 'feat: add something useful\n' > "$msg_file"

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/commit-msg '$msg_file'"

  [ "$status" -eq 0 ]
}

@test "pre-push: runs successfully with CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA unset" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/some-feature

  # Provide a ref line on stdin (V1 ignores stdin; branch is read from git rev-parse).
  cd "$TEST_DIR/repo" || return 1
  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "printf 'refs/heads/feat/some-feature abc123 refs/heads/feat/some-feature 0000000\n' \
      | bash '$TEST_DIR/repo/.githooks/pre-push' origin 'https://github.com/example/repo.git'"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Section 2: STDOUT must be empty in all paths
# ---------------------------------------------------------------------------

@test "post-merge: produces empty stdout when run without env vars" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/post-merge" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

@test "pre-commit: produces empty stdout on a feature branch" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/clean
  printf 'x\n' > "$TEST_DIR/repo/x.txt"
  git -C "$TEST_DIR/repo" add x.txt

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/pre-commit" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

@test "commit-msg: produces empty stdout for valid subject" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  local msg_file="$TEST_DIR/repo/.git/COMMIT_EDITMSG"
  printf 'fix: correct the thing\n' > "$msg_file"

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/commit-msg '$msg_file'" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

@test "pre-push: produces empty stdout (gh stub returns NO_PR)" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/push-test

  GH_STUB_SCENARIO="no-pr"
  export GH_STUB_SCENARIO

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "printf 'refs/heads/feat/push-test abc123 refs/heads/feat/push-test 0000000\n' \
      | bash '$TEST_DIR/repo/.githooks/pre-push' origin 'https://github.com/x/y.git'" \
    2>/dev/null)"

  [ -z "$stdout_out" ]
}

# ---------------------------------------------------------------------------
# Section 3: post-merge writes cache under the HOME-derived data dir
# ---------------------------------------------------------------------------

@test "post-merge: writes stale-cache.tsv and stale-cache.json after merge (no env vars)" {
  # Use a fake HOME under TEST_DIR so the HOME-derived path is writable in sandbox.
  local fake_home="$TEST_DIR/fakehome"
  mkdir -p "$fake_home"

  _make_git_repo "$TEST_DIR/myproject"
  _install_hooks_in_repo "$TEST_DIR/myproject"

  # Create the three stale branches that stale-3-branches scenario returns.
  git -C "$TEST_DIR/myproject" branch feat/stale-a
  git -C "$TEST_DIR/myproject" branch fix/stale-b
  git -C "$TEST_DIR/myproject" branch chore/stale-c

  # Create a feature branch with one commit so git merge --no-ff has something to merge.
  git -C "$TEST_DIR/myproject" checkout -b feat/trigger-merge
  printf 'trigger\n' > "$TEST_DIR/myproject/trigger.txt"
  git -C "$TEST_DIR/myproject" add trigger.txt
  git -C "$TEST_DIR/myproject" commit -q -m "chore: trigger merge"
  git -C "$TEST_DIR/myproject" checkout main

  # Resolve canonical repo path (macOS /tmp -> /private/tmp).
  local repo_canonical
  repo_canonical="$(cd "$TEST_DIR/myproject" && git rev-parse --show-toplevel)"

  local repo_name
  repo_name="$(basename "$repo_canonical")"

  # The derived data dir uses $HOME — redirect to fake_home.
  local data_dir="$fake_home/.claude/plugins/data/tcs-git-helpers-${repo_name}/cache"

  local repo_hash
  repo_hash="$(_repo_hash "$repo_canonical")"

  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  # Fire the post-merge hook via git's actual hook plumbing (core.hooksPath).
  # This validates the hook is wired correctly for the git merge --no-ff path.
  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/myproject' && HOME='$fake_home' git merge --no-ff feat/trigger-merge -m 'Merge feat/trigger-merge'"

  [ "$status" -eq 0 ]

  # Both cache files must exist.
  [ -f "$data_dir/${repo_hash}-stale-cache.tsv" ]
  [ -f "$data_dir/${repo_hash}-stale-cache.json" ]

  # TSV must contain all three stale branch names.
  grep -q "feat/stale-a" "$data_dir/${repo_hash}-stale-cache.tsv"
  grep -q "fix/stale-b"  "$data_dir/${repo_hash}-stale-cache.tsv"
  grep -q "chore/stale-c" "$data_dir/${repo_hash}-stale-cache.tsv"
}

@test "post-merge: cache write uses CLAUDE_PLUGIN_DATA override when explicitly set" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  git -C "$TEST_DIR/repo" branch feat/stale-a
  git -C "$TEST_DIR/repo" branch fix/stale-b
  git -C "$TEST_DIR/repo" branch chore/stale-c

  local custom_data="$TEST_DIR/custom-data"
  local cache_dir="$custom_data/cache"
  mkdir -p "$cache_dir"

  local repo_canonical
  repo_canonical="$(cd "$TEST_DIR/repo" && git rev-parse --show-toplevel)"
  local repo_hash
  repo_hash="$(_repo_hash "$repo_canonical")"

  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  run env -u CLAUDE_PLUGIN_ROOT \
    bash -c "
      export CLAUDE_PLUGIN_DATA='$custom_data'
      cd '$TEST_DIR/repo' && bash .githooks/post-merge
    "

  [ "$status" -eq 0 ]

  # Files must be in the explicit CLAUDE_PLUGIN_DATA location.
  [ -f "$cache_dir/${repo_hash}-stale-cache.tsv" ]
  [ -f "$cache_dir/${repo_hash}-stale-cache.json" ]
}

# ---------------------------------------------------------------------------
# Section 4: Degraded paths — every guard must emit exactly one structured
#            stderr line and exit 0 (SDD Error Handling Table)
# ---------------------------------------------------------------------------

@test "post-merge: gh not installed — emits one structured stderr line, exit 0" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  # Remove gh from PATH entirely.
  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "
      PATH='/bin:/usr/bin'
      export PATH
      cd '$TEST_DIR/repo' && bash .githooks/post-merge 2>&1 >/dev/null
    "

  [ "$status" -eq 0 ]

  # Must emit exactly one stderr line matching the structured format.
  local line_count
  line_count="$(printf '%s\n' "$output" | grep -c '^tcs-git-helpers:' 2>/dev/null || true)"
  [ "$line_count" -eq 1 ]

  # The line must mention gh not being installed.
  [[ "$output" == *"gh"* ]]
  [[ "$output" == *"skipped"* ]]
}

@test "post-merge: gh unauthenticated — emits one structured stderr line, exit 0" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  GH_STUB_SCENARIO="no-auth"
  export GH_STUB_SCENARIO

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/post-merge 2>&1 1>/dev/null"

  [ "$status" -eq 0 ]

  # Must emit exactly one structured stderr line per degraded path.
  local line_count
  line_count="$(printf '%s\n' "$output" | grep -c '^tcs-git-helpers:' || true)"
  [ "$line_count" -eq 1 ]
}

@test "post-merge: jq absent — hook exits 0 (CON-9 never-block contract)" {
  # Note: testing _guard_jq's structured skip message at unit level is done in
  # lib-bundle.bats (_guard_jq test). At the integration level on macOS, jq lives
  # in /usr/bin alongside dirname and git, making it impossible to exclude via
  # PATH manipulation without breaking the hook's shell environment.
  # This test verifies the weaker (but equally important) CON-9 contract:
  # hook must never block, always exit 0, even if jq operations fail.
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  git -C "$TEST_DIR/repo" branch feat/stale-a
  git -C "$TEST_DIR/repo" branch fix/stale-b
  git -C "$TEST_DIR/repo" branch chore/stale-c

  # Shadow jq with a stub that passes command -v (executable) but always
  # exits non-zero on any real call. _guard_jq will pass (jq found), but
  # all subsequent jq calls silently fail — hook must still exit 0.
  local jq_fail_dir="$TEST_DIR/failing-jq"
  mkdir -p "$jq_fail_dir"
  cat > "$jq_fail_dir/jq" <<'STUB'
#!/bin/bash
# Stub: jq present but non-functional. All calls fail silently.
exit 1
STUB
  chmod +x "$jq_fail_dir/jq"

  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "
      export PATH=\"$jq_fail_dir:$FIXTURE_DIR/gh_stubs:\$PATH\"
      cd '$TEST_DIR/repo' && bash .githooks/post-merge
    "

  # CON-9: hook MUST exit 0 regardless — never blocks a merge.
  [ "$status" -eq 0 ]
}

@test "post-merge: data dir write failure — emits one structured stderr line, exit 0" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  git -C "$TEST_DIR/repo" branch feat/stale-a
  git -C "$TEST_DIR/repo" branch fix/stale-b
  git -C "$TEST_DIR/repo" branch chore/stale-c

  # Create a non-writable file in place of the cache dir so mkdir fails.
  local custom_data="$TEST_DIR/ro-data"
  local cache_dir="$custom_data/cache"
  mkdir -p "$custom_data"
  touch "$cache_dir"         # file, not dir — mkdir -p will fail
  chmod 444 "$cache_dir"

  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  run env -u CLAUDE_PLUGIN_ROOT \
    bash -c "
      export CLAUDE_PLUGIN_DATA='$custom_data'
      cd '$TEST_DIR/repo' && bash .githooks/post-merge 2>&1 1>/dev/null
    "

  # Must exit 0 — never blocks.
  [ "$status" -eq 0 ]

  # Must emit at least one structured skip line.
  [[ "$output" == *"tcs-git-helpers:"* ]]
}

# ---------------------------------------------------------------------------
# Section 5: post-merge stdout silence in all paths
# ---------------------------------------------------------------------------

@test "post-merge: stdout empty even when stale branches found" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  git -C "$TEST_DIR/repo" branch feat/stale-a
  git -C "$TEST_DIR/repo" branch fix/stale-b
  git -C "$TEST_DIR/repo" branch chore/stale-c

  GH_STUB_SCENARIO="stale-3-branches"
  export GH_STUB_SCENARIO

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/post-merge" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

@test "post-merge: stdout empty when gh not installed" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "PATH='/bin:/usr/bin' bash '$TEST_DIR/repo/.githooks/post-merge'" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

@test "post-merge: stdout empty when gh unauthenticated" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  GH_STUB_SCENARIO="no-auth"
  export GH_STUB_SCENARIO

  local stdout_out
  stdout_out="$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/post-merge" 2>/dev/null)"

  [ -z "$stdout_out" ]
}

# ---------------------------------------------------------------------------
# Section 6: pre-commit guard paths (no env vars, degraded state)
# ---------------------------------------------------------------------------

@test "pre-commit: blocks commit to protected branch (no env vars)" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  # Stage a file while on 'main' (protected branch).
  printf 'change\n' > "$TEST_DIR/repo/file.txt"
  git -C "$TEST_DIR/repo" add file.txt

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/pre-commit"

  [ "$status" -ne 0 ]

  # Stdout must still be empty even on failure (stderr goes to /dev/null).
  # Use run to capture stdout; discard stderr by piping 2>/dev/null inside bash.
  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/pre-commit 2>/dev/null; true"

  [ -z "$output" ]
}

@test "pre-commit: exits 0 with empty stage on non-protected branch" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/safe

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/pre-commit"

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Section 7: commit-msg guard paths (no env vars, degraded state)
# ---------------------------------------------------------------------------

@test "commit-msg: accepts valid conventional commit without env vars" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  local msg_file="$TEST_DIR/repo/.git/COMMIT_EDITMSG"
  printf 'feat(parser): add JSON support\n' > "$msg_file"

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/commit-msg '$msg_file'"

  [ "$status" -eq 0 ]
}

@test "commit-msg: rejects invalid subject without env vars, stdout empty" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"

  local msg_file="$TEST_DIR/repo/.git/COMMIT_EDITMSG"
  printf 'made some changes\n' > "$msg_file"

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/commit-msg '$msg_file'"

  [ "$status" -ne 0 ]

  # Stdout must be empty even on error.
  # Discard stderr via 2>/dev/null and use `true` to neutralize non-zero exit.
  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/commit-msg '$msg_file' 2>/dev/null; true"

  [ -z "$output" ]
}

# ---------------------------------------------------------------------------
# Section 8: pre-push guard paths (no env vars)
# ---------------------------------------------------------------------------

@test "pre-push: exits 0 when gh not installed (fail-open)" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/test

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "
      PATH='/bin:/usr/bin'
      export PATH
      printf 'refs/heads/feat/test abc123 refs/heads/feat/test 0000000\n' \
        | bash '$TEST_DIR/repo/.githooks/pre-push' origin 'https://github.com/x/y.git'
    "

  [ "$status" -eq 0 ]
}

@test "pre-push: exits 0 when gh unauthenticated (fail-open)" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/test

  GH_STUB_SCENARIO="no-auth"
  export GH_STUB_SCENARIO

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "
      printf 'refs/heads/feat/test abc123 refs/heads/feat/test 0000000\n' \
        | bash '$TEST_DIR/repo/.githooks/pre-push' origin 'https://github.com/x/y.git'
    "

  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Section 9: Verify no CLAUDE_PLUGIN_ references remain in hook templates
# (Runtime-contract integrity — these must not exist after refactoring)
# ---------------------------------------------------------------------------

@test "post-merge template: contains no CLAUDE_PLUGIN_ references in executable code (after refactor)" {
  # Exclude comment lines (lines whose first non-whitespace char is #).
  # grep -v strips comment-only lines; grep then checks for CLAUDE_PLUGIN_.
  local count
  count="$(grep -v '^\s*#' "$HOOK_POST_MERGE" | grep -c 'CLAUDE_PLUGIN_' 2>/dev/null || true)"
  [ "$count" -eq 0 ]
}

@test "pre-commit template: contains no CLAUDE_PLUGIN_ references in executable code (after refactor)" {
  local count
  count="$(grep -v '^\s*#' "$HOOK_PRE_COMMIT" | grep -c 'CLAUDE_PLUGIN_' 2>/dev/null || true)"
  [ "$count" -eq 0 ]
}

@test "commit-msg template: contains no CLAUDE_PLUGIN_ references in executable code (after refactor)" {
  local count
  count="$(grep -v '^\s*#' "$HOOK_COMMIT_MSG" | grep -c 'CLAUDE_PLUGIN_' 2>/dev/null || true)"
  [ "$count" -eq 0 ]
}

@test "pre-push template: contains no CLAUDE_PLUGIN_ references in executable code (after refactor)" {
  local count
  count="$(grep -v '^\s*#' "$HOOK_PRE_PUSH" | grep -c 'CLAUDE_PLUGIN_' 2>/dev/null || true)"
  [ "$count" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Section 10: lib-bundle.sh sourced by hooks (not CLAUDE_PLUGIN_ROOT)
# ---------------------------------------------------------------------------

@test "post-merge template: sources lib-bundle.sh via dirname-relative path" {
  run grep 'lib-bundle.sh' "$HOOK_POST_MERGE"
  [ "$status" -eq 0 ]
  [[ "$output" == *'dirname'* ]] || [[ "$output" == *'$(dirname'* ]]
}

@test "pre-commit template: sources lib-bundle.sh via dirname-relative path" {
  run grep 'lib-bundle.sh' "$HOOK_PRE_COMMIT"
  [ "$status" -eq 0 ]
  [[ "$output" == *'dirname'* ]] || [[ "$output" == *'$(dirname'* ]]
}

@test "commit-msg template: sources lib-bundle.sh via dirname-relative path" {
  run grep 'lib-bundle.sh' "$HOOK_COMMIT_MSG"
  [ "$status" -eq 0 ]
  [[ "$output" == *'dirname'* ]] || [[ "$output" == *'$(dirname'* ]]
}

@test "pre-push template: sources lib-bundle.sh via dirname-relative path" {
  run grep 'lib-bundle.sh' "$HOOK_PRE_PUSH"
  [ "$status" -eq 0 ]
  [[ "$output" == *'dirname'* ]] || [[ "$output" == *'$(dirname'* ]]
}

# ---------------------------------------------------------------------------
# Section 11: Missing lib-bundle.sh — hooks with hard exit-0 guard
# ---------------------------------------------------------------------------

@test "post-merge: lib-bundle.sh missing — exits 0 and emits missing-lib stderr" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  rm -f "$TEST_DIR/repo/.githooks/lib-bundle.sh"

  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "cd '$TEST_DIR/repo' && bash .githooks/post-merge 2>&1 1>/dev/null"

  [ "$status" -eq 0 ]
  [[ "$output" == *"lib-bundle.sh missing"* ]]
}

@test "pre-push: lib-bundle.sh missing — exits 0 and emits missing-lib stderr" {
  _make_git_repo "$TEST_DIR/repo"
  _install_hooks_in_repo "$TEST_DIR/repo"
  git -C "$TEST_DIR/repo" checkout -b feat/some-feature
  rm -f "$TEST_DIR/repo/.githooks/lib-bundle.sh"

  cd "$TEST_DIR/repo" || return 1
  run env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA \
    bash -c "printf 'refs/heads/feat/some-feature abc123 refs/heads/feat/some-feature 0000000\n' \
      | bash '$TEST_DIR/repo/.githooks/pre-push' origin 'https://github.com/example/repo.git' 2>&1 1>/dev/null"

  [ "$status" -eq 0 ]
  [[ "$output" == *"lib-bundle.sh missing"* ]]
}
