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

## tcs-helper — Skill Authoring + Memory System (`tcs-helper@the-custom-startup`) — optional

Skill authoring tools, project memory system, and onboarding wizard. Install to build on the framework or to add the memory system to your repos.

```bash
/plugin install tcs-helper@the-custom-startup
```

**Skill authoring:**

| Skill | What it does |
|-------|-------------|
| `/skill-author` | Create, audit, or convert Claude Code skills — PICS structure, model selection, agent discovery, TDD Iron Law, verification |
| `/skill-evaluate` | Evaluate a skill's quality before importing or using |
| `/skill-import` | Fetch and install a single skill from any GitHub repo without installing the full plugin |

**Memory system:**

| Skill | What it does |
|-------|-------------|
| `/setup` | Provision `docs/ai/memory/` + CLAUDE.md hierarchy in a new repo; installs hooks |
| `/memory-add` | Capture session learnings → route to correct scope (global/project/repo) and category file |
| `/memory-sync` | Keep @imports and memory index in sync |
| `/memory-cleanup` | Archive resolved issues, prune stale entries |
| `/memory-promote` | Promote domain patterns from memory files to reusable skills |

**Hooks (installed by `/setup`):**

| Event | Hook | Purpose |
|-------|------|---------|
| `UserPromptSubmit` | `capture_learning.py` | Detect corrections/learnings, queue them |
| `SessionStart` | `session_start_reminder.py` | Show pending queue count at session open |
| `PreCompact` | `check_learnings.py` | Back up queue before context compaction |
| `PostToolUse(Bash)` | `post_commit_reminder.py` | Remind to run `/memory-add` after git commit |

→ Full reference: [`plugins/tcs-helper/README.md`](../plugins/tcs-helper/README.md)

---

## tcs-patterns — Domain Pattern Skills (`tcs-patterns@the-custom-startup`) — optional

15 pattern skills covering architecture, testing, languages, and platform. Install only the patterns relevant to your stack — they activate on trigger terms and provide interactive pattern guidance.

```bash
/plugin install tcs-patterns@the-custom-startup
```

| Category | Skills |
|----------|--------|
| **Architecture** | `/ddd` · `/hexagonal` · `/functional` · `/event-driven` |
| **API & Types** | `/api-design` · `/typescript-strict` |
| **Testing** | `/testing` · `/mutation-testing` · `/frontend-testing` · `/react-testing` · `/test-design-reviewer` |
| **Platforms** | `/node-service` · `/python-project` · `/go-idiomatic` |
| **DevOps** | `/twelve-factor` — dispatches `tcs-team:the-devops:build-platform` for implementation |
| **Integrations** | `/mcp-server` · `/obsidian-plugin` |

---

## Installing from this fork

Manual marketplace installation:

```bash
/plugin marketplace add MMoMM-org/the-custom-startup

/plugin install tcs-workflow@the-custom-startup   # core workflow
/plugin install tcs-team@the-custom-startup       # specialist agents (optional)
/plugin install tcs-helper@the-custom-startup     # skill authoring + memory system (optional)
/plugin install tcs-patterns@the-custom-startup   # domain pattern skills (optional)
```

See [installation.md](installation.md) for what the install script sets up that marketplace install does not (statusline, startup.toml, output styles, multi-AI templates).
