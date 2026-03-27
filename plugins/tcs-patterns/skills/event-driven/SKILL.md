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

## Workflow

### 1. Audit Event Schemas

Find event class/type definitions. For each:
- Past-tense name?
- Immutable fields (readonly, frozen, dataclass)?
- correlation_id / event_id present?

### 2. Audit Command/Event Separation

Flag any past-tense event type that contains handler logic as COMMAND_EVENT_MIX.

### 3. Audit Handler Idempotency

For each event handler: does it check for duplicate processing? Does it use an idempotency key or database constraint?

### 4. Report

Group violations by kind. Include concrete fix for each.
