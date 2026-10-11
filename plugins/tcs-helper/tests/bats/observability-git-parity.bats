#!/usr/bin/env bats
#
# tests/bats/observability-git-parity.bats
#
# spec 021 (observability v2), Phase 1, T1.2 -- parity of the copied clause
# stripping (SDD/ADR-2, CON-12).
#
# plugins/tcs-helper/scripts/observability/git_ops.sh carries a COPY of three
# pieces of plugins/tcs-git-helpers/scripts/lib/pattern_match.sh:
#   _strip_heredocs, _strip_quoted and the shell-executor predicate.
# The bundle may not source the guard (CON-12), so this suite is what keeps the
# two copies equal: the same corpus goes through both implementations, each
# sourced in its OWN bash process, and the results are compared byte for byte.
#
# Only this TEST sources both files; git_ops.sh itself must not source anything.
#
# bash 3.2 compatible. No process substitution (bats `run` forbids it); the
# driver is a temp file and trailing newlines are protected with a sentinel.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  GUARD_LIB="$REPO_ROOT/plugins/tcs-git-helpers/scripts/lib/pattern_match.sh"
  BUNDLE_LIB="$REPO_ROOT/plugins/tcs-helper/scripts/observability/git_ops.sh"
  DRIVER="$BATS_TEST_TMPDIR/driver.sh"
  # driver.sh <lib> <fn-prefix> <command>
  #   prints: heredoc-stripped <END1> fully-stripped <END2> executor rc
  cat > "$DRIVER" <<'DRIVER_EOF'
lib="$1"; prefix="$2"; cmd="$3"
source "$lib" || exit 97
h=$("${prefix}strip_heredocs" "$cmd"; printf x); h=${h%x}
q=$("${prefix}strip_quoted" "$h"; printf x); q=${q%x}
if "${prefix}has_shell_executor" "$q"; then e=1; else e=0; fi
# The predicate on the raw text too: stripping always appends a newline, which
# hides edge cases such as `-c` at the very end of the input.
if "${prefix}has_shell_executor" "$cmd"; then r=1; else r=0; fi
printf '[heredocs]%s[/heredocs]\n[stripped]%s[/stripped]\n[executor]%s\n[executor-raw]%s\n' "$h" "$q" "$e" "$r"
DRIVER_EOF
  NL=$'\n'
  CASES=()
  # Commit / PR bodies that merely NAME git operations.
  CASES+=("git commit -m 'revert: git reset --hard HEAD~1 and git push --force'")
  CASES+=("git commit -m \"docs: explain git clean -fd and git checkout .\"")
  CASES+=("gh pr create --title 'x' --body 'never run git push --force or bash -c here'")
  # Heredocs: quoted, dash, unquoted, with terminator indentation.
  CASES+=("git commit -F - <<'EOF'${NL}fix: git reset --hard is described here${NL}bash -c 'rm -rf x'${NL}EOF")
  CASES+=("cat <<-EOF${NL}	git push --force${NL}	EOF${NL}git status")
  CASES+=("git commit -F - <<EOF${NL}body mentions git branch -D${NL}EOF${NL}git push origin main")
  # Heredoc feeding an interpreter stays code.
  CASES+=("bash <<'EOF'${NL}git reset --hard${NL}EOF")
  CASES+=("python3 <<EOF${NL}import os${NL}EOF")
  # One heredoc per interpreter the guard names, so drift in that list shows.
  local interp
  for interp in sh bash zsh ksh dash csh tcsh fish python3.12 perl ruby node awk sed eval; do
    CASES+=("${interp} <<'EOF'${NL}git reset --hard${NL}EOF")
  done
  # `git stash` ends in "sh" but is no interpreter: its heredoc body is data.
  CASES+=("git stash <<'EOF'${NL}git reset --hard${NL}EOF")
  # Delimiter parsing: operator glued to the delimiter, double-quoted delimiter
  # (a command AFTER the terminator shows whether the terminator was matched).
  CASES+=("cat <<EOF|grep x${NL}git reset --hard${NL}EOF${NL}git push")
  CASES+=("cat <<EOF&&git status${NL}git reset --hard${NL}EOF${NL}git push")
  CASES+=("git commit -F - <<\"EOF\"${NL}git reset --hard${NL}EOF${NL}git push")
  # Executor edges: -c at end of input; the word anchor before [a-z]*sh.
  CASES+=("bash -c")
  CASES+=("my_bash -c 'git reset --hard'")
  CASES+=("/bin/bash -c 'x'")
  # Executors: real ones vs. ones a body merely mentions (#213).
  CASES+=("bash -c 'git reset --hard'")
  CASES+=("sh -c \"git push --force\"")
  CASES+=("eval 'git clean -fd'")
  CASES+=("eval \"\$cmd\"")
  CASES+=("git commit -m 'run bash -c something' && echo ok")
  CASES+=("cat <<'EOF'${NL}bash -c 'x'${NL}eval y${NL}EOF")
  # Command substitution: code inside, quoting inside, nesting.
  CASES+=("git commit -m \"\$(git rev-parse HEAD)\"")
  CASES+=("echo \"\$(printf \"x\") git reset --hard\"")
  CASES+=("echo \$(echo 'a b') && git status")
  CASES+=("x=\"\$(cd \"\$(dirname \"\$0\")\" && pwd)\" git push")
  CASES+=("echo \"\$(echo 'it''s') tail\"")
  CASES+=("git commit -m \"\$(cat <<'EOF'${NL}message with git reset --hard${NL}EOF${NL})\"")
  # Here-string, escapes, unbalanced input.
  CASES+=("cat <<< 'git reset --hard'")
  CASES+=("grep <<< \"git push --force\" && git status")
  CASES+=("echo \"say \\\"git reset --hard\\\" now\" ; git status")
  CASES+=("echo 'unterminated quote git reset --hard")
  CASES+=("git commit -F - <<EOF${NL}unterminated heredoc body git reset --hard")
  CASES+=("echo ) stray paren; git status")
  # Plain commands and empties.
  CASES+=("git status")
  CASES+=("ls -la | git commit -n")
  CASES+=("")
  CASES+=("${NL}${NL}git status${NL}")
}

_run_impl() { # <lib> <prefix> <command> -> output in $_OUT
  _OUT=$(bash "$DRIVER" "$1" "$2" "$3"; printf x) || return 1
  _OUT=${_OUT%x}
}

# The [stripped] section of $_OUT (the fully stripped text).
_stripped_part() {
  local t="${_OUT#*\[stripped\]}"
  printf '%s' "${t%%\[/stripped\]*}"
}

@test "both implementations exist and load without output" {
  [ -f "$GUARD_LIB" ]
  [ -f "$BUNDLE_LIB" ]
  run bash -c 'source "$1"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  # Sourcing must not leave errexit (e) or nounset (u) switched on.
  run bash -c 'source "$1"; printf "%s" "$-"' _ "$BUNDLE_LIB"
  [ "$status" -eq 0 ]
  case "$output" in *e* | *u*) return 1 ;; esac
}

@test "git_ops.sh has no line-start source or . command (CON-12)" {
  run grep -En '^[[:space:]]*(source|\.)[[:space:]]' "$BUNDLE_LIB"
  [ "$status" -eq 1 ]
}

@test "stripped output and executor decision are byte-identical over the corpus" {
  local i guard bundle failed=""
  for ((i = 0; i < ${#CASES[@]}; i++)); do
    _run_impl "$GUARD_LIB" "_" "${CASES[$i]}" || { failed="$failed $i(guard-failed)"; continue; }
    guard="$_OUT"
    _run_impl "$BUNDLE_LIB" "_git_ops_" "${CASES[$i]}" || { failed="$failed $i(bundle-failed)"; continue; }
    bundle="$_OUT"
    if [ "$guard" != "$bundle" ]; then
      failed="$failed $i"
      printf 'case %s differs\n--- guard\n%s\n--- bundle\n%s\n' "$i" "$guard" "$bundle" >&3
    fi
  done
  [ -z "$failed" ] || { echo "diverging cases:$failed"; return 1; }
}

# The parity loop above would pass if both sides were equally broken; these
# pin the behaviour the corpus exists for, on the bundle copy.

@test "bundle: git ops named in a commit message are blanked" {
  _run_impl "$BUNDLE_LIB" "_git_ops_" "git commit -m 'git reset --hard'" || return 1
  case "$(_stripped_part)" in *"reset --hard"*) return 1 ;; esac
  case "$_OUT" in *"[executor]0"*) ;; *) return 1 ;; esac
}

@test "bundle: a heredoc body is blanked, a heredoc into bash is kept" {
  _run_impl "$BUNDLE_LIB" "_git_ops_" "cat <<'EOF'${NL}git reset --hard${NL}EOF" || return 1
  case "$(_stripped_part)" in *"reset --hard"*) return 1 ;; esac
  _run_impl "$BUNDLE_LIB" "_git_ops_" "bash <<'EOF'${NL}git reset --hard${NL}EOF" || return 1
  case "$(_stripped_part)" in *"reset --hard"*) ;; *) return 1 ;; esac
}

@test "bundle: bash -c and eval are executors; a mention in a message is not (#213)" {
  _run_impl "$BUNDLE_LIB" "_git_ops_" "bash -c 'git reset --hard'" || return 1
  case "$_OUT" in *"[executor]1"*) ;; *) return 1 ;; esac
  _run_impl "$BUNDLE_LIB" "_git_ops_" "eval 'git clean -fd'" || return 1
  case "$_OUT" in *"[executor]1"*) ;; *) return 1 ;; esac
  _run_impl "$BUNDLE_LIB" "_git_ops_" "git commit -m 'run bash -c x'" || return 1
  case "$_OUT" in *"[executor]0"*) ;; *) return 1 ;; esac
}

@test "bundle: command substitution inside double quotes stays code" {
  _run_impl "$BUNDLE_LIB" "_git_ops_" 'echo "$(git reset --hard) prose git push"' || return 1
  case "$(_stripped_part)" in *"git reset --hard"*) ;; *) return 1 ;; esac
  case "$(_stripped_part)" in *"git push"*) return 1 ;; esac
}
