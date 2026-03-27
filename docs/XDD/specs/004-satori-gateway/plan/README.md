---
title: "M4 — Satori MCP Gateway"
spec: "004-satori-gateway"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION]` markers addressed
- [x] All specification file paths correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section complete
- [x] All implementation phases defined with linked phase files
- [x] Dependencies between phases explicit (no circular dependencies)
- [x] Parallel work tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection
- [x] Every phase references relevant SDD sections
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/004-satori-gateway/requirements.md` — PRD (R1–R6, acceptance criteria)
- `docs/XDD/specs/004-satori-gateway/solution.md` — SDD (architecture, schemas, hook design, tool contracts)

**Reference implementation** (read before coding context or session modules):
- `modules/satori/` — miyo-satori repo root (git submodule)
- context-mode source (cloned at `/tmp/context-mode-research/` during analysis):
  - `src/session/db.ts` — SessionDB, session_events schema, FIFO eviction, dedup
  - `src/session/snapshot.ts` — `buildResumeSnapshot()`, XML format, priority trimming
  - `src/session/extract.ts` — tool payload → SessionEvent mapping
  - `src/db-base.ts` — SQLiteBase, WAL pragmas, BunSQLiteAdapter

**Key Design Decisions**:
- `satori_exec(server, tool, args)` — single entry point; no `<server>_<tool>` namespace tools
- DB at `.satori/db.sqlite` (repo-local, gitignored); global config at `~/.satori/config.toml`
- Session event store (13 categories, priority tiers) + content capture store (FTS5) in one DB
- XML snapshot ≤2048 bytes; priority-tiered trimming; written at PreCompact, consumed at SessionStart
- Handler interface: `beforeCall` → security scan → downstream → `afterCall` → capture → summarize
- Hot/cold lifecycle: servers start on first `satori_exec` call, stopped on Satori shutdown
- Auto-registration: `.mcp.json` → import entries → `.mcp.satori-json`

**Implementation Commands** (run from `modules/satori/`):
```bash
cd /Volumes/Moon/Coding/the-custom-startup/modules/satori

npm install
npm run build
npm test
npm run typecheck
```

**Target repo**: `https://github.com/MMoMM-org/miyo-satori`
All implementation phases build miyo-satori. Phase 7 handles TCS submodule integration (R6.1).

---

## Implementation Phases

Each phase follows: **Prime** (context) → **Test** (RED) → **Implement** (GREEN) → **Validate** (REFACTOR + verify).

> **Dependency order**:
> - Phase 1 is the foundation. All phases require it.
> - Phases 2 and 3 can run in parallel after Phase 1.
> - Phase 4 requires Phase 3 (registry needed for routing).
> - Phase 5 requires Phases 2 and 4 (needs both DB and lifecycle).
> - Phase 6 requires Phase 5 (hooks wire into completed tools).
> - Phase 7 requires Phase 6 (E2E requires all components).

- [x] [Phase 1: Repository Foundation](phase-1.md)
- [ ] [Phase 2: Context Module](phase-2.md)
- [ ] [Phase 3: Config, Registry & Security](phase-3.md) `[parallel: true]` with Phase 2
- [ ] [Phase 4: Lifecycle Management](phase-4.md)
- [ ] [Phase 5: Tools & Gateway Routing](phase-5.md)
- [ ] [Phase 6: Hooks & Session Integration](phase-6.md)
- [ ] [Phase 7: TCS Integration & E2E Validation](phase-7.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and linked as `[Phase N: Title](phase-N.md)` | ✅ |
