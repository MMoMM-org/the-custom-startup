#!/usr/bin/env bats
# require-issue-comments.sh — PreToolUse:Bash guard.
# Blocks `gh issue view` calls that read an issue's text without its comments;
# a status-only read (`--json state`) and `--web` pass.

setup() {
  PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
  HOOK="${PLUGIN_ROOT}/scripts/require-issue-comments.sh"
  load "${PLUGIN_ROOT}/../tcs-helper/tests/bats/lib/assert"
}

_run_cmd() {
  local envelope
  envelope=$(jq -n --arg c "$1" '{tool_name: "Bash", tool_input: {command: $c}}')
  run bash "$HOOK" <<<"$envelope"
}

_assert_denied() {
  [ "$status" -eq 0 ]
  _has "$output" '"permissionDecision": "deny"'
  _has "$output" "--comments"
}

_assert_allowed() {
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "plain gh issue view is denied" {
  _run_cmd 'gh issue view 153'
  _assert_denied
}

@test "gh issue view with --comments is allowed" {
  _run_cmd 'gh issue view 153 --comments'
  _assert_allowed
}

@test "--json with body but without comments is denied" {
  _run_cmd "gh issue view 153 --json title,body --jq '.body'"
  _assert_denied
}

@test "--json=body form is denied" {
  _run_cmd 'gh issue view 153 --json=title,body'
  _assert_denied
}

@test "--json with body and comments is allowed" {
  _run_cmd "gh issue view 153 --json title,body,comments --jq '.body'"
  _assert_allowed
}

@test "status-only --json read is allowed" {
  _run_cmd 'gh issue view 262 --json state -q .state'
  _assert_allowed
}

@test "--web is allowed" {
  _run_cmd 'gh issue view 12 --web'
  _assert_allowed
}

@test "repo flag before the subcommand is still caught" {
  _run_cmd 'gh -R MMoMM-org/the-custom-startup issue view 5'
  _assert_denied
}

@test "one body read among several views is denied" {
  _run_cmd 'gh issue view 23 --json state; gh issue view 24 --json body'
  _assert_denied
}

@test "loop that requests comments for every issue is allowed" {
  _run_cmd 'for n in 250 251; do gh issue view $n --json title,body,comments; done'
  _assert_allowed
}

@test "quoted --json field list is read like an unquoted one" {
  _run_cmd 'gh issue view 7 --json "title,body"'
  _assert_denied
}

@test "quoted --json field list with comments is allowed" {
  _run_cmd "gh issue view 7 --json 'title,body,comments'"
  _assert_allowed
}

@test "other gh commands pass" {
  _run_cmd 'gh issue list --state open && gh pr view 3'
  _assert_allowed
}

@test "non-Bash tool passes" {
  run bash "$HOOK" <<<'{"tool_name":"Read","tool_input":{"file_path":"x"}}'
  _assert_allowed
}

@test "malformed stdin fails open" {
  run bash "$HOOK" <<<'not json gh issue view 1'
  _assert_allowed
}

# --- nudge-issue-list.sh: PostToolUse:Bash note after `gh issue list` ----------

_run_list() {
  local envelope
  envelope=$(jq -n --arg c "$1" '{tool_name: "Bash", tool_input: {command: $c}}')
  run bash "${PLUGIN_ROOT}/scripts/nudge-issue-list.sh" <<<"$envelope"
}

@test "gh issue list gets a note that titles are not enough" {
  _run_list 'gh issue list --state open --limit 15'
  [ "$status" -eq 0 ]
  _has "$output" '"hookEventName": "PostToolUse"'
  _has "$output" "--comments"
}

@test "gh issue list with a repo flag gets the note" {
  _run_list 'gh -R o/r issue list'
  _has "$output" '"additionalContext"'
}

@test "other commands get no note" {
  _run_list 'gh issue view 3 --comments && gh pr list'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "list nudge fails open on malformed stdin" {
  run bash "${PLUGIN_ROOT}/scripts/nudge-issue-list.sh" <<<'garbage gh issue list'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
