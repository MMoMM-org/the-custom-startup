# Specification: {{SPEC_ID}}-{{SPEC_NAME}}

## Status

| Field | Value |
|-------|-------|
| **Created** | {{CREATED_DATE}} |
| **Current Phase** | {{CURRENT_PHASE}} |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | {{LAST_UPDATED}} |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | {{PRD_STATUS}} | {{PRD_NOTES}} |
| solution.md | {{SDD_STATUS}} | {{SDD_NOTES}} |
| plan/ | {{PLAN_STATUS}} | {{PLAN_NOTES}} |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| {{DATE}} | {{DECISION}} | {{RATIONALE}} |

## Context

{{CONTEXT_NOTES}}

---
*This file is managed by the xdd-meta skill.*
