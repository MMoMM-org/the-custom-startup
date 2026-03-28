# Specification: 002-core-workflow

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-26 |
| **Current Phase** | Completed |
| **Last Updated** | 2026-03-28 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | M1 — Core Workflow Rebuild |
| solution.md | completed | |
| plan/ | completed | 6 phases, all marked completed |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-26 | Migrated from .start/specs/ → docs/XDD/specs/ | ADR-5: standardised spec location |
| 2026-03-28 | Drift fixes applied (8 warnings, 7 failures resolved) | Post-implementation validation pass |

## Context

M1 (labelled "Core Workflow Rebuild" in documents) implements the tcs-workflow plugin rebuild:
XDD skill family renames (specify → xdd), TDD enforcement (Iron Law, test-first gate), core
orchestration (implement, validate, review), and parallel skills expansion. All 6 phases completed.
Spec documents carried `status: draft` frontmatter — updated to `completed` during drift audit.

---
*This file is managed by the xdd-meta skill.*
