# Plugins

The Custom Agentic Startup is distributed as three Claude Code marketplace plugins. Install via the [interactive install script](installation.md) or manually — see [installation.md](installation.md) for both methods.

---

## tcs-start — Core Workflow (`tcs-start@the-custom-startup`)

The primary plugin. Gives you 10 slash commands covering the full development lifecycle.

```bash
/plugin install tcs-start@the-custom-startup
```

| Category | Skills |
|----------|--------|
| **Setup** | `/constitution` — project governance rules |
| **Build** | `/specify` → `/validate` → `/implement` |
| **Quality** | `/test` · `/review` |
| **Maintain** | `/analyze` · `/refactor` · `/debug` · `/document` |

Two output styles ship with the tcs-start plugin:

| Style | Voice | Best for |
|-------|-------|----------|
| **The Startup** | High-energy, fast | Sprints, execution |
| **The ScaleUp** | Calm, educational | Learning, onboarding |

Switch anytime: `/output-style tcs-start:The Startup`

→ Full reference: [`plugins/tcs-start/README.md`](../plugins/tcs-start/README.md)

---

## tcs-team — Specialist Agents (`tcs-team@the-custom-startup`) — optional

Adds 15 activity-based agents across 8 roles. They activate automatically when tcs-start skills delegate specialist work — you don't invoke them directly.

```bash
/plugin install tcs-team@the-custom-startup
```

| Role | Agents | Focus |
|------|--------|-------|
| **The Chief** | 1 | Complexity assessment, routing, parallel coordination |
| **The Analyst** | 1 | Requirements, prioritization, product research |
| **The Architect** | 4 | System design, security, robustness, compatibility |
| **The Developer** | 2 | Feature implementation, performance optimization |
| **The Tester** | 1 | Test strategy, load testing, coverage |
| **The Designer** | 3 | User research, interaction design, accessibility |
| **The DevOps** | 2 | Infrastructure, CI/CD, monitoring |
| **The Meta Agent** | 1 | Agent design and generation |

→ Full reference: [`plugins/tcs-team/README.md`](../plugins/tcs-team/README.md) · [docs/agents.md](agents.md)

---

## tcs-helper — Skill Authoring Tools (`tcs-helper@the-custom-startup`) — optional

Helper tools for creating and maintaining Claude Code skills and agents. Install this if you want to contribute skills to the framework or build your own.

```bash
/plugin install tcs-helper@the-custom-startup
```

| Tool | What it does |
|------|-------------|
| `/skill-author` | Create, audit, or convert Claude Code skills — covers PICS structure, model selection, agent discovery, TDD Iron Law, and deployment verification |
| `skills/skill-author/find-agents.sh` | Discovers all installed agents across plugin caches — used by `/skill-author` during skill creation |

→ Full reference: [`plugins/tcs-helper/README.md`](../plugins/tcs-helper/README.md)

---

## Installing from this fork

Manual marketplace installation:

```bash
/plugin marketplace add MMoMM-org/the-custom-startup

/plugin install tcs-start@the-custom-startup    # core workflow
/plugin install tcs-team@the-custom-startup     # specialist agents (optional)
/plugin install tcs-helper@the-custom-startup   # skill authoring tools (optional)
```

See [installation.md](installation.md) for what the install script sets up that marketplace install does not (statusline, startup.toml, output styles, multi-AI templates).
