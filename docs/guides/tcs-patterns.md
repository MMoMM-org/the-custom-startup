# tcs-patterns — Domain Pattern Skills

tcs-patterns is an optional plugin that brings 17 opinionated, interactive pattern skills to your Claude Code sessions. Skills are organized across 6 categories — architecture, API design and types, testing, language platforms, DevOps, and integrations — and each one activates on its own trigger terms, so you get focused guidance exactly when the relevant context appears. Install the full plugin and ignore what does not apply to your stack, or install selectively using the individual skill names.

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
| `the-architect/design-system` | `ddd`, `hexagonal`, `event-driven`, `twelve-factor` |
| `the-architect/review-security` | `api-design` |
| `the-architect/review-robustness` | `functional`, `node-service` |
| `the-developer/build-feature` | `typescript-strict`, `api-design`, `node-service`, `go-idiomatic`, `python-project` |
| `the-tester/test-strategy` | `testing`, `mutation-testing`, `frontend-testing`, `react-testing`, `test-design-reviewer` |
| `the-devops/build-platform` | `twelve-factor` |

---

## Architecture

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `ddd` | Use when auditing or designing a domain model — triggered by requests to review bounded contexts, aggregate roots, value objects, domain events, or ubiquitous language consistency. | When designing domain models or reviewing bounded context boundaries. | `/ddd [path or scope to audit]` |
| `hexagonal` | Use when auditing or designing a layered architecture — triggered by requests to review ports and adapters, dependency direction, domain isolation from frameworks, or hexagonal architecture compliance. | When auditing whether infrastructure concerns are leaking into your domain core. | `/hexagonal [path or scope to audit]` |
| `functional` | Use when implementing or reviewing code for functional correctness — triggered by requests to audit side effects, mutation, impure functions, or error handling in functional pipelines. | When refactoring toward purity or reviewing code for hidden mutation and side effects. | `/functional [path or scope to audit]` |
| `event-driven` | Use when designing or reviewing event-driven systems — triggered by requests to audit event schemas, command/event naming, handler idempotency, correlation IDs, or message ordering assumptions. | When designing event schemas or auditing handler idempotency and ordering assumptions. | `/event-driven [service or module to audit]` |

---

## API & Types

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `api-design` | Use when designing or reviewing HTTP APIs — enforces RESTful resource modelling, correct HTTP semantics, consistent error shapes, versioning strategy, and pagination contracts. | When designing new endpoints or reviewing an existing API for contract consistency. | `/api-design [API spec file, route definitions, or controller directory]` |
| `typescript-strict` | Use when working on TypeScript projects — triggered by requests to audit type safety, strict mode configuration, implicit any, null checks, or discriminated union patterns. | When tightening TypeScript strictness or auditing a codebase for unsafe type patterns. | `/typescript-strict [path, file, or tsconfig.json to audit]` |

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

---

## Integrations

| Skill | What it does | When to invoke | Invocation |
|-------|-------------|----------------|------------|
| `mcp-server` | Use when building or reviewing a Model Context Protocol server — triggered by requests to audit tool definitions, input schemas, error handling, transport setup, or capability declarations. | When building an MCP server or auditing tool definitions and capability declarations. | `/mcp-server [MCP server source path to audit or implement]` |
| `obsidian-plugin` | Use when building or reviewing Obsidian plugins — enforces plugin lifecycle patterns, proper event listener cleanup, mobile compatibility, and Obsidian API usage over raw DOM manipulation. | When building an Obsidian plugin or auditing one for lifecycle and mobile safety. | `/obsidian-plugin [plugin source path to audit]` |
