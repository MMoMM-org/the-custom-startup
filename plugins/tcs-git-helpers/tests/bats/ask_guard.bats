#!/usr/bin/env bats
#
# tests/bats/ask_guard.bats
#
# ask-guard (#299): an opt-in PreToolUse guard that answers "ask" for the
# commands and paths a repo lists in .githooks/ask-guard.conf, such as
# terraform apply, a migration or an IAM policy. No file means off.
#
# A1 is the positive control for every "no ask" assertion: the same fixture
# config does produce an ask for a matching command.

bats_require_minimum_version 1.5.0

load 'lib/helpers'

setup() {
  PLUGIN_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/ask-guard.sh"
  EXAMPLE="$PLUGIN_ROOT/templates/githooks/ask-guard.conf.example"
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  export CLAUDE_PLUGIN_DATA="$BATS_TEST_TMPDIR/data"
  unset CLAUDE_ALLOW_ASK_TERRAFORM CLAUDE_ALLOW_ASK_MIGRATIONS CLAUDE_ALLOW_GIT_BAD_OPS
  REPO="$BATS_TEST_TMPDIR/repo"
  git init -q "$REPO"
  REPO="$(cd "$REPO" && pwd -P)"
  export CLAUDE_PROJECT_DIR="$REPO"
  cd "$REPO"
  mkdir -p .githooks
}

_conf() {
  cat > "$REPO/.githooks/ask-guard.conf" <<'EOF'
# test config
command TERRAFORM (^|[^[:alnum:]_-])terraform([[:space:]]+-[^[:space:]]+)*[[:space:]]+(apply|destroy)([^[:alnum:]_-]|$)
command IAM (^|[^[:alnum:]_-])aws[[:space:]].*iam[[:space:]]+(create|delete|put|attach)
path MIGRATIONS migrations/*
path TERRAFORM *.tf
EOF
}

_bash() {
  run _run_hook_with_cmd "$1"
  [ "$status" -eq 0 ]
}

_edit() {
  local input
  input=$(jq -nc --arg t "${2:-Write}" --arg p "$1" '{tool_name:$t, tool_input:{file_path:$p}}')
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$input" "$HOOK"
  [ "$status" -eq 0 ]
}

_asks() {
  _has "$output" '"permissionDecision":"ask"'
  _has "$output" "$1"
}

_silent() {
  [ -z "$output" ] || { echo "expected no decision, got: $output" >&2; return 1; }
}

# --- off by default ------------------------------------------------------------

@test "O1 no config file: matching command gets no decision" {
  _bash 'terraform apply -auto-approve'
  _silent
}

@test "O2 the shipped example asks for nothing: every rule is commented out" {
  cp "$EXAMPLE" "$REPO/.githooks/ask-guard.conf"
  _bash 'terraform apply'
  _silent
  _edit "$REPO/migrations/001.sql"
  _silent
}

@test "O3 the example's rules, uncommented, are valid and ask" {
  sed -n -E 's/^# (command|path) /\1 /p' "$EXAMPLE" > "$REPO/.githooks/ask-guard.conf"
  [ -s "$REPO/.githooks/ask-guard.conf" ]
  run bash -c 'printf "%s" "$1" | bash "$2" 2>&1 >/dev/null' _ \
    "$(jq -nc '{tool_name:"Bash", tool_input:{command:"true"}}')" "$HOOK"
  [ -z "$output" ] || { echo "example rule rejected: $output" >&2; return 1; }
  for c in 'terraform apply' 'pulumi destroy' 'kubectl delete pod x' \
           'npx prisma migrate deploy' 'alembic upgrade head' \
           'aws iam create-user --user-name x' 'gcloud projects add-iam-policy-binding p'; do
    _bash "$c"
    _has "$output" '"permissionDecision":"ask"'
  done
}

# --- Bash ------------------------------------------------------------------------

@test "A1 matching command asks and names the rule and the override" {
  _conf
  _bash 'terraform -chdir=infra apply'
  _asks "[TERRAFORM]"
  _has "$output" "CLAUDE_ALLOW_ASK_TERRAFORM=1"
  _has "$output" ".githooks/ask-guard.conf"
}

@test "A2 a non-matching subcommand gets no decision" {
  _conf
  _bash 'terraform plan -out tf.plan'
  _silent
}

@test "A3 a chained or shell-wrapped command still asks" {
  _conf
  _bash 'cd infra && terraform destroy'
  _asks "[TERRAFORM]"
  _bash "bash -c 'terraform apply'"
  _asks "[TERRAFORM]"
}

@test "A4 two rules in one call are both named" {
  _conf
  _bash 'terraform apply; aws iam attach-role-policy --role-name x'
  _asks "[TERRAFORM]"
  _has "$output" "[IAM]"
}

@test "Q1 a quoted mention inside an argument gets no decision" {
  _conf
  _bash 'echo "terraform apply"'
  _silent
  _bash "git commit -m 'run terraform apply after review'"
  _silent
}

# --- Edit / Write ------------------------------------------------------------------

@test "P1 a write under a listed glob asks; * crosses directories" {
  _conf
  _edit "$REPO/migrations/2026/001_init.sql"
  _asks "[MIGRATIONS]"
  _edit "$REPO/infra/modules/main.tf" Edit
  _asks "[TERRAFORM]"
}

@test "P2 a write elsewhere gets no decision" {
  _conf
  _edit "$REPO/src/app.py"
  _silent
}

@test "P3 a file outside the repo matches no rule, even a bare *.tf" {
  _conf
  _edit "/elsewhere/migrations/001.sql"
  _silent
  _edit "/elsewhere/main.tf"
  _silent
}

@test "K1 path rules do not apply to Bash, command rules not to writes" {
  _conf
  _bash 'cat migrations/001.sql'
  _silent
  _edit "$REPO/terraform apply"
  _silent
}

@test "D1 a rule matched by two lines is named once" {
  cat > "$REPO/.githooks/ask-guard.conf" <<'EOF'
path MIG migrations/*
path MIG *.sql
EOF
  _edit "$REPO/migrations/001.sql"
  _asks "[MIG]"
  [ "$(printf '%s' "$output" | grep -o '\[MIG\]' | wc -l)" -eq 1 ]
}

# --- override ----------------------------------------------------------------------

@test "V1 inline override skips the ask once and is audited" {
  _conf
  _bash 'CLAUDE_ALLOW_ASK_TERRAFORM=1 terraform apply'
  _silent
  _has "$(cat "$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl")" "CLAUDE_ALLOW_ASK_TERRAFORM"
}

@test "V2 an override for one rule leaves the other asking" {
  _conf
  _bash 'CLAUDE_ALLOW_ASK_TERRAFORM=1 terraform apply; aws iam create-user --user-name x'
  _asks "[IAM]"
  _lacks "$output" "[TERRAFORM]"
}

@test "V3 env override covers Edit/Write" {
  _conf
  export CLAUDE_ALLOW_ASK_MIGRATIONS=1
  _edit "$REPO/migrations/001.sql"
  _silent
}

@test "V4 each ask is audited" {
  _conf
  _bash 'terraform apply'
  _has "$(cat "$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl")" '"hook":"ask-guard"'
}

# --- robustness --------------------------------------------------------------------

@test "M1 bad config lines are skipped with a warning, good ones still apply" {
  cat > "$REPO/.githooks/ask-guard.conf" <<'EOF'
command lowercase terraform
command BROKEN (unclosed
deny TERRAFORM terraform
path EMPTY
command TERRAFORM terraform[[:space:]]+apply
EOF
  run bash -c 'printf "%s" "$1" | bash "$2" 2>&1 >/dev/null' _ \
    "$(jq -nc '{tool_name:"Bash", tool_input:{command:"terraform apply"}}')" "$HOOK"
  _has "$output" "line 1"
  _has "$output" "line 2"
  _has "$output" "line 3"
  _has "$output" "line 4"
  _lacks "$output" "line 5"
  _bash 'terraform apply'
  _asks "[TERRAFORM]"
}

@test "M2 malformed stdin exits 0 with no decision" {
  _conf
  run bash -c 'printf "not json" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
  _silent
}

@test "M3 other tools are ignored" {
  _conf
  run bash -c 'printf "%s" "$1" | bash "$2"' _ '{"tool_name":"Read","tool_input":{"file_path":"migrations/x"}}' "$HOOK"
  [ "$status" -eq 0 ]
  _silent
}

@test "R1 registered for Bash and Edit|Write|NotebookEdit" {
  run jq -r '.hooks.PreToolUse[] | select(any(.hooks[]; .command | contains("ask-guard.sh"))) | .matcher' \
    "$PLUGIN_ROOT/hooks/hooks.json"
  _has "$output" "Bash"
  _has "$output" "Edit|Write|NotebookEdit"
}

@test "L1 hook is shellcheck-clean" {
  command -v shellcheck >/dev/null 2>&1 || skip "shellcheck not installed"
  run shellcheck -x "$HOOK"
  [ "$status" -eq 0 ]
}
