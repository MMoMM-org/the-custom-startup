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

**10 slash commands across 3 phases. Specify first, then build with confidence.**

### Key Features

- **[Spec-Driven Development](docs/concepts.md)** — PRD → SDD → Implementation Plan → Code. Write the plan before writing code.
- **[Parallel Agent Execution](docs/agents.md)** — Multiple specialist agents work simultaneously within each implementation phase.
- **[Quality Gates](docs/workflow.md#step-3-validate-before-implementation)** — Built-in validation at every stage: before you build, while you build, and before you ship.
- **Resume Across Sessions** — Specs live on disk. Hit a context limit? Start a fresh session and pick up exactly where you left off.
- **[Interactive Install Wizard](#installation)** — Choose install target, plugins, output style, statusline, and multi-AI templates — with a confirmation summary before anything is written.
- **[3 Statusline Variants](docs/statusline.md)** — Standard, enhanced with live token budget bar (via ccusage), and Starship bridge — all configurable via `statusline.toml`.
- **[Multi-AI Workflow](docs/multi-ai-workflow.md)** — Export specs as prompts for Claude.ai or Perplexity, import the results back as PRD or SDD.
- **Configurable Spec Paths** — `.claude/startup.toml` tells all skills and scripts where your specs live.

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
```

The interactive wizard guides you through: install target (global / repo / custom path) · which plugins (workflow / team / helper / patterns) · output style · multi-AI templates · statusline variant.

To uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/uninstall.sh | bash
```

→ Prefer the marketplace? See [docs/installation.md](docs/installation.md) for manual setup steps.

---

## Quick Start

After installation, optionally set up project governance rules that Claude enforces throughout the workflow:

```bash
/constitution
```

Switch [output style](docs/output-styles.md) anytime — The Startup is high-energy and fast, The ScaleUp is calm and educational:

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

→ Full workflow: [docs/workflow.md](docs/workflow.md) · Core concepts: [docs/concepts.md](docs/concepts.md)

---

## Plugins

### Workflow Plugin (`tcs-workflow`) — Core Workflow

**20 user-invocable skills** covering the full development lifecycle. → [Full skill reference](docs/skills.md)

| Category | Skills |
|----------|--------|
| **Setup** | `/constitution` — project governance rules, auto-enforced during the build workflow |
| **XDD** | `/xdd` → `/xdd-prd` → `/xdd-sdd` → `/xdd-plan` → `/xdd-tdd` · `/xdd-meta` — spec-driven development pipeline |
| **Build** | `/xdd` → `/validate` → `/implement` — spec-driven development pipeline |
| **Quality** | `/test` — code ownership enforcement · `/review` — multi-agent parallel code review · `/verify` · `/receive-review` |
| **Assist** | `/guide` · `/parallel-agents` |
| **Maintain** | `/analyze` · `/refactor` · `/debug` · `/document` |

### Team Plugin (`team`) — Specialist Agents

**15 activity-based agents across 8 roles.** These activate automatically when the workflow needs specialist expertise — you don't invoke them directly. → [Full agent reference](docs/agents.md)

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

### Helper Plugin (`tcs-helper`) — Skill Authoring + Memory System *(optional)*

Skill authoring tools and a file-based project memory system. Install to add structured memory to your repos or to build on the framework.

| Skill | Purpose |
|-------|---------|
| `/skill-author` · `/skill-evaluate` · `/skill-import` | Create, audit, and fetch Claude Code skills |
| `/setup` | Provision `docs/ai/memory/` + CLAUDE.md hierarchy; install learning-capture hooks |
| `/memory-add` · `/memory-sync` · `/memory-cleanup` · `/memory-promote` | Capture and maintain session learnings across scopes |

### Patterns Plugin (`tcs-patterns`) — Domain Pattern Skills *(optional)*

**17 pattern skills** covering architecture, testing, languages, and platform. Install only what you need — they activate on trigger terms.

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

This fork extends the original with:

- **[Interactive install/uninstall wizards](docs/workflow.md)** — global / repo / other path, plugin selection, output style, multi-AI templates, statusline with conflict detection, confirm before writing anything
- **[3 statusline variants](docs/statusline.md)** — standard, enhanced (token budget bar via ccusage), Starship bridge — each configurable via `statusline.toml`
- **Configurable specs directory** — `.claude/startup.toml` tells skills and scripts where your specs live; fallback chain keeps backward compatibility
- **[Multi-AI workflow](docs/multi-ai-workflow.md)** — export specs as prompts for Claude.ai or Perplexity, import results back as PRD/SDD
- **Script naming consistency** — all statusline scripts share the `the-custom-startup-*` prefix

---

## Documentation

→ [docs/index.md](docs/index.md) — full documentation index

---

## License

Original work © [Rudolf Schmidt](https://github.com/rsmdt) — MIT License. See [LICENSE](LICENSE) for the full original license text.

New parts added in this fork (install wizard, statusline scripts, multi-AI workflow, export/import scripts) © Marcus Breiden — MIT License.

Starship statusline integration based on an idea from [Reddit r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/).
