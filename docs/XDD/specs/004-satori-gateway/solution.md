---
spec: 004-satori-gateway
document: solution
status: completed
---

# SDD — Satori MCP Gateway (M4)

## Technology Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Runtime | Node.js 20 LTS | MCP TypeScript SDK is primary; context-mode and lasso reference implementations are Node |
| Language | TypeScript (strict) | Type safety for handler interface contract; SDK types |
| MCP SDK | `@modelcontextprotocol/sdk` | Official SDK, stdio transport |
| DB | `better-sqlite3` | Synchronous SQLite API, FTS5 support, no async complexity |
| Config | `smol-toml` | Lightweight TOML parser, zero deps |
| Process mgmt | Node `child_process` | npx server lifecycle; Docker via `dockerode` |
| Secret scan | Regex patterns (built-in) | No external deps for core security |

---

## Repository Structure

```
miyo-satori/
├── src/
│   ├── index.ts                  # Entry: MCP server bootstrap, tool registration
│   ├── db-base.ts                # SQLiteBase — opens DB, WAL pragmas, schema migration (schema embedded)
│   ├── context/
│   │   ├── session-db.ts         # Session event store (session_events, session_meta, session_resume)
│   │   ├── content-db.ts         # Content capture store (captures + FTS5)
│   │   ├── snapshot.ts           # Build XML resume snapshot from session events (pure functions)
│   │   ├── extract.ts            # Map tool hook payloads → SessionEvent objects
│   │   └── summarizer.ts         # Compress raw tool output → compact summary (content store)
│   ├── gateway/
│   │   ├── registry.ts           # Downstream server registry (load, validate, lookup)
│   │   ├── catalog.ts            # Tool catalog cache (satori_find + satori_schema data source)
│   │   └── router.ts             # satori_exec routing: server lookup → handler → downstream
│   ├── handlers/
│   │   ├── interface.ts          # SatoriHandler interface (the extension contract)
│   │   ├── passthrough.ts        # Default no-op handler
│   │   └── registry.ts           # Handler lookup by name
│   ├── lifecycle/
│   │   ├── manager.ts            # Server start/stop, hot/cold state machine
│   │   ├── runtimes/
│   │   │   ├── npx.ts            # npx runtime (spawn, health check, shutdown)
│   │   │   └── docker.ts         # Docker runtime (pull, run, stop, rm)
│   │   └── state.ts              # ServerState: stopped | starting | running | error | blocked
│   ├── security/
│   │   ├── scanner.ts            # Startup scan + runtime OUT scan
│   │   ├── patterns.ts           # Secret regex patterns + risky tool description patterns
│   │   └── audit-log.ts          # Append-only audit log writer
│   ├── config/
│   │   ├── loader.ts             # TOML load + g/p/r merge
│   │   ├── schema.ts             # Config type definitions (SatoriConfig, ServerConfig, etc.)
│   │   └── auto-register.ts      # .mcp.json import → .mcp.satori-json rename
│   └── tools/
│       ├── satori-context.ts     # satori_context tool (sub-commands: restore, query, status)
│       ├── satori-manage.ts      # satori_manage tool (server state, enable/disable)
│       ├── satori-find.ts        # satori_find tool (search tools across all servers)
│       ├── satori-schema.ts      # satori_schema tool (get full input schema for a tool)
│       └── satori-exec.ts        # satori_exec tool (single entry point for all downstream calls)
├── satori.toml.example           # Annotated config template
├── package.json
├── tsconfig.json
└── README.md
```

---

## Handler Interface

The handler interface is the primary extension point. Every downstream server has exactly one handler; the default is `passthrough`.

```typescript
// src/handlers/interface.ts

export interface ToolCallRequest {
  serverName: string;
  toolName: string;        // bare name, without namespace prefix
  arguments: Record<string, unknown>;
}

export interface ToolCallResponse {
  content: unknown;
  isError?: boolean;
}

export interface BlockedResult {
  blocked: true;
  reason: string;
}

export interface SatoriHandler {
  /** Unique name — matches handler field in satori.toml */
  readonly name: string;

  /** Called once when server config is loaded; validate handler-specific config here */
  onRegister(config: ServerConfig): Promise<void>;

  /**
   * Called before forwarding to downstream.
   * Return modified request to continue, or BlockedResult to abort.
   */
  beforeCall(request: ToolCallRequest): Promise<ToolCallRequest | BlockedResult>;

  /**
   * Called after receiving response from downstream.
   * May enrich, filter, or annotate the response.
   */
  afterCall(
    request: ToolCallRequest,
    response: ToolCallResponse,
  ): Promise<ToolCallResponse>;
}
```

Third-party handlers implement this interface and are loaded by name from a configured path:

```toml
# satori.toml
[[handlers]]
name = "my-handler"
module = "./handlers/my-handler.js"   # relative to satori.toml location
```

---

## Config Schema

### Resolution Order (g/p/r)

1. `~/.satori/config.toml` — global defaults
2. `<project-dir>/satori.toml` — project overrides
3. `<repo-root>/satori.toml` — repo overrides

Later layers override earlier layers. Array fields (`[[servers]]`) are merged by `name`;
repo-level entries win over global entries with the same name.

### Full Schema

```toml
# satori.toml — annotated full schema

[gateway]
# Auto-detect .mcp.json at repo root; import servers and rename file
auto_register_mcp_json = false

[context]
# SQLite DB path, relative to repo root (default: .satori/db.sqlite)
db_path = ".satori/db.sqlite"
# Session guide size cap (bytes)
session_guide_max_bytes = 2048
# Retain raw captures for N days before pruning
retain_days = 30

[lifecycle]
# Timeout (ms) waiting for an npx server to pass its tools/list health check (default: 30000)
npx_startup_timeout_ms = 30000

[security]
# Scan tool descriptions and configs at startup
startup_scan = true
# Scan tool call inputs before forwarding (OUT direction)
runtime_scan = true
# Scan tool call outputs before returning (IN direction, optional)
return_scan = false
# Audit log path, relative to repo root (default: .satori/scanner.log)
audit_log = ".satori/scanner.log"

# Handler definitions (optional — built-ins: passthrough, kairn)
[[handlers]]
name = "my-handler"
module = "./handlers/my-handler.js"

# Downstream server definitions
[[servers]]
name = "filesystem"          # identifier used in satori_exec("filesystem", ...)
runtime = "npx"              # npx | docker | external
command = "@modelcontextprotocol/server-filesystem"
args = ["/path/to/root"]
env = {}                     # environment variables for this server
handler = "passthrough"      # which handler to apply
enabled = true               # false = registered but not started

[[servers]]
name = "github"
runtime = "docker"
image = "ghcr.io/github/github-mcp-server"
args = []
env = { GITHUB_PERSONAL_ACCESS_TOKEN = "${GITHUB_TOKEN}" }
handler = "passthrough"
enabled = true

# External: Satori does not manage lifecycle; server must be running
[[servers]]
name = "my-local-server"
runtime = "external"
host = "localhost"
port = 3001
transport = "http"
handler = "passthrough"
enabled = true
```

### Environment Variable Expansion

Values in `env` fields support `${VAR}` syntax. Satori expands from the host shell environment
at server start time. Unexpanded variables cause a startup error — not silent failure.

---

## SQLite Schema

Database location: `.satori/db.sqlite` at repo root — gitignored, local to the project.
No hashing or global path needed; data lives alongside `satori.toml`.

```
<repo-root>/
├── satori.toml          # config (committed)
├── .satori/             # data dir (gitignored)
│   ├── db.sqlite        # session events + content captures
│   └── scanner.log      # audit log
└── .gitignore           # Satori install adds .satori/ entry
```

Global config (`~/.satori/config.toml`) stays global. Only runtime data is repo-local.

The DB has two logical stores in one file:

### Session Event Store (session awareness)

Derived from context-mode's implementation. Tracks what Claude is doing in this session
so the snapshot can restore context after a compaction.

```sql
-- Raw events captured by hooks during a session
CREATE TABLE IF NOT EXISTS session_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT    NOT NULL,
  type        TEXT    NOT NULL,   -- e.g. file_read, task_create, rule_content
  category    TEXT    NOT NULL,   -- file | task | rule | decision | cwd | error |
                                  --   env | git | subagent | intent | mcp | plan
  priority    INTEGER NOT NULL DEFAULT 2,  -- 1=highest, 5=lowest; drives snapshot budget
  data        TEXT    NOT NULL,
  source_hook TEXT    NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  data_hash   TEXT    NOT NULL DEFAULT ''  -- SHA256 prefix; dedup key
);

-- Per-session metadata
CREATE TABLE IF NOT EXISTS session_meta (
  session_id    TEXT    PRIMARY KEY,
  project_dir   TEXT    NOT NULL,
  started_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  last_event_at TEXT,
  event_count   INTEGER NOT NULL DEFAULT 0,
  compact_count INTEGER NOT NULL DEFAULT 0
);

-- Pending XML snapshots (written at PreCompact, consumed at SessionStart)
CREATE TABLE IF NOT EXISTS session_resume (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT    NOT NULL UNIQUE,
  snapshot    TEXT    NOT NULL,   -- XML ≤2048 bytes
  event_count INTEGER NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  consumed    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_session_events_session  ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_events_type     ON session_events(session_id, type);
CREATE INDEX IF NOT EXISTS idx_session_events_priority ON session_events(session_id, priority);
```

**Event categories and priority tiers:**

| Category | Priority | Snapshot budget |
|----------|----------|-----------------|
| `file`, `task`, `rule` | P1 | 50 % (~1024 B) |
| `cwd`, `error`, `decision`, `env`, `git` | P2 | 35 % (~716 B) |
| `subagent`, `skill`, `intent`, `mcp`, `plan` | P3–P4 | 15 % (~308 B) |

FIFO eviction at 1000 events per session: lowest-priority (then oldest) event is dropped first.
Deduplication window: same `type + data_hash` in the last 5 events → skip insert.

### Content Capture Store (tool output search)

Stores compressed tool output for FTS retrieval via `satori_context query`.

```sql
-- Raw tool output captures from satori_exec calls
CREATE TABLE IF NOT EXISTS captures (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT    NOT NULL,
  server      TEXT    NOT NULL,
  tool        TEXT    NOT NULL,
  input_json  TEXT,
  output_text TEXT    NOT NULL,
  summary     TEXT,              -- compressed; filled by summarizer post-capture
  captured_at INTEGER NOT NULL   -- unix timestamp
);

-- FTS5 index over captures for fast retrieval
CREATE VIRTUAL TABLE IF NOT EXISTS captures_fts USING fts5(
  server, tool, output_text, summary,
  content='captures', content_rowid='id'
);

CREATE INDEX IF NOT EXISTS idx_captures_session ON captures(session_id);
```

---

## Hooks Architecture

Satori ships a set of Claude Code hooks (`.claude-plugin/hooks/hooks.json`) that capture
session events and inject context. All hooks are non-blocking — hook failures are logged
but never interrupt Claude's flow.

| Hook | Trigger | What it does |
|------|---------|--------------|
| `PostToolUse` | After every tool call | Captures tool type + output summary → `session_events`; also writes to content `captures` |
| `PreCompact` | Before context compaction | Builds XML snapshot from all session events → stores in `session_resume` |
| `SessionStart` | On session open | Reads unconsumed `session_resume` → injects as `<session_resume>` system message |
| `UserPromptSubmit` | Before user message | Injects lightweight context hint if no resume snapshot present |
| `PreToolUse` | Before Bash/Read/Grep/WebFetch/Agent/Task | Intercepts tool call arguments for classification into event categories |

### Session ID Resolution

Hook payloads from Claude Code carry a `transcript_path` field (path to the `.jsonl` transcript
file) and optionally a `session_id` field. Satori extracts the session ID using the following
priority chain, derived from context-mode's implementation:

```typescript
function extractSessionId(input: HookPayload): string {
  // 1. UUID embedded in the transcript filename (most reliable)
  if (input.transcript_path) {
    const match = input.transcript_path.match(/([a-f0-9-]{36})\.jsonl$/);
    if (match) return match[1];
  }
  // 2. Explicit session_id field in the hook payload
  if (input.session_id) return input.session_id;
  // 3. Environment variable (set by some Claude Code configurations)
  if (process.env.CLAUDE_SESSION_ID) return process.env.CLAUDE_SESSION_ID;
  // 4. Fallback: parent process PID (unique per Claude Code process)
  return `pid-${process.ppid}`;
}
```

Claude Code environment detection: check for `CLAUDE_PROJECT_DIR` or `CLAUDE_SESSION_ID`
environment variables. Both are set by Claude Code when it launches hook processes.

### Event classification (PostToolUse)

`extract.ts` maps each tool call to a `SessionEvent`:

```
file_read     → category=file,     priority=1,  data=path
file_write    → category=file,     priority=1,  data=path
file_edit     → category=file,     priority=1,  data=path
task_create   → category=task,     priority=1,  data=JSON{subject}
task_update   → category=task,     priority=1,  data=JSON{taskId, status}
rule_path     → category=rule,     priority=1,  data=path
rule_content  → category=rule,     priority=1,  data=content (≤400 chars)
cwd_change    → category=cwd,      priority=2,  data=path
error_caught  → category=error,    priority=2,  data=message (≤150 chars)
decision_made → category=decision, priority=2,  data=text (≤200 chars)
env_set       → category=env,      priority=2,  data=key=value
git_op        → category=git,      priority=2,  data=op type
subagent_*    → category=subagent, priority=3,  data=description
intent_set    → category=intent,   priority=4,  data=mode string
mcp_call      → category=mcp,      priority=4,  data=tool:args summary
plan_enter    → category=plan,     priority=3,  data=status
```

---

## Session Snapshot Format

The `PreCompact` hook calls `snapshot.buildResumeSnapshot(events, opts)` — a pure function
that converts stored `session_events` into an XML string injected at the next `SessionStart`.

```xml
<session_resume compact_count="2" events_captured="47" generated_at="2026-03-27T14:00:00Z">
  <active_files>
    <file path="src/index.ts" ops="read:3,edit:1" last="edit" />
    <file path="src/gateway/router.ts" ops="write:1" last="write" />
  </active_files>
  <task_state>
    - Implement satori_exec routing
    - Write unit tests for handler pipeline
  </task_state>
  <rules>
    <rule_content>Use absolute paths for MCP command fields</rule_content>
    - CLAUDE.md
  </rules>
  <decisions>
    - satori_exec single entry point instead of namespace per tool
  </decisions>
  <environment>
    <cwd>/Volumes/Moon/Coding/miyo-satori</cwd>
    <git op="commit" />
  </environment>
  <errors_encountered>
    - TypeScript strict: implicit any on handler registry lookup
  </errors_encountered>
</session_resume>
```

**Budget**: 2048 bytes default. If over budget, priority tiers are dropped last-first
(P3–P4 dropped first, then P2, then P1 trimmed). Even the header + footer alone always fits.

**Sections and their source categories:**

| XML section | Source categories | Notes |
|-------------|-------------------|-------|
| `<active_files>` | `file` | Deduplicated by path; last 10; op counts |
| `<task_state>` | `task` | Pending/in-progress only; completed tasks omitted |
| `<rules>` | `rule` | Unique paths + content blocks |
| `<decisions>` | `decision` | Unique entries |
| `<environment>` | `cwd`, `env`, `git` | Last cwd; last git op; all env entries |
| `<errors_encountered>` | `error` | All recent errors |
| `<plan_mode>` | `plan` | Present only if last plan event = `plan_enter` |
| `<intent>` | `intent` | Last intent event only |
| `<subagents>` | `subagent` | P2: completed; P3: launched |
| `<mcp_tools>` | `mcp` | Deduplicated by tool name + call count |

---

## Tool Naming Convention

Claude Code sees Satori as a single MCP server exposing exactly **5 tools**, regardless of how many downstream servers are registered:

| Tool | Purpose |
|------|---------|
| `satori_context` | Context DB: restore, query, status, flush |
| `satori_manage` | Server management: list, add, remove, enable, disable, state, scan |
| `satori_find` | Search for tools across all registered servers by keyword |
| `satori_schema` | Get the full input schema for a specific tool |
| `satori_exec` | Execute a downstream tool by server + tool name |

### Discovery + dispatch flow (mirrors Airis pattern)

```
Claude: [satori_find("read file")]
→ filesystem: read_file — Read a file from the filesystem
→ filesystem: read_multiple_files — Read several files at once

Claude: [satori_schema("filesystem", "read_file")]
→ { path: { type: "string", description: "..." } }

Claude: [satori_exec("filesystem", "read_file", { path: "/src/main.ts" })]
→ compact summary of file contents
```

`satori_find` and `satori_schema` replace the auto-discovery that would otherwise come from
exposing namespaced tools via `tools/list`. Claude calls them when it needs to discover what
a server offers or verify an argument shape before executing.

### Why not namespace tools

Exposing downstream tools as individual `<server>_<tool>` entries (e.g. `filesystem_read_file`,
`github_create_issue`) does not reduce Claude's tool count — it grows proportionally to
registered servers × tools per server. The 5-tool surface stays constant regardless of
how many downstream servers are registered.

### satori_exec signature

```typescript
satori_exec(
  server: string,    // registered server name from satori.toml
  tool: string,      // bare tool name (as returned by satori_find)
  args: Record<string, unknown>  // tool arguments (schema from satori_schema)
) → string           // compact summary (not raw upstream output)
```

**Server name collision**: if two `satori.toml` entries share the same `name` field (across g/p/r levels), the higher-priority scope wins and a warning is written to the audit log.

---

## Gateway Routing

### Tool Call Flow

```
Claude calls: satori_exec("filesystem", "read_file", {path: "/src/main.ts"})
                │
                ▼
1. Validate arguments: server, tool, args all present
2. Look up "filesystem" in registry → ServerConfig found
3. Check ServerState → if stopped: lifecycle.start("filesystem")
4. Look up handler for "filesystem" → PassthroughHandler
5. handler.beforeCall({serverName: "filesystem", toolName: "read_file", arguments: {...}})
   → security.scanOut(arguments) — check for secrets/keys
   → if blocked: return error to Claude, write audit log
6. Forward to filesystem MCP server via STDIO/HTTP transport
7. Receive response from downstream
8. handler.afterCall(request, response)
   → (optional) security.scanIn(response)
9. context.store.capture(session, server, tool, input, output)
10. context.summarizer.summarize(capture) → store summary
11. Return compact summary (not raw output) to Claude
```

### Discovery Flow

```
Claude: satori_find("read file")
  → registry.list() + cached tool catalogs → filter by query
  → [{ server: "filesystem", tool: "read_file", state: "running" }, ...]

Claude: satori_schema("filesystem", "read_file")
  → registry.lookup("filesystem") → return cached MCP tool definition
  → { name: "read_file", description: "...", inputSchema: { path: {...} } }

Claude: satori_exec("filesystem", "read_file", { path: "/src/main.ts" })
  → full routing pipeline (see Tool Call Flow above)
```

**Tool catalog caching**: at startup and when a server first starts, Satori calls `tools/list`
on the downstream server and caches the result. `satori_find` and `satori_schema` always serve
from this cache — cold servers are searchable without starting them. Cache is invalidated on
`satori_manage reload` or server restart.

### Server Name Collision Handling

If two `satori.toml` entries across g/p/r scopes share the same `name` field, the higher-priority
scope wins (repo > project > global). The shadowed entry is ignored and a warning is written
to the audit log at startup.

---

## Hot/Cold Lifecycle State Machine

```
         ┌──────────┐
    ─────►  stopped  ◄────────────────────────────────┐
         └────┬─────┘                                 │
              │ tool call received + enabled=true      │ error / crash
              ▼                                        │
         ┌──────────┐                            ┌─────┴────┐
         │ starting │ ─── timeout ──────────────► │  error   │
         └────┬─────┘                            └──────────┘
              │ health check passed
              ▼
         ┌──────────┐
         │ running  │ ◄── tool calls served here
         └────┬─────┘
              │ disabled in config / satori_manage disable
              ▼
         ┌──────────┐
         │ blocked  │  (security scan result: blocked)
         └──────────┘
```

**npx runtime**: spawns `npx -y <command> [args]`, waits for `tools/list` response to confirm
readiness, then routes tool calls via STDIO transport.

**Docker runtime**: runs `docker run --rm -d [env flags] <image> [args]`, polls
`docker inspect` for running state, connects via HTTP transport on the mapped port.
Stops container on Satori shutdown or server disable.

**External runtime**: assumes server is already running; connects via configured host/port.
Satori does not manage lifecycle — only routes.

---

## Security Implementation

### Startup Scan

Runs when Satori starts and when config is reloaded. For each registered server:

1. **Config scan**: check `command`, `image`, and `args` fields for shell injection patterns
   (`&&`, `;`, `|`, backticks, `$()`, path traversal)
2. **Description scan** (after connecting to get tool list): check each tool's `description`
   field for: `exfiltrate`, `delete all`, `ignore previous instructions`, hidden Unicode
   characters (U+200B etc.), `eval`, arbitrary `exec` patterns
3. Set server status: `passed | blocked | skipped | pending`
4. Blocked servers: tools are not registered; server is not started

### Runtime OUT Scan (mandatory)

Before every `handler.beforeCall`, `security.scanOut` runs over the `arguments` object:

- Match against patterns in `patterns.ts`:
  - API key patterns: `sk-[A-Za-z0-9]{20,}`, `AKIA[0-9A-Z]{16}`, `ghp_[A-Za-z0-9]{36}`
  - Generic high-entropy strings in values >20 chars flagged for review
  - Common env var names: `API_KEY`, `SECRET`, `PASSWORD`, `TOKEN` as JSON keys with non-empty values
- If matched: block the call, log to audit log, return error to Claude explaining the block
- Pattern list is extensible via config (future)

### Audit Log Format

```
2026-03-27T14:00:00Z STARTUP  server=github   status=passed
2026-03-27T14:01:00Z BLOCKED  server=evil-mcp status=blocked reason="tool 'exfiltrate_data' matches pattern"
2026-03-27T14:02:00Z OUT_SCAN server=filesystem tool=write_file via=satori_exec reason="secret pattern matched: sk-..."
```

---

## Auto-Registration (.mcp.json Import)

Triggered when `auto_register_mcp_json = true` and `satori.toml` does not yet contain a
matching server entry.

```
1. Detect .mcp.json at repo root
2. Parse .mcp.json → extract mcpServers entries
3. For each entry:
   a. Map to Satori [[servers]] block (command → runtime=npx if npx-based, else external)
   b. Append to satori.toml (or create if absent)
   c. Env vars stay as-is; Satori expands them at runtime
4. Rename .mcp.json → .mcp.satori-json
   (Claude Code will no longer see it; Satori is now the sole manager)
5. Log: "Imported N servers from .mcp.json → .mcp.satori-json"
```

`.mcp.satori-json` is kept for reference and manual rollback. It is gitignored by default
(Satori's install step adds the pattern).

---

## Tools Exposed to Claude Code

### `satori_context`

Single tool with sub-command dispatch to avoid polluting Claude's tool list.

| Sub-command | Arguments | Description |
|-------------|-----------|-------------|
| `restore` | `session_id?` | Load most recent session guide; returns ≤2KB XML |
| `query` | `q: string`, `limit?: number` | FTS5 search over captures; returns ranked summaries |
| `status` | — | Current DB stats: sessions, captures, guide count |
| `flush` | — | Force session guide generation now (before compaction) |

### `satori_manage`

| Sub-command | Arguments | Description |
|-------------|-----------|-------------|
| `list` | — | List registered servers with state and handler |
| `add` | `name`, `runtime`, `command/image`, `args?`, `env?`, `handler?`, `scope?` | Write a new `[[servers]]` entry to the target `satori.toml` (default scope: repo) |
| `remove` | `name: string`, `scope?` | Remove a server entry from the target `satori.toml` |
| `enable` | `name: string` | Set `enabled = true` in current scope config |
| `disable` | `name: string` | Set `enabled = false` (does not remove config entry) |
| `state` | `name: string` | Show current ServerState + last error if any |
| `scan` | `name?: string` | Re-run security scan on one or all servers |
| `reload` | `name?: string` | Invalidate tool catalog cache and re-run `tools/list` for one or all running servers; used after a downstream server adds or removes tools |

`add` and `remove` write to `satori.toml` at the specified scope:
- `scope = "repo"` (default) → `<repo-root>/satori.toml`
- `scope = "project"` → `<project-dir>/satori.toml`
- `scope = "global"` → `~/.satori/config.toml`

This is the primary registration path when no `.mcp.json` exists.

### `satori_find`

Search for tools across all registered servers. Intended as the first step when Claude doesn't
know which server/tool to use.

| Argument | Type | Description |
|----------|------|-------------|
| `query` | `string` | Keyword or natural language — matched against tool name and description |
| `server` | `string?` | Optional: limit results to a specific server |

Returns a list of matches, each with `server`, `tool`, `description`, and `state` (hot/cold/blocked).
Cold servers are included in results; Satori does not need to start them to return their tool list
(tool list is cached at startup scan time).

Example output:
```json
[
  { "server": "filesystem", "tool": "read_file", "description": "Read a file from disk", "state": "running" },
  { "server": "filesystem", "tool": "read_multiple_files", "description": "Read several files", "state": "running" }
]
```

### `satori_schema`

Get the full JSON input schema for a specific tool before calling it.

| Argument | Type | Description |
|----------|------|-------------|
| `server` | `string` | Registered server name |
| `tool` | `string` | Bare tool name |

Returns the MCP tool definition: `{ name, description, inputSchema }`. The `inputSchema` is the
raw JSON Schema as declared by the downstream server. Satori caches schemas at startup scan time;
cold servers do not need to be started to return a cached schema.

Error: unknown server or tool → `{"error": "..."}`.

### `satori_exec`

Execute a downstream tool. Use `satori_find` to discover what's available and `satori_schema`
to verify argument shape before calling.

| Argument | Type | Description |
|----------|------|-------------|
| `server` | `string` | Registered server name (must match a `[[servers]]` entry) |
| `tool` | `string` | Bare tool name (as returned by `satori_find`) |
| `args` | `object` | Tool arguments (shape from `satori_schema`) |

Returns a compact summary string. Raw upstream output is stored in the context DB but not
returned directly — Claude gets the summarized form only.

Error cases:
- Server not registered → `{"error": "unknown server: <name>"}`
- Server blocked by security scan → `{"error": "server blocked: <reason>"}`
- Start timeout → `{"error": "server failed to start: <name>"}`
- Tool not found on downstream → forwarded error from downstream

---

## Discovery Mechanism

**Decision: Option C** — tool presence (runtime) + CLAUDE.md flag (fast path, set by TCS install).

For M4, only the tool presence half is implemented. Satori registers `satori_context` when
running; its absence means Satori is not available. Skills check for the tool before attempting
context queries.

The CLAUDE.md flag and skill-level integration are M5 deliverables.

---

## TCS Submodule (R6.1)

Satori lives at `modules/satori/` in the TCS repo.

```bash
# Added to TCS repo during install.sh context-mode setup:
git submodule add https://github.com/MMoMM-org/miyo-satori modules/satori
git submodule update --init --recursive

# install.sh adds to Claude Code MCP config:
# ~/.claude/settings.json or repo .claude/settings.json:
{
  "mcpServers": {
    "satori": {
      "command": "node",
      "args": ["<abs-path-to>/modules/satori/dist/src/index.js"],
      "env": {}
    }
  }
}
```

MCP command path must be absolute (relative paths fail in Claude Code — CLAUDE.md guardrail).
`install.sh` resolves the absolute path at install time.

---

## Open Questions (Deferred to Plan / Implementation)

| Question | Notes |
|----------|-------|
| ~~Session ID source~~ | **Resolved** — see Hooks Architecture / Session ID Resolution. Priority: `transcript_path` UUID → `session_id` field → `CLAUDE_SESSION_ID` env → `pid-${ppid}`. |
| FTS5 summarizer quality | How good is the compression? May need a small LLM call or heuristic ranking. Prototype first. |
| Docker availability check | Should Satori gracefully skip Docker servers if Docker is not installed? |
| Config hot-reload | Can `satori.toml` be reloaded without restarting the MCP server? |

---

## Post-MVP: Shell Pseudo-Server (context-mode parity)

context-mode exposes `ctx_execute`, `ctx_execute_file`, and `ctx_batch_execute` — tools that run
shell commands and index their output into the capture store. This functionality is in scope for
Satori but deferred post-MVP.

**Design**: ship a built-in **shell pseudo-server** registered at Satori startup without any
`satori.toml` config required. It behaves like a real downstream server from the gateway's
perspective (goes through `satori_exec`, handler pipeline, content capture, summarizer) but is
implemented internally rather than as a separate process.

```
satori_exec("shell", "execute",     { cmd: "npm test", cwd?: string })
satori_exec("shell", "execute_file", { path: "scripts/run.sh", cwd?: string })
satori_exec("shell", "batch",       { cmds: ["git status", "npm run build"] })
```

All three tools capture stdout+stderr into the content store and return a compact summary.
The pseudo-server is always registered (state: `running`) and never goes through lifecycle
management. Security OUT scan applies as normal — shell injection patterns are already in
`patterns.ts` and will catch dangerous `cmd` values.

**Implementation notes:**
- `registry.ts`: add a `isPseudoServer` flag to `ServerConfig`; pseudo-servers bypass the
  lifecycle manager and connect directly to an in-process handler
- `src/servers/shell.ts`: implements the three tool handlers as Node.js `child_process.execFile`
  calls with a configurable timeout
- `satori_find("execute")` returns the shell pseudo-server tools like any other server
- The `shell` name is reserved — user-defined servers cannot use it
- Timeout default: 30 000 ms (same as `npx_startup_timeout_ms`); configurable via
  `[servers.shell] timeout_ms` in `satori.toml`

**Spec work needed before implementation**: add `R2.7` to PRD; add pseudo-server section to SDD
Hot/Cold; add Phase 8 (or extend Phase 5) in the plan.

---

## M5 Scope Acknowledgement

The following components were deferred out of M4 during implementation and delivered in M5
(005-memory-mcp):

- `src/execution/` — PolyglotExecutor, per-language runtimes, safe env + file-content injection
- `src/knowledge/` — KnowledgeDB, FTS5 + RRF, proximity reranking, fetchAndIndex
- `satori_kb` MCP tool — knowledge search over the SQLite content store
- `builtin` runtime (`ServerConfig.runtime = 'builtin'`) — BuiltinServer dispatch path
- Schema field `context.backend` — tracks whether response came from content store

These were originally scoped for M4 but not implemented. Rather than retroactively rewriting
M4 scope, these components are fully specified and delivered in M5.

---

## Reference

- `docs/XDD/specs/004-satori-gateway/requirements.md` — PRD (this SDD implements)
- `docs/concept/v2/context-mode-MCP-Server.md` — design analysis
- `docs/concept/v2/sources v2.md` — context-mode, lasso, airis, Kairn attribution
- Implementation repo: `https://github.com/MMoMM-org/miyo-satori`
