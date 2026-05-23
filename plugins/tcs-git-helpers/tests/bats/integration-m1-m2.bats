#!/usr/bin/env bats
#
# tests/bats/integration-m1-m2.bats
#
# T3.2 — End-to-end integration test: M1 (ahead-check) + M2 (inline override scan)
#
# Exercises three scenarios that together prove the two Phase implementations
# compose correctly when the full block-bad-git-ops.sh dispatcher runs:
#
#   Scenario A (Path A sub-path): Ghost branch + inline override consumed via scan
#     CMD = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin <branch>"
#     HEAD == merged SHA → _is_ahead_of_merged returns 1 → override consumed via
#     _scan_tool_input_for_override → exits 0; audit has tool_input_truncated=true;
#     ADR-8 ahead-note absent from stderr.
#
#   Scenario B (Path B): HEAD ahead → allow with ADR-8 stderr note; no override
#     CMD = "git push origin <branch>" (no override prefix)
#     HEAD is 3 commits ahead → _is_ahead_of_merged returns 0 → exits 0;
#     stderr carries exact ADR-8 wording; no audit line (override path never reached).
#
#   Scenario C (regression guard): Ghost branch, no override → deny preserved
#     CMD = "git push origin <branch>" (no override)
#     HEAD == merged SHA → _is_ahead_of_merged returns 1 → deny with PUSH_TO_CLOSED_PR
#     (M1-AC1 regression guard; confirms M2 scan path does not interfere with deny).
#
# Spec references:
#   - SDD §Runtime View / Path A sub-path (lines 532-558): inline-override sequence
#   - SDD §Runtime View / Path B (lines 559-580): ahead-allow sequence
#   - PRD M1-AC1/AC2/AC3, M12 AC2 (tool_input_truncated in audit)
#
# Constraints:
#   - bash 3.2 only (CON-1): no associative arrays, no mapfile
#   - No new CLI deps: git, gh (stub), jq only (CON-6)
#   - Production code unchanged (CON-7): test-only task

bats_require_minimum_version 1.5.0

load 'lib/helpers'

# ----------------------------------------------------------------------
# Setup / teardown
# ----------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  FIXTURE_DIR="$PLUGIN_ROOT/tests/fixtures"
  export TESTS_DIR PLUGIN_ROOT FIXTURE_DIR
}

setup() {
  HOOK="$PLUGIN_ROOT/scripts/block-bad-git-ops.sh"

  # Sandbox CLAUDE_PLUGIN_DATA so override sentinels and audit don't leak
  # into the user's real plugin data dir.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-int-m1m2.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  AUDIT_FILE="$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl"

  # PATH-prepend gh stub so any `gh` call hits canned responses, not real GitHub.
  PATH="$FIXTURE_DIR/gh_stubs:$PATH"
  export PATH

  GH_STUB_SCENARIO="default"
  export GH_STUB_SCENARIO

  # Defensive: clear any leaked override env-vars from a prior test.
  unset CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_CLEAN_FORCE \
        CLAUDE_ALLOW_DESTRUCTIVE_CHECKOUT CLAUDE_ALLOW_DESTRUCTIVE_RESTORE \
        CLAUDE_ALLOW_FORCE_BRANCH_DELETE CLAUDE_ALLOW_STASH_DESTROY \
        CLAUDE_ALLOW_REFLOG_EXPIRE CLAUDE_ALLOW_NO_VERIFY \
        CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_FORCE_PUSH \
        CLAUDE_ALLOW_REMOTE_BRANCH_DELETE CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED \
        CLAUDE_ALLOW_RESUME_MERGED_BRANCH CLAUDE_ALLOW_HOOKSPATH_OVERRIDE \
        CLAUDE_ALLOW_GIT_BAD_OPS TCS_GIT_HELPERS_SETUP_ACTIVE \
        GH_STUB_SPY_FILE
}

teardown() {
  cd /
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    chmod -R u+rwX "$CLAUDE_PLUGIN_DATA" 2>/dev/null || true
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

# ----------------------------------------------------------------------
# Scenario A — Path A sub-path: ghost branch + inline override consumed via scan
#
# Setup: branch HEAD == merged_sha (ghost branch — merge_commit == HEAD).
# Command: "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin <branch>"
#   (no env-var export; override prefix is embedded in the CMD string only)
#
# Expected:
#   - hook exits 0 (allow — no deny JSON)
#   - ADR-8 ahead-note absent from stderr (HEAD is NOT ahead; override consumed instead)
#   - Audit log has exactly one entry with tool_input_truncated=true (scan-path write)
# ----------------------------------------------------------------------

@test "T3.2 Scenario A: ghost branch + inline override → allow; tool_input_truncated=true in audit; no ADR-8 ahead-note" {
  local repo branch merged_sha
  branch="feat/int-m1m2-scenA"

  # Build repo with branch at base commit (0 extra commits after base).
  # HEAD will equal the merge_commit, simulating a ghost branch.
  repo="$(_build_ahead_repo "$branch" 0)"
  merged_sha="$(git -C "$repo" rev-parse HEAD)"

  # Seed cache: state=MERGED, merge_commit=HEAD (ghost branch).
  _seed_pr_cache "$repo" "$branch" "MERGED" "$merged_sha"

  cd "$repo"
  # No env-var export — override travels exclusively via the CMD prefix (M2 scan path).
  run --separate-stderr _run_hook_with_cmd \
    "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin $branch"
  rm -rf "$repo"

  # Allow: no deny JSON on stdout.
  _assert_allow

  # ADR-8 ahead-note must NOT appear in stderr (HEAD == merged_sha, not ahead).
  local adr8_note="PR was merged; HEAD is ahead by new commits"
  if [[ "$stderr" == *"$adr8_note"* ]]; then
    echo "ADR-8 ahead-note MUST be absent when HEAD==merged_sha (ghost branch), got: $stderr" >&2
    return 1
  fi

  # Audit log must have exactly one entry (the override consumption).
  [ -f "$AUDIT_FILE" ] \
    || { echo "expected audit file at $AUDIT_FILE" >&2; return 1; }
  local line_count=0
  line_count=$(wc -l < "$AUDIT_FILE" | tr -d ' ')
  [ "$line_count" -eq 1 ] \
    || { echo "expected 1 audit line, got: $line_count" >&2; return 1; }

  # tool_input_truncated must be true (scan-path — not env-var-path).
  run jq -r '.tool_input_truncated' "$AUDIT_FILE"
  [ "$output" = "true" ] \
    || { echo "expected tool_input_truncated=true in audit, got: $output" >&2; return 1; }

  # env_var in audit must name the granular override variable.
  run jq -r '.env_var' "$AUDIT_FILE"
  [ "$output" = "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" ] \
    || { echo "expected env_var=CLAUDE_ALLOW_PUSH_TO_CLOSED_PR in audit, got: $output" >&2; return 1; }
}

# ----------------------------------------------------------------------
# Scenario B — Path B: HEAD ahead of merge_commit → allow + ADR-8 stderr note
#
# Setup: branch HEAD is 3 commits ahead of the cached merge_commit SHA.
# Command: plain "git push origin <branch>" (no override prefix, no env-var).
#
# Expected:
#   - hook exits 0 (allow — no deny JSON)
#   - stderr contains the exact ADR-8 wording
#   - Audit log does NOT exist (override path never reached)
# ----------------------------------------------------------------------

@test "T3.2 Scenario B: HEAD 3 commits ahead of merge_commit → allow; ADR-8 stderr note; no audit line" {
  local repo branch base_sha
  branch="feat/int-m1m2-scenB"

  # Build repo with branch at base commit (0 extra so we can record base_sha).
  repo="$(_build_ahead_repo "$branch" 0)"
  base_sha="$(git -C "$repo" rev-parse HEAD)"

  # Add 3 more commits so HEAD is 3 ahead of base_sha.
  local i=0
  while [ "$i" -lt 3 ]; do
    printf 'new work %s\n' "$i" > "$repo/new${i}.txt"
    git -C "$repo" add "new${i}.txt"
    git -C "$repo" commit -q -m "new work $i"
    i=$((i + 1))
  done

  # Seed cache: state=MERGED, merge_commit=base_sha (HEAD is now 3 ahead).
  _seed_pr_cache "$repo" "$branch" "MERGED" "$base_sha"

  cd "$repo"
  # Plain push — no override prefix.
  run --separate-stderr _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"

  # Allow: no deny JSON on stdout.
  _assert_allow

  # ADR-8 ahead-note must appear in stderr (exact wording locked per SDD ADR-8).
  local adr8_note="tcs-git-helpers: PR was merged; HEAD is ahead by new commits. A new PR will be required for this push."
  [[ "$stderr" == *"$adr8_note"* ]] \
    || { echo "expected ADR-8 note in stderr, got: $stderr" >&2; return 1; }

  # Audit log must NOT exist — override path was never entered (ahead-check returned 0
  # and _check_push_to_closed_pr returned immediately without calling _check_and_consume_override).
  if [ -f "$AUDIT_FILE" ]; then
    echo "expected NO audit file (override path not reached), but found: $AUDIT_FILE" >&2
    return 1
  fi
}

# ----------------------------------------------------------------------
# Scenario C — regression guard: ghost branch, no override → deny preserved
#
# Setup: branch HEAD == merged_sha (ghost branch), no override env-var or CMD prefix.
# Command: plain "git push origin <branch>"
#
# Expected:
#   - hook exits 0 (hook always exits 0; deny travels via JSON on stdout)
#   - stdout contains deny JSON with rule PUSH_TO_CLOSED_PR
#   - Existing deny wording present ("PR for branch" + "is MERGED")
#   - Audit log does NOT exist (deny path — no override consumed)
# ----------------------------------------------------------------------

@test "T3.2 Scenario C regression: ghost branch, no override → deny PUSH_TO_CLOSED_PR with existing wording" {
  local repo branch merged_sha
  branch="feat/int-m1m2-scenC"

  # Build repo with branch at base commit (0 extra — HEAD == merged_sha).
  repo="$(_build_ahead_repo "$branch" 0)"
  merged_sha="$(git -C "$repo" rev-parse HEAD)"

  # Seed cache: state=MERGED, merge_commit=HEAD (ghost branch).
  _seed_pr_cache "$repo" "$branch" "MERGED" "$merged_sha"

  cd "$repo"
  # Plain push — no override of any kind.
  run _run_hook_with_cmd "git push origin $branch"
  rm -rf "$repo"

  # Deny: stdout must contain permissionDecision=deny + PUSH_TO_CLOSED_PR rule.
  _assert_deny_for_rule "PUSH_TO_CLOSED_PR"

  # Pin the existing deny wording (M1-AC1 regression guard).
  [[ "$output" == *"PR for branch"* ]] \
    || { echo "expected existing deny wording 'PR for branch', got: $output" >&2; return 1; }
  [[ "$output" == *"is MERGED"* ]] \
    || { echo "expected 'is MERGED' in deny output, got: $output" >&2; return 1; }

  # No audit entry — deny path does not consume an override.
  if [ -f "$AUDIT_FILE" ]; then
    echo "expected NO audit file on deny path, but found: $AUDIT_FILE" >&2
    return 1
  fi
}
