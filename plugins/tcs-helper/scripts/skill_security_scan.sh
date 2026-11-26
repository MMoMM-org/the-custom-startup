#!/bin/bash
# skill_security_scan.sh — supply-chain scan of a skill or plugin directory
# before it is imported or adopted. Used by skill-import and skill-evaluate.
#
# Usage: skill_security_scan.sh <dir>
#
# Prints one tab-separated line per hit, paths relative to <dir>:
#   EXECUTABLE<TAB><path><TAB><why>        every file that can run code
#   <CATEGORY><TAB><path>:<line><TAB><excerpt>
# CATEGORY is NETWORK, CREDENTIALS, DYNAMIC_EXEC, WRITE_OUTSIDE or
# INSTRUCTION_OVERRIDE. Hits are leads for a human or model to read in
# context, not verdicts; an empty result does not prove a skill safe.
#
# Exit: 0 no CATEGORY hit (EXECUTABLE lines alone), 1 at least one, 2 usage.
#
# Patterns are POSIX ERE with literals in brackets ([.] [$] [|]) so BSD and
# GNU grep read them alike; no \s or \b (bash 3.2 / BSD grep).

set -u

dir="${1:-}"
if [ -z "$dir" ] || [ ! -d "$dir" ]; then
  echo "usage: skill_security_scan.sh <dir>" >&2
  exit 2
fi
cd "$dir" || exit 2

B='(^|[^[:alnum:]_.-])'   # word start
E='([^[:alnum:]_-]|$)'    # word end

NETWORK="${B}(curl|wget|nc|ncat|netcat|socat|telnet|scp|rsync|ssh)([[:space:]]|$)|${B}fetch[(]|XMLHttpRequest|${B}requests[.](get|post|put|patch|delete)[(]|urllib|http[.]client|${B}socket[.]|Invoke-WebRequest|/dev/tcp/"

CREDENTIALS="[.]ssh/|id_rsa|id_ed25519|[.]aws/|[.]config/gcloud|[.]azure/|[.]kube/config|[.]netrc|[.]npmrc|[.]pypirc|[.]docker/config[.]json|[.]git-credentials|(^|[^[:alnum:]_])[.]env([^[:alnum:]_]|$)|security (find|dump)-[a-z-]*password|[Kk]eychain|gh auth token"

# eval followed by a quote, $ or backtick, or eval(: prose "an eval run" is not code.
EVAL_ARG='[[:space:]]+["$`'"'"']'
DYNAMIC_EXEC="${B}eval(${EVAL_ARG}|[(])|base64 +(-d|-D|--decode)|[|][[:space:]]*(sudo +)?(ba|z|da|k)?sh${E}|[|][[:space:]]*python[0-9.]*${E}|source +<[(]|${B}exec[(]|new Function[(]|child_process|os[.]system[(]|shell=True"

WRITE_OUTSIDE=">>?[[:space:]]*\"?(~|[$][{]?HOME|/(etc|usr|opt|Library|var|private)/)|${B}(tee|cp|mv|install|ln|rm|chmod|chown)[[:space:]].*(~/|[$][{]?HOME[}]?/|[[:space:]]/(etc|usr|opt|Library)/)|${B}(crontab|launchctl)${E}|systemctl +--user|[.](bashrc|zshrc|bash_profile|zprofile|profile)${E}"

# Matched case-insensitively.
INSTRUCTION_OVERRIDE="(ignore|disregard|forget) +(all +|any +)?(of +)?(the +|your +|my +)?(previous|prior|above|earlier|preceding|other|system|user'?s?|claude[.]md)|(takes?|take) +precedence +over|(override|overrides|overrule|supersedes?) +(all +|any +)?(the +|your +)?(user'?s? +|system +|previous +|prior +)?(instructions|rules|system prompt|claude[.]md)|you +are +(now|no +longer)|your +(new|real|true|actual) +(role|identity|instructions|purpose)|(do not|don'?t|never) +(tell|inform|mention|show|reveal|report|notify)[a-z ]{0,30}user|without +(telling|informing|asking|notifying|showing|alerting) +(the +)?user|(hide|conceal) +[a-z ]{0,30}from +(the +)?user|silently +(run|execute|install|send|upload|delete|modify|change|write)|(bypass|disable|circumvent) +(the +|any +|all +)?(permission|sandbox|hook|safety|confirmation|approval)"

found=0

# --- executables -----------------------------------------------------------
while IFS= read -r f; do
  f="${f#./}"
  base="${f##*/}"
  why=""
  case "$base" in
    hooks.json) why="hook config" ;;
    .mcp.json) why="MCP config" ;;
    *.sh|*.bash|*.zsh|*.py|*.js|*.cjs|*.mjs|*.ts|*.rb|*.pl|*.ps1) why="script (.${base##*.})" ;;
  esac
  if [ -z "$why" ] && [ "$(head -c 2 "$f" 2>/dev/null)" = "#!" ]; then
    why="shebang"
  fi
  if [ -z "$why" ] && [ -x "$f" ]; then
    why="executable bit"
  fi
  if [ -z "$why" ] && [ "$base" = "settings.json" ] && grep -q '"hooks"' "$f" 2>/dev/null; then
    why="hook config"
  fi
  [ -n "$why" ] && printf 'EXECUTABLE\t%s\t%s\n' "$f" "$why"
done < <(find . -type f ! -path './.git/*' | LC_ALL=C sort)

# --- content patterns ------------------------------------------------------
_scan() {
  local cat="$1" pat="$2" flags="$3" hits line path rest
  hits=$(grep -rnIE "$flags" -- "$pat" . 2>/dev/null | LC_ALL=C sort -t: -k1,1 -k2,2n) || hits=""
  [ -n "$hits" ] || return 0
  found=1
  while IFS= read -r line; do
    path="${line%%:*}"; rest="${line#*:}"
    path="${path#./}"
    local num="${rest%%:*}" text="${rest#*:}"
    text=$(printf '%s' "$text" | tr '\t' ' ' | sed 's/^[[:space:]]*//' | cut -c1-160)
    printf '%s\t%s:%s\t%s\n' "$cat" "$path" "$num" "$text"
  done <<EOF
$hits
EOF
}

_scan NETWORK "$NETWORK" "-s"
_scan CREDENTIALS "$CREDENTIALS" "-s"
_scan DYNAMIC_EXEC "$DYNAMIC_EXEC" "-s"
_scan WRITE_OUTSIDE "$WRITE_OUTSIDE" "-s"
_scan INSTRUCTION_OVERRIDE "$INSTRUCTION_OVERRIDE" "-si"

exit "$found"
