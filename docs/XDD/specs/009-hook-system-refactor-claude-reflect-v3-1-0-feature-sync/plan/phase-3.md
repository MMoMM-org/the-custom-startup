---
title: "Phase 3: Pattern Detection Extension (M3)"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Pattern Detection Extension (M3)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Internal API: reflect_utils.py]` — Extended detect_learning() specification
- `[ref: SDD/Implementation Examples; M3]` — Pattern matching pipeline with false positive filter
- `[ref: PRD/Feature M3]` — Expanded pattern detection acceptance criteria

**Key Decisions**:
- ADR-3: Port patterns from claude-reflect v3.1.0, adapt for Memory Bank
- Code blocks stripped before matching
- False positive filter runs after pattern match, before confidence calculation
- Minimum 5-char length gate

**Dependencies**:
- Phase 2 complete (hook scripts already read cwd from JSON)

---

## Tasks

Extends pattern detection with CJK support, false positive filtering, code block exclusion, and context-aware confidence scoring. This is the highest-value change for learning capture quality.

- [ ] **T3.1 strip_code_blocks() + is_false_positive()** `[activity: domain-modeling]`

  1. Prime: Read claude-reflect v3.1.0's `reflect_utils.py` (fetch from GitHub if needed) for FALSE_POSITIVE_PATTERNS and NON_CORRECTION_PHRASES `[ref: SDD/Internal API: reflect_utils.py]`
  2. Test: `strip_code_blocks()`: text with no blocks unchanged; single block removed; multiple blocks removed; nested blocks handled; inline code preserved. `is_false_positive()`: "no problem" → true; "don't worry" → true; "no, that's wrong" → false; "actually, good idea" → true
  3. Implement: Add both functions to `reflect_utils.py`. Port FALSE_POSITIVE_PATTERNS and NON_CORRECTION_PHRASES lists from original.
  4. Validate: 10+ tests pass for both functions
  5. Success: Code blocks excluded, false positives filtered `[ref: PRD/M3 AC-2, AC-3]`

- [ ] **T3.2 CJK correction patterns** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read claude-reflect v3.1.0's CJK_CORRECTION_PATTERNS (13 patterns: Japanese 8, Chinese 3, Korean 2) `[ref: SDD/Internal API: reflect_utils.py]`
  2. Test: Each CJK pattern matches with expected confidence (0.60-0.90); mixed-language text matches; CJK text inside code block does not match
  3. Implement: Add CJK_CORRECTION_PATTERNS to `reflect_utils.py`. Integrate into `detect_learning()` pattern matching pipeline.
  4. Validate: 8+ tests for CJK patterns pass
  5. Success: CJK corrections detected with appropriate confidence `[ref: PRD/M3 AC-1]`

- [ ] **T3.3 calculate_confidence() + multi-pattern boost** `[activity: domain-modeling]`

  1. Prime: Read claude-reflect v3.1.0's confidence adjustment logic `[ref: SDD/Internal API: reflect_utils.py; calculate_confidence()]`
  2. Test: Short text boost (+0.05 for < 20 chars); long text penalty (-0.10 for > 500 chars); multi-pattern boost (+0.05 per extra, cap 0.95); minimum length gate (< 5 chars → None)
  3. Implement: Add `calculate_confidence()` to `reflect_utils.py`. Wire into `detect_learning()`.
  4. Validate: 8+ confidence calculation tests pass
  5. Success: Confidence reflects text context and pattern density `[ref: PRD/M3 AC-4, AC-5]`

- [ ] **T3.4 Integrate extended pipeline into detect_learning()** `[activity: domain-modeling]`

  1. Prime: Read SDD implementation example for extended detect_learning() `[ref: SDD/Implementation Examples; M3]`
  2. Test: Full pipeline tests: explicit still works; guardrail still works; correction + CJK; positive; false positive filtered; code block excluded; short text rejected; multi-pattern boosted
  3. Implement: Refactor `detect_learning()` to follow the 8-step pipeline from SDD. Preserve all existing pattern matches (no regressions).
  4. Validate: All Phase 1 detect_learning tests still pass (regression check) + all new tests pass
  5. Success: detect_learning() has 30+ tests, all passing `[ref: PRD/M3, M4]`

- [ ] **T3.5 Phase Validation** `[activity: validate]`

  - Run full suite: `python3 -m pytest tests/tcs-helper/ -v`
  - Target: 65+ tests passing
  - Verify: no regressions from Phase 1/2 tests
  - Manual: type CJK correction in Claude Code session, verify queue capture
  - Success: Pattern detection extended with zero regressions `[ref: PRD/M3, M4]`
