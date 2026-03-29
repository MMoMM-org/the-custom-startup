---
title: "Phase 1: Test Foundation + Safety Net"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Test Foundation + Safety Net

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]` — 80+ tests, 30+ detect_learning tests, conftest.py
- `[ref: PRD/Feature M4]` — Test suite expansion acceptance criteria
- `[ref: SDD/Directory Map; tests/tcs-helper/]` — Test file structure

**Key Decisions**:
- Write tests for current behavior BEFORE modifying any code (safety net)
- Use `conftest.py` for shared fixtures (tmp queues, mock stdin, etc.)
- All tests use `tmp_path` — never touch `~/.claude/`

**Dependencies**:
- None — this is the first phase

---

## Tasks

Establishes comprehensive test coverage for existing behavior, creating the safety net required before any refactoring.

- [ ] **T1.1 Shared test fixtures (conftest.py)** `[activity: testing]`

  1. Prime: Read all existing test files in `tests/tcs-helper/` to understand current patterns `[ref: SDD/Directory Map]`
  2. Test: Verify fixtures work: `tmp_queue_path`, `mock_stdin`, `sample_queue_items`, `project_path`
  3. Implement: Create `tests/tcs-helper/conftest.py` with shared pytest fixtures
  4. Validate: All existing 31 tests still pass with conftest loaded
  5. Success: conftest.py exists, existing tests unaffected `[ref: PRD/M4]`

- [ ] **T1.2 detect_learning() unit tests** `[activity: testing]`

  1. Prime: Read `plugins/tcs-helper/scripts/lib/reflect_utils.py` — understand all 4 pattern categories and `detect_learning()` logic `[ref: SDD/Internal API: reflect_utils.py]`
  2. Test: Cover current patterns: explicit (remember:, note:), guardrail (don't ever, never), correction (no, actually, stop), positive (perfect, great); test return format `(type, pattern, confidence)`; test None returns for non-matches
  3. Implement: Write 15+ parametrized tests in `tests/tcs-helper/test_reflect_utils.py` covering every existing pattern
  4. Validate: All tests pass, confirming current behavior is captured
  5. Success: `detect_learning()` has 15+ direct unit tests documenting current behavior `[ref: PRD/M4]`

- [ ] **T1.3 check_learnings.py tests** `[activity: testing]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/scripts/check_learnings.py` `[ref: SDD/Interface Specifications]`
  2. Test: Empty queue, populated queue backup, backup directory creation, malformed queue file
  3. Implement: Create `tests/tcs-helper/test_check_learnings.py` with 5+ tests
  4. Validate: Tests pass
  5. Success: PreCompact hook has test coverage `[ref: PRD/M4]`

- [ ] **T1.4 post_commit_reminder.py tests** `[activity: testing]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/scripts/post_commit_reminder.py` `[ref: SDD/Interface Specifications]`
  2. Test: git commit detection, --amend exclusion, non-git commands, malformed stdin, output JSON format
  3. Implement: Create `tests/tcs-helper/test_post_commit_reminder.py` with 5+ tests
  4. Validate: Tests pass
  5. Success: PostToolUse hook has test coverage `[ref: PRD/M4]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run full suite: `python3 -m pytest tests/tcs-helper/ -v`
  - Target: 45+ tests passing (31 existing + 14+ new)
  - No test touches `~/.claude/` (verify with grep)
  - Success: Safety net established for all existing code `[ref: PRD/M4]`
