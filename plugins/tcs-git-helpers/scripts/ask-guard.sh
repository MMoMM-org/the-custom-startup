#!/bin/bash
# tcs-git-helpers: v2.6.0
# scripts/ask-guard.sh — opt-in PreToolUse guard for irreversible actions (#299).
#
# Answers "ask" (never "deny") when a Bash command or an Edit/Write/NotebookEdit
# target matches a rule in <repo>/.githooks/ask-guard.conf: a terraform apply,
# a production migration, an IAM change. Without that file the hook does
# nothing. The file sits under .githooks/, which protect-git-internals.sh and
# the sandbox template keep the agent from editing, so the agent cannot drop
# the rule that would ask about its own action.
#
# Config, one rule per line; `#` starts a comment line:
#   command <NAME> <POSIX ERE>   matched per command clause, quoted text blanked
#   path    <NAME> <glob>        matched against the repo-relative file path;
#                                `*` also crosses `/`
# NAME is [A-Z][A-Z0-9_]*. Lines that do not parse are skipped with a stderr
# warning naming the line.
#
# Override: CLAUDE_ALLOW_ASK_<NAME>=1 as the first token of the command, or in
# the environment (the only way for Edit/Write). Single-shot and audited by
# lib/override.sh; the master CLAUDE_ALLOW_GIT_BAD_OPS=1 also counts. Every
# ask is audited too (hook=ask-guard).
#
# Hook contract: stdin PreToolUse JSON; stdout the ask decision or nothing;
# exit always 0. Anything that cannot be read fails open: the call proceeds
# under the normal permission rules.
#
# bash 3.2: no declare -A, no mapfile; ERE with [[:space:]], never \s.

set -uo pipefail

INPUT=$(cat)

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null) || TOOL=""
case "$TOOL" in
  Bash|Edit|Write|NotebookEdit) ;;
  *) exit 0 ;;
esac

ROOT="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$ROOT" ]; then
  CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // ""' 2>/dev/null) || CWD=""
  ROOT=$(git -C "${CWD:-.}" rev-parse --show-toplevel 2>/dev/null) || ROOT=""
fi
[ -n "$ROOT" ] || exit 0
CONF="$ROOT/.githooks/ask-guard.conf"
# Off unless the repo opted in. This is the only cost on every call.
[ -r "$CONF" ] || exit 0

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=./lib/audit_log.sh disable=SC1091
. "$PLUGIN_ROOT/scripts/lib/audit_log.sh"
# shellcheck source=./lib/override.sh disable=SC1091
. "$PLUGIN_ROOT/scripts/lib/override.sh"
# shellcheck source=./lib/pattern_match.sh disable=SC1091
. "$PLUGIN_ROOT/scripts/lib/pattern_match.sh"

CMD=""
SUBJECT=""
if [ "$TOOL" = "Bash" ]; then
  CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null) || CMD=""
  [ -n "$CMD" ] || exit 0
  KIND="command"
  WHAT="command"
  CLAUSES=$(_clausify "$CMD")
  SUBJECT="$CMD"
else
  FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' 2>/dev/null) || FILE=""
  [ -n "$FILE" ] || exit 0
  KIND="path"
  WHAT="write"
  case "$FILE" in
    "$ROOT"/*) REL="${FILE#"$ROOT"/}" ;;
    /*) exit 0 ;;              # outside the repo: no repo rule applies
    *) REL="${FILE#./}" ;;
  esac
  SUBJECT="<edit:>$FILE"
fi

HITS=""      # space-separated rule names, each once
lineno=0
while IFS= read -r raw || [ -n "$raw" ]; do
  lineno=$((lineno + 1))
  line="${raw%$'\r'}"
  line="${line#"${line%%[![:space:]]*}"}"
  case "$line" in ''|\#*) continue ;; esac

  kind="${line%%[[:space:]]*}"
  rest="${line#"$kind"}"; rest="${rest#"${rest%%[![:space:]]*}"}"
  name="${rest%%[[:space:]]*}"
  value="${rest#"$name"}"; value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"

  case "$kind" in
    command|path) ;;
    *) printf 'tcs-git-helpers ask-guard: %s line %d: kind must be command or path, skipped\n' "$CONF" "$lineno" >&2; continue ;;
  esac
  if ! [[ "$name" =~ ^[A-Z][A-Z0-9_]*$ ]] || [ -z "$value" ]; then
    printf 'tcs-git-helpers ask-guard: %s line %d: expected "%s NAME <pattern>" with NAME in A-Z0-9_, skipped\n' "$CONF" "$lineno" "$kind" >&2
    continue
  fi
  if [ "$kind" = "command" ]; then
    # [[ =~ ]] returns 2 for a regex that does not compile.
    [[ "" =~ $value ]]
    if [ "$?" -eq 2 ]; then
      printf 'tcs-git-helpers ask-guard: %s line %d: invalid regex, skipped\n' "$CONF" "$lineno" >&2
      continue
    fi
  fi

  [ "$kind" = "$KIND" ] || continue
  case " $HITS " in *" $name "*) continue ;; esac

  if [ "$KIND" = "command" ]; then
    _match_clauses "$CLAUSES" "$value" || continue
  else
    # shellcheck disable=SC2254  # the configured glob is meant to match
    case "$REL" in $value) ;; *) continue ;; esac
  fi
  HITS="${HITS:+$HITS }$name"
done < "$CONF"

[ -n "$HITS" ] || exit 0

ASK=""
for name in $HITS; do
  if _check_and_consume_override "ASK_$name" 2>/dev/null; then
    continue
  fi
  ASK="${ASK:+$ASK }$name"
  _audit_log hook=ask-guard env_var="CLAUDE_ALLOW_ASK_$name" master=false \
    command="$SUBJECT" pattern="$name" >/dev/null 2>&1 || true
done

[ -n "$ASK" ] || exit 0

rules=""
skip=""
for name in $ASK; do
  rules="${rules:+$rules }[$name]"
  skip="${skip:+$skip, }CLAUDE_ALLOW_ASK_${name}=1"
done
REASON="tcs-git-helpers ask-guard ${rules}: this ${WHAT} matches a rule in .githooks/ask-guard.conf for irreversible or high-cost actions. Approve only if you intend it. To skip this prompt once: ${skip}. See references/ask-guard.md."

jq -nc --arg reason "$REASON" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "ask",
    permissionDecisionReason: $reason
  }
}'
exit 0
