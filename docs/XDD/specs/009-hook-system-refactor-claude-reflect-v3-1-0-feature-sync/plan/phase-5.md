---
title: "Phase 5: Semantic Validation + Integration (C1 + C2)"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Semantic Validation + Integration (C1 + C2)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Internal API: semantic_detector.py]` — Full API specification
- `[ref: SDD/Error Handling]` — Claude CLI fallback behavior
- `[ref: PRD/Feature C1]` — Semantic AI validation acceptance criteria
- `[ref: PRD/Feature C2]` — Contradiction detection acceptance criteria

**Key Decisions**:
- ADR-2: semantic_detector.py in scripts/lib/
- Optional module — falls back gracefully when claude CLI unavailable
- Only validates items with confidence < 0.7
- Controlled via `TCS_SEMANTIC_VALIDATION=false` env var

**Dependencies**:
- Phase 4 complete (dedup infrastructure in place — contradiction detection extends it)

---

## Tasks

Adds optional AI-powered validation and contradiction detection. These are "Could Have" features — the system works fully without them.

- [ ] **T5.1 semantic_detector.py — core module** `[activity: domain-modeling]`

  1. Prime: Read claude-reflect v3.1.0's `semantic_detector.py` for API patterns. Read SDD API spec. `[ref: SDD/Internal API: semantic_detector.py]`
  2. Test: `semantic_analyze()` returns dict with expected fields; returns None when claude CLI unavailable; returns None on 5s timeout; `validate_queue_items()` filters false positives; only validates items with confidence < 0.7; respects `TCS_SEMANTIC_VALIDATION=false`
  3. Implement: Create `plugins/tcs-helper/scripts/lib/semantic_detector.py` with `semantic_analyze()`, `validate_queue_items()`, `detect_contradictions()`. Use `subprocess.run(timeout=5)` for claude CLI calls.
  4. Validate: 10+ tests in `tests/tcs-helper/test_semantic_detector.py`. All mock the claude CLI (no real API calls in tests).
  5. Success: Semantic validation available as opt-in module `[ref: PRD/C1 AC-1, AC-2, AC-3, AC-4]`

- [ ] **T5.2 Contradiction detection** `[activity: domain-modeling]`

  1. Prime: Read SDD detect_contradictions() spec and existing dedup from T4.3 `[ref: SDD/Internal API: semantic_detector.py; detect_contradictions()]`
  2. Test: Direct contradiction ("use tabs" vs "use spaces") → detected; time-based contradiction (newer recommended); no contradiction → empty result; fallback to keyword overlap when claude unavailable
  3. Implement: Implement `detect_contradictions()` in `semantic_detector.py`. Keyword-based fallback: extract key terms, compare against existing entries, flag if > 60% overlap with opposite sentiment.
  4. Validate: 5+ tests pass
  5. Success: Contradictions flagged during /memory-add `[ref: PRD/C2 AC-1, AC-2, AC-3]`

- [ ] **T5.3 Wire semantic validation into /memory-add** `[activity: domain-modeling]`

  1. Prime: Read `/memory-add` SKILL.md (already updated in T4.2 and T4.3) `[ref: PRD/C1, C2]`
  2. Test: N/A (skill workflow — validated manually)
  3. Implement: Update `/memory-add` SKILL.md to optionally call `validate_queue_items()` and `detect_contradictions()` during processing. Guard with `TCS_SEMANTIC_VALIDATION` env var check.
  4. Validate: Manual test: queue items with low confidence, run /memory-add with semantic validation enabled
  5. Success: /memory-add uses semantic validation when available `[ref: PRD/C1, C2]`

- [ ] **T5.4 Final integration validation** `[activity: validate]`

  - Run full suite: `python3 -m pytest tests/tcs-helper/ -v`
  - Target: **80+ tests passing**
  - End-to-end manual test:
    1. Start Claude Code session → session_start_reminder fires
    2. Type a correction → capture_learning captures it
    3. Type a CJK correction → captured with correct confidence
    4. Trigger a tool error → captured as tool_error
    5. Run /memory-add → dedup checks, semantic validation (if enabled), routing
    6. Verify git commit → post_commit_reminder fires
  - Verify no hook references merge_hooks.py
  - Verify plugin.json version is 3.0.0
  - Success: All features working, 80+ tests, clean codebase `[ref: PRD/M1, M2, M3, M4, S1, S2, C1, C2]`

- [ ] **T5.5 Documentation + CHANGELOG** `[activity: documentation]`

  1. Prime: Read existing README and CHANGELOG
  2. Test: N/A
  3. Implement: Update CHANGELOG with v3.0.0 entry. Update README if needed. Update `docs/ai/memory/decisions.md` with ADR-1 (merge_hooks.py removal rationale).
  4. Validate: Documentation accurate and complete
  5. Success: Release documentation ready `[ref: PRD/M1]`
