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
    head -n 5 "$f" | grep -q 'set -euo pipefail' \
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

# Helper: build the fixture repos into the per-test tempdir.
_build_fixtures() {
  bash "$FIXTURE_BUILD" "$TEST_TMP/fixtures" >/dev/null
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
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -eq 0 ]
  # Output should NOT contain ABORT or any conflict tag.
  ! echo "$output" | grep -qiE 'ABORT|husky|lefthook|pre-commit|simple-git-hooks'
}

@test "C12 detect_conflicts on with-husky aborts with husky reference" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-husky"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'husky'
  echo "$output" | grep -q 'migrating-from-husky'
}

@test "C13 detect_conflicts on with-lefthook aborts" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-lefthook"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'lefthook'
}

@test "C14 detect_conflicts on with-pre-commit aborts" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-pre-commit"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'pre-commit'
}

@test "C15 detect_conflicts on with-simple-git-hooks aborts" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-simple-git-hooks"
  run "$LIB_DIR/detect_conflicts.sh"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi 'simple-git-hooks'
}

@test "C16 detect_conflicts on with-existing-hooks emits CONFLICT (no marker)" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-existing-hooks"
  run "$LIB_DIR/detect_conflicts.sh"
  # Existing-hooks-no-marker is a CONFLICT (status non-zero) so the skill can
  # branch into per-file diff mode. The output names the condition.
  [ "$status" -ne 0 ]
  echo "$output" | grep -qiE 'no marker|existing-hooks|conflict|per-file'
}

@test "C17 detect_conflicts on with-tcs-current emits up-to-date" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-tcs-current"
  # Current matching version: detect_conflicts considers this informational, not
  # an abort. The skill body branches on the up-to-date marker independently.
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qiE 'up to date|matching|already installed'
}

@test "C18 detect_conflicts on with-tcs-older emits older-version notice" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-tcs-older"
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qiE 'older|outdated|update|v0\.'
}

@test "C19 detect_conflicts on with-non-sample-hooks emits warn" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-non-sample-hooks"
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qiE 'warn|non-sample|.git/hooks'
}

@test "C20 detect_conflicts on with-submodules lists submodules" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/with-submodules"
  run "$LIB_DIR/detect_conflicts.sh"
  echo "$output" | grep -qi 'submodule'
}

# --- install_files.sh on a clean repo ---

@test "C21 install_files on clean repo writes .githooks/* with markers" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
  run "$LIB_DIR/install_files.sh"
  [ "$status" -eq 0 ]
  [ -f .githooks/pre-commit ]
  [ -f .githooks/pre-push ]
  [ -f .githooks/commit-msg ]
  [ -f .githooks/post-merge ]
  head -3 .githooks/pre-commit | grep -q 'tcs-git-helpers: v'
}

@test "C22 install_files sets core.hooksPath=.githooks" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
  "$LIB_DIR/install_files.sh"
  [ "$(git config core.hooksPath)" = ".githooks" ]
}

@test "C23 install_files writes .config.example and exclude-paths.example" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
  "$LIB_DIR/install_files.sh"
  [ -f .githooks/.config.example ]
  [ -f .githooks/exclude-paths.example ]
}

@test "C24 install_files makes hook files executable" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
  "$LIB_DIR/install_files.sh"
  [ -x .githooks/pre-commit ]
  [ -x .githooks/pre-push ]
  [ -x .githooks/commit-msg ]
  [ -x .githooks/post-merge ]
}

@test "C25 install_files does NOT auto-commit (M10 AC5)" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
  before_log=$(git log --oneline | wc -l)
  "$LIB_DIR/install_files.sh"
  after_log=$(git log --oneline | wc -l)
  [ "$before_log" = "$after_log" ]
  # And new files should be unstaged / untracked or modified, not committed.
  [ -n "$(git status --porcelain)" ]
}

# --- subshell sentinel scope (ADR-11) ---

@test "C26 install_files exports TCS_GIT_HELPERS_SETUP_ACTIVE only inside subshell" {
  _build_fixtures
  cd "$TEST_TMP/fixtures/clean-repo"
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
  "$LIB_DIR/lock.sh" acquire
  # Try to acquire again from a fresh subshell with very short timeout.
  run env TCS_LOCK_TIMEOUT=1 "$LIB_DIR/lock.sh" acquire
  [ "$status" -ne 0 ]
  "$LIB_DIR/lock.sh" release
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

# --- with_branch_protection stub (T5.8 placeholder) ---

@test "C31 with_branch_protection.sh runs as a stub and signals T5.8 ownership" {
  _make_clean_repo "$TEST_TMP/bprepo"
  cd "$TEST_TMP/bprepo"
  run "$LIB_DIR/with_branch_protection.sh"
  # Stub: exits 0 with informational message naming T5.8 (or similar marker).
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE 'T5\.8|branch.protection|stub|not yet implemented'
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
