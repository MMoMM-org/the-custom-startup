# Concepts

This page explains how The Custom Agentic Startup works and how its pieces fit together. Read this first — everything else in the docs assumes you understand these building blocks.

→ For hands-on usage, see [workflow.md](workflow.md) and [skills.md](skills.md).

---

## The Core Idea

**Specify first. Then build.**

Most AI-assisted development jumps straight to code. The Agentic Startup flips that: you write a comprehensive specification first, get alignment on *what* and *how*, then execute with confidence. The AI builds what you actually meant — not what it guessed.

This isn't extra work. A spec catches ambiguity early, when it's cheap to fix. Finding a misunderstanding in a document takes minutes. Finding it in production code takes days.

```
You have an idea
       │
       ▼
  Write a spec        ← /specify
  (what + how + plan)
       │
       ▼
  Check quality       ← /validate
       │
       ▼
  Execute the plan    ← /implement
  (parallel agents)
       │
       ▼
  Verify & ship       ← /test → /review → /document
```

---

## The Two Plugins

The framework ships as two Claude Code plugins. They work together but can be installed separately.

### Start Plugin — The Workflow Engine

The `start` plugin is the core. It gives you 10 slash commands that guide you through the full development lifecycle.

```
SETUP
  /constitution    Create project governance rules

BUILD
  /specify         Create a spec (PRD + SDD + Plan)
  /validate        Check spec quality before building
  /implement       Execute the plan, phase by phase

QUALITY
  /test            Run tests, enforce code ownership
  /review          Multi-agent code review

MAINTAIN
  /analyze         Discover patterns in existing code
  /refactor        Improve code without changing behavior
  /debug           Systematic bug investigation
  /document        Generate documentation
```

### Team Plugin — The Specialist Library

The `team` plugin adds a library of 15 specialized agents across 8 roles. These aren't commands you type — they're specialists that activate automatically when `/implement` or `/review` delegates work that needs expertise. → [Full agent reference](agents.md)

| Role | What they do |
|------|-------------|
| **The Chief** | Assesses complexity, routes work, coordinates parallel agents |
| **The Analyst** | Requirements, prioritization, stakeholder alignment |
| **The Architect** | System design, security review, compatibility, robustness |
| **The Developer** | Feature implementation, performance optimization |
| **The Tester** | Test strategy, load testing, coverage analysis |
| **The Designer** | User research, interaction design, accessibility |
| **The DevOps** | Infrastructure, CI/CD, monitoring |
| **The Meta Agent** | Designs and generates new agents |

You don't invoke these directly. When you run `/implement` on a complex plan, The Chief assesses it and dispatches the right specialists — security work goes to The Architect, frontend components to The Developer, and so on — running in parallel where possible.

---

## The Spec — Your Single Source of Truth

When you run `/specify Add user authentication`, Claude creates a directory with three documents:

```
your-specs-dir/001-user-authentication/
├── requirements.md    ← What to build and why
├── solution.md        ← How to build it
└── plan/
    ├── README.md      ← Plan manifest (phases overview)
    ├── phase-1.md     ← First batch of tasks
    └── phase-2.md     ← Second batch, etc.
```

The specs directory location is configurable. The install wizard writes a `.claude/startup.toml` in your project (or `~/.claude/startup.toml` for global use) that tells all skills and scripts where to find your specs. If no config exists, the framework falls back to `the-custom-startup/specs/` → `.start/specs/` → `docs/specs/`. See [workflow.md](workflow.md) for the full path resolution details.

These files are your spec. They persist between Claude sessions, so you can pick up exactly where you left off — even after hitting a context limit.

### requirements.md — What to Build

Defines the feature in terms of observable behavior: what users can do, what the system must guarantee, and what constraints apply. Written in plain language, not implementation details.

```markdown
# Requirements: User Authentication

## Purpose
Allow users to securely log in and maintain persistent sessions.

## Requirements

### Requirement: Login
Users SHALL be able to log in with email and password.

#### Scenario: Successful login
- GIVEN a registered user with valid credentials
- WHEN they submit the login form
- THEN they receive a session token
- AND are redirected to their dashboard

#### Scenario: Wrong password
- GIVEN a registered user
- WHEN they submit an incorrect password
- THEN they see an error message
- AND no session is created
```

**What belongs here:** user-visible behavior, inputs/outputs, error conditions, security constraints.
**What doesn't:** class names, library choices, implementation steps.

### solution.md — How to Build It

Describes the technical approach: architecture decisions, data models, API contracts, key components. This is where you document *how* you'll satisfy the requirements.

```markdown
# Solution Design: User Authentication

## Architecture
JWT-based authentication with refresh tokens stored in httpOnly cookies.

## Data Model
User: { id, email, passwordHash, createdAt, lastLoginAt }
Session: { token, userId, expiresAt, createdAt }

## API Endpoints
POST /auth/login     — validates credentials, issues JWT
POST /auth/logout    — invalidates session
GET  /auth/me        — returns current user from token

## Security Decisions
- bcrypt for password hashing (cost factor 12)
- 15-minute access token expiry
- 7-day refresh token with rotation
```

### plan/ — When and In What Order

The plan breaks the solution into executable phases. Each phase is a set of tasks that can be worked in parallel. Phases run sequentially; tasks within a phase can run simultaneously.

```markdown
# Phase 1: Foundation

## Tasks

### Task 1.1: Database schema
Create users and sessions tables with indexes.
Acceptance: migrations run, tables exist, indexes verified.

### Task 1.2: Password utilities
Implement bcrypt hash and verify functions.
Acceptance: unit tests pass for hash/verify/timing-attack resistance.

### Task 1.3: JWT utilities
Implement sign/verify/decode for access and refresh tokens.
Acceptance: unit tests pass, expiry enforced.
```

---

## The Workflow in Practice

### Starting Fresh

```bash
/specify Add user authentication with OAuth support
```

Claude researches your codebase, asks clarifying questions, and creates all three spec documents. This can take 15–30 minutes for a complex feature. The back-and-forth is the point — it's how you find the gaps before writing code.

### Resuming After a Context Limit

Large specs approach Claude's context window. When that happens, start a new session:

```bash
/specify 001        # pass the spec ID to resume
/implement 001      # same for implementation
```

Claude reads the existing files and continues. You can split PRD → SDD → Plan across multiple sessions if needed.

### Checking Quality Before You Build

```bash
/validate 001
```

Checks three things:
- **Completeness** — no missing sections, no placeholders
- **Consistency** — requirements and solution don't contradict each other
- **Correctness** — requirements are testable, acceptance criteria are clear

Validation is advisory — it gives you recommendations, not a hard block.

### Executing the Plan

```bash
/implement 001
```

Claude works through each phase:
1. Reads the phase tasks
2. Dispatches parallel agents for independent tasks (if Team plugin is installed)
3. Runs tests after each task
4. Asks for approval before moving to the next phase

If implementation drifts from the spec (scope creep, missing items, contradictions), Claude flags it and gives you options: update the spec, adjust the code, or note it as a decision.

### Reviewing Before Merge

```bash
/review
```

Four specialists review your code simultaneously:
- **Security** — authentication, authorization, input validation
- **Performance** — queries, memory, concurrency
- **Quality** — patterns, maintainability, design
- **Tests** — coverage, edge cases, missing scenarios

Claude auto-detects what matters: async code triggers concurrency review, dependency changes trigger supply-chain checks, UI changes trigger accessibility audits.

---

## What Belongs Where

A common question: *when do I edit the spec vs. let Claude handle it?*

| Situation | What to do |
|-----------|-----------|
| Feature request is vague | Run `/specify`, let Claude ask the questions |
| You know exactly what you want | Start with `/specify` and give Claude a detailed description |
| Implementation is drifting from spec | `/implement` flags it — choose to update spec or code |
| Bug found during implementation | Run `/debug`, fix it, continue `/implement` |
| Tests are failing | Run `/test` — it fixes what it touches, period |
| Code works but is messy | Run `/refactor` — behavior is preserved |
| Need to understand existing code | Run `/analyze` before writing any spec |

---

## Key Concepts at a Glance

**Spec-driven development** — write the plan before writing the code. The spec is the source of truth; the code implements it.

**Persistent specs** — specs live as plain markdown files in your configured specs directory (set via `.claude/startup.toml`). They survive context resets, session boundaries, and team handoffs.

**Phase-based execution** — plans run phase by phase with your approval between phases. Tasks within a phase can run in parallel. → [How /implement works](workflow.md)

**Progressive disclosure** — skills and agents load only what they need, when they need it. All 10 commands are available without consuming your context budget.

**Code ownership** — when [`/test`](skills.md#test) finds a failing test, it fixes it. No "pre-existing failure" excuses. You touched the codebase, you own it.

**Drift detection** — [`/implement`](skills.md#implement) monitors whether the code being written matches the spec. Deviations are flagged early, not discovered in review.

---

## Next Steps

| You want to... | Read... |
|----------------|---------|
| See the full workflow step by step | [workflow.md](workflow.md) |
| Understand each skill in detail | [skills.md](skills.md) |
| Learn about the specialist agents | [agents.md](agents.md) |
| See all plugins and what they include | [plugins.md](plugins.md) |
| Understand the design philosophy | [PHILOSOPHY.md](PHILOSOPHY.md) |
