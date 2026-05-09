#!/usr/bin/env bats
# Tests for scripts/lib/audit_log.sh
# Spec: SDD §Audit Log Schema (overrides.jsonl), ADR-7 rotation policy, M12 AC3-AC5.

bats_require_minimum_version 1.5.0

setup() {
  PLUGIN_ROOT="$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)"
  LIB="$PLUGIN_ROOT/scripts/lib/audit_log.sh"

  TMP_DATA="$(mktemp -d)"
  export CLAUDE_PLUGIN_DATA="$TMP_DATA"
  AUDIT_DIR="$CLAUDE_PLUGIN_DATA/audit"
  AUDIT_FILE="$AUDIT_DIR/overrides.jsonl"

  WORK_DIR="$(mktemp -d)"
  cd "$WORK_DIR"
  git init -q . >/dev/null 2>&1
  git -c user.email=t@t.t -c user.name=t commit --allow-empty -q -m init >/dev/null 2>&1 || true

  # shellcheck source=/dev/null
  source "$LIB"
}

teardown() {
  cd /
  chmod -R u+rwX "$TMP_DATA" 2>/dev/null || true
  chmod -R u+rwX "$WORK_DIR" 2>/dev/null || true
  rm -rf "$TMP_DATA" "$WORK_DIR"
}

# ---------- JSONL append + validity ----------

@test "appends one JSONL line per call" {
  _audit_log hook=block-bad-git-ops env_var=CLAUDE_ALLOW_X master=false \
             command="git push origin foo" pattern="git[[:space:]]+push" \
             tool_input_truncated=false

  [ -f "$AUDIT_FILE" ]
  run wc -l < "$AUDIT_FILE"
  [ "${output// /}" = "1" ]
}

@test "each appended line is valid JSON (jq -e -c .)" {
  _audit_log hook=h1 env_var=v1 command=c1 pattern=p1
  _audit_log hook=h2 env_var=v2 command=c2 pattern=p2
  _audit_log hook=h3 env_var=v3 command=c3 pattern=p3

  run wc -l < "$AUDIT_FILE"
  [ "${output// /}" = "3" ]

  while IFS= read -r line; do
    [ -n "$line" ]
    printf '%s\n' "$line" | jq -e -c . >/dev/null
  done < "$AUDIT_FILE"
}

@test "field order is stable: ts, repo, branch, hook, env_var, master, command, pattern, tool_input_truncated" {
  # Pass keys in shuffled order; output order must still be canonical.
  _audit_log tool_input_truncated=true pattern=p command=c master=true env_var=E hook=H

  local keys
  keys="$(jq -c 'keys_unsorted' "$AUDIT_FILE")"
  [ "$keys" = '["ts","repo","branch","hook","env_var","master","command","pattern","tool_input_truncated"]' ]
}

@test "printf fallback emits canonical field order on disk (jq masked)" {
  # Mask jq with a function that returns non-zero with no output. The lib's
  # `command -v jq` succeeds (functions are visible), but the empty result
  # forces the printf fallback path. We then assert the raw on-disk line —
  # NOT a jq-parsed AST — to verify the printf path itself freezes order.
  jq() { return 127; }
  export -f jq

  _audit_log hook=H env_var=E master=true command=cmd pattern=pat tool_input_truncated=false

  unset -f jq

  run head -n 1 "$AUDIT_FILE"
  [ "$status" -eq 0 ]
  # Strict regex: all 9 keys present in canonical order, master/trunc as
  # JSON booleans (no quotes), caller fields literal.
  [[ "$output" =~ ^\{\"ts\":\"[^\"]+\",\"repo\":\"[^\"]+\",\"branch\":\"[^\"]+\",\"hook\":\"H\",\"env_var\":\"E\",\"master\":true,\"command\":\"cmd\",\"pattern\":\"pat\",\"tool_input_truncated\":false\}$ ]]
}

@test "master and tool_input_truncated are JSON booleans (not strings)" {
  _audit_log hook=H env_var=E master=true command=c pattern=p tool_input_truncated=false
  run jq -r '.master | type' "$AUDIT_FILE"
  [ "$status" -eq 0 ]
  [ "$output" = "boolean" ]
  run jq -r '.tool_input_truncated | type' "$AUDIT_FILE"
  [ "$output" = "boolean" ]
}

@test "embedded double-quotes and backslashes are JSON-escaped" {
  _audit_log hook=H env_var=E master=false \
             command='git commit -m "hello \\ world"' \
             pattern='nope' tool_input_truncated=false
  run jq -e -c . "$AUDIT_FILE"
  [ "$status" -eq 0 ]
  run jq -r '.command' "$AUDIT_FILE"
  # Two literal backslashes in input ('\\' inside single quotes) round-trip intact.
  [ "$output" = 'git commit -m "hello \\ world"' ]
}

# ---------- Rotation ----------

@test "rotation triggered at 1024000 bytes: existing .jsonl moves to .1" {
  mkdir -p "$AUDIT_DIR"
  dd if=/dev/zero of="$AUDIT_FILE" bs=1024 count=1000 status=none

  run wc -c < "$AUDIT_FILE"
  [ "${output// /}" = "1024000" ]

  _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false

  [ -f "$AUDIT_FILE.1" ]
  run wc -c < "$AUDIT_FILE.1"
  [ "${output// /}" = "1024000" ]
  # Fresh .jsonl exists with exactly one new line.
  run wc -l < "$AUDIT_FILE"
  [ "${output// /}" = "1" ]
}

@test "no rotation when file is below 1024000 bytes" {
  mkdir -p "$AUDIT_DIR"
  dd if=/dev/zero of="$AUDIT_FILE" bs=1 count=1023999 status=none

  _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false

  [ ! -f "$AUDIT_FILE.1" ]
  # New content appended to existing file.
  run wc -c < "$AUDIT_FILE"
  [ "${output// /}" -gt 1023999 ]
}

@test "rotation cascades: existing .1 moves to .2" {
  mkdir -p "$AUDIT_DIR"
  printf 'OLD_ONE\n' > "$AUDIT_FILE.1"
  dd if=/dev/zero of="$AUDIT_FILE" bs=1024 count=1000 status=none

  _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false

  [ -f "$AUDIT_FILE.2" ]
  run cat "$AUDIT_FILE.2"
  [ "$output" = "OLD_ONE" ]
}

@test "rotation cascades: existing .2 moves to .3 on subsequent rotation" {
  mkdir -p "$AUDIT_DIR"
  printf 'OLD_TWO\n' > "$AUDIT_FILE.2"
  printf 'OLD_ONE\n' > "$AUDIT_FILE.1"
  dd if=/dev/zero of="$AUDIT_FILE" bs=1024 count=1000 status=none

  _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false

  [ -f "$AUDIT_FILE.3" ]
  run cat "$AUDIT_FILE.3"
  [ "$output" = "OLD_TWO" ]
  run cat "$AUDIT_FILE.2"
  [ "$output" = "OLD_ONE" ]
}

@test "rotation: existing .3 is overwritten on subsequent rotation; no .4 ever created" {
  mkdir -p "$AUDIT_DIR"
  printf 'OLDEST_LOST\n' > "$AUDIT_FILE.3"
  printf 'OLD_TWO\n'     > "$AUDIT_FILE.2"
  printf 'OLD_ONE\n'     > "$AUDIT_FILE.1"
  dd if=/dev/zero of="$AUDIT_FILE" bs=1024 count=1000 status=none

  _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false

  [ ! -f "$AUDIT_FILE.4" ]
  # .3 now holds what was in .2 (old .3 was discarded).
  [ -f "$AUDIT_FILE.3" ]
  run cat "$AUDIT_FILE.3"
  [ "$output" = "OLD_TWO" ]
}

# ---------- Write-failure non-blocking (M12 AC5) ----------

@test "_audit_log returns 0 even when audit file is unwritable (chmod 000)" {
  mkdir -p "$AUDIT_DIR"
  : > "$AUDIT_FILE"
  chmod 000 "$AUDIT_FILE"

  run _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false
  [ "$status" -eq 0 ]
}

@test "_audit_log writes a stderr error when audit file is unwritable" {
  mkdir -p "$AUDIT_DIR"
  : > "$AUDIT_FILE"
  chmod 000 "$AUDIT_FILE"

  # bats `run --separate-stderr` records exit status into $status reliably
  # AND splits stderr into $stderr — so we test both halves of M12 AC5
  # (non-blocking exit + stderr surfaced) without a manual `rc=$?` capture
  # that would mask any future regression where _audit_log forgets to
  # `return 0` after a write failure.
  run --separate-stderr _audit_log hook=H env_var=E master=false \
                                   command=c pattern=p \
                                   tool_input_truncated=false
  [ "$status" -eq 0 ]
  [ -n "$stderr" ]
  [[ "$stderr" == *audit_log* ]]
}

@test "_audit_log returns 0 when audit directory cannot be created" {
  # Make CLAUDE_PLUGIN_DATA point at a path we cannot write into.
  local locked="$WORK_DIR/locked"
  mkdir -p "$locked"
  chmod 000 "$locked"
  export CLAUDE_PLUGIN_DATA="$locked"

  run _audit_log hook=H env_var=E master=false command=c pattern=p tool_input_truncated=false
  [ "$status" -eq 0 ]

  chmod 755 "$locked"
}
