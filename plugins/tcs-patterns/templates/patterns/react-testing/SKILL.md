---
name: react-testing
description: "Use when testing React components or hooks — enforces react-testing-library patterns, proper hook testing with renderHook, and async state handling."
user-invocable: true
argument-hint: "[component or hook test file to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:react-testing**

Act as a React testing expert. Apply React Testing Library and react-hooks-testing-library conventions. Never test implementation; always test rendered output and user interactions.

## Interface

ReactTestSmell {
  kind: ENZYME_PATTERN | MISSING_ACT | STATE_INSPECTION | MISSING_CLEANUP | WRONG_ASYNC
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  smells: ReactTestSmell[]
  usesRTL: boolean
}

## Constraints

**Always:**
- Use `@testing-library/react` render; use `@testing-library/user-event` for interactions.
- Test hooks with `renderHook` from `@testing-library/react`.
- Wrap state updates in `act()` when not using `userEvent` (which wraps automatically).
- Clean up after each test — RTL does this automatically; ensure no manual DOM manipulation escapes.
- Use `screen` queries for better error messages than destructured render.

**Never:**
- Use Enzyme (`shallow`, `mount`, `wrapper.find`).
- Assert on `component.state()` or internal hook variables.
- Use `waitFor` with `queryBy` — prefer `findBy` for async elements.
- Call `ReactDOM.render` directly — use `render` from RTL.

## Workflow

### 1. Scan for Anti-Patterns

```bash
grep -n "shallow\|mount(\|wrapper\.find\|component\.state\|ReactDOM\.render" "$TARGET" 2>/dev/null
```

Flag Enzyme and legacy React patterns.

### 2. Check Async Handling

Scan for `waitFor` with `queryBy`, missing `await` on `userEvent`, and missing `act`. Each is a potential flaky test.

### 3. Check Hook Tests

Verify hooks are tested with `renderHook`. Flag direct invocation of hooks outside a component.

### 4. Report

Group by smell kind. Include before/after code for each fix.
