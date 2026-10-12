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
# Sourced by a hook: defines functions and two constants (_GIT_OPS_COMMANDS,
# _GIT_OPS_MAX_BYTES). No output, no external commands, no `set -e`/`set -u`
# at source time; every function is `set -u` safe. bash 3.2 compatible.
#
# Locale: _git_ops_command and _git_ops_parse set `local LC_ALL=C` for
# themselves and every helper they call (byte offsets and byte lengths, which
# the linear walks and the byte cap need), restored on return. The hook
# adapter therefore does not have to source logwrite.sh (which exports
# LC_ALL=C) first. The ASCII letter lists make name matching the same in any
# locale.

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
#       Only the ONE character before the `"` is looked at: `"\\"` stays open.
#
#   Linear (spec 021 T1.5). The scanner used to step one character at a time
#   with `${cmd:$i:1}`, which re-walks the string from its start on every
#   step (character offsets, in a UTF-8 locale), and appended to a growing
#   result: quadratic, 3.2 s at 10 KB. It now cuts the command at the four
#   characters that can change state — ' " $ ) — with four nested word
#   splits (one linear pass each; never a per-step re-slice, never `${s//}`,
#   which is quadratic in bash 3.2), and handles each run between two cuts
#   as one step, printed as soon as it is decided: kept verbatim in code,
#   one space per character inside quotes. Character for character the same
#   as the stepping scanner, in any locale (tests/bats/lib_strip_linear.bats
#   holds it to a frozen copy of it).
#
#   One step is <cut> <run>: the cut character before the run ("" at the
#   start) and the text up to the next cut, which contains none of the four.
#     S: everything is blanked; `'` returns to N.
#     D: everything is blanked; `"` returns to N unless the character before
#        it is `\`.
#        $( ... ) inside a double-quoted string is still CODE. Enter it in
#        normal state so its command is matched, and remember to come back
#        to D — otherwise the substitution's own quotes desync the outer one.
#     N: runs are kept; `'` and `"` open a quote; `$(` opens a substitution
#        (saving the state to return to); `)` closes the innermost one, or
#        is kept when none is open. Quote and substitution characters are
#        blanked; a `$` without `(` is kept.
#   Whether a cut `$` is `$(` is read off the run after it.
#   `for p in $text$cut` (cut appended, unquoted) yields exactly one piece
#   more than <text> has cuts: word splitting drops one trailing empty field,
#   and this way that field is the appended one. The pieces are expanded
#   before the loop runs, so an inner loop's IFS does not disturb an outer
#   one.
#
#   bash 3.2 compatible: word splitting and parameter expansion, no
#   associative arrays, no mapfile, no function call per step (each one
#   costs more than the step). Globbing is off while it splits and restored
#   afterwards.
_git_ops_strip_quoted() {
  local state="N"        # N=normal (code), S=single-quoted, D=double-quoted
  local stack=""         # one saved state char per open $( — innermost first
  local bs=0             # 1: the last run ended in `\`
  local c1="'" c2='"' c3='$' c4=')' p1 p2 p3 run d1 d2 d3 d cut
  local noglob=1 IFS
  case "$-" in *f*) ;; *) noglob=0; set -f ;; esac
  IFS="$c1"; d1=""
  for p1 in $1$c1; do
    IFS="$c2"; d2="$d1"
    for p2 in $p1$c2; do
      IFS="$c3"; d3="$d2"
      for p3 in $p2$c3; do
        IFS="$c4"; d="$d3"
        for run in $p3$c4; do
          cut=" "
          case "$state$d" in
            N|S|D) cut="" ;;
            S\') state="N" ;;
            D\") [ "$bs" -eq 1 ] || state="N" ;;
            N\') state="S" ;;
            N\") state="D" ;;
            N\$|D\$)
              case "$run" in
                "("*)
                  stack="${state}${stack}"
                  state="N"
                  cut="  "
                  run="${run#?}"
                  ;;
                *) [ "$state" = "D" ] || cut='$' ;;
              esac
              ;;
            N\))
              if [ -n "$stack" ]; then
                state="${stack:0:1}"
                stack="${stack:1}"
              else
                cut=")"
              fi
              ;;
          esac
          if [ "$state" = "N" ]; then
            printf '%s%s' "$cut" "$run"
          else
            printf '%s%*s' "$cut" "${#run}" ''
          fi
          case "$run" in *\\) bs=1 ;; *) bs=0 ;; esac
          d="$c4"
        done
        d3="$c3"
      done
      d2="$c2"
    done
    d1="$c1"
  done
  [ "$noglob" -eq 1 ] || set +f
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
#   Linear (spec 021 T1.5): each line is printed as it is read instead of
#   being appended to a growing result, which copied the whole result on
#   every line.
#
#   bash 3.2 compatible: read loop, no mapfile.
_git_ops_strip_heredocs() {
  local line rest delim="" trimmed
  while IFS= read -r line; do
    if [ -n "$delim" ]; then
      trimmed="${line#"${line%%[![:space:]]*}"}"
      if [ "$line" = "$delim" ] || [ "$trimmed" = "$delim" ]; then
        delim=""
      fi
      printf '\n'
      continue
    fi
    printf '%s\n' "$line"
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
  done <<< "$1"
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
# nothing. Set to 4096 by the maintainer (SDD Size cap, 2026-10-12) from
# measurement: every step below it is linear, but linear is not cheap in
# bash. On macOS bash 3.2 under load a 4 KB command costs ~55 ms as prose,
# ~180 ms with dense quoting and ~390 ms with a shell special every few
# bytes; commands of a few hundred bytes stay within the CON-7 budget, so the
# cap bounds the worst case and the 15 ms git-record budget holds for typical
# commands only. Measured with ${#cmd} under _git_ops_parse's own
# `local LC_ALL=C`, so it counts bytes whatever the caller's locale.
_GIT_OPS_MAX_BYTES=4096

# ---------------------------------------------------------------------------
# Parser (T1.3). Helpers below share state with their caller through bash's
# dynamic scoping: each one's comment names the caller locals it reads and
# writes. This keeps the hook path free of per-clause command substitutions.
# Every step below the cap is linear in the input, the copied strippers above
# included (made linear in T1.5); see _GIT_OPS_MAX_BYTES for what that costs.
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
  local LC_ALL=C # byte semantics, restored on return
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

# _git_ops_mark_words   (_git_ops_parse locals: reads h, NL; writes text)
#   Rewrites the heredoc-stripped command h into words for clause parsing.
#   States: N code, S single-quoted, D double-quoted (`$(` opens code in N and
#   D, as in _git_ops_strip_quoted). Every rule below keeps a value inside
#   one word, so a value can never be split into a word that reads as a name:
#     - every byte of a quoted span, quotes included, becomes `%`: one opaque
#       word that can be counted but never matches a name;
#     - except a quoted word whose unquoted form is exactly `git` or ends in
#       `/git` (`'git'`, `"git"`, `"/usr/bin/git"`, the usual way round an
#       alias), standing alone in code: it is the invocation and is written
#       without its quotes (_git_ops_quoted_git); in code, `\git` loses its
#       backslash likewise;
#     - `>&` and `&>` (redirections) are written `> ` and ` >`, so the clause
#       split does not read their `&` as a separator;
#     - a backslash in N or D makes the next byte part of the current word
#       (both become `%`; `my\ dir` is one word); backslash-newline is a line
#       continuation and disappears;
#     - a parameter expansion `${ … }` in N or D (braces, quotes and escapes
#       inside included) becomes `%` bytes, one opaque word;
#     - a command substitution `$( … )` or `` ` … ` `` (in N or D) and a
#       process substitution `<( … )` / `>( … )` (in N) is executed code AND
#       one argument of the command around it: in its enclosing text it is a
#       single `%`; its content is appended to text after a newline, as
#       clauses of their own. Nesting follows the same rules at every depth; an
#       unclosed one is closed at the end of input.
#   Outside these every byte is kept.
#
#   Linear (under the caller's LC_ALL=C, where every length and offset is a
#   byte count). Two bash 3.2 costs shape the code: `${s:k:n}` measures all of
#   s first, and `s="${s}x"` copies all of s. So h is cut once into blocks; the
#   walk works on `cur`, the unread text, kept between ~300 bytes and one
#   block longer by appending the next block; and output goes into arrays
#   (one per substitution depth, via _git_ops_put), joined once at the end.
#   Each step takes the run up to the next byte that matters in the current
#   state (`'` in S; `"`, `\`, `$`, backtick in D; those plus `'`, `(`, `)`,
#   `<`, `>`, `&` in N), looking at most W bytes ahead.
# shellcheck disable=SC2016,SC2295 # literal $( ${ patterns; spec vars are globs
_git_ops_mark_words() {
  local len=${#h} k=0 nb=0 bi=0 cur="" w run c nxt state="N" d=0 states="" kinds=""
  local pad="%" lastc="" piece W=128 B=1024
  local nspec='['"'"'"\\$`()<>&]*' dspec='["\\$`]*'
  local qgit_re='^(['"'"'"])([^'"'"'"[:space:]]*/)?git(['"'"'"])([[:space:];&|)`]|$)'
  local -a blocks b0 sb
  local k0=0 ksb=0
  case "$h" in
    *"'"* | *'"'* | *'`'* | *'$('* | *'${'* | *\\* | *'<('* | *'>('* | *'>&'* | *'&>'*) ;;
    *)
      text="$h"
      return 0
      ;;
  esac
  while [ "${#pad}" -lt "$W" ]; do pad="${pad}${pad}"; done
  while [ "$k" -lt "$len" ]; do
    blocks[nb]="${h:$k:$B}"
    nb=$((nb + 1))
    k=$((k + B))
  done
  while :; do
    _git_ops_refill
    if [ -z "$cur" ]; then break; fi
    w="${cur:0:$W}"
    case "$state" in
      S) run="${w%%\'*}" ;;
      D) run="${w%%$dspec}" ;;
      *) run="${w%%$nspec}" ;;
    esac
    if [ -n "$run" ]; then
      if [ "$state" = "N" ]; then
        _git_ops_put "$run"
      else
        _git_ops_put "${pad:0:${#run}}"
      fi
      cur="${cur:${#run}}"
      # The whole window was plain: read on.
      if [ "${#run}" -eq "${#w}" ]; then continue; fi
    fi
    c="${cur:0:1}"
    nxt="${cur:1:1}"
    if [ "$state" = "S" ]; then
      # c is the closing quote.
      _git_ops_put "%"
      cur="${cur:1}"
      state="N"
      continue
    fi
    case "$c" in
      \\)
        if [ "$state" = "N" ] && [ "${cur:1:3}" = "git" ]; then
          # `\git` is the invocation (the alias bypass): drop the backslash.
          cur="${cur:1}"
          continue
        elif [ "$nxt" = "$NL" ]; then
          :
        elif [ -z "$nxt" ]; then
          _git_ops_put "%"
        else
          _git_ops_put "%%"
        fi
        cur="${cur:2}"
        continue
        ;;
      '$')
        case "$nxt" in
          '(')
            _git_ops_open_subst P
            eval "local -a b${d}; b${d}=(); local k${d}=0"
            cur="${cur:2}"
            ;;
          '{') _git_ops_mark_braced ;;
          *)
            if [ "$state" = "D" ]; then _git_ops_put "%"; else _git_ops_put "\$"; fi
            cur="${cur:1}"
            ;;
        esac
        continue
        ;;
      '`')
        if [ "$state" = "N" ] && [ "${kinds:0:1}" = "B" ]; then
          _git_ops_close_subst
        else
          _git_ops_open_subst B
          eval "local -a b${d}; b${d}=(); local k${d}=0"
        fi
        cur="${cur:1}"
        continue
        ;;
    esac
    if [ "$state" = "D" ]; then
      # c is the closing quote.
      _git_ops_put "%"
      cur="${cur:1}"
      state="N"
      continue
    fi
    # N only from here on.
    case "$c" in
      "'" | '"')
        if _git_ops_quoted_git; then continue; fi
        if [ "$c" = "'" ]; then state="S"; else state="D"; fi
        _git_ops_put "%"
        ;;
      '<' | '>')
        if [ "$nxt" = "(" ]; then
          _git_ops_open_subst P
          eval "local -a b${d}; b${d}=(); local k${d}=0"
          cur="${cur:2}"
          continue
        fi
        if [ "$c" = ">" ] && [ "$nxt" = "&" ]; then
          # `2>&1` is a redirection, not the `&` separator.
          _git_ops_put "> "
          cur="${cur:2}"
          continue
        fi
        _git_ops_put "$c"
        ;;
      '&')
        if [ "$nxt" = ">" ]; then
          # `&>f` is a redirection, not the `&` separator.
          _git_ops_put " >"
          cur="${cur:2}"
          continue
        fi
        _git_ops_put "&"
        ;;
      ')')
        if [ "${kinds:0:1}" = "P" ]; then
          _git_ops_close_subst
        else
          _git_ops_put ")"
        fi
        ;;
      *) _git_ops_put "$c" ;;
    esac
    cur="${cur:1}"
  done
  while [ "$d" -gt 0 ]; do _git_ops_close_subst; done
  printf -v text '%s' ${b0[@]+"${b0[@]}"} ${sb[@]+"${sb[@]}"}
}

# _git_ops_refill   (_git_ops_mark_words locals: reads blocks, nb; writes cur,
#   bi)
#   Keeps at least ~300 bytes of unread text in cur while blocks remain, so a
#   window (W) or the quoted-git look-ahead (256) never runs short early.
_git_ops_refill() {
  if [ "${#cur}" -lt 300 ] && [ "$bi" -lt "$nb" ]; then
    cur="${cur}${blocks[$bi]}"
    bi=$((bi + 1))
  fi
}

# _git_ops_put <text>   (_git_ops_mark_words locals: reads d; writes b<d>,
#   k<d>, lastc)
#   Appends one piece to the output array of the current substitution depth:
#   b0/k0 for the top level, b<d>/k<d> (declared local in _git_ops_mark_words
#   when the depth is opened) inside a substitution.
_git_ops_put() {
  if [ "$d" -eq 0 ]; then
    b0[k0]="$1"
    k0=$((k0 + 1))
  else
    eval "b${d}[k${d}]=\$1; k${d}=\$((k${d} + 1))"
  fi
  lastc="${1: -1}"
}

# _git_ops_quoted_git   (_git_ops_mark_words locals: reads cur, lastc,
#   qgit_re, NL; writes cur, and output through _git_ops_put)
#   At the start of cur is a quote in code. When it opens a quoted word whose
#   unquoted form is `git` or ends in `/git`, standing alone (start of its
#   text or after whitespace, `;`, `&`, `|`, `(` or a backtick; followed by
#   one of those, `)` or the end), writes the word without its quotes, moves
#   past it and returns 0. Otherwise returns 1. A pair whose quotes differ
#   (`"git'`) is no match. The look-ahead is 256 bytes, so a longer quoted
#   path is not seen.
_git_ops_quoted_git() {
  local m
  case "$lastc" in
    '' | ' ' | $'\t' | "$NL" | ';' | '&' | '|' | '(' | '`') ;;
    *) return 1 ;;
  esac
  if [[ "${cur:0:256}" =~ $qgit_re ]] && [ "${BASH_REMATCH[1]}" = "${BASH_REMATCH[3]}" ]; then
    m="${BASH_REMATCH[0]}"
    _git_ops_put "${BASH_REMATCH[2]}git"
    cur="${cur:$((${#m} - ${#BASH_REMATCH[4]}))}"
    return 0
  fi
  return 1
}

# _git_ops_mark_braced   (_git_ops_mark_words locals: reads pad, W; writes
#   cur, bi, and output through _git_ops_put)
#   At the start of cur is `${`. Consumes through the matching `}` (nested
#   braces, quoted segments and backslash escapes inside do not end it; an
#   unclosed one runs to the end of input) and puts one `%` per byte, a
#   window at a time.
# shellcheck disable=SC2295 # the spec variables are glob patterns
_git_ops_mark_braced() {
  local depth=0 ch q="" win part bspec=$'[{}\\\\\'"]*' dqspec='["\\]*'
  _git_ops_put "%"
  cur="${cur:1}"
  while :; do
    _git_ops_refill
    if [ -z "$cur" ]; then return 0; fi
    win="${cur:0:$W}"
    if [ "$q" = "'" ]; then
      part="${win%%\'*}"
    elif [ -n "$q" ]; then
      part="${win%%$dqspec}"
    else
      part="${win%%$bspec}"
    fi
    if [ -n "$part" ]; then
      _git_ops_put "${pad:0:${#part}}"
      cur="${cur:${#part}}"
      if [ "${#part}" -eq "${#win}" ]; then continue; fi
    fi
    ch="${cur:0:1}"
    if [ "$ch" = "\\" ]; then
      _git_ops_put "%%"
      cur="${cur:2}"
      continue
    fi
    _git_ops_put "%"
    cur="${cur:1}"
    if [ -n "$q" ]; then
      q=""
      continue
    fi
    case "$ch" in
      "'" | '"') q="$ch" ;;
      '{') depth=$((depth + 1)) ;;
      '}')
        depth=$((depth - 1))
        if [ "$depth" -eq 0 ]; then return 0; fi
        ;;
    esac
  done
}

# _git_ops_open_subst <P|B>   (_git_ops_mark_words locals: writes states,
#   kinds, d, state, lastc, and the `%` through _git_ops_put)
#   The caller then declares b<d>/k<d> local for the new depth.
_git_ops_open_subst() {
  _git_ops_put "%"
  states="${state}${states}"
  kinds="${1}${kinds}"
  d=$((d + 1))
  state="N"
  lastc=""
}

# _git_ops_close_subst   (_git_ops_mark_words locals: reads NL, b<d>; writes
#   sb, ksb, d, states, kinds, state, lastc)
#   Joins the depth's pieces once and appends them, after a newline, to the
#   substitution clauses.
_git_ops_close_subst() {
  eval "printf -v piece '%s' \${b${d}[@]+\"\${b${d}[@]}\"}"
  sb[ksb]="${NL}${piece}"
  ksb=$((ksb + 1))
  d=$((d - 1))
  state="${states:0:1}"
  states="${states:1}"
  kinds="${kinds:1}"
  lastc="%"
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

# _git_ops_cut_stop   (_git_ops_parse_clause locals: reads t, i, ex, cut,
#   assigned; output through _git_ops_emit)
#   Command-position scanning stopped on a word it does not recognise (the
#   word just read; i words of t have been read). In the executor fallback
#   after a cut or any assignment, that word may be a fragment of a quoted
#   value (`bash -c "A='x y' git push"` → `A= x y git push`, `A=x' 'y` →
#   `A=x  y`): if a git word follows, the invocation is recorded as `?`
#   rather than lost (fail closed, never a value). Elsewhere the clause simply
#   has no git invocation. Reads the rest of t once, as a slice.
_git_ops_cut_stop() {
  local w
  if [ "$ex" -ne 1 ]; then return 0; fi
  if [ "$cut" -ne 1 ] && [ "$assigned" -ne 1 ]; then return 0; fi
  for w in "${t[@]:i}"; do
    case "$w" in
      git | */git)
        _git_ops_emit '?' '' '(executor)'
        return 0
        ;;
    esac
  done
}

# _git_ops_step_position   (_git_ops_parse_clause locals: reads tok, ex, mode;
#   writes stage, skip, cut, assigned, ovr, wtakes, wlookup, wdur, tok)
#   One word in command position. Openers, leading redirections and
#   assignments are passed over; a wrapper word moves to stage `wrap` (its
#   options, listed value-taking ones with their value) or `shopt` (a shell's
#   options, executor fallback only); `git` or `*/git` moves to stage `glob`.
#   Returns 1 when the clause has no git invocation (after _git_ops_cut_stop
#   has had its say), 0 otherwise.
# shellcheck disable=SC2016 # '$(' patterns are literal openers
_git_ops_step_position() {
  local name val
  while :; do
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
      '' | '{' | '!' | if | then | elif | else | while | until | do) return 0 ;;
      git | */git)
        stage="glob"
        return 0
        ;;
      [0123456789]'<'* | [0123456789]'>'* | '<'* | '>'*)
        # A leading redirection; a bare operator takes the next word.
        val="${tok#[0123456789]}"
        val="${val//[<>-]/}"
        if [ -z "$val" ]; then skip=1; fi
        return 0
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
          '`'* | '$('*)
            # The value is a command: examine it as this word.
            tok="$val"
            continue
            ;;
        esac
        return 0
        ;;
      env) _git_ops_wrapper "-u --unset" "" 0 ;;
      sudo) _git_ops_wrapper "-u -g -h -p -C -D -r -t -U" "" 0 ;;
      time) _git_ops_wrapper "" "" 0 ;;
      nice) _git_ops_wrapper "-n" "" 0 ;;
      timeout) _git_ops_wrapper "-s -k" "" 1 ;;
      command) _git_ops_wrapper "" lookup 0 ;;
      nohup | exec) ;;
      eval)
        if [ "$mode" != "executor" ]; then return 1; fi
        ;;
      sh | [abcdefghijklmnopqrstuvwxyz]*sh | */sh | */[abcdefghijklmnopqrstuvwxyz]*sh)
        # Only in the executor fallback, where `bash -c 'git …'` has lost its
        # quotes and the payload's words follow the shell's options. These
        # options do not cut: `-c` precedes every payload.
        if [ "$mode" != "executor" ]; then return 1; fi
        stage="shopt"
        ;;
      *)
        _git_ops_cut_stop
        return 1
        ;;
    esac
    return 0
  done
}

# _git_ops_wrapper <value-taking options> <lookup|""> <1 if a duration
#   follows>   (_git_ops_parse_clause locals: writes stage, wtakes, wlookup,
#   wdur)
#   Enters stage `wrap` for a wrapper word's options.
_git_ops_wrapper() {
  stage="wrap"
  wtakes=" $1 "
  wlookup="$2"
  wdur="$3"
}

# _git_ops_step_wrap   (_git_ops_parse_clause locals: reads tok, ex, wtakes,
#   wlookup; writes stage, skip, cut, wdur)
#   One word after a wrapper. Options are passed over (a listed one with its
#   value); every option sets cut in the executor fallback (its value may have
#   been quoted and split). With lookup, an option containing v or V
#   (`command -v`) makes the clause a lookup: returns 1. timeout's duration
#   is passed over too. Returns 2 when the word is not the wrapper's: the
#   caller reads it again in command position.
_git_ops_step_wrap() {
  case "$tok" in
    -*)
      if [ -n "$wlookup" ]; then
        case "$tok" in -*[vV]*) return 1 ;; esac
      fi
      cut=$ex
      case "$wtakes" in
        *" $tok "*) skip=1 ;;
      esac
      return 0
      ;;
  esac
  if [ "$wdur" -eq 1 ]; then
    wdur=0
    cut=$ex
    stage="pos"
    return 0
  fi
  stage="pos"
  return 2
}

# _git_ops_step_global   (_git_ops_parse_clause locals: reads tok, ex, cut,
#   ovr; writes stage, skip, cut, sub; output through _git_ops_emit)
#   One word between `git` and the subcommand. Returns 1 when there is no
#   subcommand (--version, --help). In the executor fallback every option
#   except the value-less ones makes the subcommand `?`: a separate or joined
#   value may have been quoted and split by quote removal (`-C 'my dir'` →
#   `-C  my dir`, `--git-dir='a b'` → `--git-dir= a b`). A word that is no
#   option is the subcommand (_git_ops_read_subcommand); stage `args` follows.
_git_ops_step_global() {
  case "$tok" in
    --version | --help)
      # After a cut in the executor fallback this may be a value fragment of
      # the global option before it: keep the record, as `?`.
      if [ "$ex" -eq 1 ] && [ "$cut" -eq 1 ]; then
        _git_ops_emit '?' '' '(executor)'
      fi
      return 1
      ;;
    -C | -c | --git-dir | --work-tree | --namespace | --config-env | --super-prefix | --exec-path)
      skip=1
      cut=$ex
      ;;
    -p | -P | --paginate | --no-pager | --bare | --no-replace-objects | --literal-pathspecs | \
      --glob-pathspecs | --noglob-pathspecs | --icase-pathspecs | --no-optional-locks | --no-advice | \
      --no-lazy-fetch) ;;
    -*) cut=$ex ;;
    *)
      _git_ops_read_subcommand
      stage="args"
      ;;
  esac
  return 0
}

# _git_ops_read_subcommand   (_git_ops_parse_clause locals: reads cut; writes
#   tok, sub)
#   tok is the subcommand word. The subcommand is a name from
#   _GIT_OPS_COMMANDS or `?` (closed list in both modes, SDD data model
#   2026-10-12); after a cut it is always `?`.
_git_ops_read_subcommand() {
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

# _git_ops_step_argument   (_git_ops_parse_clause locals: reads tok; writes
#   tok, skip, ended, fl, nfl, npos, pos1, listing, first_word, fw_set)
#   One word after the subcommand: a flag name is added to fl (an array,
#   joined once at the end: ADR-3, short flags as their first letter, long
#   ones without `=value`); a positional is counted, never kept, except the
#   first, which is compared against the read-only forms and the ACTIONS list
#   only. first_word keeps the word right after the subcommand.
_git_ops_step_argument() {
  local name
  if [ "$fw_set" -eq 0 ]; then
    first_word="$tok"
    fw_set=1
  fi
  _git_ops_trim_closers
  if [ "$ended" -eq 1 ]; then
    npos=$((npos + 1))
    return 0
  fi
  case "$tok" in
    '') ;;
    '<'* | '>'* | [0123456789]'<'* | [0123456789]'>'*)
      # A redirection. Bare operator: its target is the next word.
      name="${tok#[0123456789]}"
      name="${name//[<>-]/}"
      if [ -z "$name" ]; then skip=1; fi
      ;;
    --)
      fl[nfl]="--"
      nfl=$((nfl + 1))
      ended=1
      listing=0
      ;;
    --?*)
      name="${tok%%=*}"
      fl[nfl]="$name"
      nfl=$((nfl + 1))
      case "$name" in
        --all | --remotes | --list | --verbose | --show-current | --contains | \
          --no-contains | --merged | --no-merged | --points-at | --sort | --format | \
          --column | --no-column | --color | --no-color) ;;
        *) listing=0 ;;
      esac
      ;;
    -?*)
      # ADR-3: a short flag is recorded as its first letter only, so a value
      # glued to it (-m<msg>, -S<key>) never reaches the record.
      fl[nfl]="-${tok:1:1}"
      nfl=$((nfl + 1))
      case "${tok#-}" in
        *[!arlv]*) listing=0 ;;
      esac
      ;;
    *)
      npos=$((npos + 1))
      if [ "$npos" -eq 1 ]; then pos1="$tok"; fi
      ;;
  esac
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
#   One pass over the words (a for loop: an indexed read of a bash 3.2 array
#   walks it from the start). Each word goes to the step of the current
#   stage: pos (command position), wrap / shopt (a wrapper's or a shell's
#   options), glob (git's global options), args (after the subcommand); skip
#   passes over an option's separate value.
_git_ops_parse_clause() {
  local -a t fl
  # shellcheck disable=SC2206 # deliberate word splitting; caller set noglob
  t=($1)
  local tok i=0 skip=0 stage="pos" ovr="" rc
  local wtakes="" wlookup="" wdur=0
  local sub="" npos=0 pos1="" listing=1 ended=0 nfl=0 first_word="" fw_set=0 flags action

  # Executor fallback only: an option value or an assignment value may have
  # been a quoted multi-word string whose fragments now stand where the
  # subcommand is read (`bash -c "git -C 'my dir' reset"`). So every wrapper
  # option, the timeout duration, an emptied assignment and every global option
  # but the value-less ones set cut, and cut makes the subcommand `?` (CON-13).
  # ex is 1 in that mode, so `cut=$ex` is a no-op elsewhere.
  local ex=0 cut=0 assigned=0
  if [ "$mode" = "executor" ]; then ex=1; fi

  for tok in ${t[@]+"${t[@]}"}; do
    i=$((i + 1))
    if [ "$skip" -gt 0 ]; then
      skip=$((skip - 1))
      continue
    fi
    case "$stage" in
      wrap)
        _git_ops_step_wrap
        rc=$?
        if [ "$rc" -eq 1 ]; then return 0; fi
        if [ "$rc" -eq 0 ]; then continue; fi
        # rc 2: the word is read again in command position.
        ;;
      shopt)
        case "$tok" in -*) continue ;; esac
        stage="pos"
        ;;
      glob)
        _git_ops_step_global || return 0
        continue
        ;;
      args)
        _git_ops_step_argument
        continue
        ;;
    esac
    _git_ops_step_position || return 0
  done
  # No subcommand: no git invocation, bare `git`, or only global options.
  if [ "$stage" != "args" ]; then return 0; fi

  # git stash <verb> [options]: the verb is the word right after `stash`; when
  # that word is an option (or absent) the verb is an implicit push, so a
  # value such as `-m list` is never read as the verb.
  if [ "$sub" = "stash" ]; then
    case "$first_word" in
      '' | -*) pos1="" ;;
    esac
  fi

  printf -v flags '%s ' ${fl[@]+"${fl[@]}"}
  flags="${flags% }"
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
  # Byte semantics for every length, offset and pattern below and in the
  # helpers, whatever the caller's locale: under C, ${s:k:n} takes a byte
  # offset (in UTF-8 bash counts characters from the start, which makes any
  # walk quadratic) and ${#cmd} counts bytes for the cap. The hook adapter's
  # own LC_ALL=C (logwrite.sh, CON-3) is not relied on. Restored on return.
  local LC_ALL=C
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
  # while `overrides` stays per clause. Only the first 4096 bytes are
  # scanned: `${s//x/y}` costs O(length) per match in bash, and a leading
  # cd path plus override never come near that length.
  scan="${cmd:0:4096}"
  scan="${scan//$NL/;}"
  if [[ "$scan" =~ $cd_re ]]; then scan="${scan:${#BASH_REMATCH[0]}}"; fi
  if [[ "$scan" =~ $ovr_re ]]; then first="${BASH_REMATCH[1]}"; fi

  local -a parts clauses
  h="$(_git_ops_strip_heredocs "$cmd")"
  q="$(_git_ops_strip_quoted "$h")"
  if _git_ops_has_shell_executor "$q"; then
    mode="executor"
    # Every quote character becomes a space: split once on both quotes and
    # join with spaces (`${h//\'/ }` would cost O(length) per quote).
    IFS=$'\'"' read -r -d '' -a parts <<< "$h" || :
    printf -v text '%s ' ${parts[@]+"${parts[@]}"}
  else
    _git_ops_mark_words
  fi

  # Clauses: one split on the separators && || | ; & and newline (an empty
  # field between `&&` or `||` is an empty clause). In normal mode
  # _git_ops_mark_words has already turned `2>&1` and `&>f` into redirections
  # without `&`; in the executor fallback such an `&` splits, which can only
  # move words after it into a clause of their own (flags there are
  # `(executor)` anyway).
  local had_noglob=0 clause
  case "$-" in *f*) had_noglob=1 ;; esac
  set -f
  IFS=$';&|\n' read -r -d '' -a clauses <<< "$text" || :
  local IFS=$' \t'
  for clause in ${clauses[@]+"${clauses[@]}"}; do
    _git_ops_parse_clause "$clause"
  done
  if [ "$had_noglob" -eq 0 ]; then set +f; fi
  return 0
}
