---
title: "Phase 5: Tools & Gateway Routing"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Tools & Gateway Routing

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "Tool Naming Convention", "Gateway Routing", and "Tools Exposed to Claude Code" before starting. Phase 5 wires together all prior work.

**Specification References**:
- `[ref: SDD/Tool Naming Convention]` — 3-tool surface: satori_exec, satori_context, satori_manage
- `[ref: SDD/Gateway Routing/Tool Call Flow]` — 11-step routing pipeline
- `[ref: SDD/Tools Exposed to Claude Code/satori_exec]` — signature, error cases
- `[ref: SDD/Handler Interface]` — beforeCall → afterCall pipeline

**Key Decisions**:
- `satori_exec(server, tool, args)` — all downstream routing goes through this; never namespace tools
- Routing flow: validate args → registry lookup → hot start → handler.beforeCall → security.scanOut → forward → handler.afterCall → content capture → summarize → return
- Return value is compact summary, not raw upstream output
- Unknown server → `{"error": "unknown server: <name>"}`; blocked server → `{"error": "server blocked: <reason>"}`

**Dependencies**: Phases 2 (ContentDB, snapshot), 3 (registry, security), 4 (lifecycle, handlers).

---

## Tasks

Implements `satori_exec` and the full gateway routing pipeline. After this phase the MCP server
exposes all 3 tools and can route calls to real downstream servers.

- [ ] **T5.1 Gateway router (router.ts)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Gateway Routing/Tool Call Flow]` — 11-step pipeline. `[ref: SDD/Tool Naming Convention]`
  2. Test: `GatewayRouter.exec("filesystem", "read_file", {path: "..."})` with mocked registry, lifecycle, handler, and downstream client: calls `registry.lookup`, `lifecycle.start`, `handler.beforeCall`, downstream `callTool`, `handler.afterCall`, `contentDb.insertCapture`. Unknown server → error result. Blocked by `beforeCall` → error result, audit log entry. Security scan blocks → error result, no downstream call. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  3. Implement: Create `src/gateway/router.ts` — `GatewayRouter` class (takes registry, lifecycle, handlerRegistry, scanner, contentDb, auditLog). `exec(server, tool, args)`: (1) lookup server, (2) check state/start, (3) get handler, (4) `handler.beforeCall`, (5) `scanner.scanOut(args)`, (6) call downstream MCP client `callTool(tool, args)`, (7) `handler.afterCall`, (8) `contentDb.insertCapture`, (9) `contentDb.updateSummary` (async, non-blocking), (10) return response content. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  4. Validate: Unit tests with all dependencies mocked: happy path (all 11 steps called in order), blocked path (beforeCall returns BlockedResult → no downstream call), scan blocked path, unknown server path, start failure path. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  5. Success: Router tests pass for all branches; step ordering is correct; downstream never called after a block.

- [ ] **T5.2 satori_exec tool** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Tools Exposed to Claude Code/satori_exec]` — argument table, error cases. `[ref: SDD/Tool Naming Convention/Why satori_exec]`
  2. Test: `satori_exec({server: "filesystem", tool: "read_file", args: {path: "..."}})` calls `GatewayRouter.exec()` and returns result. Missing `server` argument → MCP error. Missing `tool` → MCP error. Unknown server → `{"error": "unknown server: filesystem"}`. `[ref: SDD/Tools Exposed to Claude Code/satori_exec]`
  3. Implement: Create `src/tools/satori-exec.ts` — MCP tool handler. Validate `server`, `tool`, `args` present; call `router.exec(server, tool, args)`; return result string or error JSON. Register tool in `src/index.ts` with description that explains the `server/tool/args` pattern. `[ref: SDD/Tools Exposed to Claude Code/satori_exec]`
  4. Validate: Integration test: start a real npx server (e.g. `@modelcontextprotocol/server-memory`), register it, call `satori_exec("memory", "create_entities", {...})` — response captured in ContentDB. `[ref: SDD/Tools Exposed to Claude Code/satori_exec]`
  5. Success: `satori_exec` registered in MCP server; routes to downstream; captures output; returns summary.

- [ ] **T5.3 Content summarizer** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Repository Structure; src/context/summarizer.ts]`. `[ref: SDD/SQLite Schema/Content Capture Store]`
  2. Test: `summarize(rawOutput)` compresses a 5000-char tool output to ≤500 chars. Summary is human-readable (not just truncation). Structured JSON output → key fields extracted. Plain text → first N lines + trailing count. Empty input → empty summary. `[ref: SDD/Repository Structure; src/context/summarizer.ts]`
  3. Implement: Create `src/context/summarizer.ts` — `summarize(server: string, tool: string, output: string): string`. Strategy: (1) if JSON, extract keys and truncate values; (2) if multi-line text, take first 15 lines + `[... N more lines]`; (3) if short (<300 chars), return as-is. Called asynchronously from router after capture insert. `[ref: SDD/Repository Structure; src/context/summarizer.ts]`
  4. Validate: Unit tests: JSON object summary contains key names; long text summary ≤ 500 chars; short text unchanged. `[ref: SDD/Repository Structure; src/context/summarizer.ts]`
  5. Success: Summarizer produces ≤500 char output for all inputs; summary searchable in FTS5.

- [ ] **T5.4 Wire all 3 tools into MCP server** `[activity: build-feature]`

  1. Prime: Review `src/index.ts` from Phase 1 (empty tool list). `[ref: SDD/Tools Exposed to Claude Code]`
  2. Test: `tools/list` returns exactly 3 tools: `satori_exec`, `satori_context`, `satori_manage`. Each has a description. No extra tools. `[ref: SDD/Tool Naming Convention]`
  3. Implement: Update `src/index.ts`: instantiate all dependencies (config, registry, lifecycle, handler registry, session DB, content DB, router, audit log). Register all 3 tool handlers. Add startup sequence: `loadConfig()` → `autoRegisterMcpJson()` (if enabled) → `scanner.scanConfig()` → block flagged servers → set registry. `[ref: SDD/Tools Exposed to Claude Code]`
  4. Validate: `tools/list` → exactly 3 tools. `satori_exec` with unknown server → error JSON (not crash). `satori_context(status)` → JSON stats. `satori_manage(list)` → list (empty OK). `[ref: SDD/Tools Exposed to Claude Code]`
  5. Success: MCP server starts with 3 tools; all tools respond correctly; no crashes on bad input.

- [ ] **T5.5 Phase 5 Validation** `[activity: validate]`

  - `npm test` — all Phase 5 tests pass.
  - `npm run typecheck` — 0 errors.
  - `tools/list` → exactly `["satori_exec", "satori_context", "satori_manage"]`.
  - `satori_exec("nonexistent", "tool", {})` → error JSON, no crash.
  - Router unit test: all 11 flow steps covered.
  - Summarizer: 5000-char input → summary ≤ 500 chars.
