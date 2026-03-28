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

## Why Attribution Matters

Keeping this document up to date serves a practical purpose: it makes the lineage of each component visible, which makes it straightforward to check upstream sources for improvements and to give proper credit when sharing or redistributing. If you port, adapt, or extend components from other sources, add them here.
