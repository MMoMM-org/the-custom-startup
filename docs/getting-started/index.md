# What is The Custom Startup?

The Custom Startup (TCS) is a spec-driven development framework for Claude Code, distributed as Claude Code marketplace plugins. It structures the way you build software: define requirements and a technical design first, then execute with specialist agents that work together to ship production-quality code. The result is a repeatable, reviewable process instead of open-ended prompting.

---

## The 4 Plugins

| Plugin | What it does | When to use it |
|---|---|---|
| **tcs-workflow** | 20 skills covering the full development lifecycle — spec, validate, implement, test, review, refactor, and more | Always — this is the core; install it first |
| **tcs-team** | 15 specialist agents across 8 roles (Analyst, Architect, Developer, Tester, Designer, DevOps, Chief, Meta Agent) | Alongside tcs-workflow; agents activate automatically when the workflow delegates specialist work |
| **tcs-helper** | Skill authoring tools and a file-based project memory system | Optional — install if you want to build your own skills or add structured memory to your repos |
| **tcs-patterns** | 17 domain pattern skills covering architecture, testing, platforms, and integrations | Optional — install only the patterns relevant to your stack; they activate on trigger terms |

---

## How They Work Together

tcs-workflow is the entry point for everything you do in TCS — you invoke its skills directly (`/xdd`, `/implement`, `/review`, etc.) and the workflow orchestrates the rest. When a task needs specialist depth, tcs-workflow delegates to tcs-team agents automatically; you do not invoke those agents by hand. tcs-patterns extends the workflow with stack-specific guidance that activates when relevant patterns are mentioned, giving you domain expertise without changing how you work. tcs-helper sits alongside the other plugins, providing tools to extend TCS itself and to keep project knowledge organized across sessions.

Implementation follows **TDD discipline** — the `xdd-tdd` skill enforces RED → GREEN → REFACTOR per task, and the `tdd-guardian` agent blocks production code until a failing test exists. This is embedded in `/implement`, not a separate step you need to remember.

### Memory Bank

The **Memory Bank** (tcs-helper) is a layered knowledge system that captures session learnings and project knowledge across three scopes (global, project, repo). It uses Claude Code's own file discovery rules for lazy loading — knowledge is available when you're working in the relevant directory without consuming context budget upfront. Run `/setup` in any repo to provision the structure.

The Memory Bank keeps CLAUDE.md files lean by moving durable knowledge into typed category files (`general.md`, `tools.md`, `domain.md`, `decisions.md`, `context.md`, `troubleshooting.md`). Recurring patterns are promoted from memory files into reusable skills, so the bank gets leaner over time.

### Satori (optional)

**Satori** is an MCP gateway that sits between Claude Code and your MCP servers, capturing session activity into a local database and serving compact summaries. It complements the Memory Bank — Satori handles ephemeral session context, the Memory Bank holds durable knowledge. Together they keep context usage low across long sessions. The install script offers Satori setup as an optional step.

---

## Next Steps

- Install TCS — [installation.md](installation.md)
- Learn the workflow — [workflow.md](workflow.md)
- Understand the design — [concepts](../about/concepts.md)
- Browse all plugins — [plugins reference](../reference/plugins.md)
