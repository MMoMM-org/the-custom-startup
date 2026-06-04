#!/usr/bin/env bats
# sync_subissues.py — pure-core (parse + idempotent plan) tests.
# Exercises the --plan-from seam so no gh / network is involved.

setup() {
  PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
  SCRIPT="${PLUGIN_ROOT}/skills/link-issue/scripts/sync_subissues.py"
  FIXTURE="${PLUGIN_ROOT}/tests/fixtures/issues-sample.json"
  PLAN="${BATS_TMPDIR}/plan.json"
}

@test "script exists and compiles" {
  [ -f "$SCRIPT" ]
  run python3 -m py_compile "$SCRIPT"
  [ "$status" -eq 0 ]
}

@test "plan includes the three unlinked children (Part of / Epic: / Parent:) under #16" {
  run python3 "$SCRIPT" --plan-from "$FIXTURE" --out "$PLAN"
  [ "$status" -eq 0 ]
  [ "$(jq '.plan | length' "$PLAN")" -eq 3 ]
  for child in 30 32 33; do
    jq -e --argjson c "$child" '.plan[] | select(.child==$c and .epic==16)' "$PLAN"
  done
}

@test "idempotent: a child already linked to its declared epic is NOT planned" {
  python3 "$SCRIPT" --plan-from "$FIXTURE" --out "$PLAN"
  run jq -e '.plan[] | select(.child==31)' "$PLAN"
  [ "$status" -ne 0 ]   # no match → jq -e exits non-zero
}

@test "a reference to a non-OPEN / missing epic becomes an anomaly, not a link" {
  python3 "$SCRIPT" --plan-from "$FIXTURE" --out "$PLAN"
  run jq -e '.plan[] | select(.child==40)' "$PLAN"
  [ "$status" -ne 0 ]
  jq -e '.anomalies[] | select(.child==40 and .epic==99)' "$PLAN"
}

@test "a child already linked to a DIFFERENT parent is an anomaly, not silently relinked" {
  python3 "$SCRIPT" --plan-from "$FIXTURE" --out "$PLAN"
  run jq -e '.plan[] | select(.child==51)' "$PLAN"
  [ "$status" -ne 0 ]
  jq -e '.anomalies[] | select(.child==51)' "$PLAN"
}

@test "an issue with no reference is neither planned nor an anomaly" {
  python3 "$SCRIPT" --plan-from "$FIXTURE" --out "$PLAN"
  run jq -e '(.plan + .anomalies)[] | select(.child==50)' "$PLAN"
  [ "$status" -ne 0 ]
}

@test "plan carries node-IDs (not just numbers) for the apply step" {
  python3 "$SCRIPT" --plan-from "$FIXTURE" --out "$PLAN"
  jq -e '.plan[] | select(.child==30) | .child_id=="I_30" and .epic_id=="E_16"' "$PLAN"
}
