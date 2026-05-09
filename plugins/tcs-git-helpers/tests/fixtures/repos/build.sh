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
  # Rebase will conflict on file.txt and pause; .git/rebase-merge/ or rebase-apply/ remains.
  GIT_EDITOR=true git -C "$repo" rebase main >/dev/null 2>&1 || true
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

printf '%s\n' "$OUT_DIR"
