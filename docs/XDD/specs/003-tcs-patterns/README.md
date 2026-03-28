# Specification: 003-tcs-patterns

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-28 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-03-28 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Retroactively written — implementation already shipped |
| solution.md | in_progress | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | Retroactive spec — M3 was implemented without XDD workflow | Noticed during POST-ALL drift check; spec written after implementation to close the gap |
| 2026-03-28 | 17 skills total — PRD expanded from 8-skill placeholder | Sources.md documents all 17 as intentional; placeholder was written before full scope was decided |
| 2026-03-28 | TCS-native skills (7) not attributed to external sources | event-driven, api-design, go-idiomatic, node-service, python-project, mcp-server, obsidian-plugin authored directly for TCS |
| 2026-03-28 | test-design-reviewer: Andrea Laforgia via citypaul | Original author andlaf-ak/claude-code-agents; adapted by citypaul; re-adapted for TCS — chain preserved in skill |

## Context

M3 was implemented without following the XDD spec-first workflow. The `tcs-patterns` plugin
ships with 17 skills (vs 8 in the original placeholder PRD) covering architecture, API design,
testing, and platform patterns. All were intentional per `docs/concept/sources.md` but were
never documented in the spec.

This spec is written retroactively during the POST-ALL source fidelity audit (2026-03-28).

---
*This file is managed by the xdd-meta skill.*
