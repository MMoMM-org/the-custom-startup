---
title: "Phase 2: Hook System Cleanup (M1 + M2)"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Hook System Cleanup (M1 + M2)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1]` — Delete merge_hooks.py entirely
- `[ref: SDD/Implementation Examples; M2]` — cwd migration before/after
- `[ref: PRD/Feature M1]` — Eliminate merge_hooks.py acceptance criteria
- `[ref: PRD/Feature M2]` — Fix hook input contract acceptance criteria

**Key Decisions**:
- ADR-1: Delete merge_hooks.py entirely (confirmed)
- hooks.json commands lose `"${PWD}"` argument
- Scripts read `cwd` from JSON stdin with `os.getcwd()` fallback

**Dependencies**:
- Phase 1 complete (safety net tests in place)

---

## Tasks

Removes the unnecessary hook merge infrastructure and fixes the input contract for all hook scripts.

- [ ] **T2.1 Verify native hook loading** `[activity: testing]`

  1. Prime: Read `plugins/tcs-helper/hooks/hooks.json` and `plugins/tcs-helper/.claude-plugin/plugin.json` `[ref: SDD/External Interfaces]`
  2. Test: In a clean Claude Code session with tcs-helper enabled, verify hooks fire from `hooks/hooks.json` without any settings.json entries. Check session_start_reminder output appears.
  3. Implement: Document verification result. If native loading fails, stop and re-evaluate ADR-1.
  4. Validate: Hooks fire correctly from native hooks.json
  5. Success: Native hook loading confirmed `[ref: PRD/M1 AC-1]`

- [ ] **T2.2 Update hooks.json — remove ${PWD} args** `[activity: backend-api]`

  1. Prime: Read `hooks/hooks.json` and SDD implementation example for M2 `[ref: SDD/Implementation Examples; M2]`
  2. Test: Add tests in `test_capture_learning.py` that pass `cwd` via stdin JSON instead of CLI arg. Test both with and without `cwd` field (fallback to getcwd).
  3. Implement: Update `hooks.json` to remove `"${PWD}"` from all 3 commands. Update `capture_learning.py`, `session_start_reminder.py`, `check_learnings.py` to read `cwd` from `data.get('cwd', os.getcwd())`.
  4. Validate: All tests pass. Manual smoke test: hooks fire and capture a learning correctly.
  5. Success: No hook command passes `${PWD}` as CLI arg; scripts read `cwd` from JSON stdin `[ref: PRD/M2 AC-1, AC-2, AC-3]`

- [ ] **T2.3 Delete merge_hooks.py + update setup skill** `[activity: backend-api]`

  1. Prime: Read `plugins/tcs-helper/scripts/merge_hooks.py` and `plugins/tcs-helper/skills/setup/SKILL.md` Step 5 `[ref: SDD/Architecture Decisions; ADR-1]`
  2. Test: Verify no other file imports or calls merge_hooks.py (grep the codebase)
  3. Implement: Delete `scripts/merge_hooks.py`. Delete `tests/tcs-helper/test_merge_hooks.py`. Update `setup/SKILL.md` Step 5 to note that hooks are natively loaded (no action needed).
  4. Validate: Full test suite passes. No references to merge_hooks remain.
  5. Success: merge_hooks.py deleted, setup skill updated, 0 references remain `[ref: PRD/M1 AC-2, AC-4]`

- [ ] **T2.4 Clean repo settings.json + version bump** `[activity: backend-api]`

  1. Prime: Read `.claude/settings.json` (repo) `[ref: SDD/Deployment View]`
  2. Test: N/A (config change)
  3. Implement: Remove the 4 tcs-helper hook entries from `.claude/settings.json` (keep `enabledPlugins`, `claudeMdExcludes`, `cleanupPeriodDays`). Bump `plugin.json` version to `3.0.0`.
  4. Validate: Claude Code session starts cleanly. Hooks still fire (from native hooks.json). No double-fire.
  5. Success: Settings.json clean, plugin version 3.0.0 `[ref: PRD/M1 AC-3]`

- [ ] **T2.5 Phase Validation** `[activity: validate]`

  - Run full suite: `python3 -m pytest tests/tcs-helper/ -v`
  - Verify: test count = Phase 1 total minus 11 (deleted merge_hooks tests) plus new M2 tests
  - Manual: start new Claude Code session, type a correction, verify it appears in queue
  - Success: Hook system works end-to-end via native loading `[ref: PRD/M1, M2]`
