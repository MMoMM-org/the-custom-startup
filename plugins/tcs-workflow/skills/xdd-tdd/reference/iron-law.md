# TDD Iron Law

No production code without a failing test. This is the law.

## The Iron Law

> Write a failing test. Watch it fail. Write code to make it pass. Refactor. Repeat.

There are no exceptions. The law applies to:
- "Simple" getter functions
- Config file changes that affect behavior
- One-line fixes
- "Obviously correct" code
- Refactoring (tests must pass throughout)

## Rationalization Rejection Table

When you hear yourself thinking any of these — stop and do what the right column says.

| Rationalization | Counter-action |
|---|---|
| "It's too simple to test" | Write the one-assertion test now: call it with one input, assert the output. It takes a minute. |
| "I'll add tests later" | Write the failing test before the next line of production code. Code already written without one: delete it and start from the test. |
| "It's just a config change" | Write a test that loads the config through the real loader and asserts what a caller does with it: the timeout a client uses, the path it enables. Not the value read back from the file. |
| "It's obviously correct" | Then the test passes on the first GREEN. Write it and watch it fail first. |
| "I don't know how to test this" | Write the test against the call you wish existed. Move the logic out of the I/O so it takes inputs and returns outputs, and test that. |
| "The tests will just mock everything" | Mock only at the process boundary (network, clock, filesystem, subprocess). Needs more than that: split the unit and test the pure part without mocks. |
| "It's already tested indirectly" | Break the code on purpose and run the suite. Nothing goes red: the coverage is not there. Write a direct test that does go red. |
| "This is a one-line fix" | Write the test that reproduces the bug and watch it fail. The one line goes in after. |
| "We're in a hurry" | Shrink the step, not the discipline: one failing test for the next behavior only, one case, one assertion, then the code. |
| "It's a shell script, I'll just grep the file" | Grepping the source proves the source is the source. Run it against an input and assert the exit code or output. |
| "It's a skill/prompt, there's nothing to run" | Then the observable is the consuming agent's behavior — probe it (`tcs-helper:skill-author`). Prose for humans earns no test. |
| "I'll assert the constant's value" | That fires on redesign and sleeps through bugs. Test the behavior that depends on the constant. |
| "I'll compare it to what the function returns" | Then it passes no matter what the function does. Hand-derive the expected value. |

The last four are the falsifiability failures — tests that pass without verifying
anything. Full treatment in `reference/writing-good-tests.md`.

## RED-GREEN-REFACTOR

```
RED    → Write a failing test that describes the desired behavior
GREEN  → Write the minimum code to make the test pass
REFACTOR → Clean up without breaking tests
```

Each phase has exactly one exit condition:
- RED exits when: tests exist AND they fail
- GREEN exits when: all tests pass
- REFACTOR exits when: all tests still pass AND code is clean
