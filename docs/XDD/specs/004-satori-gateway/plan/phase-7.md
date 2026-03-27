---
title: "Phase 7: TCS Integration & E2E Validation"
status: pending
version: "1.0"
phase: 7
---

# Phase 7: TCS Integration & E2E Validation

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "TCS Submodule (R6.1)" and "Discovery Mechanism" before starting.

**Specification References**:
- `[ref: SDD/TCS Submodule (R6.1)]` — submodule path, install.sh MCP config, absolute path requirement
- `[ref: SDD/Discovery Mechanism]` — tool presence detection; CLAUDE.md flag = M5
- `[ref: PRD/R6.1]` — TCS ships Satori as a git submodule at modules/satori/
- `[ref: PRD/R1–R5]` — full PRD acceptance criteria for M4 scope

**Key Decisions**:
- MCP command must use absolute path (CLAUDE.md guardrail): `node /abs/path/modules/satori/dist/index.js`
- `install.sh` resolves absolute path at install time via `$(cd modules/satori && pwd)`
- `satori.toml.example` is committed; `satori.toml` and `.satori/` are gitignored in user repos
- Skill integration (context-search skill, CLAUDE.md flag) is M5 — not in scope here
- E2E test uses a real npx-based downstream server to verify full roundtrip

**Dependencies**: Phase 6 (complete implementation).

---

## Tasks

Ships miyo-satori, wires it into TCS install.sh as a git submodule, and validates the full
roundtrip: server registration → `satori_exec` call → content capture → session snapshot.

- [ ] **T7.1 miyo-satori packaging and documentation** `[activity: build-platform]`

  1. Prime: Read `modules/satori/README.md` if it exists. `[ref: SDD/TCS Submodule (R6.1)]`
  2. Test: `npm run build` produces `dist/index.js`. `node dist/index.js` starts without error. `README.md` exists with: quick start, config schema summary, tool descriptions, hooks install instructions. `satori.toml.example` exists with all schema fields annotated. `[ref: SDD/Config Schema]`
  3. Implement: Finalize `README.md` — installation, configuration, Claude Code MCP setup, hooks setup, `satori_exec` usage examples. Create `satori.toml.example` from SDD schema (annotated). Verify `package.json` `main` points to `dist/index.js`. Add `"files"` field to package.json to exclude test fixtures from publish. `[ref: SDD/Config Schema]`
  4. Validate: `npm pack --dry-run` lists expected files. `node dist/index.js` → MCP server starts. `tools/list` → 3 tools. `[ref: SDD/Tools Exposed to Claude Code]`
  5. Success: miyo-satori builds and starts; README covers all user-facing config; satori.toml.example is complete.

- [ ] **T7.2 TCS install.sh integration (R6.1)** `[activity: build-platform]`

  1. Prime: Read `install.sh` in TCS root. Read `[ref: SDD/TCS Submodule (R6.1)]` — MCP config block. CLAUDE.md guardrail: `.mcp.json` command paths must be absolute. `[ref: SDD/TCS Submodule (R6.1)]`
  2. Test: After `install.sh` runs context-mode section: `modules/satori/dist/index.js` exists (submodule initialized). Claude Code MCP config (`~/.claude/settings.json` or repo `.claude/settings.json`) contains a `satori` entry with absolute `args` path. The path resolves to an existing file. `[ref: PRD/R6.1; SDD/TCS Submodule (R6.1)]`
  3. Implement: Add to `install.sh`: (1) `git submodule update --init modules/satori` if not initialized; (2) `cd modules/satori && npm install && npm run build`; (3) resolve absolute path `SATORI_ABS=$(cd modules/satori && pwd)/dist/index.js`; (4) write MCP config entry using absolute path. Gate the section behind a feature prompt (context-mode feature). `[ref: SDD/TCS Submodule (R6.1)]`
  4. Validate: Run `install.sh` in test mode (or manually on a clean checkout): submodule initialized, dist built, MCP config entry present with absolute path, path resolves. `[ref: PRD/R6.1]`
  5. Success: `install.sh` initializes submodule, builds Satori, writes absolute-path MCP config; no relative paths in MCP config.

- [ ] **T7.3 .gitignore and repo hygiene** `[activity: build-platform]`

  1. Prime: Check TCS root `.gitignore` and `modules/satori/.gitignore`. `[ref: SDD/SQLite Schema; Database location section]`
  2. Test: TCS `.gitignore` contains: `modules/satori/node_modules/`, `modules/satori/dist/`. `modules/satori/.gitignore` contains: `dist/`, `node_modules/`, `.satori/`. `satori.toml` is NOT gitignored (user commits their config). `.satori/` is gitignored. `[ref: SDD/SQLite Schema]`
  3. Implement: Update TCS root `.gitignore` to exclude Satori build artifacts under `modules/satori/`. Update miyo-satori's own `.gitignore` to exclude `.satori/`, `dist/`, `node_modules/`. Verify `satori.toml.example` is tracked (not ignored). `[ref: SDD/SQLite Schema]`
  4. Validate: `git status` after install shows no unexpected tracked files in `modules/satori/`. `.satori/` absent from git. `satori.toml.example` tracked. `[ref: SDD/SQLite Schema]`
  5. Success: No build artifacts tracked in git; `.satori/` correctly gitignored; satori.toml.example committed.

- [ ] **T7.4 E2E roundtrip validation** `[activity: test-strategy]`

  1. Prime: Read `[ref: PRD/R1–R5]` acceptance criteria. `[ref: SDD/Gateway Routing/Tool Call Flow]`
  2. Test (E2E script): (1) Start Satori MCP server. (2) `satori_manage(add, {name: "memory", runtime: "npx", command: "@modelcontextprotocol/server-memory"})`. (3) `satori_exec("memory", "create_entities", {entities: [{name: "test", entityType: "test", observations: ["hello"]}]})` → success response. (4) Verify capture in ContentDB (1 row). (5) `satori_context(query, {q: "hello"})` → returns capture summary. (6) `satori_context(flush)` → snapshot XML in session_resume. (7) `satori_context(restore)` → returns XML. (8) Shut down Satori. `[ref: PRD/R1, R2, R3, R5]`
  3. Implement: Create `test/e2e/roundtrip.test.ts` — runs the above sequence using vitest and `@modelcontextprotocol/sdk` test client. Skip if `npx` unavailable (`process.env.CI && !process.env.RUN_E2E`). `[ref: PRD/R1–R5]`
  4. Validate: `RUN_E2E=1 npm test -- test/e2e/` — all steps pass. If any step fails, the failure message identifies the failing step clearly. `[ref: PRD/R1–R5]`
  5. Success: Full roundtrip verified; all PRD R1–R5 acceptance criteria met.

- [ ] **T7.5 Phase 7 Validation (M4 Complete)** `[activity: validate]`

  - `npm test` — all unit tests pass.
  - `RUN_E2E=1 npm test -- test/e2e/` — E2E roundtrip passes.
  - `npm run typecheck` — 0 errors.
  - `npm run build` — clean build.
  - TCS: `modules/satori/dist/index.js` present after `install.sh`.
  - MCP config: Satori entry with absolute path resolves to existing file.
  - `tools/list` → exactly 3 tools.
  - PRD acceptance criteria checklist:
    - [x] R1 satori_context: restore, query, status, flush — verified in E2E
    - [x] R2 Gateway: single MCP entry, g/p/r config — verified
    - [x] R3 Handler: passthrough default, extensible interface — verified
    - [x] R4 Hot/cold: npx server started on first exec call — verified in E2E
    - [x] R5 Security: startup scan + runtime OUT scan + audit log — unit tests
    - [x] R6.1 TCS submodule at modules/satori/ — install.sh verified
