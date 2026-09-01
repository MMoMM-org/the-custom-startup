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

# git reset --hard [<ref>]
PATTERN_RESET_HARD='git[[:space:]]+reset[[:space:]]+--hard([^[:alnum:]_]|$)'

# git clean -f / -fx / -fX / -Xf / -dfx / --force  (any bundle containing f or x, --force)
# `-[a-zA-Z]*[fx]` allows uppercase neighbours (e.g. `-fX`, `-Xf`) — `-X` removes
# only ignored files which is destructive when combined with `-f`. Substring-match
# means trailing `X` after a matched `-f` does not block the match.
PATTERN_CLEAN_FORCE='git[[:space:]]+clean[[:space:]]+(-[a-zA-Z]*[fx]|--force)'

# git checkout .   (require . to be its own argument: end-of-string or whitespace next)
PATTERN_CHECKOUT_DOT='git[[:space:]]+checkout[[:space:]]+\.([[:space:]]|$)'

# git checkout -- <path>
PATTERN_CHECKOUT_PATH='git[[:space:]]+checkout[[:space:]]+--[[:space:]]+[^[:space:]]+'

# git restore --worktree --source=<ref> ...   OR   --source=<ref> --worktree ...   OR   --staged ...
# Both flag orderings of --worktree + --source are equally valid git invocations
# and equally destructive — match either.
PATTERN_RESTORE_DESTRUCTIVE='git[[:space:]]+restore[[:space:]]+(.*--worktree.*--source.*|.*--source.*--worktree.*|.*--staged.*)'

# git branch -D <name>   (capital D = force delete; lowercase -d is the safe form)
PATTERN_BRANCH_FORCE_DELETE='git[[:space:]]+branch[[:space:]]+-D([^[:alnum:]_]|$)'

# git stash drop / git stash clear
PATTERN_STASH_DESTROY='git[[:space:]]+stash[[:space:]]+(drop|clear)([^[:alnum:]_]|$)'

# git reflog expire ...   (kills the recovery net)
PATTERN_REFLOG_EXPIRE='git[[:space:]]+reflog[[:space:]]+expire([^[:alnum:]_]|$)'

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
PATTERN_NO_VERIFY='git[[:space:]]+commit.*(--no-verify|-n([^[:alnum:]_]|$))'

# ---------------------------------------------------------------------------
# Push patterns (M1 closed-PR check + M7 destructive push variants)
# ---------------------------------------------------------------------------

# git push (any form) — used by M1 closed-PR check; not destructive on its own
PATTERN_PUSH='git[[:space:]]+push([^[:alnum:]_]|$)'

# git push ... --force   (NEGATIVE: must NOT match --force-with-lease)
#
# Why not the usual ([^[:alnum:]_]|$) boundary after `--force`? Because it
# accepts any non-word char — and `-` is non-word, so it DOES match between
# `e` and `-` in `--force-with-lease`. We instead require the next char
# after `--force` to be whitespace OR end-of-string.
PATTERN_PUSH_FORCE='git[[:space:]]+push[[:space:]].*--force([[:space:]]|$)'

# git push ... --delete <branch>   (long-form remote branch delete)
PATTERN_PUSH_DELETE_FLAG='git[[:space:]]+push[[:space:]]+(.+[[:space:]]+)?--delete([^[:alnum:]_]|$)'

# git push <remote> :<branch>   (refspec-form remote branch delete)
PATTERN_PUSH_COLON_DELETE='git[[:space:]]+push[[:space:]]+[^[:space:]]+[[:space:]]+:[^[:space:]]+'

# ---------------------------------------------------------------------------
# Branch create / resume (M2 / M3)
# ---------------------------------------------------------------------------

# git checkout -b <name>   |   git switch -c <name>
PATTERN_BRANCH_CREATE='git[[:space:]]+(checkout[[:space:]]+-b|switch[[:space:]]+-c)[[:space:]]+[^[:space:]]+'

# git checkout <branch>   |   git switch <branch>   (bare; not a flag, not a path)
# Anchored with $ so trailing args are not allowed (avoids matching pathspec forms).
# The capture excludes leading `-` (so `-b`/`-c` flag forms do NOT match) and
# leading `.` (so `git checkout .` and `git checkout .githooks` do NOT match —
# those are pathspecs, handled by PATTERN_CHECKOUT_DOT / PATTERN_CHECKOUT_PATH).
PATTERN_BRANCH_RESUME='git[[:space:]]+(checkout|switch)[[:space:]]+([^-.[:space:]][^[:space:]]*)$'

# ---------------------------------------------------------------------------
# core.hooksPath subversion (defeats .githooks/)
# ---------------------------------------------------------------------------

# git -c core.hooksPath=... <subcommand>
PATTERN_HOOKSPATH_INLINE='git[[:space:]]+-c[[:space:]]+core\.hooksPath'

# git config [--global|--local|--system|...] core.hooksPath ...
PATTERN_HOOKSPATH_CONFIG='git[[:space:]]+config[[:space:]]+(--[^[:space:]]+[[:space:]]+)?core\.hooksPath'

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
PATTERN_HOOKSPATH_CONFIG_READ='git[[:space:]]+config[[:space:]]+(--get|--get-all|--get-regexp)([[:space:]]+--[^[:space:]]+)*[[:space:]]+core\.hooksPath'

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
  local in_sq=0 in_dq=0
  local ch prev=""
  while [ "$i" -lt "$len" ]; do
    ch="${cmd:$i:1}"
    if [ "$in_sq" -eq 1 ]; then
      if [ "$ch" = "'" ]; then
        in_sq=0
      fi
      out="${out} "
    elif [ "$in_dq" -eq 1 ]; then
      if [ "$ch" = '"' ] && [ "$prev" != "\\" ]; then
        in_dq=0
      fi
      out="${out} "
    else
      case "$ch" in
        "'") in_sq=1; out="${out} " ;;
        '"') in_dq=1; out="${out} " ;;
        *)   out="${out}${ch}" ;;
      esac
    fi
    prev="$ch"
    i=$((i + 1))
  done
  printf '%s' "$out"
}

# _clausify <command>
#   Returns <command> reduced to its real command clauses, one per line:
#     1. quoted content blanked (via _strip_quoted) so git-op literals inside
#        commit/PR bodies, echo/printf payloads, and heredocs disappear;
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
    printf '%s' "$s"
    return 0
  fi
  s="$(_strip_quoted "$s")"
  s="${s//&&/$NL}"
  s="${s//||/$NL}"
  s="${s//|/$NL}"
  s="${s//;/$NL}"
  s="${s//&/$NL}"
  printf '%s' "$s"
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
