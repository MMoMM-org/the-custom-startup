---
title: "Phase 4: Setup — plan, state, writer, apply"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Setup — plan, state, writer, apply

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes; lines: 453-465]` StateDir layout
- `[ref: SDD/Internal API Changes; lines: 467-494]` plan and apply contracts
- `[ref: SDD/Application Data Models; lines: 496-583]` Change, TargetPlan, PlanRecord, PlanReport, ApplyReport
- `[ref: SDD/Implementation Examples; lines: 713-757]` plan identity walkthrough and test examples
- `[ref: SDD/Primary Flow: setup; lines: 772-807]`
- `[ref: SDD/Error Handling; lines: 809-826]`
- `[ref: SDD/ADR-2, ADR-3, ADR-6; lines: 953-981, 997-1012]`

**Key Decisions**:
- ADR-2: `apply` takes only `--plan`; recomputes and refuses on any difference; single use; 15-minute expiry.
- ADR-3: targets computed in code; managed refused in the writer; no in-place fallback; backup before replace; restore on failed verification.
- ADR-6: fail-closed sandbox keys only with `--sandbox-confirmed`; probe re-run in apply when the plan holds sandbox keys.

**Dependencies**:
- Phase 3 (findings and the CLI). T4.1 and T4.3 are parallel; T4.2 needs T4.1; T4.4 needs all three.

---

## Tasks

Delivers `plan` and `apply`: content-bound proposals, the only settings writer, and the state that makes approvals single-use.

- [ ] **T4.1 State directory and plan records (`state.py`)** `[activity: backend-io]` `[parallel: true]`

  1. Prime: StateDir layout, PlanRecord `[ref: SDD/Data Storage Changes; lines: 453-465]` `[ref: SDD/ADR-2; lines: 953-964]`
  2. Test: StateDir under `XDG_STATE_HOME` or `~/.local/state`, created 0700; record written 0600 with `O_EXCL|O_NOFOLLOW`; pre-existing symlink at the record path refused; load returns `unknown`, `expired` (clock injectable, 15 min), `consumed`; consume is idempotent and a second apply sees `consumed`; expired records removed on the next run; lock acquired and released, held across a callback; StateDir never inside the repository even when `HOME` is the repo root
  3. Implement: `lib/state.py` — `state_dir()`, `save_plan(record)`, `load_plan(plan_id, now)`, `consume(plan_id)`, `lock()`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_writer.py -k state`
  5. Success: single-use, expiring approvals `[ref: PRD/F9 AC12]` `[ref: SDD/F9.12]`

- [ ] **T4.2 Planner and the `plan` verb (`planner.py`)** `[activity: domain-modeling]`

  1. Prime: plan identity walkthrough; check catalogue "setup proposes" column; Rules 2–7, 10 `[ref: SDD/Implementation Examples; lines: 713-735]` `[ref: SDD/Complex Logic; lines: 828-865]` `[ref: PRD/Business Rules]`
  2. Test: CR (clone-risk) and C2x/C6x/C8/C9 findings produce no change; one TargetPlan per target with a CLI-rendered unified diff and header (scope, real path, profile DETECTED/EXPLICIT, plan_short); additions default selected at user scope (C1, C2, C4, C7); removals (C3, C10) in the rule's own file, each its own change id, default deselected, never narrowed; deliberate differences flagged and deselected; `--move id=project` regenerates both diffs and a new plan_id; project file never targeted unless moved; two findings on the same key → one change; C6 replacement proposes `enabledMcpjsonServers` with exactly the approved names and removes enable-all; no allowlist proposed; container never gets `disableBypassPermissionsMode`; probe ≠ pass → no sandbox keys; pass → `enabled` only; pass + `--sandbox-confirmed` → fail-closed keys; `enableWeakerNestedSandbox` never; version-gated key above detected or unknown version → `not_proposed` naming the version; no allow rule for the skill's own apply ever proposed and `self_allow_warning` set when a broad python/Bash allow exists; consent note present, bypass variant when bypass active or unknown; plan_id stable for identical inputs and different for any changed field; a plan after a completed apply selects zero changes
  3. Implement: `lib/planner.py` — `build(snapshot, findings, selection, moves, sandbox_confirmed) -> (targets, not_proposed)`, `plan_id(...)`, `render_diff(...)`; `plan` verb in `cli.py` writing the PlanRecord via `state`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_planner.py tests/tcs-helper/test_security_baseline_cli.py -k plan`
  5. Success: `[ref: PRD/F9 AC1, AC3-AC6, AC8, AC10, AC14]` `[ref: PRD/F4 AC2]` `[ref: PRD/F6 AC5-AC6]` `[ref: PRD/F8 AC2-AC3]` `[ref: PRD/F12 AC2]` `[ref: PRD/F11 AC2]` `[ref: SDD/F9.1, F9.3-F9.6, F9.8, F9.10, F9.14, F4.2, F6.5-F6.7, F8.2, F11.2, F12.2, R10, E2, E3]`

- [ ] **T4.3 Settings writer (`writer.py`)** `[activity: security]` `[parallel: true]`

  1. Prime: ADR-3 in full; writer error rows; gotchas on `$TMPDIR` and sandbox placeholders `[ref: SDD/ADR-3; lines: 965-981]` `[ref: SDD/Error Handling; lines: 809-826]` `[ref: SDD/Implementation Gotchas; lines: 1191-1211]`
  2. Test: only the three computed targets accepted; any managed path, drop-in dir or arbitrary path refused before any open; project `.claude` symlinked outside the project refused; `settings.local.json` symlinked to `~/.ssh/config` refused; user `settings.json` symlink to a dotfiles file followed, link kept, real file written; foreign uid and non-regular targets refused; 0-byte read-only placeholder refused with the `claude doctor` hint; backup written 0600 in StateDir and verified before replace; retention keeps last 10 per scope and ≥ 30 days, never the newest, ignores non-matching names; temp file in the target directory with `O_EXCL|O_NOFOLLOW`, original mode kept, new file 0600 (user/local) or 0644 masked (project); target changed between read and replace (hook in the re-stat step) → abort, nothing written; EPERM/EROFS → "run apply outside the sandbox", original intact; `os.replace` failure → error, no in-place write; post-write mismatch → restored from backup; simulated `KeyboardInterrupt` after temp write → temp removed, original intact; missing target created with only approved keys
  3. Implement: `lib/writer.py` — `allowed_targets(home, config_dir, project_dir, repo_root)`, `write_target(target_plan, expected_obj, fmt) -> Result`, `prune_backups(scope)`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_writer.py`; run on macOS CI for `F_FULLFSYNC`
  5. Success: `[ref: PRD/F9 AC7, AC9, AC11, AC13]` `[ref: PRD/Edge Cases]` `[ref: SDD/F9.7, F9.9, F9.11, F9.13, E1, E4]`

- [ ] **T4.4 The `apply` verb** `[activity: backend-api]`

  1. Prime: apply contract, setup sequence diagram, plan-identity walkthrough `[ref: SDD/Internal API Changes; lines: 467-494]` `[ref: SDD/Primary Flow: setup; lines: 772-807]` `[ref: SDD/Implementation Examples; lines: 713-757]`
  2. Test: `apply` rejects any selection argument (exit 2); unknown, expired or consumed plan → 3, nothing written; target changed since plan (append to local file) → 3; probe re-run when the plan holds sandbox keys and a now-failing probe → 3; success writes targets in order user → project → local, returns per-target results with backup path and `verified: true`, consumes the record; partial failure (one target refused) → exit 0 with that target's error and others written; a second `plan` then selects zero changes; JSON contains no `env` values
  3. Implement: `apply` verb in `cli.py` — load record, rebuild snapshot and plan from live files with the stored selection, compare `plan_id`, write via `writer` under `state.lock()`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_cli.py -k apply`
  5. Success: what is written equals what was shown `[ref: PRD/Business Rule 9]` `[ref: PRD/F9 AC2, AC12]`; idempotent `[ref: PRD/F9 AC8]` `[ref: SDD/F9.2, F9.8, F9.12]`

- [ ] **T4.5 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_*.py tests/test_json_dump_ensure_ascii.py tests/tcs-helper/test_prompt_lint_repo.py`. Review the writer and `apply` against ADR-2 and ADR-3 line by line (security reviewer). Confirm `audit` still writes nothing now that `state` exists.
