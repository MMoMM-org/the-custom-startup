---
title: "Phase 3: Config, Registry & Security"
status: pending
version: "1.0"
phase: 3
parallel: true
---

# Phase 3: Config, Registry & Security

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "Config Schema", "Security Implementation", and "Auto-Registration" before starting.

**Specification References**:
- `[ref: SDD/Config Schema]` — TOML schema, g/p/r resolution order, env var expansion
- `[ref: SDD/Security Implementation]` — startup scan, runtime OUT scan, audit log format
- `[ref: SDD/Auto-Registration]` — .mcp.json import flow
- `[ref: SDD/Tools Exposed to Claude Code/satori_manage]` — sub-command table with add/remove

**Key Decisions**:
- g/p/r merge: global → project → repo; `[[servers]]` merged by `name` (repo wins)
- `${VAR}` expansion at server start time, not parse time; unexpanded → startup error
- Startup scan: config fields + tool descriptions; runtime OUT scan: `arguments` object before every `satori_exec`
- Auto-registration is opt-in (`auto_register_mcp_json = false` by default)
- `satori_manage add/remove` write to TOML file at specified scope

**Dependencies**: Phase 1 (SQLiteBase). Runs in parallel with Phase 2.

---

## Tasks

Builds config loading, server registry, security scanner, audit log, auto-registration, and the
`satori_manage` tool. After this phase the gateway knows which servers are configured, can scan
them for security issues, and can add/remove servers via tool call.

- [ ] **T3.1 Config loader (TOML + g/p/r merge)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Config Schema/Resolution Order]` and the full TOML schema. `smol-toml` docs. `[ref: SDD/Config Schema]`
  2. Test: `loadConfig(repoRoot)` merges global → project → repo configs. Repo-level `[[servers]]` with same name as global entry shadows global. `${VAR}` in env fields expands from `process.env`. Unexpanded `${MISSING_VAR}` throws at expand time (not parse time). Missing config files are silently ignored (treated as empty). `[ref: SDD/Config Schema/Resolution Order]`
  3. Implement: Create `src/config/schema.ts` (TypeScript types: `SatoriConfig`, `ServerConfig`, `GatewayConfig`, `ContextConfig`, `SecurityConfig`). Create `src/config/loader.ts` — `loadConfig(repoRoot: string): SatoriConfig`. Locate and parse the three TOML files. Merge: scalar fields override, `[[servers]]` arrays merged by `name`. Env expansion: `expandEnv(value: string, env: NodeJS.ProcessEnv)` — replace `${KEY}` with `process.env[KEY]` or throw. `[ref: SDD/Config Schema]`
  4. Validate: Unit tests: merge test (3 configs, repo wins). Env expansion: `${GITHUB_TOKEN}` → actual value. Missing var → throws with clear message naming the var. All SDD TOML fields parse correctly (boolean, string, array). `[ref: SDD/Config Schema]`
  5. Success: Config loader tests pass; g/p/r merge correct; env expansion works; missing files tolerated.

- [ ] **T3.2 Server registry** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Repository Structure; src/gateway/registry.ts]`. `[ref: SDD/Config Schema/Downstream server definitions]`
  2. Test: `ServerRegistry.load(config)` registers all `[[servers]]` entries. `registry.lookup("filesystem")` returns `ServerConfig`. `registry.lookup("unknown")` returns `null`. Duplicate `name` entries — last one wins (g/p/r already merged before registry load). `registry.list()` returns all entries with current `enabled` state. `[ref: SDD/Config Schema]`
  3. Implement: Create `src/gateway/registry.ts` — `ServerRegistry` class. Holds a `Map<string, ServerConfig>` keyed by server name. `load(config: SatoriConfig)`: populate map from `config.servers`. Methods: `lookup(name)`, `list()`, `setEnabled(name, enabled)`. `[ref: SDD/Repository Structure; src/gateway/registry.ts]`
  4. Validate: Unit tests for all methods. Load 3 servers; lookup each; lookup unknown → null; list() returns all 3. `[ref: SDD/Config Schema]`
  5. Success: Registry correctly populated from config; lookup and list work; all tests pass.

- [ ] **T3.3 Security scanner and audit log** `[activity: review-security]`

  1. Prime: Read `[ref: SDD/Security Implementation]` — startup scan, runtime OUT scan, patterns, audit log format. `[ref: SDD/Security Implementation]`
  2. Test: `scanOut(args)` detects: `sk-[A-Za-z0-9]{20,}` API key in string value → `BlockedResult`; `GITHUB_PERSONAL_ACCESS_TOKEN` key with non-empty value → `BlockedResult`; clean args → `null` (not blocked). Startup config scan: `&&` in command field → flagged. Startup description scan: `exfiltrate` in tool description → blocked. Audit log: entries appended in correct format with ISO timestamp. `[ref: SDD/Security Implementation]`
  3. Implement: Create `src/security/patterns.ts` — regex array for API keys, env var names, shell injection. Create `src/security/scanner.ts` — `scanOut(args): BlockedResult | null`, `scanConfig(config): ScanResult`, `scanDescription(desc): ScanResult`. Create `src/security/audit-log.ts` — `appendAuditLog(entry: AuditEntry): void` (append-only, sync write). `[ref: SDD/Security Implementation]`
  4. Validate: Unit tests: 6 blocked patterns hit; 3 clean inputs pass. Audit log test: write 3 entries, read file, verify ISO timestamps and format. `[ref: SDD/Security Implementation]`
  5. Success: All security tests pass; blocked inputs never reach downstream; audit log is append-only.

- [ ] **T3.4 Auto-registration (.mcp.json import)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Auto-Registration]` — 5-step flow, `.mcp.satori-json` rename. `[ref: SDD/Auto-Registration]`
  2. Test: With `auto_register_mcp_json = true` and `.mcp.json` present: servers parsed and written to `satori.toml`; `.mcp.json` renamed to `.mcp.satori-json`. With `auto_register_mcp_json = false`: no import happens. `.mcp.json` absent: no error. Duplicate: server already in `satori.toml` → not duplicated. `[ref: SDD/Auto-Registration]`
  3. Implement: Create `src/config/auto-register.ts` — `autoRegisterMcpJson(repoRoot, config)`: detect `.mcp.json`, parse, map to `[[servers]]` TOML blocks (detect npx vs external from command shape), append to `satori.toml`, rename `.mcp.json`. `[ref: SDD/Auto-Registration]`
  4. Validate: Integration test in temp dir: write `.mcp.json`, run `autoRegisterMcpJson()`, verify `satori.toml` contains server entries, `.mcp.satori-json` exists, `.mcp.json` gone. `[ref: SDD/Auto-Registration]`
  5. Success: Auto-registration test passes; idempotent on re-run; `.mcp.satori-json` preserved for rollback.

- [ ] **T3.5 satori_manage tool** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Tools Exposed to Claude Code/satori_manage]` — all 8 sub-commands (list, add, remove, enable, disable, state, scan, reload). `[ref: SDD/Tools Exposed to Claude Code/satori_manage]`
  2. Test: `list` returns all registered servers with state and handler. `add` writes new `[[servers]]` entry to correct scope TOML file. `remove` deletes entry from TOML. `enable`/`disable` toggle `enabled` flag in TOML. `state` returns current `ServerState`. `scan` re-runs security scanner and returns result. `reload` invalidates the tool catalog for the named server (or all) and triggers a fresh `tools/list` call on running servers. `[ref: SDD/Tools Exposed to Claude Code/satori_manage]`
  3. Implement: Create `src/tools/satori-manage.ts` — dispatches on `sub_command`. `add`/`remove`/`enable`/`disable` read the target TOML, modify, and write back. `list` queries `ServerRegistry`. `state` queries lifecycle `LifecycleManager`. `scan` calls `scanner.scanConfig()`. `reload` calls `catalog.clear(name?)` then re-populates from `tools/list` on running servers. `[ref: SDD/Tools Exposed to Claude Code/satori_manage]`
  4. Validate: Integration test with temp `satori.toml`: `add` → file contains new entry; `remove` → entry gone; `enable`/`disable` → flag toggled. `list` → returns entries. `reload` on a populated catalog → catalog cleared and repopulated. `[ref: SDD/Tools Exposed to Claude Code/satori_manage]`
  5. Success: All 8 satori_manage sub-commands work; TOML mutations are non-destructive (preserve existing entries and comments where possible); tool registered in MCP server.

- [ ] **T3.6 Phase 3 Validation** `[activity: validate]`

  - `npm test` — all Phase 3 tests pass.
  - `npm run typecheck` — 0 errors.
  - MCP `tools/list` includes `satori_manage`.
  - `satori_manage(list)` → empty list (no servers configured).
  - `satori_manage(add, {name: "test", runtime: "npx", command: "..."})` → adds entry; `satori_manage(list)` → shows it; `satori_manage(remove, {name: "test"})` → removes it.
  - Security: `scanOut({API_KEY: "sk-abc123abcdefghijklmno"})` → blocked result.
