# Mutation Operators Reference

Adapted from citypaul/.dotfiles

---

## The Core Process

1. **Mutate**: Change production code (flip `*` to `/`, negate a condition)
2. **Run**: Execute the test suite
3. **Evaluate**: Did a test fail?
   - **Yes** → mutant killed (good). Revert.
   - **No** → mutant survived (bad). Add/strengthen a test.
4. **Revert**: Always restore original code before the next mutation

**Always revert each mutation before applying the next. Never leave mutated code in place.**

---

## Mutation Operators

### Arithmetic

| Original | Mutated | Test Should Verify |
|----------|---------|-------------------|
| `a + b` | `a - b` | Addition behavior |
| `a - b` | `a + b` | Subtraction behavior |
| `a * b` | `a / b` | Multiplication behavior |
| `a / b` | `a * b` | Division behavior |
| `a % b` | `a * b` | Modulo behavior |

**Tip:** Tests using identity values (0 for +/-, 1 for */) won't kill arithmetic mutants. Use non-identity values.

```typescript
// ❌ WEAK — 10 * 1 == 10 / 1
expect(calculateTotal(10, 1)).toBe(10);

// ✅ STRONG — 10 * 3 != 10 / 3
expect(calculateTotal(10, 3)).toBe(30);
```

---

### Conditional (Boundary)

| Original | Mutated |
|----------|---------|
| `a < b` | `a <= b` |
| `a <= b` | `a < b` |
| `a > b` | `a >= b` |
| `a >= b` | `a > b` |

**Always test the exact boundary value:**

```typescript
// ✅ Tests both sides of >= 18
expect(isAdult(17)).toBe(false);
expect(isAdult(18)).toBe(true);  // exact boundary
expect(isAdult(19)).toBe(true);
```

---

### Equality

| Original | Mutated |
|----------|---------|
| `a === b` | `a !== b` |
| `a !== b` | `a === b` |

---

### Logical

| Original | Mutated | Test Should Verify |
|----------|---------|-------------------|
| `a && b` | `a \|\| b` | Case where one is true, other false |
| `a \|\| b` | `a && b` | Case where one is true, other false |
| `a ?? b` | `a && b` | Nullish coalescing behavior |

```typescript
// ❌ WEAK — true && true == true || true
expect(canAccess(true, true)).toBe(true);

// ✅ STRONG — true || false != true && false
expect(canAccess(true, false)).toBe(true);   // isAdmin only
expect(canAccess(false, true)).toBe(true);   // isOwner only
expect(canAccess(false, false)).toBe(false); // neither
```

---

### Boolean Literals

| Original | Mutated |
|----------|---------|
| `true` | `false` |
| `false` | `true` |
| `!(a)` | `a` |

---

### Block Statement

| Original | Mutated |
|----------|---------|
| `{ code }` | `{ }` |

Tests that only verify "no error thrown" won't kill block mutations. Verify observable outcomes:

```typescript
// ❌ WEAK — empty function also doesn't throw
it('processes order', () => {
  expect(() => processOrder(order)).not.toThrow();
});

// ✅ STRONG
it('saves order to database', () => {
  processOrder(order);
  expect(orderRepository.save).toHaveBeenCalledWith(order);
});
```

---

### Method Expression (TypeScript/JavaScript)

| Original | Mutated |
|----------|---------|
| `startsWith()` | `endsWith()` |
| `endsWith()` | `startsWith()` |
| `toUpperCase()` | `toLowerCase()` |
| `some()` | `every()` |
| `every()` | `some()` |
| `filter()` | (removed) |
| `min()` | `max()` |
| `max()` | `min()` |
| `trim()` | `trimStart()` |

---

### Optional Chaining

| Original | Mutated |
|----------|---------|
| `foo?.bar` | `foo.bar` |
| `foo?.()` | `foo()` |

---

### Unary Operators

| Original | Mutated |
|----------|---------|
| `+a` | `-a` |
| `-a` | `+a` |
| `++a` | `--a` |
| `a++` | `a--` |

---

## Mutant States

| State | Meaning | Action |
|-------|---------|--------|
| **Killed** | Test failed when mutant applied | Good |
| **Survived** | Tests passed with mutant active | Add/strengthen test |
| **No Coverage** | No test exercises this code | Add behavior test |
| **Equivalent** | Mutant produces same behavior | Document, no action |

**Mutation Score:** `killed / valid * 100`

| Score | Quality |
|-------|---------|
| < 60% | Weak — significant gaps |
| 60–80% | Moderate |
| 80–90% | Good |
| > 90% | Strong |

---

## Equivalent Mutants

Some mutations produce identical behavior (no observable difference). These cannot be killed.

Common patterns:
- Operations with identity elements: `+= 0`, `*= 1`
- Boundary conditions that don't affect outcome when result is same for both branches
- Dead code paths

Document equivalent mutants rather than fighting them. 100% mutation score may not be achievable.

---

## Surviving Mutant: Fixes

### Add Boundary Value Tests

```typescript
// Was: only tested age 25 and 10
// Add: exact boundary
it('returns true for exactly 18', () => {
  expect(isAdult(17)).toBe(false);
  expect(isAdult(18)).toBe(true);
});
```

### Test Both Branches of Conditions

```typescript
it('grants access when admin only', () => { expect(canAccess(true, false)).toBe(true); });
it('grants access when owner only', () => { expect(canAccess(false, true)).toBe(true); });
it('denies access when neither', () => { expect(canAccess(false, false)).toBe(false); });
```

### Avoid Identity Values

```typescript
// Avoid: multiply(10, 1), add(5, 0)
// Use:   multiply(10, 3), add(5, 3)
```

### Verify Side Effects

```typescript
it('processes order', () => {
  processOrder(order);
  expect(orderRepository.save).toHaveBeenCalledWith(order);
  expect(emailService.send).toHaveBeenCalledWith(
    expect.objectContaining({ to: order.customerEmail })
  );
});
```

---

## Quick Reference: Operators Most Likely to Have Surviving Mutants

1. `>=` vs `>` — boundary not tested
2. `&&` vs `||` — only tested when both true/false
3. `+` vs `-` — only tested with 0
4. `*` vs `/` — only tested with 1
5. `some()` vs `every()` — only tested with all matching

---

## Branch Analysis Checklist

For each changed function/method:

- [ ] Arithmetic operators — would changing +, -, *, / be detected?
- [ ] Conditionals — are boundary values tested (>=, <=)?
- [ ] Boolean logic — are all branches of &&, || tested?
- [ ] Return statements — would changing return value be detected?
- [ ] Method calls — would removing or swapping methods be detected?
- [ ] String literals — would empty strings be detected?
- [ ] Array operations — would empty arrays be detected?

**Red flags (likely surviving mutants):**
- Tests only verify "no error thrown"
- Tests only check one side of a condition
- Tests use identity values (0, 1, empty string)
- Tests only verify function was called, not with what
- Tests don't verify return values
- Boundary values not tested
