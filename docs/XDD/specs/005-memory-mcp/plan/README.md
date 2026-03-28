---
title: "Memory + MCP Integration (M5)"
spec: 005-memory-mcp
status: draft
version: "1.0"
---

# Implementation Plan
## Memory + MCP Integration (M5)

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/005-memory-mcp/requirements.md` — Product Requirements (F1–F7, acceptance criteria)
- `docs/XDD/specs/005-memory-mcp/solution.md` — Solution Design (ADRs, schemas, interfaces, directory map)

**Source Reference** (port, not dependency):
- `github.com/mksglu/context-mode` — executor.ts, runtime.ts, truncate.ts, server.ts

**Key Design Decisions**:
- **ADR-1**: BuiltinRuntime dispatched via router branch — not via LifecycleManager; router checks `runtime === 'builtin'` before lifecycle
- **ADR-2**: KnowledgeDB in separate `kb.sqlite` — extends SQLiteBase, WAL mode, FTS5 Porter + trigram
- **ADR-3**: Throttle state in-memory — `Map<sessionId, number>` in KnowledgeDB instance, resets on restart
- **ADR-4**: Execution code in `src/execution/` — separate from tools/, lifecycle/, context/
- **ADR-5**: Satori owns hooks entirely — `scripts/install-hooks.sh` registers hooks; TCS only calls it
- **ADR-6**: Session guide format reuses `buildResumeSnapshot()` — no new format
- **ADR-7**: URL fetch via built-in `globalThis.fetch` — Node 18+, max 5 redirects

**Implementation Context**:
```bash
# All commands run from modules/satori/

# Install
npm install

# Test (vitest)
npm run test
npm run test -- --reporter=verbose

# Type check
npm run typecheck

# Build
npm run build

# Single test file
npm run test -- src/__tests__/knowledge-db.test.ts
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Foundation — Schema, Utilities, KnowledgeDB](phase-1.md)
- [x] [Phase 2: Core Components — PolyglotExecutor + satori_kb Tool](phase-2.md)
- [x] [Phase 3: Gateway Integration — BuiltinServer + Router + Wiring](phase-3.md)
- [x] [Phase 4: Hooks + Install Flow](phase-4.md)
- [x] [Phase 5: Integration & E2E Validation](phase-5.md)

---

## Dependency Graph

```
Phase 1 (Foundation)
  ├── T1.1 Schema extension
  ├── T1.2 Execution utilities (truncate + runtime)  [parallel with T1.3]
  └── T1.3 KnowledgeDB                               [parallel with T1.2]
        │
Phase 2 (Core Components)
  ├── T2.1 PolyglotExecutor    ← depends on T1.2     [parallel with T2.2]
  └── T2.2 satori_kb tool      ← depends on T1.3     [parallel with T2.1]
        │
Phase 3 (Gateway Integration)
  ├── T3.1 BuiltinServer       ← depends on T2.1 + T1.3
  ├── T3.2 SecurityScanner mod ← depends on T1.1     [parallel with T3.1]
  ├── T3.3 Router modification ← depends on T3.1 + T3.2
  └── T3.4 index.ts wiring     ← depends on T3.3 + T2.2
        │
Phase 4 (Hooks + Install)
  ├── T4.1 Hook scripts        ← depends on Phase 3  [parallel with T4.2, T4.3]
  ├── T4.2 install-hooks.sh    ← independent         [parallel with T4.1, T4.3]
  └── T4.3 install.sh opt-in   ← independent         [parallel with T4.1, T4.2]
        │
Phase 5 (Integration & E2E)
  └── All integration + E2E tests ← depends on Phase 4 complete
```

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest | ✅ |
