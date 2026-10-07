# Testing Through the Public API

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
  expect(result).toEqual({ success: false, error: expect.stringContaining('Amount must be positive') });
});
```

**Why assert the whole result?** Two reasons, and both bite in practice:

1. `expect(result.success).toBe(false)` does **not** narrow a discriminated union. A following `result.error` is member access on the un-narrowed `Result`, which fails to compile under strict TypeScript — see `tcs-patterns:typescript-strict`.
2. `toEqual` pins the entire result shape, so a mutation that corrupts or adds an unasserted field fails the test. Split assertions leave those fields unchecked and let such mutants survive — see `tcs-patterns:mutation-testing`.

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
