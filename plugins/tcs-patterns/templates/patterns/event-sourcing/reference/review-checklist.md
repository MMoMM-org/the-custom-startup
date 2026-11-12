# Review Checklist (step 10)

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
