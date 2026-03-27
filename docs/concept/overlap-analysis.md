# Overlap Analysis: TCS v2 Absorption Plan

**Status:** Concept document — approved design for TCS v2
**Sources analyzed:** obra/superpowers, citypaul/.dotfiles, centminmod/my-claude-code-setup
**Session:** 2026-03-24

---

## Decision Framework

Each skill/agent/concept from the source repos falls into one of four categories:

| Action | Meaning |
|---|---|
| **ABSORB** | New capability TCS lacks — create new skill/agent |
| **MERGE** | TCS has equivalent — enhance existing skill with best ideas |
| **DEPRECATE** | Source skill superseded by richer TCS equivalent |
| **SKIP** | Too platform-specific, language-specific, or not worth the weight |

---

## obra/superpowers

### ABSORB — New skills in `tcs-workflow`

| Superpowers skill | New TCS skill | Why |
|---|---|---|
| `test-driven-development` | `tcs-workflow:tdd` | Iron law RED-GREEN-REFACTOR discipline; TCS `/test` runs suites but doesn't enforce test-first |
| `receiving-code-review` | `tcs-workflow:receive-review` | TCS has no equivalent; responding to feedback with technical rigor vs. performative agreement |
| `verification-before-completion` | `tcs-workflow:verify` | Evidence-before-claims gate; prevents hallucinated success claims before committing |
| `using-git-worktrees` | `tcs-helper:git-worktree` | Optional utility; isolated workspaces for parallel feature branches |
| `finishing-a-development-branch` | `tcs-helper:finish-branch` | Optional utility; merge/PR/discard decision workflow at end of branch work |
| `dispatching-parallel-agents` | `tcs-workflow:parallel-agents` | Explicit parallel dispatch patterns; supplements implement's parallel mode |

### MERGE — Enhance existing TCS skills

| Superpowers skill | TCS skill to enhance | What to extract |
|---|---|---|
| `brainstorming` | `tcs-workflow:brainstorm` | Add spec-review subagent loop after design approval; enforce `writing-plans` handoff pattern |
| `systematic-debugging` | `tcs-workflow:debug` | Add iron-law discipline: no fixes without root cause investigation first; anti-shortcut table |
| `requesting-code-review` | `tcs-workflow:review` | Add precise subagent dispatch pattern with BASE_SHA/HEAD_SHA context; issue severity categories |
| `subagent-driven-development` | `tcs-workflow:implement` | Extract fresh-subagent-per-task pattern + two-stage review (spec compliance → code quality) |
| `writing-skills` | `tcs-helper:skill-author` | Add PICS structure verification; skill review dispatch pattern |

### DEPRECATE — Superpowers skills superseded by TCS

| Superpowers skill | TCS replacement | Notes |
|---|---|---|
| `writing-plans` | `tcs-workflow:specify-plan` | TCS plan is more structured; extract 2-5min task granularity principle |
| `executing-plans` | `tcs-workflow:implement` | TCS implement has phase management, agent teams, drift detection |
| `brainstorming` | `tcs-workflow:brainstorm` | After merge, superpowers version is redundant |

### SKIP

| Superpowers skill | Reason |
|---|---|
| `using-superpowers` | Replaced by `tcs-workflow:guide` (new orientation skill for TCS) |

---

## citypaul/.dotfiles

### ABSORB — New domain skills in `tcs-patterns` plugin

| citypaul skill | TCS home | Notes |
|---|---|---|
| `domain-driven-design` | `tcs-patterns:ddd` | Architecture patterns; not in TCS today |
| `hexagonal-architecture` | `tcs-patterns:hexagonal` | Ports-and-adapters pattern; not in TCS today |
| `functional` | `tcs-patterns:functional` | Immutable/functional programming patterns |
| `typescript-strict` | `tcs-patterns:typescript-strict` | TypeScript strict mode enforcement |
| `mutation-testing` | `tcs-patterns:mutation-testing` | Complements TDD; catches weak tests |
| `front-end-testing` | `tcs-patterns:frontend-testing` | Frontend-specific test patterns |
| `react-testing` | `tcs-patterns:react-testing` | React-specific (can be added as needed) |
| `twelve-factor` | `tcs-patterns:twelve-factor` | 12-factor app compliance patterns |

These become a 4th plugin: `tcs-patterns` — optional domain knowledge library. Projects adopt only the patterns relevant to their stack.

### ABSORB — New agents in `tcs-team`

| citypaul agent | TCS home | Notes |
|---|---|---|
| `adr.md` | `tcs-team:the-architect/record-decision.md` | Architecture Decision Records; distinct from CLAUDE.md rules |
| `progress-guardian.md` | Merge into `specify-meta` + `implement` | Plan-file progress tracking; track task state across sessions |

### ABSORB — New skills in `tcs-helper`

| citypaul concept | TCS home | Notes |
|---|---|---|
| `/setup` command | `tcs-helper:setup` | Generates project-specific CLAUDE.md + hooks + agents from stack detection |

### MERGE — Enhance existing TCS

| citypaul element | TCS skill to enhance | What to extract |
|---|---|---|
| TDD enforcement philosophy | `tcs-workflow:tdd` | 100% coverage documentation process; TDD evidence format for PRs; PR requirements checklist |
| `planning/SKILL.md` task format | `tcs-workflow:specify-plan` | Explicit RED/GREEN/REFACTOR/MUTATE steps per task in plan files |
| `pr-reviewer.md` pattern | `tcs-team:the-architect/code-reviewer.md` | Add TDD compliance dimension to review checklist |

### SKIP

| citypaul element | Reason |
|---|---|
| `expectations/SKILL.md` | Very specialized; defer unless needed |
| `ci-debugging/SKILL.md` | Narrowly scoped; covered by debug + TCS test skill |
| `test-design-reviewer/SKILL.md` | Useful but defer; may emerge naturally from tdd + review combination |

---

## claude-reflect (existing plugin)

### INTEGRATE — Foundation for `tcs-helper:memory`

`tcs-helper:memory` does not replace claude-reflect. It extends it, following the same pattern as `/miyo-reflect`.

| claude-reflect capability | Role in TCS |
|---|---|
| `/reflect` correction capture + routing | Base layer — unchanged, used as-is |
| Learning destinations model (global/project/local/rules) | Maps to TCS g/p/r scope layers |
| `/reflect-skills` session pattern analysis | **Internalized into `/memory promote`** — not called separately |
| `/miyo-reflect` extension pattern | Architectural template for `/memory route` |

`/memory promote` calls reflect-skills analysis internally and scopes results to `.claude/memory/domain.md` patterns → proposes tcs-patterns skill candidates.

---

## centminmod/my-claude-code-setup

### ABSORB — Memory system in `tcs-helper`

| centminmod concept | TCS home | Notes |
|---|---|---|
| Memory bank CLAUDE-*.md files | `tcs-helper:memory` | Repo-level typed memory (general, tools, domain, context, troubleshooting, decisions); directory structure TBD in dedicated session |
| `cleanup-context.md` | `tcs-helper:memory route` (cleanup mode) | Token reduction workflow; prune stale memory, archive resolved issues |
| `/update-memory-bank` command | `/memory sync` mode | Triggered update + CLAUDE.md import sync |

All three layers unified under one skill: global user facts (auto-memory, existing) + project session facts (auto-memory, existing) + repo-level typed files (new). `/reflect` handles capture; `/memory` handles everything TCS-specific on top.

### ABSORB — New skills in `tcs-helper`

| centminmod skill/command | TCS home | Notes |
|---|---|---|
| `claude-docs-consultant` | `tcs-helper:docs` | On-demand docs.claude.com fetcher; better than embedding docs in CLAUDE.md |
| CLAUDE.md tech-stack templates | `docs/templates/` | Consumed by `tcs-helper:setup`; Cloudflare, Convex starters |

### MERGE — Enhance existing TCS

| centminmod concept | TCS skill to enhance | What to extract |
|---|---|---|
| CoD (Chain of Draft) mode | `tcs-workflow:analyze` | Token-efficient codebase search notation; optional mode flag |
| `batch-operations-prompt` | `tcs-workflow:parallel-agents` | Explicit parallel/sequential phasing; conflict grouping patterns |

### SKIP

| centminmod element | Reason |
|---|---|
| `consult-codex` / `consult-zai` | Platform-specific (OpenAI Codex, z.ai GLM); not relevant to TCS |
| `get-current-datetime` agent | Trivial; use Bash `date` inline |

---

## New Skills Summary

### `tcs-workflow` (renamed from tcs-start)
New skills to add:
- `tdd` — RED-GREEN-REFACTOR iron law
- `receive-review` — respond to code review with rigor
- `verify` — evidence-before-completion gate
- `parallel-agents` — explicit parallel dispatch patterns
- `guide` — orientation skill (when to use each skill in the workflow)

### `tcs-team` (unchanged name)
New agents to add:
- `the-architect/record-decision.md` — Architecture Decision Records

### `tcs-helper` (expanded from skill-author only)
New skills to add:
- `memory` — unified memory management (3 layers)
- `setup` — project onboarding wizard
- `git-worktree` — isolated branch workspaces
- `finish-branch` — merge/PR decision workflow
- `docs` — on-demand documentation fetcher
- `evaluate` — score new skills/agents against TCS vision (todo #4)
- `import-skill` — fetch and evaluate skills from GitHub repos (todo #5)

### `tcs-patterns` (new plugin)
New domain knowledge skills:
- `ddd`, `hexagonal`, `functional`, `typescript-strict`
- `mutation-testing`, `frontend-testing`, `react-testing`, `twelve-factor`
