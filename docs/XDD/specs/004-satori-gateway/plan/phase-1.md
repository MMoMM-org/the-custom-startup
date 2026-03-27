---
title: "Phase 1: Repository Foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Repository Foundation

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "Technology Stack" and "Repository Structure" before starting.

**Specification References**:
- `[ref: SDD/Technology Stack]` — Node.js 20, TypeScript strict, deps list
- `[ref: SDD/Repository Structure]` — full `src/` tree

**Key Decisions**:
- TypeScript strict mode; `"module": "node16"` or `"nodenext"` for ESM + `.js` imports
- `better-sqlite3` as SQLite driver; WAL mode enabled on open
- `@modelcontextprotocol/sdk` for MCP server/transport
- `smol-toml` for TOML parsing (zero-dep, lightweight)
- `vitest` as test runner (ESM-native, fast)

**Dependencies**: None — this is the foundation phase.

---

## Tasks

Establishes the miyo-satori repo structure: package.json, tsconfig, lint config, CI skeleton, and a
buildable MCP server entry point that responds to `initialize` and returns an empty tool list.

- [ ] **T1.1 Initialize package.json and TypeScript config** `[activity: build-platform]`

  1. Prime: Read `modules/satori/package.json` if it exists. Check Node version: `node --version`. `[ref: SDD/Technology Stack]`
  2. Test: `npm install` succeeds. `npm run build` compiles to `dist/`. `npm run typecheck` returns 0 errors. `npm test` runs vitest and exits 0 (no test files yet = pass). `[ref: SDD/Technology Stack]`
  3. Implement: Create `package.json` with `"type": "module"`, scripts (`build`, `typecheck`, `test`, `dev`), and deps: `@modelcontextprotocol/sdk`, `better-sqlite3`, `smol-toml`; devDeps: `typescript`, `@types/better-sqlite3`, `@types/node`, `vitest`, `tsx`. Create `tsconfig.json` with strict mode, `moduleResolution: "node16"`, `outDir: "dist"`. Add `.gitignore` entries: `dist/`, `node_modules/`, `.satori/`. `[ref: SDD/Technology Stack]`
  4. Validate: `npm run build` — 0 errors. `npm run typecheck` — 0 errors. `dist/` created. `[ref: SDD/Technology Stack]`
  5. Success: `npm install && npm run build && npm test` all exit 0; `tsconfig.json` has `strict: true`; deps match SDD tech stack.

- [ ] **T1.2 SQLiteBase helper** `[activity: build-feature]`

  1. Prime: Read context-mode `src/db-base.ts` — SQLiteBase, WAL pragma, BunSQLiteAdapter, deleteDBFiles, closeDB. `[ref: SDD/SQLite Schema]`
  2. Test: `src/db-base.ts` exports `SQLiteBase` (abstract class). Subclass with empty `initSchema()` and `prepareStatements()` opens a DB file without error. `db.pragma("journal_mode")` returns `"wal"`. `db.cleanup()` removes DB file. `[ref: SDD/SQLite Schema]`
  3. Implement: Port `db-base.ts` from context-mode to `src/db-base.ts`. Include: `loadDatabase()` (Node: better-sqlite3; Bun: bun:sqlite via adapter), `applyWALPragmas()`, `SQLiteBase` abstract class with `open/close/cleanup`, `defaultDBPath()` using repo-local `.satori/db.sqlite`. Remove BunSQLiteAdapter if targeting Node only — decide during implementation. `[ref: SDD/SQLite Schema]`
  4. Validate: Unit test opens in-memory (`:memory:`) DB, runs `pragma journal_mode`, checks `"wal"`. Cleanup test: file created, then `cleanup()` removes it. All pass with `npm test`. `[ref: SDD/SQLite Schema]`
  5. Success: `SQLiteBase` opens, applies WAL, exposes `db` to subclasses, cleanup removes files; tests pass.

- [ ] **T1.3 MCP server bootstrap (empty tool list)** `[activity: build-feature]`

  1. Prime: Read `@modelcontextprotocol/sdk` README for `McpServer` / `StdioServerTransport` setup. `[ref: SDD/Repository Structure; src/index.ts]`
  2. Test: `node dist/index.js` starts without error. Sending MCP `initialize` message over STDIO returns a valid `InitializeResult` with `protocolVersion` and `serverInfo.name = "satori"`. `tools/list` returns `{"tools": []}`. `[ref: SDD/Tools Exposed to Claude Code]`
  3. Implement: Create `src/index.ts` — bootstrap `McpServer`, connect `StdioServerTransport`, register zero tools. Add graceful shutdown on `SIGINT`/`SIGTERM`. `[ref: SDD/Repository Structure]`
  4. Validate: `npm run build && echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"1"}}}' | node dist/index.js` — valid JSON response received. `[ref: SDD/Tools Exposed to Claude Code]`
  5. Success: MCP server starts, responds to `initialize` and `tools/list`, exits cleanly on SIGTERM.

- [ ] **T1.4 Phase 1 Validation** `[activity: validate]`

  - `npm install && npm run build` — 0 errors.
  - `npm run typecheck` — 0 errors.
  - `npm test` — all tests pass (SQLiteBase unit tests).
  - MCP server boot test: `initialize` → valid response, `tools/list` → `{"tools": []}`.
  - `.gitignore` contains `dist/`, `node_modules/`, `.satori/`.
