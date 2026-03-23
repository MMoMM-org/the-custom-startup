# Documentation

Welcome to The Custom Agentic Startup documentation.

**New here?** Start with [concepts.md](concepts.md) — it explains how everything fits together in one page.

---

## Getting Started

| Document | What it covers |
|----------|---------------|
| [concepts.md](concepts.md) | **Start here.** How the framework works, what the two plugins do, what a spec is, and how the workflow fits together — with examples. |
| [workflow.md](workflow.md) | The full spec-driven workflow step by step: specify → validate → implement → review. Includes resume patterns and pro tips. |
| [installation.md](installation.md) | Install via script (recommended) or manually via the Claude Code marketplace — with step-by-step setup for statusline, startup config, output style, and multi-AI templates. |
| [multi-ai-workflow.md](multi-ai-workflow.md) | Which phases work best in Claude.ai vs Perplexity vs Claude Code. Export/import scripts, when to use each tool. |
| [templates/](templates/) | Prompt templates for Claude.ai and Perplexity: PRD, brainstorm, research, constitution. |

---

## Core Reference

| Document | What it covers |
|----------|---------------|
| [skills.md](skills.md) | All 10 slash commands — what each does, when to use it, decision tree, and capability matrix. |
| [agents.md](agents.md) | Full agent reference: 8 roles, 15 activity agents, when each activates, and how they collaborate. |
| [plugins.md](plugins.md) | The `start` and `team` plugins: what's included, how to install, how to configure. |
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

## Plugin READMEs (upstream reference)

The original plugin documentation lives alongside the code:

- [`plugins/start/README.md`](../plugins/start/README.md) — full `start` plugin reference
- [`plugins/team/README.md`](../plugins/team/README.md) — full `team` plugin reference
- [`plugins/team/skills/README.md`](../plugins/team/skills/README.md) — team skills overview

These files are upstream originals and are not modified in this fork.
