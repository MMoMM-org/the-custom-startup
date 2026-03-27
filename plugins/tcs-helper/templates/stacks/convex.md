## Convex Rules
- Mutations are transactional — keep them focused; no external I/O in mutations
- Queries are reactive — no side effects
- Schema in `convex/schema.ts` — update before adding new fields
- Use `v.` validators for all arguments and return types
