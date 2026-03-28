---
spec: 007-satori-docs
document: requirements
status: completed
---

# PRD — Satori Documentation

## Summary

Satori (`MMoMM-org/miyo-satori`) is a standalone MCP gateway server that sits between Claude Code and any set of downstream MCP servers. It provides context compression, lazy server loading, tool discovery, a knowledge base, and security scanning in a single entry point.

This spec covers the **documentation** for satori — not the implementation. The documentation lives in `modules/satori/docs/` (the submodule repo) and serves two audiences: users setting up satori standalone, and TCS users encountering it through the install wizard.

---

## Problem Statement

- The current `README.md` is minimal (60 lines) and incomplete: `satori_kb` is missing, sub-commands are not documented, configuration options are not explained
- No user guide exists for the most common flows: setup → first tool call, session restore after compaction, security configuration
- No API reference exists: each tool has sub-commands and optional parameters that are only discoverable by reading TypeScript source
- The docs live in the submodule repo (`miyo-satori`) — TCS users installing via `modules/satori` need authoritative docs in the same location

---

## Goals

1. **User guide** — step-by-step for the two primary setup paths (standalone, TCS-integrated)
2. **API reference** — all 6 tools fully documented with sub-commands, parameters, return values, and examples
3. **Configuration reference** — every `satori.toml` field explained with type, default, and example
4. **Conceptual overview** — what satori is, how the gateway/context/kb layers relate, when to use which tool

---

## Non-Goals

- Documenting the handler interface (future/post-MVP)
- Documenting the Kairn integration (post-MVP)
- Documenting the shell pseudo-server (post-MVP)
- Tutorials for specific downstream servers (filesystem, GitHub MCP, etc.)

---

## Personas

### Persona 1 — Standalone User (primary)

A developer using Claude Code who wants to consolidate their MCP servers behind a single entry point and reduce context window pressure. They are familiar with MCP and Claude Code settings but have not used a gateway before.

**Goals:** Get satori running quickly; understand what each tool does; configure security without breaking their workflow.

**Pain Points:** The current README tells them to "add satori to your MCP config" but doesn't show what a complete working config looks like. They don't know that `satori_kb` exists or what `satori_context(flush)` does.

### Persona 2 — TCS User (secondary)

A developer using TCS who enabled "context mode" during `install.sh`. Satori was configured automatically. They want to understand what is running, how to add downstream servers, and how to use `satori_context` to resume after a compaction.

**Goals:** Understand what satori does in their TCS setup; learn the context restore flow; optionally configure additional downstream servers.

**Pain Points:** No documentation explains the TCS integration path. `satori_manage(set_project_dir)` is mentioned in `satori.toml.example` but not explained.

---

## Primary User Journeys

### Journey 1 — Standalone Setup

1. Clone or install satori → `npm install && npm run build`
2. Copy `satori.toml.example` → `satori.toml`, edit to add first downstream server
3. Add satori entry to `~/.claude/settings.json` (MCP config)
4. Start Claude Code → verify `satori_find("anything")` returns results
5. Make first tool call via `satori_exec`

### Journey 2 — Session Restore After Compaction

1. Session compacts → hook fires → `satori_context` snapshot is written
2. New session starts → user (or skill) calls `satori_context(restore)`
3. Snapshot returned → context restored without re-reading files

### Journey 3 — Tool Discovery

1. User doesn't know what tools a downstream server offers
2. `satori_find("read file")` → returns `filesystem:read_file`
3. `satori_schema("filesystem", "read_file")` → returns required params
4. `satori_exec("filesystem", "read_file", { "path": "..." })` → executes

### Journey 4 — Knowledge Base

1. User wants to index a project README or URL for later retrieval
2. `satori_kb(index, content: "...")` → chunks and indexes
3. `satori_kb(search, query: "how to configure X")` → returns relevant snippets

---

## Features

### F1 — Getting Started Guide

A step-by-step guide covering both setup paths (standalone and TCS-integrated).

**Must have:**
- Build prerequisites (`node`, `npm`, TypeScript compilation)
- Minimal working `satori.toml` with one downstream server
- Complete MCP config entry (absolute path requirement explained)
- Verification step: how to confirm satori is running
- Pointer to hooks setup

**Should have:**
- TCS-integrated path: what `install.sh` configures automatically, what the user may still want to customize

### F2 — Configuration Reference

Complete documentation of every `satori.toml` field.

**Must have:**
- All sections: `[gateway]`, `[context]`, `[lifecycle]`, `[security]`, `[[servers]]`
- Per-field: name, type, default value, description, example
- `[[servers]]` runtime types: `npx`, `docker`, `external` — each with required fields
- g/p/r config resolution order explained (global → project → repo)
- `project_dir` explained: when to use, how `satori_manage(set_project_dir)` sets it

**Should have:**
- Environment variable interpolation in server configs (e.g., `"${GITHUB_TOKEN}"`)

### F3 — Tool API Reference

Full reference for all 6 tools.

**Must have for each tool:**
- Description (what it does, when to use it)
- Sub-commands (where applicable) with parameters and return shape
- At least one usage example per sub-command
- Error cases (what goes wrong and how to recognize it)

**Tools to document:**

| Tool | Sub-commands |
|------|-------------|
| `satori_context` | `restore`, `query`, `status`, `flush` |
| `satori_manage` | `list`, `add`, `remove`, `enable`, `disable`, `state`, `scan`, `reload`, `set_project_dir` |
| `satori_find` | (query + optional server filter) |
| `satori_schema` | (server + tool) |
| `satori_exec` | (server + tool + args) |
| `satori_kb` | `index`, `search`, `fetch_and_index` |

**Note:** The existing README lists only 5 tools — `satori_kb` is missing and must be added.

### F4 — Conceptual Overview

A brief explanation of satori's architecture for users who want to understand the pieces before diving in.

**Must have:**
- What a gateway does (vs. direct MCP registration)
- The three layers: gateway routing, context DB, knowledge base
- Hot/cold loading explained (servers start only when first called)
- Security scan flow: what is scanned, when, what happens on a block

**Should have:**
- ASCII architecture diagram (reuse and update the one from the implementation PRD)

### F5 — Hooks Setup

How to configure Claude Code hooks for full satori functionality.

**Must have:**
- Which hooks satori ships (`hooks/hooks.json`)
- What each hook does: PreCompact (session guide), PostToolUse (tool capture)
- How to add them to `.claude/settings.json`

---

## Information Architecture

Documentation lives at `modules/satori/docs/`:

```
modules/satori/docs/
├── getting-started.md    ← F1: setup guide (both paths)
├── configuration.md      ← F2: satori.toml full reference
├── tools.md              ← F3: all 6 tools API reference
├── concepts.md           ← F4: architecture and mental model
└── hooks.md              ← F5: hooks setup
```

The existing `README.md` at repo root is updated to link to `docs/` and correct the tool count (5 → 6).

---

## Acceptance Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| AC-1 | All 6 tools documented with all sub-commands | Count: `satori_context` (4 sub-cmds), `satori_manage` (10 sub-cmds), `satori_kb` (3 sub-cmds), `satori_find`, `satori_schema`, `satori_exec` |
| AC-2 | Every `satori.toml` field documented with type and default | Check against `satori.toml.example` — all fields covered |
| AC-3 | Getting started guide leads a new user from clone to first `satori_exec` call | Manual walkthrough |
| AC-4 | README.md updated: 6 tools listed, links to docs/ | `grep "satori_kb" README.md` → match |
| AC-5 | No references to post-MVP features (Kairn handler, shell pseudo-server) without clear "future" label | Scan docs for Kairn, shell |
| AC-6 | `concepts.md` explains the three layers and hot/cold loading | Manual review |
| AC-7 | `hooks.md` shows the exact JSON structure to add to `.claude/settings.json` | Manual review |

---

## Out of Scope

- Interactive demos or web-based documentation
- Changelogs or version history in the docs themselves
- Documentation for the programmatic handler API (TypeScript interface)
- Coverage of post-MVP features as full documentation (brief mention with "planned" label only)
