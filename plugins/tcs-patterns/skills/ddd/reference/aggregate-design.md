# Aggregate Design

Aggregates are the hardest part of DDD to get right. Start small and tighten boundaries when you hit consistency issues.

## Design From Invariants, Not Relationships

The most common aggregate mistake is starting from entity relationships. You see "Route has many Locations, Location has one VendingMachine" and build a hierarchy mirroring that structure. The result *looks* domain-rich — organised entities, nested value objects, accessor methods — while concealing that no business behavior is being enforced anywhere.

**Aggregates are consistency boundaries, not containment hierarchies.** An aggregate exists to enforce invariants during state changes. If you cannot name the invariant, you do not need the aggregate.

The litmus test for what belongs inside one:

1. What commands change state in this area of the domain?
2. What must remain true immediately after each of those changes? — these are the invariants
3. What data is required to enforce them? — **only this** belongs in the aggregate

If the answer to (2) is only structural — one-to-many, one-to-one — a database constraint enforces it more simply and more reliably than aggregate code. Reserve aggregates for behavioral invariants: limits, conditions, what is allowed when.

```typescript
// ❌ RELATIONSHIP-DRIVEN — mirrors the entity hierarchy, enforces nothing
type Route = {
  readonly id: RouteId;
  readonly locations: ReadonlyArray<Location>;   // why is this here?
  readonly addLocation: ...;                     // manages a collection
  readonly attachVendingMachine: ...;            // manages a relationship
  readonly getAlarmCount: ...;                   // a read concern, leaking in
};

// ✅ INVARIANT-DRIVEN — VendingMachine is its own aggregate,
//    because the alarm limit is a behavioral responsibility
type VendingMachine = {
  readonly id: VendingMachineId;
  readonly locationId: LocationId;               // referenced by ID
  readonly alarms: ReadonlyArray<Alarm>;
  readonly maxConcurrentAlarms: number;          // the invariant
};

const triggerAlarm = (machine: VendingMachine, alarm: NewAlarm): TriggerAlarmResult => {
  const active = machine.alarms.filter(a => a.status === 'active');
  if (active.length >= machine.maxConcurrentAlarms) {
    return { success: false, reason: 'max-alarms-reached' };
  }
  return { success: true, machine: { ...machine, alarms: [...machine.alarms, alarm] } };
};
```

**The tell** that an aggregate is relationship-driven: its methods only add, remove, or attach children, and no business rule is enforced anywhere in it. Those relationships want to be foreign keys, not an aggregate hierarchy.

## The Always-Valid Principle

An entity must satisfy its invariants at all times — after construction, after every state transition, and when retrieved from persistence.

```typescript
// ✅ Factory function enforces invariants on creation
const createOccasion = (params: CreateOccasionParams): Occasion => {
  if (!params.name.trim()) throw new Error('Occasion name is required');
  if (params.budget.amount < 0) throw new Error('Budget cannot be negative');
  return OccasionSchema.parse({
    id: createOccasionId(),
    name: params.name.trim(),
    budget: params.budget,
    giftIdeas: [],
    ...params,
  });
};

// ✅ State transition enforces invariants — returns result type for business outcomes
type AddGiftIdeaResult =
  | { readonly success: true; readonly occasion: Occasion }
  | { readonly success: false; readonly reason: 'exceeds-budget' };

const addGiftIdea = (occasion: Occasion, idea: NewGiftIdea): AddGiftIdeaResult => {
  const totalCost = occasion.giftIdeas.reduce((sum, i) => sum + i.estimatedCost.amount, 0);
  if (totalCost + idea.estimatedCost.amount > occasion.budget.amount) {
    return { success: false, reason: 'exceeds-budget' };
  }
  return { success: true, occasion: { ...occasion, giftIdeas: [...occasion.giftIdeas, idea] } };
};
```

**Never allow temporary invalid states**, even in "internal" code. If an entity can be constructed without meeting its invariants, that's a bug.

## Sizing Aggregates

The most common mistake is making aggregates too large. Include only what's needed to enforce a consistency rule.

**Ask:** "Does modifying X require checking Y's state to maintain an invariant?"
- If yes: X and Y belong in the same aggregate
- If no: they're separate aggregates, referenced by ID

```typescript
// ❌ TOO LARGE — User doesn't need to be in the Occasion aggregate
type Occasion = {
  readonly organizer: User;         // Embedded user — wrong!
  readonly contributors: User[];    // Embedded users — wrong!
  readonly giftIdeas: GiftIdea[];
};

// ✅ RIGHT SIZE — only what's needed for consistency
type Occasion = {
  readonly organizerId: UserId;     // Reference by ID
  readonly giftIdeas: ReadonlyArray<GiftIdea>;  // Owned — needed for budget invariant
  readonly budget: Money;           // Owned — needed for budget invariant
};
```

## One Aggregate Per Transaction

Don't modify multiple aggregates in a single write operation. If a business process spans aggregates, use:

1. **Domain service** to compute changes across aggregates (pure function)
2. **Use case** to save each aggregate in sequence
3. **Eventual consistency** (domain events) if strong consistency isn't required

```typescript
// Use case saves each aggregate separately
const handlePledge = async (repos, dto) => {
  const result = pledgeContribution(occasion, contributor, amount); // Domain service
  if (result.success) {
    await repos.occasion.save(result.occasion);       // Transaction 1
    await repos.contributor.save(result.contributor);  // Transaction 2
  }
};
```

## Aggregate Root Rules

1. **External access only through the root** — never reach into child entities directly
2. **The root enforces all invariants** — children don't validate themselves in isolation
3. **Delete cascades from the root** — deleting an aggregate deletes all its children
4. **IDs are globally unique for roots** — child entity IDs only need to be unique within the aggregate

## When to Split vs Combine

**Split when:**
- Two things change for different reasons (different business rules)
- Performance: loading the full aggregate is expensive but you usually only need a subset
- Concurrency: multiple users modify different parts simultaneously

**Combine when:**
- An invariant spans both things (budget checking requires knowing all gift ideas)
- They always change together
- Splitting would require a complex coordination mechanism

**Start combined, split when you feel the pain.** Premature splitting creates coordination complexity worse than the performance problem it prevents. Aggregate boundaries are expected to evolve as domain understanding deepens — splitting or merging aggregates is a normal part of DDD, not a sign of failure.

## Concurrency: Optimistic Locking

When multiple users can modify the same aggregate concurrently, add a version field to detect conflicts:

```typescript
type Occasion = {
  readonly id: OccasionId;
  readonly version: number;  // incremented on each save
  readonly name: string;
  readonly budget: Money;
  readonly giftIdeas: ReadonlyArray<GiftIdea>;
};
```

The repository checks the version on save:

```typescript
save: async (occasion) => {
  const updated = await db.update(occasions)
    .set({ ...toRow(occasion), version: occasion.version + 1 })
    .where(and(eq(occasions.id, occasion.id), eq(occasions.version, occasion.version)));
  if (updated.rowsAffected === 0) throw new Error('Concurrent modification detected');
},
```

If two users load version 3 and both try to save, the first succeeds (version becomes 4) and the second fails (version 3 no longer matches). The use case catches this and asks the user to retry.

**When to add optimistic locking:**
- Multiple users can edit the same aggregate
- The aggregate is long-lived (not created and discarded in one request)
- Concurrent modifications would violate invariants

**When it's unnecessary:**
- Single-user aggregates (e.g., user preferences)
- Append-only aggregates (e.g., event logs)
- Short-lived aggregates created and consumed in one request
