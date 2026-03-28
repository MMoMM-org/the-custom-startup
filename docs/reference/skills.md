# Skills Reference

All 20 skills provided by the `tcs-workflow` plugin.

---

## Decision Tree

```
What do you need to do?
│
├─ Set project-wide rules? ────────────────► /constitution
│
├─ Orient after a context reset? ──────────► /guide
│
├─ Explore an idea before building? ───────► /brainstorm
│
├─ Build something new?
│   ├─ Write spec ──────────────────────────► /xdd
│   │   (or step by step: /xdd-prd → /xdd-sdd → /xdd-plan)
│   ├─ Check spec quality ──────────────────► /validate
│   └─ Execute plan ────────────────────────► /implement
│       └─ Enforce TDD per task ────────────► /xdd-tdd
│
├─ Understand existing code? ───────────────► /analyze
│   └─ Want to improve it? ─────────────────► /refactor
│
├─ Something is broken? ────────────────────► /debug
│
├─ Verify a task is done? ──────────────────► /verify
│
├─ Need tests to pass? ─────────────────────► /test
│
├─ Code ready for merge?
│   ├─ Run review ──────────────────────────► /review
│   └─ Process incoming feedback ───────────► /receive-review
│
├─ Run independent tasks in parallel? ──────► /parallel-agents
│
└─ Need documentation? ─────────────────────► /document
```

---

## Command Reference

### Setup

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/constitution` | tcs-workflow | Create or update a project constitution with governance rules | Establish guardrails before any building begins |

### XDD Workflow

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/xdd` | tcs-workflow | Orchestrates xdd-prd → xdd-sdd → xdd-plan workflow | Any new feature or significant change — full spec in one command |
| `/xdd-meta` | tcs-workflow | Scaffold, status-check, and manage specification directories | Used internally by `xdd` and `implement`; invoke directly for spec housekeeping |
| `/xdd-prd` | tcs-workflow | Create and validate product requirements documents (PRD) | When writing requirements, user stories, or acceptance criteria |
| `/xdd-sdd` | tcs-workflow | Create and validate solution design documents (SDD) | When designing architecture, interfaces, or technical decisions |
| `/xdd-plan` | tcs-workflow | Create and validate implementation plans (PLAN) | When sequencing work, defining phases, or analyzing dependencies |
| `/xdd-tdd` | tcs-workflow | Enforce the RED-GREEN-REFACTOR cycle per implementation task | At the start of each task — blocks production code until a failing test exists |

### Build

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/implement` | tcs-workflow | Executes the implementation plan from a specification | After spec is validated — loops through phases and delegates to specialists |
| `/validate` | tcs-workflow | Validate specifications, implementations, constitution compliance, or understanding | Before starting implementation; also after to check for drift |

### Quality

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/test` | tcs-workflow | Run tests and enforce strict code ownership | After implementation, when fixing bugs, or after refactoring |
| `/review` | tcs-workflow | Multi-agent code review with specialized perspectives (security, performance, patterns, simplification, tests) | Before merging a branch |
| `/receive-review` | tcs-workflow | Process incoming code review feedback — classifies each item as Accept, Push Back, Defer, or Question | When acting on feedback from a human reviewer or `/review` output |

### Maintain

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/analyze` | tcs-workflow | Discover and document business rules, technical patterns, and system interfaces | Understanding existing code before changing it |
| `/debug` | tcs-workflow | Systematically diagnose and resolve bugs through conversational investigation and root cause analysis | When something is broken |
| `/document` | tcs-workflow | Generate and maintain documentation for code, APIs, and project components | After implementation; during audits |
| `/refactor` | tcs-workflow | Refactor, simplify, or clean up code for improved maintainability without changing business logic | Cleanup without behavior change |

### Coordination

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/parallel-agents` | tcs-workflow | Validate task independence, detect file conflicts, and fan out agents concurrently | When multiple independent tasks can run at the same time |
| `/guide` | tcs-workflow | Read the current branch and open plan to orient around current state | At session start or after a context reset |

### Authoring

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/brainstorm` | tcs-workflow | Explore intent, requirements, and design through dialogue before implementation begins | Before writing a spec — validates ideas and surfaces design alternatives |
| `/verify` | tcs-workflow | Require actual command output from tests, builds, or lint before marking a task done | When a task is complete and needs evidence before closure |

---

## XDD Skills

The six XDD skills form the spec-driven workflow at the heart of the `tcs-workflow` plugin. They move a feature from idea to buildable plan in three stages:

1. **xdd-prd** — captures what to build (requirements, user stories, acceptance criteria)
2. **xdd-sdd** — captures how to build it (architecture, interfaces, technical decisions)
3. **xdd-plan** — sequences the work into phases with TDD structure and compliance gates
4. **xdd-meta** — manages the spec directory lifecycle (IDs, README tracking, phase transitions)
5. **xdd-tdd** — enforces RED-GREEN-REFACTOR at the task level during implementation
6. **xdd** — orchestrator that runs xdd-prd → xdd-sdd → xdd-plan in a single command

The standard workflow is: `/xdd` → `/validate` → `/implement`. Invoke the sub-skills individually when you need finer control over a single stage.

For full XDD workflow documentation see [`xdd.md`](xdd.md)

---

For full agent reference with per-agent descriptions see [`agents.md`](agents.md)
