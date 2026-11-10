#!/usr/bin/env bats
#
# tests/bats/command_corpus.bats
#
# Runs every line of tests/fixtures/commands/{destructive,bypass}_corpus.txt
# through the real PreToolUse dispatcher (scripts/block-bad-git-ops.sh) and
# checks its decision -- and, for a deny, that the named rule is the one that
# fired (#268). The corpora were written in T1.9 but never executed against
# the hook, so lines such as `sh -c "git push --force"` and `git clean -ndx`
# sat in them with the wrong outcome.
#
# Line format: <decision>\t<rule>\t<command>; rule NEGATIVE / DOCUMENTED_LIMITATION
# carries no rule name to check.
#
# The hook runs in a clean repository on `main` with no reachable `gh`, so the
# stateful rules (closed PR, branch from unfinished work, resumed merged
# branch) stay quiet and only the command shape decides.

bats_require_minimum_version 1.5.0

setup_file() {
  command -v jq >/dev/null || skip "jq required"
  export CORPUS_PLUGIN_ROOT
  CORPUS_PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export CORPUS_REPO="$BATS_FILE_TMPDIR/repo"
  export CORPUS_BIN="$BATS_FILE_TMPDIR/bin"
  export GIT_CONFIG_GLOBAL=/dev/null
  git init -q -b main "$CORPUS_REPO"
  # A committed directory, for the `git restore <dir>` filesystem check.
  mkdir -p "$CORPUS_REPO/src"
  printf 'a\n' > "$CORPUS_REPO/src/a.txt"
  git -C "$CORPUS_REPO" add src/a.txt
  git -C "$CORPUS_REPO" -c user.email=t@example.com -c user.name=t \
    commit -q -m init
  # gh outside the repo, so the tree stays clean: always fails = no PR info.
  mkdir -p "$CORPUS_BIN"
  printf '#!/bin/sh\nexit 1\n' > "$CORPUS_BIN/gh"
  chmod +x "$CORPUS_BIN/gh"
}

# _run_corpus <file> -- prints one line per mismatch; prints nothing when all agree.
_run_corpus() {
  local hook="$CORPUS_PLUGIN_ROOT/scripts/block-bad-git-ops.sh"
  local decision rule cmd out got
  while IFS=$'\t' read -r decision rule cmd; do
    case "$decision" in ''|'#'*) continue ;; esac
    out=$(cd "$CORPUS_REPO" && jq -nc --arg c "$cmd" \
      '{tool_name:"Bash",tool_input:{command:$c}}' \
      | PATH="$CORPUS_BIN:$PATH" bash "$hook" 2>/dev/null)
    got=allow
    case "$out" in *'"permissionDecision":"deny"'*) got=deny ;; esac
    if [ "$got" != "$decision" ]; then
      printf 'want %s, got %s: %s\n' "$decision" "$got" "$cmd"
    elif [ "$got" = deny ]; then
      case "$rule" in NEGATIVE|DOCUMENTED_LIMITATION) continue ;; esac
      case "$out" in
        *"[$rule]"*) ;;
        *) printf 'denied, but not by %s: %s\n' "$rule" "$cmd" ;;
      esac
    fi
  done < "$1"
}

@test "destructive corpus: every line gets its expected decision and rule" {
  local mismatches
  mismatches=$(_run_corpus "$CORPUS_PLUGIN_ROOT/tests/fixtures/commands/destructive_corpus.txt")
  if [ -n "$mismatches" ]; then
    printf '%s\n' "$mismatches" >&2
    return 1
  fi
}

@test "bypass corpus: every line gets its expected decision and rule" {
  local mismatches
  mismatches=$(_run_corpus "$CORPUS_PLUGIN_ROOT/tests/fixtures/commands/bypass_corpus.txt")
  if [ -n "$mismatches" ]; then
    printf '%s\n' "$mismatches" >&2
    return 1
  fi
}

@test "the corpus runner reports a mismatch (it can fail)" {
  local bad="$BATS_TEST_TMPDIR/bad.txt"
  printf 'allow\tNEGATIVE\tgit reset --hard\ndeny\tFORCE_PUSH\tgit reset --hard\n' > "$bad"
  run _run_corpus "$bad"
  [ "${#lines[@]}" -eq 2 ]
}
