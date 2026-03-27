# Category Entry Formats

## All files
```
<!-- YYYY-MM-DD -->
- [learning in one clear sentence, actionable]
```

## general.md
```
<!-- 2026-03-25 -->
- File names use kebab-case (not camelCase): `user-repository.ts` not `userRepository.ts`
```

## decisions.md
```
<!-- 2026-03-25 -->
- 2026-03-25 — Chose SQLite over Postgres — Rationale: expected low concurrency; simpler ops
```

## troubleshooting.md
```
<!-- 2026-03-25 -->
## bun test crash on M1 — Status: open
NODE_OPTIONS=--max-old-space-size=4096 fixes OOM on large test suites

## bun lock conflict — Status: resolved
Run `bun install --frozen-lockfile` to reproduce; `bun install` to fix
```

## What NOT to include
- Long prose explanations — keep it to one actionable sentence
- Code snippets longer than 3 lines (link to a doc file instead)
- Things that belong in the codebase itself (put them in code comments or README)
