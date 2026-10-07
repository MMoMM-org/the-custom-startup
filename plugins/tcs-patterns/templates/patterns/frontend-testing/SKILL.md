---
name: frontend-testing
description: "Use when writing or reviewing frontend tests — enforces testing-library best practices, user-behavior assertions, network mocking at the boundary, and accessible queries."
user-invocable: true
argument-hint: "[test file or directory to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:frontend-testing**

Act as a frontend test engineer following Testing Library philosophy. Tests should resemble how users interact with the software, not how it is implemented.

## Interface

TestSmell {
  kind: IMPLEMENTATION_DETAIL | WRONG_QUERY | SNAPSHOT_OVERUSE | MISSING_ASYNC | SHALLOW_RENDER
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  framework: string    // react | vue | svelte | vanilla
  smells: TestSmell[]
}

## Constraints

**Always:**
- Query by accessible roles (`getByRole`, `getByLabelText`, `getByText`) — not by class or ID.
- Use `userEvent` over `fireEvent` — it triggers the full event chain.
- Mock at the network boundary (MSW, `fetch` mock) — not at the component level.
- Assert what the user sees, not what state exists internally.
- Await async state changes with `waitFor` or `findBy*` queries.

**Never:**
- Use `getByTestId` as the primary query strategy — it tests nothing about the user experience.
- Use snapshots as the sole assertion — they catch everything and verify nothing meaningful.
- Shallow-render components to "isolate" them — integration tests catch more real bugs.
- Assert on implementation details (`wrapper.state()`, internal props, component refs).

## Workflow

### 1. Detect Framework

Check for `@testing-library/react`, `@testing-library/vue`, etc. in `package.json`.

### 2. Scan for Smells

```bash
grep -n "getByTestId\|shallow\|toMatchSnapshot\|fireEvent\|wrapper\.state" "$TARGET" 2>/dev/null
```

Classify each hit as TestSmell.

### 3. Propose Fixes

For each smell, show original and replacement:
- `getByTestId('submit')` → `getByRole('button', { name: /submit/i })`
- `fireEvent.click(btn)` → `await userEvent.click(btn)`

### 4. Report

Group smells by kind. Include file:line and concrete fix.
