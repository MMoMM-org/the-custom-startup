---
spec: 004-satori-gateway
document: solution
status: draft
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
│   ├── context/
│   │   ├── store.ts              # SQLite FTS5 wrapper (CRUD + FTS queries)
│   │   ├── summarizer.ts         # Compress raw tool output → compact summary
│   │   ├── session-guide.ts      # Aggregate summaries → ≤2KB session guide
│   │   └── schema.sql            # DB schema (applied on first run)
│   ├── gateway/
│   │   ├── registry.ts           # Downstream server registry (load, validate, lookup)
│   │   ├── router.ts             # Namespace-based tool call routing
│   │   └── namespace.ts          # <server>_<tool> parsing + collision detection
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
│       └── satori-manage.ts      # satori_manage tool (server state, enable/disable)
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
# SQLite DB directory (default: ~/.satori/db/)
db_dir = "~/.satori/db"
# Session guide size cap (bytes)
session_guide_max_bytes = 2048
# Retain raw captures for N days before pruning
retain_days = 30

[security]
# Scan tool descriptions and configs at startup
startup_scan = true
# Scan tool call inputs before forwarding (OUT direction)
runtime_scan = true
# Scan tool call outputs before returning (IN direction, optional)
return_scan = false
# Audit log location
audit_log = "~/.satori/scanner.log"

# Handler definitions (optional — built-ins: passthrough, kairn)
[[handlers]]
name = "my-handler"
module = "./handlers/my-handler.js"

# Downstream server definitions
[[servers]]
name = "filesystem"          # used as namespace prefix: filesystem_<tool>
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

Database location: `<db_dir>/<project-hash>.db` where project hash = SHA256 of repo root path.

```sql
-- Tool output captures
CREATE TABLE IF NOT EXISTS captures (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT    NOT NULL,
  server      TEXT    NOT NULL,
  tool        TEXT    NOT NULL,
  input_json  TEXT,
  output_text TEXT    NOT NULL,
  summary     TEXT,                -- compressed version, filled by summarizer
  captured_at INTEGER NOT NULL     -- unix timestamp
);

-- FTS5 index over captures for fast retrieval
CREATE VIRTUAL TABLE IF NOT EXISTS captures_fts USING fts5(
  server, tool, output_text, summary,
  content='captures', content_rowid='id'
);

-- Compact session guides
CREATE TABLE IF NOT EXISTS session_guides (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT    NOT NULL,
  guide       TEXT    NOT NULL,    -- ≤2KB markdown
  created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_captures_session ON captures(session_id);
CREATE INDEX IF NOT EXISTS idx_guides_session   ON session_guides(session_id);
```

---

## Gateway Routing

### Tool Call Flow

```
Claude calls: filesystem_read_file(path: "/src/main.ts")
                │
                ▼
1. Parse namespace: server="filesystem", tool="read_file"
2. Look up "filesystem" in registry → ServerConfig found
3. Check ServerState → if stopped: lifecycle.start("filesystem")
4. Look up handler for "filesystem" → PassthroughHandler
5. handler.beforeCall({server: "filesystem", tool: "read_file", arguments: {...}})
   → security.scanOut(arguments) — check for secrets
   → if blocked: return error to Claude, write audit log
6. Forward to filesystem MCP server via STDIO/HTTP
7. Receive response
8. handler.afterCall(request, response)
   → (optional) security.scanIn(response)
9. context.store.capture(session, server, tool, input, output)
10. context.summarizer.summarize(capture) → store summary
11. Return compact summary (not raw output) to Claude
```

### Namespace Collision Handling

If two registered servers expose a tool with the same base name, the namespace prefix prevents
collision. If two servers have the same `name` field (e.g. from g/p/r merge), the lower-priority
entry is shadowed and a warning is written to the audit log.

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
2026-03-27T14:02:00Z OUT_SCAN server=filesystem tool=write_file reason="secret pattern matched: sk-..."
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
| `restore` | `session_id?` | Load most recent session guide; returns ≤2KB markdown |
| `query` | `q: string`, `limit?: number` | FTS5 search over captures; returns ranked summaries |
| `status` | — | Current DB stats: sessions, captures, guide count |
| `flush` | — | Force session guide generation now (before compaction) |

### `satori_manage`

| Sub-command | Arguments | Description |
|-------------|-----------|-------------|
| `list` | — | List registered servers with state and handler |
| `enable` | `name: string` | Enable a server in current scope config |
| `disable` | `name: string` | Disable a server (does not remove config) |
| `state` | `name: string` | Show current ServerState + last error if any |
| `scan` | `name?: string` | Re-run security scan on one or all servers |

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
      "args": ["<abs-path-to>/modules/satori/dist/index.js"],
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
| Session ID source | How does Satori assign/receive a session ID from Claude Code? Check if MCP protocol carries session context. |
| FTS5 summarizer quality | How good is the compression? May need a small LLM call or heuristic ranking. Prototype first. |
| Docker availability check | Should Satori gracefully skip Docker servers if Docker is not installed? |
| Config hot-reload | Can `satori.toml` be reloaded without restarting the MCP server? |

---

## Reference

- `docs/XDD/specs/004-satori-gateway/requirements.md` — PRD (this SDD implements)
- `docs/concept/v2/context-mode-MCP-Server.md` — design analysis
- `docs/concept/v2/sources v2.md` — context-mode, lasso, airis, Kairn attribution
- Implementation repo: `https://github.com/MMoMM-org/miyo-satori`
