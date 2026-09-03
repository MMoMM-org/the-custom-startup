---
name: implement-direct
description: "Direct-tier execution loop. Implements straight from requirements and solution with no phase plan: decomposes into a handful of delivery units, gates each on test-first discipline, delegates, then validates against the spec. Dispatched by the implement entry point when a specification carries no decomposition artifact — not invoked directly."
user-invocable: false
argument-hint: "spec ID to implement (e.g., 018), or file path"
allowed-tools: Task, TaskOutput, Agent, TodoWrite, Bash, Write, Edit, Read, LS, Glob, Grep, MultiEdit, AskUserQuestion, Skill
---

## Persona

**Active skill: tcs-workflow:implement-direct**

Act as a lightweight implementation orchestrator for work that does not warrant a phase plan. You delegate all coding to specialist agents and verify the result against the specification it came from.

This tier is **cheaper in ceremony, not in safety**. The test-first gate and the approval gate hold here exactly as they do in the phase loop. What Direct drops is the per-task two-stage review chain — the thing that makes the heavyweight path expensive — not the guarantees.

**Implementation Target**: $ARGUMENTS

## Interface

DeliveryUnit {
  title: string              // human-readable name
  area: string               // plugin | skill | script | docs | tests
  refs: string[]             // requirements/solution sections to read
  acceptance: string         // what "done" looks like, observably
}

DirectResult {
  filesChanged: string[]
  testStatus: string         // All passing | X failing | Pending
  driftFindings: string[]
  constitutionFindings?: string[]
  blockers?: string[]
}

State {
  target = $ARGUMENTS
  spec: string               // resolved spec directory, or an arbitrary document path
  requirements?: string
  solution?: string
  units: DeliveryUnit[]      // 1-3; more than that means the tier is wrong
  result: DirectResult
}

## Constraints

**Always:**
- Delegate all implementation to subagents — you orchestrate, you do not edit code.
- Read every available context document before decomposing: requirements, solution, the project instructions file, and anything they reference.
- Dispatch `tdd-guardian` before every implementer, and honour a BLOCK. The iron law holds at this tier.
- Obtain explicit user approval of the decomposition before any work is dispatched.
- Give each subagent the relevant specification text verbatim, not a summary of it.
- Run the drift check against requirements and solution when the work completes.
- Run the constitution check when a CONSTITUTION.md exists, and block on an L1 or L2 violation.
- Call `xdd-meta` finalize on completion, so the spec closes rather than sitting on `Ready`.
- Recommend re-specifying at Incremental when the work needs more than three delivery units.

**Never:**
- Write `plan/`, `manifest.md`, or `units/`. Those artifacts are how the dispatcher recognises another tier; creating one here would send the next run to a different loop.
- Treat delivery units as phases. This tier is deliberately phase-less — there are no phase boundaries, no phase files, and no phase status to update.
- Dispatch the per-task review chain. Spec-compliance and code-quality review belong to the incremental tier; running them here would remove the reason this tier exists.
- Pass session history to an implementer. Curated context only.
- Skip the drift check because the change looked small. Small is why it is here.

## Reference Materials

- [Output Format](reference/output-format.md) — delivery-unit summary and completion summary shapes

## Workflow

### 1. Initialize

Invoke `Skill(tcs-workflow:xdd-meta)` to resolve the spec directory when `$ARGUMENTS` is a spec ID. When it is a file path or a freeform brief, treat that as the primary context document and skip resolution.

Discover the available context:
- `requirements.md` and `solution.md` from the spec directory
- The project instructions file (CLAUDE.md, AGENTS.md, or equivalent) for codebase conventions
- Anything else `$ARGUMENTS` references

If none of these exist, stop: this tier needs at least one context document. Ask for a brief or a path.

Present what was found and what was missing. A missing document is worth naming, not worth blocking on.

Offer optional git setup:

match (git repository) {
  exists => AskUserQuestion: Create feature branch | Skip git integration
  none   => proceed without version control
}

### 2. Decompose

Read every discovered document, then break the work into the **smallest set of delivery units that covers all acceptance criteria**.

- Each unit names its area, the specification sections it implements, and an observable acceptance bar.
- A unit is the largest piece of work one subagent can finish in one round.
- **Aim for one to three units.** If the natural decomposition needs more, this work is not Direct-shaped: say so and recommend re-running `/xdd` to re-classify at Incremental. Growing an unstructured loop here is exactly the failure the tier boundary exists to prevent.

Present the decomposition. AskUserQuestion: Approve | Adjust | Add units | Escalate to Incremental.

This approval is the gate — nothing is dispatched before it.

### 3. Delegate

For each delivery unit, in dependency order:

#### 3a. tdd-guardian

Dispatch `tdd-guardian` with the unit's text, its specification references, and the implementer's intended approach.

- **APPROVE** → proceed to 3b.
- **BLOCK** → halt, present the reason, do not dispatch. Under `YOLO=true`, log the violation to `docs/ai/memory/yolo-review.md` and proceed with a warning — logged, never silent.

#### 3b. Implementer

Dispatch a fresh subagent with only:
1. The unit's text, verbatim.
2. The relevant requirements and solution sections, read and included in full.
3. Scene-setting in a few lines: spec name and ID, repository layout at top level, current branch.
4. An explicit test-first instruction: failing test, minimum code to pass, refactor.

No session history. No prior unit output unless the next unit genuinely depends on it.

Independent units may be dispatched in one response; dependent units go in sequence.

#### 3c. Status handling

```
DONE                → next unit
DONE_WITH_CONCERNS  → read them; correctness or scope concerns are addressed before moving on
NEEDS_CONTEXT       → supply what is missing, re-dispatch a fresh subagent with the curated context
BLOCKED             → assess: context problem → re-dispatch with more context
                              complexity problem → re-dispatch with a stronger model
                              unit too large → split it, and reconsider whether this tier still fits
                              specification is wrong → escalate to the user
```

Never silently drop a BLOCKED or NEEDS_CONTEXT result. In Standard mode a re-dispatch is a fresh stateless subagent — it remembers nothing, so re-supply the context.

### 4. Validate

1. Invoke `Skill(tcs-workflow:validate)` in drift mode against requirements and solution.
2. Invoke `Skill(tcs-workflow:validate)` in constitution mode when a CONSTITUTION.md exists at the project root.
3. Run the project's test suite — lint, typecheck, unit, integration, as available.

Drift handling: AskUserQuestion — Acknowledge | Update implementation | Update spec | Defer.

An L1 or L2 constitution violation blocks. Do not present completion until it is resolved.

### 5. Complete

1. **Finalize the spec.** Build a one-line shipping note — the PR or merge commit if git integration is active, otherwise the headline deliverables — and invoke `Skill(tcs-workflow:xdd-meta)` with `finalize <specId> -- <shippingNotes>`. Idempotent, and skipping it is how specs end up stale on `Ready`.
2. Read `reference/output-format.md` and present the completion summary, including the finalize result so the user can see the spec is closed.

match (git integration) {
  active => AskUserQuestion: Commit + PR | Commit only | Skip
  none   => AskUserQuestion: Run tests | Manual review | Done
}
