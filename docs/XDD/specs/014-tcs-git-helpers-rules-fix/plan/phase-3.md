---
title: "Phase 3: Final Integration, S1 & Release"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Final Integration, S1 & Release

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 1 and Phase 2 must be complete and merged into the working tree before Phase 3 begins.

**Specification References**:
- `[ref: PRD/Feature S1; lines: 178-189]` — S1 deny-message accuracy
- `[ref: SDD/ADR-9; lines: 935-963]` — keep existing deny-message wording (option a)
- `[ref: SDD/Acceptance Criteria; lines: 1061-1076]` — S1-AC1 + M2-AC-REGEX
- `[ref: SDD/Quality Requirements; lines: 967-996]` — reliability, performance, maintainability gates
- `[ref: SDD/Deployment View; lines: 657-666]` — deployment is plugin.json version bump; PR-state cache is backward-compatible

**Key Decisions**:
- **ADR-9 (S1)**: Existing `(override: CLAUDE_ALLOW_<RULE>=1)` deny-message suffix is preserved; M2 makes the documented mechanism actually functional, so no wording edit is required. `[ref: SDD/ADR-9]`
- **Deployment**: plugin.json version bump triggers marketplace sync; consumers receive M1+M2+S1 automatically on next pull. `[ref: SDD/Deployment View]`

**Dependencies**:
- Phase 1 complete (M1 cache extension + `_is_ahead_of_merged` + `_check_push_to_closed_pr` integration).
- Phase 2 complete (M2 `_scan_tool_input_for_override` + `_check_and_consume_override` integration + Python parity).

---

## Tasks

Phase 3 verifies S1, exercises M1+M2 together in an integration test, and ships the plugin version bump.

- [x] **T3.1 S1 — Deny-message wording assertion** `[activity: backend-api]` `[ref: SDD/ADR-9; lines: 935-963]` `[ref: PRD/Feature S1; lines: 178-189]`

  1. **Prime**: Read the `_record_deny` call site at `block-bad-git-ops.sh:148` (or current equivalent) and confirm the deny-message suffix format `(override: CLAUDE_ALLOW_<RULE>=1)`. Confirm via `[ref: SDD/ADR-9; lines: 946-955]` that no edit is required.
  2. **Test (RED)**: Add (or confirm presence of) a BATS assertion in `test_push_to_closed_pr.bats` and `test_override.bats` that captures the current deny-message wording verbatim. The assertion is intentionally a "wording lock" — failing it means a wording change crept in and must be reviewed against ADR-9.
  3. **Implement (GREEN)**: No code edit. The lock test is the deliverable. If a wording change is unavoidable for unrelated reasons, document it as a deviation per the plan/README Deviation Protocol.
  4. **Validate**: BATS suite passes including the new lock assertion. No existing deny-message tests fail (S1-AC1's "no existing assertions fail" clause).
  5. **Success**:
     - [ ] Deny-message suffix `(override: CLAUDE_ALLOW_<RULE>=1)` is preserved across M1+M2 changes `[ref: SDD/ADR-9; lines: 946-955]` `[ref: PRD/AC-S1.1]`
     - [ ] All pre-existing deny-message test assertions continue to pass `[ref: SDD/Acceptance Criteria; lines: 1061-1066]`

- [x] **T3.2 End-to-end integration test — M1 + M2 combined** `[activity: testing]` `[ref: SDD/Runtime View; lines: 510-580]`

  1. **Prime**: Re-read both Runtime View sequence diagrams: `[ref: SDD/Path A sub-path; lines: 531-557]` (ghost branch + inline override consumed via scan) and `[ref: SDD/Path B; lines: 559-580]` (HEAD ahead → allow with stderr note). The integration must exercise both paths within one BATS file to prove M1 and M2 compose correctly.
  2. **Test (RED)** — add `tests/bats/test_integration_m1_m2.bats`:
     - Scenario A (Path A sub-path): Set up a temp git repo with a branch whose mock gh state returns `MERGED` with merge_commit equal to HEAD (ghost branch). Issue `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push` via the hook stdin envelope. Expect: hook exits 0 (allow); audit log records scan-path consumption with `tool_input_truncated`; stderr does NOT contain the ADR-8 ahead-note (because HEAD == merged SHA, the ahead-check returned 1, then override was consumed).
     - Scenario B (Path B): Same setup, but HEAD is 3 commits ahead of merge_commit. Issue plain `git push` via the hook stdin envelope (no override prefix). Expect: hook exits 0 (allow); stderr contains the ADR-8 ahead-note exactly; no audit-log override line (override path was never reached because ahead-check returned 0 first).
     - Scenario C (regression): Ghost branch, no override → deny preserved with existing wording (M1-AC1 regression guard).
  3. **Implement (GREEN)**: Stub `gh` and `git merge-base --is-ancestor` via the existing BATS test infrastructure (mock binaries on `PATH`). No production-code changes — Phase 1 and Phase 2 implementations should already satisfy the integration scenarios. If any scenario fails, treat it as a Phase 1 or Phase 2 gap and fix in the originating phase per the Deviation Protocol.
  4. **Validate**: `bats tests/bats/test_integration_m1_m2.bats` — all three scenarios pass; full `tests/bats/` suite still green; `python -m pytest tests/python/` still green.
  5. **Success**:
     - [ ] M1 + M2 compose without interference — ahead-check runs first; override is the fallback when not ahead `[ref: SDD/Complex Logic; lines: 610-631]`
     - [ ] Audit log captures `tool_input_truncated` only on scan-path consumption `[ref: SDD/Implementation Boundaries; lines: 142-144]`
     - [ ] Stderr ADR-8 note emitted only on Path B (ahead allow), never on Path A `[ref: SDD/Runtime View; lines: 559-580]`

- [x] **T3.3 Plugin version bump + release prep** `[activity: build-platform]` `[ref: SDD/Deployment View; lines: 657-666]` `[ref: SDD/Project Commands; lines: 254-267]`

  1. **Prime**: Read `plugins/tcs-git-helpers/.claude-plugin/plugin.json` to identify the current `version` field and any other release-affecting fields. Recall the canonical TCS bundle versioning pattern per the auto-memory reference: bump the version, push the change, marketplace sync handles the rest.
  2. **Test (RED)**: No new tests. Validation of this task is the green run of the full test suite plus shellcheck across all three touched files.
  3. **Implement (GREEN)**: Bump `plugins/tcs-git-helpers/.claude-plugin/plugin.json` `version` (semver minor — both M1 and M2 are user-visible behavior changes). Do NOT manually copy artifacts to `~/.claude/plugins/cache/` or marketplace dirs (per global auto-memory `feedback_no-manual-marketplace-sync.md`); rely on the marketplace sync on push.
  4. **Validate**: `cd plugins/tcs-git-helpers && bats tests/bats/ && python -m pytest tests/python/` — all green. `shellcheck scripts/block-bad-git-ops.sh scripts/lib/override.sh scripts/lib/cache.sh` — clean. Confirm plugin.json passes any repo-level JSON schema validation if applicable.
  5. **Success**:
     - [ ] plugin.json version bumped to next minor `[ref: SDD/Project Commands; lines: 265-266]`
     - [ ] Full test suite (BATS + pytest) green across the entire plugin `[ref: SDD/Quality Requirements; lines: 988-996]`
     - [ ] shellcheck clean on all three modified scripts `[ref: SDD/Project Commands; lines: 261-263]`

- [x] **T3.4 Phase 3 Final Validation** `[activity: validate]`

  - Run all BATS suites in `plugins/tcs-git-helpers/tests/bats/` — every file green.
  - Run all pytest suites in `plugins/tcs-git-helpers/tests/python/` — every file green.
  - `shellcheck` clean across `block-bad-git-ops.sh`, `lib/override.sh`, `lib/cache.sh`.
  - Confirm every PRD acceptance criterion has a passing test (mapping table below).
  - Confirm SDD Quality Requirements gates hold: zero false-positives on ahead branches, ≤1 extra `gh pr view` call per uncached MERGED push, sentinel double-tap still fires.
  - Spec status: ready to mark `complete` in `docs/XDD/specs/014-tcs-git-helpers-rules-fix/README.md`.

### Acceptance Criterion → Test mapping

| AC | Test file | Phase |
|----|-----------|-------|
| M1-AC1 — Squash-merge-trap deny preserved | `tests/bats/test_push_to_closed_pr.bats` | Phase 1 (T1.3) + Phase 3 (T3.2 Scenario C) |
| M1-AC2 — Head-ahead-of-merged allow + stderr note | `tests/bats/test_push_to_closed_pr.bats` | Phase 1 (T1.2 + T1.3) + Phase 3 (T3.2 Scenario B) |
| M1-AC3 — No-PR guard does not fire | `tests/bats/test_push_to_closed_pr.bats` | Phase 1 (T1.3) |
| M2-AC1 — Existing shell env-var override unchanged | `tests/bats/test_override.bats` | Phase 2 (T2.2) |
| M2-AC2 — Bash tool command-string prefix override recognized | `tests/bats/test_override.bats` | Phase 2 (T2.2) + Phase 3 (T3.2 Scenario A) |
| M2-AC3 — Fallback on absent tool input | `tests/bats/test_override.bats` | Phase 2 (T2.1 + T2.2) |
| M2-AC4 — Both env-var and command-string prefix present | `tests/bats/test_override.bats` | Phase 2 (T2.2) |
| M2-AC-REGEX — Prefix anchored to command start | `tests/bats/test_override.bats` + `tests/python/test_drift_check.py` | Phase 2 (T2.1 + T2.3) |
| S1-AC1 — Deny-message wording consistent | `tests/bats/test_push_to_closed_pr.bats` + `tests/bats/test_override.bats` | Phase 3 (T3.1) |
