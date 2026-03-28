---
title: "Phase 2: Core Components — PolyglotExecutor + satori_kb Tool"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Core Components — PolyglotExecutor + satori_kb Tool

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/BuiltinServer Internal Interface; RunArgs, RunFileArgs, BatchArgs]`
- `[ref: SDD/satori_kb Tool Interface]`
- `[ref: SDD/Complex Logic; Intent-Driven Mode]`
- `[ref: SDD/Implementation Gotchas; process group kill, #buildSafeEnv]`
- `[ref: context-mode/src/executor.ts]` — PolyglotExecutor source of truth

**Key Decisions**:
- PolyglotExecutor is a full port — do not simplify or adapt; preserve `#buildSafeEnv` DENIED list exactly
- Hard output cap: 100MB — kill process on exceed, return partial output + cap message
- Process group kill requires `detached: true` in spawn options; use `process.kill(-pid, 'SIGTERM')`
- Intent-driven mode threshold: output > 5KB + intent present → index to KnowledgeDB + search
- satori_kb follows sub_command enum pattern identical to satori-context.ts

**Dependencies**:
- T1.2 (truncate.ts + runtime.ts) must be complete before T2.1
- T1.3 (KnowledgeDB) must be complete before T2.2
- T2.1 and T2.2 are independent of each other — run in parallel

---

## Tasks

Builds the two core capability objects: the polyglot code executor and the knowledge base MCP tool.

- [x] **T2.1 PolyglotExecutor** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read `context-mode/src/executor.ts` in full; read `[ref: SDD/BuiltinServer Internal Interface]` and `[ref: SDD/Implementation Gotchas]`; read `modules/satori/src/execution/runtime.ts` and `truncate.ts` (Phase 1 output)

  **Test**:
  - `execute({language: 'shell', code: 'echo hello'})` returns `{stdout: 'hello\n', exitCode: 0}`
  - `execute()` with missing runtime returns error with runtime name in message
  - `execute()` with `timeout: 100` kills slow process and returns timeout message
  - `execute()` with output > 100MB triggers hard cap and kills process
  - `execute({background: true})` returns without waiting for process to complete
  - `executeFile({path, language})` reads file and executes it
  - `#buildSafeEnv` strips BASH_ENV, NODE_OPTIONS, LD_PRELOAD from env (verify in test by checking spawned env)
  - Process group kill: spawning a process that spawns children — all children killed on timeout

  **Implement**:
  - Create `modules/satori/src/execution/executor.ts` — port `PolyglotExecutor` class from context-mode; includes `execute()`, `executeFile()`, `cleanupBackgrounded()`, `#buildSafeEnv()`; uses `detectRuntimes()` and `buildCommand()` from `runtime.ts`; uses `smartTruncate` from `truncate.ts`; add `// port: context-mode/src/executor.ts` comment
  - Create `modules/satori/src/__tests__/execution-executor.test.ts`

  **Validate**: `npm run test -- src/__tests__/execution-executor.test.ts`; typecheck passes

  - Success: `#buildSafeEnv` DENIED list matches context-mode reference exactly `[ref: SDD/System-Wide Patterns; Security]`
  - Success: Process group kill leaves no orphaned children `[ref: SDD/Implementation Gotchas]`
  - Success: 100MB hard cap kills and returns partial output `[ref: PRD/F3; execution AC]`
  - Success: All 11 language commands execute (or return clear runtime-missing error) `[ref: PRD/F3; language support AC]`

- [x] **T2.2 satori_kb MCP tool** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read `modules/satori/src/tools/satori-context.ts` (sub_command pattern to follow); read `[ref: SDD/satori_kb Tool Interface]`; read Phase 1 KnowledgeDB output

  **Test**:
  - `satori_kb({sub_command: 'index', content: '# Title\nBody'})` returns `{indexed: 1}`
  - `satori_kb({sub_command: 'search', query: 'title'})` returns array of results with `snippet`, `title`, `score`
  - `satori_kb({sub_command: 'fetch_and_index', url: '...'})` — mock fetch, verifies chunks stored
  - `satori_kb({sub_command: 'search'})` without query returns error
  - `satori_kb({sub_command: 'index'})` without content returns error
  - Throttle block response includes `blocked: true` and `redirect: 'satori_exec'`
  - `contentType: 'code'` filter passes to KnowledgeDB correctly
  - `isError: true` set on all error responses

  **Implement**:
  - Create `modules/satori/src/tools/satori-kb.ts` — `registerSatoriKb(server, knowledgeDb)` function; Zod schema with `sub_command: z.enum(['index', 'search', 'fetch_and_index'])`; switch dispatch; delegates to `knowledgeDb.*`; handles throttle block response shape
  - Create `modules/satori/src/__tests__/satori-kb.test.ts`

  **Validate**: `npm run test -- src/__tests__/satori-kb.test.ts`; typecheck passes

  - Success: Tool interface matches SDD spec exactly `[ref: SDD/satori_kb Tool Interface]`
  - Success: All error paths return `isError: true` `[ref: SDD/Error Handling]`
  - Success: Throttle block redirects to `satori_exec` `[ref: PRD/F4; progressive throttling AC]`

- [x] **T2.3 Phase 2 Validation** `[activity: validate]`

  Run all Phase 1 + Phase 2 tests. Verify typecheck passes. Confirm `PolyglotExecutor` and `satori_kb` are importable but not yet wired into the MCP server (Phase 3).
