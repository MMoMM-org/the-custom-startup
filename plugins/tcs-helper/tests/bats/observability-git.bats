#!/usr/bin/env bats
# shellcheck disable=SC2016,SC1003 # commands and payloads under test are literal text
#
# tests/bats/observability-git.bats
#
# spec 021 (observability v2), Phase 1, T1.3 -- the git invocation parser in
# plugins/tcs-helper/scripts/observability/git_ops.sh:
#
#   _git_ops_command <payload>   decodes tool_input.command from a hook payload
#   _git_ops_parse <command>     one line per non-read-only git invocation:
#                                subcommand TAB action TAB flags TAB overrides
#                                TAB override_first
#
# Contract: SDD "Implementation Examples" (decoder, traced parse, read-only
# predicate, ACTIONS), "Complex Logic" (executor rule, command position, global
# options), ADR-3 (short flag = first letter), ADR-9 (names only, closed
# read-only list), CON-13 (names, never values); PRD F3 Business Rules 2-4, 6.
#
# Every expectation is written out literally in the test (an independent
# oracle), never derived from the parser. Records are built with `rec`, which
# joins five fields with TABs.
#
# bash 3.2 compatible; no process substitution (bats `run` forbids it).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  BUNDLE_LIB="$REPO_ROOT/plugins/tcs-helper/scripts/observability/git_ops.sh"
  # shellcheck source=/dev/null
  source "$BUNDLE_LIB"
  NL=$'\n'
  TAB=$'\t'
}

# rec <subcommand> <action> <flags> <overrides> <override_first>
rec() {
  printf '%s\t%s\t%s\t%s\t%s' "$1" "$2" "$3" "$4" "$5"
}

# expect_parse <command> <expected output>  (expected "" = no record)
expect_parse() {
  run _git_ops_parse "$1"
  if [ "$status" -ne 0 ]; then
    printf 'command:  %s\nstatus:   %s\n' "$1" "$status"
    return 1
  fi
  if [ "$output" != "$2" ]; then
    printf 'command:  [%s]\nexpected: [%s]\nactual:   [%s]\n' "$1" "$2" "$output"
    return 1
  fi
}

# expect_decode <payload> <expected decoded command>
expect_decode() {
  run _git_ops_command "$1"
  if [ "$status" -ne 0 ]; then
    printf 'payload: %s\nstatus:  %s\n' "$1" "$status"
    return 1
  fi
  if [ "$output" != "$2" ]; then
    printf 'payload:  [%s]\nexpected: [%s]\nactual:   [%s]\n' "$1" "$2" "$output"
    return 1
  fi
}

# --- decoder ----------------------------------------------------------------

@test "decoder: an escaped quote decodes to a quote" {
  expect_decode '{"tool_input":{"command":"git commit -m \"x\""}}' 'git commit -m "x"'
}

@test "decoder: an escaped backslash decodes to one backslash" {
  expect_decode '{"tool_input":{"command":"echo a\\b"}}' 'echo a\b'
}

@test "decoder: an escaped backslash before the closing quote ends the string" {
  expect_decode '{"tool_input":{"command":"echo a\\","description":"git reset"}}' 'echo a\'
}

@test "decoder: backslash-n decodes to a newline" {
  expect_decode '{"tool_input":{"command":"git status\ngit push"}}' "git status${NL}git push"
}

@test "decoder: backslash-t decodes to a tab" {
  expect_decode '{"tool_input":{"command":"git\tpush"}}' "git${TAB}push"
}

@test "decoder: slash and CR escapes decode; a u-escape stays the literal six bytes" {
  expect_decode '{"tool_input":{"command":"a\/b\rc\u0041"}}' "a/b"$'\r'"c\\u0041"
}

@test "decoder: stops at the first unescaped quote" {
  expect_decode '{"tool_input":{"command":"git push","description":"git reset --hard"}}' 'git push'
}

@test "decoder: a missing command key prints nothing" {
  expect_decode '{"tool_name":"Bash","tool_input":{"description":"x"}}' ''
}

@test "decoder: an escaped command key inside another string is not the key" {
  expect_decode '{"tool_input":{"description":"say \"command\":\"git reset\""}}' ''
}

@test "decoder: an unterminated string prints nothing" {
  expect_decode '{"tool_input":{"command":"git reset --hard' ''
}

@test "decoder: an unterminated string ending in a backslash prints nothing" {
  expect_decode '{"tool_input":{"command":"git reset\' ''
}

# --- the traced example (SDD Runtime View) ----------------------------------

@test "traced example yields exactly the two SDD records" {
  local cmd expected
  cmd='cd repo && CLAUDE_ALLOW_RESET_HARD=1 git -C sub reset --hard origin/main; git status; git commit -m "drop git reset" -qa'
  expected="$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_RESET_HARD)${NL}$(rec commit '' '-m -q' '' CLAUDE_ALLOW_RESET_HARD)"
  expect_parse "$cmd" "$expected"
}

@test "traced example through the decoder yields the same two records" {
  local payload decoded expected
  payload='{"session_id":"s","tool_name":"Bash","tool_input":{"command":"cd repo && CLAUDE_ALLOW_RESET_HARD=1 git -C sub reset --hard origin/main; git status; git commit -m \"drop git reset\" -qa","description":"d"}}'
  decoded="$(_git_ops_command "$payload")"
  expected="$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_RESET_HARD)${NL}$(rec commit '' '-m -q' '' CLAUDE_ALLOW_RESET_HARD)"
  expect_parse "$decoded" "$expected"
}

# --- read-only predicate (ADR-9) --------------------------------------------

@test "read-only: every always-read-only subcommand records nothing, with any flags" {
  local sub failed=""
  for sub in status log diff show rev-parse rev-list ls-files ls-tree ls-remote \
    cat-file blame describe shortlog grep for-each-ref show-ref name-rev \
    merge-base help version var count-objects check-ignore check-attr \
    whatchanged cherry verify-commit verify-tag fsck archive; do
    run _git_ops_parse "git $sub -x --long=value positional"
    if [ "$status" -ne 0 ] || [ -n "$output" ]; then
      failed="$failed $sub"
    fi
  done
  [ -z "$failed" ] || { echo "recorded although read-only:$failed"; return 1; }
}

@test "read-only: git status alone records nothing" {
  expect_parse 'git status' ''
}

@test "read-only: bare git, git --version, git --help record nothing" {
  expect_parse 'git' '' || return 1
  expect_parse 'git --version' '' || return 1
  expect_parse 'git --help' '' || return 1
  expect_parse 'git help reset' ''
}

@test "branch: listing forms record nothing" {
  expect_parse 'git branch' '' || return 1
  expect_parse 'git branch -a -v' '' || return 1
  expect_parse 'git branch -vv --list' '' || return 1
  expect_parse 'git branch -r --merged --no-color' '' || return 1
  expect_parse "git branch --sort=-committerdate --format='%(refname:short)'" '' || return 1
  expect_parse 'git branch --show-current' ''
}

@test "branch: -D x is recorded with -D" {
  expect_parse 'git branch -D x' "$(rec branch '' '-D' '' '')"
}

@test "branch: a new branch name is recorded" {
  expect_parse 'git branch newname' "$(rec branch '' '' '' '')"
}

@test "branch: a quoted new branch name is recorded" {
  expect_parse 'git branch "newname"' "$(rec branch '' '' '' '')"
}

@test "branch: a non-listing letter in a bundle is recorded" {
  expect_parse 'git branch -ad' "$(rec branch '' '-a' '' '')"
}

@test "branch: --contains with a separate value is recorded (accepted, SDD)" {
  expect_parse 'git branch --contains abc' "$(rec branch '' '--contains' '' '')"
}

@test "tag: listing forms record nothing" {
  expect_parse 'git tag' '' || return 1
  expect_parse "git tag -l 'v*'" '' || return 1
  expect_parse 'git tag --list v1' ''
}

@test "tag: tag v1 is recorded" {
  expect_parse 'git tag v1' "$(rec tag '' '' '' '')"
}

@test "tag: tag -d v1 is recorded with -d" {
  expect_parse 'git tag -d v1' "$(rec tag '' '-d' '' '')"
}

@test "stash: list and show record nothing" {
  expect_parse 'git stash list' '' || return 1
  expect_parse 'git stash show -p stash@{0}' ''
}

@test "stash: pop is recorded with action pop" {
  expect_parse 'git stash pop' "$(rec stash pop '' '' '')"
}

@test "stash: drop is recorded with action drop" {
  expect_parse 'git stash drop stash@{1}' "$(rec stash drop '' '' '')"
}

@test "stash: push is recorded with action push and its flags" {
  expect_parse 'git stash push -m "wip"' "$(rec stash push '-m' '' '')"
}

@test "stash: bare stash is recorded without action" {
  expect_parse 'git stash' "$(rec stash '' '' '' '')"
}

@test "config: read forms record nothing" {
  expect_parse 'git config --get user.name' '' || return 1
  expect_parse 'git config --global --get user.name' '' || return 1
  expect_parse 'git config --get-regexp alias' '' || return 1
  expect_parse 'git config -l' '' || return 1
  expect_parse 'git config --list' '' || return 1
  expect_parse 'git config get user.name' '' || return 1
  expect_parse 'git config list' ''
}

@test "config: config user.name x is recorded" {
  expect_parse 'git config user.name x' "$(rec config '' '' '' '')"
}

@test "config: config --global user.name x is recorded with --global" {
  expect_parse 'git config --global user.name "A B"' "$(rec config '' '--global' '' '')"
}

@test "remote: read forms record nothing" {
  expect_parse 'git remote' '' || return 1
  expect_parse 'git remote -v' '' || return 1
  expect_parse 'git remote show origin' '' || return 1
  expect_parse 'git remote get-url origin' ''
}

@test "remote: set-url is recorded with action set-url" {
  expect_parse 'git remote set-url origin git@h:o/r.git' "$(rec remote set-url '' '' '')"
}

@test "remote: add is recorded with action add" {
  expect_parse 'git remote add up https://h/o/r' "$(rec remote add '' '' '')"
}

@test "worktree: list records nothing" {
  expect_parse 'git worktree list --porcelain' ''
}

@test "worktree: remove is recorded with action remove and its flags" {
  expect_parse 'git worktree remove --force ../wt' "$(rec worktree remove '--force' '' '')"
}

@test "reflog: bare and show record nothing" {
  expect_parse 'git reflog' '' || return 1
  expect_parse 'git reflog show HEAD' ''
}

@test "reflog: expire is recorded with action expire" {
  expect_parse 'git reflog expire --expire=now --all' "$(rec reflog expire '--expire --all' '' '')"
}

@test "notes: list and show record nothing; add is recorded" {
  expect_parse 'git notes list' '' || return 1
  expect_parse 'git notes show HEAD' '' || return 1
  expect_parse 'git notes add -m x' "$(rec notes add '-m' '' '')"
}

@test "submodule: bare and status record nothing; update is recorded" {
  expect_parse 'git submodule' '' || return 1
  expect_parse 'git submodule status' '' || return 1
  expect_parse 'git submodule update --init' "$(rec submodule update '--init' '' '')"
}

@test "actions: bisect, sparse-checkout and lfs sub-verbs are recorded" {
  expect_parse 'git bisect start' "$(rec bisect start '' '' '')" || return 1
  expect_parse 'git sparse-checkout set src' "$(rec sparse-checkout set '' '' '')" || return 1
  expect_parse 'git lfs push origin main' "$(rec lfs push '' '' '')"
}

@test "actions: a positional outside the ACTIONS list gives no action" {
  expect_parse 'git stash frobnicate' "$(rec stash '' '' '' '')" || return 1
  expect_parse 'git worktree banana' "$(rec worktree '' '' '' '')" || return 1
  expect_parse 'git remote origin' "$(rec remote '' '' '' '')"
}

@test "actions: a subcommand without an ACTIONS list gives no action" {
  expect_parse 'git push origin pop' "$(rec push '' '' '' '')"
}

@test "unknown subcommand is recorded as ? (fail closed, closed list)" {
  expect_parse 'git frobnicate --x' "$(rec '?' '' '--x' '' '')"
}

@test "an alias is recorded as ?" {
  expect_parse 'git co main' "$(rec '?' '' '' '' '')"
}

# --- words: a value always stays in one word --------------------------------

@test "words: a backslash-escaped space keeps -C's value one word" {
  expect_parse 'git -C my\ secretdir push' "$(rec push '' '' '' '')"
}

@test "words: a backslash-escaped space keeps -c's value one word" {
  expect_parse 'git -c user.name=john\ doe commit' "$(rec commit '' '' '' '')"
}

@test "words: a backslash-escaped space keeps a positional one word" {
  expect_parse 'git commit --author a\ --hunter2' "$(rec commit '' '--author' '' '')"
}

@test "words: a backslash-escaped space keeps an assignment one word" {
  expect_parse 'A=x\ y git push' "$(rec push '' '' '' '')"
}

@test "words: backslash-newline is a line continuation" {
  expect_parse "git push \\${NL}  --force" "$(rec push '' '--force' '' '')"
}

@test "words: a parameter expansion is one word" {
  expect_parse 'git -C ${D:-a b c} push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'git -C ${D:-"a } b"} push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'git -C ${D:-${E:-a b}} push' "$(rec push '' '' '' '')"
}

@test "words: a process substitution is code and one word" {
  expect_parse 'diff <(git push) x' "$(rec push '' '' '' '')" || return 1
  expect_parse 'git apply <(cat p) --index' "$(rec apply '' '--index' '' '')"
}

@test "executor: an assignment with a quoted value before git yields ?" {
  local want
  want="$(rec '?' '' '(executor)' '' '')"
  expect_parse "bash -c \"A=\\\"x y\\\" git push\"" "$want" || return 1
  expect_parse "bash -c \"A=x' 'y git push\"" "$want"
}

@test "undeterminable subcommand: git \$X gives ?" {
  expect_parse 'git $X --hard' "$(rec '?' '' '--hard' '' '')"
}

@test "undeterminable subcommand: quoted or substituted subcommand gives ?" {
  expect_parse 'git "reset" --hard' "$(rec '?' '' '--hard' '' '')" || return 1
  expect_parse 'git "$(echo reset)" --hard' "$(rec '?' '' '--hard' '' '')" || return 1
  expect_parse 'git re"set" --hard' "$(rec '?' '' '--hard' '' '')"
}

@test "undeterminable subcommand: an alias failing the name pattern gives ?" {
  expect_parse 'git Reset --hard' "$(rec '?' '' '--hard' '' '')" || return 1
  expect_parse 'git my_alias' "$(rec '?' '' '' '' '')"
}

# --- global options ---------------------------------------------------------

@test "global options: -C dir is skipped with its value" {
  expect_parse 'git -C some/dir reset' "$(rec reset '' '' '' '')"
}

@test "global options: -c x=y -C d commit" {
  expect_parse 'git -c x=y -C d commit' "$(rec commit '' '' '' '')"
}

@test "global options: a quoted -c value with spaces is one value" {
  expect_parse 'git -c "user.name=A B" commit' "$(rec commit '' '' '' '')"
}

@test "global options: --git-dir with separate and joined value" {
  expect_parse 'git --git-dir x reset' "$(rec reset '' '' '' '')" || return 1
  expect_parse 'git --git-dir=x reset' "$(rec reset '' '' '' '')" || return 1
  expect_parse 'git --work-tree w --namespace n --exec-path=/x reset' "$(rec reset '' '' '' '')"
}

@test "global options: -p and --no-pager take no value" {
  expect_parse 'git -p log' '' || return 1
  expect_parse 'git -p reset' "$(rec reset '' '' '' '')" || return 1
  expect_parse 'git --no-pager reset' "$(rec reset '' '' '' '')" || return 1
  expect_parse 'git --bare --no-optional-locks -P reset' "$(rec reset '' '' '' '')"
}

@test "global options: an unknown leading option is skipped alone" {
  expect_parse 'git --frob reset' "$(rec reset '' '' '' '')"
}

# --- flag names (ADR-3) -----------------------------------------------------

@test "flags: --opt=value records --opt" {
  expect_parse 'git push --force-with-lease=origin/main' "$(rec push '' '--force-with-lease' '' '')"
}

@test "flags: -mfoo records -m" {
  expect_parse 'git commit -mfoo' "$(rec commit '' '-m' '' '')"
}

@test "flags: -fd records -f" {
  expect_parse 'git clean -fd' "$(rec clean '' '-f' '' '')"
}

@test "flags: -- is recorded as a flag name and ends flags" {
  expect_parse 'git checkout -- file' "$(rec checkout '' '--' '' '')" || return 1
  expect_parse 'git checkout -f -- -x --y' "$(rec checkout '' '-f --' '' '')"
}

@test "flags: a lone - is a positional" {
  expect_parse 'git apply -' "$(rec apply '' '' '' '')"
}

@test "flags: redirections are not flags or positionals" {
  expect_parse 'git push --force 2>&1 >/dev/null' "$(rec push '' '--force' '' '')" || return 1
  expect_parse 'git tag > tags.txt' ''
}

# --- quoting, heredocs, executors -------------------------------------------

@test "a commit message mentioning git reset yields only commit" {
  expect_parse 'git commit -m "explain git reset --hard; git push -f"' "$(rec commit '' '-m' '' '')"
}

@test "a heredoc commit body mentioning git reset yields only commit" {
  expect_parse "git commit -F - <<'EOF'${NL}git reset --hard${NL}EOF" "$(rec commit '' '-F' '' '')"
}

@test "here-string: a <<< body is data" {
  expect_parse 'git commit -F - <<< "git reset --hard"' "$(rec commit '' '-F' '' '')"
}

@test "executor: bash -c 'git reset --hard' yields reset with flags (executor)" {
  expect_parse "bash -c 'git reset --hard'" "$(rec reset '' '(executor)' '' '')"
}

@test "executor: a message word that looks like a flag stays (executor)" {
  expect_parse "sh -c \"git commit -m '--codename-x'\"" "$(rec commit '' '(executor)' '' '')"
}

@test "executor: eval gives the action and the override" {
  expect_parse "CLAUDE_ALLOW_GIT_BAD_OPS=1 eval \"git stash drop\"" \
    "$(rec stash drop '(executor)' CLAUDE_ALLOW_GIT_BAD_OPS CLAUDE_ALLOW_GIT_BAD_OPS)"
}

@test "executor: a -c value cut open by quote removal makes the subcommand ?" {
  expect_parse "bash -c \"git -c core.editor='vim' commit\"" "$(rec '?' '' '(executor)' '' '')"
}

@test "executor: a separate global option value makes the subcommand ?" {
  local want
  want="$(rec '?' '' '(executor)' '' '')"
  expect_parse "bash -c \"git -C 'my dir' reset\"" "$want" || return 1
  expect_parse "bash -c \"git --git-dir 'a b' push\"" "$want" || return 1
  expect_parse "bash -c \"git --work-tree 'a b' push\"" "$want" || return 1
  expect_parse "bash -c 'git -C dir reset'" "$want"
}

@test "executor: a joined global option value makes the subcommand ?" {
  local want
  want="$(rec '?' '' '(executor)' '' '')"
  expect_parse "bash -c \"git --git-dir='a b' push\"" "$want" || return 1
  expect_parse "bash -c \"git --git-dir=a' b' push\"" "$want" || return 1
  expect_parse "bash -c 'git --git-dir=x push'" "$want"
}

@test "executor: value-less global options keep the subcommand" {
  expect_parse "bash -c 'git --no-pager -p reset'" "$(rec reset '' '(executor)' '' '')"
}

@test "executor: an emptied assignment before git makes the subcommand ?" {
  expect_parse "bash -c \"A='git push-me' true\"" "$(rec '?' '' '(executor)' '' '')"
}

@test "executor: a wrapper option or duration makes the subcommand ?" {
  local want
  want="$(rec '?' '' '(executor)' '' '')"
  expect_parse "bash -c \"sudo -u 'x git' secretword\"" "$want" || return 1
  expect_parse "bash -c \"env -u 'x git' secretword\"" "$want" || return 1
  expect_parse "bash -c \"env -S 'git secretword'\"" "$want" || return 1
  expect_parse "bash -c \"nice -n '5 git' secretword\"" "$want" || return 1
  expect_parse "bash -c \"timeout '5 git' secretword\"" "$want" || return 1
  expect_parse "bash -c \"time -p git push\"" "$want"
}

@test "executor: wrappers without options keep the subcommand" {
  expect_parse "bash -c 'sudo env nohup git push'" "$(rec push '' '(executor)' '' '')"
}

@test "executor: a fake clause from a nested-quote separator never names a command" {
  local commit_rec unknown
  commit_rec="$(rec commit '' '(executor)' '' '')"
  unknown="$(rec '?' '' '(executor)' '' '')"
  expect_parse "bash -c \"git commit -m 'a && git push-it now'\"" "${commit_rec}${NL}${unknown}" || return 1
  expect_parse "bash -c \"git commit -m 'wip; git hunter2tok'\"" "${commit_rec}${NL}${unknown}"
}

@test "executor: an alias behind bash -c gives ?" {
  expect_parse "bash -c 'git co main'" "$(rec '?' '' '(executor)' '' '')"
}

@test "executor: git's own commands are on the closed list" {
  local c failed=""
  for c in reset push commit stash worktree lfs cherry-pick filter-branch; do
    run _git_ops_parse "bash -c 'git $c'"
    if [ "$output" != "$(rec "$c" '' '(executor)' '' '')" ]; then
      failed="$failed ${c}[$output]"
    fi
  done
  [ -z "$failed" ] || { echo "not recorded by name:$failed"; return 1; }
}

@test "executor: read-only invocations inside bash -c record nothing" {
  expect_parse "bash -c 'git status && git log'" ''
}

@test "executor: bash -c only inside a message is no executor" {
  expect_parse "git commit -m 'run bash -c x' && git push" "$(rec commit '' '-m' '' '')${NL}$(rec push '' '' '' '')"
}

# --- command position -------------------------------------------------------

@test "wrappers: env, sudo, command, nohup, time, exec" {
  local push
  push="$(rec push '' '' '' '')"
  expect_parse 'env git push' "$push" || return 1
  expect_parse 'sudo git push' "$push" || return 1
  expect_parse 'command git push' "$push" || return 1
  expect_parse 'command -p git push' "$push" || return 1
  expect_parse 'nohup git push' "$push" || return 1
  expect_parse 'time git push' "$push" || return 1
  expect_parse 'exec git push' "$push" || return 1
  expect_parse '/usr/bin/git push' "$push"
}

@test "wrappers with options: sudo -u, env -i, env -u, time -p, nice -n, timeout" {
  expect_parse 'sudo -u u git push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'env -i git push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'env -u V git push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'env -i A=b git push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'time -p git push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'nice -n 5 git gc' "$(rec gc '' '' '' '')" || return 1
  expect_parse 'timeout 5 git fetch' "$(rec fetch '' '' '' '')" || return 1
  expect_parse 'timeout -s KILL 5 git fetch' "$(rec fetch '' '' '' '')"
}

@test "wrappers: command -v git is a lookup, no invocation" {
  expect_parse 'command -v git' '' || return 1
  expect_parse 'command -V git' ''
}

@test "leading assignments are skipped" {
  expect_parse 'GIT_DIR=x FOO=bar git reset' "$(rec reset '' '' '' '')"
}

@test "openers: \$(...), backticks, subshell, group, if, !" {
  expect_parse 'x=$(git reset --hard)' "$(rec reset '' '--hard' '' '')" || return 1
  expect_parse '`git pull`' "$(rec pull '' '' '' '')" || return 1
  expect_parse 'x=`git pull`' "$(rec pull '' '' '' '')" || return 1
  expect_parse '(git reset)' "$(rec reset '' '' '' '')" || return 1
  expect_parse '{ git reset; }' "$(rec reset '' '' '' '')" || return 1
  expect_parse 'if git pull; then echo ok; fi' "$(rec pull '' '' '' '')" || return 1
  expect_parse 'while git push; do :; done' "$(rec push '' '' '' '')" || return 1
  expect_parse '! git push' "$(rec push '' '' '' '')"
}

@test "separators: && || | ; & and newline each start a command" {
  local expected
  expected="$(rec add '' '' '' '')${NL}$(rec commit '' '-m' '' '')${NL}$(rec push '' '' '' '')${NL}$(rec fetch '' '' '' '')${NL}$(rec gc '' '' '' '')${NL}$(rec pull '' '' '' '')"
  expect_parse "git add .${NL}git commit -m x && git push || git fetch | git gc & git pull" "$expected"
}

@test "not an invocation: git mentioned as an argument" {
  expect_parse 'echo git reset --hard' '' || return 1
  expect_parse 'grep -r "git push" .' ''
}

@test "documented limit: xargs git and find -exec git are not recognised" {
  expect_parse 'printf x | xargs git branch -D' '' || return 1
  expect_parse 'find . -exec git rm {} +' ''
}

# --- overrides (guard first-token rule) -------------------------------------

@test "overrides: first token is override_first" {
  expect_parse 'CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_RESET_HARD)"
}

@test "overrides: one leading cd/pushd (&& ; newline) keeps first position" {
  local want
  want="$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_RESET_HARD)"
  expect_parse 'cd /x && CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' "$want" || return 1
  expect_parse 'cd /x; CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' "$want" || return 1
  expect_parse 'pushd /x && CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' "$want" || return 1
  expect_parse "cd /x${NL}CLAUDE_ALLOW_RESET_HARD=1 git reset --hard" "$want"
}

@test "overrides: two leading cd clauses lose first position" {
  expect_parse 'cd /a && cd /b && CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD '')"
}

@test "overrides: an override after another command is not first" {
  expect_parse 'git status; CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD '')"
}

@test "overrides: leading whitespace is not first position (guard anchor)" {
  expect_parse ' CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD '')"
}

@test "overrides: =0, =yes and = are not overrides" {
  expect_parse 'CLAUDE_ALLOW_RESET_HARD=0 git reset --hard' "$(rec reset '' '--hard' '' '')" || return 1
  expect_parse 'CLAUDE_ALLOW_RESET_HARD=yes git reset --hard' "$(rec reset '' '--hard' '' '')" || return 1
  expect_parse 'CLAUDE_ALLOW_RESET_HARD= git reset --hard' "$(rec reset '' '--hard' '' '')" || return 1
  expect_parse 'CLAUDE_ALLOW_RESET_HARD=11 git reset --hard' "$(rec reset '' '--hard' '' '')"
}

@test "overrides: several names in order; only the first stands first" {
  expect_parse 'CLAUDE_ALLOW_A=1 CLAUDE_ALLOW_B=1 git push --force' \
    "$(rec push '' '--force' 'CLAUDE_ALLOW_A CLAUDE_ALLOW_B' CLAUDE_ALLOW_A)"
}

@test "overrides: override_first goes on every record of the command" {
  expect_parse 'CLAUDE_ALLOW_X=1 git reset --hard && CLAUDE_ALLOW_X=1 git push && git clean -f' \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_X CLAUDE_ALLOW_X)${NL}$(rec push '' '' CLAUDE_ALLOW_X CLAUDE_ALLOW_X)${NL}$(rec clean '' '-f' '' CLAUDE_ALLOW_X)"
}

@test "overrides: a first-position override on a non-git clause covers the command" {
  expect_parse 'CLAUDE_ALLOW_RESET_HARD=1 true && git reset --hard' \
    "$(rec reset '' '--hard' '' CLAUDE_ALLOW_RESET_HARD)"
}

@test "overrides: a first-position override on a read-only clause covers the command" {
  expect_parse 'CLAUDE_ALLOW_RESET_HARD=1 git status && git reset --hard' \
    "$(rec reset '' '--hard' '' CLAUDE_ALLOW_RESET_HARD)"
}

@test "overrides: a mid-command override is in overrides only" {
  expect_parse 'git status && CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD '')"
}

@test "overrides: in the executor fallback override_first is per command too" {
  expect_parse "CLAUDE_ALLOW_RESET_HARD=1 bash -c 'git status; git reset --hard'" \
    "$(rec reset '' '(executor)' '' CLAUDE_ALLOW_RESET_HARD)"
}

@test "overrides: an override through env counts, but not as first" {
  expect_parse 'env CLAUDE_ALLOW_X=1 git push' "$(rec push '' '' CLAUDE_ALLOW_X '')"
}

# --- CON-13: no value in any record -----------------------------------------

@test "secrets corpus: no value reaches any record" {
  local s="hunter2tok" i out line why failed=""
  local -a corpus
  corpus=(
    "GITHUB_TOKEN=$s git push"
    "GH_TOKEN=$s CLAUDE_ALLOW_PUSH=1 git push origin main"
    "git push https://u:$s@github.com/o/r.git main"
    "git clone https://x-access-token:$s@github.com/o/r"
    "git -c http.extraHeader=\"Authorization: Bearer $s\" push"
    "git -c http.extraHeader=Authorization:$s fetch"
    "git commit -m$s"
    "git commit -m $s"
    "git commit --message=$s"
    "git remote set-url origin https://$s@github.com/o/r"
    "git credential-x --with-token $s"
    "git credential-x --with-token=$s"
    "git push --push-option=$s"
    "CLAUDE_ALLOW_X=$s git reset"
    "bash -c \"GITHUB_TOKEN=$s git push https://u:$s@h/r\""
    "sh -c 'git remote set-url origin https://$s@h/r'"
    "eval \"git commit -m $s\""
    "bash -c 'git commit -m$s --author=$s'"
    "bash -c \"git -c http.extraHeader='Authorization: Bearer $s' push\""
    "bash -c \"git -c x='$s' push\""
    "bash -c \"git -c 'x.y=a $s' push\""
    "bash -c \"git -C 'my $s' reset\""
    "bash -c \"git --git-dir 'a $s' push\""
    "bash -c \"git --git-dir='a $s' push\""
    "bash -c \"git --git-dir=a' $s' push\""
    "bash -c \"git --work-tree 'a $s' push\""
    "bash -c \"git --work-tree='a $s' push\""
    "bash -c \"git --namespace 'a $s' push\""
    "bash -c \"git --frob 'a $s' push\""
    "bash -c \"A='git $s' true\""
    "bash -c \"sudo -u 'x git' $s\""
    "bash -c \"env -u 'x git' $s\""
    "bash -c \"env -S 'git $s'\""
    "bash -c \"nice -n '5 git' $s\""
    "bash -c \"timeout '5 git' $s\""
    "bash -c \"git commit -m 'wip; git $s'\""
    "bash -c \"git commit -m 'a && git $s now'\""
    "bash -c \"git commit -m 'a || git push-it now'\""
    "bash -c \"git -C 'a --version' push\""
    # Command substitutions (one opaque word; content parsed on its own).
    'git -C $(echo hunter2) push'
    'git --git-dir $(realpath hunter2) push'
    'git -C `realpath hunter2` push'
    'git -C $(cd hunter2 && pwd) push'
    'git -C $(dirname $(echo hunter2)) push'
    'git -C $(echo `echo hunter2`) push'
    'git $(echo hunter2) push'
    'GIT_DIR=$(pwd) git push'
    'GIT_DIR=$(echo hunter2) git push'
    'git commit -m "$(git reset --hard)"'
    "bash -c \"A='x y' git push\""
    "bash -c \"A='x $s' git push\""
    # Escapes, parameter expansions, process substitutions, closed list.
    'git -C my\ hunter2 push'
    'git -c user.name=john\ hunter2 commit'
    'git -C ${D:-a hunter2 c} push'
    'git commit --author a\ --hunter2'
    'A=x\ hunter2 git push'
    "bash -c \"A=\\\"x hunter2\\\" git push\""
    "bash -c \"A=x' 'hunter2 git push\""
    'diff <(git push hunter2) x'
    'git hunter2'
    'git co hunter2'
    # Non-ASCII words never pass as names.
    'git é'
    'git Ä --x'
    'git pushé'
  )
  for ((i = 0; i < ${#corpus[@]}; i++)); do
    out="$(LC_ALL=en_US.UTF-8 _git_ops_parse "${corpus[$i]}")"
    if [ -z "$out" ]; then
      failed="$failed [no record: ${corpus[$i]}]"
      continue
    fi
    while IFS= read -r line; do
      why="$(_record_violation "$line")"
      if [ -n "$why" ]; then
        failed="$failed [${corpus[$i]} -> $line: $why]"
      fi
    done <<< "$out"
  done
  [ -z "$failed" ] || { echo "$failed"; return 1; }
}

# _record_violation <record>  prints why a record breaks CON-13, or nothing.
#   Every field is checked against the shape a NAME may have, so a value can
#   only pass by being shaped like a name; the corpus's secret words are
#   rejected by equality in the name fields and as substrings anywhere.
_record_violation() {
  local line="$1" f1 f2 f3 f4 f5 rest w tabs
  local lower='abcdefghijklmnopqrstuvwxyz' upper='ABCDEFGHIJKLMNOPQRSTUVWXYZ' digit='0123456789'
  tabs="${line//[!$TAB]/}"
  if [ "${#tabs}" -ne 4 ]; then echo "not five fields"; return 0; fi
  f1="${line%%"$TAB"*}"; rest="${line#*"$TAB"}"
  f2="${rest%%"$TAB"*}"; rest="${rest#*"$TAB"}"
  f3="${rest%%"$TAB"*}"; rest="${rest#*"$TAB"}"
  f4="${rest%%"$TAB"*}"; f5="${rest#*"$TAB"}"
  for w in hunter2tok hunter2 push-it é Ä; do
    case "$line" in *"$w"*) echo "contains secret word $w"; return 0 ;; esac
    if [ "$f1" = "$w" ] || [ "$f2" = "$w" ]; then echo "names $w"; return 0; fi
  done
  case "$f1" in
    '?') ;;
    [$lower]*) case "$f1" in *[!$lower$digit-]*) echo "subcommand not a name"; return 0 ;; esac ;;
    *) echo "subcommand not a name"; return 0 ;;
  esac
  case "$f2" in *[!$lower-]*) echo "action not a name"; return 0 ;; esac
  for w in $f3; do
    case "$w" in
      '(executor)') ;;
      -*=* | -*"%"*) echo "flag carries a value: $w"; return 0 ;;
      -*) ;;
      *) echo "flag field holds a non-flag: $w"; return 0 ;;
    esac
  done
  for w in $f4 $f5; do
    case "$w" in
      CLAUDE_ALLOW_?*) case "${w#CLAUDE_ALLOW_}" in *[!$upper${digit}_]*) echo "override not a name: $w"; return 0 ;; esac ;;
      *) echo "override not a name: $w"; return 0 ;;
    esac
  done
}

# --- command substitution: executed code, and one word around it --------------

@test "substitution: a \$( ) value after -C is one word" {
  expect_parse 'git -C $(echo x) push' "$(rec push '' '' '' '')"
}

@test "substitution: a \$( ) value after --git-dir is one word" {
  expect_parse 'git --git-dir $(realpath x) push' "$(rec push '' '' '' '')"
}

@test "substitution: a backtick value after -C is one word" {
  expect_parse 'git -C `realpath x` push' "$(rec push '' '' '' '')"
}

@test "substitution: a value with a separator inside stays one word" {
  expect_parse 'git -C $(cd x && pwd) push' "$(rec push '' '' '' '')"
}

@test "substitution: nested substitutions are one word" {
  expect_parse 'git -C $(dirname $(echo x)) push' "$(rec push '' '' '' '')" || return 1
  expect_parse 'git -C $(echo `echo x`) push' "$(rec push '' '' '' '')"
}

@test "substitution: an assignment value keeps the assignment one word" {
  expect_parse 'GIT_DIR=$(pwd) git push' "$(rec push '' '' '' '')"
}

@test "substitution: in subcommand position gives ?" {
  expect_parse 'git $(echo reset) --hard' "$(rec '?' '' '--hard' '' '')"
}

@test "substitution: its content is parsed as its own clauses" {
  expect_parse 'git commit -m "$(git reset --hard)"' "$(rec commit '' '-m' '' '')${NL}$(rec reset '' '--hard' '' '')" || return 1
  expect_parse 'echo $(git reset --hard)' "$(rec reset '' '--hard' '' '')" || return 1
  expect_parse 'echo `git push`' "$(rec push '' '' '' '')"
}

@test "substitution: nested content is parsed at every depth" {
  expect_parse 'echo $(echo $(git push --force))' "$(rec push '' '--force' '' '')"
}

@test "substitution: inside single quotes it is data" {
  expect_parse "git commit -m '\$(git reset --hard)'" "$(rec commit '' '-m' '' '')"
}

@test "executor: a value fragment that stops the scan still yields ?" {
  local want
  want="$(rec '?' '' '(executor)' '' '')"
  expect_parse "bash -c \"A='x y' git push\"" "$want" || return 1
  expect_parse "bash -c \"sudo -u 'a b' git push\"" "$want" || return 1
  expect_parse "bash -c \"git -C 'a --version' push\"" "$want"
}

@test "executor: without a cut an unknown first word is no invocation" {
  expect_parse "bash -c 'echo git push'" ''
}

@test "names are ASCII: non-ASCII letters give ? in a UTF-8 locale" {
  run env LC_ALL=en_US.UTF-8 bash -c 'source "$1"; _git_ops_parse "git é"; _git_ops_parse "git Ä"; _git_ops_parse "git pushé"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ "$output" = "$(rec '?' '' '' '' '')${NL}$(rec '?' '' '' '' '')${NL}$(rec '?' '' '' '' '')" ]
}

@test "a non-ASCII assignment name is no assignment in a UTF-8 locale" {
  run env LC_ALL=en_US.UTF-8 bash -c 'source "$1"; _git_ops_parse "CLAUDE_ALLOW_RÉSET=1 git push"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- robustness -------------------------------------------------------------

@test "a non-git command and empty input print nothing" {
  expect_parse 'ls -la' '' || return 1
  expect_parse '' '' || return 1
  expect_parse "${NL}${NL}" ''
}

@test "parse and decoder are safe under set -u" {
  run bash -uc 'source "$1"; _git_ops_parse "$2"; _git_ops_parse ""; _git_ops_parse "( )"; _git_ops_command "{}"; _git_ops_command "$3"' \
    _ "$BUNDLE_LIB" 'cd r && CLAUDE_ALLOW_A=1 git -C s reset --hard; git' '{"command":"git push"}'
  [ "$status" -eq 0 ]
  [ "$output" = "$(rec reset '' '--hard' CLAUDE_ALLOW_A CLAUDE_ALLOW_A)${NL}git push" ]
}

@test "parse leaves the caller's noglob and IFS untouched" {
  run bash -c 'source "$1"; _git_ops_parse "git push *" >/dev/null
    case "$-" in *f*) echo noglob-left-on ;; esac
    t=$(printf " \t\nx"); [ "$IFS" = "${t%x}" ] || echo ifs-changed' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "parse restores noglob when the caller had it on" {
  run bash -c 'set -f; source "$1"; _git_ops_parse "git push" >/dev/null
    case "$-" in *f*) ;; *) echo noglob-switched-off ;; esac' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
