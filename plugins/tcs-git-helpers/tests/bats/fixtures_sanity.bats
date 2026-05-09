#!/usr/bin/env bats
# T1.9 — Test Fixtures + Synthetic Repos sanity check
#
# Verifies:
#   - tests/fixtures/repos/build.sh produces all 9 scenarios into a tempdir
#   - each generated repo passes `git fsck` (errors only, dangling allowed
#     for the legitimately rebase-paused fixture)
#   - synthetic repos have the expected branch / state shapes
#   - destructive_corpus.txt + bypass_corpus.txt are well-formed and end
#     with a trailing newline
#   - configs/{good,bad,malicious}.config exist and end with a newline
#   - gh_stubs/gh is executable and emits valid JSON for default scenarios
#   - gh_stubs response wire-format matches real `gh`:
#       pr list --json … -> ARRAY     (jq -e 'type=="array"')
#       pr view --json … -> OBJECT    (jq -e 'type=="object"')

FIXTURE_DIR="${BATS_TEST_DIRNAME}/../fixtures"
BUILD_SH="${FIXTURE_DIR}/repos/build.sh"
GH_STUB="${FIXTURE_DIR}/gh_stubs/gh"

setup_file() {
  command -v jq      >/dev/null || skip "jq required"
  command -v git     >/dev/null || skip "git required"
  command -v shasum  >/dev/null || skip "shasum required"

  # Build all scenarios once per file run for speed.
  export TCS_FIXTURES_OUT
  TCS_FIXTURES_OUT=$(mktemp -d "${TMPDIR:-/tmp}/tcs-fixtures-bats.XXXXXX")
  bash "$BUILD_SH" "$TCS_FIXTURES_OUT" >/dev/null
}

teardown_file() {
  if [ -n "${TCS_FIXTURES_OUT:-}" ] && [ -d "${TCS_FIXTURES_OUT}" ]; then
    rm -rf "${TCS_FIXTURES_OUT}"
  fi
}

# ---------------------------------------------------------------------------
# build.sh shape & properties
# ---------------------------------------------------------------------------

@test "build.sh exists and is executable" {
  [ -x "$BUILD_SH" ]
}

@test "build.sh has bash shebang" {
  head -n 1 "$BUILD_SH" | grep -qE '^#!.*bash'
}

@test "build.sh produces all 9 scenario directories" {
  for s in clean-unmerged dirty squash-merged merge-commit-merged closed-pr \
           detached-head rebase-in-progress large-50-branches long-1000-commits; do
    [ -d "$TCS_FIXTURES_OUT/$s" ] || {
      echo "missing scenario directory: $s" >&2
      return 1
    }
  done
}

# ---------------------------------------------------------------------------
# Synthetic repos pass `git fsck`
# ---------------------------------------------------------------------------

@test "every working repo passes git fsck (no errors)" {
  for r in "$TCS_FIXTURES_OUT"/*/; do
    case "$r" in
      *.origin.git/) continue ;;  # bare origins
    esac
    # Allow dangling objects (rebase-in-progress legitimately has them);
    # fail only on actual errors.
    run git -C "$r" fsck --no-dangling
    [ "$status" -eq 0 ] || {
      echo "fsck failed in $r (status=$status)" >&2
      echo "$output" >&2
      return 1
    }
  done
}

# ---------------------------------------------------------------------------
# Per-scenario state assertions
# ---------------------------------------------------------------------------

@test "clean-unmerged: branch ahead of origin/main, working tree clean" {
  local repo="$TCS_FIXTURES_OUT/clean-unmerged"
  run git -C "$repo" symbolic-ref --short HEAD
  [ "$output" = "feat/clean-unmerged" ]

  run git -C "$repo" status --porcelain
  [ -z "$output" ]   # clean

  run git -C "$repo" rev-list --count origin/main..HEAD
  [ "$output" -ge 1 ]
}

@test "dirty: working tree has uncommitted modifications and untracked files" {
  local repo="$TCS_FIXTURES_OUT/dirty"
  run git -C "$repo" status --porcelain
  [ -n "$output" ]
  [[ "$output" == *" M tracked.txt"*  || "$output" == *"M  tracked.txt"* ]]
  [[ "$output" == *"?? untracked.txt"* ]]
}

@test "squash-merged: branch tip is NOT ancestor of origin/main, all cherry lines are '-'" {
  local repo="$TCS_FIXTURES_OUT/squash-merged"
  # Branch tip should NOT be an ancestor of origin/main (squash made a new commit).
  run git -C "$repo" merge-base --is-ancestor feat/squashed origin/main
  [ "$status" -ne 0 ]

  # `git cherry origin/main feat/squashed` should print only '-' lines.
  run git -C "$repo" cherry origin/main feat/squashed
  [ "$status" -eq 0 ]
  [ -n "$output" ]
  while IFS= read -r line; do
    [[ "$line" == "- "* ]] || {
      echo "cherry line not a '-' line: $line" >&2
      return 1
    }
  done <<< "$output"
}

@test "merge-commit-merged: branch tip IS ancestor of origin/main (safe to resume)" {
  local repo="$TCS_FIXTURES_OUT/merge-commit-merged"
  run git -C "$repo" merge-base --is-ancestor feat/merge-commit origin/main
  [ "$status" -eq 0 ]
}

@test "closed-pr: branch and origin both have feat/closed-pr-branch" {
  local repo="$TCS_FIXTURES_OUT/closed-pr"
  run git -C "$repo" symbolic-ref --short HEAD
  [ "$output" = "feat/closed-pr-branch" ]

  run git -C "$repo" rev-parse --verify refs/remotes/origin/feat/closed-pr-branch
  [ "$status" -eq 0 ]
}

@test "detached-head: HEAD is detached, no symbolic-ref" {
  local repo="$TCS_FIXTURES_OUT/detached-head"
  run git -C "$repo" symbolic-ref --short -q HEAD
  [ "$status" -ne 0 ]   # detached -> non-zero
  run git -C "$repo" rev-parse --verify HEAD
  [ "$status" -eq 0 ]
}

@test "rebase-in-progress: .git/rebase-merge or rebase-apply directory exists" {
  local repo="$TCS_FIXTURES_OUT/rebase-in-progress"
  if [ ! -d "$repo/.git/rebase-merge" ] && [ ! -d "$repo/.git/rebase-apply" ]; then
    echo "no rebase state directory in $repo/.git" >&2
    return 1
  fi
}

@test "large-50-branches: at least 50 feat/branch-* branches exist" {
  local repo="$TCS_FIXTURES_OUT/large-50-branches"
  run git -C "$repo" for-each-ref --format='%(refname:short)' 'refs/heads/feat/branch-*'
  local count
  count=$(printf '%s\n' "$output" | grep -c 'feat/branch-' || true)
  [ "$count" -eq 50 ]
}

@test "long-1000-commits: feat/long branch has at least 1000 commits" {
  local repo="$TCS_FIXTURES_OUT/long-1000-commits"
  run git -C "$repo" rev-list --count feat/long
  [ "$status" -eq 0 ]
  [ "$output" -ge 1000 ]
}

# ---------------------------------------------------------------------------
# Corpus files: trailing newline + parseable rows
# ---------------------------------------------------------------------------

_assert_trailing_newline() {
  local file="$1"
  [ -s "$file" ] || {
    echo "file empty: $file" >&2
    return 1
  }
  # Last byte must be 0x0a (\n).
  local last
  last=$(tail -c 1 "$file" | od -An -tx1 | tr -d ' \n')
  [ "$last" = "0a" ] || {
    echo "file does not end with newline: $file (last-byte=$last)" >&2
    return 1
  }
}

@test "destructive_corpus.txt ends with trailing newline" {
  _assert_trailing_newline "$FIXTURE_DIR/commands/destructive_corpus.txt"
}

@test "bypass_corpus.txt ends with trailing newline" {
  _assert_trailing_newline "$FIXTURE_DIR/commands/bypass_corpus.txt"
}

@test "destructive_corpus.txt rows are parseable as decision\\trule\\tcommand" {
  local file="$FIXTURE_DIR/commands/destructive_corpus.txt"
  local n=0
  while IFS= read -r line; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    # 2 tabs minimum -> 3 fields
    local tab_count
    tab_count=$(printf '%s' "$line" | tr -cd '\t' | wc -c | tr -d ' ')
    [ "$tab_count" -ge 2 ] || {
      echo "row has fewer than 2 tabs: $line" >&2
      return 1
    }
    local decision
    decision=$(printf '%s' "$line" | cut -f1)
    case "$decision" in
      deny|allow) ;;
      *) echo "row decision not deny|allow: $line" >&2; return 1 ;;
    esac
    n=$((n+1))
  done < "$file"
  # Sanity: corpus has substantial coverage
  [ "$n" -ge 60 ] || {
    echo "destructive_corpus.txt has only $n rows; expected >= 60" >&2
    return 1
  }
}

@test "destructive_corpus.txt covers all 11 M7 rule names + NEGATIVE" {
  local file="$FIXTURE_DIR/commands/destructive_corpus.txt"
  for rule in RESET_HARD CLEAN_FORCE DESTRUCTIVE_CHECKOUT DESTRUCTIVE_RESTORE \
              FORCE_BRANCH_DELETE STASH_DESTROY REFLOG_EXPIRE NO_VERIFY \
              FORCE_PUSH REMOTE_BRANCH_DELETE HOOKSPATH_OVERRIDE NEGATIVE; do
    grep -qE "^[a-z]+\s$rule\s" "$file" || grep -qP "^[a-z]+\t$rule\t" "$file" 2>/dev/null || {
      # Fallback: literal tab match via awk
      awk -F'\t' -v r="$rule" '$2==r{found=1} END{exit !found}' "$file" || {
        echo "rule missing from corpus: $rule" >&2
        return 1
      }
    }
  done
}

@test "bypass_corpus.txt covers DOCUMENTED_LIMITATION (alias/function escape hatch)" {
  awk -F'\t' '$2=="DOCUMENTED_LIMITATION"{n++} END{exit (n>=3)?0:1}' \
    "$FIXTURE_DIR/commands/bypass_corpus.txt"
}

# ---------------------------------------------------------------------------
# Config fixtures: existence + trailing newline
# ---------------------------------------------------------------------------

@test "configs/good.config exists and ends with newline" {
  _assert_trailing_newline "$FIXTURE_DIR/configs/good.config"
}

@test "configs/bad.config exists and ends with newline" {
  _assert_trailing_newline "$FIXTURE_DIR/configs/bad.config"
}

@test "configs/malicious.config exists and ends with newline" {
  _assert_trailing_newline "$FIXTURE_DIR/configs/malicious.config"
}

@test "good.config: every non-comment line is KEY=VALUE" {
  while IFS= read -r line; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    [[ "$line" == *=* ]] || {
      echo "good.config line is not KEY=VALUE: $line" >&2
      return 1
    }
  done < "$FIXTURE_DIR/configs/good.config"
}

@test "good.config: every assigned key is on the documented allowlist" {
  local allowlist=" TCS_PROTECTED_BRANCHES TCS_HOOK_EXCLUDE_PATHS_FILE TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK TCS_ENABLE_PR_PUSH_CHECK TCS_ALLOW_AMEND_ON_PROTECTED "
  while IFS= read -r line; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    local key="${line%%=*}"
    case "$allowlist" in
      *" $key "*) ;;
      *) echo "good.config has unknown key: $key" >&2; return 1 ;;
    esac
  done < "$FIXTURE_DIR/configs/good.config"
}

@test "malicious.config: contains injection vectors (cmdsub, backtick, newline, traversal)" {
  local f="$FIXTURE_DIR/configs/malicious.config"
  grep -q '\$('  "$f"     # command substitution
  grep -q '`'    "$f"     # backticks
  grep -q '\\n'  "$f"     # newline-escape injection
  grep -q '\.\./' "$f"    # path traversal
}

# ---------------------------------------------------------------------------
# gh_stubs: executable, valid JSON, real-gh wire format
# ---------------------------------------------------------------------------

@test "gh_stubs/gh is executable with bash shebang" {
  [ -x "$GH_STUB" ]
  head -n 1 "$GH_STUB" | grep -qE '^#!.*bash'
}

@test "gh_stubs README documents scenarios" {
  [ -f "$FIXTURE_DIR/gh_stubs/README.md" ]
  grep -q 'closed-pr'        "$FIXTURE_DIR/gh_stubs/README.md"
  grep -q 'merged-pr'        "$FIXTURE_DIR/gh_stubs/README.md"
  grep -q 'no-auth'          "$FIXTURE_DIR/gh_stubs/README.md"
  grep -q 'rate-limited'     "$FIXTURE_DIR/gh_stubs/README.md"
}

@test "gh_stubs response files are valid JSON" {
  while IFS= read -r f; do
    jq -e . "$f" >/dev/null || {
      echo "invalid JSON: $f" >&2
      return 1
    }
  done < <(find "$FIXTURE_DIR/gh_stubs/responses" -name '*.json' -type f)
}

@test "gh_stubs pr-list returns ARRAY envelope (mirrors real gh)" {
  for s in default closed-pr merged-pr open-pr no-pr squash-merged-batch; do
    f="$FIXTURE_DIR/gh_stubs/responses/$s/pr-list.json"
    [ -f "$f" ] || continue
    jq -e 'type == "array"' "$f" >/dev/null || {
      echo "$s/pr-list.json is not a JSON array" >&2
      return 1
    }
  done
}

@test "gh_stubs pr-view returns OBJECT envelope (mirrors real gh)" {
  for f in "$FIXTURE_DIR"/gh_stubs/responses/*/pr-view.json; do
    [ -f "$f" ] || continue
    jq -e 'type == "object"' "$f" >/dev/null || {
      echo "$f is not a JSON object" >&2
      return 1
    }
    # mergeCommit field must exist (object or null)
    jq -e 'has("mergeCommit")' "$f" >/dev/null || {
      echo "$f missing mergeCommit field" >&2
      return 1
    }
  done
}

@test "gh_stubs/gh: --version returns stub identifier" {
  run "$GH_STUB" --version
  [ "$status" -eq 0 ]
  [[ "$output" == *"stub-tcs-git-helpers"* ]]
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=default pr list returns []" {
  run env GH_STUB_SCENARIO=default "$GH_STUB" pr list --head feat/foo --state all --json state,number --limit 1
  [ "$status" -eq 0 ]
  [ "$output" = "[]" ]
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=closed-pr pr list returns CLOSED PR" {
  run env GH_STUB_SCENARIO=closed-pr "$GH_STUB" pr list --head feat/closed-pr-branch --state all --json state,number --limit 1
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | jq -e '.[0].state == "CLOSED"' >/dev/null
  printf '%s\n' "$output" | jq -e '.[0].number == 42' >/dev/null
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=merged-pr pr view returns mergeCommit object" {
  run env GH_STUB_SCENARIO=merged-pr "$GH_STUB" pr view 43 --json mergeCommit
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | jq -e '.mergeCommit.oid' >/dev/null
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=no-auth exits 4 with auth error" {
  run env GH_STUB_SCENARIO=no-auth "$GH_STUB" pr list --head feat/foo
  [ "$status" -eq 4 ]
  [[ "$output" == *"not authenticated"* ]]
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=rate-limited exits 4 with rate-limit error" {
  run env GH_STUB_SCENARIO=rate-limited "$GH_STUB" pr list --head feat/foo
  [ "$status" -eq 4 ]
  [[ "$output" == *"rate limit"* ]]
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=network-fail exits 1" {
  run env GH_STUB_SCENARIO=network-fail "$GH_STUB" pr list --head feat/foo
  [ "$status" -eq 1 ]
  [[ "$output" == *"no such host"* ]]
}

@test "gh_stubs/gh: GH_STUB_SCENARIO=timeout exits 124 (matches /usr/bin/timeout)" {
  run env GH_STUB_SCENARIO=timeout "$GH_STUB" pr list --head feat/foo
  [ "$status" -eq 124 ]
  [[ "$output" == *"timeout"* ]]
}
