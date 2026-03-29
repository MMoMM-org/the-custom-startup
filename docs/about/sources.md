# Sources and Attribution

This document records the origins of The Custom Startup's components and acknowledges the work this project builds on.

---

## Base Fork

**The Custom Startup is forked from [rsmdt/the-startup](https://github.com/rsmdt/the-startup)** by [@rsmdt](https://github.com/rsmdt).

The following concepts and structures were derived from that repository:

- **Spec-driven workflow concept** — the principle that every feature begins with a written specification before any code is written
- **Activity-based agent architecture** — organizing agents by what they *do* (activities) rather than by role alone
- **Slash command lifecycle** — the `specify → validate → implement → review` progression as the primary development loop
- **Output styles system** — the mechanism for defining and activating named output personalities

The Custom Startup extends these foundations with a full plugin architecture, an expanded agent library, the XDD specification system, and the tcs-patterns skill collection.

---

## tcs-patterns Plugin — Skill Origins

The `tcs-patterns` plugin contains 17 domain pattern skills across three origin categories.

### citypaul-derived (10 skills)

These skills were ported from [citypaul's Claude Code skills collection](https://github.com/citypaul) and converted to PICS format (the structured skill format used throughout The Custom Startup):

- `ddd`
- `frontend-testing`
- `functional`
- `hexagonal`
- `mutation-testing`
- `react-testing`
- `test-design-reviewer`
- `testing`
- `twelve-factor`
- `typescript-strict`

Porting to PICS format involved restructuring content into progressive disclosure sections, adding frontmatter trigger terms, and aligning with the skill conventions used in this project. The underlying knowledge and guidance originates with citypaul's work.

### TCS-native (5 skills)

These skills were created specifically for The Custom Startup and have no upstream source:

- `api-design`
- `event-driven`
- `go-idiomatic`
- `node-service`
- `python-project`

### Integration skills (2 skills)

Full SKILL.md implementations for specific platform targets, created for this project:

- `mcp-server`
- `obsidian-plugin`

---

## Agent Architecture

The 15 agents across 8 roles in the `tcs-team` plugin are TCS-native — none are ported from an external source.

The activity-based organization pattern (grouping agents by what they do rather than mapping one-to-one to job titles) draws on published research into LLM multi-agent collaboration and the patterns established by leading agent frameworks. Key references include:

- *Multi-Agent Collaboration Mechanisms* (2025) — research on specialization and task decomposition in LLM agent systems
- Industry framework patterns from CrewAI, AutoGen, and LangGraph

These influenced the structural approach; the agent definitions, prompts, and role boundaries are original to this project.

---

## Output Styles

The `the-startup` and `the-scaleup` output styles were developed for this fork and are not derived from upstream sources.

---

## Memory Bank — Source Influences

The Memory Bank system in `tcs-helper` draws on several community approaches to Claude Code memory management.

### claude-reflect

**Repository:** [claude-reflect marketplace plugin](https://github.com/BayramAnnakov/claude-reflect)

Foundation for the Memory Bank capture layer. The two-stage self-learning hooks (detect corrections → queue → route to destinations) and the learning destinations model (global CLAUDE.md, project CLAUDE.md, CLAUDE.local.md) directly informed the TCS global/project/repo routing table. The `reflect-skills` session analysis — identifying repeating patterns and generating skill files — provides the promotion mechanism used by `/memory-promote`.

### John Conneely Memory System

**Article:** [How I Finally Sorted My Claude Code Memory](https://www.youngleaders.tech/p/how-i-finally-sorted-my-claude-code-memory)

The memory category taxonomy (general conventions, tools integrations, domain knowledge) is applied across TCS scopes instead of a single global bucket. The MEMORY.md index-only pattern with a ~200-line budget was adopted as a design constraint. The principle that routing rules belong in CLAUDE.md, not in MEMORY.md, directly informed the TCS approach.

### centminmod/my-claude-code-setup

**Repository:** [centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup)

The memory bank architecture (per-concern files: activeContext, patterns, decisions, troubleshooting) informed the repo-level typed memory directory at `docs/ai/memory/`. The cleanup-context workflow (token reduction, archive resolved issues) forms the core of `/memory-cleanup`. Stack-aware CLAUDE.md templates (Cloudflare Workers, Convex) provided the pattern reused in `/setup`.

### citypaul/.dotfiles (philosophy)

**Repository:** [citypaul/.dotfiles](https://github.com/citypaul/.dotfiles)

Beyond the pattern skills (listed above), the philosophy-first CLAUDE.md approach (~100 lines core, skills on demand) justified keeping all CLAUDE.md files lean and delegating detail to skills and memory docs. The setup command concept (detect stack, generate CLAUDE.md + hooks) directly inspired `/setup`.

---

## TDD Discipline — Source Influences

### obra/superpowers

**Repository:** [obrasuperpowers](https://github.com/obrasuperpowers) by Jesse Vincent

The TDD RED-GREEN-REFACTOR iron law and the rejected-rationalizations table are embedded into the `xdd-tdd` skill and the TDD/SDD integration design. The verification-before-completion discipline (evidence-before-claims) is implemented as the `/verify` gate. The receiving-code-review rigor pattern forms the basis of `/receive-review`. Dispatching-parallel-agents patterns were absorbed into `/parallel-agents`. Systematic-debugging anti-shortcut rules strengthen `/debug`.

---

## Satori — Source Influences

### context-mode

**Repository:** [mksglu/context-mode](https://github.com/mksglu/context-mode) by Mert Koseoglu

The MCP server concept — capturing tool outputs in a structured database and serving compact summaries instead of replaying full outputs — is the architectural basis for Satori's context capture layer. The reported 90-98% context reduction motivated offloading session data to a context server.

### MCP Gateway patterns

**Repositories:** [lasso-security/mcp-gateway](https://github.com/lasso-security/mcp-gateway), [agiletec-inc/airis-mcp-gateway](https://github.com/agiletec-inc/airis-mcp-gateway)

The gateway design — composing multiple downstream MCP servers behind a single endpoint — provided the reference architecture for Satori's server routing layer.

---

## Why Attribution Matters

Keeping this document up to date serves a practical purpose: it makes the lineage of each component visible, which makes it straightforward to check upstream sources for improvements and to give proper credit when sharing or redistributing. If you port, adapt, or extend components from other sources, add them here.
