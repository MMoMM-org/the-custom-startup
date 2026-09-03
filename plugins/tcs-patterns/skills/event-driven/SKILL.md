---
name: event-driven
description: "Use when designing or reviewing event-driven systems — triggered by requests to audit event schemas, command/event naming, handler idempotency, correlation IDs, or message ordering assumptions."
user-invocable: true
argument-hint: "[service or module to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:event-driven**

Act as an event-driven architecture practitioner. Events are facts that happened — immutable, ordered, and replayable. Commands are intents that may be rejected.

## Interface

EventViolation {
  kind: MUTABLE_EVENT | MISSING_CORRELATION | COMMAND_EVENT_MIX | NON_IDEMPOTENT_HANDLER | ORDERING_ASSUMPTION
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  violations: EventViolation[]
  hasCorrelationId: boolean
  hasIdempotencyKey: boolean
}

## Constraints

**Always:**
- Name events in past tense (`OrderPlaced`, `UserDeleted`) — they are facts, not intentions.
- Name commands in imperative (`PlaceOrder`, `DeleteUser`) — they may be rejected.
- Include correlation ID and event ID in every event for tracing and deduplication.
- Make every event handler idempotent — processing the same event twice must be safe.
- Use immutable data structures for event payloads.

**Never:**
- Include mutable objects or closures in event payloads.
- Assume event ordering across different streams or partitions without explicit sequencing.
- Use an event as a command (triggering behaviour that may be rejected without a command pattern).
- Store derived state only in the event stream without a queryable projection.

## Boundaries

| Concern | Owner |
|---|---|
| Events as **messages** — schema fields, command/event naming, correlation and causation IDs, handler idempotency, ordering and partitioning, outbox, DLQ | **this skill** |
| Events as **persistence** — the append-only log as source of truth, Decider write model, rehydration, event store and optimistic concurrency, projections, event versioning, snapshots | `tcs-patterns:event-sourcing` |
| Read/write separation without an event log | `tcs-patterns:hexagonal` (`reference/cqrs-lite.md`) |

The two are independent: a system can be event-driven over a CRUD database, and event-sourced with no message bus at all. Publishing an event to tell another service something happened needs no event store.

## Reference Materials

- `reference/event-patterns.md` — event schema design, CQRS, saga patterns, transactional outbox, DLQ

## Workflow

### 1. Audit Event Schemas

Read `reference/event-patterns.md` Event Schema Design and Naming Conventions sections.

Find event class/type definitions. For each:
- Past-tense name?
- Immutable fields (readonly, frozen, dataclass)?
- correlation_id / event_id present?

### 2. Audit Command/Event Separation

Flag any past-tense event type that contains handler logic as COMMAND_EVENT_MIX.

### 3. Audit Handler Idempotency

Read `reference/event-patterns.md` Idempotent Handlers section.

For each event handler: does it check for duplicate processing? Does it use an idempotency key or database constraint?

### 4. Report

Group violations by kind. Include concrete fix for each.

Read `reference/event-patterns.md` Anti-Patterns table for common fixes.
