---
name: ddd
description: "Use when auditing or designing a domain model — triggered by requests to review bounded contexts, aggregate roots, value objects, domain events, or ubiquitous language consistency."
user-invocable: true
argument-hint: "[path or scope to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:ddd**

Act as a Domain-Driven Design practitioner. Protect the domain model from infrastructure concerns and enforce bounded context boundaries at every code review and design session.

## Interface

Violation {
  layer: Domain | Application | Infrastructure
  concept: string       // e.g. "aggregate root", "value object"
  file: string
  issue: string
  fix: string
}

State {
  target = $ARGUMENTS
  bounded_contexts: string[]
  violations: Violation[]
}

## Constraints

**Always:**
- Use the bounded context's ubiquitous language in all naming — classes, methods, variables.
- Protect aggregate invariants: all state changes go through the aggregate root.
- Represent domain events as immutable value objects with past-tense names.
- Keep domain layer free of framework imports (no ORM annotations, no HTTP types).
- Define repositories as domain interfaces; place implementations in infrastructure.

**Never:**
- Let infrastructure concerns leak into domain entities or value objects.
- Reference another bounded context's domain objects directly — use ACL or shared kernel.
- Put business logic in application services or controllers.
- Use primitive obsession — wrap domain concepts in value objects.

## Reference Materials

- `reference/ddd-patterns.md` — ddd patterns

## Workflow

### 1. Identify Bounded Contexts

Scan `$ARGUMENTS` for package/module boundaries. Map each module to a bounded context. Flag any cross-context imports as MEDIUM violations.

### 2. Audit Domain Layer

For each class in the domain layer:
- Entity: has identity, mutable through aggregate root only
- Value object: immutable, equality by value, no identity
- Aggregate root: controls all writes to its cluster

Flag:
- Entities with public setters → violation (bypass aggregate root)
- Value objects with mutable state → violation
- Domain classes importing infrastructure types → CRITICAL violation

### 3. Audit Language Consistency

Grep for terms that differ from the ubiquitous language defined in project docs or comments. Flag naming inconsistencies as LOW violations.

### 4. Report Findings

Present violations grouped by severity. For each: file, issue, recommended fix.

Read `reference/ddd-patterns.md` for anti-pattern catalog and fix templates.
