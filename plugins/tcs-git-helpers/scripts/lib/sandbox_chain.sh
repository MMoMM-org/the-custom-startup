#!/bin/bash
# tcs-git-helpers: v2.5.0
# scripts/lib/sandbox_chain.sh — helpers for SANDBOX_CHAINED_GIT (#311).
#
# With the sandbox settings template applied (#303), a git command that
# writes .git/config runs outside the Bash sandbox only when the Bash call IS
# that command: every part of a chained call must match an excludedCommands
# entry, and a `VAR=1` prefix stops the match too (verified on macOS). Run
# chained, the command stays sandboxed, the config write is denied, and git
# still exits 0 -- `git push -u` pushes and sets no upstream.
#
# Functions (all return 0 = yes, 1 = no; none writes stdout):
#   _sc_is_bare_git <cmd>           the call is one plain `git <sub> …`
#   _sc_branch_create_tracks <norm> a normalised `checkout -b`/`switch -c`
#                                   clause would set tracking
#   _sc_sandbox_excludes <entry>…   the loaded settings exclude one of the
#                                   given commands and do not disable the
#                                   sandbox
#
# Requires pattern_match.sh (_strip_heredocs, _strip_quoted). bash 3.2.
# Fail-open: anything unreadable answers "no", so the hook allows.

# _sc_is_bare_git <cmd>
#   True when the whole call, quoted text blanked, is a single `git` command
#   with the subcommand right after `git`: no separator, pipe, redirect,
#   substitution or newline, no leading `cd`/`VAR=` and no global option
#   (`git -C <dir> push` does not match `git push *`).
_sc_is_bare_git() {
  local s first second
  s="$(_strip_quoted "$(_strip_heredocs "$1")")"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  # shellcheck disable=SC2016  # a literal "$(" is the pattern
  case "$s" in
    *$'\n'*|*';'*|*'&'*|*'|'*|*'<'*|*'>'*|*'`'*|*'$('*) return 1 ;;
  esac
  read -r first second _ <<< "$s"
  [ "$first" = "git" ] || return 1
  case "$second" in
    ""|-*) return 1 ;;
  esac
  return 0
}

# _sc_branch_create_tracks <normalised clause>
#   `git checkout -b <new> [<start>]` / `git switch -c <new> [<start>]` sets
#   tracking -- and so writes .git/config -- with --track/-t, or when <start>
#   is a remote-tracking branch and branch.autoSetupMerge is not false
#   (`always` tracks any start point). --no-track never does. Run with $PWD
#   at the target repository.
_sc_branch_create_tracks() {
  local -a toks
  local t i=0 n seen_flag=0 new="" start="" track="" setup
  read -ra toks <<< "$1"
  n=${#toks[@]}
  while [ "$i" -lt "$n" ]; do
    t="${toks[$i]}"
    i=$((i + 1))
    if [ "$seen_flag" = 0 ]; then
      case "$t" in -b|-c) seen_flag=1 ;; esac
      continue
    fi
    case "$t" in
      --no-track) track=no ;;
      -t|--track|--track=*) track=yes ;;
      --) ;;
      -*) ;;
      *)
        if [ -z "$new" ]; then new="$t"
        elif [ -z "$start" ]; then start="$t"
        fi ;;
    esac
  done
  [ "$track" = "no" ] && return 1
  [ "$track" = "yes" ] && return 0
  [ -n "$start" ] || return 1
  setup="$(git config --get branch.autoSetupMerge 2>/dev/null || true)"
  case "$setup" in
    false) return 1 ;;
    always) return 0 ;;
  esac
  git show-ref -q --verify "refs/remotes/$start" 2>/dev/null
}

# _sc_sandbox_excludes <entry>…
#   True when user, project or local settings list one of <entry> in
#   sandbox.excludedCommands, and the most specific sandbox.enabled among
#   them is not false. Without the exclusion, running the command alone
#   would not help either, so there is nothing to tell Claude.
_sc_sandbox_excludes() {
  local root list want
  local -a files=()
  command -v jq >/dev/null 2>&1 || return 1
  root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
  [ -f "$HOME/.claude/settings.json" ] && files+=("$HOME/.claude/settings.json")
  if [ -n "$root" ]; then
    [ -f "$root/.claude/settings.json" ] && files+=("$root/.claude/settings.json")
    [ -f "$root/.claude/settings.local.json" ] && files+=("$root/.claude/settings.local.json")
  fi
  [ "${#files[@]}" -gt 0 ] || return 1
  # Files in precedence order, so the last non-null sandbox.enabled wins.
  list="$(jq -rs '
    ([.[] | .sandbox.enabled? | select(. != null)] | last) as $on
    | if $on == false then empty
      else [.[] | .sandbox.excludedCommands? // [] | .[]?] | unique | .[]
      end' "${files[@]}" 2>/dev/null)" || return 1
  [ -n "$list" ] || return 1
  for want in "$@"; do
    printf '%s\n' "$list" | grep -qxF -- "$want" && return 0
  done
  return 1
}
