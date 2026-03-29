# Specification: 008-memory-claude-md-optimize

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-29 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-03-29 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | PRD complete, all sections filled, validated |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | Spec created, starting with PRD | Full XDD workflow per project rules |
| 2026-03-29 | Name: memory-claude-md-optimize | Consistent with other memory-* skills, descriptive for user invocation |
| 2026-03-29 | All 3 scopes (g/p/r) with user choice | User needs global optimization too, ask which scopes at invocation |
| 2026-03-29 | Replace @ imports with descriptive references | @imports load everything into context; descriptive refs let Claude decide when to load |
| 2026-03-29 | Include quality optimization from Anthropic plugin | Not just migration — also audit, score, and optimize content quality |

## Context

A tcs-helper skill that optimizes and migrates flat CLAUDE.md files into the Memory Bank structure. Combines quality audit (conciseness, actionability, currency, architecture clarity) with structural migration (categorize content into Memory Bank categories). Replaces @-imports with descriptive references. Non-destructive with backups, user review before applying, and archive option.

Reference: Anthropic's claude-md-management plugin for quality scoring patterns.

---
*This file is managed by the xdd-meta skill.*
