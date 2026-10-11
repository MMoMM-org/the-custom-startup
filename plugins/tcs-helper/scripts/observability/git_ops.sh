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
#                               Names only (CON-13): no flag value, positional,
#                               path, URL, message or assignment value is ever
#                               printed. Flags are printed in full; the 256-byte
#                               cap is the writer's job.
#
# Parsing (SDD Runtime View, Complex Logic; ADR-3, ADR-9):
#   heredoc bodies and quoted text are stripped with the copied functions
#   below; quoted text is then re-marked with `%` so a quoted argument still
#   counts as one opaque word (`git branch "x"` has a positional, `git "reset"`
#   has an undeterminable subcommand `?`). When the stripped text runs a shell
#   on a payload (`bash -c`, `eval`), the executor fallback applies instead:
#   every quote character becomes a space and the records carry
#   flags `(executor)`. Clauses split on && || | ; & and newline; in each, the
#   command position skips openers, assignments and wrappers (env sudo time
#   nice timeout nohup exec command) before looking for `git` or `*/git`.
#   override_first mirrors the guard's first-token rule
#   (tcs-git-helpers lib/override.sh, one leading cd/pushd clause stripped).
#
# Known limits (documented, not silent): `xargs git …`, `find … -exec git …`,
# git run from a script file, and git inside a `$( )` that is not at command
# position (`echo $(git reset)`) are not recognised and record nothing. In the
# executor fallback, nested quoting is gone, so a quoted multi-word value
# before the subcommand can shift which word is read as the subcommand.
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
# Sourced by a hook: defines functions only. No output, no external commands,
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

# ---------------------------------------------------------------------------
# Parser (T1.3). Helpers below share state with _git_ops_parse through bash's
# dynamic scoping: they read and assign locals that _git_ops_parse declares,
# which keeps the hook path free of per-clause command substitutions.
# ---------------------------------------------------------------------------

# _git_ops_command <payload>
#   Prints the decoded value of the first `"command":"` key in <payload>.
#   The key is matched with its leading quote, so an escaped occurrence
#   (`\"command\":\"` inside another string) is not a match. Nothing is printed
#   when the key is missing or the string never closes (CON-9).
_git_ops_command() {
  local payload="${1-}" rest out="" upto_quote upto_bs chunk esc
  case "$payload" in
    *'"command":"'*) ;;
    *) return 0 ;;
  esac
  rest="${payload#*\"command\":\"}"
  while :; do
    upto_quote="${rest%%\"*}"
    upto_bs="${rest%%\\*}"
    chunk="$upto_quote"
    if [ "${#upto_bs}" -lt "${#chunk}" ]; then chunk="$upto_bs"; fi
    # Neither a quote nor a backslash left: the string is unterminated.
    if [ "${#chunk}" -eq "${#rest}" ]; then return 0; fi
    out="${out}${chunk}"
    rest="${rest:${#chunk}}"
    case "$rest" in
      '"'*)
        printf '%s' "$out"
        return 0
        ;;
    esac
    esc="${rest:1:1}"
    case "$esc" in
      '') return 0 ;;
      '"') out="${out}\"" ;;
      \\) out="${out}\\" ;;
      /) out="${out}/" ;;
      n) out="${out}"$'\n' ;;
      t) out="${out}"$'\t' ;;
      r) out="${out}"$'\r' ;;
      *) out="${out}\\${esc}" ;;
    esac
    rest="${rest:2}"
  done
}

# _git_ops_mark_quoted   (reads h, q; assigns text — locals of _git_ops_parse)
#   h is the heredoc-stripped command, q the same after _git_ops_strip_quoted;
#   the two are position-aligned (stripping maps one byte to one byte). Every
#   run of blanks in q whose bytes in h are not blank was quoted text or a
#   `$(`/`)` delimiter. The delimiters become blanks again (the substitution's
#   code stays in scope); the quoted span between the run's edges becomes `%`,
#   one opaque word that can be counted but never matches a name.
_git_ops_mark_quoted() {
  # shellcheck disable=SC2016 # a literal glob bracket of $ ( )
  local rest="$q" off=0 run seg lead trail mid n subst='[$()]'
  if [ "$h" = "$q" ]; then
    text="$q"
    return 0
  fi
  text=""
  while [ -n "$rest" ]; do
    run="${rest%%' '*}"
    text="${text}${run}"
    off=$((off + ${#run}))
    rest="${rest:${#run}}"
    if [ -z "$rest" ]; then break; fi
    run="${rest%%[! ]*}"
    n=${#run}
    seg="${h:$off:$n}"
    if [ "$seg" != "$run" ]; then
      seg="${seg//$subst/ }"
      seg="${seg//[[:space:]]/ }"
      lead="${seg%%[! ]*}"
      if [ "${#lead}" -lt "$n" ]; then
        trail="${seg##*[! ]}"
        mid="${seg:${#lead}:$((n - ${#lead} - ${#trail}))}"
        seg="${lead}${mid//?/%}${trail}"
      fi
    fi
    text="${text}${seg}"
    off=$((off + n))
    rest="${rest:$n}"
  done
}

# _git_ops_trim_closers   (assigns tok — a local of the caller)
#   Drops trailing backticks and parentheses: `(git reset)`, `` `git pull` ``.
_git_ops_trim_closers() {
  while :; do
    case "$tok" in
      *'`' | *')') tok="${tok%?}" ;;
      *) return 0 ;;
    esac
  done
}

# _git_ops_parse_clause <clause>
#   (reads mode, first_left; may clear first_left — locals of _git_ops_parse)
#   Prints the record for the clause's git invocation, if it has one and it is
#   not read-only. Word splitting relies on the caller's IFS and noglob.
# shellcheck disable=SC2016 # '$(' patterns are literal openers
_git_ops_parse_clause() {
  local -a t
  # shellcheck disable=SC2206 # deliberate word splitting; caller set noglob
  t=($1)
  local n=${#t[@]} i=0 tok name val ovr="" ofirst="" letters
  if [ "$n" -eq 0 ]; then return 0; fi

  # override_first: the clause the guard reads as first, i.e. the first one
  # whose first word is the first-position override assignment.
  if [ -n "$first_left" ] && [ "${t[0]}" = "${first_left}=1" ]; then
    ofirst="$first_left"
    first_left=""
  fi

  # Command position: openers, assignments, wrappers.
  while [ "$i" -lt "$n" ]; do
    tok="${t[$i]}"
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
        continue
        ;;
      git | */git) break ;;
      [[:alpha:]_]*=*)
        name="${tok%%=*}"
        case "$name" in
          *[![:alnum:]_]*) return 0 ;;
        esac
        val="${tok#*=}"
        case "$name" in
          CLAUDE_ALLOW_?*)
            case "${name#CLAUDE_ALLOW_}" in
              *[![:upper:][:digit:]_]*) ;;
              *) if [ "$val" = "1" ]; then ovr="${ovr} ${name}"; fi ;;
            esac
            ;;
        esac
        case "$val" in
          '`'* | '$('*)
            t[i]="$val"
            continue
            ;;
        esac
        i=$((i + 1))
        continue
        ;;
      env)
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -u | --unset) i=$((i + 2)) ;;
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      sudo)
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -u | -g | -h | -p | -C | -D | -r | -t | -U) i=$((i + 2)) ;;
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      time)
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      nice)
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -n) i=$((i + 2)) ;;
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      timeout)
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -s | -k) i=$((i + 2)) ;;
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        i=$((i + 1)) # the duration
        ;;
      nohup | exec)
        i=$((i + 1))
        ;;
      command)
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -*[vV]*) return 0 ;; # a lookup, not an invocation
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      eval)
        if [ "$mode" != "executor" ]; then return 0; fi
        i=$((i + 1))
        ;;
      sh | [[:lower:]]*sh | */sh | */[[:lower:]]*sh)
        # Only in the executor fallback, where `bash -c 'git …'` has lost its
        # quotes and the payload's words follow the shell's options.
        if [ "$mode" != "executor" ]; then return 0; fi
        i=$((i + 1))
        while [ "$i" -lt "$n" ]; do
          case "${t[$i]}" in
            -*) i=$((i + 1)) ;;
            *) break ;;
          esac
        done
        ;;
      *) return 0 ;;
    esac
  done
  if [ "$i" -ge "$n" ]; then return 0; fi
  i=$((i + 1))

  # Global options between `git` and the subcommand. In the executor fallback
  # a value ending in `=` was cut open by quote removal (`-c k='v w'`): the
  # next word is still value, so the subcommand cannot be determined (CON-13).
  local cut=0
  while [ "$i" -lt "$n" ]; do
    case "${t[$i]}" in
      --version | --help) return 0 ;;
      -C | -c | --git-dir | --work-tree | --namespace | --config-env | --super-prefix | --exec-path)
        if [ "$mode" = "executor" ]; then
          case "${t[$((i + 1))]-}" in *=) cut=1 ;; esac
        fi
        i=$((i + 2))
        ;;
      -*) i=$((i + 1)) ;;
      *) break ;;
    esac
  done
  if [ "$i" -ge "$n" ]; then return 0; fi

  local sub
  tok="${t[$i]}"
  _git_ops_trim_closers
  sub="$tok"
  if [ "$cut" -eq 1 ]; then sub='?'; fi
  case "$sub" in
    [[:lower:]]*)
      case "$sub" in
        *[![:lower:][:digit:]-]*) sub='?' ;;
      esac
      ;;
    *) sub='?' ;;
  esac
  i=$((i + 1))

  # Flags and positionals. Positionals are counted, never printed: the first
  # one is compared against the read-only forms and the ACTIONS list only.
  local flags="" npos=0 pos1="" ended=0 listing=1 skip=0
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
      '' ) ;;
      '<'* | '>'* | [[:digit:]]'<'* | [[:digit:]]'>'*)
        # A redirection. Bare operator: its target is the next word.
        val="${tok#[[:digit:]]}"
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

  # Read-only predicate (ADR-9, closed list; everything else is recorded).
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

  # ACTIONS (closed): the first positional is the action only if listed.
  local action=""
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

  # Executor fallback: the payload's own quoting is gone, so a word from a
  # message could look like a flag. Flag names are not trusted there.
  if [ "$mode" = "executor" ]; then flags="(executor)"; fi

  printf '%s\t%s\t%s\t%s\t%s\n' "$sub" "$action" "$flags" "${ovr# }" "$ofirst"
}

# _git_ops_parse <decoded command>
#   Prints zero or more records (see header). Always returns 0.
_git_ops_parse() {
  local cmd="${1-}"
  case "$cmd" in
    *git*) ;;
    *) return 0 ;;
  esac
  local NL=$'\n' h q text mode="normal" first_left="" scan
  local cd_re='^[[:space:]]*(cd|pushd)[[:space:]]+[^&;]*(&&|;)[[:space:]]*'
  local ovr_re='^(CLAUDE_ALLOW_[A-Z0-9_]+)=1[[:space:]]'

  # The guard's first-token rule (lib/override.sh), on the command as typed:
  # newlines read as `;`, one leading cd/pushd clause stripped, then the
  # override must be the very first word.
  scan="${cmd//$NL/;}"
  if [[ "$scan" =~ $cd_re ]]; then scan="${scan:${#BASH_REMATCH[0]}}"; fi
  if [[ "$scan" =~ $ovr_re ]]; then first_left="${BASH_REMATCH[1]}"; fi

  h="$(_git_ops_strip_heredocs "$cmd")"
  q="$(_git_ops_strip_quoted "$h")"
  if _git_ops_has_shell_executor "$q"; then
    mode="executor"
    text="${h//\'/ }"
    text="${text//\"/ }"
  else
    _git_ops_mark_quoted
  fi

  # `2>&1` and `&>f` are redirections, not the `&` separator.
  text="${text//'>&'/'> '}"
  text="${text//'&>'/' >'}"
  text="${text//'&&'/$NL}"
  text="${text//'||'/$NL}"
  text="${text//'|'/$NL}"
  text="${text//';'/$NL}"
  text="${text//'&'/$NL}"

  local had_noglob=0 clause rest
  case "$-" in *f*) had_noglob=1 ;; esac
  set -f
  local IFS=$' \t'
  rest="${text}${NL}"
  while [ -n "$rest" ]; do
    clause="${rest%%"$NL"*}"
    rest="${rest#*"$NL"}"
    _git_ops_parse_clause "$clause"
  done
  if [ "$had_noglob" -eq 0 ]; then set +f; fi
  return 0
}
