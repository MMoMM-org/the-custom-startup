---
title: "Phase 1: Foundation — Schema, Utilities, KnowledgeDB"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Foundation — Schema, Utilities, KnowledgeDB

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Constraints; CON-1–CON-7]`
- `[ref: SDD/Schema Changes; ServerConfig.runtime + ContextConfig.backend]`
- `[ref: SDD/KnowledgeDB Schema]`
- `[ref: SDD/Directory Map; src/execution/ + src/knowledge/]`
- `[ref: SDD/ADR-2; KnowledgeDB separate kb.sqlite]`
- `[ref: SDD/ADR-3; throttle state in-memory]`
- `[ref: SDD/Implementation Gotchas; FTS5 triggers, Bun detection]`
- `[ref: context-mode/src/truncate.ts]` — smartTruncate source of truth
- `[ref: context-mode/src/runtime.ts]` — detectRuntimes, buildCommand, Language type

**Key Decisions**:
- `runtime: 'builtin'` added to ServerConfig union — never written to satori.toml by users
- `context.backend?: 'satori' | 'kairn'` added to ContextConfig — parsed in Phase 3
- KnowledgeDB extends SQLiteBase — WAL, same close/cleanup lifecycle as ContentDB
- Throttle counter: `Map<sessionId, number>` instance field in KnowledgeDB (not persisted)
- Execution utilities are a direct port from context-mode — mark with `// port: context-mode/src/...`
- FTS5 trigram requires SQLite 3.38+ — detect at startup, log warning if absent, fall back to Porter-only

**Dependencies**:
- None — this is the foundation phase. All tasks can begin immediately.

---

## Tasks

Establishes the data schema, execution utility primitives, and knowledge base storage layer that all subsequent phases depend on.

- [x] **T1.1 Schema extension** `[activity: backend-api]`

  **Prime**: Read `modules/satori/src/config/schema.ts` (current state) and `[ref: SDD/Schema Changes]`

  **Test**: Type-check passes with `runtime: 'builtin'` as valid ServerConfig; `context.backend: 'kairn'` valid in ContextConfig; existing `'npx' | 'docker' | 'external'` values unchanged

  **Implement**: Edit `modules/satori/src/config/schema.ts` — add `'builtin'` to `ServerConfig.runtime` union; add `backend?: 'satori' | 'kairn'` to `ContextConfig`

  **Validate**: `npm run typecheck` passes; no existing tests broken

  - Success: `ServerConfig.runtime` accepts `'builtin'`; `ContextConfig.backend` field exists `[ref: SDD/Schema Changes]`
  - Success: `SatoriConfig` and all downstream consumers compile without change `[ref: PRD/F7]`

- [x] **T1.2 Execution utilities** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read `context-mode/src/truncate.ts` and `context-mode/src/runtime.ts` in full; read `[ref: SDD/Implementation Gotchas; Bun detection, process group kill]`

  **Test**:
  - `smartTruncate(input, maxBytes)` returns at most `maxBytes`; preserves 60%/40% head/tail split; snaps to line boundary; inserts separator with skipped-line count
  - `capBytes(input, max)` returns empty string for empty input; truncates at byte boundary not char boundary
  - `detectRuntimes()` returns available runtimes on current machine (at least `shell`/`bash`)
  - `buildCommand('python', filePath)` returns correct spawn args; `buildCommand('rust', filePath)` returns compile-then-run sequence
  - All 11 Language values accepted by `buildCommand` without throwing

  **Implement**:
  - Create `modules/satori/src/execution/truncate.ts` — port `smartTruncate`, `capBytes`, `truncateString` from context-mode; add `// port: context-mode/src/truncate.ts` comment
  - Create `modules/satori/src/execution/runtime.ts` — port `Language` type, `detectRuntimes()`, `buildCommand()` from context-mode; add `// port: context-mode/src/runtime.ts` comment
  - Create `modules/satori/src/__tests__/execution-truncate.test.ts` and `execution-runtime.test.ts`

  **Validate**: `npm run test -- src/__tests__/execution-truncate.test.ts execution-runtime.test.ts`; typecheck passes

  - Success: `smartTruncate` 60/40 split matches context-mode reference behaviour `[ref: SDD/Complex Logic; intent-driven mode]`
  - Success: All 11 languages produce valid spawn args `[ref: PRD/F3; 11-language support]`

- [x] **T1.3 KnowledgeDB** `[activity: data-architecture]` `[parallel: true]`

  **Prime**: Read `modules/satori/src/db-base.ts` and `modules/satori/src/context/content-db.ts` (pattern to follow); read `[ref: SDD/KnowledgeDB Schema]` and `[ref: SDD/ADR-2]` and `[ref: SDD/Implementation Gotchas; FTS5 triggers, trigram detection]`

  **Test**:
  - `KnowledgeDB` constructs and creates `kb.sqlite` at given path
  - `index({content, title, type})` chunks markdown by headings (≥1 chunk per heading); code blocks not split
  - `index()` returns chunk count
  - `search({query})` returns `SearchResult[]` sorted by RRF score
  - `search()` with no matching terms returns empty array
  - Levenshtein correction fires for queries with 1–2 char typos
  - `contentType` filter returns only matching type
  - Throttle: calls 1–3 return 2 results; calls 4–8 return 1; call 9 returns `ThrottleBlock`
  - `fetchAndIndex({url})` returns error object on non-200 response (mock fetch in test)
  - FTS5 triggers keep `chunks_fts` and `chunks_trigram` in sync after insert and delete

  **Implement**:
  - Create `modules/satori/src/knowledge/knowledge-db.ts` — `KnowledgeDB extends SQLiteBase`; `initSchema()` creates `chunks`, `chunks_fts` (Porter), `chunks_trigram` (trigram with SQLite version guard), triggers; `prepareStatements()`; `index()`, `search()` (RRF + proximity + fuzzy), `fetchAndIndex()` (built-in fetch, max 5 redirects); throttle `Map<sessionId, number>`; smart snippets
  - Create `modules/satori/src/__tests__/knowledge-db.test.ts`

  **Validate**: `npm run test -- src/__tests__/knowledge-db.test.ts`; typecheck passes

  - Success: FTS5 Porter + trigram tables created; triggers sync on insert/delete `[ref: SDD/KnowledgeDB Schema]`
  - Success: RRF merge returns higher-ranked results for multi-strategy matches `[ref: SDD/Complex Logic; RRF + Proximity]`
  - Success: Progressive throttle blocks at call 9 with redirect message `[ref: PRD/F4; throttling AC]`
  - Success: `fetchAndIndex` never returns raw HTML in result `[ref: PRD/F4; fetch AC]`

- [x] **T1.4 Phase 1 Validation** `[activity: validate]`

  Run all Phase 1 tests. Verify `npm run typecheck` passes. Confirm `schema.ts` change does not break existing satori tests. Check FTS5 trigram availability warning in test environment.
