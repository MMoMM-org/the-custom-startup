# Specification: 008-memory-claude-md-optimize

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-29 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-03-29 |


## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | PRD complete, all sections filled, validated |
| solution.md | completed | SDD complete, all ADRs confirmed |
| plan/ | completed | 3 phases, 15 tasks |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | Spec created, starting with PRD | Full XDD workflow per project rules |
| 2026-03-29 | Name: memory-claude-md-optimize | Consistent with other memory-* skills, descriptive for user invocation |
| 2026-03-29 | All 3 scopes (g/p/r) with user choice | User needs global optimization too, ask which scopes at invocation |
| 2026-03-29 | Replace @ imports with descriptive references | @imports load everything into context; descriptive refs let Claude decide when to load |
| 2026-03-29 | Include quality optimization from Anthropic plugin | Not just migration — also audit, score, and optimize content quality |
| 2026-03-29 | ADR-1: Pure Skill Architecture (no Python helpers) | Simplest, portable, matches tcs-helper patterns — Claude uses tools directly |
| 2026-03-29 | ADR-2: Rubric-Guided LLM Categorization | Claude judgment + reference doc rubric > keyword matching for edge cases |
| 2026-03-29 | ADR-3: In-Place Suffixed Backups | Easy to find and rollback; matches PRD spec |
| 2026-03-29 | ADR-4: Non-Blocking Secret Detection | Warn in report, don't block — user retains control |
| 2026-03-29 | SDD complete, moving to PLAN | All 4 ADRs confirmed, project path fix applied |
| 2026-03-29 | PLAN complete: 3 phases, 15 tasks | Phase 1: refs (parallel), Phase 2: SKILL.md, Phase 3: validation |

## Context

A tcs-helper skill that optimizes and migrates flat CLAUDE.md files into the Memory Bank structure. Combines quality audit (conciseness, actionability, currency, architecture clarity) with structural migration (categorize content into Memory Bank categories). Replaces @-imports with descriptive references. Non-destructive with backups, user review before applying, and archive option.

Reference: Anthropic's claude-md-management plugin for quality scoring patterns.

---
*This file is managed by the xdd-meta skill.*
