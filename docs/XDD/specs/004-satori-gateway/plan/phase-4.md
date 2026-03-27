---
title: "Phase 4: Lifecycle Management"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Lifecycle Management

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "Hot/Cold Lifecycle State Machine" and the runtime descriptions (npx, docker, external) before starting.

**Specification References**:
- `[ref: SDD/Hot/Cold Lifecycle State Machine]` — state diagram, npx + docker + external runtimes
- `[ref: SDD/Handler Interface]` — SatoriHandler, ToolCallRequest, BlockedResult
- `[ref: SDD/Repository Structure; src/lifecycle/, src/handlers/]`

**Key Decisions**:
- State machine: `stopped → starting → running | error | blocked`; `satori_manage disable` → `blocked`
- `npx` runtime: spawn `npx -y <command> [args]`, wait for `tools/list` response, STDIO transport
- `docker` runtime: `docker run --rm -d`, poll `docker inspect` for running state, HTTP transport
- `external` runtime: no lifecycle management; connect via host/port
- Handler pipeline: `beforeCall` → `afterCall`; passthrough is the default (no-op)

**Dependencies**: Phase 3 (registry + security needed for lifecycle start and handler lookup).

---

## Tasks

Builds the hot/cold lifecycle state machine for npx and Docker runtimes, the handler interface,
and the passthrough handler. After this phase, Satori can start, health-check, and route through
a downstream server.

- [ ] **T4.1 Server state machine (lifecycle/state.ts + manager.ts)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Hot/Cold Lifecycle State Machine]` — full state diagram. `[ref: SDD/Repository Structure; src/lifecycle/]`
  2. Test: `LifecycleManager.start("filesystem")` transitions from `stopped → starting → running`. `start()` on an already-`running` server is a no-op. `start()` when state is `blocked` returns error immediately. `stop()` transitions `running → stopped`. State is readable via `getState(name)`. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  3. Implement: Create `src/lifecycle/state.ts` — `ServerState` type (`"stopped" | "starting" | "running" | "error" | "blocked"`), `ServerStateMap`. Create `src/lifecycle/manager.ts` — `LifecycleManager` class: `start(name)`, `stop(name)`, `getState(name)`, `setBlocked(name, reason)`. Start delegates to runtime-specific module based on `ServerConfig.runtime`. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  4. Validate: Unit tests with mocked runtime modules: all state transitions verified; concurrent `start()` calls don't double-spawn. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  5. Success: State machine tests pass; transitions are correct; blocked state prevents start attempts.

- [ ] **T4.2 npx runtime** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Hot/Cold Lifecycle State Machine; npx runtime section]`. MCP SDK STDIO transport docs. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  2. Test: `NpxRuntime.start(config)` spawns a child process and returns a connected MCP `Client`. `tools/list` succeeds against the spawned server. `stop()` terminates the child process (SIGTERM + SIGKILL fallback). Timeout during `tools/list` → transitions to `error` state. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  3. Implement: Create `src/lifecycle/runtimes/npx.ts` — `NpxRuntime` class. `start()`: spawn `npx -y <command> [args]` with env, attach `StdioClientTransport`, call `client.connect()`, call `client.listTools()` as health check. Return `{client, process}`. `stop()`: send SIGTERM; if still running after 3s, SIGKILL. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  4. Validate: Integration test (skipped in CI if npx unavailable): spawn `@modelcontextprotocol/server-memory`, call `tools/list`, verify non-empty. Stop — process exits. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  5. Success: npx runtime starts a real MCP server, passes health check, stops cleanly; unit tests with mocked spawn pass in CI.

- [ ] **T4.3 Docker runtime** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Hot/Cold Lifecycle State Machine; Docker runtime section]`. `dockerode` API docs. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  2. Test: `DockerRuntime.start(config)` calls `dockerode` to start container with correct env flags and port mapping. `stop()` stops the container. Docker unavailable → graceful error (not crash). `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  3. Implement: Create `src/lifecycle/runtimes/docker.ts` — `DockerRuntime` class. `start()`: `docker.createContainer({...}).start()`, poll `inspect` until running (max 30s), connect via HTTP transport at mapped port. `stop()`: `container.stop()`. Dependency check: test `docker info` before any op; if unavailable, return error immediately. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  4. Validate: Unit tests with mocked dockerode verify API call shapes. Docker-unavailable test: graceful error returned. `[ref: SDD/Hot/Cold Lifecycle State Machine]`
  5. Success: Docker runtime implementation complete; unit tests pass; graceful docker-absent handling.

- [ ] **T4.4 Handler interface and passthrough handler** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Handler Interface]` — `SatoriHandler`, `ToolCallRequest`, `ToolCallResponse`, `BlockedResult`. `[ref: SDD/Handler Interface]`
  2. Test: `PassthroughHandler.beforeCall(req)` returns `req` unchanged. `PassthroughHandler.afterCall(req, res)` returns `res` unchanged. `HandlerRegistry.lookup("passthrough")` returns `PassthroughHandler`. `HandlerRegistry.lookup("unknown")` returns `PassthroughHandler` (safe default). `[ref: SDD/Handler Interface]`
  3. Implement: Create `src/handlers/interface.ts` — export `ToolCallRequest`, `ToolCallResponse`, `BlockedResult`, `SatoriHandler` interface, `ServerConfig` type. Create `src/handlers/passthrough.ts` — `PassthroughHandler implements SatoriHandler`. Create `src/handlers/registry.ts` — `HandlerRegistry`: `register(handler)`, `lookup(name)` (returns passthrough if not found). `[ref: SDD/Handler Interface]`
  4. Validate: Unit tests: passthrough returns inputs unchanged; registry lookup by name; fallback to passthrough. `[ref: SDD/Handler Interface]`
  5. Success: Handler interface complete; passthrough is a safe no-op; registry falls back gracefully.

- [ ] **T4.5 Phase 4 Validation** `[activity: validate]`

  - `npm test` — all Phase 4 unit tests pass.
  - `npm run typecheck` — 0 errors.
  - State machine: `stopped → starting → running → stopped` verified.
  - Blocked state: `start()` returns error without spawning.
  - PassthroughHandler: request and response pass through unmodified.
  - HandlerRegistry: unknown name → returns passthrough (no throw).
