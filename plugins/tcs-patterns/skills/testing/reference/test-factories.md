# The Test Factory Pattern

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

---

## Factory Composition

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

---

## Anti-Patterns

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
