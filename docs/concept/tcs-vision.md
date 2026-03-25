# TCS v2 Vision

**Status:** North star document — use to evaluate new skills, agents, and concepts
**Session:** 2026-03-24

---

## What TCS v2 Is

**The Custom Startup v2** is a complete spec-driven, test-verified development framework for Claude Code. It covers the full loop from idea to merged code, enforced by a TDD discipline gate between design and implementation.

**Core philosophy:**
- **SDD defines contracts. TDD verifies them.** No gap between design and code.
- **Spec-driven, not ad-hoc.** Every feature starts with a specification; implementation follows a plan.
- **Evidence over claims.** No task is "done" until tests pass and output is verified.
- **Progressive disclosure.** Load only what's needed; avoid context bloat.
- **YAGNI ruthlessly.** Minimum complexity to solve the current problem.

---

## Plugin Architecture

TCS v2 consists of four plugins. Install only what you need.

### `tcs-workflow` (core — required)
The spec-to-ship pipeline. Replaces `tcs-start`.

**Primary workflow:**
```
/guide          → orientation: when to use each skill
/brainstorm     → socratic design refinement (with spec-review loop)
/specify        → PRD → SDD (contracts) → PLAN (TDD-structured tasks)
/implement      → orchestrates: fresh subagent per task + two-stage review
/tdd            → RED-GREEN-REFACTOR iron law (called by implement)
/verify         → evidence-before-claims gate (called by implement)
/test           → full suite + quality checks
/review         → code review dispatch + TDD compliance
/receive-review → respond to feedback with technical rigor
/finish-branch  → merge / PR / discard decision at branch completion
```

**Supporting skills:**
```
/debug          → 4-phase root cause investigation
/refactor       → behavior-preserving code improvements
/validate       → drift detection, spec compliance, constitution checks
/analyze        → codebase discovery and pattern documentation
/document       → documentation generation
/constitution   → define and enforce project governance rules
/parallel-agents → explicit parallel agent dispatch patterns
```

### `tcs-team` (specialist agents — recommended)
15+ specialist agents organized by role. Invoked via Task tool by orchestrator skills.

**Roles:** the-chief, the-analyst, the-architect, the-developer, the-designer, the-tester, the-devops, the-meta-agent

**New in v2:** `the-architect/record-decision` (Architecture Decision Records)

### `tcs-helper` (optional tooling — install as needed)
Development utilities that aren't core workflow.

```
/skill-author   → create and audit skills
/memory         → unified memory management (3 layers: global, project, repo)
/setup          → project onboarding wizard (generates CLAUDE.md + hooks + agents)
/git-worktree   → isolated branch workspaces for parallel work
/finish-branch  → moved here if not using tcs-workflow
/docs           → on-demand documentation fetcher (docs.claude.com)
/evaluate       → score new skills/agents against TCS vision
/import-skill   → fetch and evaluate skills from GitHub repos
```

### `tcs-patterns` (domain knowledge — install per project)
Optional domain skill library. Install only patterns relevant to your stack.

```
/ddd                → Domain-Driven Design patterns
/hexagonal          → Hexagonal architecture (ports and adapters)
/functional         → Functional/immutable programming patterns
/typescript-strict  → TypeScript strict mode enforcement
/mutation-testing   → Mutation testing to strengthen test suites
/frontend-testing   → Frontend-specific test patterns
/react-testing      → React component and hook testing
/twelve-factor      → 12-factor app compliance
```

---

## Workflow in Detail

### The Hard Gate

```
DESIGN PHASE                    IMPLEMENTATION PHASE
─────────────────               ─────────────────────
/brainstorm                     /implement
/specify                            for each task:
  PRD (what)                          /tdd (RED: write failing test)
  SDD (contracts) ──────────────────► tests anchor to SDD contracts
  PLAN (TDD tasks)                    /tdd (GREEN: minimal implementation)
                                      /tdd (REFACTOR: clean up)
                                      /verify (evidence gate)
                                  /test (full suite)
                              /review
                              /receive-review
                              /finish-branch
```

The hard gate is at the transition from PLAN to implement: no implementation task starts without a corresponding SDD contract and a PLAN task with explicit RED/GREEN/REFACTOR steps.

### `/guide` Skill

A new orientation skill (analogous to `superpowers:using-superpowers`) that:
- Explains when to invoke each skill
- Describes the full workflow loop
- Provides decision trees for common situations (solo feature, bug fix, refactor, emergency patch)
- Loaded automatically on first use via SessionStart hook

---

## Memory System

Three layers, managed by `tcs-helper:memory`. Each layer has a different **scope** (who it applies to) and **category** (what type of knowledge it holds).

### Layers × Categories

Memory is organized on two axes: **scope** (global / project / repo) and **category** (general, tools, domain).

| Category | Global `~/.claude/` | Project `~/.claude/projects/*/memory/` | Repo `.claude/memory/` |
|---|---|---|---|
| **general** | Personal style, cross-project conventions (`memory-preferences.md`) | Project-wide conventions, workflow decisions | Repo-specific patterns, naming, code style |
| **tools** | Always-used integrations you own (Jira, Snowflake, Slack quirks) | — | Codebase-specific tooling (CI scripts, API client, deployment quirks) |
| **domain** | Pointers to promoted `tcs-patterns` skills | Cross-repo domain models (e.g. MiYo architecture) | Business rules, data models, architectural decisions for this repo |
| **context** | — | Session history, active goals (auto-memory) | Active session state, current branch context |
| **troubleshooting** | — | — | Known issues and proven solutions for this repo |

### The Reflect Stack

The memory system is built on three existing tools, layered together:

```
claude-reflect  (/reflect)       — capture corrections, route to correct destination
miyo-reflect    (/miyo-reflect)  — proof-of-concept: reflect extended with repo-specific routing
reflect-skills  (/reflect-skills) — promote repeating patterns into skills
```

`tcs-helper:memory` does NOT build a new capture system. It extends claude-reflect with:
- **g/p/r routing awareness** — knows which layer (global / project / repo) a learning belongs to
- **Category routing** — routes to the correct file within a layer (tools.md, domain.md, etc.)
- The same extension pattern `/miyo-reflect` already uses for MiYo repos

### Domain Knowledge Lifecycle

Domain knowledge follows a promotion path. `/reflect-skills` IS the promotion mechanism — it already implements this loop:

```
1. Staging    → corrections/learnings routed to .claude/memory/domain.md via /reflect
                session patterns accumulate over time

2. Detection  → /reflect-skills scans session history, identifies repeating domain patterns
                semantically (intent-matching, not keyword-matching)

3. Promotion  → user approves → skill file generated (tcs-patterns candidate)
                e.g. domain knowledge about hexagonal architecture → tcs-patterns:hexagonal

4. Pointer    → domain.md entry replaced with: "see tcs-patterns:hexagonal"
                domain.md shrinks; CLAUDE.md shrinks; skill handles the knowledge
```

This is the organic growth path for `tcs-patterns`: skills aren't designed top-down, they're promoted bottom-up from actual session patterns. `/reflect-skills` automates the detection step.

**Why this matters for file size:** Every pattern that gets promoted removes content from CLAUDE.md and memory files. Conneely reduced his CLAUDE.md from 189 to 63 lines this way. The same mechanism scales: more sessions → more patterns detected → more promotions → leaner memory files.

### What `tcs-helper:memory` Provides

All memory operations live in one skill, invoked with a mode argument:

```
/memory route    → after /reflect: routes learnings into the correct .claude/memory/ category file
                   (tools.md, domain.md, general.md, context.md, troubleshooting.md)
                   this is the repo-layer extension of /reflect, analogous to /miyo-reflect

/memory sync     → ensure .claude/memory/*.md files are @imported in project CLAUDE.md
                   keeps routing rules in CLAUDE.md, not in the 200-line MEMORY.md budget

/memory cleanup  → prune stale entries, archive resolved troubleshooting, reduce token load

/memory promote  → scan .claude/memory/domain.md for repeating patterns (using reflect-skills
                   analysis internally) → propose tcs-patterns skill candidates → on approval,
                   generate skill file and replace memory entry with a pointer
```

Post-session flow (analogous to `/miyo-reflect` for MiYo):
```
/reflect         → processes correction queue via claude-reflect (unchanged)
/memory route    → routes repo learnings to .claude/memory/ category files   ← TCS extension
/memory promote  → (periodically) promote mature domain patterns to skills
```

`/reflect` stays as the base capture layer. `/memory` handles everything TCS-specific on top of it.

### Routing Rules (in CLAUDE.md, not in MEMORY.md)

Per Conneely: routing rules belong in CLAUDE.md (always loaded), not in the 200-line MEMORY.md budget. The MEMORY.md index lists what exists; CLAUDE.md tells Claude where to write new learnings.

### Directory Structure

To be finalized in the memory system session. Indicative repo layout:

```
.claude/memory/
├── MEMORY.md          # index (200-line budget; listed in CLAUDE.md @import)
├── general.md         # repo conventions, style
├── tools.md           # codebase-specific tool knowledge
├── domain.md          # business rules, data models
├── decisions.md       # architectural decisions (or links to ADR files)
├── context.md         # active session state, current goals
└── troubleshooting.md # known issues and proven fixes
```

---

## Modular CLAUDE.md Approach

**Philosophy (from citypaul v3.0.0):** Core CLAUDE.md stays lean (~100 lines, philosophy + skill triggers). All detail lives in skills loaded on demand.

**Project-specific CLAUDE.md** generated by `tcs-helper:setup`:
- Detects tech stack (TypeScript, Go, Python, Rust, etc.)
- Generates `.claude/CLAUDE.md` with stack-relevant imports
- Creates project-specific hooks (format on save, lint on edit)
- Configures relevant tcs-patterns imports for the detected stack

**Tech-stack templates** in `docs/templates/`:
- `cloudflare.md` — Cloudflare Workers/Pages project starter
- `convex.md` — Convex database project starter
- `nextjs.md` — Next.js project starter (TBD)
- Templates consumed by `tcs-helper:setup`; never loaded wholesale

---

## Evaluation Criteria for New Skills/Agents

Use this checklist (enforced by `tcs-helper:evaluate`) when considering new skills:

### Uniqueness
- [ ] Does TCS already have a skill/agent that covers this?
- [ ] If overlap exists — is the new skill significantly better, or just different?
- [ ] Does this fill a real gap in the spec-to-ship workflow?

### Fit
- [ ] Does it follow progressive disclosure (SKILL.md + reference/ pattern)?
- [ ] Does it respect YAGNI (no speculative features)?
- [ ] Is it workflow-agnostic enough to work with the TCS pipeline?
- [ ] Does it belong in tcs-workflow, tcs-team, tcs-helper, or tcs-patterns?

### Integration
- [ ] Does it conflict with any existing skill's responsibility?
- [ ] Can it be merged into an existing skill instead of added standalone?
- [ ] Does it have clear trigger conditions (prevents accidental activation)?

### Quality
- [ ] Is the SKILL.md under ~25KB?
- [ ] Are constraints listed as Always/Never?
- [ ] Does it have an Interface section defining its state?

**Score interpretation:**
- 12/12 checks: ABSORB immediately
- 8-11/12: ABSORB with minor adaptation
- 5-7/12: MERGE into existing skill
- <5/12: SKIP or park for later

---

## What TCS v2 Is NOT

- **Not a coding style enforcer.** tcs-patterns handles language/framework conventions. Core TCS is language-agnostic.
- **Not a CI/CD system.** tcs-helper can generate hooks but doesn't manage pipelines.
- **Not a documentation generator.** `/document` exists but is supplementary, not central.
- **Not a project management tool.** Plans are implementation sequencing aids, not sprint boards.
- **Not a replacement for the developer's judgement.** TCS enforces discipline; it doesn't replace thinking.

---

## Pending Decisions (for follow-up sessions)

- [ ] Exact directory structure for `.claude/memory/CLAUDE-*.md` repo layer
- [ ] Whether `tcs-patterns` ships as part of the main marketplace repo or as a separate repo
- [ ] ADR file format and location (docs/adr/ or .claude/adr/)
- [ ] Renaming of existing tcs-start skills to tcs-workflow namespace (migration path for existing users)
- [ ] `tcs-helper:evaluate` scoring algorithm detail
- [ ] `tcs-helper:import-skill` GitHub API integration and transformation rules
