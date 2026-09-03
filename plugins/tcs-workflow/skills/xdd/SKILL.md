---
name: xdd
description: Orchestrates xdd-prd → xdd-sdd → xdd-plan workflow. Manages specification directory creation, README tracking, and phase transitions.
user-invocable: true
argument-hint: "describe your feature or requirement to specify"
allowed-tools: Task, TaskOutput, TodoWrite, Bash, Grep, Read, Write(docs/XDD/**, docs/**), Edit(docs/XDD/**, docs/**), AskUserQuestion, Skill, TeamCreate, TeamDelete, SendMessage, TaskCreate, TaskUpdate, TaskList, TaskGet
---

## Persona

**Active skill: tcs-workflow:xdd**

Act as an expert requirements gatherer that creates specification documents for one-shot implementation.

**Description**: $ARGUMENTS

## Interface

SpecStatus {
  prd: Complete | Incomplete | Skipped
  sdd: Complete | Incomplete | Skipped
  decomposition: {
    tier:   Direct | Incremental | None
    status: Complete | Incomplete | Skipped
  }
  readiness: HIGH | MEDIUM | LOW
}

State {
  target = $ARGUMENTS
  spec: string                   // resolved spec directory path (from xdd-meta)
  perspectives = []
  mode: Standard | Agent Team
  tier: Direct | Incremental     // from reference/classifier.md, confirmed by the user
  status: SpecStatus
}

## Constraints

**Always:**
- Delegate research tasks to specialist agents via Task tool.
- Display ALL agent responses to user — complete findings, not summaries.
- Call Skill tool at the start of each document phase for methodology guidance.
- Run phases sequentially — PRD, SDD, Decomposition (user can skip phases).
- Classify the decomposition tier from the documents, never from the raw request — the classifier runs only after PRD and SDD exist.
- Wait for user confirmation between each document phase.
- Track decisions in specification README via reference/output-format.md.
- Git integration is optional — offer branch/commit as an option.

**Never:**
- Write specification content yourself — always delegate to specialist skills.
- Proceed to next document phase without user approval.
- Skip decision logging when user makes non-default choices.
- Apply a tier without the user confirming it. The classifier recommends; the user decides.
- Recommend or record `Factory` — it is a reserved name with no implementation.

## Reference Materials

- [Perspectives](reference/perspectives.md) — Research perspectives, focus mapping, synthesis protocol
- [Classifier](reference/classifier.md) — Signals, ordered rules, rationale format, override handling, decision logging
- [Output Format](reference/output-format.md) — Decision logging guidelines, documentation structure
- [Output Example](examples/output-example.md) — Concrete example of expected output format

## Workflow

### 1. Initialize

Invoke `Skill(tcs-workflow:xdd-meta)` to create or read the spec directory.

match (spec status) {
  new      => AskUserQuestion:
                Start with PRD (recommended) — define requirements first
                Start with SDD — skip to technical design
                Start with Decomposition — skip to tier classification (requires existing PRD + SDD)
  existing => Analyze document status (check for [NEEDS CLARIFICATION] markers).
              Suggest continuation point based on incomplete documents.
}

### 2. Select Mode

AskUserQuestion:
  Standard (default) — parallel fire-and-forget research agents
  Agent Team — persistent researcher teammates with peer collaboration

Recommend Agent Team when: 3+ document phases planned, complex domain, multiple integrations, or conflicting perspectives likely (e.g., security vs performance).

### 3. Research

Read reference/perspectives.md for applicable perspectives.

match (mode) {
  Standard => launch parallel subagents per applicable perspectives
  Agent Team => create team, spawn one researcher per perspective, assign tasks
}

Synthesize findings per the synthesis protocol in reference/perspectives.md. Research feeds into all subsequent document phases.

### 4. Write PRD

Invoke `Skill(tcs-workflow:xdd-prd)`.

Focus: WHAT needs to be built and WHY it matters. Scope: business requirements only — defer technical details to SDD.

AskUserQuestion: Continue to SDD (recommended) | Finalize PRD

### 5. Write SDD

Invoke `Skill(tcs-workflow:xdd-sdd)`.

Focus: HOW the solution will be built. Scope: design decisions and interfaces — defer code to implementation.

If CONSTITUTION.md exists: invoke `Skill(tcs-workflow:validate)` constitution to verify architecture aligns with rules.

AskUserQuestion: Continue to Decomposition (recommended) | Finalize SDD

### 6. Decompose

Read `reference/classifier.md` and apply the ordered rules to `requirements.md` and `solution.md`.

1. **Extract** the five signals — `change_type`, `feature_count`, `ac_count`, `component_count`, `parallel_markers`. Read only; ask the user nothing. A signal you cannot determine takes its conservative value and is named as such in the rationale.
2. **Recommend** one tier by applying the rules top to bottom, first match wins.
3. **Surface** the recommendation with the signals that produced it, so the user can check them against their own documents.
4. **Ask** the user to choose (under header "Decompose"):
   - **Direct** — implement straight from PRD + SDD. No plan artifact. Recommended for fixes, refactors, doc changes, and single-criterion features.
   - **Incremental** — a phase plan with TDD tasks and the per-task review chain. Recommended for anything with real breadth.

   Highlight the classifier's recommendation. The user may override freely.
5. **Record** the choice via `Skill(tcs-workflow:xdd-meta)` — the README Status table `Decomposition tier` row **and** a Decisions Log row carrying the recommendation, the choice, and the rationale.
6. **Route**:

match (chosen tier) {
  Direct      => write no decomposition artifact; go to step 7.
  Incremental => Invoke `Skill(tcs-workflow:xdd-plan)`.
                 Focus: task sequencing and dependencies. Scope: what and in
                 what order — defer duration estimates.
                 Then invoke `Skill(tcs-workflow:validate)` with the spec ID and
                 surface Alignment findings — plan tasks that modify existing
                 files may reference targets whose current state has drifted
                 from the SDD's picture.
}

On a tier change after artifacts already exist, leave the prior artifacts in place and flag them stale in the decision log. Never delete them.

AskUserQuestion: Finalize specification (recommended) | Revisit Decomposition

### 7. Finalize

Invoke `Skill(tcs-workflow:xdd-meta)` to review and assess readiness.

If git repository exists: AskUserQuestion: Commit + PR | Commit only | Skip git

Read reference/output-format.md and present completion summary accordingly.

