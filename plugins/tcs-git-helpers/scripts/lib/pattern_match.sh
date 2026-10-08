#!/usr/bin/env bash
# scripts/lib/pattern_match.sh — POSIX ERE patterns for destructive git ops
#
# CONSTRAINTS (CON-1, CON-9 from SDD):
#   - bash 3.2 compatible (macOS default `/bin/bash` 3.2.57).
#   - Patterns MUST compile on both regex engines bash is built against:
#     BSD/libc (macOS) and GNU/glibc (Linux, Docker). A pattern that fails to
#     compile makes `[[ =~ ]]` return 2, which every caller here reads as
#     "no match" — the guard then fails OPEN and silently allows the command.
#   - Whitespace: [[:space:]]+ — NEVER \s. `\s` is a PCRE extension: glibc
#     accepts it, BSD does not, so it silently stops matching on macOS.
#   - Word boundaries: ([^[:alnum:]_]|$) — NEVER \b, and NEVER the BSD-only
#     [[:<:]] / [[:>:]]. glibc rejects [[:<:]]/[[:>:]] outright
#     ("Invalid character class name"), which is the fail-open case above.
#     ([^[:alnum:]_]|$) is equivalent for a *trailing* boundary in a substring
#     match: it requires the next character to be a non-word char, or the end
#     of the string. It consumes that character, so only use it pattern-final.
#   - Non-space runs: [^[:space:]]+.
#
# PURPOSE:
#   Source of truth for the regex constants used by the PreToolUse:Bash
#   dispatcher (`scripts/block-bad-git-ops.sh`) and any other hook that
#   needs to recognise destructive or stateful git command shapes.
#
# DESIGN:
#   Each canonical destructive pattern from PRD §Feature M7 has its own
#   exported PATTERN_<NAME> constant so it can be re-used across hooks
#   without duplication. The single helper `_match_command` runs a bash
#   `[[ =~ ]]` regex match (substring, not anchored) so compound forms
#   like `cd foo && git ...` match too.
#
# COVERAGE (PRD §Feature M7 destructive list — 14+ canonical patterns):
#     1. git reset --hard                    -> PATTERN_RESET_HARD
#     2. git clean -f / -fx / --force        -> PATTERN_CLEAN_FORCE
#     3. git checkout .                      -> PATTERN_CHECKOUT_DOT
#     4. git checkout -- <path>              -> PATTERN_CHECKOUT_PATH
#     5. git restore --worktree --source / --staged -> PATTERN_RESTORE_DESTRUCTIVE
#     6. git branch -D                       -> PATTERN_BRANCH_FORCE_DELETE
#     7. git stash drop / clear              -> PATTERN_STASH_DESTROY
#     8. git reflog expire                   -> PATTERN_REFLOG_EXPIRE
#     9. git commit --no-verify / -n         -> PATTERN_NO_VERIFY
#    10. git push (any)                      -> PATTERN_PUSH         [M1]
#    11. git push --force (NOT --force-with-lease) -> PATTERN_PUSH_FORCE
#    12. git push --delete <branch>          -> PATTERN_PUSH_DELETE_FLAG
#    13. git push <remote> :<branch>         -> PATTERN_PUSH_COLON_DELETE
#    14. gh api ... git/refs ... DELETE       -> PATTERN_GH_REF_DELETE_A/B
#    15. git checkout -b / git switch -c     -> PATTERN_BRANCH_CREATE  [M2]
#    16. git checkout / git switch <branch>  -> PATTERN_BRANCH_RESUME  [M3]
#    17. git -c core.hooksPath=...           -> PATTERN_HOOKSPATH_INLINE
#    18. git config core.hooksPath ...       -> PATTERN_HOOKSPATH_CONFIG

# ---------------------------------------------------------------------------
# Destructive operation patterns (PRD §Feature M7)
# ---------------------------------------------------------------------------

# Shared anchor for every git pattern (#171). `git` must be a command word:
# preceded by the start of the clause or by a character that cannot belong to
# a path segment's NAME -- so `/usr/bin/git`, `(git`, `'git` and `"git` count,
# while `/r/.git reset` and `my-git reset` do not. The old anchor,
# `git[[:space:]]+`, matched any substring, so a path ending in `.git`
# satisfied it for the wrong reason.
#
# Global options between `git` and the subcommand (`-C <path>`, `-c k=v`,
# `--no-pager`, `--git-dir=…`) are NOT handled here: _clausify adds a
# normalised copy of each clause with them removed (see _normalize_git_clause),
# so every pattern below stays written against the plain form.
_GIT_CMD='(^|[^[:alnum:]_.-])git[[:space:]]+'

# git reset --hard [<ref>]
PATTERN_RESET_HARD="$_GIT_CMD"'reset[[:space:]]+--hard([^[:alnum:]_]|$)'

# git clean -f / -fx / -fX / -Xf / -dfx / --force  (any bundle containing f or x, --force)
# `-[a-zA-Z]*[fx]` allows uppercase neighbours (e.g. `-fX`, `-Xf`) — `-X` removes
# only ignored files which is destructive when combined with `-f`. Substring-match
# means trailing `X` after a matched `-f` does not block the match.
PATTERN_CLEAN_FORCE="$_GIT_CMD"'clean[[:space:]]+(-[a-zA-Z]*[fx]|--force)'

# git checkout .   (require . to be its own argument: end-of-string or whitespace next)
PATTERN_CHECKOUT_DOT="$_GIT_CMD"'checkout[[:space:]]+\.([[:space:]]|$)'

# git checkout -- <path>
PATTERN_CHECKOUT_PATH="$_GIT_CMD"'checkout[[:space:]]+--[[:space:]]+[^[:space:]]+'

# git restore --worktree --source=<ref> ...   OR   --source=<ref> --worktree ...   OR   --staged ...
# Both flag orderings of --worktree + --source are equally valid git invocations
# and equally destructive — match either.
PATTERN_RESTORE_DESTRUCTIVE="$_GIT_CMD"'restore[[:space:]]+(.*--worktree.*--source.*|.*--source.*--worktree.*|.*--staged.*)'

# git branch -D <name>   (capital D = force delete; lowercase -d is the safe form)
PATTERN_BRANCH_FORCE_DELETE="$_GIT_CMD"'branch[[:space:]]+-D([^[:alnum:]_]|$)'

# git stash drop / git stash clear
PATTERN_STASH_DESTROY="$_GIT_CMD"'stash[[:space:]]+(drop|clear)([^[:alnum:]_]|$)'

# git reflog expire ...   (kills the recovery net)
PATTERN_REFLOG_EXPIRE="$_GIT_CMD"'reflog[[:space:]]+expire([^[:alnum:]_]|$)'

# git commit ... --no-verify   |   git commit ... -n
# Caveat: bundled-flag forms like `-nm "msg"` (shell-parsed as -n + -m) are NOT
# detected — the trailing boundary requires a word→non-word transition, and
# `n` followed by another word char (`m`) has none. Accepted trade-off: PRD M7 lists `-n` as the
# canonical form. Widening to `-[a-zA-Z]*n` would also flag the discrete flag
# bundle `-an` (= -a + -n) which is correct in spirit, but the design choice in
# v1.0 is to stay specific to the canonical forms documented in the PRD.
#
# NOTE: Dispatchers must call _match_no_verify instead of _match_command
# directly so that compound commands like `git commit && echo -n` do not
# produce a false-positive. See _match_no_verify below.
PATTERN_NO_VERIFY="$_GIT_CMD"'commit.*(--no-verify|-n([^[:alnum:]_]|$))'

# ---------------------------------------------------------------------------
# Push patterns (M1 closed-PR check + M7 destructive push variants)
# ---------------------------------------------------------------------------

# git push (any form) — used by M1 closed-PR check; not destructive on its own
PATTERN_PUSH="$_GIT_CMD"'push([^[:alnum:]_]|$)'

# git push ... --force   (NEGATIVE: must NOT match --force-with-lease)
#
# Why not the usual ([^[:alnum:]_]|$) boundary after `--force`? Because it
# accepts any non-word char — and `-` is non-word, so it DOES match between
# `e` and `-` in `--force-with-lease`. We instead require the next char
# after `--force` to be whitespace OR end-of-string.
PATTERN_PUSH_FORCE="$_GIT_CMD"'push[[:space:]].*--force([[:space:]]|$)'

# git push ... --delete <branch>   (long-form remote branch delete)
PATTERN_PUSH_DELETE_FLAG="$_GIT_CMD"'push[[:space:]]+(.+[[:space:]]+)?--delete([^[:alnum:]_]|$)'

# git push <remote> :<branch>   (refspec-form remote branch delete)
PATTERN_PUSH_COLON_DELETE="$_GIT_CMD"'push[[:space:]]+[^[:space:]]+[[:space:]]+:[^[:space:]]+'

# ---------------------------------------------------------------------------
# Branch create / resume (M2 / M3)
# ---------------------------------------------------------------------------

# git checkout -b <name>   |   git switch -c <name>
PATTERN_BRANCH_CREATE="$_GIT_CMD"'(checkout[[:space:]]+-b|switch[[:space:]]+-c)[[:space:]]+[^[:space:]]+'

# git checkout <branch>   |   git switch <branch>   (bare; not a flag, not a path)
# Anchored with $ so trailing args are not allowed (avoids matching pathspec forms).
# The capture excludes leading `-` (so `-b`/`-c` flag forms do NOT match) and
# leading `.` (so `git checkout .` and `git checkout .githooks` do NOT match —
# those are pathspecs, handled by PATTERN_CHECKOUT_DOT / PATTERN_CHECKOUT_PATH).
PATTERN_BRANCH_RESUME="$_GIT_CMD"'(checkout|switch)[[:space:]]+([^-.[:space:]][^[:space:]]*)$'

# ---------------------------------------------------------------------------
# core.hooksPath subversion (defeats .githooks/)
# ---------------------------------------------------------------------------

# git -c core.hooksPath=... <subcommand>
PATTERN_HOOKSPATH_INLINE="$_GIT_CMD"'-c[[:space:]]+core\.hooksPath'

# git config [--global|--local|--system|...] core.hooksPath ...
PATTERN_HOOKSPATH_CONFIG="$_GIT_CMD"'config[[:space:]]+(--[^[:space:]]+[[:space:]]+)?core\.hooksPath'

# ---------------------------------------------------------------------------
# gh API bypass patterns (remote ref deletion via GitHub REST API)
# ---------------------------------------------------------------------------

# gh api repos/OWNER/REPO/git/refs/heads/BRANCH -X DELETE
# gh api repos/OWNER/REPO/git/refs/heads/BRANCH --method DELETE
# (method flag AFTER the URL path)
PATTERN_GH_REF_DELETE_A='gh[[:space:]]+api[[:space:]].*git/refs/.*(-X|--method)[[:space:]]+DELETE'

# gh api -X DELETE repos/OWNER/REPO/git/refs/heads/BRANCH
# gh api --method DELETE repos/OWNER/REPO/git/refs/heads/BRANCH
# (method flag BEFORE the URL path)
PATTERN_GH_REF_DELETE_B='gh[[:space:]]+api[[:space:]].*(-X|--method)[[:space:]]+DELETE.*git/refs/'

# Read-only forms (--get, --get-all, --get-regexp). These never mutate state
# so they bypass the HOOKSPATH_OVERRIDE check, allowing debugging like
# `git config --get core.hooksPath` without setting TCS_GIT_HELPERS_SETUP_ACTIVE.
PATTERN_HOOKSPATH_CONFIG_READ="$_GIT_CMD"'config[[:space:]]+(--get|--get-all|--get-regexp)([[:space:]]+--[^[:space:]]+)*[[:space:]]+core\.hooksPath'

# Export pattern constants so child shells (e.g. when sourced from a hook
# script that re-execs in a subshell) see them too.
export \
  PATTERN_RESET_HARD \
  PATTERN_CLEAN_FORCE \
  PATTERN_CHECKOUT_DOT \
  PATTERN_CHECKOUT_PATH \
  PATTERN_RESTORE_DESTRUCTIVE \
  PATTERN_BRANCH_FORCE_DELETE \
  PATTERN_STASH_DESTROY \
  PATTERN_REFLOG_EXPIRE \
  PATTERN_NO_VERIFY \
  PATTERN_PUSH \
  PATTERN_PUSH_FORCE \
  PATTERN_PUSH_DELETE_FLAG \
  PATTERN_PUSH_COLON_DELETE \
  PATTERN_GH_REF_DELETE_A \
  PATTERN_GH_REF_DELETE_B \
  PATTERN_BRANCH_CREATE \
  PATTERN_BRANCH_RESUME \
  PATTERN_HOOKSPATH_INLINE \
  PATTERN_HOOKSPATH_CONFIG \
  PATTERN_HOOKSPATH_CONFIG_READ

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

# _match_command <command> <pattern>
#   Returns 0 if <command> matches <pattern> (POSIX ERE substring match), 1 otherwise.
#   <pattern> MUST be a POSIX ERE — never PCRE. See CON-9.
#
#   The right-hand side of [[ =~ ]] is intentionally unquoted so bash treats
#   it as a regex (quoting forces literal-string match in bash 3.2+).
_match_command() {
  local cmd="$1"
  local pattern="$2"
  [[ "$cmd" =~ $pattern ]]
}

# _is_git_token <token>
#   True iff <token> names the git binary: `git` or `<path>/git`, optionally
#   behind the opening quote of a `bash -c '…'` payload or a `$(`/backtick.
_is_git_token() {
  local t="$1"
  t="${t#\$(}"
  t="${t#[\'\"\`(]}"
  case "$t" in
    git|*/git) return 0 ;;
  esac
  return 1
}

# _hookspath_config_arg <name=value>
#   True iff the `-c`/`--config-env` argument sets core.hooksPath. git config
#   keys are case-insensitive, so `core.hookspath` counts too. bash 3.2 has no
#   ${v,,}; nocasematch is 3.1+ and is restored before returning.
_hookspath_config_arg() {
  local key="${1%%=*}" rc=1 restore=""
  shopt -q nocasematch || restore=1
  shopt -s nocasematch
  case "$key" in
    core.hookspath) rc=0 ;;
  esac
  [ -n "$restore" ] && shopt -u nocasematch
  return "$rc"
}

# _normalize_git_clause <clause>
#   Returns <clause> with git's global options removed from every git
#   invocation in it (#171): `git -C /r -c k=v --no-pager reset --hard` →
#   `git reset --hard`. The destructive patterns are written against the plain
#   form; without this, any global option in between disarmed 18 of them.
#
#   Options taking the NEXT token as their value: -C, -c, --git-dir,
#   --work-tree, --namespace, --config-env, --super-prefix. Every other
#   leading `-…` token (`--no-pager`, `-P`, `--bare`, the `=` forms) is
#   dropped alone. An unknown option is dropped too: that direction exposes
#   the subcommand, so the guard matches more, never less.
#
#   One exception: a -c/--config-env that sets core.hooksPath is re-emitted
#   as `-c core.hooksPath=…` so PATTERN_HOOKSPATH_INLINE still sees it, in
#   canonical case.
#
#   Tokens are rejoined with single spaces; patterns use [[:space:]]+, so that
#   loses nothing they look at. bash 3.2: `read -ra` and builtins only.
#
#   The result is left in _GIT_NORM rather than printed: a hot-path caller
#   (_with_normalized_clauses, once per clause on every Bash tool call) would
#   otherwise pay a `$(…)` subshell fork per clause. _normalize_git_clause
#   wraps it for callers that want stdout.
_GIT_NORM=""
_normalize_git_clause_into() {
  local -a toks
  local out="" i=0 n t v
  # Fast path: nothing to strip unless a dash token follows a git. No
  # here-string (a temp file in bash 3.2) for the common case.
  case "$1" in
    *git[[:space:]]*-*) ;;
    *) _GIT_NORM="$1"; return 0 ;;
  esac
  read -ra toks <<< "$1"
  n=${#toks[@]}
  while [ "$i" -lt "$n" ]; do
    t="${toks[$i]}"
    out="${out}${out:+ }${t}"
    i=$((i + 1))
    _is_git_token "$t" || continue
    while [ "$i" -lt "$n" ]; do
      t="${toks[$i]}"
      case "$t" in
        -C|--git-dir|--work-tree|--namespace|--super-prefix)
          i=$((i + 2)) ;;
        -c|--config-env)
          v="${toks[$((i + 1))]:-}"
          if _hookspath_config_arg "$v"; then
            out="${out} -c core.hooksPath=${v#*=}"
          fi
          i=$((i + 2)) ;;
        --config-env=*)
          v="${t#--config-env=}"
          if _hookspath_config_arg "$v"; then
            out="${out} -c core.hooksPath=${v#*=}"
          fi
          i=$((i + 1)) ;;
        -*)
          i=$((i + 1)) ;;
        *)
          break ;;
      esac
    done
  done
  _GIT_NORM="$out"
}

_normalize_git_clause() {
  _normalize_git_clause_into "$1"
  printf "%s" "$_GIT_NORM"
}

# _git_dash_c_dir <clause>
#   The directory the clause's first git invocation runs in, as named by its
#   `-C` options; empty when there are none. Successive -C values combine the
#   way git combines them: a relative one is joined onto the previous, an
#   absolute one resets. Relative results stay relative -- the caller resolves
#   them against its own working directory.
_git_dash_c_dir() {
  local -a toks
  local dir="" i=0 n t v
  read -ra toks <<< "$1"
  n=${#toks[@]}
  while [ "$i" -lt "$n" ]; do
    t="${toks[$i]}"
    i=$((i + 1))
    _is_git_token "$t" || continue
    while [ "$i" -lt "$n" ]; do
      t="${toks[$i]}"
      case "$t" in
        -C)
          v="${toks[$((i + 1))]:-}"
          case "$v" in
            /*) dir="$v" ;;
            "") ;;
            *) dir="${dir:+$dir/}$v" ;;
          esac
          i=$((i + 2)) ;;
        -c|--git-dir|--work-tree|--namespace|--config-env|--super-prefix)
          i=$((i + 2)) ;;
        -*)
          i=$((i + 1)) ;;
        *)
          break ;;
      esac
    done
    break
  done
  printf '%s' "$dir"
}

# _strip_quoted <command>
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
_strip_quoted() {
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

# _strip_heredocs <command>
#   Blanks heredoc BODIES, keeping the line that opens them.
#
#   A heredoc body is data on stdin — `git commit -F - <<EOF … EOF` carries a
#   commit message, and a destructive literal described in it is prose, not an
#   instruction. Must run BEFORE _strip_quoted: a quoted delimiter (<<'EOF')
#   would otherwise be blanked, leaving a `<<` with nothing to match the
#   terminator against, and the body still in scope.
#
#   Exception, same principle as _clausify's shell-executor guard: when the
#   heredoc feeds a shell (`bash <<EOF`), the body is CODE. Left intact.
#
#   Not stripped: `<<<` here-strings — those are single-line and _strip_quoted
#   already handles their quoting.
#
#   bash 3.2 compatible: read loop, no mapfile.
_strip_heredocs() {
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

# _clausify <command>
#   Returns <command> reduced to its real command clauses, one per line:
#     1. heredoc bodies blanked (via _strip_heredocs), then quoted content
#        blanked (via _strip_quoted), so git-op literals inside commit/PR
#        bodies, echo/printf payloads and heredocs disappear. Order matters:
#        a quoted delimiter (<<'EOF') must survive long enough to match its
#        own terminator. Command substitutions are NOT blanked — they execute,
#        so their content stays in scope and only their quoting is stripped;
#     2. shell separators (&&, ||, |, ;, &) normalized to newlines so an
#        unbounded `.*` in a pattern cannot bridge across into a sibling command.
#   Compute ONCE per hook invocation and reuse across patterns (the char-by-char
#   _strip_quoted is the only O(n) step; do it once, not per pattern — CON-2).
#
#   Separator order matters: two-char operators (&&, ||) FIRST, else `&`/`|`
#   would half-consume them. bash 3.2 compatible.
_clausify() {
  local s NL
  NL=$'\n'
  s="$1"
  # Shell-executor guard: when the command invokes a shell on a quoted payload
  # (`bash -c '…'`, `sh -c "…"`, `eval '…'`), that payload is CODE, not data —
  # a destructive op hidden in a subshell must still be caught. Leave it intact
  # (raw whole-command match) rather than blanking the quotes. Conservative: an
  # ambiguous executor falls back to the original substring behaviour.
  if [[ "$s" =~ (^|[^[:alnum:]_])[a-z]*sh[[:space:]]+-c([[:space:]]|$) ]] \
     || [[ "$s" =~ (^|[^[:alnum:]_])eval([[:space:]]|$) ]]; then
    _with_normalized_clauses "$s"
    return 0
  fi
  s="$(_strip_heredocs "$s")"
  s="$(_strip_quoted "$s")"
  s="${s//&&/$NL}"
  s="${s//||/$NL}"
  s="${s//|/$NL}"
  s="${s//;/$NL}"
  s="${s//&/$NL}"
  _with_normalized_clauses "$s"
}

# _with_normalized_clauses <clauses>
#   Prints each clause, followed -- when it differs -- by its
#   _normalize_git_clause form (#171). The raw clause stays first and in
#   place: a caller that maps a match back to its clause (_clause_target_dir)
#   reads the -C path from it, and no existing match is lost.
_with_normalized_clauses() {
  local clause norm out="" NL
  NL=$'\n'
  # Fast path: most Bash tool calls have no git with an option at all; they
  # pay nothing beyond this one glob test, as before #171.
  case "$1" in
    *git[[:space:]]*-*) ;;
    *) printf "%s" "$1"; return 0 ;;
  esac
  while IFS= read -r clause; do
    out="${out}${clause}${NL}"
    _normalize_git_clause_into "$clause"
    norm="$_GIT_NORM"
    if [ -n "$norm" ] && [ "$norm" != "$clause" ]; then
      out="${out}${norm}${NL}"
    fi
  done <<< "$1"
  printf '%s' "${out%"$NL"}"
}

# _match_clauses <clausified> <pattern>
#   True (0) iff <pattern> matches any clause of <clausified> (output of
#   _clausify). Use this — not raw _match_command against $CMD — for every
#   dispatch pattern, so a git-op literal quoted inside another command's
#   argument does not trip a false denial (#42 sibling fix).
#
#   Trade-off: a dangerous token that is itself a quoted required argument
#   (e.g. `git checkout -b "name with spaces"`, `git push o ":br"`) is blanked
#   and will not match. Such quoted forms are vanishingly rare and the inline
#   `CLAUDE_ALLOW_<RULE>=1` override remains available.
#
#   bash 3.2 compatible: here-string + read loop, no mapfile.
_match_clauses() {
  local clause
  while IFS= read -r clause; do
    _match_command "$clause" "$2" && return 0
  done <<< "$1"
  return 1
}

# _match_no_verify <command>
#   True (0) iff a genuine --no-verify / -n flag belongs to a `git commit` clause.
#   Splits on shell separators so PATTERN_NO_VERIFY's `.*` cannot bridge from
#   `git commit` into a sibling command's `-n` (e.g. `git commit && echo -n`).
#
#   Separator normalization order: two-char operators FIRST (&&, ||), then
#   single-char (|, ;, &), so `&&`/`||` are not half-consumed by `&`/`|`.
#   The here-string `<<<` appends a trailing newline which produces an empty
#   final clause; empty clauses cannot match PATTERN_NO_VERIFY.
#
#   bash 3.2 compatible: `${var//pat/repl}` and `<<<` are both available in
#   bash 3.2.57 (macOS default). `$'\n'` in parameter-substitution replacement
#   is handled via a NL variable to ensure compatibility.
_match_no_verify() {
  _match_clauses "$(_clausify "$1")" "$PATTERN_NO_VERIFY"
}
