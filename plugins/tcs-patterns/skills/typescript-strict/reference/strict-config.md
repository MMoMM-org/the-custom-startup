# TypeScript Strict Mode — Config Reference

Adapted from citypaul/.dotfiles

## tsconfig.json — Full Strict Settings

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noPropertyAccessFromIndexSignature": true,
    "forceConsistentCasingInFileNames": true,
    "allowUnusedLabels": false
  }
}
```

## What Each Setting Does

**Core strict flags:**
- `strict: true` — Enables all strict type checking options
- `noImplicitAny` — Error on expressions/declarations with implied `any` type
- `strictNullChecks` — `null` and `undefined` have their own types
- `noUnusedLocals` — Error on unused local variables
- `noUnusedParameters` — Error on unused function parameters
- `noImplicitReturns` — Error when not all code paths return a value
- `noFallthroughCasesInSwitch` — Error on fallthrough switch cases

**Additional safety flags (CRITICAL):**
- `noUncheckedIndexedAccess` — Array/object access returns `T | undefined` (prevents runtime errors)
- `exactOptionalPropertyTypes` — Distinguishes `property?: T` from `property: T | undefined`
- `noPropertyAccessFromIndexSignature` — Requires bracket notation for index signature properties
- `forceConsistentCasingInFileNames` — Prevents cross-OS case sensitivity issues
- `allowUnusedLabels: false` — Error on unused labels

**Additional rules:**
- No `@ts-ignore` without explicit comments explaining why
- These rules apply to test code as well as production code

---

## Type vs Interface

### `type` — for data structures

```typescript
export type User = {
  readonly id: string;
  readonly email: string;
  readonly name: string;
  readonly roles: ReadonlyArray<string>;
};
```

Use `type` for: data shapes, unions, intersections, mapped types. Use `readonly` to signal immutability.

### `interface` — for behavior contracts

```typescript
export interface UserRepository {
  findById(id: string): Promise<User | undefined>;
  save(user: User): Promise<void>;
}
```

Use `interface` when: something must be implemented (`implements`), for dependency injection contracts.

---

## Branded Types

```typescript
type UserId = string & { readonly brand: unique symbol };
type PaymentAmount = number & { readonly brand: unique symbol };

const processPayment = (userId: UserId, amount: PaymentAmount) => { ... };

// ❌ Can't pass raw string/number — type error
processPayment('user-123', 100);

// ✅ Must use branded type
const userId = 'user-123' as UserId;
const amount = 100 as PaymentAmount;
processPayment(userId, amount);
```

---

## Schema-First at Trust Boundaries

**Schemas ARE required when:**
- Data crosses trust boundary (external → internal)
- Type has validation rules (format, constraints)
- Shared data contract between systems

```typescript
const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
});
type User = z.infer<typeof UserSchema>;

const user = UserSchema.parse(apiResponse); // validate at boundary
```

**Schemas NOT required for:**
- Pure internal types (utilities, state)
- Result/Option types
- TypeScript utility types (`Partial<T>`, `Pick<T>`)
- Behavior contracts (interfaces)

---

## noUnusedParameters Catches Design Issues

When a function parameter is unused, it often signals the parameter belongs in a different layer. Strict mode catches these design issues at compile time rather than in code review.

---

## Summary Checklist

- [ ] No `any` types — use `unknown` where type is truly unknown
- [ ] No type assertions without justification
- [ ] `type` for data structures with `readonly`
- [ ] `interface` for behavior contracts
- [ ] Schemas defined once, imported everywhere (not duplicated)
- [ ] Strict mode enabled with all checks passing
- [ ] Branded types for IDs and safety-critical primitives
- [ ] Schemas at trust boundaries (API input, form data, external responses)
