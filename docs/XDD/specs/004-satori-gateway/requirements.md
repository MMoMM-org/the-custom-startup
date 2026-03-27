---
spec: 004-satori-gateway
document: requirements
status: draft
---

# PRD — Satori MCP Gateway (M4)

## Summary

Satori is a standalone MCP server (`MMoMM-org/miyo-satori`) that acts as a context-reducing
gateway between Claude Code and any set of downstream MCP servers. TCS includes it as a git
submodule and activates it when the context-mode feature is enabled during install.

Satori is designed to work independently of TCS — it is general-purpose infrastructure that
TCS happens to use. The standalone nature is the reason for a separate repo.

---

## Problem Statement

- Claude Code's context window fills rapidly with raw tool outputs, logs, and state
- Multiple MCP servers require multiple Claude Code entries — no central management point
- MCP servers may receive or return sensitive data (keys, tokens, secrets) with no filtering layer
- Servers based on `npx` or similar are loaded regardless of whether they are needed
- Session context is lost on compaction or when starting a new session

---

## Goals

1. **Context reduction** — capture and compress tool output; serve only compact, relevant
   summaries to Claude (baseline: context-mode's reported 90–98% reduction)
2. **Gateway/registry** — single MCP entry point in Claude Code that fronts multiple downstream
   servers; tools are namespaced and routed transparently
3. **Handler architecture** — extensible plugin layer between Satori and each registered
   downstream server; default is passthrough, specific handlers can add pre/post processing
4. **Hot/cold loading** — downstream servers are only started when a) enabled in config and
   b) actually invoked; supports npx and Docker-based server runtimes
5. **Security — OUT direction** (primary) — ensure no secrets, API keys, or sensitive material
   are forwarded to downstream MCP servers
6. **Security — IN direction** (optional) — filter or annotate data coming back from downstream
   servers before it reaches Claude
7. **Session continuity** — generate a compact session guide on compaction; new sessions can
   restore task context without replaying full history

## Non-Goals

- Full reimplementation of lasso-mcp-gateway (use patterns, not the codebase)
- Full reimplementation of airis-mcp-gateway (same)
- Replacing Kairn — Kairn is an optional handler, not a Satori competitor
- Providing a full web UI for managing context history (CLI/config only for MVP)
- Hard dependency on TCS — Satori must be usable outside TCS

---

## Scope Boundaries

What Satori takes from reference projects (selective adoption):

| Source | What we take | What we skip |
|--------|-------------|--------------|
| context-mode | SQLite FTS5 DB, tool capture, session guide generation | Web viewer |
| lasso-mcp-gateway | Gateway/registry pattern, security scan model, blocked-server gate | Full reputation scoring, cloud policy sync |
| airis-mcp-gateway | Hot/cold server lifecycle, single-entrypoint tool routing | Full airis orchestration layer |
| Kairn/evolving-lite | Optional handler replacing built-in SQLite for semantic queries | Embedding infrastructure (Kairn supplies this) |

### Kairn as a Memory Backend

By default, Satori uses its internal SQLite FTS5 database for all context storage. When Kairn
is installed and registered as a handler, it takes over as the semantic query backend:

- **SQLite** remains responsible for: raw tool output capture, log storage, session events
- **Kairn handler** intercepts: session-boot context requests, semantic/graph queries
  ("how did I fix this before?"), project knowledge lookups
- The switch is automatic when Kairn is registered — no code change in Satori core required

This means M4 ships with the handler interface that makes Kairn pluggable. The Kairn handler
itself is a post-MVP deliverable.

---

## Requirements

### R1 — Context Server

| ID | Requirement | Priority |
|----|-------------|----------|
| R1.1 | Intercept and store tool call outputs in a per-project SQLite FTS5 database | Must |
| R1.2 | Return compact, task-relevant summaries instead of raw outputs | Must |
| R1.3 | Generate a ≤2KB session guide on PreCompact or session end | Must |
| R1.4 | Expose a `satori_context` tool; sub-commands handle restore, query, and status | Must |
| R1.5 | Isolate databases per project (keyed by repo root path) | Must |

### R2 — Gateway / Registry

| ID | Requirement | Priority |
|----|-------------|----------|
| R2.1 | Present as a single MCP server entry to Claude Code | Must |
| R2.2 | Maintain a registry of downstream MCP server definitions loaded from config | Must |
| R2.3 | Namespace downstream tools as `<server>_<tool>` to avoid collisions | Must |
| R2.4 | Route tool calls to the correct downstream server based on namespace | Must |
| R2.5 | Support g/p/r config: global (`~/.satori/config.toml`), project dir, repo root (`satori.toml`) | Must |
| R2.6 | Support auto-registration of repo-level `.mcp.json` (enabled/disabled per config) | Should |

### R3 — Handler / Plugin Architecture

| ID | Requirement | Priority |
|----|-------------|----------|
| R3.1 | Define a handler interface that sits between Satori core and each downstream server | Must |
| R3.2 | Default handler: transparent passthrough (no transformation) | Must |
| R3.3 | Handlers can intercept tool call inputs (before forwarding) and outputs (before returning) | Must |
| R3.4 | Handlers are registered per downstream server in config | Must |
| R3.5 | Handler registration API must allow third-party handlers without forking Satori | Should |
| R3.6 | Ship a Kairn handler (post-MVP) that routes semantic queries to Kairn and replaces built-in SQLite for session-boot context | Future |

### R4 — Hot/Cold Loading

| ID | Requirement | Priority |
|----|-------------|----------|
| R4.1 | Downstream servers are only started when enabled in config AND a tool call is received | Must |
| R4.2 | Servers can be disabled globally or per-project without removing their config | Must |
| R4.3 | Satori manages server lifecycle for npx-based and Docker-based runtimes; others may need external start | Must |
| R4.4 | Server state (running/stopped/error) is accessible via a management tool | Should |

### R5 — Security

| ID | Requirement | Priority |
|----|-------------|----------|
| R5.1 | Scan tool call inputs for secrets patterns (API keys, tokens, credentials) before forwarding OUT | Must |
| R5.2 | Block forwarding when secrets are detected; log the occurrence | Must |
| R5.3 | Scan tool descriptions and server configs on startup for risky patterns (exfiltrate, delete, hidden instructions) | Should |
| R5.4 | Server status after scan: `passed / blocked / skipped / pending` | Should |
| R5.5 | Tools from `blocked` servers are not registered — invisible to Claude | Should |
| R5.6 | Write audit log at `~/.satori/scanner.log` with reasons | Should |
| R5.7 | IN direction: optionally annotate or filter outputs from downstream before returning to Claude | May |

### R6 — TCS Integration (M4 scope only)

M4 delivers the submodule wiring. All skill-level integration (routing table, memory-add,
skill detection) is deferred to `005-memory-mcp` (M5).

| ID | Requirement | Priority |
|----|-------------|----------|
| R6.1 | TCS includes `miyo-satori` as a git submodule | Must |

---

## Architecture Overview

```
Claude Code
    │
    │ (single MCP entry: "satori")
    ▼
┌─────────────────────────────────────────────┐
│  Satori                                     │
│  ┌─────────────┐  ┌──────────────────────┐ │
│  │ Context     │  │ Gateway / Registry   │ │
│  │ Server      │  │ ┌──────────────────┐ │ │
│  │ (SQLite     │  │ │ Handler Registry │ │ │
│  │  FTS5)      │  │ └──────────────────┘ │ │
│  │             │  │   ↓ route + handle   │ │
│  │ satori_     │  └──────────────────────┘ │
│  │ context     │          │                │
│  └─────────────┘          │                │
└───────────────────────────┼────────────────┘
                            │
          ┌─────────────────┼──────────────┐
          ▼                 ▼              ▼
   [passthrough]       [kairn]        [custom]
   downstream A        handler        handler
        │              (future)
   npx / docker
   server B
   (hot/cold)
```

---

## Configuration Model

Config uses TOML. Location follows g/p/r resolution:
- **Global**: `~/.satori/config.toml`
- **Project**: `<project-dir>/satori.toml`
- **Repo**: `satori.toml` at repo root (not hidden, version-controllable)

Server-specific settings (env vars, paths, ports) live in the Satori config, not in `.mcp.json`.
The `.mcp.json` in a repo can be auto-detected for server discovery only; Satori's own config
is authoritative for how each server is started and configured.

```toml
# satori.toml (repo root)

[gateway]
auto_register_mcp_json = true   # detect .mcp.json in repo root for discovery

[[servers]]
name = "filesystem"
runtime = "npx"
command = "@modelcontextprotocol/server-filesystem"
args = ["/path/to/project"]
env = {}
handler = "passthrough"
enabled = true

[[servers]]
name = "github"
runtime = "docker"
image = "ghcr.io/github/github-mcp-server"
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "${GITHUB_TOKEN}" }
handler = "passthrough"
enabled = true

# future — post-MVP
[[servers]]
name = "kairn"
runtime = "npx"
command = "@primeline/kairn-mcp"
handler = "kairn"
enabled = false
```

---

## Discovery (Open Question for SDD)

Which TCS workflow skills need to know whether Satori is running?

Memory-skill integration is out of scope for M4 (→ M5). The question for M4 is whether
any non-memory TCS skills benefit from Satori awareness — e.g., `analyze`, `debug`, `implement`
using `satori_context` for session state instead of re-reading files.

Candidate approaches:
- **Tool-availability check**: skills attempt `satori_context` at session start; absent → fall back
- **CLAUDE.md flag**: `tcs-helper:setup` writes `context_server: satori`; skills read the flag
- **Both**: flag for fast path, tool check as runtime fallback

Decision deferred to SDD.

---

## Auto-Registration (Open Question for SDD)

When a repo contains `.mcp.json`, Satori can detect the file and offer those servers for
registration. Benefit: zero manual config for repos that already have MCP config.
Risk: Claude Code may only read MCP config on startup — auto-registered servers may not be
available until next launch. Needs testing before committing to the design.

Decision deferred to SDD after testing Claude Code MCP reload behavior.

---

## TCS Roadmap Position

```
M2 (Memory System, file-only) ✅
  └─ M4 (Satori — this spec)
       └─ M5 (Memory + MCP Integration)
```

Satori is a dependency for M5. M5 adds the routing-table integration and skill-level
detection that connects file-based memory with Satori context storage.

---

## Reference

- `docs/concept/v2/context-mode-MCP-Server.md` — Perplexity design analysis (gateway, security, Kairn)
- `docs/concept/v2/TCS v2 Memory & Context Layout Spec.md §5` — Memory/context routing table
- `docs/concept/v2/sources v2.md` — context-mode, lasso, airis, Kairn attribution
- Implementation repo: `https://github.com/MMoMM-org/miyo-satori`
