#!/usr/bin/env bats
# shellcheck disable=SC2016,SC1003,SC2030,SC2031 # literal commands under test; bats run sets status/output
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
# The last section (T2.2) runs log_tool.sh end to end and reads the git
# records back from events.jsonl.
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

# _utf8_locale  sets UTF8_LOCALE to the first installed UTF-8 locale out of
#   en_US.UTF-8 and C.UTF-8 (any spelling `locale -a` uses). Fails, rather than
#   skipping, when there is none: the locale tests must never pass vacuously.
_utf8_locale() {
  local l
  UTF8_LOCALE=""
  for l in $(locale -a 2>/dev/null); do
    case "$l" in
      en_US.UTF-8 | en_US.utf8) UTF8_LOCALE="$l"; return 0 ;;
    esac
  done
  for l in $(locale -a 2>/dev/null); do
    case "$l" in
      C.UTF-8 | C.utf8) UTF8_LOCALE="$l"; return 0 ;;
    esac
  done
  echo "no UTF-8 locale (en_US.UTF-8 or C.UTF-8) installed" >&2
  return 1
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

@test "command position: a backslash-escaped git is the invocation" {
  expect_parse '\git push' "$(rec push '' '' '' '')"
}

@test "command position: a single-quoted git is the invocation" {
  expect_parse "'git' push" "$(rec push '' '' '' '')"
}

@test "command position: a double-quoted git is the invocation" {
  expect_parse '"git" push' "$(rec push '' '' '' '')" || return 1
  expect_parse '"/usr/bin/git" push' "$(rec push '' '' '' '')"
}

@test "command position: a quoted git inside a message stays in the message" {
  expect_parse "git commit -m \"say 'git' push\"" "$(rec commit '' '-m' '' '')"
}

@test "command position: leading redirections are skipped" {
  expect_parse '>/dev/null git push' "$(rec push '' '' '' '')" || return 1
  expect_parse '2>/dev/null git push' "$(rec push '' '' '' '')" || return 1
  expect_parse '2>&1 git push' "$(rec push '' '' '' '')" || return 1
  expect_parse '> out git push' "$(rec push '' '' '' '')"
}

@test "stash: an option before the verb means an implicit push, so -m list is recorded" {
  expect_parse 'git stash -m list' "$(rec stash '' '-m' '' '')" || return 1
  expect_parse 'git stash -m show' "$(rec stash '' '-m' '' '')"
}

@test "stash: the verb right after stash still decides" {
  expect_parse 'git stash list' '' || return 1
  expect_parse 'git stash push -m x' "$(rec stash push '-m' '' '')"
}

@test "flags: an unquoted separate value beginning with - reads as a flag (ADR-3 residual)" {
  expect_parse 'git commit -m --x' "$(rec commit '' '-m --x' '' '')" || return 1
  expect_parse 'git commit -m -x' "$(rec commit '' '-m -x' '' '')"
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

@test "overrides: a newline reads as the guard's ; (not as whitespace)" {
  expect_parse "CLAUDE_ALLOW_RESET_HARD=1${NL}git reset --hard" "$(rec reset '' '--hard' '' '')" || return 1
  expect_parse "cd /x &&${NL}CLAUDE_ALLOW_RESET_HARD=1 git reset --hard" \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD '')" || return 1
  expect_parse "cd${NL}/x; CLAUDE_ALLOW_RESET_HARD=1 git reset --hard" \
    "$(rec reset '' '--hard' CLAUDE_ALLOW_RESET_HARD '')"
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

# _secrets_corpus  fills the caller's array `corpus` with credential-bearing
#   command lines. Shared by the parser test below and the end-to-end test in
#   the T2.2 section (the same corpus through log_tool.sh into events.jsonl).
#   Every secret word is one of hunter2tok, hunter2, push-it, é, Ä.
_secrets_corpus() {
  local s="hunter2tok"
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
}

@test "secrets corpus: no value reaches any record" {
  local i out line why failed=""
  local -a corpus
  _secrets_corpus
  _utf8_locale || return 1
  for ((i = 0; i < ${#corpus[@]}; i++)); do
    out="$(export LC_ALL="$UTF8_LOCALE"; _git_ops_parse "${corpus[$i]}")"
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

@test "a UTF-8 locale exists and bash reads a two-byte letter as one character in it" {
  _utf8_locale || return 1
  run env LC_ALL="$UTF8_LOCALE" bash -c 'x="é"; printf %s "${#x}"'
  [ "$status" -eq 0 ]
  [ "$output" = "1" ]
}

@test "names are ASCII: non-ASCII letters give ? in a UTF-8 locale" {
  _utf8_locale || return 1
  run env LC_ALL="$UTF8_LOCALE" bash -c 'x="é"; [ "${#x}" -eq 1 ] || exit 3
    source "$1"; _git_ops_parse "git é"; _git_ops_parse "git Ä"; _git_ops_parse "git pushé"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ "$output" = "$(rec '?' '' '' '' '')${NL}$(rec '?' '' '' '' '')${NL}$(rec '?' '' '' '' '')" ]
}

@test "a non-ASCII assignment name is no assignment in a UTF-8 locale" {
  _utf8_locale || return 1
  run env LC_ALL="$UTF8_LOCALE" bash -c 'x="é"; [ "${#x}" -eq 1 ] || exit 3
    source "$1"; _git_ops_parse "CLAUDE_ALLOW_RÉSET=1 git push"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- size cap and scale (SDD Complex Logic, Size cap) -----------------------


# _rep <unit> <n>  prints the first n bytes of <unit> repeated.
_rep() {
  local s="$1"
  while [ "${#s}" -lt "$2" ]; do s="$s$s"; done
  printf '%s' "${s:0:$2}"
}

# _pad <n>  prints n `x` bytes.
_pad() {
  _rep x "$1"
}

# _best_of_3 <command…>  runs the command three times (output discarded) and
#   prints the fastest wall time as TIMEFORMAT=%R prints it. Defined here and
#   handed to the timing subshells with `declare -f`.
_best_of_3() {
  local TIMEFORMAT=%R t best="" _
  for _ in 1 2 3; do
    t=$( { time "$@" >/dev/null; } 2>&1 )
    if [ -z "$best" ] || [ "${t/./}" -lt "${best/./}" ]; then best="$t"; fi
  done
  printf '%s' "$best"
}

# Scale a wall-clock budget (in ms) by $TCS_PERF_SLACK (4 in CI), the
# convention of the other observability suites; duplicated, they are
# standalone.
_perf_budget_ms() {
  local budget="$1" slack="${TCS_PERF_SLACK:-1}"
  case "$slack" in
    '' | *[!0-9]*) slack=1 ;;
  esac
  if [ "$slack" -lt 1 ]; then slack=1; fi
  printf '%d' $((budget * slack))
}

# _ms <seconds as printed by TIMEFORMAT=%R>  prints whole milliseconds.
_ms() {
  local s="$1" whole frac
  whole="${s%%.*}"
  frac="${s#*.}000"
  frac="${frac:0:3}"
  printf '%d' $((10#$whole * 1000 + 10#$frac))
}

# _linear_ok <ms at 1x> <ms at 10x> <absolute budget ms> [floor ms]
#   Ten times the input may take at most ~15 times as long, never less than
#   the floor (default 200 ms; timer resolution and machine load), and must
#   stay inside the absolute budget. Both bounds scale with TCS_PERF_SLACK.
#   The quadratic versions this guards against took seconds at 10x.
_linear_ok() {
  local t1="$1" t10="$2" budget allowed floor="${4:-200}"
  budget="$(_perf_budget_ms "$3")"
  allowed=$((t1 * 15))
  if [ "$allowed" -lt "$floor" ]; then allowed="$floor"; fi
  allowed="$(_perf_budget_ms "$allowed")"
  if [ "$t10" -gt "$allowed" ] || [ "$t10" -gt "$budget" ]; then
    echo "1x ${t1} ms, 10x ${t10} ms (allowed ${allowed} ms, budget ${budget} ms)"
    return 1
  fi
}

# _scale <budget ms> <floor ms> <script>  runs <script> in a new `bash` (the
#   first on PATH: 3.2 on macOS, 5.x in CI's Linux leg) with the library
#   sourced, _rep and _best_of_3 defined and LC_ALL=C (the locale
#   _git_ops_parse runs its helpers under); the script prints "<t1> <t10>".
_scale() {
  run bash -c 'export LC_ALL=C; source "$1"; eval "$2"; eval "$3"' _ \
    "$BUNDLE_LIB" "$(declare -f _rep _best_of_3)" "$3"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  _linear_ok "$(_ms "${output% *}")" "$(_ms "${output#* }")" "$1" "$2"
}

@test "size cap: the cap is 4096" {
  [ "$_GIT_OPS_MAX_BYTES" -eq 4096 ]
}

@test "size cap: above the cap a free-standing git word gives one oversize marker" {
  expect_parse "git commit -m \"$(_pad 17000)\" && git push" "$(rec '?' '' '(oversize)' '' '')"
}

@test "size cap: above the cap a git word after ( or a separator still gives the marker" {
  expect_parse "echo $(_pad 17000);(git push)" "$(rec '?' '' '(oversize)' '' '')"
}

@test "size cap: the oversize marker keeps a first-position override" {
  expect_parse "CLAUDE_ALLOW_RESET_HARD=1 git reset --hard # $(_pad 4200)" \
    "$(rec '?' '' '(oversize)' '' CLAUDE_ALLOW_RESET_HARD)"
}

@test "size cap: the oversize marker keeps an override after one leading cd" {
  expect_parse "cd /x && CLAUDE_ALLOW_X=1 git push --force # $(_pad 4200)" \
    "$(rec '?' '' '(oversize)' '' CLAUDE_ALLOW_X)"
}

@test "size cap: a mid-command override is not override_first on the marker" {
  expect_parse "git status; CLAUDE_ALLOW_X=1 git push --force # $(_pad 4200)" \
    "$(rec '?' '' '(oversize)' '' '')"
}

@test "size cap: above the cap without a free-standing git word nothing is printed" {
  expect_parse "echo digit $(_pad 17000) gitx" ''
}

@test "size cap: at the cap the command is parsed; one byte more is not" {
  local cmd
  cmd="git push --force # $(_pad 4077)"
  [ "${#cmd}" -eq 4096 ] || return 1
  expect_parse "$cmd" "$(rec push '' '--force' '' '')" || return 1
  expect_parse "${cmd}x" "$(rec '?' '' '(oversize)' '' '')"
}

@test "size cap: a quoted message just under the cap is parsed" {
  expect_parse "git commit -m \"$(_pad 4000)\" && git push" \
    "$(rec commit '' '-m' '' '')${NL}$(rec push '' '' '' '')"
}

@test "size cap: the cap counts bytes in a UTF-8 caller locale too" {
  _utf8_locale || return 1
  # 2100 two-byte letters: 4211 bytes but only 2111 characters.
  run env LC_ALL="$UTF8_LOCALE" bash -c 'source "$1"
    x="é"; [ "${#x}" -eq 1 ] || exit 3
    s="é"; while [ "${#s}" -lt 2100 ]; do s="$s$s"; done
    _git_ops_parse "git push # ${s:0:2100}"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ "$output" = "$(rec '?' '' '(oversize)' '' '')" ]
}

@test "scale: the decoder is linear in the number of escapes and stays correct" {
  _scale 2000 500 '
    mk() { local k=0 s=""; while [ "$k" -lt "$1" ]; do s="${s}ab \\\"q\\\" \\n"; k=$((k + 1)); done
      printf "{\"tool_input\":{\"command\":\"git commit -m \\\\\"%s\\\\\"\"}}" "$s"; }
    want() { local k=0 s=""; while [ "$k" -lt "$1" ]; do s="${s}ab \"q\" "$'"'\n'"'; k=$((k + 1)); done
      printf "git commit -m \"%s\"" "$s"; }
    p1=$(mk 300); p10=$(mk 3000)
    [ "$(_git_ops_command "$p10")" = "$(want 3000)" ] || { echo wrong-decode; exit 1; }
    echo "$(_best_of_3 _git_ops_command "$p1") $(_best_of_3 _git_ops_command "$p10")"'
}

@test "scale: marking a long quoted span is linear" {
  _scale 1000 200 '
    NL=$'"'\n'"'
    h="git commit -m \"$(_rep x 1500)\""; t1=$(_best_of_3 _git_ops_mark_words)
    h="git commit -m \"$(_rep x 15000)\""; t10=$(_best_of_3 _git_ops_mark_words)
    echo "$t1 $t10"'
}

@test "scale: marking special-dense code is linear" {
  _scale 2000 200 '
    NL=$'"'\n'"'
    h="git commit $(_rep "\"a\" \$x \\\\ " 1500)"; t1=$(_best_of_3 _git_ops_mark_words)
    h="git commit $(_rep "\"a\" \$x \\\\ " 15000)"; t10=$(_best_of_3 _git_ops_mark_words)
    echo "$t1 $t10"'
}

@test "scale: marking escaped dollars inside double quotes is linear" {
  _scale 2000 200 '
    NL=$'"'\n'"'
    h="git commit -m \"$(_rep "\\\$x" 1500)\""; t1=$(_best_of_3 _git_ops_mark_words)
    h="git commit -m \"$(_rep "\\\$x" 15000)\""; t10=$(_best_of_3 _git_ops_mark_words)
    echo "$t1 $t10"'
}

# The full parse end to end (stripping, word marking, clause split, clause
# parse), with the cap lifted for the measurement: the linearity it protects
# is what makes any cap value affordable.
@test "scale: parsing dense, quoted-git, clause-heavy and word-heavy commands is linear" {
  _scale 12000 300 '
    _GIT_OPS_MAX_BYTES=999999
    t1=0 t10=0
    for unit in "\"a\" \$x \\\\ " "'"'"'git'"'"' x;" "git a; " "a " "-x "; do
      a=$(_best_of_3 _git_ops_parse "git commit $(_rep "$unit" 1500)")
      b=$(_best_of_3 _git_ops_parse "git commit $(_rep "$unit" 15000)")
      t1=$((t1 + 10#${a/./})); t10=$((t10 + 10#${b/./}))
    done
    printf "%d.%03d %d.%03d\n" $((t1 / 1000)) $((t1 % 1000)) $((t10 / 1000)) $((t10 % 1000))'
}


@test "unquote: a mismatched quote pair does not hide a later quoted git" {
  expect_parse "git commit -m \"git' x\"; \"git\" push" "$(rec commit '' '-m' '' '')${NL}$(rec push '' '' '' '')"
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

# =============================================================================
# T2.2 -- end to end: log_tool.sh writes git records
# =============================================================================
#
# The adapter is exec'd as an external process from inside a throwaway repo,
# payload on stdin, as the harness runs it; the record file is then read
# back. Parser-level expectations live above; these cases check what reaches
# events.jsonl: the record shape, the caller fields, the fail-open paths and
# the cost (PRD F3 AC1-AC10, SDD Runtime View primary flow and error
# handling, CON-7, CON-13).
#
# Each case calls _e2e_setup first; the parser cases above stay fixture-free.

_e2e_setup() {
  ADAPTER_DIR="$REPO_ROOT/plugins/tcs-helper/scripts/observability"
  ADAPTER="$ADAPTER_DIR/log_tool.sh"
  GUARD="$REPO_ROOT/plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh"

  local tmpbase="${TMPDIR:-/tmp}"
  while [ "$tmpbase" != "/" ] && [ "${tmpbase%/}" != "$tmpbase" ]; do
    tmpbase="${tmpbase%/}"
  done
  TEST_DIR="$(mktemp -d "$tmpbase/tcs-observability-git.XXXXXX")" || return 1

  # git -C plus an isolated global config: a failed init must never fall
  # back to the enclosing repository.
  REPO="$TEST_DIR/myrepo"
  mkdir -p "$REPO"
  export GIT_CONFIG_GLOBAL=/dev/null
  git -C "$REPO" init -q -b main || return 1
  [ -d "$REPO/.git" ] || return 1

  DATA="$TEST_DIR/data"
  EVENTS="$DATA/observability/events.jsonl"

  # Warm the files under test: macOS charges 150-290 ms for a file's first exec.
  CLAUDE_OBSERVABILITY_ENABLED=1 "$ADAPTER" >/dev/null 2>&1 </dev/null
  return 0
}

teardown() {
  [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
  return 0
}

# _json_str <text>  prints <text> as the body of a JSON string (no quotes).
_json_str() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

# _bash_payload <command> [extra top-level JSON fragment]
#   A PreToolUse Bash payload in the field order Claude Code 2.1.296 sends.
_bash_payload() {
  printf '{"session_id":"sess-g","transcript_path":"/home/u/.claude/projects/x/s.jsonl","cwd":"%s"%s,"permission_mode":"default","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"%s","description":"d"},"tool_use_id":"toolu_01GIT"}' \
    "$REPO" "${2:-}" "$(_json_str "$1")"
}

# _adapter <script> <payload file> [NAME=VALUE ...]
#   Runs <script> from $REPO with the payload on stdin and recording on.
#   Sets status; stdout and stderr land in $TEST_DIR/out and $TEST_DIR/err.
_adapter() {
  local script="$1" file="$2"
  shift 2
  status=0
  env CLAUDE_OBSERVABILITY_ENABLED=1 CLAUDE_OBSERVABILITY_DATA="$DATA" "$@" \
    bash -c 'cd "$1" && "$2" < "$3"' _ "$REPO" "$script" "$file" \
    >"$TEST_DIR/out" 2>"$TEST_DIR/err" </dev/null || status=$?
}

# _record_git <command> [extra fragment] [-- NAME=VALUE ...]  runs the real
#   adapter on a Bash payload for <command> and requires exit 0, silence.
_record_git() {
  local cmd="$1" extra=""
  shift
  if [ $# -gt 0 ] && [ "$1" != "--" ]; then extra="$1"; shift; fi
  if [ "${1:-}" = "--" ]; then shift; fi
  _bash_payload "$cmd" "$extra" > "$TEST_DIR/payload.json"
  _adapter "$ADAPTER" "$TEST_DIR/payload.json" "$@"
  _silent_ok
}

_silent_ok() {
  [ "$status" -eq 0 ] || { echo "exit $status"; return 1; }
  [ -s "$TEST_DIR/out" ] && { echo "stdout: $(cat "$TEST_DIR/out")"; return 1; }
  [ -s "$TEST_DIR/err" ] && { echo "stderr: $(cat "$TEST_DIR/err")"; return 1; }
  return 0
}

# _git_lines  prints the kind=git records written so far (one per line).
_git_lines() {
  [ -f "$EVENTS" ] || return 0
  grep -F '"kind":"git"' "$EVENTS" || true
}

_git_count() {
  local n
  n="$(_git_lines | wc -l | tr -d ' ')"
  printf '%s' "$n"
}

# _expect_line <line> <exact JSON fragment>...  every fragment must occur.
_expect_line() {
  local line="$1" f
  shift
  for f in "$@"; do
    case "$line" in
      *"$f"*) ;;
      *) printf 'missing %s in\n%s\n' "$f" "$line"; return 1 ;;
    esac
  done
}

# _forbid_line <line> <text>...  no text may occur.
_forbid_line() {
  local line="$1" f
  shift
  for f in "$@"; do
    case "$line" in
      *"$f"*) printf 'unexpected %s in\n%s\n' "$f" "$line"; return 1 ;;
    esac
  done
}

# _expect_exact <line> <JSON after the ts field>  the whole record line must
#   be {"ts":"<UTC timestamp>",<rest>: field order, no extra or duplicate
#   field. Only the timestamp is matched as a pattern.
_expect_exact() {
  case "$1" in
    '{"ts":"'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'",'"$2") return 0 ;;
  esac
  printf 'expected: {"ts":"…",%s\nactual:   %s\n' "$2" "$1"
  return 1
}

@test "e2e: git reset --hard from the main session writes one git record" {
  _e2e_setup || return 1
  _record_git 'git reset --hard' || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  local line
  line="$(_git_lines)"
  _expect_line "$line" '"kind":"git"' '"session":"sess-g"' '"repo":"myrepo"' \
    '"subcommand":"reset"' '"action":""' '"flags":"--hard"' '"overrides":""' \
    '"override_first":""' '"caller":"main"' '"tool_use_id":"toolu_01GIT"' || return 1
  # The main session says so: no agent fields to leave ambiguous (F3 AC3).
  _forbid_line "$line" caller_agent_type caller_agent_id || return 1
  # Field order: the SDD data model's, after the four frozen fields.
  _expect_exact "$line" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"reset","action":"","flags":"--hard","overrides":"","override_first":"","caller":"main","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: inside a subagent the record names caller subagent, its type and id" {
  _e2e_setup || return 1
  _record_git 'git reset --hard' ',"agent_id":"ag-77","agent_type":"general-purpose"' || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_exact "$(_git_lines)" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"reset","action":"","flags":"--hard","overrides":"","override_first":"","caller":"subagent","caller_agent_type":"general-purpose","caller_agent_id":"ag-77","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: a command that quotes agent_id keys cannot forge a subagent caller" {
  _e2e_setup || return 1
  _record_git 'git commit -m "{\"agent_id\":\"forged\"}"' || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_line "$(_git_lines)" '"subcommand":"commit"' '"caller":"main"' || return 1
  _forbid_line "$(cat "$EVENTS")" forged
}

@test "e2e: an override is named, first position recorded, value never" {
  _e2e_setup || return 1
  _record_git 'CLAUDE_ALLOW_RESET_HARD=1 git reset --hard' || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  local line
  line="$(_git_lines)"
  # The exact line leaves no room for the value (`=1`) anywhere.
  _expect_exact "$line" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"reset","action":"","flags":"--hard","overrides":"CLAUDE_ALLOW_RESET_HARD","override_first":"CLAUDE_ALLOW_RESET_HARD","caller":"main","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: a compound command with three git calls, one read-only, writes two records" {
  _e2e_setup || return 1
  _record_git 'git add -A && git status && git commit -m "wip"' || return 1
  [ "$(_git_count)" = "2" ] || { cat "$EVENTS"; return 1; }
  local first second
  first="$(_git_lines | sed -n 1p)"
  second="$(_git_lines | sed -n 2p)"
  _expect_exact "$first" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"add","action":"","flags":"-A","overrides":"","override_first":"","caller":"main","tool_use_id":"toolu_01GIT"}' || return 1
  _expect_exact "$second" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"commit","action":"","flags":"-m","overrides":"","override_first":"","caller":"main","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: git status alone writes nothing" {
  _e2e_setup || return 1
  _record_git 'git status' || return 1
  [ ! -e "$EVENTS" ] || { cat "$EVENTS"; return 1; }
}

@test "e2e: a command naming git without running it writes nothing" {
  _e2e_setup || return 1
  # Passes the adapter's "git" substring test, so the parser runs.
  _record_git 'echo github digit && ls .gitignore' || return 1
  [ ! -e "$EVENTS" ] || { cat "$EVENTS"; return 1; }
  _record_git 'ls -la' || return 1
  [ ! -e "$EVENTS" ] || { cat "$EVENTS"; return 1; }
}

@test "e2e: git stash pop is recorded with action pop" {
  _e2e_setup || return 1
  _record_git 'git stash pop' || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_exact "$(_git_lines)" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"stash","action":"pop","flags":"","overrides":"","override_first":"","caller":"main","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: an unknown subcommand is recorded as ? with its flags" {
  _e2e_setup || return 1
  _record_git 'git frobnicate --x' || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_exact "$(_git_lines)" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"?","action":"","flags":"--x","overrides":"","override_first":"","caller":"main","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: an oversize command writes the one value-free marker record" {
  _e2e_setup || return 1
  _record_git "git commit -m $(_pad 5000)" || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_line "$(_git_lines)" '"subcommand":"?"' '"flags":"(oversize)"' || return 1
  _forbid_line "$(cat "$EVENTS")" xxxxxxxx
}

@test "e2e: flags over 256 bytes are cut by the writer and marked truncated" {
  _e2e_setup || return 1
  local f="" i
  for ((i = 0; i < 40; i++)); do f="$f --flag-number-$i"; done
  _record_git "git push$f" || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_line "$(_git_lines)" '"subcommand":"push"' '"flags":"--flag-number-0 ' '"truncated":true'
}

@test "e2e: a guard-denied git reset --hard is still recorded (hooks run side by side)" {
  _e2e_setup || return 1
  command -v jq >/dev/null 2>&1 || { echo "jq is required by the guard under test"; return 1; }
  _bash_payload 'git reset --hard' > "$TEST_DIR/payload.json"
  # Claude Code runs every matching PreToolUse hook on the same payload;
  # neither waits for the other.
  _adapter "$GUARD" "$TEST_DIR/payload.json"
  [ "$status" -eq 0 ] || return 1
  grep -qF '"permissionDecision":"deny"' "$TEST_DIR/out" || { cat "$TEST_DIR/out"; return 1; }
  grep -qF 'RESET_HARD' "$TEST_DIR/out" || return 1
  _adapter "$ADAPTER" "$TEST_DIR/payload.json"
  _silent_ok || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_line "$(_git_lines)" '"subcommand":"reset"' '"flags":"--hard"' '"override_first":""'
}

@test "e2e: git_ops.sh missing or broken: no git record, exit 0, silent; skill and dispatch still record" {
  _e2e_setup || return 1
  local bundle="$TEST_DIR/bundle" variant
  for variant in missing syntax empty; do
    rm -rf "$bundle" "$DATA"
    mkdir -p "$bundle"
    cp "$ADAPTER_DIR/log_tool.sh" "$ADAPTER_DIR/logwrite.sh" "$bundle/"
    case "$variant" in
      syntax) printf '_git_ops_parse() {\n  if then\n' > "$bundle/git_ops.sh" ;;
      empty) : > "$bundle/git_ops.sh" ;;
    esac
    _bash_payload 'git reset --hard' > "$TEST_DIR/payload.json"
    _adapter "$bundle/log_tool.sh" "$TEST_DIR/payload.json"
    _silent_ok || { echo "variant $variant"; return 1; }
    [ "$(_git_count)" = "0" ] || { echo "variant $variant"; cat "$EVENTS"; return 1; }

    printf '{"session_id":"sess-g","hook_event_name":"PreToolUse","tool_name":"Skill","tool_input":{"skill":"tcs-issues:issue"},"tool_use_id":"toolu_S"}' > "$TEST_DIR/skill.json"
    _adapter "$bundle/log_tool.sh" "$TEST_DIR/skill.json"
    _silent_ok || return 1
    printf '{"session_id":"sess-g","hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"description":"d","prompt":"p","subagent_type":"Explore"},"tool_use_id":"toolu_A"}' > "$TEST_DIR/agent.json"
    _adapter "$bundle/log_tool.sh" "$TEST_DIR/agent.json"
    _silent_ok || return 1
    grep -qF '"kind":"skill"' "$EVENTS" || { echo "variant $variant: no skill record"; return 1; }
    grep -qF '"kind":"dispatch"' "$EVENTS" || { echo "variant $variant: no dispatch record"; return 1; }
  done
}

@test "e2e: a parser line with fewer than five fields writes no record" {
  _e2e_setup || return 1
  local bundle="$TEST_DIR/bundle"
  mkdir -p "$bundle"
  cp "$ADAPTER_DIR/log_tool.sh" "$ADAPTER_DIR/logwrite.sh" "$bundle/"
  # A stub parser: one short line (three TABs), then one well-formed line.
  cat > "$bundle/git_ops.sh" <<'STUB'
_git_ops_command() { printf 'git x'; }
_git_ops_parse() { printf 'reset\t\t--hard\tCLAUDE_ALLOW_X\n'; printf 'push\t\t\t\t\n'; }
STUB
  _bash_payload 'git x' > "$TEST_DIR/payload.json"
  _adapter "$bundle/log_tool.sh" "$TEST_DIR/payload.json"
  _silent_ok || return 1
  [ "$(_git_count)" = "1" ] || { cat "$EVENTS"; return 1; }
  _expect_exact "$(_git_lines)" '"kind":"git","session":"sess-g","repo":"myrepo","subcommand":"push","action":"","flags":"","overrides":"","override_first":"","caller":"main","tool_use_id":"toolu_01GIT"}'
}

@test "e2e: git rev-parse runs once per payload, however many records" {
  _e2e_setup || return 1
  local shim="$TEST_DIR/shim" count="$TEST_DIR/rev-parse.count" real
  real="$(command -v git)"
  mkdir -p "$shim"
  printf '#!/bin/sh\n[ "$1" = rev-parse ] && printf x >> "%s"\nexec "%s" "$@"\n' "$count" "$real" > "$shim/git"
  chmod +x "$shim/git"
  : > "$count"
  _record_git 'git add -A && git commit -m x && git push && git tag v1' -- PATH="$shim:$PATH" || return 1
  [ "$(_git_count)" = "4" ] || { cat "$EVENTS"; return 1; }
  [ "$(wc -c < "$count" | tr -d ' ')" = "1" ] || { echo "rev-parse ran $(wc -c < "$count" | tr -d ' ') times"; return 1; }
  # The toplevel it resolved is the one every record carries.
  [ "$(grep -c '"repo":"myrepo"' "$EVENTS" | tr -d ' ')" = "4" ]
}

@test "e2e: the secrets corpus leaves no value in events.jsonl, reduced or detail" {
  _e2e_setup || return 1
  local -a corpus
  _secrets_corpus
  local mode i before after w failed=""
  for mode in 0 1; do
    rm -rf "$DATA"
    for ((i = 0; i < ${#corpus[@]}; i++)); do
      before="$(_git_count)"
      _bash_payload "${corpus[$i]}" > "$TEST_DIR/payload.json"
      _adapter "$ADAPTER" "$TEST_DIR/payload.json" CLAUDE_OBSERVABILITY_DETAIL="$mode"
      _silent_ok || { failed="$failed [detail=$mode not silent: ${corpus[$i]}]"; continue; }
      after="$(_git_count)"
      # Every corpus command is a git command: no record would make the
      # leak check below vacuous for it.
      [ "$after" -gt "$before" ] || failed="$failed [detail=$mode no record: ${corpus[$i]}]"
    done
    for w in hunter2tok hunter2 push-it é Ä; do
      if grep -qF -- "$w" "$EVENTS"; then
        failed="$failed [detail=$mode: $w in $(grep -F -- "$w" "$EVENTS" | head -1)]"
      fi
    done
  done
  [ -z "$failed" ] || { echo "$failed"; return 1; }
}

_now_us() {
  perl -MTime::HiRes=time -e 'printf q{%d}, time()*1000000'
}

# _best_ms <runs> <script> <payload file>  prints the fastest wall time, in
#   ms, of <runs> adapter execs (wall clock, so a busy machine only slows it).
_best_ms() {
  local runs="$1" script="$2" file="$3" i t0 t1 best=""
  for ((i = 0; i < runs; i++)); do
    t0="$(_now_us)"
    CLAUDE_OBSERVABILITY_ENABLED=1 CLAUDE_OBSERVABILITY_DATA="$DATA" "$script" < "$file" >/dev/null 2>&1
    t1="$(_now_us)"
    if [ -z "$best" ] || [ $((t1 - t0)) -lt "$best" ]; then best=$((t1 - t0)); fi
  done
  printf '%d' $((best / 1000))
}

# CON-7 (revised 2026-10-12, README Decisions Log): one git record may add
# at most 30 ms over the non-git path. The recorder runs in parallel with the
# guard, so its cost overlaps the guard's. On macOS about 12 ms of it is the
# one `git rev-parse` through the xcrun shim; the writer's fast path keeps
# the record itself to a few ms. Best of 15 on each side, so a busy machine
# only adds noise to both.
#
# Measured at ~27 ms added on an idle macOS machine, close to the budget, so
# a transient spike gets up to three attempts and the case passes if any one
# is within budget. It is never skipped: under sustained CPU load it fails,
# and the failure prints the floor. An idle floor is ~11 ms on macOS; a
# much higher one means a loaded machine -- rerun locally with
# TCS_PERF_SLACK=2 (CI runs with 4).
@test "perf: one git record costs at most 30 ms over the non-git path (CON-7)" {
  _e2e_setup || return 1
  command -v perl >/dev/null 2>&1 || { echo "perl is required for a sub-second clock"; return 1; }
  _bash_payload 'git push origin main' > "$TEST_DIR/git.json"
  _bash_payload 'ls -la' > "$TEST_DIR/nongit.json"
  local git_ms floor_ms added budget attempt passed=0
  budget="$(_perf_budget_ms 30)"
  (cd "$REPO" && _best_ms 2 "$ADAPTER" "$TEST_DIR/git.json" >/dev/null)
  [ "$(_git_count)" -ge 1 ] || return 1
  for attempt in 1 2 3; do
    floor_ms="$(cd "$REPO" && _best_ms 15 "$ADAPTER" "$TEST_DIR/nongit.json")"
    git_ms="$(cd "$REPO" && _best_ms 15 "$ADAPTER" "$TEST_DIR/git.json")"
    added=$((git_ms - floor_ms))
    printf 'git record, attempt %d: %d ms total, %d ms non-git floor, %d ms added (budget %d ms)\n' \
      "$attempt" "$git_ms" "$floor_ms" "$added" "$budget" >&3
    if [ "$added" -le "$budget" ]; then passed=1; break; fi
  done
  [ "$passed" -eq 1 ] || {
    printf '%d ms added, %d ms floor, budget %d ms after 3 attempts\n' "$added" "$floor_ms" "$budget"
    printf 'machine loaded? floor is %dms (idle ~11 ms); locally rerun with TCS_PERF_SLACK=2\n' "$floor_ms"
    return 1
  }
}

@test "perf (gross guard): a 4 KB compound git command stays bounded" {
  _e2e_setup || return 1
  command -v perl >/dev/null 2>&1 || { echo "perl is required for a sub-second clock"; return 1; }
  local cmd="" ms budget
  local msg=""
  # A typical large command: a few git calls around a long message.
  while [ "${#msg}" -lt 3950 ]; do msg="${msg}Rework the parser so a value stays one word. "; done
  cmd="git add -A && git commit -m \"${msg:0:3950}\" && git push origin main"
  [ "${#cmd}" -le 4096 ] || { echo "fixture is ${#cmd} bytes"; return 1; }
  _bash_payload "$cmd" > "$TEST_DIR/big.json"
  ms="$(cd "$REPO" && _best_ms 3 "$ADAPTER" "$TEST_DIR/big.json")"
  budget="$(_perf_budget_ms 1000)"
  printf '4 KB compound command (%d bytes): %d ms, %d records per run (budget %d ms)\n' \
    "${#cmd}" "$ms" $(( $(_git_count) / 3 )) "$budget" >&3
  [ "$(_git_count)" = "9" ] || return 1
  [ "$ms" -le "$budget" ]
}
