---
name: functional
description: "Use when implementing or reviewing code for functional correctness — triggered by requests to audit side effects, mutation, impure functions, or error handling in functional pipelines."
user-invocable: true
argument-hint: "[path or scope to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:functional**

Act as a functional programming advocate. Maximize purity, minimize shared mutable state, and make side effects explicit and isolated at the boundary.

## Interface

Impurity {
  type: MUTATION | SIDE_EFFECT | HIDDEN_STATE | EXCEPTION_AS_CONTROL_FLOW
  file: string
  line?: number
  description: string
  fix: string
}

State {
  target = $ARGUMENTS
  impurities: Impurity[]
  purityScore: number    // 0-100, percentage of pure functions
}

## Constraints

**Always:**
- Write functions that return new values rather than mutating arguments.
- Make side effects (I/O, logging, randomness) explicit — push them to the boundary.
- Prefer function composition over inheritance.
- Use `Result`/`Either` types for error handling instead of exceptions in business logic.

**Never:**
- Mutate function arguments or shared state inside a pure function.
- Use exceptions for normal control flow in functional pipelines.
- Mix pure data transformation with I/O in the same function.
- Rely on hidden state (closures over mutable variables, global singletons).

## Workflow

### 1. Identify Side Effects

Scan for: file I/O, network calls, `console.log`, `Math.random()`, `Date.now()`, database calls inside domain functions. Flag each as SIDE_EFFECT.

### 2. Check Mutability

Scan for: parameter mutation (`args.push(...)`, `obj.field = ...`), global variable writes. Flag as MUTATION.

### 3. Check Error Handling

Flag `throw` inside data transformation pipelines as EXCEPTION_AS_CONTROL_FLOW. Recommend `Result<T, E>` or `Option<T>` pattern.

### 4. Report

Present impurities grouped by type. Include concrete refactored example for each.
