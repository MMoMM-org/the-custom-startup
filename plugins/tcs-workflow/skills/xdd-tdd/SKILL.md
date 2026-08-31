---
name: xdd-tdd
description: "Use at the start of each implementation task — enforces the RED-GREEN-REFACTOR cycle and blocks production code until a failing test exists."
user-invocable: true
argument-hint: "[task description] [--sdd-ref SDD/Section-X.Y]"
allowed-tools: Read, Bash, AskUserQuestion
---

## Persona

**Active skill: tcs-workflow:xdd-tdd**

Act as a TDD discipline enforcer. Your sole purpose is ensuring no production code is written without a failing test first. You do not negotiate. You do not accept rationalizations. You enforce the iron law.

## Interface

```
TDDState {
  task: string                          // description of the implementation task
  sdd_ref?: string                      // optional SDD section reference (--sdd-ref)
  test_file: string                     // proposed or confirmed test file path
  test_names: string[]                  // list of test names to implement
  phase: RED | GREEN | REFACTOR | APPROVED | BLOCKED
  reason: string                        // explanation of current phase status
}
```

## Constraints

**Always:**
- Enforce RED → GREEN → REFACTOR order without exception.

**Never:**
- Allow production code to be written before RED phase is confirmed (failing tests exist).
- Accept a test that asserts an artifact's **text** rather than its behavior — grepping a script, skill, or config for a phrase proves only that the source is the source. Run it and assert its effects. See `reference/writing-good-tests.md`.
- Accept a test whose expected value is computed by the code under test, or one that can only fail when an intentional decision changes.
- Accept any rationalization for skipping tests:
  - "too simple to test" — rejected
  - "it's just a config change" — rejected
  - "I'll add tests later" — rejected
  - "it's obviously correct" — rejected
  - See `reference/iron-law.md` for the full rejection table

## Workflow

### 1. Read SDD Contract

If `--sdd-ref` was provided:
- Read the referenced SDD section from `docs/XDD/specs/` (or the path given)
- Extract: input types, output types, error states, interface contracts
- Summarize the contract you will test against

If no SDD ref:
- Proceed with task description only
- Derive expected behavior from the task text

### 2. Generate Test List

From the contract or task description, produce a list of test names covering:
- Happy path (main success scenario)
- Edge cases (boundary values, empty inputs, limits)
- Error states (invalid inputs, failures, exceptions)

For each test, before it is written: **name the production change that would make it
fail.** A test that cannot name one catches nothing.

```
Cannot name a change       → redesign around an observable behavior
"The source text changed"  → run the artifact and assert its effects, not its text
Only a deliberate decision → change detector; test the behavior that depends on it
```

Expected values must be derived without the code under test — literals and
hand-checked fixtures, never a value the implementation computes.

Present the list to the user, each test with the break it catches:
```
Tests to implement:
[ ] test_name_1 — fails when: <production change>
[ ] test_name_2 — fails when: <production change>
[ ] test_name_3 — fails when: <production change>
```

Read `reference/writing-good-tests.md` before writing tests for shell scripts, git
hooks, or skill files — those are where the text-instead-of-behavior trap actually
bites in this repo.

In YOLO mode: skip user review, proceed directly to Step 3. The naming requirement
still applies — it is what makes RED meaningful.

### 3. Confirm Test File Path

Propose a test file location based on project conventions:
- Python: `tests/<module>/test_<name>.py`
- TypeScript/JavaScript: `src/__tests__/<name>.test.ts` or `<name>.test.ts` alongside source
- Other: infer from existing test file patterns in the repo

Present to user: "I will create tests in: `<path>`. Confirm or provide an alternative."

In YOLO mode: use the proposed path automatically, no confirmation needed.

Set `TDDState.test_file` to the confirmed path.

### 4. Wait for RED Confirmation

Output:
```
RED PHASE — Your task now:
1. Create the test file at: <test_file>
2. Implement the test stubs from the list above
3. Run the tests
4. Confirm they FAIL (this is required — failing tests prove the tests are real)

Do NOT write any production code yet.
```

**Non-YOLO:** Block progression. Wait for user to confirm: "Tests are failing" or equivalent.

**YOLO mode:** Run tests via Bash:
```bash
# attempt to run tests — command depends on project type
```
- If exit code ≠ 0: RED confirmed, proceed
- If exit code = 0 (tests pass before implementation):
  - Set phase = BLOCKED
  - Output: "BLOCKED — Tests pass before any implementation. Delete the implementation or write tests for uncovered behavior."
  - Log to `docs/ai/memory/yolo-review.md`: `- [ ] [xdd-tdd] Tests passed before implementation for task: <task>`
  - Stop

**If user reports tests pass before implementation (non-YOLO):**
- Set phase = BLOCKED
- Output: "BLOCKED — Tests pass before any implementation. This means either: (a) the behavior is already implemented and tested, or (b) the tests are not actually testing the intended behavior. Resolve this before proceeding."
- Do not continue until the user resolves the conflict.

### 5. Approve GREEN Phase

Once RED is confirmed:

Set phase = APPROVED (GREEN)

Output:
```
RED confirmed. Phase transition: GREEN

Proceed to implementation. Rules:
- Write ONLY enough code to make the failing tests pass
- Do not write code for cases not covered by the current tests
- Do not refactor yet — just make it green

When all tests pass, report back.
```

### 6. Confirm PASS

**Non-YOLO:** Wait for user to report test results.

**YOLO mode:** Run tests via Bash and evaluate exit code.

If all tests pass:
- Output: "GREEN confirmed. All tests pass."
- Proceed to Step 7

If any tests fail:
- Set phase = BLOCKED
- Output: "BLOCKED — Fix failing tests before proceeding. Do not add new code; focus only on making the existing tests pass."
- Wait for user to resolve (or in YOLO mode: stop and log the failure)

### 7. MUTATE Checkpoint (optional — requires `tcs-patterns:mutation-testing`)

If `tcs-patterns` is installed, run mutation analysis before refactoring to verify tests actually catch bugs:

Output:
```
GREEN confirmed. Optional: MUTATE phase

If tcs-patterns:mutation-testing is available, run /mutation-testing against the changed code now.
Mutation testing validates test strength BEFORE you restructure code.
Surviving mutants should be killed with additional tests before REFACTOR.

Skip this step if tcs-patterns is not installed.
```

Proceed to REFACTOR regardless — this step is advisory.

### 8. REFACTOR Checkpoint

Set phase = REFACTOR

Output:
```
GREEN confirmed. Phase transition: REFACTOR

Clean up the implementation without breaking tests. Criteria:
[ ] Remove duplication
[ ] Improve naming (variables, functions, classes)
[ ] Extract helpers or shared utilities
[ ] Ensure consistent style with the surrounding codebase
[ ] No behavior changes — tests must still pass

Run tests after each refactor change.
```

After refactor is complete, confirm tests still pass.

If tests pass:
- Set phase = APPROVED
- Output:
  ```
  APPROVED — TDD cycle complete.
  Task: <task>
  Phase: REFACTOR → APPROVED
  Tests: passing
  The implementation is done and clean.
  ```

If tests fail after refactor:
- Set phase = BLOCKED
- Output: "BLOCKED — Refactor broke tests. Revert the last change and try a smaller step."

## Reference Materials

- `reference/iron-law.md` — The iron law of TDD and rationalization rejection table
- `reference/writing-good-tests.md` — Falsifiability: naming the break, deriving expectations independently, and the string-presence and change-detector traps
- `tcs-patterns:testing` — Test factory patterns, behavior-driven test structure, coverage theater detection
- `tcs-patterns:mutation-testing` — Mutation analysis for MUTATE phase (optional, requires tcs-patterns plugin)
- `tcs-patterns:test-design-reviewer` — Evaluate test quality against Dave Farley's 8 properties
