# Routing Reference — Scope × Lifetime × Category

| Learning type | Examples | Target scope | Target file |
|---|---|---|---|
| Personal correction | "stop adding semicolons to commit messages" | global | ~/.claude/includes/memory-*.md |
| Workflow preference | "always use worktrees for features" | global | ~/.claude/includes/memory-*.md |
| Project decision | "we use monorepo for all TCS work" | project | ~/Kouzou/projects/<proj>/memory.md |
| Naming convention | "use kebab-case for all file names" | repo | general.md |
| Code style rule | "no `any` types in TypeScript" | repo | general.md |
| Build command quirk | "use `bun run` not `npm run`" | repo | tools.md |
| CI knowledge | "GitHub Actions cache key is `bun.lock`" | repo | tools.md |
| Business rule | "UserRepository returns null for unknown IDs" | repo | domain.md |
| Data model fact | "Order.status is always lowercase" | repo | domain.md |
| Architecture choice | "chose hexagonal over layered" | repo | decisions.md |
| Tech tradeoff | "using SQLite because low concurrency expected" | repo | decisions.md |
| Current sprint goal | "implementing auth this week" | repo | context.md |
| Known blocker | "bun test crashes on M1 with arm64 native modules" | repo | troubleshooting.md |
| Proven fix | "set NODE_OPTIONS=--max-old-space-size=4096 for builds" | repo | troubleshooting.md |
| Structural thing ruled out | "no, a PAT bypass would cover every merge you make" | repo | declined.md |
| Agent's own accumulated observation | "this repo keeps shipping `any` in the API layer" | agent | `.claude/agent-memory/<agentType>/` |

---

## Agent memory — the fourth store, and when it is the right one

A subagent with `memory: user\|project\|local` gets a directory that persists across
conversations, and the first 200 lines / 25 KB of its `MEMORY.md` is injected into its system
prompt automatically. That makes it a fourth store beside the three above, so it needs a rule or it
becomes the fragmentation `/memory-sync` exists to prevent — one agent at a time.

**The discriminating question:**

> Would the main session, another agent, or a human reviewing later need this?
> → **Memory Bank.** Is it useful only to this one agent, built up across repetitions only it
> witnesses? → **agent memory.**

Almost everything is the first case. Agent memory earns its place in exactly one shape: an
observation no single run makes notable, which only becomes true in aggregate, seen only by an
agent that runs often. A reviewer noticing "this repo keeps doing X" is the canonical example — no
one writes that down today, because no individual instance is worth writing down.

### Why this store exists at all

Not because it is better. Because of what actually reaches a subagent, which is narrower than it
looks:

| Layer | Reaches a subagent? |
|---|---|
| `CLAUDE.md` hierarchy, including its `@`-imports (`active.md`, `memory.md`) | **yes**, in full |
| `docs/ai/memory/{general,tools,domain,…}.md` | **no** — `memory.md` links them as plain Markdown, not `@`-imports, so an agent must choose to read them |
| `~/.claude/projects/<slug>/memory/` (user auto-memory) | **no**, by design |
| Main conversation history | **no** — that is the point of a subagent |

And in the other direction a subagent can write to **none** of these. What it learns dies with it
unless a human notices it in the report and runs `/memory-add`. Anything below that reporting
threshold is simply lost. Agent memory is the only write-back channel there is.

### Two hard constraints

**Never on a read-only agent.** `memory:` also grants general-purpose `Write` and `Edit` — not
confined to the memory directory (measured; see `agent-author/reference/conventions.md` § Tool
Scoping and issue #144). A reviewer declaring `tools: Read, Grep, Glob` alongside `memory: project`
can write anywhere, and the frontmatter still reads as read-only. That excludes the archetypes this
store would otherwise suit best.

**Never for anything a second party needs.** Decisions, conventions, blockers and shared gotchas go
in the Memory Bank even when an agent is the one who discovered them. Agent memory is invisible to
the main session, to other agents, and to `/memory-sync` — and it is written without the routing
gate `/memory-add` provides.

### Scopes

| Scope | Location | Use when |
|---|---|---|
| `project` | `.claude/agent-memory/<agentType>/` | repo-specific, shareable — the default |
| `local` | `.claude/agent-memory-local/<agentType>/` | repo-specific, not checked in |
| `user` | `~/.claude/agent-memory/<agentType>/` | follows the agent across repos |

The directory is keyed by **`<agentType>`**, so renaming an agent orphans its memory.

No TCS agent uses this yet. Adopting it for one is tracked in #85; a consuming repo's `.gitignore`
posture (`agent-memory` in, `agent-memory-local` out) is decided there rather than here.
