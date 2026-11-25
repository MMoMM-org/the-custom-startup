#!/bin/bash
# tests/manual/host-sandbox-git-check.sh — run the #303 scripts on a macOS
# host under the system bash 3.2 and BSD tools, without bats.
#
#   /bin/bash plugins/tcs-git-helpers/tests/manual/host-sandbox-git-check.sh
#
# Needs only git and jq (/usr/bin/jq ships with macOS 15+). Installs nothing,
# writes only to a temp dir it removes. Each script is run as `/bin/bash
# <script>`, so a newer bash on PATH cannot hide a bash 3.2 failure.
#
# Exit: 0 all passed, 1 a check failed, 2 a prerequisite is missing.

# Each check passes the status of the condition just before it on purpose.
# shellcheck disable=SC2319

set -u

HERE="$(cd "$(dirname "$0")" && pwd -P)"
PLUGIN_ROOT="$(cd "$HERE/../.." && pwd -P)"
REPAIR="$PLUGIN_ROOT/scripts/git-sandbox-repair.sh"
HELPER="$PLUGIN_ROOT/skills/git-setup/lib/sandbox_settings.sh"
TEMPLATE="$PLUGIN_ROOT/templates/claude-settings/sandbox-git.json"

for tool in git jq; do
  command -v "$tool" >/dev/null 2>&1 || { printf 'MISSING %s\n' "$tool"; exit 2; }
done

printf 'bash: %s\n' "$(/bin/bash -c 'echo $BASH_VERSION')"
printf 'git:  %s\n' "$(git --version)"
printf 'jq:   %s (%s)\n\n' "$(jq --version)" "$(command -v jq)"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/tcs-host-check.XXXXXX")" || exit 2
trap 'rm -rf "$WORK"' EXIT
WORK="$(cd "$WORK" && pwd -P)"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com
export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com

FAILED=0
_check() { # name, condition result (0 = pass), detail
  if [ "$2" -eq 0 ]; then
    printf 'PASS %s\n' "$1"
  else
    printf 'FAIL %s\n%s\n' "$1" "$3" | sed '2,$s/^/     /'
    FAILED=1
  fi
}

# Fresh repo with a pushed main and an unpushed feat branch.
_repo() {
  rm -rf "$WORK/remote.git" "$WORK/repo"
  git init -q --bare "$WORK/remote.git"
  git init -q "$WORK/repo"
  cd "$WORK/repo" || exit 2
  git checkout -q -b main
  git commit -q --allow-empty -m init
  git remote add origin "$WORK/remote.git"
  git push -q -u origin main 2>/dev/null
  git checkout -q -b feat
  printf 'x\n' > f.txt
  git add f.txt
  git commit -q -m feat
}

# --- git-sandbox-repair.sh ---------------------------------------------------
_repo
git push -q origin feat 2>/dev/null
out="$(/bin/bash "$REPAIR" 2>&1)"; rc=$?
up="$(git rev-parse --abbrev-ref 'feat@{upstream}' 2>/dev/null)"
[ "$rc" -eq 0 ] && [ "$up" = "origin/feat" ]
_check "repair: missing upstream is set" $? "rc=$rc upstream=$up
$out"

_repo
git checkout -q main
git read-tree feat
out="$(/bin/bash "$REPAIR" 2>&1)"; rc=$?
head_now="$(git symbolic-ref --short HEAD)"
[ "$rc" -eq 2 ] && [ "$head_now" = "main" ] \
  && printf '%s' "$out" | grep -qF "REPORT index matches branch 'feat' but HEAD is on 'main'"
_check "repair: index/HEAD mismatch reported, HEAD left alone (bash 3.2 parse)" $? "rc=$rc HEAD=$head_now
$out"

_repo
printf 'y\n' > g.txt
git add g.txt
out="$(/bin/bash "$REPAIR" 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && ! printf '%s' "$out" | grep -q REPORT
_check "repair: staged work is not reported" $? "rc=$rc
$out"

# --- sandbox_settings.sh -----------------------------------------------------
_repo
out="$(/bin/bash "$HELPER" --diff 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && [ ! -e .claude/settings.json ] \
  && printf '%s' "$out" | grep -qF 'PENDING' \
  && printf '%s' "$out" | grep -qF '+      "git push *",'
_check "settings: --diff shows the change, writes nothing (no /dev/fd)" $? "rc=$rc
$out"

out="$(/bin/bash "$HELPER" --apply 2>&1)"; rc=$?
same=1
[ "$(jq -S . .claude/settings.json 2>/dev/null)" = "$(jq -S . "$TEMPLATE")" ] && same=0
[ "$rc" -eq 0 ] && [ "$same" -eq 0 ]
_check "settings: --apply writes the template" $? "rc=$rc
$out"

before="$(cat .claude/settings.json)"
out="$(/bin/bash "$HELPER" --apply 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && [ "$(cat .claude/settings.json)" = "$before" ] \
  && printf '%s' "$out" | grep -qF 'UP-TO-DATE'
_check "settings: re-run is a no-op" $? "rc=$rc
$out"

printf '{"model":"sonnet","sandbox":{"excludedCommands":["docker *","gh *"]}}\n' > .claude/settings.json
out="$(/bin/bash "$HELPER" --apply 2>&1)"; rc=$?
[ "$rc" -eq 0 ] \
  && [ "$(jq -r .model .claude/settings.json)" = "sonnet" ] \
  && [ "$(jq -r '.sandbox.excludedCommands[0]' .claude/settings.json)" = "docker *" ] \
  && [ "$(jq '[.sandbox.excludedCommands[] | select(. == "gh *")] | length' .claude/settings.json)" -eq 1 ]
_check "settings: existing keys kept, no duplicates" $? "rc=$rc
$out
$(cat .claude/settings.json)"

printf '\n'
if [ "$FAILED" -eq 0 ]; then printf 'ALL PASSED\n'; else printf 'FAILURES above\n'; fi
exit "$FAILED"
