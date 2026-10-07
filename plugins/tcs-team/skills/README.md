# Skills Library

Reusable expertise modules that provide consistent guidance across multiple agents.

## Directory Structure

```
skills/
├── api-contract-design/
├── architecture-selection/
├── code-quality-review/
├── domain-modeling/
├── feature-prioritization/
├── frontend-patterns/
├── pattern-detection/
├── performance-analysis/
├── platform-operations/
├── project-discovery/
├── requirements-elicitation/
├── security-assessment/
├── technical-writing/
├── test-practices/
└── user-research/
```

**Exactly one level.** Claude Code discovers a plugin skill only at
`skills/<name>/SKILL.md`. A `SKILL.md` nested any deeper is found by nothing: it cannot be
invoked, and an agent that names it under `skills:` has that entry silently dropped. These
skills sat under category directories until 2026-10-01, so every agent's `skills:` line
resolved to nothing for as long as they existed. Do not reintroduce grouping directories here
— group in the index below instead.

## Skills Index

Grouping is editorial — it is not the directory layout. The right-hand column names the
reachable skill each one must not be confused with, which is also what its `description` says.

| Skill | Theme | Not to be confused with |
|-------|-------|-------------------------|
| `project-discovery` | orientation | `tcs-workflow:analyze` |
| `pattern-detection` | orientation | `tcs-workflow:analyze` |
| `feature-prioritization` | product | — |
| `requirements-elicitation` | product | `tcs-workflow:brainstorm`, `tcs-workflow:xdd-prd` |
| `user-research` | product | — |
| `api-contract-design` | design | `tcs-api-design` |
| `architecture-selection` | design | `tcs-hexagonal`, `tcs-event-driven` |
| `domain-modeling` | design | `tcs-ddd` |
| `frontend-patterns` | design | — |
| `technical-writing` | delivery | `tcs-workflow:document` |
| `test-practices` | delivery | `tcs-testing` |
| `platform-operations` | delivery | `tcs-observability`, `tcs-twelve-factor` |
| `code-quality-review` | review | `tcs-workflow:review` |
| `performance-analysis` | review | — |
| `security-assessment` | review | `tcs-secure-oauth-oidc` |

The `tcs-<name>` skills in the right-hand column are tcs-patterns catalogue patterns, installed per
repository with `/tcs-patterns:patterns-setup` (readable without installing via
`/tcs-patterns:pattern <name>`).

## Usage

Skills are referenced in agent YAML frontmatter:

```yaml
---
name: my-agent
skills: project-discovery, pattern-detection, test-practices
---
```

When the agent is invoked, Claude Code loads each listed skill's **full body** into context at
startup. Resolution is **by name against the discovered skill registry**, and a name that does
not resolve is skipped with only a debug-log warning — so a typo, or a skill at the wrong depth,
costs the agent its context and says nothing. A name must also be unique: two discoverable
skills answering to it make which body loads undefined. That is why `testing` here is
`test-practices` — `tcs-testing` already holds the plain name.

## Creating New Skills

Each skill folder contains:
- `SKILL.md` - Skill definition with frontmatter (`name`, `description`)
- Optional support files (`reference/`, `templates/`, `examples/`, `checklists/`)
