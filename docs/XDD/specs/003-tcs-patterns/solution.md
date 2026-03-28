---
spec: 003-tcs-patterns
document: solution
status: completed
version: "1.0"
---

# SDD — tcs-patterns Plugin (M3)

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Architecture pattern clearly stated with rationale
- [x] All architecture decisions confirmed by user
- [x] Every interface has specification

### QUALITY CHECKS (Should Pass)

- [x] Constraints → Strategy → Design path is logical
- [x] Every component in directory map has rationale
- [x] A developer could implement from this design

---

## Constraints

CON-1 **Plain markdown only.** Skills are SKILL.md files. No compiled code, no runtime
dependencies. bash 3.2 compatible where scripts are used.

CON-2 **Skill size limit.** Each SKILL.md ≤ 25 KB. Deep content goes into `reference/`
subdirectories loaded on demand.

CON-3 **skill-author mandatory.** Every new or modified skill must pass through
`/tcs-helper:skill-author` for authoring and audit. No hand-crafted SKILL.md outside
that workflow.

CON-4 **No workflow logic.** tcs-patterns skills are domain knowledge libraries, not
workflow orchestrators. They advise, audit, and scaffold — they do not call other skills,
run tests, or manage phases.

CON-5 **Selective install.** The plugin ships all 17 skills; `install.sh` offers per-skill
selection. Users who install only `ddd` get no other skill directories.

---

## Architecture

### Pattern: Domain Knowledge Library

tcs-patterns is a **static knowledge library** — pure markdown, no runtime, no agents.
Each skill is an independent, self-contained advisory unit that loads on demand when the
user invokes it by name.

This is intentionally different from tcs-workflow (orchestration) and tcs-team (agents).
tcs-patterns skills:
- Carry domain expertise in their reference/ files
- Provide audit checklists and build scaffolds in their workflow sections
- Dispatch to tcs-team agents only for implementation work (e.g. twelve-factor → build-platform)
- Never manage phases, files, or state themselves

---

## Repository Structure

```
plugins/tcs-patterns/
├── .claude-plugin/
│   └── plugin.json                   # Plugin manifest
└── skills/
    ├── api-design/
    │   ├── SKILL.md
    │   └── reference/api-patterns.md
    ├── ddd/
    │   ├── SKILL.md
    │   └── reference/
    │       ├── aggregate-design.md
    │       ├── bounded-contexts.md
    │       ├── ddd-patterns.md
    │       ├── domain-events.md
    │       ├── domain-services.md
    │       ├── error-modeling.md
    │       └── testing-by-layer.md
    ├── event-driven/
    │   ├── SKILL.md
    │   └── reference/event-patterns.md
    ├── frontend-testing/
    │   ├── SKILL.md
    │   └── reference/testing-patterns.md
    ├── functional/
    │   ├── SKILL.md
    │   └── reference/functional-patterns.md
    ├── go-idiomatic/
    │   ├── SKILL.md
    │   └── reference/go-patterns.md
    ├── hexagonal/
    │   ├── SKILL.md
    │   └── reference/
    │       ├── cqrs-lite.md
    │       ├── cross-cutting-concerns.md
    │       ├── hexagonal-layers.md
    │       ├── incremental-adoption.md
    │       ├── testing-hex-arch.md
    │       └── worked-example.md
    ├── mcp-server/
    │   ├── SKILL.md                  # Build + Audit workflow
    │   └── reference/mcp-patterns.md
    ├── mutation-testing/
    │   ├── SKILL.md
    │   └── reference/mutation-operators.md
    ├── node-service/
    │   ├── SKILL.md
    │   └── reference/node-patterns.md
    ├── obsidian-plugin/
    │   ├── SKILL.md                  # Build + Audit workflow
    │   └── reference/obsidian-api.md
    ├── python-project/
    │   ├── SKILL.md
    │   └── reference/python-patterns.md
    ├── react-testing/
    │   ├── SKILL.md
    │   └── reference/react-patterns.md
    ├── test-design-reviewer/
    │   └── SKILL.md
    ├── testing/
    │   └── SKILL.md
    ├── twelve-factor/
    │   ├── SKILL.md
    │   └── reference/twelve-factor-checklist.md
    └── typescript-strict/
        ├── SKILL.md
        └── reference/strict-config.md
```

---

## Plugin Manifest Contract

```json
{
  "name": "tcs-patterns",
  "version": "1.0.0",
  "description": "Domain pattern skills for TCS projects. Install only the patterns relevant to your stack.",
  "author": { "name": "Marcus Breiden" },
  "keywords": ["patterns", "ddd", "hexagonal", "typescript", "testing", ...]
}
```

Skills are discovered by Claude Code via the `skills/` directory convention — no explicit
skills registration field is needed in plugin.json for directory-based plugins.

---

## Skill Format Contract

Every skill in tcs-patterns follows PICS structure:

### Frontmatter

```yaml
---
name: skill-name                # matches directory name
description: "Trigger conditions only — when to use this skill, not what it does."
user-invocable: true
argument-hint: "[optional args]"
allowed-tools: Read, Bash, Grep, Glob
---
```

**Description rule:** The description is the activation trigger for Claude Code. It must
describe *when* to invoke the skill, not *what* the skill contains. Agents read the
description to decide whether to call the skill — never the body.

### PICS Sections

```
## Persona
Act as a [domain] specialist. One or two sentences establishing the expert role.
Adapted from [Source] if applicable.

## Interface
Typed interfaces for violations/findings (for audit skills) or state (for all).

## Constraints
Always/Never rules. These are the non-negotiables of the domain.

## Workflow
Step-by-step guidance. Reference reference/ files at decision points.
For skills that both build and audit: Entry Point match + separate numbered sections.
```

### Progressive Disclosure Pattern

```
skills/[name]/
├── SKILL.md           # Core — always loaded. Persona, interface, constraints, workflow.
└── reference/
    ├── [topic-1].md   # Deep content — loaded when that topic is needed.
    └── [topic-2].md
```

Reference files contain: checklists, anti-pattern tables, code templates, worked examples,
configuration snippets. They are referenced from the workflow with explicit
`Read reference/[file].md` instructions.

### Skill Types in tcs-patterns

| Type | Workflow | Examples |
|---|---|---|
| **Audit** | Scans code, finds violations, reports with file:line | ddd, hexagonal, typescript-strict |
| **Build + Audit** | Build path scaffolds from scratch; Audit path reviews existing | mcp-server, obsidian-plugin |
| **Advisory** | Checklist-driven guidance, no code scanning | twelve-factor, testing |
| **Dispatch** | Identifies need, then delegates implementation to tcs-team agent | twelve-factor → build-platform |

---

## Skill Inventory

| Skill | Type | Source | Reference Files | Status |
|---|---|---|---|---|
| `api-design` | Audit | TCS-native | api-patterns.md | ✅ |
| `ddd` | Audit | citypaul | 7 reference files | ✅ |
| `event-driven` | Audit | TCS-native | event-patterns.md | ✅ |
| `frontend-testing` | Audit | citypaul | testing-patterns.md | ✅ |
| `functional` | Audit | citypaul | functional-patterns.md | ✅ |
| `go-idiomatic` | Audit | TCS-native | go-patterns.md | ✅ |
| `hexagonal` | Audit | citypaul | 6 reference files | ✅ |
| `mcp-server` | Build+Audit | TCS-native | mcp-patterns.md | ✅ |
| `mutation-testing` | Audit | citypaul | mutation-operators.md | ✅ |
| `node-service` | Audit | TCS-native | node-patterns.md | ✅ |
| `obsidian-plugin` | Build+Audit | TCS-native | obsidian-api.md | ✅ |
| `python-project` | Audit | TCS-native | python-patterns.md | ✅ |
| `react-testing` | Audit | citypaul | react-patterns.md | ✅ |
| `test-design-reviewer` | Audit | Andrea Laforgia via citypaul | — | ✅ (self-contained) |
| `testing` | Advisory | citypaul | — | ✅ (self-contained) |
| `twelve-factor` | Advisory+Dispatch | citypaul | twelve-factor-checklist.md | ✅ |
| `typescript-strict` | Audit | citypaul | strict-config.md | ✅ |

All 17 skills have reference/ files. ✅

---

## Architecture Decisions

### ADR-1: Pure Markdown — No Runtime

**Choice:** All 17 skills are markdown only. No TypeScript, no Python scripts, no agents.

**Rationale:** Domain knowledge does not change at runtime. A DDD checklist is the same
every session. Markdown is readable, diffable, and has zero installation surface. Skills
that need to run code (audit scans) use Bash tool via Claude Code's built-in execution.

**Trade-offs:** Cannot do semantic analysis or call external APIs. Complex checks that
would benefit from a real parser (e.g. AST-based DDD boundary detection) are out of scope.
Future: post-M3 agents could provide deeper analysis.

---

### ADR-2: Reference/ Progressive Disclosure

**Choice:** Deep content lives in `reference/` subdirectories, not inline in SKILL.md.

**Rationale:** CON-2 (25 KB limit). More importantly: loading domain deep-dives for every
invocation wastes context. Skills should load only what the current step needs.

**Pattern:** SKILL.md workflow steps explicitly `Read reference/[file].md` at the point
where that content is needed — never front-loaded.

---

### ADR-3: Selective Install — All 17 Shipped, User Picks

**Choice:** Plugin ships all 17 skills in one repo; `install.sh` offers per-skill selection.

**Rationale:** Centralised authoring and maintenance. Users in a Go shop don't need
`react-testing`; users in a React shop don't need `go-idiomatic`. Selective install keeps
each project's Claude Code context lean.

**Alternative rejected:** Separate repos per skill family — too much maintenance overhead
for what is essentially a documentation library.

---

### ADR-4: Build + Audit Dual Workflow for mcp-server / obsidian-plugin

**Choice:** mcp-server and obsidian-plugin have two workflow paths: Build (scaffold from
scratch) and Audit (review existing code). Entry point dispatches based on `$ARGUMENTS`.

**Rationale:** These are platform-specific skills where developers start from zero as often
as they inherit existing code. A pure audit skill is not useful when there is nothing to
audit yet.

**Pattern:**
```
match ($ARGUMENTS) {
  empty | "build"  => Build workflow
  file path        => Audit workflow
}
```

---

### ADR-5: twelve-factor Dispatches to tcs-team:the-devops:build-platform

**Choice:** The `twelve-factor` skill is advisory — it identifies gaps but dispatches
implementation remediation to `tcs-team:the-devops:build-platform`.

**Rationale:** twelve-factor compliance work (Dockerfiles, CI pipelines, env config) is
infrastructure implementation, not domain knowledge guidance. tcs-team's build-platform
agent is the right specialist. tcs-patterns should stay advisory.

---

### ADR-6: event-driven, api-design, go-idiomatic, node-service, python-project, mcp-server, obsidian-plugin are TCS-native

**Choice:** These 7 skills have no external source — authored directly for TCS needs.

**Rationale:** The citypaul/.dotfiles source covers architecture + frontend testing well.
Platform patterns (Node.js, Python, Go) and integration patterns (MCP, Obsidian) are TCS
requirements not covered by that source. They follow the same PICS format as citypaul-derived
skills — no special treatment.

---

## Source Attribution

Full attribution: `docs/concept/sources.md` — citypaul section.

| Skill(s) | Source |
|---|---|
| ddd, hexagonal, functional, typescript-strict, mutation-testing, frontend-testing, react-testing, twelve-factor, testing | Paul Dobbins (citypaul/.dotfiles) |
| test-design-reviewer | Andrea Laforgia (andlaf-ak/claude-code-agents), via citypaul |
| event-driven, api-design, go-idiomatic, node-service, python-project, mcp-server, obsidian-plugin | TCS-native |

---

## Open Items (Post-M3)
- Consider tcs-team agents for deep AST-based analysis (DDD boundary violations, etc.)
