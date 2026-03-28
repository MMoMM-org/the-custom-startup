# Specification: 005-memory-mcp

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-03-27 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-03-27 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | PRD complete — all sections filled, no clarification markers |
| solution.md | completed | All 7 ADRs confirmed |
| plan/ | completed | 5 phases, 19 tasks, dependency graph defined |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-27 | Architecture: Transparent — hooks do work, skills unchanged | Minimises TCS changes; Satori owns its own concerns |
| 2026-03-27 | Routing: really-short-lived → Satori DB; short-lived stays in context.md | context.md is human-readable + git-tracked; cost of moving outweighs benefit |
| 2026-03-27 | ctx_execute: BuiltinRuntime "bash" pseudo-server in satori_exec | Natural fit; all router pipeline applies automatically |
| 2026-03-27 | satori_kb: new dedicated tool, separate kb.sqlite | Clean separation from session state (satori_context) and execution (satori_exec) |
| 2026-03-27 | context-search skill: ships from miyo-satori, not tcs-workflow | Directly interfaces with Satori context DB; TCS has no business owning that interface |
| 2026-03-27 | PRD complete — moved to SDD phase | All sections filled; validation checklist passed; 3 open questions deferred to SDD |
| 2026-03-28 | SDD complete — all 7 ADRs confirmed | ADR-5 revised: Satori owns hooks entirely, TCS has zero dependency on Satori internals |
| 2026-03-28 | PLAN complete — 5 phases, 19 tasks | Phases 1–4 sequential with parallel opportunities; Phase 5 E2E validation |
| 2026-03-27 | Kairn: context.backend field, warning-only for MVP | Replaces SQLite entirely post-MVP; field reserves the extension point without blocking M5 |
| 2026-03-27 | ctx_stats / ctx_doctor: post-MVP (M5.1) | Observability tools, not blocking for core integration |

## Context

Connects M2 (file-based memory) with M4 (Satori MCP gateway). Adds execution tools
(satori_exec "bash"), knowledge base tools (satori_kb), detection for skills/hooks,
install opt-in, and Kairn prep field. All features degrade gracefully when Satori absent.

Source reference: context-mode (mksglu/context-mode) — PolyglotExecutor, FTS5 search stack,
progressive throttling, intent-driven mode, smartTruncate, #buildSafeEnv.

---
*This file is managed by the xdd-meta skill.*
