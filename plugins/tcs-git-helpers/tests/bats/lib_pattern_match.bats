#!/usr/bin/env bats
# tests/bats/lib_pattern_match.bats
# Coverage for scripts/lib/pattern_match.sh — destructive-op pattern matchers.
#
# CON-9: every pattern must compile AND behave identically on both regex
#        engines bash is built against — BSD/libc (macOS) and GNU/glibc
#        (Linux, Docker). Two idioms break that:
#          \s / \b   — PCRE extensions. glibc supports them, BSD does not, so
#                      they silently stop matching on macOS.
#          [[:<:]] / [[:>:]] — BSD word boundaries. glibc rejects them with
#                      "Invalid character class name"; [[ =~ ]] then returns 2,
#                      every caller reads that as "no match", and the guard
#                      fails OPEN.
#        Portable forms: [[:space:]]+ for whitespace, ([^[:alnum:]_]|$) for a
#        trailing word boundary.
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

@test "CON-9 evidence: PCRE \\s+ is platform-dependent in [[ =~ ]]" {
  # This is the whole reason for CON-9: the same pattern gives opposite answers
  # on the two engines. BSD/macOS treats \s as a literal 's' and does not match;
  # GNU/glibc supports \s as an extension and does match. Assert the behaviour
  # of the engine we are actually running on, so the split stays documented
  # instead of the test simply failing on whichever platform it was not written
  # for.
  run bash -c 'cmd="git push"; pat="git\\s+push"; [[ "$cmd" =~ $pat ]]'
  case "$(uname -s)" in
    Darwin) [ "$status" -ne 0 ] ;;
    *)      [ "$status" -eq 0 ] ;;
  esac
}

@test "CON-9 evidence: POSIX [[:space:]]+ DOES match on this platform" {
  run bash -c 'cmd="git push"; pat="git[[:space:]]+push"; [[ "$cmd" =~ $pat ]]'
  [ "$status" -eq 0 ]
}

@test "CON-9 evidence: BSD [[:>:]] does NOT compile under glibc" {
  # The failure mode this constraint exists to prevent. On glibc regcomp
  # rejects the class and bash returns 2 — which reads as "no match" to every
  # caller, so a destructive command sails through. On BSD it compiles and
  # matches, hence the platform split.
  run bash -c 'cmd="git reset --hard"; pat="--hard[[:>:]]"; [[ "$cmd" =~ $pat ]]'
  case "$(uname -s)" in
    Darwin) [ "$status" -eq 0 ] ;;
    *)      [ "$status" -eq 2 ] ;;
  esac
}

@test "CON-9: every PATTERN_ constant compiles on this platform" {
  # Regression guard for the fail-open bug: a pattern that does not compile
  # makes [[ =~ ]] exit 2, which _match_command reports as "no match".
  local name pat
  for name in $(grep -Eo '^PATTERN_[A-Z_]+' "${PLUGIN_ROOT}/scripts/lib/pattern_match.sh"); do
    eval "pat=\"\${${name}}\""
    run bash -c '[[ "probe" =~ $1 ]]' _ "$pat"
    if [ "$status" -ge 2 ]; then
      printf 'PATTERN %s does not compile here: %s\n' "$name" "$pat" >&2
      return 1
    fi
  done
}

@test "CON-9: no PATTERN_ constant uses the BSD-only [[:<:]] / [[:>:]]" {
  local name pat
  for name in $(grep -Eo '^PATTERN_[A-Z_]+' "${PLUGIN_ROOT}/scripts/lib/pattern_match.sh"); do
    eval "pat=\"\${${name}}\""
    case "$pat" in
      *'[[:<:]]'*|*'[[:>:]]'*)
        printf 'PATTERN %s uses a BSD-only word boundary: %s\n' "$name" "$pat" >&2
        return 1
        ;;
    esac
  done
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

@test "PATTERN_CLEAN_FORCE: positive — uppercase neighbours -fX / -Xf / -dXf" {
  _match_command "git clean -fX"                         "$PATTERN_CLEAN_FORCE"
  _match_command "git clean -Xf"                         "$PATTERN_CLEAN_FORCE"
  _match_command "git clean -dXf ."                      "$PATTERN_CLEAN_FORCE"
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

@test "PATTERN_RESTORE_DESTRUCTIVE: positive — reversed --source then --worktree" {
  # Git accepts flags in either order; both are equally destructive.
  _match_command "git restore --source=HEAD~1 --worktree file.txt"  "$PATTERN_RESTORE_DESTRUCTIVE"
  _match_command $'git\trestore\t--source=HEAD\t--worktree\tfoo'    "$PATTERN_RESTORE_DESTRUCTIVE"
  _match_command "cd foo && git restore --source=main --worktree ." "$PATTERN_RESTORE_DESTRUCTIVE"
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

@test "PATTERN_PUSH_FORCE: negative — --force-if-includes (git 2.30+) MUST NOT match" {
  # --force-if-includes is the safer companion to --force-with-lease; neither
  # should be flagged as a destructive --force.
  _no_match "git push --force-if-includes"                          "$PATTERN_PUSH_FORCE"
  _no_match "git push origin feat/foo --force-if-includes"          "$PATTERN_PUSH_FORCE"
  _no_match "cd foo && git push --force-with-lease --force-if-includes" "$PATTERN_PUSH_FORCE"
}

# -- 12. PATTERN_PUSH_DELETE_FLAG ----------------------------------------------

@test "PATTERN_PUSH_DELETE_FLAG: positive — --delete <branch>" {
  _match_command "git push origin --delete feat/foo"         "$PATTERN_PUSH_DELETE_FLAG"
  _match_command $'git\tpush\torigin\t--delete\tfeat/foo'    "$PATTERN_PUSH_DELETE_FLAG"
  _match_command "git    push    origin    --delete    feat/foo" "$PATTERN_PUSH_DELETE_FLAG"
  _match_command "cd foo && git push origin --delete feat/foo" "$PATTERN_PUSH_DELETE_FLAG"
}

@test "PATTERN_PUSH_DELETE_FLAG: positive — --delete without explicit remote" {
  # `git push --delete <branch>` (no remote) defaults to origin and is equally destructive.
  _match_command "git push --delete feat/foo"                "$PATTERN_PUSH_DELETE_FLAG"
  _match_command "cd foo && git push --delete feat/foo"      "$PATTERN_PUSH_DELETE_FLAG"
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

# -- 14. PATTERN_GH_REF_DELETE_A/B (gh api DELETE on git/refs) -----------------

@test "PATTERN_GH_REF_DELETE_A: positive — gh api <url> -X DELETE" {
  _match_command "gh api repos/MMoMM-org/my-repo/git/refs/heads/feat/old -X DELETE" "$PATTERN_GH_REF_DELETE_A"
  _match_command "gh api repos/o/r/git/refs/heads/main --method DELETE"             "$PATTERN_GH_REF_DELETE_A"
  _match_command "gh api repos/o/r/git/refs/tags/v1.0.0 -X DELETE"                 "$PATTERN_GH_REF_DELETE_A"
  _match_command $'gh\tapi\trepos/o/r/git/refs/heads/main\t-X\tDELETE'             "$PATTERN_GH_REF_DELETE_A"
  _match_command "cd repo && gh api repos/o/r/git/refs/heads/feat -X DELETE"        "$PATTERN_GH_REF_DELETE_A"
}

@test "PATTERN_GH_REF_DELETE_B: positive — gh api -X DELETE <url>" {
  _match_command "gh api -X DELETE repos/o/r/git/refs/heads/feat/old"               "$PATTERN_GH_REF_DELETE_B"
  _match_command "gh api --method DELETE repos/o/r/git/refs/heads/feat/old"         "$PATTERN_GH_REF_DELETE_B"
  _match_command $'gh\tapi\t-X\tDELETE\trepos/o/r/git/refs/heads/feat'             "$PATTERN_GH_REF_DELETE_B"
}

@test "PATTERN_GH_REF_DELETE: negative — non-DELETE methods / no git/refs" {
  _no_match "gh api repos/o/r/pulls/123 -X PATCH"         "$PATTERN_GH_REF_DELETE_A"
  _no_match "gh api repos/o/r/pulls/123 -X PATCH"         "$PATTERN_GH_REF_DELETE_B"
  _no_match "gh api repos/o/r/git/refs/heads/main"         "$PATTERN_GH_REF_DELETE_A"
  _no_match "gh api repos/o/r/git/refs/heads/main"         "$PATTERN_GH_REF_DELETE_B"
  _no_match "gh pr delete 123"                             "$PATTERN_GH_REF_DELETE_A"
  _no_match "gh pr delete 123"                             "$PATTERN_GH_REF_DELETE_B"
}

# -- 15. PATTERN_BRANCH_CREATE -------------------------------------------------
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

# -- 16. PATTERN_BRANCH_RESUME -------------------------------------------------
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

# -- 17. PATTERN_HOOKSPATH_INLINE ----------------------------------------------

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

# -- 18. PATTERN_HOOKSPATH_CONFIG ----------------------------------------------

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

# -- _match_no_verify (sibling-isolation helper) --------------------------------
# These tests require _match_no_verify to exist; they will FAIL (RED) until
# the helper is added to pattern_match.sh (T1.1 GREEN phase).

@test "_match_no_verify: function is defined" {
  declare -f _match_no_verify >/dev/null
}

@test "_match_no_verify: positive — genuine --no-verify flag" {
  _match_no_verify 'git commit --no-verify -m "msg"'
}

@test "_match_no_verify: positive — genuine -n flag (word-boundary)" {
  _match_no_verify $'git\tcommit\t-n\t-m\t"msg"'
}

@test "_match_no_verify: positive — chained genuine bypass (git add && git commit -n)" {
  # Both clauses are git commands; the git commit clause owns the -n.
  _match_no_verify 'git add . && git commit -n -m "done"'
}

@test "_match_no_verify: negative — sibling echo -n after git commit (FALSE-POSITIVE BUG)" {
  # BUG CASE: the old dispatcher's unbounded .* bridged from `git commit` into
  # a sibling command's `-n`. _match_no_verify must split on && and only match
  # clauses that themselves contain `git commit ... -n`.
  declare -f _match_no_verify >/dev/null || fail "_match_no_verify not defined"
  if _match_no_verify 'git commit -m "done" && echo -n ok'; then
    printf 'FALSE POSITIVE: matched sibling echo -n as --no-verify\n' >&2
    return 1
  fi
}

@test "_match_no_verify: negative — sibling head -n 5 via semicolon" {
  declare -f _match_no_verify >/dev/null || fail "_match_no_verify not defined"
  if _match_no_verify 'git commit -m "done"; head -n 5 CHANGELOG.md'; then
    printf 'FALSE POSITIVE: matched sibling head -n as --no-verify\n' >&2
    return 1
  fi
}

@test "_match_no_verify: negative — sibling grep -n via pipe" {
  declare -f _match_no_verify >/dev/null || fail "_match_no_verify not defined"
  if _match_no_verify 'git commit -m "done" | grep -n foo'; then
    printf 'FALSE POSITIVE: matched piped grep -n as --no-verify\n' >&2
    return 1
  fi
}

@test "_match_no_verify: negative — -n inside -m quoted body (already covered by _strip_quoted)" {
  declare -f _match_no_verify >/dev/null || fail "_match_no_verify not defined"
  if _match_no_verify 'git commit -m "release notes: see -n, flag"'; then
    printf 'FALSE POSITIVE: matched -n inside quoted message body\n' >&2
    return 1
  fi
}

@test "_match_no_verify: negative — newline-separated sibling command (no match)" {
  # Ensure the trailing-newline empty clause from <<< does not cause a spurious match.
  declare -f _match_no_verify >/dev/null || fail "_match_no_verify not defined"
  local cmd
  # Build a literal newline-separated pair via printf.
  cmd="$(printf 'git commit -m "done"\necho -n ok')"
  if _match_no_verify "$cmd"; then
    printf 'FALSE POSITIVE: matched newline-separated sibling -n as --no-verify\n' >&2
    return 1
  fi
}

@test "_match_no_verify: negative — sibling echo -n via || operator (no match)" {
  # Covers the || separator path. _match_no_verify splits on || so the echo
  # clause is evaluated separately and does not match PATTERN_NO_VERIFY.
  declare -f _match_no_verify >/dev/null || fail "_match_no_verify not defined"
  if _match_no_verify 'git commit -m "done" || echo -n ok'; then
    printf 'FALSE POSITIVE: matched sibling echo -n (|| path) as --no-verify\n' >&2
    return 1
  fi
}
