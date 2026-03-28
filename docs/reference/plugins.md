# Plugins

The Custom Agentic Startup is distributed as four Claude Code marketplace plugins. Install all of them via the [interactive install script](../installation.md), or install individual plugins manually using the commands below.

---

## tcs-workflow

```
/plugin install tcs-workflow@the-custom-startup
```

The core workflow plugin. It gives you a spec-driven, test-verified development lifecycle through 20 skills covering everything from specification and validation through implementation, review, and documentation. All other TCS plugins integrate with and extend the workflow that tcs-workflow defines.

20 skills — full reference: [skills.md](../skills.md)

Two output styles ship with tcs-workflow:

| Style | Voice | Best for |
|-------|-------|----------|
| **The Startup** | High-energy, fast | Sprints, execution |
| **The ScaleUp** | Calm, educational | Learning, onboarding |

Switch anytime: `/output-style tcs-workflow:the-startup`

---

## tcs-team

```
/plugin install tcs-team@the-custom-startup
```

Adds 15 activity-based agents across 8 specialist roles. They activate automatically when tcs-workflow skills delegate work that requires a specialist — you do not invoke them directly. Each agent brings focused expertise, tooling permissions, and decision protocols for its domain.

15 agents across 8 roles — full reference: [agents.md](../agents.md)

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

---

## tcs-helper

```
/plugin install tcs-helper@the-custom-startup
```

Optional. Provides skill authoring tools, a project memory system, and a repo onboarding wizard. Install this plugin when you want to build on the framework, author new skills, or add structured session-learning capture to your repos.

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
| `/memory-add` | Capture session learnings and route them to the correct scope and category file |
| `/memory-sync` | Keep `@imports` and the memory index in sync |
| `/memory-cleanup` | Archive resolved issues, prune stale entries |
| `/memory-promote` | Promote domain patterns from memory files to reusable skills |

**Hooks (installed by `/setup`):**

| Event | Hook | Purpose |
|-------|------|---------|
| `UserPromptSubmit` | `capture_learning.py` | Detect corrections and learnings, queue them |
| `SessionStart` | `session_start_reminder.py` | Show pending queue count at session open |
| `PreCompact` | `check_learnings.py` | Back up queue before context compaction |
| `PostToolUse(Bash)` | `post_commit_reminder.py` | Remind to run `/memory-add` after git commit |

---

## tcs-patterns

```
/plugin install tcs-patterns@the-custom-startup
```

Optional. 17 pattern skills covering architecture, API design, testing, language platforms, DevOps, and integrations. Install selectively — each skill activates on trigger terms and provides interactive, opinionated guidance for its domain without requiring the whole plugin. You can install the full plugin and only use the skills relevant to your stack.

17 skills — full reference: [../guides/tcs-patterns.md](../guides/tcs-patterns.md)

| Category | Skills |
|----------|--------|
| **Architecture** | `ddd` · `hexagonal` · `functional` · `event-driven` |
| **API & Types** | `api-design` · `typescript-strict` |
| **Testing** | `testing` · `mutation-testing` · `frontend-testing` · `react-testing` · `test-design-reviewer` |
| **Platforms** | `node-service` · `python-project` · `go-idiomatic` |
| **DevOps** | `twelve-factor` |
| **Integrations** | `mcp-server` · `obsidian-plugin` |

Invoke any skill by name: `/ddd`, `/hexagonal`, `/typescript-strict`, etc.
