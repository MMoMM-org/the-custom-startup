---
name: event-sourcing
description: "Use when designing, implementing, or auditing an event-sourced context — triggered by work on an append-only log as the source of truth, a Decider write model (decide/evolve/initialState), rehydration by folding, an event store port with optimistic concurrency, projections and read models, event versioning and upcasters, snapshots, crypto-shredding, or the prior question of whether event sourcing is the right rung at all."
user-invocable: true
argument-hint: "[bounded context, module, or path to design or audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:event-sourcing**

Act as an event-sourcing practitioner. Event sourcing stores every change as an immutable, past-tense fact and derives state by folding them: `state = events.reduce(evolve, initialState)`. The log is the truth; aggregate state, read models and search indexes are disposable derivations you can delete and rebuild.

Two positions decide most of the work:

- **It is the top of the complexity ladder, not a default.** The first job on any request is to check which rung the problem actually needs. Most features stop at explicit return values, an audit table, or the outbox pattern. Greg Young: *"The largest failure I see from people using event sourcing is that they try to use it everywhere."*
- **The write model is pure, so the hard parts are all at the edges.** `decide` and `evolve` are plain functions over plain data and take minutes to get right. Optimistic concurrency, versioning, projection idempotency and replay-safety are where event-sourced systems actually fail.

## Interface

EventSourcingDefect {
  site: string        // file:line, stream name, projection name, or "absent"
  area: ADOPTION | EVENT_MODEL | DECIDER | STORE | PROJECTION | VERSIONING | OPERATIONS
  kind: WRONG_RUNG | CRUD_EVENT | RULES_IN_EVOLVE | NO_EXPECTED_VERSION | MUTATED_HISTORY
      | NO_VERSION_STRATEGY | NON_IDEMPOTENT_PROJECTION | SNAPSHOT_AS_TRUTH
      | UNBOUNDED_STREAM | REPLAY_SIDE_EFFECT | STORE_AS_QUERY_API
  severity: CRITICAL | HIGH | MEDIUM | LOW
  fix: string
}

Decider<State, Command, Event> {
  initialState: State                              // the state of a stream with zero events
  decide: (command, state) => Decision<Event>      // all business rules; accept-with-events or reject-with-reason
  evolve: (state, event) => State                  // applies valid facts; no command rules
  isTerminal?: (state) => boolean                  // optional end state
}

State {
  target = $ARGUMENTS
  contexts: { eventSourced: string[], crud: string[] }
  defects: EventSourcingDefect[]
}

## Constraints

**Always:**
- Rebuild state by folding `evolve` over the stream. A current-state row stored alongside the log is a second truth, and the two will diverge.
- Put every business rule in `decide`, returning accept-with-events or reject-with-reason. Expected business outcomes are result types, not exceptions.
- Append with an expected version. Without it, two concurrent withdrawals both pass the balance check and overdraw the account.
- Resolve a version conflict by reloading and re-deciding against fresh state — bounded, so a hot stream cannot spin forever. Never re-append events computed against state that has moved.
- Capture in the event the values that were true when it happened — the price charged, the rate applied. An event must be interpretable years later without joining to a mutable table.
- Validate stored events against a schema on read, *then* upcast, before `evolve` ever sees them. Stored JSON is untrusted input crossing a trust boundary.
- Key projection writes on the event id or the global position. Stream versions repeat across streams, so a bare version guard is safe only for a read-model row scoped to one stream.
- Keep `decide` deterministic. Time and identifiers arrive through the command; the domain calls no clock, no random, no I/O.

**Never:**
- Update or delete a stored event. Correct a mistake by appending a compensating event, the way an accountant posts a reversal. *"The moment you allow a single edit, everything becomes suspect."*
- Put command policy in `evolve`. A known event that cannot follow the current state is corrupt history — surface it; a silent no-op hides a real corruption.
- Treat a snapshot as authoritative. If you cannot delete every snapshot and rebuild identically, the log has stopped being the source of truth.
- Let another context subscribe to your internal domain events — that makes your persistence your public API. Publish deliberate, versioned integration events instead.
- Fire external side effects from `evolve` or a projection rebuild. A replay does not know it is a replay, and neither will the payment gateway.
- Ship v1 events without a plan for reading them from v2 code. Events are immutable and permanent; you *will* need to read old shapes.
- Query the event store to answer a user's question. It answers get-by-id; everything else is a projection.
- Adopt event sourcing system-wide. It is a per-bounded-context choice, and most contexts are CRUD.

## Boundaries

| Concern | Owner |
|---|---|
| Events as **persistence** — the log as source of truth, decider, rehydration, event store, projections, versioning, snapshots | **this skill** |
| Events as **messages** — schema fields, past-tense naming, correlation and causation IDs, handler idempotency, ordering and partitioning, DLQ, transactional outbox | `tcs-patterns:event-driven` |
| Aggregate boundaries and the invariants that justify them, bounded contexts, ubiquitous language | `tcs-patterns:ddd` |
| The event store as a driven port, keeping the domain free of infrastructure, fakes for driven ports, CQRS-lite for contexts that are *not* event-sourced | `tcs-patterns:hexagonal` |
| Schema-first parsing at the boundary, branded IDs, discriminated unions with exhaustive `never` guards | `tcs-patterns:typescript-strict` |
| Test structure, factories, behaviour through the public API | `tcs-patterns:testing` |
| Purity, immutability, errors as values | `tcs-patterns:functional` |

The split with `event-driven` is the one that matters: **that** skill owns how a message is shaped and delivered, **this** one owns whether the log is the truth. A system can be event-driven over a CRUD database, and event-sourced with no message bus at all. Event naming and correlation-ID rules stay with `event-driven` — this skill does not restate them.

## Reference Materials

| Reference | Load when |
|---|---|
| `reference/when-to-use.md` | Deciding whether to adopt it — the complexity ladder, the costs, and the distinctions from CQRS, event-driven architecture, Kafka, and audit logs/CDC |
| `reference/modelling-events.md` | Discovering and naming events — EventStorming, commands vs events, granularity (thin/fat/summary), the internal/external split |
| `reference/decider-and-rehydration.md` | Writing the decide/evolve pair — the `Decision` type, determinism, the retrying command handler, decider composition |
| `reference/event-store.md` | Designing the port and its adapter — the Postgres schema and compare-and-swap append, the event envelope, tolerant deserialization, the TS/Node tooling landscape |
| `reference/projections-and-read-models.md` | Building read models — inline/live/async, catch-up subscriptions and checkpoints, idempotency, read-your-writes, rebuilds |
| `reference/event-versioning.md` | Evolving event schemas — tolerant readers, upcasting, copy-transform, and how to need less versioning |
| `reference/testing-event-sourced-systems.md` | Testing deciders, projections and upcasters as behaviour, and why the literature's given-when-then is the decider's algebra |
| `reference/production-concerns.md` | Snapshots, short streams, sagas, delivery guarantees, compensating events, GDPR and crypto-shredding, the full anti-pattern catalogue |
| `reference/references.md` | Checking the rationale or primary source behind a piece of this guidance |

## Workflow

### 1. Check the rung before anything else

Event sourcing is a modelling decision, not a storage optimisation. The ladder — explicit return values → in-process domain events → outbox → event sourcing — is climbed one rung at a time.

Ask the one question: **is the history of what happened part of the domain?** Not "would an audit trail be nice", but does the business reason in past events, need to reconstruct past state, or want several independently-evolving views over the same facts?

| Symptom | Rung |
|---|---|
| Forms over data, no meaningful history | current-state storage |
| "Who changed what, when" | append-only audit table |
| Other services must learn that something happened | outbox pattern (`tcs-patterns:event-driven`) |
| History is a first-class requirement; multiple read models over the same facts | event sourcing |

Record the verdict per bounded context and name the contexts that stay CRUD. Adopting it beyond the one or two contexts whose history is part of the domain is `WRONG_RUNG` at CRITICAL — it is the defect that gets the pattern ripped out later. See `reference/when-to-use.md`.

### 2. Audit the event model

Events are the most permanent thing in the system; they are replayed for as long as it lives.

- **No CRUD events.** `AccountCreated`/`AccountUpdated`/`AccountDeleted` is a database changelog in costume — it records that data changed, not what happened. `AccountOpened`, `AddressCorrected`, `AccountClosed` record intent. Flag as `CRUD_EVENT`.
- **Self-contained facts.** Values captured at the moment, not references resolved later. An event carrying only an id forces subscribers to call back, reintroducing the coupling the log was meant to remove.
- **Discriminated unions** with a `type` discriminant and exhaustive `never`-guarded handling, matching commands and state.
- **Internal and external events are split.** Internal events stay free to change; what leaves the context is a deliberate, versioned contract.

Naming and envelope fields are `tcs-patterns:event-driven`'s call — apply that skill rather than re-deriving them here. Depth on discovery, granularity and the internal/external split is in `reference/modelling-events.md`.

### 3. Audit the decider

The write model is a **Decider** — one aggregate as three pure functions, enforcing the invariants `tcs-patterns:ddd` requires of an aggregate root, but persisted as its events rather than as its state. The division of labour is strict, and getting it wrong rots the whole model:

- `decide` holds **all** business rules, reads state, and returns accept-with-events or reject-with-reason. No side effects, no storage, no clock.
- `evolve` holds **no** command rules. It applies every valid stored event exhaustively. A known event that cannot follow the current state is corrupt history and must surface as such.

```bash
# Business rules smuggled into replay, and non-determinism in the domain
grep -rnE "const evolve|function evolve" src/ | head
grep -rnE "Date\.now\(\)|new Date\(\)|Math\.random|randomUUID" src/domain/ 2>/dev/null | head
```

A rejection the business wants to keep — a declined withdrawal worth analysing for fraud — is an *event*, not a `Decision` rejection. See `reference/decider-and-rehydration.md`.

### 4. Verify the command handler loop

Every event-sourced write is the same four moves, and the fourth is the one that gets skipped:

```typescript
const { events, version } = await store.readStream(streamId);   // 1. load
const state = events.reduce(evolve, initialState);              // 2. rehydrate (pure)
const decision = decide(command, state);                        // 3. decide (pure)
if (!decision.accepted) return { success: false, reason: decision.reason };
const outcome = await store.appendToStream(                     // 4. append, asserting the stream has not moved
  streamId, decision.events, { expectedVersion: version },
);
```

An append without `expectedVersion` is `NO_EXPECTED_VERSION` at CRITICAL: concurrent commands silently violate invariants. A conflict means the state you decided against is stale, so the handler reloads and re-decides — bounded, then surfaces `concurrent-modification`. The production form of the loop is in `reference/decider-and-rehydration.md`.

### 5. Check the store contract

Whatever the technology, an event store must provide append-only writes, gapless ordering within a stream, optimistic concurrency on an expected version, and read-a-stream. Production adds global ordering and subscriptions.

It is a **driven port** — define the interface in application language beside the handler that consumes it, implement it in an adapter, and translate any library's thrown `ConcurrencyError` into a returned result at that boundary so the domain stays exception-free for expected outcomes.

Check that stored events are parsed against a schema on read before anything folds them, and that the envelope (id, type, stream id, version, global position, timestamp, correlation/causation metadata) is separate from the domain payload. `reference/event-store.md` has the Postgres schema, the atomic compare-and-swap append, and an honest read of Emmett, KurrentDB, message-db and DynamoDB.

### 6. Demand a versioning strategy

Because events are immutable, **all schema change happens at read time**. A system with no strategy is `NO_VERSION_STRATEGY` at HIGH before a single event has been written — the cost lands later, when it is unaffordable.

- A **tolerant reader** is the day-one baseline: map JSON into the current type, ignore unknown fields, and default only what is genuinely derivable and context-invariant.
- An **upcaster** handles anything more than additive. Pure, chainable, no I/O — an upcaster that calls the network turns every replay into an N+1 storm.
- Young's test: a new version must be derivable from the old. If it is not, it is a **new event type**, not a new version. A field's *meaning* never changes within a version, and a field is never renamed silently.

See `reference/event-versioning.md`.

### 7. Audit projections and read models

The log only answers get-by-id, so every query is served by a projection — another fold, into a query-shaped view.

- **Idempotency is mandatory.** Delivery is at-least-once, so a projection may see the same event twice. Key on the event id or global position; a projection that adds to a running total without a redelivery guard is `NON_IDEMPOTENT_PROJECTION` at HIGH — a latent data-corruption bug.
- **Checkpoints** advance in the same transaction as the projection write, under a single ordered owner. Exercise two concurrent workers, a crash before commit, and an out-of-order position in the tests.
- **Eventual consistency is the headline trade-off**, not a defect. The classic failure is POST-redirect-GET into a 404. Prefer returning the just-written state from the command; design the UI for lag rather than pretending it away. Monitor projection lag as a first-class metric.
- **Projections are disposable.** Fix a bad one by correcting `apply`, resetting the view and checkpoint, and replaying. Never hand-edit rows — the next rebuild silently reverts the edit.

See `reference/projections-and-read-models.md`.

### 8. Test as behaviour

The write model is pure data in, pure data out, so no mocks are needed anywhere.

The literature's `given(events).when(command).then(events)` is not a convention — it is the decider's algebra named. Express it in the repository's established style (`tcs-patterns:testing`): fold factory-built events with `evolve` for the starting state, call `decide` directly, assert on the returned events. Do not introduce a DSL only because event-sourcing texts use one.

Do not write a 1:1 `evolve` test per transition — that pins an implementation detail. The decider tests already fold through it. Beyond that: the command handler against an in-memory `EventStore` fake (a real implementation backed by a `Map`, not a mock), projections fed a sequence and asserted on the view, a redelivery test proving no double-count, and every upcaster tested both directly and folded through the *current* `evolve`. That last one catches a versioning bug before it corrupts a replay. See `reference/testing-event-sourced-systems.md`.

### 9. Check the operational surface

- **Snapshots**, if any, are a rebuildable cache — test the system with and without them. Most streams never need one; `SNAPSHOT_AS_TRUTH` is CRITICAL.
- **Short streams** beat snapshots. Give a stream an explicit lifetime and close the books at a natural business boundary with a summary event that opens the next one. An ever-growing stream is `UNBOUNDED_STREAM`.
- **Cross-aggregate work is a process manager**, never a distributed transaction. The stream is the consistency boundary.
- **Replay must not re-fire real-world effects.** Side effects live in handlers excluded from replay and idempotent under redelivery. `REPLAY_SIDE_EFFECT` is CRITICAL.
- **PII in an append-only log** needs a decision before the first event: crypto-shredding, forgettable payloads, segregation, or retention. Encrypted personal data may still be personal data in law — get compliance sign-off rather than assuming the technique settles it.
- **Back up the log.** Everything else is derived.

See `reference/production-concerns.md`.

### 10. Report

Group defects by `area`, and lead with the ones that cannot be fixed later: `WRONG_RUNG` (the pattern should not be here at all), `NO_EXPECTED_VERSION` and `MUTATED_HISTORY` (the guarantees are already broken), `NO_VERSION_STRATEGY` (the cost compounds with every event written).

Before closing, check these:

- [ ] Adoption is per bounded context, justified by history being part of the domain, with a cheaper rung ruled out
- [ ] Events are intention-revealing business facts, self-contained, modelled as discriminated unions — no CRUD events
- [ ] Internal events are separated from the published external contract
- [ ] `decide` holds all rules and returns accept-with-events or reject-with-reason; `evolve` holds none and surfaces corrupt history
- [ ] `decide` is deterministic — time and ids arrive through the command
- [ ] State is a fold; no current-state row competes with the log
- [ ] Every append asserts an expected version, and conflicts reload-and-re-decide within a bound
- [ ] The event store is a driven port with a test fake; the domain has zero infrastructure imports
- [ ] Stored events are schema-validated on read, then upcast, before `evolve`
- [ ] A versioning strategy exists — tolerant reader at minimum — and upcasters are pure and tested
- [ ] Read models are rebuildable projections with checkpoints; every one is idempotent under redelivery
- [ ] The UI accounts for eventual consistency, and projection lag is monitored
- [ ] Snapshots are a rebuildable cache; streams have a bounded lifetime
- [ ] No external side effect can fire during a replay or rebuild
- [ ] A PII strategy is decided if events carry personal data
