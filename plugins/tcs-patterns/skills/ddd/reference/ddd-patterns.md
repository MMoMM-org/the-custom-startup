# DDD Anti-Pattern Catalog

Adapted from citypaul/.dotfiles

---

## Anti-Patterns

### Anemic Domain Model

Entities are data bags with no behavior. All logic lives in "services."

```typescript
// ❌ Anemic — data bag, no behavior
type Order = { id: string; items: Item[]; total: number; status: string };
const orderService = { calculateTotal: (order: Order) => { order.total = ...; } };

// ✅ Behavior belongs next to the type
const calculateTotal = (order: Order): Money =>
  order.items.reduce((sum, i) => sum + i.price.amount, 0);
```

**Fix:** Put behavior as pure functions next to the types they operate on.

---

### Generic Technical Names

Using `Item`, `Entity`, `Record`, `Data`, `Info` instead of domain terms.

```typescript
// ❌ Generic
type Item = { id: string; text: string; parentId: string };

// ✅ Domain language
type GiftIdea = { id: GiftIdeaId; description: string; occasionId: OccasionId };
```

**Fix:** Always use the glossary. If the domain term is unclear, that's a modeling gap to discuss.

---

### Presentation Logic in Domain

Display formatting in `domain/`. The test: "make this look right for a human" = presentation. "Enforce a business rule" = domain. Purity is not sufficient.

```typescript
// ❌ Pure but NOT domain
export const formatEventDate = (date: string | null) =>
  date ? format(parseISO(date), "MMMM d, yyyy") : undefined;
// → belongs in lib/format.ts

// ✅ Pure AND domain — enforces a business rule
export const isPastEvent = (eventDate: string | null, now: Date) =>
  eventDate ? parseISO(eventDate) < now : false;
```

**Fix:** Move formatting to `lib/`. Only keep business rules in `domain/`.

---

### Leaking Domain Logic

Business logic in route handlers, database queries, or adapters.

```typescript
// ❌ Business rule in route handler
export async function POST(request: Request) {
  const order = await orderRepo.findById(id);
  if (order.total > 1000) { await requireManagerApproval(order); } // business rule!
}

// ✅ Domain service
const placeOrder = (order: Order): PlaceOrderResult => {
  if (order.total.amount > 1000) return { success: false, reason: 'requires-approval' };
  ...
};
```

---

### Over-Engineering

Not every project needs aggregates, domain events, or bounded contexts.

**Start with:**
1. Ubiquitous language (glossary)
2. Value objects and entities
3. Add complexity only when the domain demands it

---

### Resisting Model Evolution

Treating the initial model as sacred — refusing to rename types, split aggregates, or restructure bounded contexts as understanding deepens.

**Fix:** The model should evolve continuously. Evans calls moments of fundamental improvement "breakthroughs." TDD and behavioral tests make this evolution safe.

---

### Temporary Invalid States

Allowing an entity to exist in an invalid state, even briefly.

```typescript
// ❌ Constructor that requires a follow-up call
const order = new Order();
order.initialize(items, customer); // required but not enforced

// ✅ Factory enforces invariants on construction
const createOrder = (items: readonly Item[], customer: Customer): Order => {
  if (items.length === 0) throw new Error('Order must have items');
  return OrderSchema.parse({ id: createOrderId(), items, customer, status: 'draft' });
};
```

---

### Aggregate Too Large

Including entities that don't need to be in the same aggregate.

```typescript
// ❌ Too large — User doesn't need to be inside Occasion
type Occasion = {
  readonly organizer: User;
  readonly contributors: User[];
  readonly giftIdeas: GiftIdea[];
};

// ✅ Right size — reference by ID
type Occasion = {
  readonly organizerId: UserId;
  readonly giftIdeas: ReadonlyArray<GiftIdea>;
  readonly budget: Money;
};
```

**Rule:** Include only what's needed to enforce a consistency invariant.

---

### Using Repositories for Cross-Aggregate Reads

Repositories enforce aggregate boundaries — correct for writes, wrong for display reads that need to JOIN.

```typescript
// ❌ N+1 queries through repositories
const events = await eventRepo.findAll();
const details = await Promise.all(events.map(e => occasionRepo.findById(e.occasionId)));

// ✅ Query function JOINs freely (CQRS-lite)
const getEventSummaries = async (db: Database) =>
  db.select({ ... }).from(events).innerJoin(occasions, ...).all();
```

---

## Checklist

- [ ] Glossary file exists and is up to date
- [ ] All types use glossary terms (no `Item`, `Entity`, `Data`)
- [ ] All functions use glossary verbs and nouns
- [ ] All test descriptions use domain language
- [ ] Value objects are immutable and identity-less
- [ ] Entities are always valid (invariants enforced on construction and transitions)
- [ ] Branded IDs for entities; branded types for safety-critical primitives
- [ ] Aggregate roots enforce all invariants
- [ ] Other aggregates referenced by ID, not embedded
- [ ] Cross-aggregate logic in domain services, not crammed into one entity
- [ ] Repository interfaces defined in domain layer
- [ ] Discriminated unions have exhaustive switch handling
- [ ] Expected business outcomes use result types, not exceptions
- [ ] Domain logic has zero infrastructure dependencies
- [ ] Presentation logic is NOT in domain/ (even if pure)
- [ ] Tests organized by domain concept, not implementation file
