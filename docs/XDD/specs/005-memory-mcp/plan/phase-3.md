---
title: "Phase 3: Gateway Integration — BuiltinServer + Router + Wiring"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Gateway Integration — BuiltinServer + Router + Wiring

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1; BuiltinRuntime dispatch in router]`
- `[ref: SDD/Router Modification; builtin dispatch branch]`
- `[ref: SDD/BuiltinServer Internal Interface]`
- `[ref: SDD/Primary Flow; satori_exec sequence diagram]`
- `[ref: SDD/System-Wide Patterns; Security — scanArgs on builtin]`
- `[ref: SDD/Implementation Gotchas; satori_exec args type casting]`
- `modules/satori/src/gateway/router.ts` — existing pipeline (lines 32-130)
- `modules/satori/src/security/scanner.ts` — existing scanConfig (lines 96-117)
- `modules/satori/src/index.ts` — startup wiring

**Key Decisions**:
- ADR-1: `runtime === 'builtin'` branch in router before lifecycle check — BuiltinServer injected into router constructor
- BuiltinServer is NOT a RuntimeInterface — it bypasses LifecycleManager entirely
- SecurityScanner.scanConfig() must skip shell injection check for runtime='builtin' (no command field)
- SecurityScanner.scanArgs() still applies to all builtin exec args
- `index.ts` must register `satori_kb` tool and init `KnowledgeDB`; check `context.backend` and warn if 'kairn'
- "bash" builtin server auto-registered — added to registry before user config loads

**Dependencies**:
- T2.1 (PolyglotExecutor) must be complete before T3.1
- T1.3 (KnowledgeDB) must be complete before T3.1 (intent-driven mode)
- T3.2 (scanner mod) is independent of T3.1 — run in parallel
- T3.3 (router) depends on T3.1 + T3.2
- T3.4 (index.ts) depends on T3.3 + T2.2 (satori_kb tool)

---

## Tasks

Wires all new components into the live Satori MCP server — the router, security scanner, and startup sequence.

- [x] **T3.1 BuiltinServer** `[activity: backend-api]`

  **Prime**: Read `modules/satori/src/lifecycle/runtimes/npx.ts` (pattern to understand, not extend); read `[ref: SDD/BuiltinServer Internal Interface]`; read Phase 2 PolyglotExecutor and KnowledgeDB output

  **Test**:
  - `BuiltinServer.exec('bash', 'run', {language: 'python', code: 'print(1)'})` returns output string
  - `BuiltinServer.exec('bash', 'run_file', {path: '...', language: 'shell'})` executes file
  - `BuiltinServer.exec('bash', 'batch', {commands: [{label:'a', command:'echo hi'}], queries: ['hi']})` returns indexed results
  - Intent-driven mode: output > 5KB + intent set → returns `intent_search_results` not raw output
  - Intent-driven mode: output ≤ 5KB + intent set → returns full output (intent ignored)
  - Unknown tool name returns error
  - Unknown server name returns error

  **Implement**:
  - Create `modules/satori/src/execution/builtin-server.ts` — `BuiltinServer` class; constructor takes `PolyglotExecutor` + `KnowledgeDB`; `exec(serverName, tool, args)` method; dispatches `run`/`run_file`/`batch` to executor; implements intent-driven mode threshold (5KB = 5_000 bytes); `batch` indexes each command output + runs queries

  **Validate**: Unit tests pass; typecheck passes

  - Success: Intent-driven mode threshold is exactly 5_000 bytes `[ref: SDD/Complex Logic; intent-driven mode]`
  - Success: `batch` auto-indexes and returns search results in one response `[ref: PRD/F3; batch AC]`

- [x] **T3.2 SecurityScanner modification** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read `modules/satori/src/security/scanner.ts` in full; read `[ref: SDD/System-Wide Patterns; Security]`

  **Test**:
  - `scanConfig({name: 'bash', runtime: 'builtin'})` returns `{status: 'passed'}` (no command to scan)
  - `scanConfig({name: 'bad', runtime: 'npx', command: 'evil && rm -rf'})` still blocked (existing behaviour unchanged)
  - `scanArgs({code: 'print(1)'})` passes (clean args)
  - Existing scanner tests all still pass

  **Implement**:
  - Edit `modules/satori/src/security/scanner.ts` — in `scanConfig()`, skip shell injection pattern check when `config.runtime === 'builtin'` (no `command` or `image` field to scan)

  **Validate**: All existing scanner tests pass + new builtin tests; typecheck passes

  - Success: `runtime='builtin'` servers pass startup scan without false positives `[ref: SDD/System-Wide Patterns; Security]`
  - Success: All existing non-builtin scan behaviour unchanged `[ref: SDD/Implementation Boundaries; Must Preserve]`

- [x] **T3.3 Router modification** `[activity: backend-api]`

  **Prime**: Read `modules/satori/src/gateway/router.ts` lines 32-130 in full; read `[ref: SDD/Router Modification]` and `[ref: SDD/ADR-1]`

  **Test**:
  - `router.exec('bash', 'run', {language: 'shell', code: 'echo 1'})` routes to BuiltinServer (not lifecycle)
  - `router.exec('bash', 'run', {...})` result is captured to ContentDB (insertCapture called)
  - `router.exec('bash', 'run', {...})` scanArgs runs before dispatch
  - `router.exec('npx-server', 'some-tool', {})` still routes through existing lifecycle path (unchanged)
  - Blocked scanArgs on builtin returns isError response without executing

  **Implement**:
  - Edit `modules/satori/src/gateway/router.ts` — inject `BuiltinServer` via constructor; add branch after `registry.lookup()`: if `config.runtime === 'builtin'`, run `scanArgs` → `builtinServer.exec()` → `insertCapture` → `summarizeAsync` → return; existing lifecycle flow unchanged for all other runtimes

  **Validate**: All existing router tests pass + new builtin routing tests; typecheck passes

  - Success: Builtin dispatch bypasses LifecycleManager entirely `[ref: SDD/ADR-1]`
  - Success: Capture + summarize applied to builtin results `[ref: SDD/Primary Flow; sequence diagram]`
  - Success: Existing npx/docker/external routing behaviour unchanged `[ref: SDD/Implementation Boundaries]`

- [x] **T3.4 index.ts wiring** `[activity: backend-api]`

  **Prime**: Read `modules/satori/src/index.ts` in full; read `[ref: SDD/Directory Map]` and `[ref: SDD/Error Handling; context.backend kairn warning]`

  **Test**:
  - Startup with `context.backend = 'kairn'` in config logs warning and falls back to satori
  - `satori_kb` tool registered in MCP server (appears in tool list)
  - "bash" builtin server present in registry after startup
  - `KnowledgeDB` initialised and `kb.sqlite` created on first use
  - `BuiltinServer` injected into router with correct `PolyglotExecutor` + `KnowledgeDB` instances

  **Implement**:
  - Edit `modules/satori/src/index.ts`:
    1. Init `KnowledgeDB` (after ContentDB init, same `.satori/` directory)
    2. Check `config.context?.backend === 'kairn'` → log warning
    3. Create `PolyglotExecutor` + `BuiltinServer(executor, knowledgeDb)`
    4. Register "bash" server in registry as builtin (prepend to config.servers before registry.load)
    5. Inject `builtinServer` into `GatewayRouter` constructor
    6. Call `registerSatoriKb(server, knowledgeDb)` alongside existing tool registrations

  **Validate**: Full `npm run test`; typecheck passes; manual smoke test: start Satori, call `satori_exec("bash", "run", {language: "shell", code: "echo ok"})` via MCP

  - Success: All 6 tools registered in MCP server `[ref: SDD/Directory Map]`
  - Success: `context.backend='kairn'` warning logged at startup `[ref: PRD/F7; Kairn prep AC]`
  - Success: "bash" builtin server appears in `satori_manage(list)` output `[ref: PRD/F3]`

- [x] **T3.5 Phase 3 Validation** `[activity: validate]`

  Run full `npm run test` suite. Run `npm run typecheck`. Verify no regressions in existing satori tests (satori-manage, config-loader, satori-context). Confirm router handles both builtin and existing runtime paths correctly.
