#!/usr/bin/env bats
#
# tests/bats/sandbox_settings.bats
#
# skills/git-setup/lib/sandbox_settings.sh (#303): merges
# templates/claude-settings/sandbox-git.json into .claude/settings.json,
# additively and idempotently.

bats_require_minimum_version 1.5.0

load 'lib/helpers'

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HELPER="$PLUGIN_ROOT/skills/git-setup/lib/sandbox_settings.sh"
  TEMPLATE="$PLUGIN_ROOT/templates/claude-settings/sandbox-git.json"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  REPO="$BATS_TEST_TMPDIR/repo"
  git init -q -b main "$REPO"
  SETTINGS="$REPO/.claude/settings.json"
  cd "$REPO"
}

@test "S1 template is valid JSON and protects .githooks" {
  run jq -e '.sandbox.filesystem.denyWrite | index("./.githooks")' "$TEMPLATE"
  [ "$status" -eq 0 ]
}

@test "S2 --diff on a repo without settings shows the change and writes nothing" {
  run "$HELPER" --diff
  [ "$status" -eq 0 ]
  _has "$output" "PENDING $SETTINGS"
  _has "$output" '+      "git push *",'
  [ ! -e "$SETTINGS" ]
}

@test "S3 --apply writes every template entry, then a re-run is a no-op" {
  run "$HELPER" --apply
  [ "$status" -eq 0 ]
  _has "$output" "WRITTEN $SETTINGS"
  [ "$(jq -S . "$SETTINGS")" = "$(jq -S . "$TEMPLATE")" ]
  before="$(cat "$SETTINGS")"
  run "$HELPER" --apply
  [ "$status" -eq 0 ]
  _has "$output" "UP-TO-DATE $SETTINGS"
  [ "$(cat "$SETTINGS")" = "$before" ]
}

@test "S4 existing keys and entries are kept, order kept, nothing duplicated" {
  mkdir -p "$REPO/.claude"
  cat > "$SETTINGS" <<'JSON'
{
  "model": "sonnet",
  "permissions": { "allow": ["Bash(ls *)"], "ask": ["Bash(rm *)", "Bash(git remote add *)"] },
  "sandbox": { "enabled": true, "excludedCommands": ["docker *", "gh *"] }
}
JSON
  run "$HELPER" --apply
  [ "$status" -eq 0 ]
  [ "$(jq -r .model "$SETTINGS")" = "sonnet" ]
  [ "$(jq -r .sandbox.enabled "$SETTINGS")" = "true" ]
  [ "$(jq -c .permissions.allow "$SETTINGS")" = '["Bash(ls *)"]' ]
  [ "$(jq -r '.permissions.ask[0]' "$SETTINGS")" = "Bash(rm *)" ]
  [ "$(jq -r '.sandbox.excludedCommands[0]' "$SETTINGS")" = "docker *" ]
  [ "$(jq '[.sandbox.excludedCommands[] | select(. == "gh *")] | length' "$SETTINGS")" -eq 1 ]
  [ "$(jq '[.permissions.ask[] | select(. == "Bash(git remote add *)")] | length' "$SETTINGS")" -eq 1 ]
  [ "$(jq -r '.sandbox.filesystem.denyWrite[0]' "$SETTINGS")" = "./.githooks" ]
}

@test "S5 invalid JSON is refused and left untouched" {
  mkdir -p "$REPO/.claude"
  printf '{ not json\n' > "$SETTINGS"
  run -1 "$HELPER" --apply
  _has "$output" "is not a JSON object"
  [ "$(cat "$SETTINGS")" = "{ not json" ]
}

@test "S6 a non-array where the template has an array is refused" {
  mkdir -p "$REPO/.claude"
  printf '{"sandbox":{"excludedCommands":"git push *"}}\n' > "$SETTINGS"
  run -1 "$HELPER" --apply
  _has "$output" "cannot merge"
  [ "$(jq -r .sandbox.excludedCommands "$SETTINGS")" = "git push *" ]
}

@test "S7 no mode argument exits 1" {
  run -1 "$HELPER"
}

@test "S8 helper is shellcheck-clean" {
  command -v shellcheck >/dev/null 2>&1 || skip "shellcheck not installed"
  run shellcheck "$HELPER"
  [ "$status" -eq 0 ]
}
