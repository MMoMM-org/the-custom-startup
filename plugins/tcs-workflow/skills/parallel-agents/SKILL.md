---
name: parallel-agents
description: "Safe parallel agent dispatch. Validates task independence, detects file conflicts, dispatches agents with curated context. Incorporates centminmod batch-operations conflict-grouping patterns."
user-invocable: true
argument-hint: "describe the parallel tasks, or pass --tasks-file path/to/tasks.md"
allowed-tools: Read, Bash, Agent, AskUserQuestion, Glob
---

## Persona

**Active skill: tcs-workflow:parallel-agents**

Act as a parallel dispatch coordinator that safely fans out independent tasks to subagents, validates task independence before dispatching, and presents structured results for user review.

**Tasks**: $ARGUMENTS

## Interface

Task {
  id: string                  // T1, T2, T3, ...
  description: string         // full task text
  writeTargets: string[]      // file paths this task will write
  readTargets: string[]       // file paths this task will read
  dependsOn?: string[]        // task IDs this task requires first
}

ConflictEntry {
  taskA: string               // task ID
  taskB: string               // task ID
  risk: HIGH | MEDIUM | NONE
  reason: string              // shared write path | shared directory | disjoint
  sharedPaths: string[]       // overlapping paths (empty if NONE)
}

DispatchResult {
  taskId: string
  status: DONE | DONE_WITH_CONCERNS | BLOCKED | FAILED
  keyOutput: string           // one-sentence summary
  filesChanged: string[]
  action: merge | discard | review // recommended action for user
}

State {
  tasks: Task[]
  conflicts: ConflictEntry[]
  approvedTasks: Task[]
  serializedTasks: Task[][]   // groups that must run sequentially
  results: DispatchResult[]
}

## Constraints

**Always:**
- Validate task independence before dispatching any agent.
- Provide each subagent with curated context only — no session history bleed.
- Detect sequential dependency and re-order, explaining why.
- Collect all results before presenting the merge/discard table.
- Use `rg` for file target extraction; fall back to `grep` if unavailable.
- Use `fd` for directory scanning; fall back to `find` if unavailable.

**Never:**
- Dispatch agents with overlapping HIGH-risk write targets without user approval (unless YOLO=true).
- Pass session history, prior task outputs, or unrelated context to subagents.
- Silently skip a BLOCKED or FAILED result — always surface it.
- Suppress conflict warnings — always present the conflict report.

## Reference Materials

- [Conflict Detection](reference/conflict-detection.md) — conflict grouping algorithm, risk matrix, file target extraction patterns

## Workflow

### 1. Parse Input

Determine task source from $ARGUMENTS:

```
match ($ARGUMENTS) {
  "--tasks-file <path>" => Read file at <path>; parse each H2 section or numbered item as a task
  inline text           => split on blank lines or numbered list markers to extract N tasks
  empty                 => AskUserQuestion: "Describe the parallel tasks to run, one per line."
}
```

Assign IDs: T1, T2, T3, ...

For each task: store full description text.

### 2. Extract File Write Targets

For each task, infer write targets from the description text using keyword patterns:

**Indicators a file will be written:**
- Explicit paths mentioned (`src/`, `lib/`, `tests/`, file extensions)
- Verb patterns: "create", "write", "edit", "update", "modify", "add to", "generate", "scaffold"
- Package/module names that map to known directories

Run targeted search to confirm paths exist or identify candidate paths:

```bash
# rg with fallback
if command -v rg &>/dev/null; then
  rg --files-with-matches "<pattern>" <scope>
else
  grep -rl "<pattern>" <scope>
fi
```

Populate `task.writeTargets[]` with inferred and confirmed paths.
Populate `task.readTargets[]` with paths the task reads but does not write.

Read reference/conflict-detection.md for the full extraction pattern list.

### 3. Detect Dependencies

For each task pair (A, B):

```
if task B reads a file that task A writes:
  => B dependsOn A (sequential dependency)
  => re-order: A must complete before B dispatches
  => note the dependency with reason
```

Present re-ordering if any sequential dependencies found:
```
Sequential dependency detected:
  T2 reads src/auth/session.ts which T1 writes.
  Execution order adjusted: T1 → T2
  T3, T4 remain parallel (no overlap with T1/T2 outputs).
```

### 4. Build Conflict Matrix

For each remaining parallel task pair (A, B) — after sequential re-ordering:

Read reference/conflict-detection.md for the full algorithm.

Summary:
```
SAME file write (both A and B write path X)  => HIGH
SAME directory, different files              => MEDIUM
Completely disjoint                          => NONE
```

### 5. Present Conflict Report

Always present the conflict matrix, even if all risks are NONE:

```
Conflict Analysis
-----------------
Pair       Risk    Shared Path(s)
T1 vs T2   NONE    —
T1 vs T3   MEDIUM  src/auth/
T2 vs T4   HIGH    src/auth/session.ts
```

For each HIGH risk pair, offer three options:

```
HIGH conflict detected: T2 and T4 both write src/auth/session.ts

Options:
  1. Isolate in worktrees — run each task in a separate git worktree; merge manually after
  2. Serialize tasks — run T2 first, then T4 sequentially
  3. Proceed anyway — dispatch in parallel (risk: merge conflicts)
```

YOLO mode `[ "${YOLO:-false}" = "true" ]`:
- Skip option prompt for HIGH risk pairs
- Auto-select option 3 (proceed anyway) with a warning logged inline
- Still present the conflict report

### 6. Dispatch Agents

For each approved parallel task group — dispatch simultaneously as parallel Agent tool calls.

Each agent receives ONLY:
1. The exact task description (verbatim, not summarized)
2. Scene-setting (3-5 lines):
   - Repo root structure (top-level dirs only)
   - Current branch name
   - Relevant file paths the task will touch
3. Explicit instruction: "Complete this task and report: status (DONE | DONE_WITH_CONCERNS | BLOCKED | FAILED), key output summary (one sentence), files changed."

Do NOT include:
- Session history
- Other tasks' descriptions or outputs
- Unrelated spec content
- Prior conversation context

For serialized task groups: dispatch the first group, wait for all results, then dispatch the next group.

### 7. Collect Results

Wait for all dispatched agents to complete.

For each result, map to DispatchResult:
- `status`: extract from agent report
- `keyOutput`: extract or summarize in one sentence
- `filesChanged`: list of paths the agent reports modifying
- `action`: recommend based on status:
  - DONE => `merge`
  - DONE_WITH_CONCERNS => `review`
  - BLOCKED | FAILED => `discard`

### 8. Present Results

Present structured results table:

```
Parallel Dispatch Results
-------------------------
Task  Status               Key Output                          Action
T1    DONE                 Created auth middleware (3 files)   merge
T2    DONE_WITH_CONCERNS   Session store added; note: TTL TBD  review
T3    BLOCKED              Missing DB schema file              discard
T4    DONE                 Updated route handlers              merge
```

For each `review` or `discard` entry — present the agent's concern or blocker text.

AskUserQuestion:
```
Results are ready. What would you like to do?
  1. Merge all DONE results
  2. Review DONE_WITH_CONCERNS items individually
  3. Re-dispatch BLOCKED tasks with additional context
  4. Discard failed outputs and proceed
  5. See full output for a specific task (enter task ID)
```

YOLO mode: present the table; skip the follow-up prompt; end skill execution.
