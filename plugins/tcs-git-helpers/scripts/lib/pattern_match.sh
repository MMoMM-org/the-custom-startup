#!/usr/bin/env bash
# scripts/lib/pattern_match.sh — POSIX ERE patterns for destructive git ops
#
# CONSTRAINTS (CON-1, CON-9 from SDD):
#   - bash 3.2 compatible (macOS default `/bin/bash` 3.2.57).
#   - All patterns use POSIX ERE: [[:space:]]+ for whitespace,
#     [[:<:]] / [[:>:]] for word boundaries, [^[:space:]]+ for non-space.
#   - NEVER use \s, \S, \b — they are PCRE/Perl extensions and silently
#     do NOT match in bash 3.2 [[ =~ ]] (POSIX ERE only).
#     Empirically verified: `[[ "git push" =~ git\s+push ]]` evaluates false;
#     `[[ "git push" =~ git[[:space:]]+push ]]` evaluates true.
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
#    14. git checkout -b / git switch -c     -> PATTERN_BRANCH_CREATE  [M2]
#    15. git checkout / git switch <branch>  -> PATTERN_BRANCH_RESUME  [M3]
#    16. git -c core.hooksPath=...           -> PATTERN_HOOKSPATH_INLINE
#    17. git config core.hooksPath ...       -> PATTERN_HOOKSPATH_CONFIG

# ---------------------------------------------------------------------------
# Destructive operation patterns (PRD §Feature M7)
# ---------------------------------------------------------------------------

# git reset --hard [<ref>]
PATTERN_RESET_HARD='git[[:space:]]+reset[[:space:]]+--hard[[:>:]]'

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
PATTERN_BRANCH_FORCE_DELETE='git[[:space:]]+branch[[:space:]]+-D[[:>:]]'

# git stash drop / git stash clear
PATTERN_STASH_DESTROY='git[[:space:]]+stash[[:space:]]+(drop|clear)[[:>:]]'

# git reflog expire ...   (kills the recovery net)
PATTERN_REFLOG_EXPIRE='git[[:space:]]+reflog[[:space:]]+expire[[:>:]]'

# git commit ... --no-verify   |   git commit ... -n
# Caveat: bundled-flag forms like `-nm "msg"` (shell-parsed as -n + -m) are NOT
# detected — `[[:>:]]` requires a word→non-word transition, and `n` followed by
# another word char (`m`) has none. Accepted trade-off: PRD M7 lists `-n` as the
# canonical form. Widening to `-[a-zA-Z]*n` would also flag the discrete flag
# bundle `-an` (= -a + -n) which is correct in spirit, but the design choice in
# v1.0 is to stay specific to the canonical forms documented in the PRD.
PATTERN_NO_VERIFY='git[[:space:]]+commit.*(--no-verify|-n[[:>:]])'

# ---------------------------------------------------------------------------
# Push patterns (M1 closed-PR check + M7 destructive push variants)
# ---------------------------------------------------------------------------

# git push (any form) — used by M1 closed-PR check; not destructive on its own
PATTERN_PUSH='git[[:space:]]+push[[:>:]]'

# git push ... --force   (NEGATIVE: must NOT match --force-with-lease)
#
# Why not just [[:>:]] after --force? Because [[:>:]] matches between a word
# char and a non-word char — and `-` is non-word, so [[:>:]] DOES match
# between `e` and `-` in `--force-with-lease`. We instead require the next
# char after `--force` to be whitespace OR end-of-string.
PATTERN_PUSH_FORCE='git[[:space:]]+push[[:space:]].*--force([[:space:]]|$)'

# git push ... --delete <branch>   (long-form remote branch delete)
PATTERN_PUSH_DELETE_FLAG='git[[:space:]]+push[[:space:]]+(.+[[:space:]]+)?--delete[[:>:]]'

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
