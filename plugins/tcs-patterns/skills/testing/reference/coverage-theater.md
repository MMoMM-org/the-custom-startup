# Coverage Theater Detection

Watch for these patterns that give fake 100% coverage.

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

For the falsifiable check that assertions would catch a real defect, load `tcs-patterns:mutation-testing`.
