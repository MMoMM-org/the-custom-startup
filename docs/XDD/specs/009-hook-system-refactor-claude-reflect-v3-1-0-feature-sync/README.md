# Specification: 009-Hook System Refactor + claude-reflect v3.1.0 Feature Sync

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-29 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-03-29 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Approved 2026-03-29 |
| solution.md | completed | Approved 2026-03-29, 3 ADRs confirmed |
| plan/ | completed | 5 phases, 21 tasks, approved 2026-03-29 |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | Start with PRD | Spec-first workflow per project convention |
| 2026-03-29 | Scope: hook refactor + selective feature port from claude-reflect v3.1.0 | Original has significant features (semantic detection, /reflect, tool error extraction) missing in TCS fork; hooks system has 5 known issues |
| 2026-03-29 | ADR-1: Delete merge_hooks.py entirely | Native plugin hooks make it redundant. Clean break. |
| 2026-03-29 | ADR-2: semantic_detector.py in scripts/lib/ | Consistent with existing structure |
| 2026-03-29 | ADR-3: Port patterns from original, adapt | Fastest path, well-tested upstream |
| 2026-03-29 | M1 simplified: no migration logic | Single-user context, stale hooks already cleaned manually |
| 2026-03-29 | Spec finalized: PRD + SDD + PLAN approved | Ready for implementation |

## Context

Two workstreams converging into one spec:

1. **Hook System Refactor**: eliminate merge_hooks.py, use native Claude Code plugin hooks, fix scope handling (5 issues identified: no scope tracking, hardcoded --scope r, pre-resolved template vars, PWD handling, unnecessary merge step)

2. **claude-reflect v3.1.0 Feature Sync**: selectively port valuable features adapted to Memory Bank architecture. Key candidates: semantic AI detection (~350 LOC), improved pattern matching (CJK, false positives), /reflect 10-phase workflow, tool error/rejection extraction, cross-tier dedup + contradiction detection, 160-test suite.

Architecture constraint: Original routes to CLAUDE.md (9 tiers, flat). TCS uses Memory Bank (6 categories, structured). All ported features must adapt to Memory Bank routing.

---
*This file is managed by the xdd-meta skill.*
