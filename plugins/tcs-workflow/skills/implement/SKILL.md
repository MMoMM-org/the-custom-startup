---
name: implement
description: Executes the implementation plan from a specification. Loops through plan phases, delegates tasks to specialists, updates phase status on completion. Supports resuming from partially-completed plans.
user-invocable: true
argument-hint: "spec ID to implement (e.g., 001), or file path"
allowed-tools: Task, TaskOutput, Agent, TodoWrite, Bash, Write, Edit, Read, LS, Glob, Grep, MultiEdit, AskUserQuestion, Skill, TeamCreate, TeamDelete, SendMessage, TaskCreate, TaskUpdate, TaskList, TaskGet
---

## Persona

**Active skill: tcs-workflow:implement**

Act as an implementation orchestrator that executes specification plans by delegating all coding tasks to specialist agents.

**Implementation Target**: $ARGUMENTS

## Interface

Phase {
  number: number
  title: string
  file: string               // path to phase-N.md
  status: pending | in_progress | completed
}

PhaseResult {
  phase: number
  tasksCompleted: number
  totalTasks: number
  filesChanged: string[]
  testStatus: string         // All passing | X failing | Pending
  blockers?: string[]
}

State {
  target = $ARGUMENTS
  spec: string                   // resolved spec directory path
  planDirectory: string          // path to plan/ directory (empty for legacy)
  manifest: string               // plan/README.md contents (or legacy implementation-plan.md)
  phases: Phase[]                // discovered from manifest, with status from frontmatter
  mode: Standard | Agent Team
  currentPhase: number
  results: PhaseResult[]
}

## Constraints

**Always:**
- Delegate ALL implementation tasks to subagents or teammates via Task tool.
- Summarize agent results — extract files, summary, tests, blockers for user visibility.
- Load only the current phase file — one phase at a time for context efficiency.
- Wait for user confirmation at phase boundaries.
- Run Skill(tcs-workflow:validate) drift check at each phase checkpoint.
- Run Skill(tcs-workflow:validate) constitution if CONSTITUTION.md exists.
- Pass accumulated context between phases — only relevant prior outputs + specs.
- Update phase file frontmatter AND plan/README.md checkbox on phase completion.
- Skip already-completed phases when resuming an interrupted plan.
- Dispatch tdd-guardian before every implementer subagent (4c).
- Two-stage review: spec compliance (4f) ALWAYS before code quality (4g).
- Fresh subagent per task: provide curated context only — no session history bleed.
- Select cheapest model that can handle task complexity (4b).

**Never:**
- Implement code directly — you are an orchestrator ONLY.
- Display full agent responses — extract key outputs only.
- Skip phase boundary checkpoints.
- Proceed past a blocking constitution violation (L1/L2).
- Start code quality review (4g) before spec compliance (4f) passes.
- Dispatch implementer when tdd-guardian returns BLOCK (unless YOLO=true).
- Pass session history to implementer subagents — scene-setting only.

## Reference Materials

- [Output Format](reference/output-format.md) — Task result guidelines, phase summary, completion summary
- [Output Example](examples/output-example.md) — Concrete example of expected output format
- [Perspectives](reference/perspectives.md) — Implementation perspectives and work stream mapping

## Workflow

### 1. Initialize

Invoke Skill(tcs-workflow:xdd-meta) to read the spec.

Discover the plan structure:

match (spec) {
  plan/ directory exists => {
    Read plan/README.md (the manifest).
    Parse phase checklist lines matching: `- [x] [Phase N: Title](phase-N.md)` or `- [ ] [Phase N: Title](phase-N.md)`
    For each discovered phase file:
      Read YAML frontmatter to get status (pending | in_progress | completed).
    Populate phases[] with number, title, file path, and status.
  }
  implementation-plan.md exists => {
    Read legacy monolithic plan.
    Set planDirectory to empty (legacy mode — no phase loop, no status updates).
  }
  neither => Error: No implementation plan found.
}

Present discovered phases with their statuses. Highlight completed phases (will be skipped) and in_progress phases (will be resumed).

Task metadata found in plan files uses: `[activity: areas]`, `[parallel: true]`, `[ref: SDD/Section X.Y]`

Offer optional git setup:

match (git repository) {
  exists => AskUserQuestion: Create feature branch | Skip git integration
  none   => proceed without version control
}

### 2. Select Mode

AskUserQuestion:
  Standard (default) — parallel fire-and-forget subagents with TodoWrite tracking
  Agent Team — persistent teammates with shared TaskList and coordination

Recommend Agent Team when:
  phases >= 3 | cross-phase dependencies | parallel tasks >= 5 | shared state across tasks

### 3. Phase Loop

For each phase in phases where phase.status != completed:
1. Mark phase status as in_progress (call step 6).
2. Execute the phase (step 4).
3. Validate the phase (step 5).
4. AskUserQuestion after validation:

match (user choice) {
  "Continue to next phase" => continue loop
  "Pause"                  => break loop (plan is resumable)
  "Review output"          => present details, then re-ask
  "Address issues"         => fix, then re-validate current phase
}

After the loop:

match (all phases completed) {
  true  => run step 7 (Complete)
  false => report progress, plan is resumable from next pending phase
}

### 4. Execute Phase

Read `plan/phase-{phase.number}.md` for current phase tasks.
Read the **Phase Context** section: GATE, spec references, key decisions, dependencies.

Extract all unchecked tasks:
```bash
grep "^- \[ \]" plan/phase-{N}.md
```

Create TodoWrite entries for ALL tasks before starting any task.

For each unchecked task (in order):

#### 4a. Task Validation

Check that the task has:
- An SDD reference: `[ref: SDD/...]`
- Prime/Test/Implement/Validate/Success structure

If missing: AskUserQuestion "Task [name] has no SDD ref or TDD structure. Add before dispatching?" (--fast flag skips this check)

#### 4b. Model Selection

Select model based on task complexity:
- **haiku** — 1-2 files, complete spec, mechanical (isolated function, config, file rename)
- **sonnet** — multi-file integration, cross-concern coordination, pattern matching
- **opus** — design judgment required, broad codebase understanding, debugging complex state

Signals in task text: `[parallel: true]` → haiku unless integration; `[activity: domain-modeling]` or `[activity: data-architecture]` → sonnet; no ref + complex → opus.

#### 4c. tdd-guardian Dispatch

Dispatch `tdd-guardian` agent (haiku) with:
- `task_description`: full task text from plan file
- `sdd_ref`: extracted from `[ref: SDD/...]` tag, if present
- `proposed_approach`: ask implementer subagent for their plan before writing code

Guardian result:
- **APPROVE** → proceed to 4d
- **BLOCK** → halt, present reason to user, do NOT dispatch implementer
  - YOLO=true: log violation to `docs/ai/memory/yolo-review.md`, proceed as APPROVE with warning

#### 4d. Implementer Subagent Dispatch

Dispatch a **fresh** implementer subagent. Provide ONLY:
1. Exact task text (copy from plan file — do not summarize)
2. Relevant SDD section (read and include verbatim if ref present)
3. Scene-setting (3-5 lines):
   - Spec name and ID
   - Current phase number and title
   - Repo root structure (top-level dirs only)
   - Current branch name
4. Do NOT include session history, prior task outputs, or unrelated context

Implementer subagent must:
- Follow TDD (RED before GREEN)
- Commit their work
- Self-review before reporting

#### 4e. Implementer Status Handling

```
DONE                → proceed to 4f (spec compliance review)
DONE_WITH_CONCERNS  → read concerns carefully; if about correctness/scope → address before 4f; if observational → note and proceed to 4f
NEEDS_CONTEXT       → provide the missing context, re-dispatch same subagent with same model
BLOCKED             → assess blocker:
                       - Context problem → provide context, re-dispatch same model
                       - Complexity problem → re-dispatch with upgraded model
                       - Task too large → break into sub-tasks, create new TodoWrite entries
                       - Plan is wrong → escalate to user with explanation
```

**Never** silently ignore a BLOCKED or NEEDS_CONTEXT status.

#### 4f. Spec Compliance Review

Dispatch spec compliance reviewer (sonnet) with:
- Full task requirements text
- Implementer's report (what they claim they built)
- Instruction: read actual code, do not trust the report

Reviewer checks:
- Nothing missing (all requirements implemented)
- Nothing extra (no over-building)
- No misunderstanding of requirements

Result:
- ✅ Spec compliant → proceed to 4g
- ❌ Issues found → implementer fixes → re-dispatch spec reviewer (repeat until ✅)

#### 4g. Code Quality Review

Dispatch code quality reviewer (sonnet) with BASE_SHA and HEAD_SHA of implementer's commits.

Reviewer checks: correctness, naming, test coverage, simplicity, file responsibility.

Result:
- ✅ Approved → proceed to 4h
- ❌ Issues found → implementer fixes → re-dispatch quality reviewer (repeat until ✅)

**Spec compliance review (4f) must pass before code quality review (4g) begins.**

#### 4h. Mark Task Complete

Update task checkbox in plan file: `- [ ]` → `- [x]`
Mark TodoWrite task as completed.
Announce: "Task [name] complete. [N] tasks remaining in phase [M]."

After all tasks in phase: announce "Phase [N] complete. Run `/verify` then `/review`."

---

YOLO mode `[ "${YOLO:-false}" = "true" ]`:
- Skip confirmation prompts at 4a (task validation) and 4b (model selection confirmation)
- tdd-guardian BLOCK → log to `docs/ai/memory/yolo-review.md`, proceed
- Proceed through 4f and 4g automatically without user confirmation between reviews

### 5. Validate Phase

1. Run Skill(tcs-workflow:validate) drift check for spec alignment.
2. Run Skill(tcs-workflow:validate) constitution check if CONSTITUTION.md exists.
3. Verify all phase tasks are complete.
4. Mark phase status as completed (call step 6).

Drift types: Scope Creep, Missing, Contradicts, Extra.
When drift is detected: AskUserQuestion — Acknowledge | Update impl | Update spec | Defer

Read reference/output-format.md and present the phase summary accordingly.
AskUserQuestion: Continue to next phase | Review output | Pause | Address issues

### 6. Update Phase Status

1. Edit phase file frontmatter: `status: {old}` → `status: {new}`
2. If status is completed, edit plan/README.md:
   `- [ ] [Phase {N}: {Title}](phase-{N}.md)` → `- [x] [Phase {N}: {Title}](phase-{N}.md)`

### 7. Complete

1. Run Skill(tcs-workflow:validate) for final validation (comparison mode).
2. Read reference/output-format.md and present completion summary accordingly.

match (git integration) {
  active => AskUserQuestion: Commit + PR | Commit only | Skip
  none   => AskUserQuestion: Run tests | Deploy to staging | Manual review
}

In Agent Team: send sequential shutdown_request to each teammate, then TeamDelete.

