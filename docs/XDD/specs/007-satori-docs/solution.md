---
spec: 007-satori-docs
document: solution
status: completed
---

# SDD — Satori Documentation

## Summary

This document describes HOW the satori documentation will be built: file layout, content model per document, source-of-truth rules, and cross-document link map. No code is written — the deliverables are Markdown files in `modules/satori/docs/`.

---

## Architecture Decisions

### ADR-1: 5-file IA in `modules/satori/docs/`

**Choice:** Create a `docs/` directory in the satori submodule with 5 separate files.

**Rationale:** Each file has a distinct purpose and audience. A single monolithic file would be hard to navigate; a 2-file split (guide + reference) blurs the line between conceptual content and API reference.

**Trade-offs:** More files to maintain, but each file stays focused and can be linked to directly.

**Files:**
```
modules/satori/docs/
├── getting-started.md    ← setup and first use (F1)
├── configuration.md      ← satori.toml full reference (F2)
├── tools.md              ← all tools API reference (F3, F4-bash)
├── concepts.md           ← architecture and mental model (F4-concepts)
└── hooks.md              ← Claude Code hooks setup (F5)
```

---

### ADR-2: Zod schemas are the source of truth for all tool parameters

**Choice:** Before writing any tool documentation, read the Zod input schema from `src/tools/*.ts`. Never recall parameters from memory.

**Rationale:** The README is already outdated (`satori_kb` missing). Zod schemas are the authoritative contract — they match exactly what the MCP server accepts at runtime.

**Files to read:**
| Tool | Source file |
|------|-------------|
| `satori_context` | `src/tools/satori-context.ts` |
| `satori_manage` | `src/tools/satori-manage.ts` |
| `satori_find` | `src/tools/satori-find.ts` |
| `satori_schema` | `src/tools/satori-schema.ts` |
| `satori_exec` | `src/tools/satori-exec.ts` |
| `satori_kb` | `src/tools/satori-kb.ts` |
| `bash` builtin | `src/execution/builtin-server.ts` + `src/execution/runtime.ts` |

---

### ADR-3: README updated in-place (not rewritten)

**Choice:** Update the existing `README.md` minimally: correct tool count (5 → 7 tools: 6 satori_* + bash builtin), add `satori_kb` to the tools table, add a `## Documentation` section linking to `docs/`.

**Rationale:** README is the repo landing page and first touchpoint. It should remain a quick-reference, not a full guide. All depth lives in `docs/`.

**What changes in README:**
1. Tools table: add `satori_kb` row and `bash` builtin note
2. Add `## Documentation` section with links to all 5 docs files
3. Correct the usage example if it references missing tools

---

### ADR-4: `bash` builtin fully documented; Kairn = planned

**Choice:** Document `satori_exec("bash", ...)` fully in `tools.md`. Kairn handler gets a single paragraph in `concepts.md` under `## Planned Extensions`.

**Rationale:** The `bash` builtin server (`BuiltinServer` in `src/execution/builtin-server.ts`) is fully implemented with 3 tools (`run`, `run_file`, `batch`) and intent-driven mode. It bypasses `LifecycleManager` — always available, no `satori.toml` entry needed. Kairn integration is not yet implemented.

---

## Content Model Per File

### `getting-started.md`

**Purpose:** Get a new user from zero to first successful `satori_exec` call.

**Sections:**
1. **Prerequisites** — Node.js ≥18, npm, TypeScript build step
2. **Build** — `npm install && npm run build`
3. **Configure: `satori.toml`** — copy example, add first downstream server; show minimal working config with one `npx` server
4. **Register with Claude Code** — exact JSON to add to `~/.claude/settings.json` (absolute path, why it must be absolute)
5. **Verify** — how to confirm satori is running: call `satori_manage(list)` or `satori_find("anything")`
6. **First tool call** — complete example: `satori_find` → `satori_schema` → `satori_exec`
7. **TCS-integrated path** — what `install.sh` configures automatically; what the user may still customize

**Key constraints:**
- Absolute path requirement for MCP config must be called out explicitly (common error)
- TCS path is a subsection, not the primary flow — standalone first

---

### `configuration.md`

**Purpose:** Complete reference for every `satori.toml` field.

**Sections:**
1. **Config resolution order** — global (`~/.satori/config.toml`) → project → repo (`satori.toml`); merge rules; `[[servers]]` wins by name
2. **`project_dir`** — what it is, when to set it (multi-repo projects), how `satori_manage(set_project_dir)` writes it
3. **`[gateway]`** — `auto_register_mcp_json` (bool, default false); what happens when enabled; `.mcp.json` → `.mcp.satori-json` rename
4. **`[context]`** — `db_path`, `session_guide_max_bytes` (default 2048), `retain_days` (default 30)
5. **`[lifecycle]`** — `npx_startup_timeout_ms` (default 30000)
6. **`[security]`** — `startup_scan`, `runtime_scan`, `return_scan`, `audit_log`; scan statuses (`passed / blocked / skipped / pending`)
7. **`[[servers]]`** — per-runtime fields:

| Runtime | Required fields | Optional fields |
|---------|----------------|-----------------|
| `npx` | `name`, `runtime`, `command` | `args`, `env`, `handler`, `enabled` |
| `docker` | `name`, `runtime`, `image` | `args`, `env`, `handler`, `enabled` |
| `external` | `name`, `runtime`, `host`, `port` | `transport`, `handler`, `enabled` |

**Key constraints:**
- Source: `src/config/schema.ts` + `satori.toml.example` (read both before writing)
- Show env var interpolation: `"${GITHUB_TOKEN}"` syntax
- Show at least one complete example per runtime type

---

### `tools.md`

**Purpose:** Full API reference for all tools — inputs, outputs, sub-commands, examples.

**Structure:** One H2 section per tool, sub-commands as H3. Read Zod schemas from source before writing each section.

#### Tool sections:

**`satori_context`** — sub-commands: `restore`, `query`, `status`, `flush`
- `restore`: returns ≤2KB XML session snapshot; marks consumed; `session_id` optional
- `query`: FTS search over captured tool outputs; `q` (string), `limit` (int); returns ranked results
- `status`: current DB stats (capture count, last event, DB path)
- `flush`: force-write session guide before natural compaction

**`satori_manage`** — sub-commands: `list`, `add`, `remove`, `enable`, `disable`, `state`, `scan`, `reload`, `set_project_dir`
- `list`: all registered servers with runtime, handler, enabled status
- `add`: register a new server at runtime; `name`, `runtime`, `command`/`image`, optional `args`, `env`, `handler`, `scope`
- `remove`: remove server by name from config; `name`, `scope`
- `enable` / `disable`: toggle server; `name`, `scope`
- `state`: lifecycle state of a server (running / stopped / error / blocked); `name`
- `scan`: re-run security scan on all or named server; `name` optional
- `reload`: reload config from disk without restarting satori
- `set_project_dir`: write `project_dir` to repo-level `satori.toml`; `dir`

**`satori_find`** — search tool catalog across all registered servers
- `query` (string): keyword search over tool names and descriptions
- `server` (optional): restrict to a specific server
- Returns: array of `{ server, tool, description, state }`

**`satori_schema`** — get input schema for a specific tool
- `server` (string): server name
- `tool` (string): tool name
- Returns: `{ name, description, inputSchema }` (JSON Schema)

**`satori_exec`** — route a tool call to a downstream server
- `server` (string): server name (or `"bash"` for builtin)
- `tool` (string): tool name
- `args` (object, optional): tool arguments
- `session_id` (optional): for context capture scoping
- Starts server on first call if not already running

**`satori_kb`** — local knowledge base with BM25+RRF search
- `index`: chunk and index markdown content; `content` (string), `title` (optional), `type` (`prose`|`code`), `url` (optional)
- `search`: BM25+RRF search; `query` (string), `contentType` (optional), `limit` (optional), `session_id` (optional)
- `fetch_and_index`: fetch a URL and index its content; `url` (string)

**`bash` builtin (via `satori_exec("bash", ...)`)**
- Not discoverable via `satori_find` — bypasses LifecycleManager; always available; no `satori.toml` entry needed
- `run`: execute code; `language` (required: `shell`, `python`, `javascript`, `typescript`, `ruby`, `go`, `rust`, `php`, `perl`, `r`, `elixir`), `code` (string), `timeout` (ms), `background` (bool), `intent` (string), `env` (object)
  - **Intent-driven mode**: when `intent` is set and stdout > 5000 bytes → output is indexed to KnowledgeDB and semantic search results are returned instead of raw stdout
- `run_file`: execute a file; `path`, `language`, optional `code` (prepend), `timeout`
- `batch`: run multiple shell commands; `commands` (array of `{label, command}`), `queries` (array of strings for intent-driven retrieval), `timeout`

---

### `concepts.md`

**Purpose:** Mental model — how the pieces fit together and why.

**Sections:**
1. **What is a gateway?** — one MCP entry in Claude Code fronts N downstream servers; tools namespaced by server name
2. **Three layers** — gateway routing, context DB, knowledge base — what each does and when to use which
3. **Hot/cold loading** — servers start only when first called; `enabled = false` = never starts; security scan blocks before first start
4. **Security scan** — startup scan (server configs) vs runtime scan (tool arguments); what patterns trigger a block; `blocked` server = invisible to Claude
5. **Intent-driven mode** — how `bash:run` + `satori_exec` with `intent` parameter auto-compress large outputs via KnowledgeDB
6. **Session continuity** — PreCompact hook triggers snapshot; `satori_context(restore)` at session start; 2KB XML format
7. **Architecture diagram** (ASCII):

```
Claude Code
    │
    │  single MCP entry: "satori"
    ▼
┌─────────────────────────────────────────────────┐
│  Satori                                         │
│                                                 │
│  ┌────────────────┐  ┌──────────────────────┐   │
│  │ Context Server │  │ Gateway / Registry   │   │
│  │ (SQLite FTS5)  │  │  ┌────────────────┐  │   │
│  │                │  │  │ Tool Catalog   │  │   │
│  │ satori_context │  │  └────────────────┘  │   │
│  │ satori_kb      │  │  route + handle      │   │
│  └────────────────┘  └──────────────────────┘   │
│                                │                │
│  ┌─────────────────────────┐   │                │
│  │ Builtin Server ("bash") │   │                │
│  │ run / run_file / batch  │   │                │
│  └─────────────────────────┘   │                │
└───────────────────────────────┼────────────────┘
                                │
              ┌─────────────────┼────────────┐
              ▼                 ▼            ▼
       [npx server A]   [docker server B]  [external C]
         (hot/cold)       (hot/cold)
```

8. **Planned Extensions** — Kairn handler (semantic memory backend replacing SQLite for session-boot queries); brief description, no implementation details

---

### `hooks.md`

**Purpose:** Step-by-step hooks setup for full satori functionality.

**Sections:**
1. **Why hooks?** — satori passively captures tool output via PostToolUse; PreCompact triggers session guide generation; without hooks, context DB stays empty
2. **Available hooks** — what `hooks/hooks.json` contains:
   - `PreCompact` → `satori_context(flush)` — writes session guide before compaction
   - `PostToolUse` — captures tool output to context DB
3. **Setup** — exact JSON to add to `.claude/settings.json` (copy from `hooks/hooks.json`); show full settings.json structure
4. **Verify** — how to confirm hooks are active: make a tool call, then `satori_context(status)` → capture count > 0

**Key constraint:** Read `modules/satori/hooks/hooks.json` before writing this section — actual hook commands must be verbatim.

---

## README Update Model

The existing `README.md` gets these changes only:

1. **Tools table:** Add `satori_kb` row; add note about `bash` builtin accessed via `satori_exec("bash", ...)`
2. **`## Documentation` section** (new, after Quick Start):
   ```markdown
   ## Documentation

   → [Getting Started](docs/getting-started.md) — setup and first use
   → [Configuration](docs/configuration.md) — satori.toml reference
   → [Tools](docs/tools.md) — full API reference
   → [Concepts](docs/concepts.md) — architecture and mental model
   → [Hooks](docs/hooks.md) — Claude Code hooks setup
   ```
3. **Usage example:** Verify it still uses valid tool names (no changes to code blocks unless broken)

---

## Cross-Document Link Map

| Source | Links to | Reason |
|--------|----------|--------|
| `getting-started.md` | `configuration.md` | "See configuration reference for all fields" |
| `getting-started.md` | `hooks.md` | "Set up hooks for full functionality" |
| `getting-started.md` | `tools.md` | "See tools reference for all available tools" |
| `tools.md` (`satori_exec`) | `configuration.md` (`[[servers]]`) | "Servers must be configured before use" |
| `tools.md` (`satori_context`) | `hooks.md` | "Requires PreCompact hook to populate" |
| `tools.md` (`bash` builtin) | `tools.md` (`satori_kb`) | "Intent-driven mode uses satori_kb internally" |
| `concepts.md` | `tools.md` | "See tools reference" |
| `concepts.md` | `configuration.md` | "See security configuration" |
| `README.md` | all 5 docs files | Documentation section |

---

## Implementation Gotchas

- **Read `hooks/hooks.json` before writing `hooks.md`** — do not assume hook command format
- **Read `src/config/schema.ts` before writing `configuration.md`** — all fields are defined there; `satori.toml.example` may not list every field
- **`bash` builtin is not in `satori_find` catalog** — document this explicitly in `tools.md` to avoid confusion ("why doesn't `satori_find('run')` return results?")
- **`satori_kb` search returns `ThrottleBlock` when rate-limited** — document this as a possible return shape in the API reference
- **Intent-driven threshold is exactly 5000 bytes** — document as `> 5000 bytes stdout`

---

## Quality Requirements

| Criterion | Check |
|-----------|-------|
| All 6 satori_* tools documented | Count sections in tools.md |
| bash builtin fully documented with all 3 tools and intent-driven mode | Manual review |
| All satori.toml fields documented | Compare against `src/config/schema.ts` |
| No `[NEEDS CLARIFICATION]` markers | Grep |
| README updated with satori_kb and docs/ links | Grep for `satori_kb` and `docs/getting-started` |
| All cross-document links resolve | Check file existence |

---

## Acceptance Criteria Mapping

| PRD AC | SDD Component | How addressed |
|--------|---------------|---------------|
| AC-1: All 6 tools + all sub-commands | `tools.md` | One section per tool, sub-commands as H3 |
| AC-2: All satori.toml fields | `configuration.md` | Read `src/config/schema.ts`; table per section |
| AC-3: Getting started guide | `getting-started.md` | Journey 1 (standalone) as primary flow |
| AC-4: README updated with 6 tools + docs links | README update | In-place: add satori_kb, Documentation section |
| AC-5: No undated post-MVP content | `concepts.md` | Kairn in `## Planned Extensions` only |
| AC-6: Three layers + hot/cold in concepts.md | `concepts.md` | Sections 2 and 3 |
| AC-7: hooks.md with exact JSON | `hooks.md` | Read `hooks/hooks.json` before writing |
