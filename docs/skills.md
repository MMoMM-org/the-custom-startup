# Skills Reference

All 10 slash commands provided by The Agentic Startup.

---

## Decision Tree

```
What do you need to do?
│
├─ Set project-wide rules? ───────────────► /constitution
│
├─ Build something new? ──────────────────► /specify
│                                           then: /validate → /implement
│
├─ Understand existing code? ─────────────► /analyze
│   └─ Want to improve it? ───────────────► /refactor
│
├─ Something is broken? ──────────────────► /debug
│
├─ Need to run tests? ────────────────────► /test
│
├─ Code ready for merge? ─────────────────► /review
│
└─ Need documentation? ───────────────────► /document
```

---

## Command Reference

| Command | Plugin | Purpose | When to use |
|---------|--------|---------|-------------|
| `/constitution` | tcs-start | Create project governance rules | Establish guardrails before building |
| `/specify` | tcs-start | Create specs (PRD + SDD + PLAN) | Any new feature or significant change |
| `/validate` | tcs-start | Check spec quality (3 Cs) | Before starting implementation |
| `/implement` | tcs-start | Execute plan phase-by-phase | After spec is validated |
| `/test` | tcs-start | Run tests, enforce code ownership | After implementation, when fixing bugs |
| `/review` | tcs-start | Multi-agent code review | Before merging |
| `/document` | tcs-start | Generate/sync documentation | After implementation |
| `/analyze` | tcs-start | Discover patterns & business rules | Understanding existing code |
| `/refactor` | tcs-start | Improve code quality | Cleanup without behavior change |
| `/debug` | tcs-start | Root cause analysis & fix | When something is broken |
| `/skill-author` | tcs-helper | Create, audit, or convert skills | Authoring Claude Code skills or agents |

---

## Skill Details

### `/specify`

Creates a full specification from a brief description. Runs three sub-skills in sequence:

1. **specify-requirements** — Product Requirements Document (PRD)
2. **specify-solution** — Solution Design Document (SDD)
3. **specify-plan** — Implementation Plan (phased, TDD-structured)

Pass an ID to resume: `/specify 001`

### `/validate`

Checks specifications or implementations against the 3 Cs:
- **Completeness** — nothing missing
- **Consistency** — no contradictions
- **Correctness** — achievable and testable

Also supports constitution mode: `/validate constitution`

### `/implement`

Reads the plan from `the-custom-startup/specs/[NNN]/plan/` and executes it phase by phase. Tracks progress in spec files so you can resume across context resets.

### `/review`

Launches four specialist agents in parallel:
- Security — OWASP, auth, input validation
- Performance — queries, memory, bundle size
- Quality — patterns, maintainability, style
- Tests — coverage, edge cases, regression risk

### `/constitution`

Creates a `CONSTITUTION.md` at the project root with enforceable rules:
- L1 (Must) — blocking, autofix available
- L2 (Should) — blocking, manual fix required
- L3 (May) — advisory only

### `/brainstorm`

Exploratory skill — use before specifying to validate ideas and design approaches. Not listed in the main table because it's pre-workflow.

---

→ Full agent reference with per-agent descriptions: [agents.md](agents.md)
