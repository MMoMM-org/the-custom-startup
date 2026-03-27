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
- `[ref: SDD/Tool Naming Convention]` — 5-tool surface: satori_context, satori_manage, satori_find, satori_schema, satori_exec
- `[ref: SDD/Gateway Routing/Discovery Flow]` — find → schema → exec 3-step pattern
- `[ref: SDD/Gateway Routing/Tool Call Flow]` — 11-step routing pipeline
- `[ref: SDD/Tools Exposed to Claude Code]` — all 5 tool specs
- `[ref: SDD/Handler Interface]` — beforeCall → afterCall pipeline

**Key Decisions**:
- `satori_exec(server, tool, args)` — all downstream routing goes through this; never namespace tools
- `satori_find(query, server?)` — keyword search over cached tool catalog; cold servers included
- `satori_schema(server, tool)` — returns cached MCP tool definition (name + description + inputSchema)
- Tool catalog is cached at startup and on first server start; `satori_find`/`satori_schema` never start servers
- Routing flow: validate args → registry lookup → hot start → handler.beforeCall → security.scanOut → forward → handler.afterCall → content capture → summarize → return
- Return value is compact summary, not raw upstream output
- Unknown server → `{"error": "unknown server: <name>"}`; blocked server → `{"error": "server blocked: <reason>"}`

**Dependencies**: Phases 2 (ContentDB, snapshot), 3 (registry, security), 4 (lifecycle, handlers).

---

## Tasks

Implements `satori_find`, `satori_schema`, `satori_exec`, the tool catalog cache, and the full
gateway routing pipeline. After this phase the MCP server exposes all 5 tools and can discover
and route calls to real downstream servers.

- [ ] **T5.1 Tool catalog cache (catalog.ts)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Gateway Routing/Discovery Flow]` — caching strategy, cold server search. `[ref: SDD/Repository Structure; src/gateway/catalog.ts]`
  2. Test: `ToolCatalog.populate(serverName, toolList)` stores tool definitions. `ToolCatalog.search("read file")` returns tools whose name or description matches. `ToolCatalog.getSchema("filesystem", "read_file")` returns cached MCP tool definition. `ToolCatalog.search("read")` with `server="filesystem"` filter returns only filesystem tools. Server not in catalog → `getSchema` returns null (not throw). `[ref: SDD/Gateway Routing/Discovery Flow]`
  3. Implement: Create `src/gateway/catalog.ts` — `ToolCatalog` class. Internal: `Map<serverName, McpTool[]>`. Methods: `populate(server, tools)`, `search(query, server?)` (case-insensitive substring match on name + description), `getSchema(server, tool)` (returns `McpTool | null`), `serverTools(server)` (all tools for a server), `clear(server?)`. `[ref: SDD/Repository Structure; src/gateway/catalog.ts]`
  4. Validate: Unit tests: search hits on name and description; server filter works; missing server → empty results; `getSchema` for unknown tool → null. `[ref: SDD/Gateway Routing/Discovery Flow]`
  5. Success: Catalog tests pass; search is case-insensitive; cold servers searchable without starting them.

- [ ] **T5.2 satori_find and satori_schema tools** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Tools Exposed to Claude Code/satori_find]` and `[ref: SDD/Tools Exposed to Claude Code/satori_schema]`. `[ref: SDD/Gateway Routing/Discovery Flow]`
  2. Test: `satori_find("read")` → list of matching tools across all servers with state. `satori_find("read", server="filesystem")` → only filesystem matches. `satori_find("zzznomatch")` → empty array. `satori_schema("filesystem", "read_file")` → `{ name, description, inputSchema }`. `satori_schema("unknown", "tool")` → error JSON. `[ref: SDD/Tools Exposed to Claude Code/satori_find]`
  3. Implement: Create `src/tools/satori-find.ts` — queries `ToolCatalog.search()`, enriches each result with current `ServerState` from `LifecycleManager`. Create `src/tools/satori-schema.ts` — calls `ToolCatalog.getSchema()`, returns formatted JSON. Both tools registered in `src/index.ts`. `[ref: SDD/Tools Exposed to Claude Code]`
  4. Validate: Integration test: populate catalog with 3 servers (10 tools each), call `satori_find("create")` → subset returned with state. `satori_schema` roundtrip: populate → retrieve → correct shape. `[ref: SDD/Tools Exposed to Claude Code]`
  5. Success: Both tools registered; `satori_find` returns state-enriched results; `satori_schema` returns full inputSchema.

- [ ] **T5.3 Gateway router (router.ts)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Gateway Routing/Tool Call Flow]` — 11-step pipeline. `[ref: SDD/Tool Naming Convention]`
  2. Test: `GatewayRouter.exec("filesystem", "read_file", {path: "..."})` with mocked registry, lifecycle, handler, and downstream client: calls `registry.lookup`, `lifecycle.start`, `handler.beforeCall`, downstream `callTool`, `handler.afterCall`, `contentDb.insertCapture`. Unknown server → error result. Blocked by `beforeCall` → error result, audit log entry. Security scan blocks → error result, no downstream call. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  3. Implement: Create `src/gateway/router.ts` — `GatewayRouter` class (takes registry, lifecycle, handlerRegistry, scanner, contentDb, auditLog). `exec(server, tool, args)`: (1) lookup server, (2) check state/start, (3) get handler, (4) `handler.beforeCall`, (5) `scanner.scanOut(args)`, (6) call downstream MCP client `callTool(tool, args)`, (7) `handler.afterCall`, (8) `contentDb.insertCapture`, (9) `contentDb.updateSummary` (async, non-blocking), (10) return response content. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  4. Validate: Unit tests with all dependencies mocked: happy path (all 11 steps called in order), blocked path (beforeCall returns BlockedResult → no downstream call), scan blocked path, unknown server path, start failure path. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  5. Success: Router tests pass for all branches; step ordering is correct; downstream never called after a block.

- [ ] **T5.4 satori_exec tool** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Tools Exposed to Claude Code/satori_exec]` — argument table, error cases. `[ref: SDD/Tool Naming Convention/Why satori_exec]`
  2. Test: `satori_exec({server: "filesystem", tool: "read_file", args: {path: "..."}})` calls `GatewayRouter.exec()` and returns result. Missing `server` argument → MCP error. Missing `tool` → MCP error. Unknown server → `{"error": "unknown server: filesystem"}`. `[ref: SDD/Tools Exposed to Claude Code/satori_exec]`
  3. Implement: Create `src/tools/satori-exec.ts` — MCP tool handler. Validate `server`, `tool`, `args` present; call `router.exec(server, tool, args)`; return result string or error JSON. Register tool in `src/index.ts` with description that explains the `server/tool/args` pattern. `[ref: SDD/Tools Exposed to Claude Code/satori_exec]`
  4. Validate: Integration test: start a real npx server (e.g. `@modelcontextprotocol/server-memory`), register it, call `satori_exec("memory", "create_entities", {...})` — response captured in ContentDB. `[ref: SDD/Tools Exposed to Claude Code/satori_exec]`
  5. Success: `satori_exec` registered in MCP server; routes to downstream; captures output; returns summary.

- [ ] **T5.5 Content summarizer** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Repository Structure; src/context/summarizer.ts]`. `[ref: SDD/SQLite Schema/Content Capture Store]`
  2. Test: `summarize(rawOutput)` compresses a 5000-char tool output to ≤500 chars. Summary is human-readable (not just truncation). Structured JSON output → key fields extracted. Plain text → first N lines + trailing count. Empty input → empty summary. `[ref: SDD/Repository Structure; src/context/summarizer.ts]`
  3. Implement: Create `src/context/summarizer.ts` — `summarize(server: string, tool: string, output: string): string`. Strategy: (1) if JSON, extract keys and truncate values; (2) if multi-line text, take first 15 lines + `[... N more lines]`; (3) if short (<300 chars), return as-is. Called asynchronously from router after capture insert. `[ref: SDD/Repository Structure; src/context/summarizer.ts]`
  4. Validate: Unit tests: JSON object summary contains key names; long text summary ≤ 500 chars; short text unchanged. `[ref: SDD/Repository Structure; src/context/summarizer.ts]`
  5. Success: Summarizer produces ≤500 char output for all inputs; summary searchable in FTS5.

- [ ] **T5.6 Wire all 5 tools into MCP server** `[activity: build-feature]`

  1. Prime: Review `src/index.ts` from Phase 1 (empty tool list). `[ref: SDD/Tools Exposed to Claude Code]`
  2. Test: `tools/list` returns exactly 5 tools: `satori_context`, `satori_manage`, `satori_find`, `satori_schema`, `satori_exec`. Each has a description. No extra tools. `[ref: SDD/Tool Naming Convention]`
  3. Implement: Update `src/index.ts`: instantiate all dependencies (config, registry, catalog, lifecycle, handler registry, session DB, content DB, router, audit log). Register all 5 tool handlers. Startup sequence: `loadConfig()` → `autoRegisterMcpJson()` (if enabled) → `scanner.scanConfig()` → block flagged servers → populate catalog from startup `tools/list` calls on running servers. `[ref: SDD/Tools Exposed to Claude Code]`
  4. Validate: `tools/list` → exactly 5 tools. `satori_find("read")` → non-empty if servers configured. `satori_exec` with unknown server → error JSON (not crash). `satori_context(status)` → JSON stats. `satori_manage(list)` → list (empty OK). `[ref: SDD/Tools Exposed to Claude Code]`
  5. Success: MCP server starts with 5 tools; all tools respond correctly; no crashes on bad input.

- [ ] **T5.7 Phase 5 Validation** `[activity: validate]`

  - `npm test` — all Phase 5 tests pass.
  - `npm run typecheck` — 0 errors.
  - `tools/list` → exactly `["satori_context", "satori_manage", "satori_find", "satori_schema", "satori_exec"]`.
  - `satori_find("nonexistent_keyword_xyz")` → empty array (not error).
  - `satori_exec("nonexistent", "tool", {})` → error JSON, no crash.
  - Router unit test: all 11 flow steps covered.
  - Summarizer: 5000-char input → summary ≤ 500 chars.
  - Discovery flow E2E: find → schema → exec roundtrip with a real npx server.
