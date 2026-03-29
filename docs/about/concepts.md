# Concepts

This document explains the design thinking behind The Custom Startup. It covers the core workflow, the TDD + SDD integration, the Memory Bank system, and the optional Satori context layer. Read this for the *why* — the reference docs cover the *how*.

---

## Vision

The Custom Startup started as a fork of [the-startup](https://github.com/rsmdt/the-startup) by Rudolf Schmidt. It has since grown into an opinionated, standalone framework — a curated collection of skills, agents, and features designed to make Claude Code sessions predictable, reviewable, and context-efficient.

The core philosophy:

- **Spec-driven, not ad-hoc.** Every feature starts with a specification. Implementation follows a plan.
- **SDD defines contracts. TDD verifies them.** No gap between design and code.
- **Evidence over claims.** No task is "done" until tests pass and output is verified.
- **Progressive disclosure.** Load only what's needed; avoid context bloat.
- **Humans decide, AI executes.** The framework keeps critical decisions with you and hands off implementation details to the agents.

---

## eXtended Design & Development (XDD)

XDD is the primary workflow. The name reflects that it *extends* traditional design (SDD) with test-driven discipline (TDD) — the X avoids the awkward "STDD" or "TSDD" that a literal combination would produce.

The workflow produces three linked documents before any code is written:

```
/xdd "Add user authentication"
  │
  ├─ xdd-prd  → requirements.md    (WHAT and WHY)
  ├─ xdd-sdd  → solution.md        (HOW and WHERE — contracts, interfaces, data models)
  └─ xdd-plan → plan/README.md     (WHEN and IN WHAT ORDER — TDD-structured tasks)
```

Each plan task is anchored to an SDD contract and structured as a TDD cycle (RED → GREEN → REFACTOR). This is the binding layer between design and implementation.

### The Validation Loop

The workflow does not end when implementation finishes. After building, you validate *back* against the spec:

```
Spec (PRD + SDD) → Implement → Validate back against spec → Fix drift → Ship
```

`/validate drift` compares what was built against what was specified, categorizing divergences as scope creep, missing items, contradictions, or extra work. This backward validation is what makes the spec actually useful — it closes the loop instead of leaving the spec as a write-once document that nobody checks.

---

## TDD + SDD Integration

SDD and TDD are not competing methodologies. They operate at different abstraction layers and are naturally complementary:

- **SDD defines contracts** — interface signatures, data models, behavior contracts (preconditions, postconditions, error conditions), integration points
- **TDD verifies contracts** — each SDD contract becomes a failing test that defines the implementation target

| SDD element | TDD target |
|---|---|
| Function signature | Input/output boundary test |
| Data model | Shape validation test |
| Behavior contract | Happy path + edge case tests |
| Error condition | Error handling test |
| Integration point | Contract/mock boundary test |

### The Iron Law

> **No production code without a failing test first.**

The `xdd-tdd` skill enforces this during implementation. The `tdd-guardian` agent (dispatched automatically by `/implement` before each task) blocks production code until a failing test exists. This is not optional or advisory — it is a hard gate.

| Rejected excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. The test takes 30 seconds. |
| "I'll test after" | Tests-after = "what does this do?" Tests-first = "what should this do?" |
| "Already manually tested" | Ad-hoc is not systematic. No record, can't re-run. |

### How It Flows

```
/xdd
  └─ xdd-plan produces TDD-structured tasks (RED / GREEN / REFACTOR per task)

/implement
  └─ for each task:
       tdd-guardian checks for test plan     ← hard gate
       RED:      write failing test anchored to SDD contract
       GREEN:    write minimal implementation
       REFACTOR: clean up, keep green
       /verify:  evidence gate (tests pass, output verified)
```

---

## Memory Bank

The Memory Bank is a layered, file-based knowledge system provided by the `tcs-helper` plugin. It captures session learnings and project knowledge across three scopes, using Claude Code's own file discovery rules for lazy loading — meaning knowledge is available when relevant without consuming context budget upfront.

### Three Scopes

| Scope | Location | What lives here |
|---|---|---|
| **Global** | `~/.claude/` | Personal preferences, cross-project conventions, always-used tool integrations |
| **Project** | `~/.claude/projects/<project>/` or a dedicated project directory | Project-wide conventions, cross-repo domain models, workflow decisions |
| **Repo** | `docs/ai/memory/` in the repo | Codebase-specific patterns, business rules, decisions, troubleshooting |

### Memory Categories

Within each scope, knowledge is organized by category:

| Category | Contains | Example |
|---|---|---|
| `general.md` | Conventions, patterns, code style | "All API responses use camelCase" |
| `tools.md` | Tooling and CI/CD specifics | "Deployment uses GitHub Actions with matrix builds" |
| `domain.md` | Business rules and data models | "Orders transition: draft → confirmed → shipped → delivered" |
| `decisions.md` | Architecture decision summaries | "JWT over sessions — see ADR-003" |
| `context.md` | Current focus areas and goals | "Migrating auth from v1 to v2 this sprint" |
| `troubleshooting.md` | Known issues and proven fixes | "PostgreSQL connection pool exhaustion — increase max to 20" |

### How It Works

1. **Capture** — Python hooks (installed by `/setup`) detect corrections and learnings during sessions, queuing them at `~/.claude/projects/<encoded>/learnings-queue.json`
2. **Route** — `/memory-add` processes the queue and routes each learning to the correct scope and category file
3. **Maintain** — `/memory-sync` keeps indices in sync, `/memory-cleanup` archives stale entries, `/memory-promote` elevates recurring patterns into reusable skills

### Context Minimization

The Memory Bank is not just a knowledge store — it is a context reduction strategy:

- **Lazy loading via file structure** — Claude Code loads `CLAUDE.md` files only from directories being actively worked in. Placing memory in `docs/ai/memory/` means it is loaded only when relevant.
- **Index-not-content pattern** — The `memory.md` index file stays under ~200 lines, pointing to category files rather than inlining content.
- **Promotion lifecycle** — Recurring domain patterns are promoted from memory files into reusable skills (via `/memory-promote`), replacing verbose memory entries with short pointers. This keeps memory files lean over time.

### Provisioning

Run `/setup` (tcs-helper) in any repo to provision the full Memory Bank structure:

```
docs/ai/
└── memory/
    ├── memory.md           ← index (~200 lines max)
    ├── general.md
    ├── tools.md
    ├── domain.md
    ├── decisions.md
    ├── context.md
    └── troubleshooting.md
```

The setup skill also generates scope-appropriate `CLAUDE.md` files and installs the capture hooks.

---

## Satori — MCP Gateway (Optional)

Satori is an MCP gateway server that sits between Claude Code and your MCP servers. It captures session activity (tool calls, file edits, git operations) into a local SQLite database and serves compact, relevant summaries back to Claude — reducing context window consumption while maintaining session continuity.

### What It Does

- **Context capture** — Records all MCP tool calls and their outputs to a per-project database
- **Context retrieval** — `satori_context` returns a compact session snapshot instead of Claude replaying full tool outputs
- **Server gateway** — Routes tool calls to downstream MCP servers, starting them on demand (hot/cold mode)
- **Knowledge base** — `satori_kb` provides index/search/fetch for project knowledge

### How It Relates to the Memory Bank

The Memory Bank and Satori operate at different time scales:

| | Memory Bank | Satori |
|---|---|---|
| **Time scale** | Medium to long-lived | Session-lived |
| **Storage** | Markdown files in git | SQLite database (local) |
| **Content** | Patterns, decisions, domain rules | Tool outputs, session events, task state |
| **Human-readable** | Yes — designed for human review | Primarily for AI consumption |
| **Survives** | Git history, branches, team handoffs | Session continuity, context compaction |

Together, they form a two-tier knowledge system: Satori handles the ephemeral session context that would otherwise bloat the context window, while the Memory Bank holds the durable knowledge that persists across sessions.

### Installation

The install script offers Satori setup during installation. It builds the submodule, registers the MCP server, and optionally installs context-capture hooks. Satori is not required — all core workflows function without it.

---

## What Was Planned vs. What Was Built

The original v2 concept documents (created March 2026) envisioned several features. Here is what shipped and what remains planned:

| Concept | Status | Notes |
|---|---|---|
| 4-plugin architecture (workflow, team, helper, patterns) | Shipped | All four plugins implemented and published |
| XDD workflow (PRD → SDD → Plan) | Shipped | 6 XDD skills, spec directory management |
| TDD integration (iron law, tdd-guardian) | Shipped | xdd-tdd skill + tdd-guardian agent in implement |
| Memory Bank (3-scope, category-based) | Shipped | 5 memory skills + setup + hooks |
| Satori MCP gateway | Shipped | Submodule, install script integration |
| Memory Bank + Satori deep integration | Planned | Satori auto-routing memory to Memory Bank categories |
| MCP security scanner in gateway | Planned | Concept: scan downstream servers before exposing tools |
| Kairn semantic memory integration | Planned | Graph-based project memory as optional Satori upgrade |
| YOLO mode documentation | Planned | Structured audit log for unattended sessions |

---

## Further Reading

- [Workflow reference](../getting-started/workflow.md) — step-by-step BUILD loop
- [XDD reference](../reference/xdd.md) — all 6 XDD skills in detail
- [Plugins reference](../reference/plugins.md) — what each plugin contains
- [Sources and attribution](sources.md) — where the ideas came from
- [The Custom Philosophy](the-custom-philosophy.md) — why this fork exists
