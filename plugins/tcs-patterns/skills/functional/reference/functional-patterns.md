# Functional Patterns Reference

Adapted from citypaul/.dotfiles

---

## Core Principles

- **No data mutation** — immutable structures only
- **Pure functions** wherever possible
- **Composition** over inheritance
- **Self-documenting code** — no comments needed
- **Array methods** over loops
- **Options objects** over positional parameters

---

## Functional Light

We follow "Functional Light" — practical patterns without heavy abstractions.

**What we DO:** Pure functions, immutable data, composition, declarative code, array methods, type safety, `readonly`

**What we DON'T do:** Category theory, monads, heavy FP libraries (fp-ts, Ramda), over-engineering

**Why:** The goal is maintainable, testable code — not academic purity.

---

## Immutable Array Operations

Complete catalog of mutations and their immutable alternatives:

```typescript
// ❌ WRONG - Mutations
items.push(newItem);        // Add to end
items.pop();                // Remove last
items.unshift(newItem);     // Add to start
items.shift();              // Remove first
items.splice(index, 1);     // Remove at index
items.reverse();            // Reverse
items.sort();               // Sort
items[i] = newValue;        // Update at index

// ✅ CORRECT - Immutable alternatives
const withNew = [...items, newItem];
const withoutLast = items.slice(0, -1);
const withFirst = [newItem, ...items];
const withoutFirst = items.slice(1);
const removed = [...items.slice(0, index), ...items.slice(index + 1)];
const reversed = [...items].reverse();   // copy first!
const sorted = [...items].sort();        // copy first!
const updated = items.map((item, idx) => idx === i ? newValue : item);
```

Common patterns:

```typescript
const withoutItem = items.filter(item => item.id !== targetId);
const replaced = items.map(item => item.id === targetId ? newItem : item);
const inserted = [...items.slice(0, index), newItem, ...items.slice(index)];
```

---

## Immutable Object Updates

```typescript
// ❌ WRONG
user.name = "New";
Object.assign(user, { name: "New" });

// ✅ CORRECT
const updated = { ...user, name: "New" };

// ✅ CORRECT - Nested update
const updatedCart = {
  ...cart,
  items: cart.items.map((item, i) =>
    i === targetIndex ? { ...item, quantity: newQuantity } : item
  ),
};
```

---

## Readonly Keyword

Use `readonly` on all data structures to signal immutability:

```typescript
// ✅ CORRECT
type Scenario = {
  readonly id: string;
  readonly name: string;
  readonly mocks: ReadonlyArray<Mock>;
};

// ❌ WRONG - mutable
type Scenario = {
  id: string;
  mocks: Mock[];
};
```

---

## Array Methods Over Loops

```typescript
// ✅ Map — transform each element
const scenarioIds = scenarios.map(s => s.id);

// ✅ Filter — select subset
const activeScenarios = scenarios.filter(s => s.active);

// ✅ Reduce — aggregate values
const total = items.reduce((sum, item) => sum + item.price * item.quantity, 0);

// ✅ Chain for complex transformations
const total = items
  .filter(item => item.active)
  .map(item => item.price * item.quantity)
  .reduce((sum, price) => sum + price, 0);
```

When loops are acceptable: early termination (use `Array.find()`), performance-critical paths (measure first), necessary side effects.

---

## Options Objects Over Positional Parameters

```typescript
// ❌ WRONG - positional, unclear call site
createPayment(100, 'GBP', 'card_123', '123', true, false);

// ✅ CORRECT - named, self-documenting
type CreatePaymentOptions = {
  amount: number;
  currency: string;
  cardId: string;
  cvv: string;
  saveCard?: boolean;
  sendReceipt?: boolean;
};

createPayment({
  amount: 100,
  currency: 'GBP',
  cardId: 'card_123',
  cvv: '123',
  saveCard: true,
});
```

Use positional when: 1-2 params max, obvious order (e.g., `add(a, b)`).

---

## Pure Functions

No side effects, deterministic output. Same input → same output.

```typescript
// ❌ WRONG - mutation + external state
function addScenario(scenarios: Scenario[], newScenario: Scenario): void {
  scenarios.push(newScenario);
}

// ✅ CORRECT - pure
function addScenario(
  scenarios: ReadonlyArray<Scenario>,
  newScenario: Scenario,
): ReadonlyArray<Scenario> {
  return [...scenarios, newScenario];
}
```

**Isolate impure functions at edges** (adapters, ports). Keep core domain logic pure.

---

## Early Returns Over Nesting

**Max 2 levels of function nesting.** Beyond that, extract functions.

```typescript
// ❌ WRONG - deep nesting
function processOrder(order: Order) {
  if (order.items.length > 0) {
    if (order.customer.verified) {
      if (order.total > 0) { /* ... */ }
    }
  }
}

// ✅ CORRECT - guard clauses (early returns)
function processOrder(order: Order) {
  if (order.items.length === 0) return;
  if (!order.customer.verified) return;
  if (order.total <= 0) return;
  // main logic at top level
}
```

---

## Result Type for Error Handling

```typescript
type Result<T, E = Error> =
  | { readonly success: true; readonly data: T }
  | { readonly success: false; readonly error: E };

function processPayment(payment: Payment): Result<Transaction> {
  if (payment.amount <= 0) {
    return { success: false, error: new Error('Invalid amount') };
  }
  return { success: true, data: executePayment(payment) };
}

// Caller handles both cases explicitly
const result = processPayment(payment);
if (!result.success) { console.error(result.error); return; }
console.log(result.data.transactionId);  // TypeScript knows data exists
```

---

## Summary Checklist

- [ ] No data mutation — using spread operators
- [ ] Pure functions wherever possible (no side effects)
- [ ] Self-documenting code (no comments needed)
- [ ] Array methods (`map`, `filter`, `reduce`) over loops
- [ ] Options objects for 3+ parameters
- [ ] Composed small functions, not complex monoliths
- [ ] `readonly` on all data structure properties
- [ ] `ReadonlyArray<T>` for immutable arrays
- [ ] Max 2 levels of nesting (use early returns / guard clauses)
- [ ] Result types for error handling
