# Documentation

Welcome to The Custom Agentic Startup documentation.

**New here?** Start with [concepts.md](concepts.md) — it explains how everything fits together in one page.

---

## Getting Started

| Document | What it covers |
|----------|---------------|
| [concepts.md](concepts.md) | **Start here.** How the framework works, what the plugins do, what a spec is, and how the workflow fits together — with examples. |
| [workflow.md](workflow.md) | The full spec-driven workflow step by step: specify → validate → implement → review. Includes resume patterns and pro tips. |
| [installation.md](installation.md) | Install via script (recommended) or manually via the Claude Code marketplace — with step-by-step setup for statusline, startup config, output style, and multi-AI templates. |
| [multi-ai-workflow.md](multi-ai-workflow.md) | Which phases work best in Claude.ai vs Perplexity vs Claude Code. Export/import scripts, when to use each tool. |
| [templates/](templates/) | Prompt templates for Claude.ai and Perplexity: PRD, brainstorm, research, constitution. |

---

## Core Reference

| Document | What it covers |
|----------|---------------|
| [skills.md](skills.md) | All tcs-start slash commands — what each does, when to use it, decision tree, and capability matrix. |
| [agents.md](agents.md) | Full agent reference: 8 roles, 15 activity agents, when each activates, and how they collaborate. |
| [plugins.md](plugins.md) | All four plugins: `tcs-workflow`, `tcs-team`, `tcs-helper` (memory system), `tcs-patterns` — what's included, how to install. |
| [output-styles.md](output-styles.md) | The Startup vs The ScaleUp — tone, voice, when to switch. |

---

## Statusline

| Document | What it covers |
|----------|---------------|
| [statusline.md](statusline.md) | All three variants (standard, enhanced, Starship), `statusline.toml` config reference, placeholders, color thresholds. |
| [statusline-starship.md](statusline-starship.md) | Starship bridge setup: env_var modules, `starship.toml` config. |

---

## Philosophy & Design

| Document | What it covers |
|----------|---------------|
| [PHILOSOPHY.md](PHILOSOPHY.md) | Why spec-driven development, activity-based agents, research foundation, design principles. |
| [the-custom-philosophy.md](the-custom-philosophy.md) | Why this fork exists: install experience, statusline feedback loop, multi-AI workflow, configurable paths. |

---

## Plugin READMEs

- [`plugins/tcs-workflow/README.md`](../plugins/tcs-workflow/README.md) — full `tcs-workflow` plugin reference
- [`plugins/tcs-team/README.md`](../plugins/tcs-team/README.md) — full `tcs-team` plugin reference
- [`plugins/tcs-team/skills/README.md`](../plugins/tcs-team/skills/README.md) — tcs-team skills overview
- [`plugins/tcs-helper/README.md`](../plugins/tcs-helper/README.md) — tcs-helper plugin reference (skill authoring + memory system)
- [`plugins/tcs-patterns/README.md`](../plugins/tcs-patterns/README.md) — tcs-patterns plugin reference (domain pattern skills)
