```
████████ ██   ██ ███████
   ██    ██   ██ ██
   ██    ███████ █████
   ██    ██   ██ ██
   ██    ██   ██ ███████

 ██████ ██    ██ ███████ ████████  ██████  ███    ███
██      ██    ██ ██         ██    ██    ██ ████  ████
██      ██    ██ ███████    ██    ██    ██ ██ ████ ██
██      ██    ██      ██    ██    ██    ██ ██  ██  ██
 ██████  ██████  ███████    ██     ██████  ██      ██

 █████  ██████  ███████ ███   ██ ████████ ██  ██████
██   ██ ██      ██      ████  ██    ██    ██ ██
███████ ██  ███ █████   ██ ██ ██    ██    ██ ██
██   ██ ██   ██ ██      ██  ████    ██    ██ ██
██   ██  ██████ ███████ ██   ███    ██    ██  ██████

███████ ████████  █████  ██████  ████████ ██   ██ ██████
██         ██    ██   ██ ██   ██    ██    ██   ██ ██   ██
███████    ██    ███████ ██████     ██    ██   ██ ██████
     ██    ██    ██   ██ ██   ██    ██    ██   ██ ██
███████    ██    ██   ██ ██   ██    ██     █████  ██
```

> A customized fork of [the-startup](https://github.com/rsmdt/the-startup) by [@rsmdt](https://github.com/rsmdt).
> See [What's different](#whats-different) for changes made in this fork.

---

## What is The Agentic Startup?

**The Agentic Startup** is a multi-agent AI framework that makes Claude Code work like a startup team. Instead of asking Claude to "just build it", you specify what you want first — creating a clear plan with requirements, a technical design, and an implementation roadmap. Then you execute that plan with parallel specialist agents that work together to turn your ideas into shipped code.

**20+ skills across 4 plugins. Specify first, then build with confidence.**

### Key Features

- **[Spec-Driven Development](docs/getting-started/index.md)** — PRD → SDD → Implementation Plan → Code. Write the plan before writing code.
- **[eXtended Design & Development (XDD)](docs/reference/xdd.md)** — PRD → SDD → Plan → Implement → Validate back. Full spec-first workflow with 6 dedicated XDD skills and backward validation to catch drift.
- **[TDD Enforcement](docs/about/concepts.md#tdd--sdd-integration)** — RED → GREEN → REFACTOR iron law. The `tdd-guardian` agent blocks production code until a failing test exists — no exceptions.
- **[Parallel Agent Execution](docs/reference/agents.md)** — Multiple specialist agents work simultaneously within each implementation phase.
- **[Memory Bank](docs/about/concepts.md#memory-bank)** — Layered memory system (global / project / repo) with progressive disclosure. Keeps context usage low while maintaining project knowledge across sessions. Run `/setup` to provision.
- **[Multi-AI Workflow](docs/guides/multi-ai-workflow.md)** — Export specs as prompts for Claude.ai or Perplexity, import the results back as PRD or SDD.
- **[Quality Gates](docs/getting-started/workflow.md#step-3-validate-before-implementation)** — Built-in validation at every stage: before you build, while you build, and before you ship.
- **[Satori Integration](docs/about/concepts.md#satori--mcp-gateway-optional)** *(optional)* — MCP gateway that captures session activity and serves compact summaries, further reducing context consumption.
- **Resume Across Sessions** — Specs live on disk. Hit a context limit? Start a fresh session and pick up exactly where you left off.
- **[Interactive Install Wizard](#installation)** — Choose install target, plugins, output style, statusline, and multi-AI templates — with a confirmation summary before anything is written.
- **[3 Statusline Variants](docs/guides/statusline.md)** — Standard, enhanced with live token budget bar (via ccusage), and Starship bridge — all configurable via `statusline.toml`.
- **[Output Styles](docs/reference/output-styles.md)** — The Startup (high-energy, fast) and The ScaleUp (calm, educational).
- **Configurable Spec Paths** — `.claude/startup.toml` tells all skills and scripts where your specs live.

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
```

The interactive wizard lets you choose: install target (global / repo / custom path) · which plugins ([workflow](#workflow-plugin-tcs-workflow--core-workflow) / [team](#team-plugin-tcs-team--specialist-agents) / [helper](#helper-plugin-tcs-helper--skill-authoring--memory-bank-optional) / [patterns](#patterns-plugin-tcs-patterns--domain-pattern-skills-optional)) · output style · multi-AI templates · statusline variant · optional [Satori](docs/about/concepts.md#satori--mcp-gateway-optional) MCP gateway.

To uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/uninstall.sh | bash
```

→ Prefer the marketplace? See [docs/getting-started/installation.md](docs/getting-started/installation.md) for manual setup steps.

---

## Quick Start

After installation, optionally set up project governance rules that Claude enforces throughout the workflow:

```bash
/constitution
```

Switch [output style](docs/reference/output-styles.md) anytime — The Startup is high-energy and fast, The ScaleUp is calm and educational:

```bash
/output-style "tcs-workflow:The Startup"
/output-style "tcs-workflow:The ScaleUp"
```

Then start building:

```bash
# Step 1: Create a specification (requirements + technical design + implementation plan)
/xdd Add user authentication with OAuth support

# Step 2: Optionally validate the spec before building
/validate 001

# Step 3: Execute the plan
/implement 001
```

→ Full workflow: [docs/getting-started/workflow.md](docs/getting-started/workflow.md) · Core concepts: [docs/getting-started/index.md](docs/getting-started/index.md)

---

## Plugins

### Workflow Plugin (`tcs-workflow`) — Core Workflow

**20 user-invocable skills** covering the full development lifecycle. → [Full skill reference](docs/reference/skills.md)

| Category | Skills |
|----------|--------|
| **Setup** | `/constitution` — project governance rules, auto-enforced during the build workflow |
| **XDD** | `/xdd` → `/xdd-prd` → `/xdd-sdd` → `/xdd-plan` → `/xdd-tdd` · `/xdd-meta` — spec + TDD pipeline |
| **Build** | `/xdd` → `/validate` → `/implement` (with TDD enforcement) — spec-driven development pipeline |
| **Quality** | `/test` — code ownership enforcement · `/review` — multi-agent parallel code review · `/verify` · `/receive-review` |
| **Assist** | `/guide` · `/brainstorm` · `/parallel-agents` |
| **Maintain** | `/analyze` · `/refactor` · `/debug` · `/document` |

### Team Plugin (`tcs-team`) — Specialist Agents

**15 activity-based agents across 8 roles.** These activate automatically when the workflow needs specialist expertise — you don't invoke them directly. → [Full agent reference](docs/reference/agents.md)

| Role | Focus |
|------|-------|
| **The Chief** | Complexity assessment, routing, parallel coordination |
| **The Analyst** | Requirements, prioritization, product research |
| **The Architect** | System design, security, robustness, compatibility review |
| **The Developer** | Feature implementation, performance optimization |
| **The Tester** | Test strategy, load testing, coverage |
| **The Designer** | User research, interaction design, accessibility |
| **The DevOps** | Infrastructure, CI/CD, monitoring |
| **The Meta Agent** | Agent design and generation |

### Helper Plugin (`tcs-helper`) — Skill Authoring + Memory Bank *(optional)*

Skill authoring tools, a layered **[Memory Bank](docs/about/concepts.md#memory-bank)** for structured learning and context minimization, and git workflow helpers. Install to add persistent project knowledge to your repos or to extend the framework.

| Skill | Purpose |
|-------|---------|
| `/skill-author` · `/skill-evaluate` · `/skill-import` | Create, audit, and fetch Claude Code skills |
| `/setup` | Provision `docs/ai/memory/` + CLAUDE.md hierarchy; install learning-capture hooks |
| `/memory-add` · `/memory-sync` · `/memory-cleanup` · `/memory-promote` | Capture and maintain session learnings across scopes |
| `/git-worktree` · `/finish-branch` | Git workflow management — isolated workspaces, branch completion |
| `/docs` | Fetch and cache current Claude Code documentation on demand |

### Patterns Plugin (`tcs-patterns`) — Domain Pattern Skills *(optional)*

**17 pattern skills** covering architecture, testing, languages, and platform. Install only what you need — they activate on trigger terms. Agents from `tcs-team` automatically use relevant pattern skills when delegating specialist work.

| Category | Skills |
|----------|--------|
| **Architecture** | `/ddd` · `/hexagonal` · `/functional` · `/event-driven` |
| **API & Types** | `/api-design` · `/typescript-strict` |
| **Testing** | `/testing` · `/mutation-testing` · `/frontend-testing` · `/react-testing` · `/test-design-reviewer` |
| **Platforms** | `/node-service` · `/python-project` · `/go-idiomatic` |
| **DevOps** | `/twelve-factor` |
| **Integrations** | `/mcp-server` · `/obsidian-plugin` |

---

## What's Different

The Custom Startup evolved from a fork of [the-startup](https://github.com/rsmdt/the-startup) into an opinionated, standalone framework. It retains the spec-driven workflow and activity-based agent architecture from upstream, and adds:

- **[Memory Bank](docs/about/concepts.md#memory-bank)** — Layered memory system (global / project / repo) with progressive disclosure for context minimization. Capture session learnings, maintain project knowledge, promote patterns to reusable skills.
- **[TDD enforcement](docs/about/concepts.md#tdd--sdd-integration)** — `xdd-tdd` skill + `tdd-guardian` agent enforce the RED → GREEN → REFACTOR iron law during implementation. No production code without a failing test.
- **[Satori gateway](docs/about/concepts.md#satori--mcp-gateway-optional)** *(optional)* — MCP gateway for session context capture, compact summaries, and downstream server routing. Further reduces context consumption.
- **[XDD workflow](docs/reference/xdd.md)** — 6-skill spec pipeline (xdd, xdd-meta, xdd-prd, xdd-sdd, xdd-plan, xdd-tdd) with backward validation to detect spec drift after implementation
- **[Interactive install/uninstall wizards](docs/getting-started/installation.md)** — global / repo / other path, plugin selection, output style, multi-AI templates, statusline with conflict detection, optional Satori setup
- **[3 statusline variants](docs/guides/statusline.md)** — standard, enhanced (token budget bar via ccusage), Starship bridge — each configurable via `statusline.toml`
- **[Multi-AI workflow](docs/guides/multi-ai-workflow.md)** — export specs as prompts for Claude.ai or Perplexity, import results back as PRD/SDD
- **[tcs-patterns plugin](docs/guides/tcs-patterns.md)** — 17 optional domain pattern skills (architecture, testing, platforms, integrations)
- **Configurable specs directory** — `.claude/startup.toml` tells skills and scripts where your specs live; fallback chain keeps backward compatibility

See [about/sources.md](docs/about/sources.md) for full attribution.

---

## Documentation

→ [docs/getting-started/index.md](docs/getting-started/index.md) — full documentation index
→ [CHANGELOG.md](CHANGELOG.md) — version history

---

## License

MIT License. See [LICENSE](LICENSE) for the full text.

For detailed attribution of all source influences — upstream fork, pattern skills, Memory Bank design, TDD discipline, and Satori — see [docs/about/sources.md](docs/about/sources.md).
