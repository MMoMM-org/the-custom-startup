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

When you hear yourself thinking any of these — stop. Apply the law.

| Rationalization | Rejection |
|---|---|
| "It's too simple to test" | Simple code is the easiest to test. Write the test. |
| "I'll add tests later" | Later never comes. RED first, always. |
| "It's just a config change" | Config changes affect behavior. Behavior needs tests. |
| "I don't know how to test this" | That's a design problem. Make it testable. |
| "The tests will just mock everything" | Then your design has too many dependencies. |
| "It's already tested indirectly" | Indirect tests don't give you RED. Write a direct test. |
| "This is a one-line fix" | One-line fixes break things. One-line tests prevent that. |
| "We're in a hurry" | Skipping TDD makes you slower, not faster. |

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
