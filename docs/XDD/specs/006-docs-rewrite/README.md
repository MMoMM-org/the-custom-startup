# Specification: 006-docs-rewrite

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-28 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-03-28 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | |
| solution.md | completed | 4 ADRs confirmed |
| plan/ | completed | 5 phases, 22 tasks |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | Restructure IA (not in-place rewrite) | v2 has too many breaking changes for patch updates; clean hierarchy matches new mental model |
| 2026-03-28 | Primary audience: new users | Upgraders can diff git history; new users need clear onboarding |
| 2026-03-28 | Promote concept/ content, then delete | Valuable insights exist but directory is internal; promote into philosophy + xdd docs |
| 2026-03-28 | the-custom-philosophy.md replaces PHILOSOPHY.md | Keeps attribution and custom fork narrative intact |
| 2026-03-28 | Add about/sources.md attribution doc | Keep citypaul, rsmdt attribution visible and explicit |
| 2026-03-28 | PRD approved, transition to SDD | All sections complete, open questions resolved, CHANGELOG.md added as Should Have |
| 2026-03-28 | SDD approved, transition to PLAN | All 4 ADRs confirmed by user |

## Context

Full brainstorm design saved at: `docs/XDD/ideas/2026-03-28-docs-rewrite.md`

---
*This file is managed by the specify-meta skill.*
