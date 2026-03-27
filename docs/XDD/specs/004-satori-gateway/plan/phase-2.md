---
title: "Phase 2: Context Module"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Context Module

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "SQLite Schema", "Hooks Architecture", and "Session Snapshot Format" before starting. Also read context-mode's `src/session/db.ts`, `src/session/snapshot.ts`, and `src/session/extract.ts`.

**Specification References**:
- `[ref: SDD/SQLite Schema/Session Event Store]` — session_events, session_meta, session_resume tables
- `[ref: SDD/SQLite Schema/Content Capture Store]` — captures + FTS5
- `[ref: SDD/Session Snapshot Format]` — XML format, budget, priority tiers, section table
- `[ref: SDD/Hooks Architecture/Event classification]` — category → event type mapping
- `[ref: SDD/Tools Exposed to Claude Code/satori_context]` — restore, query, status, flush sub-commands

**Key Decisions**:
- Session event store and content capture store share one DB file (`.satori/db.sqlite`)
- `snapshot.ts` is pure functions — no DB access, no side effects; fully unit-testable
- `extract.ts` maps MCP tool call hook payloads (JSON) → `SessionEvent`; isolated from DB
- FIFO eviction at 1000 events; SHA256-prefix dedup over last 5 events

**Dependencies**: Phase 1 (SQLiteBase required).

---

## Tasks

Builds the full context module: two DB stores, session event extraction, XML snapshot builder,
and the `satori_context` tool skeleton backed by real data.

- [ ] **T2.1 SessionDB (session event store)** `[activity: build-feature]`

  1. Prime: Read context-mode `src/session/db.ts` completely — schema, FIFO eviction, dedup, prepared statements pattern. `[ref: SDD/SQLite Schema/Session Event Store]`
  2. Test: `SessionDB` inserts events; dedup skips same type+hash within 5-event window; eviction drops lowest-priority (then oldest) when count exceeds 1000; `getEvents()` returns ordered events; `upsertResume()` + `getResume()` roundtrip; `incrementCompactCount()` increments. `[ref: SDD/SQLite Schema/Session Event Store]`
  3. Implement: Create `src/context/session-db.ts` extending `SQLiteBase`. Schema: `session_events`, `session_meta`, `session_resume` with indexes. Prepared statements: `insertEvent` (with SHA256 dedup hash), `checkDuplicate`, `evictLowestPriority`, `getEvents`, `getEventCount`, `ensureSession`, `getSessionStats`, `incrementCompactCount`, `upsertResume`, `getResume`, `markResumeConsumed`, `deleteSession`, `cleanupOldSessions`. Wrap insert in a transaction: dedup check → eviction → insert → update meta. `[ref: SDD/SQLite Schema/Session Event Store; context-mode src/session/db.ts]`
  4. Validate: All unit tests pass. Run with in-memory DB (`:memory:` path). Eviction test: insert 1001 events (priority 3), check count stays ≤ 1000. Dedup test: insert same type+data twice → count = 1. `[ref: SDD/SQLite Schema/Session Event Store]`
  5. Success: All SessionDB tests pass; eviction and dedup work correctly; transactions are atomic.

- [ ] **T2.2 ContentDB (capture store + FTS5)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/SQLite Schema/Content Capture Store]` — captures + FTS5 schema. `[ref: SDD/Tools Exposed to Claude Code/satori_context query sub-command]`
  2. Test: `ContentDB.insertCapture()` stores a capture; `ContentDB.search("query")` returns ranked FTS5 results; `ContentDB.updateSummary()` fills the summary field; summary appears in subsequent FTS search results. `[ref: SDD/SQLite Schema/Content Capture Store]`
  3. Implement: Create `src/context/content-db.ts` extending `SQLiteBase`. Schema: `captures` + `captures_fts` FTS5 virtual table (content-rowid mode). Methods: `insertCapture()`, `updateSummary()`, `search(q, limit)`, `getBySession(sessionId)`, `pruneOlderThan(days)`. FTS5 trigger insert after capture insert. `[ref: SDD/SQLite Schema/Content Capture Store]`
  4. Validate: Insert 3 captures with different servers/tools; `search("specific term")` returns only matching capture; summary update visible in FTS results. Tests pass. `[ref: SDD/SQLite Schema/Content Capture Store]`
  5. Success: FTS5 search returns ranked results; summary field searchable after `updateSummary()`; all ContentDB tests pass.

- [ ] **T2.3 Session event extraction (extract.ts)** `[activity: build-feature]`

  1. Prime: Read context-mode `src/session/extract.ts`. Read `[ref: SDD/Hooks Architecture/Event classification]` — full category→type mapping table. `[ref: SDD/Hooks Architecture]`
  2. Test: `extractEvent(hookPayload)` returns correct `SessionEvent` for: `Read` tool (category=file, type=file_read), `Write` tool (file_write), `Edit` tool (file_edit), Bash tool (no session event — Bash is intercepted but not directly categorized unless it produces an error), `TaskCreate` (task, priority 1), `TaskUpdate` (task), `Agent` dispatch (subagent_launched, priority 3). Returns `null` for unknown tool types. `[ref: SDD/Hooks Architecture/Event classification]`
  3. Implement: Create `src/context/extract.ts` — pure function `extractEvent(toolName: string, toolInput: unknown, toolOutput?: unknown): SessionEvent | null`. Map tool names to categories and types per the SDD classification table. Parse `toolInput` JSON for data extraction (e.g. path from Read/Write, subject from TaskCreate). `[ref: SDD/Hooks Architecture/Event classification]`
  4. Validate: Unit tests cover all 14 event categories; boundary cases: malformed input returns null gracefully; data truncation at limits (path ≤200 chars, content ≤400 chars). `[ref: SDD/Hooks Architecture/Event classification]`
  5. Success: All extraction mappings tested and correct; pure function (no imports of DB modules).

- [ ] **T2.4 Snapshot builder (snapshot.ts)** `[activity: build-feature]`

  1. Prime: Read context-mode `src/session/snapshot.ts` completely — all section renderers, `buildResumeSnapshot()`, budget trimming loop. Read `[ref: SDD/Session Snapshot Format]`. `[ref: SDD/Session Snapshot Format]`
  2. Test: `buildResumeSnapshot(events)` with full event set produces valid XML under 2048 bytes. P3-P4 sections dropped when over budget (verify by supplying large events). P1 sections (active_files, task_state, rules) always present if they fit. Active files deduped by path; last 10 kept. Task state omits completed tasks. `buildResumeSnapshot([])` returns `<session_resume ...></session_resume>` (minimal). `[ref: SDD/Session Snapshot Format]`
  3. Implement: Port `src/session/snapshot.ts` from context-mode to `src/context/snapshot.ts`. Adapt imports to Satori's types. Section renderers: `renderActiveFiles`, `renderTaskState`, `renderRules`, `renderDecisions`, `renderEnvironment`, `renderErrors`, `renderIntent`, `renderSubagents`, `renderMcpTools`. Budget loop: try all tiers; drop P3, then P2, then truncate P1. `[ref: SDD/Session Snapshot Format; context-mode src/session/snapshot.ts]`
  4. Validate: Unit test with 50 events produces XML ≤ 2048 bytes. Budget stress test: supply 200 file events (large paths) — output still ≤ 2048. Section content is valid XML (no unescaped `<>&`). `buildResumeSnapshot([])` output passes XML parse. `[ref: SDD/Session Snapshot Format]`
  5. Success: All snapshot tests pass; output is always ≤ maxBytes; pure functions with no side effects.

- [ ] **T2.5 satori_context tool (restore, query, status, flush)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Tools Exposed to Claude Code/satori_context]` — sub-command table. `[ref: SDD/Tools Exposed to Claude Code]`
  2. Test: `restore` returns XML from `session_resume` (or "no snapshot available"); `query` returns FTS5 matches from ContentDB; `status` returns DB stats (session count, capture count, guide count); `flush` calls `buildResumeSnapshot()` and `upsertResume()` and returns confirmation. Unknown sub-command returns error. `[ref: SDD/Tools Exposed to Claude Code/satori_context]`
  3. Implement: Create `src/tools/satori-context.ts` — MCP tool handler with `sub_command: string` argument dispatching to the four sub-commands. Wire to `SessionDB` and `ContentDB` instances. `restore`: fetches session_resume, marks consumed. `query`: calls `ContentDB.search()`. `status`: counts rows. `flush`: reads session_events → `buildResumeSnapshot()` → `upsertResume()`. `[ref: SDD/Tools Exposed to Claude Code/satori_context]`
  4. Validate: Integration test: insert 5 captures into ContentDB, call `query("keyword")` — matching capture returned. Insert 10 events, call `flush` — snapshot XML in session_resume table. Call `restore` — returns snapshot, marks consumed. `[ref: SDD/Tools Exposed to Claude Code/satori_context]`
  5. Success: All 4 sub-commands work end-to-end; `satori_context` registered in MCP server and visible in `tools/list`.

- [ ] **T2.6 Phase 2 Validation** `[activity: validate]`

  - `npm test` — all Phase 2 unit and integration tests pass.
  - `npm run typecheck` — 0 errors.
  - MCP `tools/list` includes `satori_context` with correct description.
  - `satori_context(restore)` → "no snapshot available" (empty DB).
  - `satori_context(flush)` → generates snapshot, `satori_context(restore)` → returns it.
  - `satori_context(query, {q: "test"})` → FTS5 results or empty array.
  - `satori_context(status)` → JSON object with numeric counts.
