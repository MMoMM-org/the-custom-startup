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
- Justify every aggregate boundary by an invariant it enforces, never by an entity relationship. If you cannot name what must remain true after a state change, there is no aggregate there — see `reference/aggregate-design.md`.
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

*How* an aggregate is persisted is out of scope here. If its events are the source of truth rather than its state, `tcs-patterns:event-sourcing` owns the write model (the Decider), the event store, and replay; `tcs-patterns:event-driven` owns publishing those events to other contexts.

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
- **Relationship-driven aggregates** → MEDIUM violation. The tell: the aggregate's methods only add, remove, or attach children, and no business rule is enforced anywhere in it. Those relationships want to be foreign keys. Ask "what must remain true when this changes?" — if the only answer is structural, the aggregate is ceremony.
- Aggregates carrying read-only properties that exist purely for query convenience → MEDIUM violation (a read concern leaking into a write model)

### 3. Audit Language Consistency

**The glossary is the naming authority, not a suggestion.** Locate the repository's declared glossary — a `GLOSSARY.md`, a glossary section in domain docs, or the terms fixed in `reference/bounded-contexts.md`. If the project has none, that is the finding: an undeclared ubiquitous language cannot be violated, and cannot be enforced either. Report it and stop auditing terms.

With a glossary in hand, run the protocol:

1. **Detect** — find code terms that diverge from it: synonyms (`Client` where the glossary says `Customer`), generic stand-ins (`Item`, `Data`, `Manager`), and terms used in code that the glossary never defines.
2. **Propose** — for each divergence, name the glossary term it should be, or propose the glossary entry it is missing. A divergence is one of the two; it is never just "inconsistent".
3. **Decide** — a term used consistently in code but absent from the glossary is a *language change*, not a violation. Surface it as a decision for the user, not a defect.
4. **Record** — an accepted change updates the glossary first. The glossary leads; code follows.
5. **Rename** — only then rename in code, in one pass, so the two never drift apart mid-change.

Severity: a term contradicting the glossary is MEDIUM (the model and the language disagree). A term missing from the glossary is LOW (a gap to close). An absent glossary is HIGH — nothing downstream of it can be enforced.

*The glossary-as-authority protocol is adapted from `citypaul/.dotfiles`' `ubiquitous-language` skill; see ADR 0002 for why it lives here rather than as its own skill.*

### 4. Report Findings

Present violations grouped by severity. For each: file, issue, recommended fix.

Read `reference/ddd-patterns.md` for anti-pattern catalog and fix templates.
