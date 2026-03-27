---
name: testing
description: Testing patterns for behavior-driven tests. Use when writing tests, creating test factories, structuring test files, or deciding what to test. Do NOT use for UI-specific testing (see frontend-testing or react-testing skills).
user-invocable: true
---

**Active skill: tcs-patterns:testing**

For verifying test effectiveness through mutation analysis, load `tcs-patterns:mutation-testing`.
For evaluating test quality against Dave Farley's properties, load `tcs-patterns:test-design-reviewer`.
For UI testing patterns, load `tcs-patterns:frontend-testing` or `tcs-patterns:react-testing`.

Adapted from citypaul/.dotfiles

---

## Core Principle

**Test behavior, not implementation.** 100% coverage through business behavior, not implementation details.

Validation code in `payment-validator.ts` gets 100% coverage by testing `processPayment()` behavior — NOT by directly testing validator functions.

---

## Test Through Public API Only

Never test implementation details. Test behavior through public APIs.

```typescript
// ❌ WRONG - testing HOW (implementation detail)
it('should call validateAmount', () => {
  const spy = jest.spyOn(validator, 'validateAmount');
  processPayment(payment);
  expect(spy).toHaveBeenCalled();
});

// ❌ WRONG - testing private methods
it('should validate CVV format', () => {
  const result = validator._validateCVV('123');
  expect(result).toBe(true);
});

// ✅ CORRECT - testing behavior through public API
it('should reject negative amounts', () => {
  const payment = getMockPayment({ amount: -100 });
  const result = processPayment(payment);
  expect(result.success).toBe(false);
  expect(result.error).toContain('Amount must be positive');
});
```

---

## Don't Extract for Testability

Never extract a function into its own file purely to give it its own unit test. Extract for readability, DRY (same **knowledge** used in multiple places), or separation of concerns — not testability.

If code is inline in a function, it gets coverage through that function's behavioral tests.

```typescript
// ❌ WRONG — extracted single-use helper with its own test file
// prepare-participant-data.ts (new file, one caller)
export const prepareParticipantData = (items: Item[]) => ({
  yourClaims: items.filter(i => i.isClaimed && i.isClaimedByCurrentUser),
  available: items.filter(i => !i.isClaimedByCurrentUser),
});

// ✅ CORRECT — inline in consumer, tested through its behavior
export const loadParticipantView = async (db, eventId, userId) => {
  const items = await getItems(db, eventId);
  const yourClaims = items.filter(i => i.isClaimed && i.isClaimedByCurrentUser);
  const available = items.filter(i => !i.isClaimedByCurrentUser);
  return { yourClaims, available };
};
```

**When extraction IS justified (DRY):** same filtering logic used by multiple consumers with the same business meaning. But still test it through each consumer's behavior, not as an isolated unit.

---

## No 1:1 Mapping Between Tests and Implementation

Don't create test files that mirror implementation files.

```
# ❌ WRONG
tests/
  payment-validator.test.ts  ← 1:1 mapping
  payment-processor.test.ts  ← 1:1 mapping

# ✅ CORRECT
tests/
  process-payment.test.ts    ← Tests behavior, not implementation files
```

---

## Test Factory Pattern

For test data, use factory functions with optional overrides. **No `let`/`beforeEach` — use factories for fresh state.**

```typescript
// Import real schema — never redefine in tests
import { UserSchema } from '@/schemas/user';

const getMockUser = (overrides?: Partial<User>): User =>
  UserSchema.parse({
    id: 'user-123',
    name: 'Test User',
    email: 'test@example.com',
    role: 'user',
    isActive: true,
    createdAt: new Date('2024-01-01'),
    ...overrides,
  });

// Usage
it('creates user with custom email', () => {
  const user = getMockUser({ email: 'custom@example.com' });
  expect(createUser(user).success).toBe(true);
});
```

**Why validate with schema?** Ensures test data matches production schema. Schema changes fail tests immediately — no silent drift.

### Factory Composition

```typescript
const getMockOrder = (overrides?: Partial<Order>): Order =>
  OrderSchema.parse({
    id: 'order-1',
    items: [getMockItem()],
    customer: getMockCustomer(),
    payment: getMockPayment(),
    ...overrides,
  });

// Override nested objects
it('calculates total with multiple items', () => {
  const order = getMockOrder({
    items: [getMockItem({ price: 100 }), getMockItem({ price: 200 })],
  });
  expect(calculateTotal(order)).toBe(300);
});
```

### Anti-Patterns

```typescript
// ❌ WRONG — shared mutable state
let user: User;
beforeEach(() => { user = { id: 'user-123', name: 'Test User', ... }; });
it('test 1', () => { user.name = 'Modified'; }); // mutates shared state!
it('test 2', () => { expect(user.name).toBe('Test User'); }); // fails!

// ✅ CORRECT — fresh state per test
it('test 1', () => { const user = getMockUser({ name: 'Modified' }); });
it('test 2', () => { const user = getMockUser(); expect(user.name).toBe('Test User'); });

// ❌ WRONG — incomplete objects
const getMockUser = () => ({ id: 'user-123' }); // missing required fields

// ❌ WRONG — redefining schemas in tests
const UserSchema = z.object({ ... }); // already defined in src/schemas/user.ts!
```

---

## Coverage Theater Detection

Watch for these patterns that give fake 100% coverage:

**Pattern 1 — Mock the function being tested:**
```typescript
// ❌ Tests nothing
it('calls validator', () => {
  const spy = jest.spyOn(validator, 'validate');
  validate(payment);
  expect(spy).toHaveBeenCalled(); // meaningless
});
```

**Pattern 2 — Only verify function was called:**
```typescript
// ❌ No behavior validation
it('processes payment', () => {
  const spy = jest.spyOn(processor, 'process');
  handlePayment(payment);
  expect(spy).toHaveBeenCalledWith(payment); // so what?
});
```

**Pattern 3 — 100% line coverage, 0% branch coverage:**
```typescript
// ❌ Only happy path — missing all error branches
it('validates payment', () => {
  expect(validate(getMockPayment()).success).toBe(true);
});
```

---

## Summary Checklist

- [ ] Testing behavior through public API (not implementation details)
- [ ] No mocks of the function being tested
- [ ] No tests of private methods or internal state
- [ ] Factory functions return complete, valid objects
- [ ] Factories validate with real schemas (not redefined in tests)
- [ ] `Partial<T>` for type-safe overrides
- [ ] No `let`/`beforeEach` — factories for fresh state
- [ ] Edge cases covered (not just happy path)
- [ ] Tests survive refactoring of implementation internals
- [ ] No 1:1 mapping between test files and implementation files
