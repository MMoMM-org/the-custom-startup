# Quick Start

You've installed TCS. This walkthrough takes you through your first complete workflow in under 30 minutes.

**Prerequisites:** TCS installed ([Installation](installation.md)) · Claude Code running · A project to work with

---

## Step 1: Set your output style

```bash
/output-style tcs-workflow:The Startup    # high-signal, fast-paced — good for active builds
/output-style tcs-workflow:The ScaleUp   # structured, process-oriented — good for team reviews
```

Pick one and run it at the start of your Claude session. You can switch at any time.

---

## Step 2: (Optional) Set up governance

```bash
/constitution
```

Creates a `CONSTITUTION.md` at your project root that defines enforceable coding, architecture, and process rules — auto-checked during implementation. Optional, but recommended for teams.

---

## Step 3: Specify your first feature

```bash
/xdd Add user authentication
```

This kicks off the XDD (eXtended Design & Development) workflow: Claude researches your codebase, asks you clarifying questions, and produces three linked documents — PRD, SDD, and PLAN — before any code is written. It's interactive; Claude will ask questions along the way.

The spec lands in `docs/XDD/specs/001-user-authentication/` (the directory name reflects your feature).

> **Tip:** `/xdd` orchestrates the full pipeline automatically (PRD → SDD → Plan). If you want more control over individual phases, invoke them directly: `/xdd-prd`, `/xdd-sdd`, `/xdd-plan`.

---

## Step 4: Validate before building

```bash
/validate 001
```

Checks the spec for completeness, consistency, and correctness before you invest implementation time.

---

## Step 5: Implement

```bash
/implement 001
```

Executes the plan phase by phase using parallel agents. Claude pauses for your confirmation between phases. TDD is enforced automatically — the `tdd-guardian` agent blocks production code until a failing test exists for each task.

---

## Step 6: Review

```bash
/review
```

Runs four parallel specialist agents — security, performance, quality, and tests — and surfaces their findings in one consolidated report.

---

## What's next

- [Workflow reference](workflow.md) — full BUILD loop, all commands, and the XDD workflow in detail
- [Skills reference](../reference/skills.md) — all 20 skills with usage notes
- [tcs-patterns guide](../guides/tcs-patterns.md) — optional domain pattern skills (DDD, hexagonal, TypeScript strict, and more)
