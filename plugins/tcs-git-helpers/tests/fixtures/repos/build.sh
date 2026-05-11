#!/bin/bash
# tests/fixtures/repos/build.sh
# Build synthetic git repos for tcs-git-helpers test fixtures (T1.9).
#
# Bash 3.2 compatible. No network. Idempotent (each scenario rebuilt fresh).
#
# Usage: build.sh [OUT_DIR]
#   OUT_DIR - destination root; default = $(mktemp -d ...)
#
# On success: prints OUT_DIR on stdout. Tests consume that path.
#
# Scenarios produced (per SDD/research/performance.md §7 worst-case matrix):
#   clean-unmerged/        - branch with commits ahead of origin/main, no PR
#   dirty/                 - branch with uncommitted changes in working tree
#   squash-merged/         - branch whose patches were squash-merged to main
#   merge-commit-merged/   - branch merged into main via --no-ff merge commit
#   closed-pr/             - clean+unmerged repo named for stub-PR=CLOSED scenario
#   detached-head/         - HEAD detached at HEAD~1
#   rebase-in-progress/    - rebase paused on conflict (.git/rebase-*/ exists)
#   large-50-branches/     - repo with 50 local branches (perf scenario §7.1)
#   long-1000-commits/     - branch with 1000 empty commits (perf scenario §7.7)
#
# All repos use deterministic identity + timestamps so SHAs are reproducible.

set -euo pipefail

OUT_DIR="${1:-}"
if [ -z "$OUT_DIR" ]; then
  OUT_DIR=$(mktemp -d "${TMPDIR:-/tmp}/tcs-git-helpers-fixtures.XXXXXX")
fi
mkdir -p "$OUT_DIR"

# --- Deterministic identity & dates ---------------------------------------
export GIT_AUTHOR_NAME="tcs-fixture"
export GIT_AUTHOR_EMAIL="fixture@tcs.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

# Avoid host-config leak (gpgsign, hooksPath, etc.)
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

# --- Helpers --------------------------------------------------------------

_init_repo() {
  # $1 = repo dir; creates a working repo with main branch.
  local dir="$1"
  rm -rf "$dir"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config commit.gpgsign false
  git -C "$dir" config tag.gpgsign false
  git -C "$dir" config user.name "$GIT_AUTHOR_NAME"
  git -C "$dir" config user.email "$GIT_AUTHOR_EMAIL"
}

_init_bare() {
  # $1 = bare repo dir; creates a bare origin.
  local dir="$1"
  rm -rf "$dir"
  mkdir -p "$dir"
  git -C "$dir" init -q --bare -b main
}

_commit() {
  # $1 = repo dir; $2 = filename; $3 = content; $4 = subject
  local dir="$1" file="$2" content="$3" subject="$4"
  printf '%s\n' "$content" > "$dir/$file"
  git -C "$dir" add "$file"
  git -C "$dir" commit -q -m "$subject"
}

# --- Scenario 1: clean-unmerged ------------------------------------------
build_clean_unmerged() {
  local repo="$OUT_DIR/clean-unmerged"
  local origin="$OUT_DIR/clean-unmerged.origin.git"

  _init_bare "$origin"
  _init_repo "$repo"
  _commit "$repo" main.txt "main-content" "feat: initial commit"
  git -C "$repo" remote add origin "$origin"
  git -C "$repo" push -q -u origin main

  git -C "$repo" checkout -q -b feat/clean-unmerged
  _commit "$repo" feature.txt "feature work" "feat: add feature"
  # Tree clean, branch ahead of origin/main, no PR (PR-state simulated by stub if needed).
}

# --- Scenario 2: dirty ----------------------------------------------------
build_dirty() {
  local repo="$OUT_DIR/dirty"
  local origin="$OUT_DIR/dirty.origin.git"

  _init_bare "$origin"
  _init_repo "$repo"
  _commit "$repo" main.txt "main-content" "feat: initial commit"
  git -C "$repo" remote add origin "$origin"
  git -C "$repo" push -q -u origin main

  git -C "$repo" checkout -q -b feat/dirty-tree
  _commit "$repo" tracked.txt "tracked v1" "feat: tracked file"
  # Leave uncommitted modification + untracked file in working tree.
  printf '%s\n' "tracked v2 (uncommitted)" > "$repo/tracked.txt"
  printf '%s\n' "untracked content" > "$repo/untracked.txt"
}

# --- Scenario 3: squash-merged -------------------------------------------
build_squash_merged() {
  local repo="$OUT_DIR/squash-merged"
  local origin="$OUT_DIR/squash-merged.origin.git"

  _init_bare "$origin"
  _init_repo "$repo"
  _commit "$repo" main.txt "main-content" "feat: initial commit"
  git -C "$repo" remote add origin "$origin"
  git -C "$repo" push -q -u origin main

  git -C "$repo" checkout -q -b feat/squashed
  # Single commit so the squash commit's patch-id matches the branch commit's
  # patch-id; `git cherry` then prints '-' (the canonical squash-merge signal).
  # Multi-commit squashes intentionally produce a different patch-id on main
  # and `git cherry` would return '+' lines — that limitation is documented
  # in references/squash-merge-trap.md and tracked separately.
  _commit "$repo" feature.txt "feature work" "feat: feature work"

  # Squash-merge: produces a single new commit on main with the same patch.
  git -C "$repo" checkout -q main
  git -C "$repo" merge --squash feat/squashed >/dev/null
  git -C "$repo" commit -q -m "feat: squash-merged feature"
  git -C "$repo" push -q origin main

  # Local feat/squashed tip is NOT ancestor of origin/main, but its patch IS applied.
  # `git cherry origin/main feat/squashed` -> all '-' lines.
  git -C "$repo" checkout -q feat/squashed
}

# --- Scenario 4: merge-commit-merged -------------------------------------
build_merge_commit_merged() {
  local repo="$OUT_DIR/merge-commit-merged"
  local origin="$OUT_DIR/merge-commit-merged.origin.git"

  _init_bare "$origin"
  _init_repo "$repo"
  _commit "$repo" main.txt "main-content" "feat: initial commit"
  git -C "$repo" remote add origin "$origin"
  git -C "$repo" push -q -u origin main

  git -C "$repo" checkout -q -b feat/merge-commit
  _commit "$repo" m1.txt "m1" "feat: m1"
  _commit "$repo" m2.txt "m2" "feat: m2"

  # Merge-commit (not squash) preserves branch SHAs in main's history.
  git -C "$repo" checkout -q main
  git -C "$repo" merge --no-ff -m "Merge branch 'feat/merge-commit'" feat/merge-commit >/dev/null
  git -C "$repo" push -q origin main

  # Local feat/merge-commit tip IS ancestor of origin/main -> SAFE to resume.
  git -C "$repo" checkout -q feat/merge-commit
}

# --- Scenario 5: closed-pr -----------------------------------------------
build_closed_pr() {
  # Repo state matches clean-unmerged; the "closed PR" is provided by gh stubs.
  local repo="$OUT_DIR/closed-pr"
  local origin="$OUT_DIR/closed-pr.origin.git"

  _init_bare "$origin"
  _init_repo "$repo"
  _commit "$repo" main.txt "main-content" "feat: initial commit"
  git -C "$repo" remote add origin "$origin"
  git -C "$repo" push -q -u origin main

  git -C "$repo" checkout -q -b feat/closed-pr-branch
  _commit "$repo" closed.txt "closed pr work" "feat: closed pr work"
  git -C "$repo" push -q -u origin feat/closed-pr-branch
}

# --- Scenario 6: detached-head -------------------------------------------
build_detached_head() {
  local repo="$OUT_DIR/detached-head"

  _init_repo "$repo"
  _commit "$repo" first.txt "first" "feat: first"
  _commit "$repo" second.txt "second" "feat: second"

  # Detach at HEAD~1 (the first commit).
  local first_sha
  first_sha=$(git -C "$repo" rev-parse HEAD~1)
  git -C "$repo" checkout -q --detach "$first_sha"
}

# --- Scenario 7: rebase-in-progress --------------------------------------
build_rebase_in_progress() {
  local repo="$OUT_DIR/rebase-in-progress"

  _init_repo "$repo"
  _commit "$repo" file.txt "base" "feat: base"

  git -C "$repo" checkout -q -b feat/rebase
  _commit "$repo" file.txt "feat-version" "feat: branch change"

  git -C "$repo" checkout -q main
  _commit "$repo" file.txt "main-version" "feat: main change"

  git -C "$repo" checkout -q feat/rebase
  # Non-interactive rebase pauses on conflict; .git/rebase-merge/ (or
  # rebase-apply/ on the legacy backend) remains. No editor involvement —
  # we don't pass -i, so GIT_EDITOR/GIT_SEQUENCE_EDITOR are not needed.
  git -C "$repo" rebase main >/dev/null 2>&1 || true
}

# --- Scenario 8: large-50-branches ---------------------------------------
build_large_50_branches() {
  local repo="$OUT_DIR/large-50-branches"

  _init_repo "$repo"
  _commit "$repo" main.txt "main" "feat: initial"

  local i
  for i in $(seq -w 1 50); do
    git -C "$repo" branch "feat/branch-${i}" main
  done
}

# --- Scenario 9: long-1000-commits ---------------------------------------
build_long_1000_commits() {
  local repo="$OUT_DIR/long-1000-commits"

  _init_repo "$repo"
  _commit "$repo" main.txt "main" "feat: initial"
  git -C "$repo" checkout -q -b feat/long

  # Empty commits keep this fast (~1.2s on M-series macOS in practice).
  local i
  for i in $(seq 1 1000); do
    git -C "$repo" commit -q --allow-empty -m "feat: commit ${i}"
  done
}

# --- Scenarios for skill_setup (T5.1) ------------------------------------

# clean-repo: bare git init + one commit. No .githooks, no remote.
build_clean_repo() {
  local repo="$OUT_DIR/clean-repo"
  _init_repo "$repo"
  _commit "$repo" README.md "clean repo" "feat: init"
}

# with-husky: .husky/ directory + package.json with "husky" key.
build_with_husky() {
  local repo="$OUT_DIR/with-husky"
  _init_repo "$repo"
  _commit "$repo" README.md "husky repo" "feat: init"
  mkdir -p "$repo/.husky/_"
  printf '#!/bin/sh\nnpm test\n' > "$repo/.husky/pre-commit"
  chmod +x "$repo/.husky/pre-commit"
  cat > "$repo/package.json" <<'EOF'
{
  "name": "with-husky",
  "version": "1.0.0",
  "scripts": {
    "prepare": "husky install"
  },
  "devDependencies": {
    "husky": "^9.0.0"
  }
}
EOF
  git -C "$repo" add . >/dev/null
  git -C "$repo" commit -q -m "chore: add husky"
}

# with-lefthook: lefthook.yml at root.
build_with_lefthook() {
  local repo="$OUT_DIR/with-lefthook"
  _init_repo "$repo"
  _commit "$repo" README.md "lefthook repo" "feat: init"
  cat > "$repo/lefthook.yml" <<'EOF'
pre-commit:
  commands:
    lint:
      run: npm run lint
EOF
  git -C "$repo" add lefthook.yml >/dev/null
  git -C "$repo" commit -q -m "chore: add lefthook"
}

# with-pre-commit: .pre-commit-config.yaml at root.
build_with_pre_commit() {
  local repo="$OUT_DIR/with-pre-commit"
  _init_repo "$repo"
  _commit "$repo" README.md "pre-commit repo" "feat: init"
  cat > "$repo/.pre-commit-config.yaml" <<'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
EOF
  git -C "$repo" add .pre-commit-config.yaml >/dev/null
  git -C "$repo" commit -q -m "chore: add pre-commit framework"
}

# with-simple-git-hooks: package.json with "simple-git-hooks" key.
build_with_simple_git_hooks() {
  local repo="$OUT_DIR/with-simple-git-hooks"
  _init_repo "$repo"
  _commit "$repo" README.md "sgh repo" "feat: init"
  cat > "$repo/package.json" <<'EOF'
{
  "name": "with-simple-git-hooks",
  "version": "1.0.0",
  "simple-git-hooks": {
    "pre-commit": "npm test"
  }
}
EOF
  git -C "$repo" add package.json >/dev/null
  git -C "$repo" commit -q -m "chore: add simple-git-hooks"
}

# with-existing-hooks: .githooks/* WITHOUT a tcs-git-helpers marker.
build_with_existing_hooks() {
  local repo="$OUT_DIR/with-existing-hooks"
  _init_repo "$repo"
  _commit "$repo" README.md "existing hooks" "feat: init"
  mkdir -p "$repo/.githooks"
  printf '#!/bin/sh\n# repo-local pre-commit (not tcs-git-helpers)\nexit 0\n' \
    > "$repo/.githooks/pre-commit"
  chmod +x "$repo/.githooks/pre-commit"
  git -C "$repo" add .githooks >/dev/null
  git -C "$repo" commit -q -m "chore: add custom .githooks"
}

# with-tcs-current: .githooks/* WITH marker matching the CURRENT plugin
# version (read from plugin.json at fixture-build time so the detector's
# OK path is exercised against the real WANT_VERSION, not a stale literal).
build_with_tcs_current() {
  local repo="$OUT_DIR/with-tcs-current"
  _init_repo "$repo"
  _commit "$repo" README.md "tcs current" "feat: init"
  mkdir -p "$repo/.githooks"
  local plugin_root manifest version
  plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  manifest="$plugin_root/.claude-plugin/plugin.json"
  if [ -f "$manifest" ]; then
    version="$(grep -E '"version"[[:space:]]*:' "$manifest" \
      | head -1 \
      | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  else
    version="0.0.0"
  fi
  printf '#!/bin/bash\n# tcs-git-helpers: v%s\nexit 0\n' "$version" \
    > "$repo/.githooks/pre-commit"
  chmod +x "$repo/.githooks/pre-commit"
  git -C "$repo" add .githooks >/dev/null
  git -C "$repo" commit -q -m "chore: install tcs-git-helpers v$version"
}

# with-tcs-older: .githooks/* WITH older v0.9.0 marker.
build_with_tcs_older() {
  local repo="$OUT_DIR/with-tcs-older"
  _init_repo "$repo"
  _commit "$repo" README.md "tcs older" "feat: init"
  mkdir -p "$repo/.githooks"
  printf '#!/bin/bash\n# tcs-git-helpers: v0.9.0\nexit 0\n' \
    > "$repo/.githooks/pre-commit"
  chmod +x "$repo/.githooks/pre-commit"
  git -C "$repo" add .githooks >/dev/null
  git -C "$repo" commit -q -m "chore: install tcs-git-helpers v0.9.0"
}

# with-non-sample-hooks: .git/hooks/ contains non-.sample files.
build_with_non_sample_hooks() {
  local repo="$OUT_DIR/with-non-sample-hooks"
  _init_repo "$repo"
  _commit "$repo" README.md "non-sample hooks" "feat: init"
  printf '#!/bin/sh\necho "legacy pre-commit"\nexit 0\n' \
    > "$repo/.git/hooks/pre-commit"
  chmod +x "$repo/.git/hooks/pre-commit"
}

# with-submodules: .gitmodules present.
build_with_submodules() {
  local repo="$OUT_DIR/with-submodules"
  local sub_origin="$OUT_DIR/with-submodules.sub.git"

  _init_bare "$sub_origin"
  # Seed the bare repo with one commit so add can succeed without network.
  # The seeder must NOT live under $OUT_DIR/ (fixtures_sanity.bats iterates
  # every `*/` and runs fsck). Use $TMPDIR instead, then drop it.
  local seeder
  seeder="$(mktemp -d "${TMPDIR:-/tmp}/tcs-sub-seed.XXXXXX")"
  _init_repo "$seeder"
  _commit "$seeder" sub.txt "sub content" "feat: sub init"
  git -C "$seeder" remote add origin "$sub_origin"
  git -C "$seeder" push -q -u origin main
  rm -rf "$seeder"

  _init_repo "$repo"
  _commit "$repo" README.md "with submodules" "feat: init"
  # Allow `file://` submodules (off by default since git 2.38) for tests.
  git -C "$repo" -c protocol.file.allow=always submodule add -q "$sub_origin" libs/sub
  git -C "$repo" commit -q -m "chore: add submodule"
}

# --- Driver ---------------------------------------------------------------

build_clean_unmerged
build_dirty
build_squash_merged
build_merge_commit_merged
build_closed_pr
build_detached_head
build_rebase_in_progress
build_large_50_branches
build_long_1000_commits

# T5.1 setup-skill scenarios
build_clean_repo
build_with_husky
build_with_lefthook
build_with_pre_commit
build_with_simple_git_hooks
build_with_existing_hooks
build_with_tcs_current
build_with_tcs_older
build_with_non_sample_hooks
build_with_submodules

printf '%s\n' "$OUT_DIR"
