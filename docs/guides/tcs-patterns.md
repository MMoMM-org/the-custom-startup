# tcs-patterns — Domain Pattern Skills

tcs-patterns is an optional plugin that brings 20 opinionated, interactive pattern skills to your Claude Code sessions. Skills are organized across 6 categories — architecture, API design and types, testing, language platforms, DevOps, and integrations — and each one activates on its own trigger terms, so you get focused guidance exactly when the relevant context appears. Install the full plugin and ignore what does not apply to your stack, or install selectively using the individual skill names.

```
/plugin install tcs-patterns@the-custom-startup
```

> Install only what's relevant to your stack — each skill adds ~25KB to your context

### Installing individual skills

If you don't want the full plugin, you can install individual skills:

**Option A — Use `/skill-import` (requires tcs-helper):**

```bash
/skill-import MMoMM-org/the-custom-startup plugins/tcs-patterns/skills/ddd
```

This fetches a single skill from the repository and installs it to the correct location, including any supporting files in `reference/` or `examples/`.

**Option B — Manual copy:**

Copy the skill directory from the repo to your Claude Code skills directory:

```bash
cp -r plugins/tcs-patterns/skills/ddd ~/.claude/skills/ddd
```

Include the entire directory (SKILL.md plus any `reference/`, `examples/`, `validation.md` subdirectories) — the skill may reference these supporting files at runtime.

### Agent integration

When `tcs-team` agents delegate specialist work, they automatically use relevant pattern skills if installed. You don't need to invoke patterns manually during agent-driven workflows.

| Agent | Uses patterns |
|---|---|
| `the-architect/design-system` | `ddd`, `hexagonal`, `event-driven`, `event-sourcing`, `twelve-factor` |
| `the-architect/review-security` | `api-design`, `secure-oauth-oidc` |
| `the-architect/review-robustness` | `functional`, `node-service` |
| `the-developer/build-feature` | `typescript-strict`, `api-design`, `node-service`, `go-idiomatic`, `python-project` |
| `the-tester/test-strategy` | `testing`, `mutation-testing`, `frontend-testing`, `react-testing`, `test-design-reviewer` |
| `the-devops/build-platform` | `twelve-factor` |
| `the-devops/monitor-production` | `observability` |

---

## Architecture

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `ddd` | Use when auditing or designing a domain model — triggered by requests to review bounded contexts, aggregate roots, value objects, domain events, or ubiquitous language consistency. | When designing domain models or reviewing bounded context boundaries. | `/ddd [path or scope to audit]` |
| `hexagonal` | Use when auditing or designing a layered architecture — triggered by requests to review ports and adapters, dependency direction, domain isolation from frameworks, or hexagonal architecture compliance. | When auditing whether infrastructure concerns are leaking into your domain core. | `/hexagonal [path or scope to audit]` |
| `functional` | Use when implementing or reviewing code for functional correctness — triggered by requests to audit side effects, mutation, impure functions, or error handling in functional pipelines. | When refactoring toward purity or reviewing code for hidden mutation and side effects. | `/functional [path or scope to audit]` |
| `event-driven` | Use when designing or reviewing event-driven systems — triggered by requests to audit event schemas, command/event naming, handler idempotency, correlation IDs, or message ordering assumptions. | When designing event schemas or auditing handler idempotency and ordering assumptions. | `/event-driven [service or module to audit]` |
| `event-sourcing` | Use when designing, implementing, or auditing an event-sourced context — the append-only log as source of truth, a Decider write model, rehydration by folding, an event store with optimistic concurrency, projections and read models, event versioning, snapshots. | When the event log is (or is becoming) your source of truth — and to decide whether it should be. | `/event-sourcing [bounded context, module, or path]` |

`event-driven` owns events as **messages** — schema, naming, correlation IDs, handler idempotency, ordering. `event-sourcing` owns events as **persistence**. The two are independent: a system can be event-driven over a CRUD database, and event-sourced with no message bus at all.

---

## API & Types

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `api-design` | Use when designing or reviewing HTTP APIs — enforces RESTful resource modelling, correct HTTP semantics, consistent error shapes, versioning strategy, and pagination contracts. | When designing new endpoints or reviewing an existing API for contract consistency. | `/api-design [API spec file, route definitions, or controller directory]` |
| `typescript-strict` | Use when working on TypeScript projects — triggered by requests to audit type safety, strict mode configuration, implicit any, null checks, or discriminated union patterns. | When tightening TypeScript strictness or auditing a codebase for unsafe type patterns. | `/typescript-strict [path, file, or tsconfig.json to audit]` |

---

## Security

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `secure-oauth-oidc` | Use when designing, implementing, auditing, or migrating OAuth 2.0 and OpenID Connect — covers authorization servers, clients and relying parties, resource servers, redirect URIs, PKCE, state and nonce, ID Token validation, refresh rotation, and sender-constrained tokens against the RFC 9700 / BCP 240 baseline. | When designing an auth flow, auditing one, or migrating off implicit or password grants. | `/secure-oauth-oidc [flow, component, or path]` |

`the-architect/review-security` **reviews** an auth change; this skill is the reference its findings are checkable against. Findings carry a control ID from the RFC 9700 catalog so the two can be reconciled rather than double-counted.

The browser-facing session layer that consumes these tokens — session cookies, CSRF policy, public/protected route classification — has no skill yet; see issue #98.

---

## Testing

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `testing` | Testing patterns for behavior-driven tests. Use when writing tests, creating test factories, structuring test files, or deciding what to test. Do NOT use for UI-specific testing (see frontend-testing or react-testing skills). | When setting up test structure or writing unit and integration tests for non-UI code. | `/testing` |
| `mutation-testing` | Use when strengthening test suites — runs mutation analysis to find tests that pass without actually verifying behavior, and guides writing assertions that kill surviving mutants. | When your test suite passes but you suspect it is not actually catching regressions. | `/mutation-testing [test directory or module to analyse]` |
| `frontend-testing` | Use when writing or reviewing frontend tests — enforces testing-library best practices, user-behavior assertions, network mocking at the boundary, and accessible queries. | When writing tests for UI components and you want behavior-first, accessible queries. | `/frontend-testing [test file or directory to audit]` |
| `react-testing` | Use when testing React components or hooks — enforces react-testing-library patterns, proper hook testing with renderHook, and async state handling. | When testing React components or custom hooks and you need React-specific patterns. | `/react-testing [component or hook test file to audit]` |
| `test-design-reviewer` | Evaluates test quality using Dave Farley's 8 properties. Use when reviewing tests, assessing test suite quality, or analyzing test effectiveness against TDD best practices. | When reviewing an existing test suite for quality and alignment with TDD principles. | `/test-design-reviewer` |

---

## Platforms

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `node-service` | Use when building or reviewing Node.js services — enforces async/await hygiene, unhandled rejection handling, graceful shutdown, and event loop safety. | When building a Node.js service or auditing one for reliability and event loop safety. | `/node-service [service source path to audit]` |
| `python-project` | Use when setting up or reviewing a Python project — triggered by requests to audit type hints, linter configuration, virtual environment setup, pytest structure, or PEP 8 compliance. | When starting a Python project or auditing one for type coverage and project hygiene. | `/python-project [project path or file to audit]` |
| `go-idiomatic` | Use when writing or reviewing Go code — enforces idiomatic error handling, small interface design, standard package layout, goroutine safety, and proper use of defer. | When writing Go code or reviewing it for idiomatic patterns and goroutine correctness. | `/go-idiomatic [package or file path to audit]` |

---

## DevOps

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `twelve-factor` | Use when auditing or designing service configuration, deployment, or runtime behaviour — triggered by requests to review environment config, stateless processes, log handling, backing services, or twelve-factor compliance. | When designing service configuration or auditing a deployment for twelve-factor compliance. | `/twelve-factor [repo path or service to audit]` |
| `observability` | Use when instrumenting a service or reviewing its telemetry — wide events and canonical log lines, OpenTelemetry traces and metrics, context propagation, sampling and metric cardinality, where instrumentation code belongs, and testing instrumentation as behaviour. | When instrumenting a service, or when nobody can see what production is doing. | `/observability [service, module, or path]` |

`twelve-factor` owns log transport and shape; `observability` owns what goes into the stream. SLOs, error budgets, alerting and dashboards belong to `the-devops/monitor-production`, not to either skill.

---

## Integrations

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `mcp-server` | Use when building or reviewing a Model Context Protocol server — triggered by requests to audit tool definitions, input schemas, error handling, transport setup, or capability declarations. | When building an MCP server or auditing tool definitions and capability declarations. | `/mcp-server [MCP server source path to audit or implement]` |
| `obsidian-plugin` | Use when building or reviewing Obsidian plugins — enforces plugin lifecycle patterns, proper event listener cleanup, mobile compatibility, and Obsidian API usage over raw DOM manipulation. | When building an Obsidian plugin or auditing one for lifecycle and mobile safety. | `/obsidian-plugin [plugin source path to audit]` |

---

## Hooks

Most pattern rules are advisory — the skill tells you what good looks like when you ask. A few are different: violating them is unrecoverable later, so the plugin enforces them at write time via a `PreToolUse` hook.

| Hook | Event | Scope | What it does |
|------|-------|-------|--------------|
| `block-eslint-disable.sh` | `PreToolUse` (`Write`/`Edit`/`NotebookEdit`) | Repos detected as Obsidian plugins | Denies any write that introduces `eslint-disable` (line, block, or file form) or a rule mapped to `"off"` in the ESLint config |

### Why this one blocks

The Obsidian community-plugin reviewer scans submissions for disabled ESLint rules and **rejects the plugin from official registration** if it finds any — for every rule the project's config loads, not just `obsidianmd/*`. There is no "justified disable" exception, so the fix is always code-side. The `obsidian-plugin` skill flags disables at audit time (Step 11); the hook stops them from being written in the first place.

The denial message names the offending rule and, for the rules that recur in practice (`ui/sentence-case`, `prefer-active-window-timers`, `manage-class`, `no-html-element-creation`, `@typescript-eslint/prefer-import` on CJS globals), the concrete non-disable fix.

### Scope gate

The hook stays completely silent unless all three hold:

1. the target file is inside a git repository,
2. that repository looks like an Obsidian plugin — a `manifest.json` containing `minAppVersion`, or a `package.json` depending on `obsidian`,
3. the target file is not Markdown (documentation legitimately quotes the pattern).

Content is read from the *incoming* text only (`content` / `new_string` / `new_source`), so removing an existing disable is never blocked by its own payload.

### Escape hatch

For a plugin that will never be submitted to the community directory, relaunch Claude with:

```bash
CLAUDE_ALLOW_ESLINT_DISABLE=1 claude
```
