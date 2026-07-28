#!/usr/bin/env bats
# Tests for scripts/block-eslint-disable.sh.
#
# Coverage:
#   - Tool gate: non-editing tools / empty file_path → exit 0 silent
#   - Scope gate: non-Obsidian repo, non-repo path, Markdown → exit 0 silent
#   - Deny: eslint-disable in Write content / Edit new_string
#   - Deny: rule mapped to "off" in eslint.config.js
#   - Allow: a disable present only in old_string (i.e. being removed)
#   - Allow: CLAUDE_ALLOW_ESLINT_DISABLE=1 escape hatch
#   - Repo detection via package.json "obsidian" dependency
#   - Remediation hint is rule-specific for obsidianmd/ui/sentence-case

bats_require_minimum_version 1.5.0

setup() {
  PLUGIN_ROOT="$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/block-eslint-disable.sh"

  if [ -n "${BATS_TEST_TMPDIR:-}" ] && [ -d "$BATS_TEST_TMPDIR" ]; then
    TEST_DIR="$BATS_TEST_TMPDIR"
  else
    mkdir -p "$PLUGIN_ROOT/tests/.scratch"
    TEST_DIR="$(mktemp -d "$PLUGIN_ROOT/tests/.scratch/block-eslint-disable.XXXXXX")"
  fi
  export TEST_DIR

  export GIT_AUTHOR_NAME="bats" GIT_AUTHOR_EMAIL="b@a.ts"
  export GIT_COMMITTER_NAME="bats" GIT_COMMITTER_EMAIL="b@a.ts"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  unset CLAUDE_ALLOW_ESLINT_DISABLE
}

teardown() {
  if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
    chmod -R u+w "$TEST_DIR" 2>/dev/null || true
    rm -rf "$TEST_DIR"
  fi
}

# Build a git repo under $TEST_DIR/<name>.
# Modes: obsidian-manifest | obsidian-package | plain
make_repo() {
  local name="$1" mode="$2"
  local repo="$TEST_DIR/$name"
  mkdir -p "$repo/src"
  git -C "$repo" init -q 2>/dev/null || (cd "$repo" && git init -q)
  case "$mode" in
    obsidian-manifest)
      printf '{"id":"demo","name":"Demo","minAppVersion":"1.5.0"}\n' > "$repo/manifest.json" ;;
    obsidian-package)
      printf '{"name":"demo","devDependencies":{"obsidian": "latest"}}\n' > "$repo/package.json" ;;
    plain)
      printf '{"name":"demo"}\n' > "$repo/package.json" ;;
  esac
  printf '%s' "$repo"
}

payload() {
  # payload <tool> <file_path> <json_field> <text>
  jq -nc --arg tool "$1" --arg fp "$2" --arg field "$3" --arg text "$4" \
    '{tool_name: $tool, tool_input: ({file_path: $fp} + {($field): $text})}'
}

@test "non-editing tool is ignored" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Bash "$repo/src/main.ts" content "// eslint-disable-next-line")' | '$HOOK'"
  [ -z "$output" ]
}

@test "denies eslint-disable in Write content" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/src/main.ts" content "// eslint-disable-next-line obsidianmd/ui/sentence-case")' | '$HOOK'"
  [ "$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision')" = "deny" ]
}

@test "denies eslint-disable in Edit new_string" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Edit "$repo/src/main.ts" new_string "/* eslint-disable */")' | '$HOOK'"
  [ "$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision')" = "deny" ]
}

@test "sentence-case disable gets a rule-specific remediation hint" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/src/main.ts" content "// eslint-disable-next-line obsidianmd/ui/sentence-case")' | '$HOOK'"
  reason="$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecisionReason')"
  case "$reason" in
    *"sentence case"*) ;;
    *) printf 'reason lacked sentence-case hint: %s\n' "$reason" >&2; return 1 ;;
  esac
}

@test "denies a rule mapped to off in eslint.config.js" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/eslint.config.js" content '  "obsidianmd/ui/sentence-case": "off",')' | '$HOOK'"
  [ "$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision')" = "deny" ]
}

@test "detects an Obsidian repo via the package.json obsidian dependency" {
  repo="$(make_repo obs obsidian-package)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/src/main.ts" content "// eslint-disable-line")' | '$HOOK'"
  [ "$(printf '%s' "$output" | jq -r '.hookSpecificOutput.permissionDecision')" = "deny" ]
}

@test "allows a disable in a non-Obsidian repo" {
  repo="$(make_repo plain plain)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/src/main.ts" content "// eslint-disable-next-line")' | '$HOOK'"
  [ -z "$output" ]
}

@test "allows Markdown that quotes the pattern" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/README.md" content "Never write // eslint-disable here.")' | '$HOOK'"
  [ -z "$output" ]
}

@test "allows removing an existing disable (old_string only)" {
  repo="$(make_repo obs obsidian-manifest)"
  json="$(jq -nc --arg fp "$repo/src/main.ts" \
    '{tool_name:"Edit", tool_input:{file_path:$fp, old_string:"// eslint-disable-next-line", new_string:"const x = 1;"}}')"
  run -0 bash -c "printf '%s' '$json' | '$HOOK'"
  [ -z "$output" ]
}

@test "allows clean content" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "printf '%s' '$(payload Write "$repo/src/main.ts" content "const x = 1;")' | '$HOOK'"
  [ -z "$output" ]
}

@test "CLAUDE_ALLOW_ESLINT_DISABLE=1 bypasses the guard" {
  repo="$(make_repo obs obsidian-manifest)"
  run -0 bash -c "CLAUDE_ALLOW_ESLINT_DISABLE=1; export CLAUDE_ALLOW_ESLINT_DISABLE; printf '%s' '$(payload Write "$repo/src/main.ts" content "// eslint-disable-next-line")' | '$HOOK'"
  [ -z "$output" ]
}

@test "path outside any git repo is ignored" {
  mkdir -p "$TEST_DIR/loose"
  run -0 bash -c "printf '%s' '$(payload Write "$TEST_DIR/loose/main.ts" content "// eslint-disable")' | '$HOOK'"
  [ -z "$output" ]
}
