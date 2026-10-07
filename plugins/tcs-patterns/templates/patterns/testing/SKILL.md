---
name: testing
description: "Testing patterns for behavior-driven tests. Use when writing tests, creating test factories, structuring test files, or deciding what to test. Do NOT use for UI-specific testing (see frontend-testing or react-testing skills)."
user-invocable: true
argument-hint: "[module to write tests for, or test file/directory to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:testing**

Act as a test engineer who treats tests as executable specifications of behavior. A test that survives a refactor of the implementation's internals is doing its job; one that breaks is testing the wrong thing.

For verifying test effectiveness through mutation analysis, load `tcs-patterns:mutation-testing`.
For evaluating test quality against Dave Farley's properties, load `tcs-patterns:test-design-reviewer`.
For UI testing patterns, load `tcs-patterns:frontend-testing` or `tcs-patterns:react-testing`.

Adapted from citypaul/.dotfiles

## Interface

TestSmell {
  kind: IMPLEMENTATION_DETAIL | PRIVATE_METHOD | SPLIT_ASSERTION | EXTRACTED_FOR_TESTABILITY | MIRRORED_TEST_FILE | SHARED_MUTABLE_STATE | REDEFINED_SCHEMA | COVERAGE_THEATER
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  mode: WRITE | AUDIT
  smells: TestSmell[]
}

**In scope:** What a test asserts, how test data is built, and how test files are organized, for non-UI code.
**Out of scope:** Component and browser tests, mutation scoring, RED-GREEN-REFACTOR cycle enforcement.

## Constraints

**Always:**
- Test behavior through the public API — the entry point a real caller uses.
- Assert the whole result object with `toEqual`, not one field per assertion.
- Build test data with factory functions taking `Partial<T>` overrides.
- Parse factory output through the real production schema, so it returns a complete, valid object.
- Cover the error branches, not only the happy path.

**Never:**
- Test private methods, internal state, or how a function does its work.
- Spy on the function under test and assert only that it was called.
- Extract a function into its own file to give it a unit test.
- Mirror implementation files 1:1 with test files.
- Hold test state in `let` + `beforeEach` — a factory gives each test fresh state.
- Redefine a production schema inside a test file.

## Reference Materials

- reference/public-api-testing.md — public-API examples, extraction rule, file layout
- reference/test-factories.md — factory pattern, composition, anti-patterns
- reference/coverage-theater.md — patterns that fake 100% coverage

## Workflow

### 1. Name the Behavior Under Test

Identify the public entry point a caller actually invokes, and state the business behavior in the test name. If the behavior can only be reached through a private function or an internal helper, the test target is wrong — move up to the caller.

Read reference/public-api-testing.md when the boundary is unclear.

### 2. Construct Test Data

Write or reuse a factory for each entity the behavior needs. Read reference/test-factories.md.

### 3. Write the Assertion

Assert the complete returned value in one `toEqual`. Add a case for each error branch the behavior can take.

### 4. Audit an Existing Suite

Identify the test framework first, then grep for its spy, call-assertion and shared-setup constructs. For Jest and Vitest:

```bash
grep -rn "spyOn\|toHaveBeenCalled\|beforeEach" "$TARGET" 2>/dev/null
```

The equivalents elsewhere: `unittest.mock.patch` and `assert_called*` under pytest, `setUp` under unittest, recorder assertions under gomock.

Then check by reading, since these do not grep cleanly:
- calls into private or underscore-prefixed functions
- test files that mirror implementation file names 1:1
- single-caller helpers extracted into their own file with their own test
- schemas redefined in the test file instead of imported
- assertions split across several `expect` calls on one result

Read reference/coverage-theater.md and classify anything matching as `COVERAGE_THEATER`.

### 5. Report

Group smells by kind. Give file:line and a concrete replacement for each. Where coverage looks complete but the assertions are weak, say so and point at `tcs-patterns:mutation-testing` for the falsifiable check.

### Entry Point

- Writing new tests → steps 1–3.
- Auditing a file, directory, or suite → steps 4–5.
- Reviewing tests just written → steps 4–5 against those files.
