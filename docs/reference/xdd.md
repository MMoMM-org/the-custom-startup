# XDD Workflow

Experience-Driven Development (XDD) puts the spec before the code. Before a single line of
implementation is written, you produce three linked documents: a Product Requirements Document
(PRD) that defines *what* to build and *why*, a Solution Design Document (SDD) that defines
*how* to build it, and an implementation Plan that sequences the work phase by phase. Only
after all three are complete does implementation begin. This spec-first discipline makes
implementation predictable and eliminates mid-build clarification cycles.

---

## The Workflow

```
1. Brainstorm   — explore the problem space; clarify goals, scope, and constraints
        |
        v
2. /xdd         — orchestrates the full spec loop:
        |
        |-- xdd-prd  → requirements.md    (WHAT and WHY)
        |-- xdd-sdd  → solution.md        (HOW and WHERE)
        |-- xdd-plan → plan/README.md     (task sequence, per phase files)
        |
        v
3. /validate    — verify the spec against CONSTITUTION.md rules (if present)
        |
        v
4. /implement   — execute the plan phase by phase, task by task (TDD: red → green → refactor)
        |
        v
5. /review      — code review before merging
```

Each phase in step 2 requires user confirmation before proceeding to the next. You can start
at any phase (PRD, SDD, or PLAN) and skip phases your situation does not require. The
`xdd-meta` skill manages spec directory scaffolding and tracks decisions throughout.

---

## XDD Skills

### xdd

**Name:** `xdd`

**Description:** Orchestrates xdd-prd → xdd-sdd → xdd-plan workflow. Manages specification
directory creation, README tracking, and phase transitions.

**When to use it:** Run `/xdd <feature description>` to start a new specification from
scratch, or to continue an existing one. This is the primary entry point for the XDD
workflow — it calls `xdd-prd`, `xdd-sdd`, and `xdd-plan` in sequence and coordinates user
confirmations between phases.

**Key outputs:**
- Delegates to `xdd-meta` to scaffold `docs/XDD/specs/NNN-name/`
- Drives creation of `requirements.md`, `solution.md`, and `plan/README.md` via sub-skills
- Logs design decisions in the spec README throughout the session

---

### xdd-meta

**Name:** `xdd-meta`

**Description:** Scaffold, status-check, and manage specification directories under
`docs/XDD/` (configurable via `.claude/startup.toml`). Handles auto-incrementing IDs,
README tracking, phase transitions, and decision logging. Used by both xdd and implement
workflows.

**When to use it:** Called internally by `xdd` and `implement`. Invoke directly when you
need to check the status of an existing spec (`/xdd-meta 003`), scaffold a new spec
directory without starting the full PRD flow, or log a decision to a spec README.

**Key outputs:**
- `docs/XDD/specs/NNN-name/` directory (auto-incremented ID)
- `docs/XDD/specs/NNN-name/README.md` (spec manifest with phase status and decisions log)

---

### xdd-prd

**Name:** `xdd-prd`

**Description:** Create and validate product requirements documents (PRD). Use when writing
requirements, defining user stories, specifying acceptance criteria, analyzing user needs,
or working on requirements.md files in `docs/XDD/specs/`. Includes validation checklist,
iterative cycle pattern, and multi-angle review process.

**When to use it:** Called by `xdd` during the PRD phase, or invoke directly with
`/xdd-prd` when you need to write or revise requirements for an existing spec. Use this
skill when the question you are answering is *what* to build and *why* — not how.

**Key outputs:**
- `docs/XDD/specs/NNN-name/requirements.md` — PRD with problem statement, personas, user
  journeys, feature requirements (MoSCoW), acceptance criteria, and success metrics

---

### xdd-sdd

**Name:** `xdd-sdd`

**Description:** Create and validate solution design documents (SDD). Use when designing
architecture, defining interfaces, documenting technical decisions, analyzing system
components, or working on solution.md files in `docs/XDD/specs/`. Includes validation
checklist, consistency verification, and overlap detection.

**When to use it:** Called by `xdd` after PRD is approved, or invoke directly with
`/xdd-sdd` to write or revise the technical design for an existing spec. Use this skill
when the question you are answering is *how* to build it — architecture, interfaces, data
models, ADRs.

**Key outputs:**
- `docs/XDD/specs/NNN-name/solution.md` — SDD with architecture decisions (ADRs), component
  design, interface contracts, data models, and traceability back to PRD requirements

---

### xdd-plan

**Name:** `xdd-plan`

**Description:** Create and validate implementation plans (PLAN). Use when planning
implementation phases, defining tasks, sequencing work, analyzing dependencies, or working
on plan files in `docs/XDD/specs/`. Generates per-phase files (plan/README.md +
plan/phase-N.md) for progressive disclosure. Includes TDD phase structure and specification
compliance gates.

**When to use it:** Called by `xdd` after SDD is approved, or invoke directly with
`/xdd-plan` to write or revise the plan for an existing spec. Use this skill to break the
SDD design into executable, sequenced tasks where every task follows the TDD cycle: Prime,
Test, Implement, Validate.

**Key outputs:**
- `docs/XDD/specs/NNN-name/plan/README.md` — phase manifest with a checklist of phase links
- `docs/XDD/specs/NNN-name/plan/phase-N.md` — one file per phase, containing tasks with
  spec references, dependency annotations, and TDD structure

---

### xdd-tdd

**Name:** `xdd-tdd`

**Description:** Use at the start of each implementation task — enforces the RED-GREEN-REFACTOR
cycle and blocks production code until a failing test exists.

**When to use it:** Invoke at the start of each implementation task during the `/implement`
phase. Pass the task description and an optional SDD section reference
(`/xdd-tdd <task> --sdd-ref SDD/Section-X.Y`). This skill enforces the TDD iron law: no
production code is written until a failing test exists, and it will not accept
rationalizations for skipping tests.

**Key outputs:**
- A list of test names to implement (happy path, edge cases, error states)
- Confirmed test file path following project conventions
- Phase gate progression: RED confirmed → GREEN approved → REFACTOR checkpoint → APPROVED

---

## Spec Directory Structure

Each spec lives under `docs/XDD/specs/` in a directory named with a zero-padded three-digit
ID and a kebab-case feature name:

```
docs/XDD/specs/
└── NNN-feature-name/
    ├── README.md          # spec manifest: phase status, decisions log, last updated
    ├── requirements.md    # PRD: what and why (produced by xdd-prd)
    ├── solution.md        # SDD: how and where (produced by xdd-sdd)
    └── plan/
        ├── README.md      # plan manifest: phase checklist with links to phase files
        ├── phase-1.md     # phase 1 tasks with TDD structure and spec references
        ├── phase-2.md     # phase 2 tasks
        └── phase-N.md     # additional phases as needed
```

The `plan/README.md` phase checklist uses this exact format, which is parsed by the
`implement` skill for phase discovery and status tracking:

```markdown
- [ ] [Phase 1: Title](phase-1.md)
- [ ] [Phase 2: Title](phase-2.md)
```

Other directories under `docs/XDD/` are managed by `xdd-meta` but are not part of the
spec for a single feature:

```
docs/XDD/
├── specs/     # one subdirectory per specification (NNN-name/)
├── adr/       # architecture decision records (cross-cutting)
└── ideas/     # brainstorm notes and early exploration
```

---

## Configuration

The base directory for all XDD artifacts is controlled by the `docs_base` key in
`.claude/startup.toml`. The default value is `docs/XDD`.

```toml
# .claude/startup.toml
[tcs]
docs_base = "docs/XDD"
```

To relocate the XDD directory — for example, if your project uses `docs/specs` as the
convention — set `docs_base` to the new path:

```toml
[tcs]
docs_base = "docs/specs"
```

Subdirectories (`specs/`, `adr/`, `ideas/`) are derived automatically from this value.
No other configuration is required.

**Scope chain:** A repo-level `.claude/startup.toml` overrides the global
`~/.claude/startup.toml`. The global file applies to all projects where no repo-level
override exists.
