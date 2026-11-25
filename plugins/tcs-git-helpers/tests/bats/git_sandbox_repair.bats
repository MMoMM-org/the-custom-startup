#!/usr/bin/env bats
#
# tests/bats/git_sandbox_repair.bats
#
# scripts/git-sandbox-repair.sh (#303): repairs the upstream a sandboxed
# `git push -u` failed to set, and only reports an index/HEAD mismatch left by
# an interrupted `git checkout -b`.

bats_require_minimum_version 1.5.0

load 'lib/helpers'

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  REPAIR="$PLUGIN_ROOT/scripts/git-sandbox-repair.sh"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com
  export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com

  REMOTE="$BATS_TEST_TMPDIR/remote.git"
  REPO="$BATS_TEST_TMPDIR/repo"
  git init -q --bare -b main "$REMOTE"
  git init -q -b main "$REPO"
  git -C "$REPO" commit -q --allow-empty -m init
  git -C "$REPO" remote add origin "$REMOTE"
  git -C "$REPO" push -q -u origin main
  git -C "$REPO" checkout -q -b feat
  printf 'x\n' > "$REPO/f.txt"
  git -C "$REPO" add f.txt
  git -C "$REPO" commit -q -m feat
  cd "$REPO"
}

_pushed_without_upstream() {
  git -C "$REPO" push -q origin feat
}

@test "R1 missing upstream with origin/<branch> present is set" {
  _pushed_without_upstream
  run "$REPAIR"
  [ "$status" -eq 0 ]
  _has "$output" "FIXED upstream of feat set to origin/feat"
  [ "$(git -C "$REPO" rev-parse --abbrev-ref 'feat@{upstream}')" = "origin/feat" ]
}

@test "R2 --dry-run names the fix and writes nothing" {
  _pushed_without_upstream
  run "$REPAIR" --dry-run
  [ "$status" -eq 0 ]
  _has "$output" "WOULD-FIX set upstream of feat to origin/feat"
  run git -C "$REPO" config --get branch.feat.remote
  [ "$status" -eq 1 ]
}

@test "R3 a branch that already tracks its upstream is OK" {
  git -C "$REPO" push -q -u origin feat
  run "$REPAIR"
  [ "$status" -eq 0 ]
  _has "$output" "OK feat tracks origin/feat"
}

@test "R4 an unpushed branch is information, not a repair" {
  run "$REPAIR"
  [ "$status" -eq 0 ]
  _has "$output" "INFO feat has no upstream and origin/feat does not exist"
  run git -C "$REPO" config --get branch.feat.remote
  [ "$status" -eq 1 ]
}

@test "R5 index on another branch's tree is reported, HEAD left alone, exit 2" {
  git -C "$REPO" checkout -q main
  # What an interrupted `checkout -b` leaves: the index holds feat's tree,
  # HEAD still points at main.
  git -C "$REPO" read-tree feat
  run "$REPAIR"
  [ "$status" -eq 2 ]
  _has "$output" "REPORT index matches branch 'feat' but HEAD is on 'main'"
  _has "$output" "git symbolic-ref HEAD refs/heads/feat"
  _lacks "$output" "origin/feat"
  [ "$(git -C "$REPO" symbolic-ref --short HEAD)" = "main" ]
}

@test "R6 staged work that matches no branch is not reported" {
  printf 'y\n' > "$REPO/g.txt"
  git -C "$REPO" add g.txt
  run "$REPAIR"
  [ "$status" -eq 0 ]
  _lacks "$output" "REPORT"
}

@test "R7 detached HEAD skips the upstream check" {
  git -C "$REPO" checkout -q --detach
  run "$REPAIR"
  [ "$status" -eq 0 ]
  _has "$output" "INFO detached HEAD"
}

@test "R8 outside a git repository it exits 1" {
  cd "$BATS_TEST_TMPDIR"
  run -1 env GIT_CEILING_DIRECTORIES="$BATS_TEST_TMPDIR" "$REPAIR"
}

@test "R9 an unknown argument exits 1" {
  run -1 "$REPAIR" --force
}

@test "R10 script is shellcheck-clean" {
  command -v shellcheck >/dev/null 2>&1 || skip "shellcheck not installed"
  run shellcheck "$REPAIR"
  [ "$status" -eq 0 ]
}
