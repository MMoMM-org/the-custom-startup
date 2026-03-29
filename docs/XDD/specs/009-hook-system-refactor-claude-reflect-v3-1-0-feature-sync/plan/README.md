---
title: "Hook System Refactor + claude-reflect v3.1.0 Feature Sync"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/009-hook-system-refactor-claude-reflect-v3-1-0-feature-sync/requirements.md` — Product Requirements
- `docs/XDD/specs/009-hook-system-refactor-claude-reflect-v3-1-0-feature-sync/solution.md` — Solution Design

**Key Design Decisions**:
- **ADR-1**: Delete merge_hooks.py entirely — Claude Code natively loads hooks/hooks.json from enabled plugins
- **ADR-2**: semantic_detector.py in scripts/lib/ — Co-located with reflect_utils.py
- **ADR-3**: Port patterns from original, adapt — Copy claude-reflect v3.1.0 patterns, adapt confidence for Memory Bank

**Implementation Context**:
```bash
# Testing (always activate venv first)
source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -v

# Quick single-file test
source venv/bin/activate && python3 -m pytest tests/tcs-helper/test_reflect_utils.py -v

# Verify hook scripts run without error
echo '{"prompt":"test","cwd":"/tmp"}' | python3 plugins/tcs-helper/scripts/capture_learning.py
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Test Foundation + Safety Net](phase-1.md)
- [x] [Phase 2: Hook System Cleanup (M1 + M2)](phase-2.md)
- [ ] [Phase 3: Pattern Detection Extension (M3)](phase-3.md)
- [ ] [Phase 4: Tool Errors + Deduplication (S1 + S2)](phase-4.md)
- [ ] [Phase 5: Semantic Validation + Integration (C1 + C2)](phase-5.md)

**Dependency graph:**
```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5
(tests)    (hooks)     (patterns)   (should)    (could)
```

All phases are sequential — each builds on the previous. Within phases, some tasks are parallelizable.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
