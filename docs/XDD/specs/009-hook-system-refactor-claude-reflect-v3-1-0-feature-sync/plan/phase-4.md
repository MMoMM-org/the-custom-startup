---
title: "Phase 4: Tool Errors + Deduplication (S1 + S2)"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Tool Errors + Deduplication (S1 + S2)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Secondary Flow: Tool Error Capture]` — S1 tool error flow
- `[ref: SDD/Interface Specifications; Data Storage Changes]` — Extended queue item format
- `[ref: PRD/Feature S1]` — Tool error extraction acceptance criteria
- `[ref: PRD/Feature S2]` — Cross-category deduplication acceptance criteria

**Key Decisions**:
- Tool errors queued with `item_type: 'tool_error'` (new field, backward compatible)
- Only persistent errors captured (seen 2+ times in session)
- Dedup runs in `/memory-add` skill, not in hooks
- Exact duplicates silently skipped; near-duplicates flagged to user

**Dependencies**:
- Phase 3 complete (pattern detection extended, queue item format understood)

---

## Tasks

Adds tool error capture to the PostToolUse hook and cross-category deduplication to /memory-add.

- [ ] **T4.1 Tool error detection in post_commit_reminder.py** `[activity: backend-api]`

  1. Prime: Read `post_commit_reminder.py` and SDD tool error flow `[ref: SDD/Secondary Flow: Tool Error Capture]`
  2. Test: Tool output with error → queued with `item_type: 'tool_error'`; transient error (first occurrence) → not captured; repeated error → captured; categorization: module_not_found, connection_refused, etc.; non-error tool output → no queue write
  3. Implement: Extend `post_commit_reminder.py` to detect error patterns in `tool_output`. Add error pattern categorization. Queue persistent errors (track occurrence count in memory within session via simple counter file).
  4. Validate: 8+ tests pass. Existing git commit detection still works.
  5. Success: Persistent tool errors captured and categorized `[ref: PRD/S1 AC-1, AC-2, AC-4]`

- [ ] **T4.2 Tool error routing in /memory-add** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/skills/memory-add/SKILL.md` `[ref: PRD/S1 AC-3]`
  2. Test: N/A (skill workflow change — validated via manual test)
  3. Implement: Update `/memory-add` SKILL.md to route `item_type: 'tool_error'` items to `troubleshooting.md` by default. Add routing rule.
  4. Validate: Manual test: queue a tool_error item, run /memory-add, verify it routes to troubleshooting.md
  5. Success: Tool errors route to troubleshooting.md `[ref: PRD/S1 AC-3]`

- [ ] **T4.3 Cross-category deduplication** `[activity: domain-modeling]`

  1. Prime: Read all 6 Memory Bank category files to understand current content format `[ref: SDD/Acceptance Criteria; S2]`
  2. Test: Exact duplicate across files → silently skipped; near-duplicate (same meaning) → flagged; no duplicate → passes through; dedup performance: 20 items against 6 files < 5 seconds
  3. Implement: Add `find_duplicates(learning: str, memory_dir: str) -> list` to `reflect_utils.py`. Checks all 6 category files for exact and near-duplicate matches (keyword overlap scoring). Update `/memory-add` SKILL.md to call dedup before writing.
  4. Validate: 6+ tests for dedup logic. Manual test with /memory-add.
  5. Success: Duplicates detected across categories `[ref: PRD/S2 AC-1, AC-2, AC-3, AC-4]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Run full suite: `python3 -m pytest tests/tcs-helper/ -v`
  - Target: 75+ tests passing
  - Manual: trigger a tool error, run /memory-add, verify routing
  - Success: Tool errors and dedup working end-to-end `[ref: PRD/S1, S2]`
