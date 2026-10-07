# tcs-patterns — Domain Pattern Skills

tcs-patterns is an optional plugin with a catalogue of 21 opinionated, interactive pattern skills — architecture, API design and types, security, testing, language platforms, DevOps, and integrations — and an installer that puts only the patterns your repository needs into that repository. Each installed pattern activates on its own trigger terms, so you get focused guidance when the relevant context appears, and a repository pays for the skill listing of its own patterns only.

> **Upgrading from 1.x:** the 21 patterns are no longer plugin skills. None is active until you run the setup, and an installed pattern is `/tcs-<name>` (for example `/tcs-ddd`), not `/tcs-patterns:<name>`.

## Setup

```
/plugin install tcs-patterns@the-custom-startup
/tcs-patterns:patterns-setup install
```

Run the second command in the repository you want patterns for (it must be a git repository). The setup:

1. **Scans** the repository and proposes the patterns its files justify, each with its evidence and its cost in skill-listing characters.
2. **Asks at most three questions** (backend concerns, architectural styles, test-quality checks), and only those the scan could not settle. A repository without a server framework is never asked about backends.
3. **Confirms** what will be installed, which companions are offered (a pattern that cites another), and what was left out and why. Nothing is written before you confirm.
4. **Installs** each pattern into `.claude/skills/tcs-<name>/` and records it in `.claude/skills/.tcs-patterns-manifest`.
5. **Offers to commit** exactly those files. Teammates get the patterns only once they are committed.

### Installed patterns

An installed pattern is a normal repository skill, invoked by its prefixed name (see the invocation column below) or by its trigger terms. The `tcs-` prefix keeps patterns apart from your own skills; the installer refuses to overwrite a skill it did not write.

### The four verbs

```
/tcs-patterns:patterns-setup <install|update|remove|status> [path]
```

| Verb | What it does |
|---|---|
| `install` | The flow above. |
| `update` | Refreshes patterns whose catalogue version moved on. A pattern with local edits is shown as a diff and replaced only on your say-so. |
| `remove` | Deletes a pattern and its manifest entry. Local edits are shown as a diff first and deleted only on your say-so. |
| `status` | Reports what is installed, its version, what has drifted, and leftovers of an interrupted run. Changes nothing. |

### Reading a pattern without installing it

```
/tcs-patterns:pattern <pattern-name>
```

Prints the pattern's full body as shipped and writes nothing. An unknown name lists the available patterns.

### Drift advisory

Installed patterns are copies. With `tcs-git-helpers` installed, its session-start brief names any installed pattern that is behind the catalogue and points to `/tcs-patterns:patterns-setup update`. Repositories without installed patterns see nothing. Without `tcs-git-helpers`, run `status`.

### Agent integration

Installed patterns are ordinary repository skills, so any session in that repository, including those that `tcs-team` agents run, can pick them up by their descriptions. Patterns you did not install are not loaded.

---

The invocation column below shows the name an installed pattern has; arguments are optional scope hints.

## Architecture

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `ddd` | Use when auditing or designing a domain model — triggered by requests to review bounded contexts, aggregate roots, value objects, domain events, or ubiquitous language consistency. | When designing domain models or reviewing bounded context boundaries. | `/tcs-ddd [path or scope to audit]` |
| `hexagonal` | Use when auditing or designing a layered architecture — triggered by requests to review ports and adapters, dependency direction, domain isolation from frameworks, or hexagonal architecture compliance. | When auditing whether infrastructure concerns are leaking into your domain core. | `/tcs-hexagonal [path or scope to audit]` |
| `functional` | Use when implementing or reviewing code for functional correctness — triggered by requests to audit side effects, mutation, impure functions, or error handling in functional pipelines. | When refactoring toward purity or reviewing code for hidden mutation and side effects. | `/tcs-functional [path or scope to audit]` |
| `event-driven` | Use when designing or reviewing event-driven systems — triggered by requests to audit event schemas, command/event naming, handler idempotency, correlation IDs, or message ordering assumptions. | When designing event schemas or auditing handler idempotency and ordering assumptions. | `/tcs-event-driven [service or module to audit]` |
| `event-sourcing` | Use when designing, implementing, or auditing an event-sourced context — the append-only log as source of truth, a Decider write model, rehydration by folding, an event store with optimistic concurrency, projections and read models, event versioning, snapshots. | When the event log is (or is becoming) your source of truth — and to decide whether it should be. | `/tcs-event-sourcing [bounded context, module, or path]` |

`event-driven` owns events as **messages** — schema, naming, correlation IDs, handler idempotency, ordering. `event-sourcing` owns events as **persistence**. The two are independent: a system can be event-driven over a CRUD database, and event-sourced with no message bus at all.

---

## API & Types

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `api-design` | Use when designing or reviewing HTTP APIs — enforces RESTful resource modelling, correct HTTP semantics, consistent error shapes, versioning strategy, and pagination contracts. | When designing new endpoints or reviewing an existing API for contract consistency. | `/tcs-api-design [API spec file, route definitions, or controller directory]` |
| `typescript-strict` | Use when working on TypeScript projects — triggered by requests to audit type safety, strict mode configuration, implicit any, null checks, or discriminated union patterns. | When tightening TypeScript strictness or auditing a codebase for unsafe type patterns. | `/tcs-typescript-strict [path, file, or tsconfig.json to audit]` |

---

## Security

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `secure-oauth-oidc` | Use when designing, implementing, auditing, or migrating OAuth 2.0 and OpenID Connect — covers authorization servers, clients and relying parties, resource servers, redirect URIs, PKCE, state and nonce, ID Token validation, refresh rotation, and sender-constrained tokens against the RFC 9700 / BCP 240 baseline. | When designing an auth flow, auditing one, or migrating off implicit or password grants. | `/tcs-secure-oauth-oidc [flow, component, or path]` |
| `bff-entry-points` | Use when adding, hardening, or auditing browser-facing HTTP entry points — an explicit public/protected classification for every production route, a composition-prepared registrar, session cookies, CSRF, Origin and Fetch Metadata policy, protected SSE and WebSocket upgrades, and the automated gates that keep it true. | When adding or reviewing an endpoint, or when nobody can say which routes are public. | `/tcs-bff-entry-points [service, route, or path]` |

`the-architect/review-security` **reviews** an auth change; this pattern is the reference its findings are checkable against. Findings carry a control ID from the RFC 9700 catalog so the two can be reconciled rather than double-counted.

`secure-oauth-oidc` stops at "token obtained"; `bff-entry-points` starts at "application session established". One owns the protocol, the other owns the session it produces and every route that session unlocks.

---

## Testing

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `testing` | Testing patterns for behavior-driven tests. Use when writing tests, creating test factories, structuring test files, or deciding what to test. Do NOT use for UI-specific testing (see frontend-testing or react-testing skills). | When setting up test structure or writing unit and integration tests for non-UI code. | `/tcs-testing` |
| `mutation-testing` | Use when strengthening test suites — runs mutation analysis to find tests that pass without actually verifying behavior, and guides writing assertions that kill surviving mutants. | When your test suite passes but you suspect it is not actually catching regressions. | `/tcs-mutation-testing [test directory or module to analyse]` |
| `frontend-testing` | Use when writing or reviewing frontend tests — enforces testing-library best practices, user-behavior assertions, network mocking at the boundary, and accessible queries. | When writing tests for UI components and you want behavior-first, accessible queries. | `/tcs-frontend-testing [test file or directory to audit]` |
| `react-testing` | Use when testing React components or hooks — enforces react-testing-library patterns, proper hook testing with renderHook, and async state handling. | When testing React components or custom hooks and you need React-specific patterns. | `/tcs-react-testing [component or hook test file to audit]` |
| `test-design-reviewer` | Evaluates test quality using Dave Farley's 8 properties. Use when reviewing tests, assessing test suite quality, or analyzing test effectiveness against TDD best practices. | When reviewing an existing test suite for quality and alignment with TDD principles. | `/tcs-test-design-reviewer` |

---

## Platforms

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `node-service` | Use when building or reviewing Node.js services — enforces async/await hygiene, unhandled rejection handling, graceful shutdown, and event loop safety. | When building a Node.js service or auditing one for reliability and event loop safety. | `/tcs-node-service [service source path to audit]` |
| `python-project` | Use when setting up or reviewing a Python project — triggered by requests to audit type hints, linter configuration, virtual environment setup, pytest structure, or PEP 8 compliance. | When starting a Python project or auditing one for type coverage and project hygiene. | `/tcs-python-project [project path or file to audit]` |
| `go-idiomatic` | Use when writing or reviewing Go code — enforces idiomatic error handling, small interface design, standard package layout, goroutine safety, and proper use of defer. | When writing Go code or reviewing it for idiomatic patterns and goroutine correctness. | `/tcs-go-idiomatic [package or file path to audit]` |

---

## DevOps

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `twelve-factor` | Use when auditing or designing service configuration, deployment, or runtime behaviour — triggered by requests to review environment config, stateless processes, log handling, backing services, or twelve-factor compliance. | When designing service configuration or auditing a deployment for twelve-factor compliance. | `/tcs-twelve-factor [repo path or service to audit]` |
| `observability` | Use when instrumenting a service or reviewing its telemetry — wide events and canonical log lines, OpenTelemetry traces and metrics, context propagation, sampling and metric cardinality, where instrumentation code belongs, and testing instrumentation as behaviour. | When instrumenting a service, or when nobody can see what production is doing. | `/tcs-observability [service, module, or path]` |

`twelve-factor` owns log transport and shape; `observability` owns what goes into the stream. SLOs, error budgets, alerting and dashboards belong to `the-devops/monitor-production`, not to either skill.

---

## Integrations

| Pattern | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `mcp-server` | Use when building or reviewing a Model Context Protocol server — triggered by requests to audit tool definitions, input schemas, error handling, transport setup, or capability declarations. | When building an MCP server or auditing tool definitions and capability declarations. | `/tcs-mcp-server [MCP server source path to audit or implement]` |
| `obsidian-plugin` | Use when building or reviewing Obsidian plugins — enforces plugin lifecycle patterns, proper event listener cleanup, mobile compatibility, and Obsidian API usage over raw DOM manipulation. | When building an Obsidian plugin or auditing one for lifecycle and mobile safety. | `/tcs-obsidian-plugin [plugin source path to audit]` |

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
