# Documentation

Welcome to The Custom Agentic Startup documentation.

---

## Core

| Document | What it covers |
|----------|---------------|
| [workflow.md](workflow.md) | Core spec-driven workflow: specify → validate → implement → review. The primary loop for building features. |
| [skills.md](skills.md) | All 10 slash commands — what each does, when to use it, decision tree. |
| [agents.md](agents.md) | Full agent reference: 8 roles, 15 activity agents, when to use each. |
| [plugins.md](plugins.md) | The `start` and `team` plugins: skills overview, agent roster, output styles. |
| [output-styles.md](output-styles.md) | The Startup vs The ScaleUp — tone, voice, when to switch. |

## Statusline

| Document | What it covers |
|----------|---------------|
| [statusline.md](statusline.md) | All three variants, `statusline.toml` config reference, placeholders, thresholds. |
| [statusline-starship.md](statusline-starship.md) | Starship bridge setup: env_var modules, `starship.toml` config. |

## Multi-AI Workflow

| Document | What it covers |
|----------|---------------|
| [multi-ai-workflow.md](multi-ai-workflow.md) | Which phases work best in Claude.ai vs Perplexity vs Claude Code. Export/import scripts. |
| [templates/](templates/) | Prompt templates for Claude.ai and Perplexity (PRD, brainstorm, research, constitution). |

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
