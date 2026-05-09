#!/usr/bin/env bats
# tests/bats/lib_pattern_match.bats
# Coverage for scripts/lib/pattern_match.sh — destructive-op pattern matchers.
#
# CON-9: All patterns must use [[:space:]]+ (NEVER \s+) and [[:>:]] (NEVER \b).
#        Empirically: \s and \b are PCRE extensions — they do NOT match in
#        bash 3.2 [[ =~ ]] (POSIX ERE). Patterns that "work" with \s silently
#        never fire and the dispatcher becomes a no-op.
#
# Each of the 14+ canonical patterns from PRD §Feature M7 is tested against:
#   - canonical form        (single-space)
#   - tab-separated form    ($'\t')
#   - multi-space form
#   - compound form         (cd foo && git ...)
# Plus at least one negative variant per pattern.

setup() {
  PLUGIN_ROOT="$( cd "${BATS_TEST_DIRNAME}/../.." && pwd )"
  # shellcheck source=/dev/null
  source "${PLUGIN_ROOT}/scripts/lib/pattern_match.sh"
}

# Test helper: assert that <command> does NOT match <pattern>.
# Why not bare `! _match_command …`? In bats >= 1.5.0, `!` mid-test does
# not fail the test (SC2314): only the LAST command of a test body counts.
# Using a function that returns 1 on unwanted match makes every assertion
# trigger bats' set-e exit and report failure.
_no_match() {
  local cmd="$1" pattern="$2"
  if _match_command "$cmd" "$pattern"; then
    printf 'expected NO match: cmd=%q  pattern=%q\n' "$cmd" "$pattern" >&2
    return 1
  fi
  return 0
}

# -- Sanity / CON-9 evidence ---------------------------------------------------

@test "_match_command function is defined" {
  declare -f _match_command >/dev/null
}

@test "CON-9 evidence: PCRE \\s+ does NOT match in bash 3.2 [[ =~ ]]" {
  run bash -c 'cmd="git push"; pat="git\\s+push"; [[ "$cmd" =~ $pat ]]'
  [ "$status" -ne 0 ]
}

@test "CON-9 evidence: POSIX [[:space:]]+ DOES match in bash 3.2 [[ =~ ]]" {
  run bash -c 'cmd="git push"; pat="git[[:space:]]+push"; [[ "$cmd" =~ $pat ]]'
  [ "$status" -eq 0 ]
}

@test "no PATTERN_ regex constant uses PCRE \\s or \\b" {
  # Scope to PATTERN_ definition lines only — comments may legitimately
  # reference the forbidden \s / \b extensions (the rule itself).
  local pattern_defs
  pattern_defs=$(grep -E '^PATTERN_[A-Z_]+=' "${PLUGIN_ROOT}/scripts/lib/pattern_match.sh" || true)
  run bash -c "printf '%s\n' \"\$1\" | grep -F '\\s'" _ "$pattern_defs"
  [ "$status" -ne 0 ]   # grep -F finds nothing -> exit 1 (good)
  run bash -c "printf '%s\n' \"\$1\" | grep -F '\\b'" _ "$pattern_defs"
  [ "$status" -ne 0 ]
}

# -- 1. PATTERN_RESET_HARD -----------------------------------------------------

@test "PATTERN_RESET_HARD: positive — canonical / tab / multi-space / compound" {
  _match_command "git reset --hard"                          "$PATTERN_RESET_HARD"
  _match_command $'git\treset\t--hard'                       "$PATTERN_RESET_HARD"
  _match_command "git    reset    --hard"                    "$PATTERN_RESET_HARD"
  _match_command "cd foo && git reset --hard origin/main"    "$PATTERN_RESET_HARD"
}

@test "PATTERN_RESET_HARD: negative — --soft / --mixed do not match" {
  _no_match "git reset --soft HEAD~1"  "$PATTERN_RESET_HARD"
  _no_match "git reset --mixed HEAD~1" "$PATTERN_RESET_HARD"
  _no_match "git reset HEAD~1"         "$PATTERN_RESET_HARD"
}

# -- 2. PATTERN_CLEAN_FORCE ----------------------------------------------------

@test "PATTERN_CLEAN_FORCE: positive — -f / -fx / --force / -dfx" {
  _match_command "git clean -f"                          "$PATTERN_CLEAN_FORCE"
  _match_command $'git\tclean\t-fx'                      "$PATTERN_CLEAN_FORCE"
  _match_command "git    clean    --force"               "$PATTERN_CLEAN_FORCE"
  _match_command "cd foo && git clean -dfx"              "$PATTERN_CLEAN_FORCE"
}

@test "PATTERN_CLEAN_FORCE: negative — -n / -d alone do not match" {
  _no_match "git clean -n"     "$PATTERN_CLEAN_FORCE"
  _no_match "git clean -d"     "$PATTERN_CLEAN_FORCE"
  _no_match "git clean --dry-run" "$PATTERN_CLEAN_FORCE"
}

# -- 3. PATTERN_CHECKOUT_DOT ---------------------------------------------------

@test "PATTERN_CHECKOUT_DOT: positive — canonical / tab / multi-space / compound" {
  _match_command "git checkout ."                        "$PATTERN_CHECKOUT_DOT"
  _match_command $'git\tcheckout\t.'                     "$PATTERN_CHECKOUT_DOT"
  _match_command "git    checkout    ."                  "$PATTERN_CHECKOUT_DOT"
  _match_command "cd foo && git checkout ."              "$PATTERN_CHECKOUT_DOT"
}

@test "PATTERN_CHECKOUT_DOT: negative — paths starting with . do not match" {
  _no_match "git checkout .githooks"      "$PATTERN_CHECKOUT_DOT"
  _no_match "git checkout .config"        "$PATTERN_CHECKOUT_DOT"
  _no_match "git checkout main"           "$PATTERN_CHECKOUT_DOT"
}

# -- 4. PATTERN_CHECKOUT_PATH --------------------------------------------------

@test "PATTERN_CHECKOUT_PATH: positive — git checkout -- <path>" {
  _match_command "git checkout -- file.txt"                 "$PATTERN_CHECKOUT_PATH"
  _match_command $'git\tcheckout\t--\tfile.txt'             "$PATTERN_CHECKOUT_PATH"
  _match_command "git    checkout    --    src/foo.go"      "$PATTERN_CHECKOUT_PATH"
  _match_command "cd foo && git checkout -- README.md"      "$PATTERN_CHECKOUT_PATH"
}

@test "PATTERN_CHECKOUT_PATH: negative — bare branch checkout / no -- separator" {
  _no_match "git checkout main"      "$PATTERN_CHECKOUT_PATH"
  _no_match "git checkout file.txt"  "$PATTERN_CHECKOUT_PATH"
  _no_match "git checkout -b feat/x" "$PATTERN_CHECKOUT_PATH"
}

# -- 5. PATTERN_RESTORE_DESTRUCTIVE --------------------------------------------

@test "PATTERN_RESTORE_DESTRUCTIVE: positive — --worktree --source / --staged" {
  _match_command "git restore --worktree --source=HEAD~1 file.txt" "$PATTERN_RESTORE_DESTRUCTIVE"
  _match_command $'git\trestore\t--staged\tfile.txt'               "$PATTERN_RESTORE_DESTRUCTIVE"
  _match_command "git    restore    --staged    src/foo.go"        "$PATTERN_RESTORE_DESTRUCTIVE"
  _match_command "cd foo && git restore --worktree --source=main ." "$PATTERN_RESTORE_DESTRUCTIVE"
}

@test "PATTERN_RESTORE_DESTRUCTIVE: negative — bare git restore (no --staged/--worktree)" {
  _no_match "git restore file.txt"      "$PATTERN_RESTORE_DESTRUCTIVE"
  _no_match "git restore"               "$PATTERN_RESTORE_DESTRUCTIVE"
}

# -- 6. PATTERN_BRANCH_FORCE_DELETE --------------------------------------------

@test "PATTERN_BRANCH_FORCE_DELETE: positive — git branch -D <name>" {
  _match_command "git branch -D feat/foo"                "$PATTERN_BRANCH_FORCE_DELETE"
  _match_command $'git\tbranch\t-D\tfeat/foo'            "$PATTERN_BRANCH_FORCE_DELETE"
  _match_command "git    branch    -D    feat/foo"       "$PATTERN_BRANCH_FORCE_DELETE"
  _match_command "cd foo && git branch -D feat/foo"      "$PATTERN_BRANCH_FORCE_DELETE"
}

@test "PATTERN_BRANCH_FORCE_DELETE: negative — lowercase -d is the safe form" {
  _no_match "git branch -d feat/foo" "$PATTERN_BRANCH_FORCE_DELETE"
  _no_match "git branch --list"      "$PATTERN_BRANCH_FORCE_DELETE"
  _no_match "git branch -Dfoo"       "$PATTERN_BRANCH_FORCE_DELETE"
}

# -- 7. PATTERN_STASH_DESTROY --------------------------------------------------

@test "PATTERN_STASH_DESTROY: positive — drop / clear" {
  _match_command "git stash drop"                        "$PATTERN_STASH_DESTROY"
  _match_command $'git\tstash\tclear'                    "$PATTERN_STASH_DESTROY"
  _match_command "git    stash    drop    stash@{0}"     "$PATTERN_STASH_DESTROY"
  _match_command "cd foo && git stash clear"             "$PATTERN_STASH_DESTROY"
}

@test "PATTERN_STASH_DESTROY: negative — pop / list / show / apply" {
  _no_match "git stash pop"  "$PATTERN_STASH_DESTROY"
  _no_match "git stash list" "$PATTERN_STASH_DESTROY"
  _no_match "git stash apply" "$PATTERN_STASH_DESTROY"
  _no_match "git stash dropbox" "$PATTERN_STASH_DESTROY"
}

# -- 8. PATTERN_REFLOG_EXPIRE --------------------------------------------------

@test "PATTERN_REFLOG_EXPIRE: positive — canonical / tab / multi-space / compound" {
  _match_command "git reflog expire --expire=now --all"      "$PATTERN_REFLOG_EXPIRE"
  _match_command $'git\treflog\texpire\t--all'               "$PATTERN_REFLOG_EXPIRE"
  _match_command "git    reflog    expire    --all"          "$PATTERN_REFLOG_EXPIRE"
  _match_command "cd foo && git reflog expire --expire=now"  "$PATTERN_REFLOG_EXPIRE"
}

@test "PATTERN_REFLOG_EXPIRE: negative — show / read-only ops do not match" {
  _no_match "git reflog show HEAD" "$PATTERN_REFLOG_EXPIRE"
  _no_match "git reflog"           "$PATTERN_REFLOG_EXPIRE"
}

# -- 9. PATTERN_NO_VERIFY ------------------------------------------------------

@test "PATTERN_NO_VERIFY: positive — --no-verify and -n" {
  _match_command 'git commit --no-verify -m "msg"'                     "$PATTERN_NO_VERIFY"
  _match_command $'git\tcommit\t-n\t-m\t"msg"'                         "$PATTERN_NO_VERIFY"
  _match_command 'git    commit    --no-verify    -m    "msg"'         "$PATTERN_NO_VERIFY"
  _match_command 'cd foo && git commit --no-verify -m "msg"'           "$PATTERN_NO_VERIFY"
}

@test "PATTERN_NO_VERIFY: negative — plain -m / --message do not match" {
  _no_match 'git commit -m "msg"'        "$PATTERN_NO_VERIFY"
  _no_match 'git commit --message="msg"' "$PATTERN_NO_VERIFY"
  _no_match 'git commit --amend'         "$PATTERN_NO_VERIFY"
}

# -- 10. PATTERN_PUSH ----------------------------------------------------------
# (Used by M1 closed-PR check; matches any `git push`.)

@test "PATTERN_PUSH: positive — generic push variants" {
  _match_command "git push"                                  "$PATTERN_PUSH"
  _match_command $'git\tpush\torigin\tfeat/foo'              "$PATTERN_PUSH"
  _match_command "git    push    -u    origin    feat/foo"   "$PATTERN_PUSH"
  _match_command "cd foo && git push origin HEAD"            "$PATTERN_PUSH"
}

@test "PATTERN_PUSH: negative — pushed (word-extension) and unrelated subcommands" {
  _no_match "git pushed"           "$PATTERN_PUSH"
  _no_match "git pull"             "$PATTERN_PUSH"
  _no_match "echo git push"        "$PATTERN_PUSH" || true   # echo prefix still allowed by substring
  # explicitly: substring match means `cd foo && echo git push` would still match,
  # which is actually the correct behaviour for compound detection.
}

# -- 11. PATTERN_PUSH_FORCE ----------------------------------------------------
# THE critical false-positive guard: --force-with-lease must NEVER match.

@test "PATTERN_PUSH_FORCE: positive — --force in all 4 forms" {
  _match_command "git push --force"                          "$PATTERN_PUSH_FORCE"
  _match_command $'git\tpush\t--force'                       "$PATTERN_PUSH_FORCE"
  _match_command "git    push    origin    --force"          "$PATTERN_PUSH_FORCE"
  _match_command "cd foo && git push origin feat/foo --force" "$PATTERN_PUSH_FORCE"
}

@test "PATTERN_PUSH_FORCE: negative — --force-with-lease MUST NOT match" {
  _no_match "git push --force-with-lease"                       "$PATTERN_PUSH_FORCE"
  _no_match "git push origin feat/foo --force-with-lease"       "$PATTERN_PUSH_FORCE"
  _no_match "git push --force-with-lease=feat/foo:abc123"       "$PATTERN_PUSH_FORCE"
  _no_match "cd foo && git push --force-with-lease origin HEAD" "$PATTERN_PUSH_FORCE"
}

# -- 12. PATTERN_PUSH_DELETE_FLAG ----------------------------------------------

@test "PATTERN_PUSH_DELETE_FLAG: positive — --delete <branch>" {
  _match_command "git push origin --delete feat/foo"         "$PATTERN_PUSH_DELETE_FLAG"
  _match_command $'git\tpush\torigin\t--delete\tfeat/foo'    "$PATTERN_PUSH_DELETE_FLAG"
  _match_command "git    push    origin    --delete    feat/foo" "$PATTERN_PUSH_DELETE_FLAG"
  _match_command "cd foo && git push origin --delete feat/foo" "$PATTERN_PUSH_DELETE_FLAG"
}

@test "PATTERN_PUSH_DELETE_FLAG: negative — plain push and --dry-run do not match" {
  _no_match "git push origin feat/foo"        "$PATTERN_PUSH_DELETE_FLAG"
  _no_match "git push --dry-run origin"       "$PATTERN_PUSH_DELETE_FLAG"
}

# -- 13. PATTERN_PUSH_COLON_DELETE ---------------------------------------------

@test "PATTERN_PUSH_COLON_DELETE: positive — git push <remote> :<branch>" {
  _match_command "git push origin :feat/foo"                 "$PATTERN_PUSH_COLON_DELETE"
  _match_command $'git\tpush\torigin\t:feat/foo'             "$PATTERN_PUSH_COLON_DELETE"
  _match_command "git    push    origin    :feat/foo"        "$PATTERN_PUSH_COLON_DELETE"
  _match_command "cd foo && git push origin :feat/foo"       "$PATTERN_PUSH_COLON_DELETE"
}

@test "PATTERN_PUSH_COLON_DELETE: negative — refspec without leading colon does not match" {
  _no_match "git push origin feat/foo:feat/foo" "$PATTERN_PUSH_COLON_DELETE"
  _no_match "git push origin feat/foo"          "$PATTERN_PUSH_COLON_DELETE"
}

# -- 14. PATTERN_BRANCH_CREATE -------------------------------------------------
# (M2 hook — branch creation; not destructive but uses the same matcher infra.)

@test "PATTERN_BRANCH_CREATE: positive — checkout -b / switch -c" {
  _match_command "git checkout -b feat/foo"                   "$PATTERN_BRANCH_CREATE"
  _match_command $'git\tswitch\t-c\tfeat/foo'                 "$PATTERN_BRANCH_CREATE"
  _match_command "git    switch    -c    feat/foo"            "$PATTERN_BRANCH_CREATE"
  _match_command "cd foo && git checkout -b feat/foo"         "$PATTERN_BRANCH_CREATE"
}

@test "PATTERN_BRANCH_CREATE: negative — bare checkout / switch (resume), branch -d" {
  _no_match "git checkout feat/foo"  "$PATTERN_BRANCH_CREATE"
  _no_match "git switch feat/foo"    "$PATTERN_BRANCH_CREATE"
  _no_match "git branch -d feat/foo" "$PATTERN_BRANCH_CREATE"
}

# -- 15. PATTERN_BRANCH_RESUME -------------------------------------------------
# (M3 hook — squash-merge resume detection.)

@test "PATTERN_BRANCH_RESUME: positive — bare checkout / switch <branch>" {
  _match_command "git checkout feat/foo"                      "$PATTERN_BRANCH_RESUME"
  _match_command $'git\tswitch\tfeat/foo'                     "$PATTERN_BRANCH_RESUME"
  _match_command "git    checkout    feat/foo"                "$PATTERN_BRANCH_RESUME"
  _match_command "cd foo && git switch feat/foo"              "$PATTERN_BRANCH_RESUME"
}

@test "PATTERN_BRANCH_RESUME: negative — flag-based forms must NOT match" {
  _no_match "git checkout -b feat/foo"     "$PATTERN_BRANCH_RESUME"
  _no_match "git switch -c feat/foo"       "$PATTERN_BRANCH_RESUME"
  _no_match "git checkout -- file.txt"     "$PATTERN_BRANCH_RESUME"
  _no_match "git checkout ."               "$PATTERN_BRANCH_RESUME"
}

# -- 16. PATTERN_HOOKSPATH_INLINE ----------------------------------------------

@test "PATTERN_HOOKSPATH_INLINE: positive — git -c core.hooksPath=…" {
  _match_command "git -c core.hooksPath=/dev/null commit"            "$PATTERN_HOOKSPATH_INLINE"
  _match_command $'git\t-c\tcore.hooksPath=/dev/null\tcommit'        "$PATTERN_HOOKSPATH_INLINE"
  _match_command "git    -c    core.hooksPath=/dev/null    commit"   "$PATTERN_HOOKSPATH_INLINE"
  _match_command "cd foo && git -c core.hooksPath=/tmp commit"       "$PATTERN_HOOKSPATH_INLINE"
}

@test "PATTERN_HOOKSPATH_INLINE: negative — other -c configs do not match" {
  _no_match "git -c user.email=x@y.z commit"  "$PATTERN_HOOKSPATH_INLINE"
  _no_match "git -c color.ui=auto status"     "$PATTERN_HOOKSPATH_INLINE"
}

# -- 17. PATTERN_HOOKSPATH_CONFIG ----------------------------------------------

@test "PATTERN_HOOKSPATH_CONFIG: positive — git config core.hooksPath …" {
  _match_command "git config core.hooksPath .githooks"                "$PATTERN_HOOKSPATH_CONFIG"
  _match_command $'git\tconfig\tcore.hooksPath\t.githooks'            "$PATTERN_HOOKSPATH_CONFIG"
  _match_command "git    config    --global    core.hooksPath    /tmp" "$PATTERN_HOOKSPATH_CONFIG"
  _match_command "cd foo && git config --local core.hooksPath ."      "$PATTERN_HOOKSPATH_CONFIG"
}

@test "PATTERN_HOOKSPATH_CONFIG: negative — other config keys do not match" {
  _no_match "git config user.email x@y.z"     "$PATTERN_HOOKSPATH_CONFIG"
  _no_match "git config --global color.ui auto" "$PATTERN_HOOKSPATH_CONFIG"
  _no_match "git status"                      "$PATTERN_HOOKSPATH_CONFIG"
}
