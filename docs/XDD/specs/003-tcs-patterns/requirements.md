---
spec: 003-tcs-patterns
document: requirements
status: completed
version: "1.0"
---

# PRD — tcs-patterns Plugin (M3)

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

Provide an optional, selectively-installable plugin (`tcs-patterns`) that ships curated domain
knowledge skills — so developers can load authoritative architectural and testing guidance
on demand without bloating their always-on context.

### Problem Statement

TCS workflow skills (tcs-workflow) enforce *how* to build software (spec → test → implement →
review). They say nothing about *what good looks like* in specific domains. A developer working
with DDD, hexagonal architecture, or mutation testing must either carry that knowledge personally
or search external docs. Neither is reliable.

1. **No domain guidance on demand.** A developer who types `/implement` gets orchestration but
   no opinion on whether their domain model follows DDD boundaries, their ports-and-adapters
   split is correct, or their mutations are being killed.
2. **tcs-workflow skills are context-heavy.** Adding domain rules to core workflow skills would
   bloat every session. Domain knowledge should be opt-in, not always-on.
3. **Domain patterns are scattered.** Good patterns exist in citypaul/.dotfiles, obra/superpowers,
   and community sources — but they require manual extraction and adaptation.

### Value Proposition

Install only the patterns you need. Each skill is independent, self-contained, and activates on
demand. No overhead when not relevant.

---

## Personas

### Persona A — The Architecture-Conscious Developer

Works on a TypeScript backend with DDD and hexagonal architecture. Wants to catch domain boundary
violations before code review. Uses `/ddd` and `/hexagonal` when designing new aggregates.

**Journey:** Writing a new Order aggregate → invokes `/ddd` for boundary checklist → invokes
`/hexagonal` to validate adapter separation → proceeds with implementation.

### Persona B — The Quality-Obsessed Tester

Runs a mutation testing suite and wants to know which mutants survive and why. Uses `/mutation-testing`
to plan a targeted kill campaign. Also uses `/test-design-reviewer` to audit new test files.

**Journey:** After `/implement` completes a payment module → invokes `/mutation-testing` to
design a strengthening pass → invokes `/test-design-reviewer` to evaluate test quality against
Farley's 8 properties.

### Persona C — The Platform Developer

Building a Node.js service or Python package. Wants stack-specific conventions applied consistently.
Uses `/node-service`, `/python-project`, or `/go-idiomatic` at project start.

**Journey:** Starting a new API service → invokes `/node-service` for project structure guidance
→ invokes `/api-design` for endpoint contract review → invokes `/twelve-factor` for deploy
compliance.

---

## Features

### Skill Inventory (17 skills)

All skills follow PICS format (Persona, Interface, Constraints, Workflow) with progressive disclosure
via `reference/` subdirectories.

#### Architecture Skills

| Skill | Source | Description |
|---|---|---|
| `ddd` | citypaul/.dotfiles | Domain-Driven Design: aggregates, bounded contexts, ubiquitous language, anti-corruption layers |
| `hexagonal` | citypaul/.dotfiles | Ports and adapters: domain core isolation, adapter separation, dependency inversion |
| `functional` | citypaul/.dotfiles | Functional and immutable programming patterns: pure functions, composition, side-effect isolation |
| `event-driven` | TCS-native | Event-driven architecture: event sourcing, CQRS, saga patterns, event schema design |

#### API & Type Skills

| Skill | Source | Description |
|---|---|---|
| `api-design` | TCS-native | REST/HTTP API design: resource naming, status codes, pagination, versioning, error envelopes |
| `typescript-strict` | citypaul/.dotfiles | TypeScript strict mode enforcement: no `any`, explicit return types, discriminated unions |

#### Testing Skills

| Skill | Source | Description |
|---|---|---|
| `testing` | citypaul/.dotfiles | General testing patterns: test pyramid, isolation, naming conventions, test data management |
| `mutation-testing` | citypaul/.dotfiles | Strengthen test suites via mutation: identify weak assertions, plan kill campaigns |
| `frontend-testing` | citypaul/.dotfiles | Frontend-specific testing: component isolation, async patterns, user-event simulation |
| `react-testing` | citypaul/.dotfiles | React component and hook testing: render, query, user-event, testing-library idioms |
| `test-design-reviewer` | Andrea Laforgia (via citypaul) | Evaluate tests against Dave Farley's 8 properties of good tests |
| `twelve-factor` | citypaul/.dotfiles | 12-factor app compliance: config, logs, processes, port binding, dev/prod parity |

#### Platform Skills

| Skill | Source | Description |
|---|---|---|
| `node-service` | TCS-native | Node.js service conventions: project structure, error handling, logging, shutdown |
| `python-project` | TCS-native | Python project patterns: pyproject.toml, type hints, ruff, venv, module layout |
| `go-idiomatic` | TCS-native | Go idioms: error handling, interfaces, goroutines, project layout, tooling |

#### Integration Skills

| Skill | Source | Description |
|---|---|---|
| `mcp-server` | TCS-native | MCP server development patterns: tool design, parameter schemas, error responses — **stub only, not production-ready** |
| `obsidian-plugin` | TCS-native | Obsidian plugin development: plugin API, CodeMirror, settings, manifest — **stub only, not production-ready** |

### Plugin Characteristics (Must-Haves)

**R1 — Selective Install**
Each skill is independently installable. Users who only want `ddd` and `typescript-strict` do
not install `obsidian-plugin`. The plugin ships all 17 but install.sh offers per-skill selection.

**R2 — Progressive Disclosure**
Each SKILL.md stays under ~25 KB. Deep content (checklists, anti-patterns, examples) lives in
`reference/` subdirectories loaded on demand.

**R3 — Source Attribution**
Skills derived from external sources attribute their origin in the SKILL.md file. See
`docs/concept/sources.md` for full attribution.

**R4 — Separate from Promotion**
`tcs-patterns` is a curated pre-built library, not a promotion target. Skills generated by
`tcs-helper:memory-promote` always land at `~/.claude/skills/<name>/SKILL.md` (global) or
`.claude/skills/<name>/SKILL.md` (repo-local) — never inside the tcs-patterns plugin directory.
Promoted skills follow the same PICS format as tcs-patterns skills, but live outside it.

**R5 — twelve-factor Dispatch**
The `twelve-factor` skill dispatches implementation work to `tcs-team:the-devops:build-platform`
for hands-on remediation (skill itself is advisory only).

---

## Acceptance Criteria

**R1 — Selective Install**
- AC-1: `install.sh` offers a tcs-patterns section where the user can select all, none, or
  specific skills.
- AC-2: Installing only `ddd` does not create directories for the other 16 skills.

**R2 — Progressive Disclosure**
- AC-1: Every SKILL.md is under 25 KB.
- AC-2: At least one `reference/` file exists per skill for deeper content.

**R3 — Source Attribution**
- AC-1: Skills from citypaul/.dotfiles include `Adapted from citypaul/.dotfiles` in the
  SKILL.md Persona section.
- AC-2: `test-design-reviewer` includes attribution to Andrea Laforgia.

**R4 — Separate from Promotion**
- AC-1: Skills promoted by `tcs-helper:memory-promote` do NOT appear in `plugins/tcs-patterns/`.
- AC-2: Promoted skills land at `~/.claude/skills/` (global) or `.claude/skills/` (repo-local).

**R5 — twelve-factor Dispatch**
- AC-1: When `/twelve-factor` detects a compliance gap, it offers to invoke
  `tcs-team:the-devops:build-platform` for remediation.

---

## Won't Build (M3)

- **Skill versioning** — skills ship at a single version; no per-skill semver.
- **Skill dependency graph** — no formal mechanism for one skill to require another.
- **Auto-detection** — skills are user-invoked; no automatic activation based on file detection.
- **tcs-team domain agents** — agent versions of domain skills are post-M3.
- **mcp-server / obsidian-plugin fully fleshed out** — both exist as stubs only; production-ready content is post-M3.

---

## Source Attribution

Full attribution table: `docs/concept/sources.md` — citypaul section.

Key sources:
- **citypaul/.dotfiles** (Paul Dobbins): 9 skills — ddd, hexagonal, functional, typescript-strict,
  mutation-testing, frontend-testing, react-testing, twelve-factor, testing
- **Andrea Laforgia** (andlaf-ak/claude-code-agents): test-design-reviewer, adapted via citypaul
- **TCS-native** (no external source): event-driven, api-design, go-idiomatic, node-service,
  python-project, mcp-server, obsidian-plugin
