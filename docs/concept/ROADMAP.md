# TCS v2 — Roadmap

**Status:** Planning phase complete. Implementation ready for M1 + M2.
**Branch:** `feat/tcs-v2-roadmap`
**Last updated:** 2026-03-25

---

## Overview

TCS v2 is the full rebuild of The Custom Startup into a spec-driven, test-verified, memory-aware development framework. The rebuild is organized into two parallel tracks and five milestones.

The methodology foundation (TDD+SDD integration) is not a standalone milestone — it is woven into M1 and M2 as a design constraint. See `docs/concept/tdd-sdd-integration.md`.

---

## Tracks

```
Track A: Workflow & Skills          Track B: Memory & Context
─────────────────────────           ──────────────────────────
M1: Core Workflow Rebuild           M2: Memory + CLAUDE.md System
    tcs-start → tcs-workflow            docs/ai/memory/ structure
    Superpowers absorption              Modular CLAUDE.md templates
    New skills + enhanced skills        memory-route/sync/cleanup/promote
    TDD+SDD integration                 tcs-helper:setup
                  │                                │
M3: tcs-patterns Plugin             M4: Satori/MCP Gateway
    Domain knowledge library            context-mode as gateway
    DDD, hexagonal, functional          Security scanner
    ADR agent                           Kairn integration
                  └──────────┬──────────┘
                             │
                    M5: Memory + MCP Integration
                        Short-lived → context server
                        Semantic queries via Kairn
                        File memory + MCP in sync
```

**Dependency order:**
- M1 and M2 are independent — can be built in parallel
- M3 requires M1 stable (domain skills need tcs-workflow in place)
- M4 is standalone (MCP infrastructure, no TCS skill dependencies)
- M5 requires M2 + M4 complete

---

## Milestones

### M1 — Core Workflow Rebuild
**Spec:** `docs/XDD/specs/002-core-workflow/`
**Branch:** `feat/tcs-v2-m1-workflow` (when ready to implement)
**Status:** Spec in progress

Renames `tcs-start` → `tcs-workflow` and absorbs the best of superpowers, citypaul, and centminmod into the core workflow plugin.

Key deliverables:
- Plugin rename + user migration path
- New skills: `tdd`, `verify`, `receive-review`, `parallel-agents`, `git-worktree`, `finish-branch`, `guide`
- Enhanced skills: `brainstorm` (spec-review loop), `debug` (iron law), `review` (dispatch), `implement` (fresh-subagent + two-stage review)
- TDD+SDD integration: PLAN tasks have explicit RED/GREEN/REFACTOR steps anchored to SDD contracts

Reference: `docs/concept/overlap-analysis.md` — superpowers and citypaul absorption table.

---

### M2 — Memory + CLAUDE.md System
**Spec:** `docs/XDD/specs/001-memory-claude/`
**Branch:** `feat/tcs-v2-m2-memory` (when ready to implement)
**Status:** Spec complete — ready for `/implement`

Builds the file-based memory system and modular CLAUDE.md approach. No MCP dependency.

Key deliverables:
- `docs/ai/memory/` directory structure (general, tools, domain, decisions, context, troubleshooting)
- Lean CLAUDE.md design: root (<100 lines) + per-directory (src/, test/, docs/, docs/ai/)
- Scope × Lifetime × Category routing model
- 4 skills in `tcs-helper`: `memory-route`, `memory-sync`, `memory-cleanup`, `memory-promote`
- `tcs-helper:setup` — project onboarding wizard

Reference: `docs/concept/v2/TCS v2 Memory & Context Layout Spec.md`, `docs/concept/v2/RepoStruktur_Claude.md`.

---

### M3 — tcs-patterns Plugin
**Spec:** `docs/XDD/specs/003-tcs-patterns/`
**Branch:** `feat/tcs-v2-m3-patterns` (when ready to implement)
**Status:** Placeholder — specify after M1 stable

New optional plugin for domain knowledge skills.

Key deliverables:
- New `tcs-patterns` plugin structure
- Domain skills: DDD, hexagonal-architecture, functional, typescript-strict, mutation-testing, frontend-testing, react-testing, twelve-factor
- ADR agent in `tcs-team:the-architect/record-decision.md`
- Promotion pipeline from M2's `memory-promote` into tcs-patterns

Reference: `docs/concept/overlap-analysis.md` — citypaul extraction table.

---

### M4 — Satori/MCP Gateway
**Spec:** `docs/XDD/specs/004-satori-gateway/`
**Branch:** `feat/tcs-v2-m4-satori` (when ready to implement)
**Status:** Placeholder — specify as standalone project

Extends `context-mode` MCP server into a full gateway with security scanning and optional Kairn integration.

Key deliverables:
- context-mode as MCP Gateway/Registry (single entry point for multiple downstream servers)
- Hot/cold mode: only load MCP servers when enabled and needed
- Security scanner: scan MCP server configs before exposing tools to Claude
- Kairn integration: optional semantic project memory as upgrade over SQLite
- g/p/r config separation for MCP definitions
- Potential rename: "Satori" (gateway that distills context to its essence)

Reference: `docs/concept/v2/context-mode-MCP-Server.md`.

---

### M5 — Memory + MCP Integration
**Spec:** `docs/XDD/specs/005-memory-mcp/`
**Branch:** `feat/tcs-v2-m5-mcp-memory` (when ready to implement)
**Status:** Placeholder — specify after M2 + M4 complete

Retrofits M2's memory system to use the M4 context server for short-lived and session data.

Key deliverables:
- "Really short lived" session data → context-mode DB (not file system)
- `tcs-helper:context-search` skill for semantic queries via Kairn (when available)
- Updated routing table: lifetime "really short lived" → MCP, all others stay file-based
- Graceful degradation: all workflows still function without MCP (file fallback)
- Session continuity across context compaction via context-mode session guide

Reference: `docs/concept/v2/TCS v2 Memory & Context Layout Spec.md` §5.

---

## Concept Documents

All design decisions are documented in `docs/concept/`:

| Document | Purpose |
|---|---|
| `tdd-sdd-integration.md` | How SDD contracts become TDD test targets |
| `overlap-analysis.md` | What to absorb/merge/skip from all source repos |
| `tcs-vision.md` | North star: plugin architecture, memory model, evaluation criteria |
| `sources.md` | Attribution for all source repos and articles |
| `ROADMAP.md` | This file |
| `v2/` | Raw research and Perplexity threads (reference only) |

---

## Open Decisions

- [ ] ADR file location: `docs/adr/` or `.claude/adr/` ?
- [ ] tcs-patterns: same repo as TCS or separate marketplace repo?
- [ ] Satori rename: keep `context-mode` name or rename to `satori`?
- [ ] YOLO mode memory: structured dump file so user can review session writes (from v2 spec §4.3)
- [ ] context-mode discovery: how TCS detects if context-mode/Kairn is installed (tool availability check?)
