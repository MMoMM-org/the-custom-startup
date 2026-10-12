#!/usr/bin/env bash
# scripts/observability/git_ops.sh -- git invocation parsing for git-operation
# recording (spec 021, observability v2, Phase 1, T1.2 and T1.3).
#
# Public functions (pure: no writes, no `git`, no network, no subprocess
# besides the two command substitutions that capture the copied strippers):
#   _git_ops_command <payload>  decodes tool_input.command from a PreToolUse
#                               payload (\" \\ \/ \n \t \r decoded, \uXXXX
#                               kept as six bytes); prints nothing when the key
#                               is missing or the string is unterminated.
#   _git_ops_parse <command>    prints one line per git invocation that is not
#                               read-only:
#                               subcommand TAB action TAB flags TAB overrides
#                               TAB override_first
#                               Names only (CON-13): the subcommand is a git
#                               command name or `?`, the action is from a
#                               closed list, overrides are CLAUDE_ALLOW_*
#                               names, and positionals, paths, URLs, messages
#                               and assignment values are never printed. A
#                               flag's value is not printed when it is glued
#                               to the flag (`-mX` → `-m`, `--o=X` → `--o`),
#                               quoted, or a plain word; but an unquoted
#                               separate value that itself begins with `-` is
#                               read as a flag (`-m --x` → `-m --x`, `-m -x`
#                               → `-m -x`), the names-only trade-off ADR-3
#                               accepts (the SDD has no per-flag value table).
#                               Flags are printed in full; the 256-byte cap is
#                               the writer's job.
#
# Parsing (SDD Runtime View, Complex Logic; ADR-3, ADR-9):
#   heredoc bodies are stripped with the copied function below, then the text
#   is cut into words by _git_ops_mark_words so that a value always stays in
#   one word: a quoted span, a backslash-escaped byte (`my\ dir`) and a
#   parameter expansion `${ … }` are opaque `%` words (`git branch "x"` has a
#   positional); a command or process substitution, `$( … )`, backticks,
#   `<( … )`, `>( … )`, at any depth, is one `%` word in the command around it
#   (`git -C $(pwd) push` → push, `GIT_DIR=$(pwd) git push` → push) and its
#   content is parsed as clauses of its own (`git commit -m "$(git reset)"`
#   → commit and reset). The copied quote stripper decides only the executor
#   predicate. When the stripped text runs a shell on a payload (`bash -c`,
#   `eval`), the executor fallback applies instead: every quote character
#   becomes a space and the records carry flags `(executor)`. In both modes
#   the subcommand is recorded by name only if it is on _GIT_OPS_COMMANDS,
#   else `?` (aliases, unknown and undeterminable names, `git "reset"`,
#   `git $(echo reset)`). Clauses split on && || | ; & and newline; in each,
#   the command position skips openers, assignments and wrappers (env sudo
#   time nice timeout nohup exec command) before looking for `git` or
#   `*/git`. override_first mirrors the guard's first-token rule
#   (tcs-git-helpers lib/override.sh, one leading cd/pushd clause stripped).
#
# Known limits (documented, not silent): `xargs git …`, `find … -exec git …`,
# git run from a script file, git behind `setsid` or another wrapper not
# listed above, git behind `env -C dir` (that value is not skipped) and git
# inside `case … in pattern) git …` are not recognised and record nothing.
# Executor mode is decided for the whole command: one `bash -c` or `eval`
# anywhere puts every clause of it through the fallback. In the
# executor fallback, nested quoting is gone, so any value before the
# subcommand (wrapper option or duration, empty assignment, global option
# other than the value-less ones) makes the subcommand `?` rather than risk a
# value fragment in its place (CON-13); when such a fragment, or one after
# any assignment, then stops the command-position scan, a later git word
# still yields a `?` record (_git_ops_cut_stop). Substitutions in that mode
# are handled only at command position. Name patterns are ASCII letter lists,
# not ranges or classes, so they hold in any locale. override_first belongs to
# the whole command (the guard applies a first-position override to all of
# it); `overrides` to the clause.
#
# COPIED, NOT SOURCED (SDD/ADR-2, CON-12):
#   _git_ops_strip_heredocs, _git_ops_strip_quoted and
#   _git_ops_has_shell_executor are copies of _strip_heredocs, _strip_quoted
#   and _has_shell_executor in
#   plugins/tcs-git-helpers/scripts/lib/pattern_match.sh. They are NOT
#   sourced from there: this bundle runs from $HOME/.claude/observability/
#   without CLAUDE_PLUGIN_ROOT and installs independently of tcs-git-helpers
#   (maintainer ruling, as in observability-setup/lib/drift_check.sh: mirror
#   the contract, not the code). Without the stripping, a `git reset` named
#   in a commit message would be recorded as a git operation.
#
#   Not copied: the guard's raw-substring fallback (_with_normalized_clauses)
#   and its clause splitting policy.
#
#   The two copies are kept equal by
#   plugins/tcs-helper/tests/bats/observability-git-parity.bats, which runs a
#   shared corpus through both and compares the stripped text and the
#   executor decision byte for byte. Change one copy, change the other.
#
# The comments INSIDE the copied functions are verbatim from the guard; their
# references to the dispatcher and _clausify point at tcs-git-helpers, not here.
#
# Sourced by a hook: defines functions and one constant
# (_GIT_OPS_COMMANDS). No output, no external commands,
# no `set -e`/`set -u` at source time; every function is `set -u` safe.
# bash 3.2 compatible.

# _git_ops_strip_quoted <command>
#   Returns <command> with content inside single- and double-quoted segments
#   replaced by spaces (token boundaries preserved). Used to prevent regex
#   patterns whose `.*` would otherwise bridge from the real argv into a
#   quoted message body (e.g. NO_VERIFY matching `-n,` inside `-m "...-n,..."`).
#
#   Scope: applied ONLY where a verb commonly carries a quoted message body
#   (currently just NO_VERIFY's `git commit -m "..."`). Other patterns must
#   keep using raw $CMD — see block-bad-git-ops.sh dispatcher.
#
#   Known limitations (documented; users hit them rarely and have the v2.2.0
#   `CLAUDE_ALLOW_NO_VERIFY=1` inline-override path as escape hatch):
#     - Nested quotes inside command substitution (e.g. "$(printf "x")") may
#       confuse the scanner: the inner `"` is read as closing the outer dq.
#       The heredoc form `"$(cat <<'EOF' …EOF)"` is NOT affected because the
#       outer `"..."` contains no inner `"` characters.
#     - Backslash-escaping inside double quotes is honored (`\"` does not
#       close the dq). Single quotes follow POSIX — no escapes inside.
#
#   bash 3.2 compatible: pure parameter expansion, no associative arrays,
#   no mapfile.
_git_ops_strip_quoted() {
  local cmd="$1"
  local out=""
  local i=0
  local len=${#cmd}
  local state="N"        # N=normal (code), S=single-quoted, D=double-quoted
  local stack=""         # one saved state char per open $( — innermost first
  local ch prev="" nxt
  while [ "$i" -lt "$len" ]; do
    ch="${cmd:$i:1}"
    nxt="${cmd:$((i + 1)):1}"
    case "$state" in
      S)
        if [ "$ch" = "'" ]; then state="N"; fi
        out="${out} "
        ;;
      D)
        # $( ... ) inside a double-quoted string is still CODE. Enter it in
        # normal state so its command is matched, and remember to come back
        # to D — otherwise the substitution's own quotes desync the outer one.
        if [ "$ch" = '$' ] && [ "$nxt" = "(" ]; then
          stack="D${stack}"
          state="N"
          out="${out}  "
          prev="("
          i=$((i + 2))
          continue
        fi
        if [ "$ch" = '"' ] && [ "$prev" != "\\" ]; then state="N"; fi
        out="${out} "
        ;;
      N)
        if [ "$ch" = '$' ] && [ "$nxt" = "(" ]; then
          stack="N${stack}"
          out="${out}  "
          prev="("
          i=$((i + 2))
          continue
        fi
        case "$ch" in
          "'") state="S"; out="${out} " ;;
          '"') state="D"; out="${out} " ;;
          ')')
            if [ -n "$stack" ]; then
              state="${stack:0:1}"
              stack="${stack:1}"
              out="${out} "
            else
              out="${out}${ch}"
            fi
            ;;
          *) out="${out}${ch}" ;;
        esac
        ;;
    esac
    prev="$ch"
    i=$((i + 1))
  done
  printf '%s' "$out"
}

# _git_ops_strip_heredocs <command>
#   Blanks heredoc BODIES, keeping the line that opens them.
#
#   A heredoc body is data on stdin — `git commit -F - <<EOF … EOF` carries a
#   commit message, and a destructive literal described in it is prose, not an
#   instruction. Must run BEFORE _git_ops_strip_quoted: a quoted delimiter (<<'EOF')
#   would otherwise be blanked, leaving a `<<` with nothing to match the
#   terminator against, and the body still in scope.
#
#   Exception, same principle as _clausify's shell-executor guard: when the
#   heredoc feeds a shell (`bash <<EOF`), the body is CODE. Left intact.
#
#   Not stripped: `<<<` here-strings — those are single-line and _git_ops_strip_quoted
#   already handles their quoting.
#
#   bash 3.2 compatible: read loop, no mapfile.
_git_ops_strip_heredocs() {
  local cmd="$1"
  local out="" NL line rest delim="" trimmed
  NL=$'\n'
  while IFS= read -r line; do
    if [ -n "$delim" ]; then
      trimmed="${line#"${line%%[![:space:]]*}"}"
      if [ "$line" = "$delim" ] || [ "$trimmed" = "$delim" ]; then
        delim=""
      fi
      out="${out}${NL}"
      continue
    fi
    out="${out}${line}${NL}"
    case "$line" in
      *"<<"*)
        rest="${line#*<<}"
        # `<<<` is a here-string, not a heredoc.
        case "$rest" in
          "<"*) continue ;;
        esac
        # A heredoc feeding an interpreter carries code; leave it in scope.
        # Named explicitly, not as [a-z]*sh — that also matches the "sh" in
        # `git stash`, which would leave a stash command's heredoc in scope.
        if [[ "$line" =~ (^|[^[:alnum:]_])(sh|bash|zsh|ksh|dash|csh|tcsh|fish|python[0-9.]*|perl|ruby|node|awk|sed|eval)([[:space:]]|$) ]]; then
          continue
        fi
        rest="${rest#-}"
        rest="${rest#"${rest%%[![:space:]]*}"}"
        delim="${rest%%[[:space:]]*}"
        delim="${delim%%[<>|;&]*}"
        delim="${delim//\'/}"
        delim="${delim//\"/}"
        ;;
    esac
  done <<< "$cmd"
  printf '%s' "$out"
}

# _git_ops_has_shell_executor <stripped-command>
#   True (0) iff the command, already reduced by _git_ops_strip_heredocs and
#   _git_ops_strip_quoted, invokes a shell on a payload (`bash -c`, `sh -c`)
#   or `eval`. Called on STRIPPED text only (#213).  Parity-tested against the
#   guard (see header).
_git_ops_has_shell_executor() {
  [[ "$1" =~ (^|[^[:alnum:]_])[a-z]*sh[[:space:]]+-c([[:space:]]|$) ]] \
    || [[ "$1" =~ (^|[^[:alnum:]_])eval([[:space:]]|$) ]]
}

# _GIT_OPS_COMMANDS -- the closed list of git's own command names. In both
# modes the subcommand is recorded by name only if it is on this list, else
# `?` (unknown, alias, undeterminable; SDD data model, 2026-10-12): whatever
# syntax splits a value into words, no word other than a git command name can
# reach the record (CON-13).
# Source: `git help -a` (git version 2.50.1, Apple Git-155), sections "Main
# Porcelain", "Ancillary", "Interacting with Others" and "Low-level"; the
# interface/format guides and external commands are excluded; plus `lfs`.
# A space-delimited string: membership is one glob test, no loop, no fork (the
# idiom of logwrite.sh's _OBSERVABILITY_DETAIL_ONLY_FIELDS).
_GIT_OPS_COMMANDS=" add am annotate apply archimport archive backfill bisect blame branch bugreport bundle cat-file check-attr check-ignore check-mailmap check-ref-format checkout checkout-index cherry cherry-pick citool clean clone column commit commit-graph commit-tree config count-objects credential credential-cache credential-store cvsexportcommit cvsimport cvsserver daemon describe diagnose diff diff-files diff-index diff-pairs diff-tree difftool fast-export fast-import fetch fetch-pack filter-branch fmt-merge-msg for-each-ref for-each-repo format-patch fsck gc get-tar-commit-id gitk gitweb grep gui hash-object help hook http-backend imap-send index-pack init instaweb interpret-trailers log ls-files ls-remote ls-tree mailinfo mailsplit maintenance merge merge-base merge-file merge-index merge-one-file merge-tree mergetool mktag mktree multi-pack-index mv name-rev notes p4 pack-objects pack-redundant pack-refs patch-id prune prune-packed pull push quiltimport range-diff read-tree rebase reflog refs remote repack replace replay request-pull rerere reset restore rev-list rev-parse revert rm scalar send-email send-pack sh-i18n sh-setup shortlog show show-branch show-index show-ref sparse-checkout stash status stripspace submodule svn switch symbolic-ref tag unpack-file unpack-objects update-index update-ref update-server-info var verify-commit verify-pack verify-tag version whatchanged worktree write-tree lfs "

# _GIT_OPS_MAX_BYTES -- the parse cap (SDD Complex Logic, Size cap). A decoded
# command longer than this is not parsed: _git_ops_parse prints one value-free
# `? (oversize)` record when it holds a free-standing `git` word, else
# nothing. 16384 is a first setting; T1.5 re-measures it once the copied
# strippers are linear. Measured with ${#cmd}, which counts bytes under the
# hook's LC_ALL=C (CON-3) and characters in a UTF-8 locale (never more than
# the bytes, so the cap can only be reached later, by at most the byte width).
_GIT_OPS_MAX_BYTES=16384

# ---------------------------------------------------------------------------
# Parser (T1.3). Helpers below share state with their caller through bash's
# dynamic scoping: each one's comment names the caller locals it reads and
# writes. This keeps the hook path free of per-clause command substitutions.
# Every step below the cap is linear in the input apart from the copied
# strippers above (made linear in T1.5).
# ---------------------------------------------------------------------------

# _git_ops_command <payload>
#   Prints the decoded value of the first `"command":"` key in <payload>.
#   The key is matched with its leading quote, so an escaped occurrence
#   (`\"command\":\"` inside another string) is not a match. Nothing is printed
#   when the key is missing or the string never closes (CON-9).
#   One pass: the rest of the payload is split once on `\` (read -a), so each
#   part after the first starts with an escaped byte; the first unescaped `"`
#   in a literal stretch ends the string. Pieces are collected in an array and
#   printed once, so no string is re-sliced or re-copied per escape.
_git_ops_command() {
  local payload="${1-}" rest p esc first_part=1 lit_only=0 k=0
  local -a parts out
  case "$payload" in
    *'"command":"'*) ;;
    *) return 0 ;;
  esac
  rest="${payload#*\"command\":\"}"
  # shellcheck disable=SC2141 # the backslash IS the separator here
  IFS=$'\\' read -r -d '' -a parts <<< "$rest" || :
  out=()
  # Iterated with for, appended at a running index: bash 3.2 arrays are lists,
  # so an indexed read inside the loop would make the pass quadratic.
  for p in ${parts[@]+"${parts[@]}"}; do
    if [ "$first_part" -eq 1 ]; then
      first_part=0
    else
      if [ "$lit_only" -eq 1 ]; then
        # This part follows an escaped backslash: no escape at its start.
        lit_only=0
      elif [ -z "$p" ]; then
        # `\\`: the escaped byte is the next backslash itself.
        out[k]=$'\\'
        k=$((k + 1))
        lit_only=1
        continue
      else
        esc="${p:0:1}"
        p="${p:1}"
        case "$esc" in
          '"') out[k]='"' ;;
          /) out[k]='/' ;;
          n) out[k]=$'\n' ;;
          t) out[k]=$'\t' ;;
          r) out[k]=$'\r' ;;
          *) out[k]="\\${esc}" ;;
        esac
        k=$((k + 1))
      fi
    fi
    case "$p" in
      *'"'*)
        out[k]="${p%%\"*}"
        printf '%s' "${out[@]}"
        return 0
        ;;
    esac
    out[k]="$p"
    k=$((k + 1))
  done
  # No closing quote: the string is unterminated.
  return 0
}

# _git_ops_unquote_git   (_git_ops_parse locals: reads and writes h)
#   A word whose shell-unquoted form is exactly `git` or ends in `/git` is the
#   invocation, however it is quoted: `\git`, `'git'`, `"git"`, `"/usr/bin/git"`
#   (the usual way round an alias). Their quotes are removed before the words
#   are marked, so the word reads as `git`. Inside a quoted message the same
#   rewrite only drops quote characters around the word, which leaves it in
#   the message. A match whose quotes differ (`"git'`) is left as it is and
#   the scan continues after it.
_git_ops_unquote_git() {
  local re m pre rest done_part=""
  h="${h//\\git/git}"
  re='(^|[[:space:];&|(`])(['"'"'"])([^'"'"'"[:space:]]*/)?git(['"'"'"])([[:space:];&|)`]|$)'
  rest="$h"
  while [[ "$rest" =~ $re ]]; do
    m="${BASH_REMATCH[0]}"
    pre="${rest%%"$m"*}"
    if [ "${BASH_REMATCH[2]}" = "${BASH_REMATCH[4]}" ]; then
      done_part="${done_part}${pre}${BASH_REMATCH[1]}${BASH_REMATCH[3]}git${BASH_REMATCH[5]}"
    else
      done_part="${done_part}${pre}${m}"
    fi
    rest="${rest#*"$m"}"
  done
  h="${done_part}${rest}"
}

# _git_ops_mark_words   (_git_ops_parse locals: reads h, NL; writes text)
#   Rewrites the heredoc-stripped command h into words for clause parsing.
#   States: N code, S single-quoted, D double-quoted (`$(` opens code in N and
#   D, as in _git_ops_strip_quoted). Every rule below keeps a value inside
#   one word, so a value can never be split into a word that reads as a name:
#     - every byte of a quoted span, quotes included, becomes `%`: one opaque
#       word that can be counted but never matches a name;
#     - a backslash in N or D makes the next byte part of the current word
#       (both become `%`; `my\ dir` is one word); backslash-newline is a line
#       continuation and disappears;
#     - a parameter expansion `${ … }` in N or D (braces, quotes and escapes
#       inside included) becomes `%` bytes, one opaque word;
#     - a command substitution `$( … )` or `` ` … ` `` (in N or D) and a
#       process substitution `<( … )` / `>( … )` (in N) is executed code AND
#       one argument of the command around it: in its enclosing text it is a
#       single `%`; its content is appended to text after a newline, as
#       clauses of its own. Nesting follows the same rules at every depth; an
#       unclosed one is closed at the end of input.
#   Outside these every byte is kept.
#   Linear: each step consumes the run up to the next byte that matters in the
#   current state (`'` in S; `"`, `\`, `$`, backtick in D; those plus `'`,
#   `(`, `)`, `<`, `>` in N) and appends it, or that many `%` from a pad built
#   once, in one append.
# shellcheck disable=SC2016,SC2295 # literal $( ${ patterns; spec vars are globs
_git_ops_mark_words() {
  local rest="$h" run c nxt state="N" d=0 states="" kinds="" subs="" pad="%"
  local nspec='['"'"'"\\$`()<>]*' dspec='["\\$`]*'
  local -a buf
  case "$h" in
    *"'"* | *'"'* | *'`'* | *'$('* | *'${'* | *\\* | *'<('* | *'>('*) ;;
    *)
      text="$h"
      return 0
      ;;
  esac
  while [ "${#pad}" -lt "${#h}" ]; do pad="${pad}${pad}"; done
  buf[0]=""
  while [ -n "$rest" ]; do
    case "$state" in
      S)
        run="${rest%%\'*}"
        buf[d]="${buf[d]}${pad:0:${#run}}"
        rest="${rest:${#run}}"
        if [ -z "$rest" ]; then break; fi
        buf[d]="${buf[d]}%"
        rest="${rest:1}"
        state="N"
        continue
        ;;
      D)
        run="${rest%%$dspec}"
        buf[d]="${buf[d]}${pad:0:${#run}}"
        rest="${rest:${#run}}"
        if [ -z "$rest" ]; then break; fi
        if [ "${rest:0:1}" = '"' ]; then
          buf[d]="${buf[d]}%"
          rest="${rest:1}"
          state="N"
          continue
        fi
        ;;
      N)
        run="${rest%%$nspec}"
        buf[d]="${buf[d]}${run}"
        rest="${rest:${#run}}"
        if [ -z "$rest" ]; then break; fi
        ;;
    esac
    # At a byte that matters, in N or D.
    c="${rest:0:1}"
    nxt="${rest:1:1}"
    case "$c" in
      \\)
        if [ "$nxt" = "$NL" ]; then
          rest="${rest:2}"
        elif [ -z "$nxt" ]; then
          buf[d]="${buf[d]}%"
          rest=""
        else
          buf[d]="${buf[d]}%%"
          rest="${rest:2}"
        fi
        continue
        ;;
      '$')
        case "$nxt" in
          '(')
            _git_ops_open_subst P
            rest="${rest:2}"
            ;;
          '{') _git_ops_mark_braced ;;
          *)
            if [ "$state" = "D" ]; then buf[d]="${buf[d]}%"; else buf[d]="${buf[d]}\$"; fi
            rest="${rest:1}"
            ;;
        esac
        continue
        ;;
      '`')
        if [ "$state" = "N" ] && [ "${kinds:0:1}" = "B" ]; then
          _git_ops_close_subst
        else
          _git_ops_open_subst B
        fi
        rest="${rest:1}"
        continue
        ;;
    esac
    # N only from here on.
    case "$c" in
      "'")
        state="S"
        buf[d]="${buf[d]}%"
        ;;
      '"')
        state="D"
        buf[d]="${buf[d]}%"
        ;;
      '<' | '>')
        if [ "$nxt" = "(" ]; then
          _git_ops_open_subst P
          rest="${rest:2}"
          continue
        fi
        buf[d]="${buf[d]}${c}"
        ;;
      ')')
        if [ "${kinds:0:1}" = "P" ]; then
          _git_ops_close_subst
        else
          buf[d]="${buf[d]})"
        fi
        ;;
      *) buf[d]="${buf[d]}${c}" ;;
    esac
    rest="${rest:1}"
  done
  while [ "$d" -gt 0 ]; do _git_ops_close_subst; done
  text="${buf[0]}${subs}"
}

# _git_ops_mark_braced   (_git_ops_mark_words locals: reads pad; writes rest,
#   buf[d])
#   rest starts with `${`. Consumes through the matching `}` (nested braces,
#   quoted segments and backslash escapes inside do not end it; an unclosed
#   one runs to the end of input) and appends one `%` per character, a run at
#   a time.
# shellcheck disable=SC2295 # the spec variables are glob patterns
_git_ops_mark_braced() {
  local depth=0 c q="" run bspec=$'[{}\\\\\'"]*' dqspec='["\\]*'
  buf[d]="${buf[d]}%"
  rest="${rest:1}"
  while [ -n "$rest" ]; do
    if [ "$q" = "'" ]; then
      run="${rest%%\'*}"
    elif [ -n "$q" ]; then
      run="${rest%%$dqspec}"
    else
      run="${rest%%$bspec}"
    fi
    buf[d]="${buf[d]}${pad:0:${#run}}"
    rest="${rest:${#run}}"
    if [ -z "$rest" ]; then return 0; fi
    c="${rest:0:1}"
    if [ "$c" = "\\" ]; then
      buf[d]="${buf[d]}%%"
      rest="${rest:2}"
      continue
    fi
    buf[d]="${buf[d]}%"
    rest="${rest:1}"
    if [ -n "$q" ]; then
      q=""
      continue
    fi
    case "$c" in
      "'" | '"') q="$c" ;;
      '{') depth=$((depth + 1)) ;;
      '}')
        depth=$((depth - 1))
        if [ "$depth" -eq 0 ]; then return 0; fi
        ;;
    esac
  done
}

# _git_ops_open_subst <P|B>   (_git_ops_mark_words locals: writes buf, d,
#   states, kinds, state)
_git_ops_open_subst() {
  buf[d]="${buf[d]}%"
  states="${state}${states}"
  kinds="${1}${kinds}"
  d=$((d + 1))
  buf[d]=""
  state="N"
}

# _git_ops_close_subst   (_git_ops_mark_words locals: reads NL; writes buf, d,
#   states, kinds, state, subs)
_git_ops_close_subst() {
  subs="${subs}${NL}${buf[d]}"
  d=$((d - 1))
  state="${states:0:1}"
  states="${states:1}"
  kinds="${kinds:1}"
}

# _git_ops_trim_closers   (caller local: reads and writes tok)
#   Drops trailing backticks and parentheses: `(git reset)`, `` `git pull` ``.
_git_ops_trim_closers() {
  while :; do
    case "$tok" in
      *'`' | *')') tok="${tok%?}" ;;
      *) return 0 ;;
    esac
  done
}

# _git_ops_emit <subcommand> <action> <flags>
#   (_git_ops_parse_clause locals: reads ovr; _git_ops_parse: reads first)
#   Prints one record line.
_git_ops_emit() {
  printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "${ovr# }" "$first"
}

# _git_ops_cut_stop   (_git_ops_parse_clause locals: reads t, n, i, ex, cut,
#   assigned)
#   Command-position scanning stopped on a word it does not recognise. In the
#   executor fallback after a cut or any assignment, that word may be a
#   fragment of a quoted value (`bash -c "A='x y' git push"` → `A= x y git
#   push`, `A=x' 'y` → `A=x  y`): if a git word follows, the invocation is
#   recorded as `?` rather than lost (fail closed, never a value). Elsewhere
#   the clause simply has no git invocation.
_git_ops_cut_stop() {
  local j
  if [ "$ex" -ne 1 ]; then return 0; fi
  if [ "$cut" -ne 1 ] && [ "$assigned" -ne 1 ]; then return 0; fi
  j=$((i + 1))
  while [ "$j" -lt "$n" ]; do
    case "${t[$j]}" in
      git | */git)
        _git_ops_emit '?' '' '(executor)'
        return 0
        ;;
    esac
    j=$((j + 1))
  done
}

# _git_ops_skip_wrapper_options <value-taking options> [lookup]
#   (_git_ops_parse_clause locals: reads t, n, ex; writes i, cut)
#   i is just past a wrapper word. Skips its options; an option named in the
#   space-separated list also takes the next word. Every option sets cut in
#   the executor fallback (its value may have been quoted and split). With
#   `lookup`, an option containing v or V (`command -v`) makes the clause a
#   lookup: returns 1, no invocation.
_git_ops_skip_wrapper_options() {
  local takes=" $1 " lookup="${2-}" o
  while [ "$i" -lt "$n" ]; do
    o="${t[$i]}"
    case "$o" in
      -*) ;;
      *) return 0 ;;
    esac
    if [ -n "$lookup" ]; then
      case "$o" in -*[vV]*) return 1 ;; esac
    fi
    cut=$ex
    case "$takes" in
      *" $o "*) i=$((i + 2)) ;;
      *) i=$((i + 1)) ;;
    esac
  done
  return 0
}

# _git_ops_command_position   (_git_ops_parse_clause locals: reads t, n, ex,
#   mode; writes i, tok, cut, assigned, ovr, and t[i] for a substitution
#   value)
#   Skips openers, leading redirections, assignments and wrappers. Returns 0
#   with t[i] the git word, or 1 when the clause has no git invocation (after
#   _git_ops_cut_stop has had its say).
# shellcheck disable=SC2016 # '$(' patterns are literal openers
_git_ops_command_position() {
  local name val
  while [ "$i" -lt "$n" ]; do
    tok="${t[$i]}"
    # `$(` and a leading backtick survive only in the executor fallback's
    # text; in normal mode _git_ops_mark_words has turned them into `%`. A
    # leading `(` (subshell) can appear in both.
    while :; do
      case "$tok" in
        '$('*) tok="${tok#??}" ;;
        '`'* | '('*) tok="${tok#?}" ;;
        *) break ;;
      esac
    done
    case "$tok" in
      '' | '{' | '!' | if | then | elif | else | while | until | do)
        i=$((i + 1))
        ;;
      git | */git) return 0 ;;
      [0123456789]'<'* | [0123456789]'>'* | '<'* | '>'*)
        # A leading redirection; a bare operator takes the next word.
        val="${tok#[0123456789]}"
        val="${val//[<>-]/}"
        if [ -z "$val" ]; then i=$((i + 2)); else i=$((i + 1)); fi
        ;;
      [abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_]*=*)
        name="${tok%%=*}"
        case "$name" in
          *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_]*)
            _git_ops_cut_stop
            return 1
            ;;
        esac
        val="${tok#*=}"
        if [ -z "$val" ]; then cut=$ex; fi
        assigned=1
        case "$name" in
          CLAUDE_ALLOW_?*)
            case "${name#CLAUDE_ALLOW_}" in
              *[!ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_]*) ;;
              *) if [ "$val" = "1" ]; then ovr="${ovr} ${name}"; fi ;;
            esac
            ;;
        esac
        case "$val" in
          '`'* | '$('*) t[i]="$val" ;; # the value is a command: examine it
          *) i=$((i + 1)) ;;
        esac
        ;;
      env)
        i=$((i + 1))
        _git_ops_skip_wrapper_options "-u --unset"
        ;;
      sudo)
        i=$((i + 1))
        _git_ops_skip_wrapper_options "-u -g -h -p -C -D -r -t -U"
        ;;
      time)
        i=$((i + 1))
        _git_ops_skip_wrapper_options ""
        ;;
      nice)
        i=$((i + 1))
        _git_ops_skip_wrapper_options "-n"
        ;;
      timeout)
        i=$((i + 1))
        _git_ops_skip_wrapper_options "-s -k"
        i=$((i + 1)) # the duration
        cut=$ex
        ;;
      nohup | exec)
        i=$((i + 1))
        ;;
      command)
        i=$((i + 1))
        _git_ops_skip_wrapper_options "" lookup || return 1
        ;;
      eval)
        if [ "$mode" != "executor" ]; then return 1; fi
        i=$((i + 1))
        ;;
      sh | [abcdefghijklmnopqrstuvwxyz]*sh | */sh | */[abcdefghijklmnopqrstuvwxyz]*sh)
        # Only in the executor fallback, where `bash -c 'git …'` has lost its
        # quotes and the payload's words follow the shell's options. These
        # options do not cut: `-c` precedes every payload.
        if [ "$mode" != "executor" ]; then return 1; fi
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      *)
        _git_ops_cut_stop
        return 1
        ;;
    esac
  done
  return 1
}

# _git_ops_global_options   (_git_ops_parse_clause locals: reads t, n, ex;
#   writes i, cut)
#   i is just past `git`. Skips global options. Returns 0 with t[i] the
#   subcommand word, 1 when there is none (bare `git`, --version, --help).
#   In the executor fallback every option except the value-less ones makes
#   the subcommand `?`: a separate or joined value may have been quoted and
#   split by quote removal (`-C 'my dir'` → `-C  my dir`, `--git-dir='a b'`
#   → `--git-dir= a b`).
_git_ops_global_options() {
  while [ "$i" -lt "$n" ]; do
    case "${t[$i]}" in
      --version | --help)
        # After a cut in the executor fallback this may be a value fragment
        # of the global option before it: keep the record, as `?`.
        if [ "$ex" -eq 1 ] && [ "$cut" -eq 1 ]; then
          _git_ops_emit '?' '' '(executor)'
        fi
        return 1
        ;;
      -C | -c | --git-dir | --work-tree | --namespace | --config-env | --super-prefix | --exec-path)
        i=$((i + 2))
        cut=$ex
        ;;
      -p | -P | --paginate | --no-pager | --bare | --no-replace-objects | --literal-pathspecs | \
        --glob-pathspecs | --noglob-pathspecs | --icase-pathspecs | --no-optional-locks | --no-advice | \
        --no-lazy-fetch)
        i=$((i + 1))
        ;;
      -*)
        i=$((i + 1))
        cut=$ex
        ;;
      *) return 0 ;;
    esac
  done
  return 1
}

# _git_ops_read_subcommand   (_git_ops_parse_clause locals: reads t, i, cut;
#   writes tok, sub)
#   The subcommand is a name from _GIT_OPS_COMMANDS or `?` (closed list in
#   both modes, SDD data model 2026-10-12); after a cut it is always `?`.
_git_ops_read_subcommand() {
  tok="${t[$i]}"
  _git_ops_trim_closers
  sub="$tok"
  if [ "$cut" -eq 1 ]; then sub='?'; fi
  case "$_GIT_OPS_COMMANDS" in
    *" $sub "*) ;;
    *) sub='?' ;;
  esac
  case "$sub" in
    [abcdefghijklmnopqrstuvwxyz]*)
      case "$sub" in
        *[!abcdefghijklmnopqrstuvwxyz0123456789-]*) sub='?' ;;
      esac
      ;;
    *) sub='?' ;;
  esac
}

# _git_ops_scan_arguments   (_git_ops_parse_clause locals: reads t, n, sub;
#   writes i, tok, flags, npos, pos1, listing)
#   i is just past the subcommand. Collects flag names (ADR-3) and counts
#   positionals; positionals are never printed: the first one is compared
#   against the read-only forms and the ACTIONS list only.
_git_ops_scan_arguments() {
  local ended=0 skip=0 first_word="${t[$i]-}" name val letters
  while [ "$i" -lt "$n" ]; do
    tok="${t[$i]}"
    i=$((i + 1))
    if [ "$skip" -eq 1 ]; then
      skip=0
      continue
    fi
    _git_ops_trim_closers
    if [ "$ended" -eq 1 ]; then
      npos=$((npos + 1))
      continue
    fi
    case "$tok" in
      '') ;;
      '<'* | '>'* | [0123456789]'<'* | [0123456789]'>'*)
        # A redirection. Bare operator: its target is the next word.
        val="${tok#[0123456789]}"
        val="${val//[<>-]/}"
        if [ -z "$val" ]; then skip=1; fi
        ;;
      --)
        flags="${flags} --"
        ended=1
        listing=0
        ;;
      --?*)
        name="${tok%%=*}"
        flags="${flags} ${name}"
        case "$name" in
          --all | --remotes | --list | --verbose | --show-current | --contains | \
            --no-contains | --merged | --no-merged | --points-at | --sort | --format | \
            --column | --no-column | --color | --no-color) ;;
          *) listing=0 ;;
        esac
        ;;
      -?*)
        # ADR-3: a short flag is recorded as its first letter only, so a
        # value glued to it (-m<msg>, -S<key>) never reaches the record.
        flags="${flags} -${tok:1:1}"
        letters="${tok#-}"
        case "$letters" in
          *[!arlv]*) listing=0 ;;
        esac
        ;;
      *)
        npos=$((npos + 1))
        if [ "$npos" -eq 1 ]; then pos1="$tok"; fi
        ;;
    esac
  done
  flags="${flags# }"

  # git stash <verb> [options]: the verb is the word right after `stash`; when
  # that word is an option (or absent) the verb is an implicit push, so a
  # value such as `-m list` is never read as the verb.
  if [ "$sub" = "stash" ]; then
    case "$first_word" in
      '' | -*) pos1="" ;;
    esac
  fi
}

# _git_ops_is_read_only   (_git_ops_parse_clause locals: reads sub, flags,
#   npos, pos1, listing)
#   Returns 0 when the invocation is read-only (ADR-9, closed list; anything
#   not listed here, `?` included, is recorded).
_git_ops_is_read_only() {
  case "$sub" in
    status | log | diff | show | rev-parse | rev-list | ls-files | ls-tree | ls-remote | \
      cat-file | blame | describe | shortlog | grep | for-each-ref | show-ref | name-rev | \
      merge-base | help | version | var | count-objects | check-ignore | check-attr | \
      whatchanged | cherry | verify-commit | verify-tag | fsck | archive)
      return 0
      ;;
    branch)
      if [ "$npos" -eq 0 ] && [ "$listing" -eq 1 ]; then return 0; fi
      ;;
    tag)
      if [ "$npos" -eq 0 ]; then return 0; fi
      case " $flags " in *" -l "* | *" --list "*) return 0 ;; esac
      ;;
    stash | notes)
      case "$pos1" in list | show) return 0 ;; esac
      ;;
    remote)
      if [ "$npos" -eq 0 ]; then return 0; fi
      case "$pos1" in show | get-url) return 0 ;; esac
      ;;
    config)
      case " $flags " in
        *" --get "* | *" --get-all "* | *" --get-regexp "* | *" --list "* | *" -l "*) return 0 ;;
      esac
      case "$pos1" in get | list) return 0 ;; esac
      ;;
    worktree)
      if [ "$pos1" = "list" ]; then return 0; fi
      ;;
    reflog)
      if [ "$npos" -eq 0 ] || [ "$pos1" = "show" ]; then return 0; fi
      ;;
    submodule)
      if [ "$npos" -eq 0 ] || [ "$pos1" = "status" ]; then return 0; fi
      ;;
  esac
  return 1
}

# _git_ops_read_action   (_git_ops_parse_clause locals: reads sub, pos1;
#   writes action)
#   ACTIONS (closed): the first positional is the action only if listed.
_git_ops_read_action() {
  action=""
  case "$sub" in
    stash)
      case "$pos1" in push | pop | apply | drop | clear | branch | create | store | save | list | show) action="$pos1" ;; esac
      ;;
    worktree)
      case "$pos1" in add | remove | move | prune | lock | unlock | repair | list) action="$pos1" ;; esac
      ;;
    remote)
      case "$pos1" in add | remove | rm | rename | set-url | set-head | set-branches | prune | update | show | get-url) action="$pos1" ;; esac
      ;;
    reflog)
      case "$pos1" in expire | delete | show) action="$pos1" ;; esac
      ;;
    submodule)
      case "$pos1" in add | deinit | update | init | sync | set-url | set-branch | absorbgitdirs | status | foreach) action="$pos1" ;; esac
      ;;
    notes)
      case "$pos1" in add | append | copy | edit | merge | remove | prune | list | show) action="$pos1" ;; esac
      ;;
    bisect)
      case "$pos1" in start | good | bad | new | old | skip | reset | run) action="$pos1" ;; esac
      ;;
    sparse-checkout)
      case "$pos1" in init | set | add | reapply | disable | list) action="$pos1" ;; esac
      ;;
    lfs)
      case "$pos1" in install | uninstall | track | untrack | push | pull | fetch | migrate | prune) action="$pos1" ;; esac
      ;;
  esac
}

# _git_ops_parse_clause <clause>
#   (_git_ops_parse locals: reads mode, first)
#   Prints the record for the clause's git invocation, if it has one and it is
#   not read-only. Word splitting relies on the caller's IFS and noglob.
#   The steps are helpers sharing this function's locals: command position,
#   global options, subcommand, arguments, read-only predicate, action.
_git_ops_parse_clause() {
  local -a t
  # shellcheck disable=SC2206 # deliberate word splitting; caller set noglob
  t=($1)
  local n=${#t[@]} i=0 tok ovr=""
  if [ "$n" -eq 0 ]; then return 0; fi

  # Executor fallback only: an option value or an assignment value may have
  # been a quoted multi-word string whose fragments now stand where the
  # subcommand is read (`bash -c "git -C 'my dir' reset"`). So every wrapper
  # option, the timeout duration, an emptied assignment and every global option
  # but the value-less ones set cut, and cut makes the subcommand `?` (CON-13).
  # ex is 1 in that mode, so `cut=$ex` is a no-op elsewhere.
  local ex=0 cut=0 assigned=0
  if [ "$mode" = "executor" ]; then ex=1; fi

  _git_ops_command_position || return 0
  i=$((i + 1))
  _git_ops_global_options || return 0

  local sub flags="" npos=0 pos1="" listing=1 action
  _git_ops_read_subcommand
  i=$((i + 1))
  _git_ops_scan_arguments
  if _git_ops_is_read_only; then return 0; fi
  _git_ops_read_action

  # Executor fallback: the payload's own quoting is gone, so a word from a
  # message could look like a flag. Flag names are not trusted there.
  if [ "$ex" -eq 1 ]; then flags="(executor)"; fi

  _git_ops_emit "$sub" "$action" "$flags"
}

# _git_ops_parse <decoded command>
#   Prints zero or more records (see header). Always returns 0.
_git_ops_parse() {
  local cmd="${1-}"
  case "$cmd" in
    *git*) ;;
    *) return 0 ;;
  esac

  # Size cap: above it, no parse; one value-free marker record when a
  # free-standing `git` word is present (SDD Complex Logic, Size cap).
  if [ "${#cmd}" -gt "$_GIT_OPS_MAX_BYTES" ]; then
    local oversize_re='(^|[[:space:];&|(`])git([[:space:]]|$)'
    if [[ "$cmd" =~ $oversize_re ]]; then
      printf '%s\t%s\t%s\t%s\t%s\n' '?' '' '(oversize)' '' ''
    fi
    return 0
  fi

  local NL=$'\n' h q text mode="normal" first="" scan
  local cd_re='^[[:space:]]*(cd|pushd)[[:space:]]+[^&;]*(&&|;)[[:space:]]*'
  local ovr_re='^(CLAUDE_ALLOW_[ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_]+)=1[[:space:]]'

  # The guard's first-token rule (lib/override.sh), on the command as typed:
  # newlines read as `;`, one leading cd/pushd clause stripped, then the
  # override must be the very first word. The guard then applies it to the
  # whole command, so override_first goes on every record of the command,
  # while `overrides` stays per clause.
  scan="${cmd//$NL/;}"
  if [[ "$scan" =~ $cd_re ]]; then scan="${scan:${#BASH_REMATCH[0]}}"; fi
  if [[ "$scan" =~ $ovr_re ]]; then first="${BASH_REMATCH[1]}"; fi

  h="$(_git_ops_strip_heredocs "$cmd")"
  q="$(_git_ops_strip_quoted "$h")"
  if _git_ops_has_shell_executor "$q"; then
    mode="executor"
    text="${h//\'/ }"
    text="${text//\"/ }"
  else
    _git_ops_unquote_git
    _git_ops_mark_words
  fi

  # `2>&1` and `&>f` are redirections, not the `&` separator.
  # bash 3.2 keeps quotes in a quoted replacement inside "…", so the
  # replacements come from variables.
  local gt_sp='> ' sp_gt=' >'
  text="${text//'>&'/$gt_sp}"
  text="${text//'&>'/$sp_gt}"
  text="${text//'&&'/$NL}"
  text="${text//'||'/$NL}"
  text="${text//'|'/$NL}"
  text="${text//';'/$NL}"
  text="${text//'&'/$NL}"

  local had_noglob=0 clause
  local -a clauses
  case "$-" in *f*) had_noglob=1 ;; esac
  set -f
  # One split into clauses (read -a on newline), not a re-slice per clause.
  IFS="$NL" read -r -d '' -a clauses <<< "$text" || :
  local IFS=$' \t'
  for clause in ${clauses[@]+"${clauses[@]}"}; do
    _git_ops_parse_clause "$clause"
  done
  if [ "$had_noglob" -eq 0 ]; then set +f; fi
  return 0
}
