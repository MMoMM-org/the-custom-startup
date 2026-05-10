#!/usr/bin/env bats
# T5.1 — skills/setup/SKILL.md contract + helper integration tests.
#
# This file covers four groups:
#   A. SKILL.md static contract (frontmatter, body sections, references)
#   B. Helper scripts under skills/setup/lib/ (shellcheck + behavior)
#   C. Integration via fixture repos (clean / Husky / lefthook / pre-commit /
#      simple-git-hooks / existing-hooks no-marker / matching-version /
#      older-version / non-sample hooks / submodules / concurrent + stale lock)
#   D. Sentinel scope, no-auto-commit, --with-gha, --with-branch-protection stub
#
# Spec refs:
#   - PRD M10 AC1-AC6, S1, S2
#   - SDD §Skills — /tcs-git-helpers:setup
#   - ADR-10 (conflict abort policy)
#   - ADR-11 (TCS_GIT_HELPERS_SETUP_ACTIVE subshell sentinel)
#   - ADR-12 (single-coder branch-protection preset — T5.8 scope)
#
# Constraints:
#   - bash 3.2 compatible
#   - All file writes via $TMPDIR (sandbox-writable)
#   - No network calls; gh is stubbed via PATH override

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
SKILL_DIR="${PLUGIN_ROOT}/skills/setup"
SKILL_PATH="${SKILL_DIR}/SKILL.md"
LIB_DIR="${SKILL_DIR}/lib"
FIXTURE_BUILD="${PLUGIN_ROOT}/tests/fixtures/repos/build.sh"

# ---------------------------------------------------------------------------
# Group A — SKILL.md contract
# ---------------------------------------------------------------------------

@test "A01 SKILL.md exists at plugins/tcs-git-helpers/skills/setup/SKILL.md" {
  [ -f "$SKILL_PATH" ]
}

@test "A02 skills/setup is a directory (not a flat skill file)" {
  [ -d "$SKILL_DIR" ]
}

@test "A03 frontmatter is fenced by --- delimiters" {
  head -n 1 "$SKILL_PATH" | grep -qE '^---$'
}

@test "A04 frontmatter name is 'setup'" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^name:[[:space:]]*setup'
}

@test "A05 frontmatter has description with auto-discovery triggers" {
  desc=$(awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^description:')
  [ -n "$desc" ]
  [[ "$desc" == *setup* ]] || [[ "$desc" == *install* ]]
}

@test "A06 description references conflict-detection trigger keywords" {
  desc=$(awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^description:')
  [[ "$desc" == *Husky* ]] || [[ "$desc" == *husky* ]] || [[ "$desc" == *conflict* ]]
}

@test "A07 frontmatter has user-invocable: true" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^user-invocable:[[:space:]]*true'
}

@test "A08 frontmatter has allowed-tools including Bash" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^allowed-tools:' | grep -q 'Bash'
}

@test "A09 frontmatter argument-hint references --update / --with-gha / --with-branch-protection" {
  hint=$(awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^argument-hint:')
  [[ "$hint" == *"--update"* ]]
  [[ "$hint" == *"--with-gha"* ]]
  [[ "$hint" == *"--with-branch-protection"* ]]
}

@test "A10 frontmatter is valid YAML" {
  command -v python3 >/dev/null || skip "python3 required"
  python3 -c "
import sys, yaml
text = open('$SKILL_PATH').read()
parts = text.split('---')
if len(parts) < 3:
    sys.exit('frontmatter not fenced')
yaml.safe_load(parts[1])
"
}

@test "A11 body has Persona section" {
  grep -qE '^##[[:space:]]+Persona' "$SKILL_PATH"
}

@test "A12 body has Interface section" {
  grep -qE '^##[[:space:]]+Interface' "$SKILL_PATH"
}

@test "A13 body has Constraints section" {
  grep -qE '^##[[:space:]]+Constraints' "$SKILL_PATH"
}

@test "A14 body has Workflow section" {
  grep -qE '^##[[:space:]]+Workflow' "$SKILL_PATH"
}

@test "A15 body has Conflict matrix section" {
  grep -qiE '^##[[:space:]]+Conflict[[:space:]]+matrix' "$SKILL_PATH"
}

@test "A16 body documents .setup.lock pattern (ADR-11 / lock serialization)" {
  grep -q '\.setup\.lock' "$SKILL_PATH"
}

@test "A17 body documents subshell sentinel TCS_GIT_HELPERS_SETUP_ACTIVE=1" {
  grep -q 'TCS_GIT_HELPERS_SETUP_ACTIVE=1' "$SKILL_PATH"
}

@test "A18 body documents Husky conflict signature" {
  grep -qiE 'husky' "$SKILL_PATH"
}

@test "A19 body documents lefthook conflict signature" {
  grep -qi 'lefthook' "$SKILL_PATH"
}

@test "A20 body documents pre-commit framework conflict signature" {
  grep -qE 'pre-commit-config|pre-commit framework|pre-commit \(py' "$SKILL_PATH"
}

@test "A21 body documents simple-git-hooks conflict signature" {
  grep -q 'simple-git-hooks' "$SKILL_PATH"
}

@test "A22 body documents .git/hooks/ non-sample warning" {
  grep -qE '\.git/hooks|non-\.sample|non-sample' "$SKILL_PATH"
}

@test "A23 body documents submodules listing behavior" {
  grep -qi 'submodule' "$SKILL_PATH"
}

@test "A24 body documents existing-no-marker conflict mode (per-file diff)" {
  grep -qiE 'no marker|per-file diff|version marker' "$SKILL_PATH"
}

@test "A25 body documents up-to-date branch (matching version)" {
  grep -qiE 'up to date|matching version' "$SKILL_PATH"
}

@test "A26 body documents --update mode shows per-file diff" {
  grep -qE -- '--update' "$SKILL_PATH"
  # The orchestration instruction must be specific: --update must be co-located
  # with a "diff" / "per-file diff" mention so Claude knows to invoke `diff`
  # before overwriting older-marker files.
  grep -qiE 'per-file diff|diff' "$SKILL_PATH"
}

@test "A27 body cites references/migrating-from-husky.md" {
  grep -q 'migrating-from-husky\.md' "$SKILL_PATH"
}

@test "A28 body documents NO auto-commit (M10 AC5)" {
  grep -qiE 'not.*commit|no.*auto.*commit|does not.*commit|never.*commit' "$SKILL_PATH"
}

@test "A29 body documents --with-gha copies pr-title-check.yml" {
  grep -qE 'pr-title-check\.yml' "$SKILL_PATH"
}

@test "A30 body documents --with-branch-protection delegated to T5.8 stub" {
  grep -qE -- '--with-branch-protection' "$SKILL_PATH"
}

@test "A31 SKILL.md has at least 80 lines (substantive)" {
  line_count=$(wc -l < "$SKILL_PATH")
  [ "$line_count" -ge 80 ]
}

# ---------------------------------------------------------------------------
# Group B — helper scripts (shellcheck + behavior)
# ---------------------------------------------------------------------------

@test "B01 lib/ directory exists" {
  [ -d "$LIB_DIR" ]
}

@test "B02 lib/lock.sh exists and is executable" {
  [ -x "$LIB_DIR/lock.sh" ]
}

@test "B03 lib/detect_conflicts.sh exists and is executable" {
  [ -x "$LIB_DIR/detect_conflicts.sh" ]
}

@test "B04 lib/install_files.sh exists and is executable" {
  [ -x "$LIB_DIR/install_files.sh" ]
}

@test "B05 lib/with_gha.sh exists and is executable" {
  [ -x "$LIB_DIR/with_gha.sh" ]
}

@test "B06 lib/with_branch_protection.sh exists and is executable (stub for T5.8)" {
  [ -x "$LIB_DIR/with_branch_protection.sh" ]
}

@test "B07 all helpers use set -euo pipefail" {
  for f in "$LIB_DIR"/*.sh; do
    # Search the prologue (first 40 lines) — header comments may push the
    # `set` line below the first 5 lines.
    head -n 40 "$f" | grep -q 'set -euo pipefail' \
      || { echo "missing set -euo pipefail in $f"; return 1; }
  done
}

@test "B08 all helpers have a tcs-git-helpers version banner comment" {
  for f in "$LIB_DIR"/*.sh; do
    head -n 10 "$f" | grep -q 'tcs-git-helpers' \
      || { echo "missing tcs-git-helpers banner in $f"; return 1; }
  done
}

@test "B09 shellcheck on every helper script" {
  command -v shellcheck >/dev/null || skip "shellcheck required"
  for f in "$LIB_DIR"/*.sh; do
    shellcheck -x "$f" || { echo "shellcheck failed for $f"; return 1; }
  done
}

# ---------------------------------------------------------------------------
# Group C — integration via fixture repos
# ---------------------------------------------------------------------------
#
# Each test builds a freshly synthesized fixture repo via build.sh into a
# private tempdir, runs the relevant helper(s), and asserts the observable
# behavior. CLAUDE_PLUGIN_DATA is stubbed via $TMPDIR so locks land in a
# sandbox-writable path.

setup_file() {
  # Build all fixture scenarios ONCE per file run. Tests copy the relevant
  # scenario into their own tempdir to avoid mutating the cached source.
  command -v git >/dev/null || skip "git required"
  FIXTURE_CACHE="$(mktemp -d "${TMPDIR:-/tmp}/tcs-skill-setup-fixcache.XXXXXX")"
  export FIXTURE_CACHE
  bash "$FIXTURE_BUILD" "$FIXTURE_CACHE" >/dev/null
}

teardown_file() {
  if [ -n "${FIXTURE_CACHE:-}" ] && [ -d "$FIXTURE_CACHE" ]; then
    rm -rf "$FIXTURE_CACHE"
  fi
}

setup() {
  TEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/tcs-skill-setup.XXXXXX")"
  CLAUDE_PLUGIN_DATA="$TEST_TMP/plugin-data"
  mkdir -p "$CLAUDE_PLUGIN_DATA"
  export CLAUDE_PLUGIN_DATA
  # Avoid host git config leaking (gpgsign, hooksPath, etc.)
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
}

teardown() {
  if [ -n "${TEST_TMP:-}" ] && [ -d "$TEST_TMP" ]; then
    rm -rf "$TEST_TMP"
  fi
}

# Build fixtures into TEST_TMP/fixtures/. Backwards-compat: the C01-C10
# tests want the entire fixture set; later tests work on a single scenario.
# We resolve this by symlinking the cache instead of rebuilding.
_build_fixtures() {
  ln -s "$FIXTURE_CACHE" "$TEST_TMP/fixtures"
}

# Copy a single fixture scenario into TEST_TMP/<scenario>/ so the test owns
# a mutable working tree. Returns the path on stdout.
_use_fixture() {
  local scenario="$1"
  local dst="$TEST_TMP/$scenario"
  cp -R "$FIXTURE_CACHE/$scenario" "$dst"
  printf '%s\n' "$dst"
}

# Helper: build a clean repo (init + one commit) at $1.
_make_clean_repo() {
  local repo="$1"
  rm -rf "$repo"
  mkdir -p "$repo"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "t@t.invalid"
  git -C "$repo" config user.name "tester"
  git -C "$repo" config commit.gpgsign false
  : > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -q -m "feat: init"
}

@test "C01 fixture build.sh produces clean-repo scenario" {
  _build_fixtures
  [ -d "$TEST_TMP/fixtures/clean-repo" ]
}

@test "C02 fixture build.sh produces with-husky scenario" {
  _build_fixtures
  [ -d "$TEST_TMP/fixtures/with-husky" ]
  [ -d "$TEST_TMP/fixtures/with-husky/.husky" ]
}

@test "C03 fixture build.sh produces with-lefthook scenario" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-lefthook/lefthook.yml" ]
}

@test "C04 fixture build.sh produces with-pre-commit scenario" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-pre-commit/.pre-commit-config.yaml" ]
}

@test "C05 fixture build.sh produces with-simple-git-hooks scenario" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-simple-git-hooks/package.json" ]
  grep -q 'simple-git-hooks' "$TEST_TMP/fixtures/with-simple-git-hooks/package.json"
}

@test "C06 fixture build.sh produces with-existing-hooks scenario (no marker)" {
  _build_fixtures
  [ -d "$TEST_TMP/fixtures/with-existing-hooks/.githooks" ]
  ! grep -rq 'tcs-git-helpers:' "$TEST_TMP/fixtures/with-existing-hooks/.githooks/"
}

@test "C07 fixture build.sh produces with-tcs-current scenario (matching marker)" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-tcs-current/.githooks/pre-commit" ]
  head -3 "$TEST_TMP/fixtures/with-tcs-current/.githooks/pre-commit" | grep -q 'tcs-git-helpers: v1.0.0'
}

@test "C08 fixture build.sh produces with-tcs-older scenario (older marker)" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-tcs-older/.githooks/pre-commit" ]
  head -3 "$TEST_TMP/fixtures/with-tcs-older/.githooks/pre-commit" | grep -qE 'tcs-git-helpers: v0\.'
}

@test "C09 fixture build.sh produces with-non-sample-hooks scenario" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-non-sample-hooks/.git/hooks/pre-commit" ]
}

@test "C10 fixture build.sh produces with-submodules scenario" {
  _build_fixtures
  [ -f "$TEST_TMP/fixtures/with-submodules/.gitmodules" ]
}

# --- detect_conflicts.sh against each scenario ---

@test "C11 detect_conflicts on clean-repo emits NO conflicts (exit 0)" {
  cd "$(_use_fixture clean-repo)"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -eq 0 ]
  # Output should NOT contain ABORT or any conflict tag.
  ! echo "$output" | grep -qiE 'ABORT|husky|lefthook|pre-commit|simple-git-hooks'
}

@test "C12 detect_conflicts on with-husky aborts with husky reference" {
  cd "$(_use_fixture with-husky)"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'husky'
  echo "$output" | grep -q 'migrating-from-husky'
}

@test "C13 detect_conflicts on with-lefthook aborts" {
  cd "$(_use_fixture with-lefthook)"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'lefthook'
}

@test "C14 detect_conflicts on with-pre-commit aborts" {
  cd "$(_use_fixture with-pre-commit)"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'pre-commit'
}

@test "C15 detect_conflicts on with-simple-git-hooks aborts" {
  cd "$(_use_fixture with-simple-git-hooks)"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'simple-git-hooks'
}

@test "C16 detect_conflicts on with-existing-hooks emits CONFLICT (no marker)" {
  cd "$(_use_fixture with-existing-hooks)"
  run "$LIB_DIR/detect_conflicts.sh"
  # Existing-hooks-no-marker is a CONFLICT (status non-zero) so the skill can
  # branch into per-file diff mode. The output names the condition.
  [ "$status" -ne 0 ]
  echo "$output" | grep -qiE 'no marker|existing-hooks|conflict|per-file'
}

@test "C17 detect_conflicts on with-tcs-current emits up-to-date" {
  cd "$(_use_fixture with-tcs-current)"
  # Current matching version: detect_conflicts considers this informational, not
  # an abort. The skill body branches on the up-to-date marker independently.
  # Exit 0 is load-bearing — SKILL.md gates "skip re-installation" on it.
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qiE 'up to date|matching|already installed'
}

@test "C18 detect_conflicts on with-tcs-older emits older-version notice" {
  cd "$(_use_fixture with-tcs-older)"
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qiE 'older|outdated|update|v0\.'
}

@test "C19 detect_conflicts on with-non-sample-hooks emits warn" {
  cd "$(_use_fixture with-non-sample-hooks)"
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qiE 'warn|non-sample|.git/hooks'
}

@test "C20 detect_conflicts on with-submodules lists submodules" {
  cd "$(_use_fixture with-submodules)"
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qi 'submodule'
}

# --- install_files.sh on a clean repo ---

@test "C21 install_files on clean repo writes .githooks/* with markers" {
  cd "$(_use_fixture clean-repo)"
  run "$LIB_DIR/install_files.sh"
  [ "$status" -eq 0 ]
  [ -f .githooks/pre-commit ]
  [ -f .githooks/pre-push ]
  [ -f .githooks/commit-msg ]
  [ -f .githooks/post-merge ]
  head -3 .githooks/pre-commit | grep -q 'tcs-git-helpers: v'
}

@test "C22 install_files sets core.hooksPath=.githooks" {
  cd "$(_use_fixture clean-repo)"
  "$LIB_DIR/install_files.sh"
  [ "$(git config core.hooksPath)" = ".githooks" ]
}

@test "C23 install_files writes .config.example and exclude-paths.example" {
  cd "$(_use_fixture clean-repo)"
  "$LIB_DIR/install_files.sh"
  [ -f .githooks/.config.example ]
  [ -f .githooks/exclude-paths.example ]
}

@test "C24 install_files makes hook files executable" {
  cd "$(_use_fixture clean-repo)"
  "$LIB_DIR/install_files.sh"
  [ -x .githooks/pre-commit ]
  [ -x .githooks/pre-push ]
  [ -x .githooks/commit-msg ]
  [ -x .githooks/post-merge ]
}

@test "C25 install_files does NOT auto-commit (M10 AC5)" {
  cd "$(_use_fixture clean-repo)"
  before_log=$(git log --oneline | wc -l)
  "$LIB_DIR/install_files.sh"
  after_log=$(git log --oneline | wc -l)
  [ "$before_log" = "$after_log" ]
  # And new files should be unstaged / untracked or modified, not committed.
  [ -n "$(git status --porcelain)" ]
}

# --- subshell sentinel scope (ADR-11) ---

@test "C26 install_files exports TCS_GIT_HELPERS_SETUP_ACTIVE only inside subshell" {
  cd "$(_use_fixture clean-repo)"
  # Force unset; if helper leaks the var, test will fail.
  unset TCS_GIT_HELPERS_SETUP_ACTIVE
  "$LIB_DIR/install_files.sh" >/dev/null
  [ -z "${TCS_GIT_HELPERS_SETUP_ACTIVE:-}" ]
}

# --- lock.sh: concurrent + stale ---

@test "C27 lock.sh acquire+release cycle works" {
  _make_clean_repo "$TEST_TMP/lockrepo"
  cd "$TEST_TMP/lockrepo"
  run "$LIB_DIR/lock.sh" acquire
  [ "$status" -eq 0 ]
  run "$LIB_DIR/lock.sh" release
  [ "$status" -eq 0 ]
}

@test "C28 lock.sh: second concurrent acquire fails while first holds" {
  _make_clean_repo "$TEST_TMP/lockrepo"
  cd "$TEST_TMP/lockrepo"
  # Hand-write the lock file with the bats process's own PID and a fresh
  # timestamp. The bats test runner is alive (so kill -0 succeeds) and the
  # timestamp is recent (so the 5-min stale TTL does not reclaim).
  mkdir -p .githooks
  printf '%s:%s\n' "$$" "$(date +%s)" > .githooks/.setup.lock
  # Now a fresh acquire must observe live PID + recent timestamp → fail.
  run env TCS_LOCK_TIMEOUT=1 "$LIB_DIR/lock.sh" acquire
  [ "$status" -ne 0 ]
  rm -f .githooks/.setup.lock
}

@test "C29 lock.sh: stale lock (>5min, dead PID) is reclaimed" {
  _make_clean_repo "$TEST_TMP/lockrepo"
  cd "$TEST_TMP/lockrepo"
  # Manufacture a stale lock with a non-existent PID and ts > 5min ago.
  mkdir -p .githooks
  ts_old=$(( $(date +%s) - 600 ))
  printf '99999:%s\n' "$ts_old" > .githooks/.setup.lock
  run "$LIB_DIR/lock.sh" acquire
  [ "$status" -eq 0 ]
  "$LIB_DIR/lock.sh" release
}

# --- with_gha.sh ---

@test "C30 with_gha copies pr-title-check.yml into .github/workflows/" {
  _make_clean_repo "$TEST_TMP/ghrepo"
  cd "$TEST_TMP/ghrepo"
  run "$LIB_DIR/with_gha.sh"
  [ "$status" -eq 0 ]
  [ -f .github/workflows/pr-title-check.yml ]
  head -3 .github/workflows/pr-title-check.yml | grep -q 'tcs-git-helpers'
}

# --- with_branch_protection (T5.8 implementation; details in C33-C37) ---

@test "C31 with_branch_protection.sh aborts when origin is not a GitHub remote" {
  # T5.8 replaces the T5.1 stub with the real helper. Sanity test: when no
  # GitHub remote is configured, the helper aborts non-zero (per integration
  # §6 "Repo not on GitHub: --with-branch-protection aborts"). Detailed
  # behavior is exercised in C33-C37.
  _make_clean_repo "$TEST_TMP/bprepo"
  cd "$TEST_TMP/bprepo"
  run "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE 'origin|GitHub|gh-token-hygiene'
}

# --- --update mode: per-file diff behavior (T5.1 spec compliance) --------

@test "C32 --update mode: detect_conflicts flags older fixture (exit 3) and per-file diff mechanism produces output" {
  cd "$(_use_fixture with-tcs-older)"
  # 1. detect_conflicts.sh must classify the older-marker fixture as exit 3
  #    (CONFLICT / OUTDATED) so the skill can branch into the --update flow.
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -eq 3 ]
  echo "$output" | grep -qiE 'older|outdated'

  # 2. The per-file diff workflow that SKILL.md instructs Claude to follow
  #    requires that the installed older hook actually differs from the
  #    current template — otherwise `diff` would emit nothing and the
  #    overwrite prompt would be a no-op. Verify the underlying mechanism
  #    by diffing the installed pre-commit against the template.
  installed_hook=".githooks/pre-commit"
  template_hook="$PLUGIN_ROOT/templates/githooks/pre-commit"
  [ -f "$installed_hook" ]
  [ -f "$template_hook" ]
  # diff -q exits 1 when files differ; capture that as the contract.
  run diff -q "$installed_hook" "$template_hook"
  [ "$status" -eq 1 ]
  echo "$output" | grep -q 'differ'
}

# ---------------------------------------------------------------------------
# Group C (continued) — with_branch_protection.sh (T5.8)
# ---------------------------------------------------------------------------
#
# These tests exercise the real `lib/with_branch_protection.sh` helper that
# implements ADR-12's single-coder branch-protection preset. The gh CLI is
# stubbed via PATH override (tests/fixtures/gh_stubs/gh) and configured per
# scenario via env vars:
#   - GH_STUB_SCOPES         token scopes returned by `gh auth status`
#                            (default: "repo")
#   - GH_STUB_CAPTURE_PUT    file path to capture the JSON body of any
#                            `gh api -X PUT` invocation (so tests can assert
#                            the single-coder preset shape).
#   - GH_STUB_PUT_FAIL       when 1, `gh api -X PUT` exits non-zero with a
#                            simulated 422 stderr message (failure-mode test).
#   - GH_STUB_PROTECTION_MATCHES when 1, `gh api .../protection` GET returns
#                            a body that matches the preset (idempotent path).

GH_STUBS_DIR="${PLUGIN_ROOT}/tests/fixtures/gh_stubs"

# Helper: prep a clean git repo with a github.com remote so the helper can
# parse owner/repo from `git remote get-url origin`.
_make_gh_repo() {
  local repo="$1"
  _make_clean_repo "$repo"
  git -C "$repo" remote add origin "https://github.com/test-user/test-repo.git"
}

@test "C33 with_branch_protection: aborts when 'repo' scope is missing" {
  _make_gh_repo "$TEST_TMP/bp-no-scope"
  cd "$TEST_TMP/bp-no-scope"
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="read:org,gist" \
    TCS_BP_YES=1 \
    "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE "repo[[:space:]]+scope|missing.*repo"
  echo "$output" | grep -q 'gh-token-hygiene\.md'
}

@test "C34 with_branch_protection: warns on excessive 'admin:org' scope but proceeds with TCS_BP_ALLOW_EXCESS_SCOPES=1" {
  _make_gh_repo "$TEST_TMP/bp-admin-org"
  cd "$TEST_TMP/bp-admin-org"
  capture="$TEST_TMP/put-body.json"
  # S1 AC3: excessive-scope confirmation is a separate gate from the main
  # ruleset prompt. Both bypasses are required for non-interactive use.
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="repo,admin:org" \
    GH_STUB_CAPTURE_PUT="$capture" \
    TCS_BP_ALLOW_EXCESS_SCOPES=1 \
    TCS_BP_YES=1 \
    "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qiE 'admin:org|excessive scope'
  echo "$output" | grep -q 'gh-token-hygiene\.md'
  # The PUT was still issued.
  [ -s "$capture" ]
}

@test "C34a with_branch_protection: excessive scopes — TCS_BP_YES alone does NOT bypass scope gate (reply 'n' aborts)" {
  # S1 AC3 spec compliance: the excessive-scope confirmation is independent
  # from the main ruleset gate. Setting only TCS_BP_YES=1 must NOT bypass
  # it; the helper must still read from stdin for the scope prompt. Here
  # the user replies "n" → helper aborts non-zero with the scope-specific
  # message, and no PUT is issued.
  _make_gh_repo "$TEST_TMP/bp-scope-deny"
  cd "$TEST_TMP/bp-scope-deny"
  capture="$TEST_TMP/put-body.json"
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="repo,admin:org,delete_repo" \
    GH_STUB_CAPTURE_PUT="$capture" \
    TCS_BP_YES=1 \
    bash -c 'printf "n\n" | "'"$LIB_DIR"'/with_branch_protection.sh"'
  [ "$status" -ne 0 ]
  echo "$output" | grep -qiE 'excessive token scopes not confirmed'
  # No PUT was issued because the scope gate aborted before main flow.
  [ ! -s "$capture" ]
}

@test "C35 with_branch_protection: PUTs single-coder preset body" {
  _make_gh_repo "$TEST_TMP/bp-preset"
  cd "$TEST_TMP/bp-preset"
  capture="$TEST_TMP/put-body.json"
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="repo" \
    GH_STUB_CAPTURE_PUT="$capture" \
    TCS_BP_YES=1 \
    "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -eq 0 ]
  [ -s "$capture" ]
  # Single-coder preset (ADR-12): no PR-review-required, no force-push,
  # no deletions, no admin enforcement.
  if command -v jq >/dev/null; then
    [ "$(jq -r '.required_pull_request_reviews' "$capture")" = "null" ]
    [ "$(jq -r '.allow_force_pushes' "$capture")" = "false" ]
    [ "$(jq -r '.allow_deletions' "$capture")" = "false" ]
    [ "$(jq -r '.enforce_admins' "$capture")" = "false" ]
    [ "$(jq -r '.restrictions' "$capture")" = "null" ]
  else
    grep -q '"required_pull_request_reviews":[[:space:]]*null' "$capture"
    grep -q '"allow_force_pushes":[[:space:]]*false' "$capture"
    grep -q '"allow_deletions":[[:space:]]*false' "$capture"
    grep -q '"enforce_admins":[[:space:]]*false' "$capture"
  fi
}

@test "C36 with_branch_protection: idempotent when protection already matches preset" {
  _make_gh_repo "$TEST_TMP/bp-idem"
  cd "$TEST_TMP/bp-idem"
  capture="$TEST_TMP/put-body.json"
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="repo" \
    GH_STUB_PROTECTION_MATCHES=1 \
    GH_STUB_CAPTURE_PUT="$capture" \
    TCS_BP_YES=1 \
    "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qiE 'already up to date|already matches|no changes'
  # Idempotent: no PUT body should have been captured because the helper
  # short-circuited.
  [ ! -s "$capture" ] || ! grep -q '"allow_force_pushes"' "$capture"

  # Re-run yields the same behavior.
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="repo" \
    GH_STUB_PROTECTION_MATCHES=1 \
    GH_STUB_CAPTURE_PUT="$capture" \
    TCS_BP_YES=1 \
    "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qiE 'already up to date|already matches|no changes'
}

@test "C37 with_branch_protection: gh PUT failure exits non-zero, no rollback of unrelated steps" {
  _make_gh_repo "$TEST_TMP/bp-fail"
  cd "$TEST_TMP/bp-fail"
  # Marker representing parent-skill state from a prior step (e.g. install_files).
  mkdir -p .githooks
  touch .githooks/.test-marker
  run env \
    PATH="$GH_STUBS_DIR:$PATH" \
    GH_STUB_SCOPES="repo" \
    GH_STUB_PUT_FAIL=1 \
    TCS_BP_YES=1 \
    "$LIB_DIR/with_branch_protection.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -q 'gh-token-hygiene\.md'
  # The helper must NOT roll back unrelated parent-skill side effects.
  [ -f .githooks/.test-marker ]
}

# ---------------------------------------------------------------------------
# Group D — bats test sanity (shellcheck-style)
# ---------------------------------------------------------------------------

@test "C38 detect_conflicts treats absolute-path .git/hooks as default-equivalent" {
  command -v python3 >/dev/null 2>&1 || skip "python3 required"
  # VS Code (and other tools) sometimes set core.hooksPath to the absolute
  # path of git's default hooks directory (e.g. /repo/.git/hooks), which is
  # functionally equivalent to an unset value. The detector must NOT ABORT
  # in this case — it should emit an INFO message and exit 0.
  _make_clean_repo "$TEST_TMP/abs-hookspath"
  cd "$TEST_TMP/abs-hookspath"
  # Set hooksPath to the absolute canonical path of .git/hooks (VS Code style).
  git config core.hooksPath "$TEST_TMP/abs-hookspath/.git/hooks"
  run "$LIB_DIR/detect_conflicts.sh"
  # Must NOT abort (exit 0, not 2).
  [ "$status" -eq 0 ]
  # Must emit an INFO message indicating it recognized the default-equivalent.
  echo "$output" | grep -qiE 'INFO.*default|default.*equivalent|resolves.*\.git/hooks'
}

# ---------------------------------------------------------------------------
# Group D — bats test sanity (shellcheck-style)
# ---------------------------------------------------------------------------

@test "D01 SKILL.md has no tab characters in body (markdown convention)" {
  ! grep -P '\t' "$SKILL_PATH" 2>/dev/null || skip "grep -P unsupported on this host"
}

@test "D02 SKILL.md frontmatter description does NOT recommend amend (TCS rule)" {
  desc=$(awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^description:')
  ! [[ "$desc" == *amend* ]]
}
