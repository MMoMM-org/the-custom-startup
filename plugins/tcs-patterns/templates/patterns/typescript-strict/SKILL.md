---
name: typescript-strict
description: "Use when working on TypeScript projects — triggered by requests to audit type safety, strict mode configuration, implicit any, null checks, or discriminated union patterns."
user-invocable: true
argument-hint: "[path, file, or tsconfig.json to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:typescript-strict**

Act as a TypeScript type safety expert. Treat every `any`, non-null assertion, and missing type annotation as a defect.

## Interface

TypeViolation {
  kind: IMPLICIT_ANY | EXPLICIT_ANY | NON_NULL_ASSERTION | MISSING_ANNOTATION | UNSAFE_CAST
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  tsconfig: object | null
  violations: TypeViolation[]
}

## Constraints

**Always:**
- Enable `strict: true` in tsconfig — this covers noImplicitAny, strictNullChecks, and more.
- Type all function parameters and return values explicitly.
- Use discriminated unions (`type Result = { ok: true; value: T } | { ok: false; error: E }`) for variants.
- Use `unknown` instead of `any` when the type is genuinely unknown; narrow before use.

**Never:**
- Use `any` — replace with `unknown`, a specific type, or a generic.
- Use non-null assertion (`!`) without a comment explaining why null is impossible here.
- Cast with `as` without evidence — prefer type guards (`is` predicates) or narrowing.
- Suppress TypeScript errors with `@ts-ignore` or `@ts-expect-error` without explanation.

## Reference Materials

- `reference/strict-config.md` — strict config

## Workflow

### 1. Check tsconfig

Read `tsconfig.json`. Flag missing or disabled strict options:
- `strict` (preferred over individual flags)
- `noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess`

### 2. Scan for Violations

```bash
grep -rn "\bany\b\|as any\|@ts-ignore\|@ts-expect-error\|\!" --include="*.ts" "$TARGET" 2>/dev/null | head -50
```

Classify each hit as TypeViolation. Skip test files if `--skip-tests` is passed.

### 3. Propose Fixes

For each violation, propose the minimal type-safe replacement. For `any` in function signatures, offer generic `<T>` alternatives.

### 4. Report

Group by violation kind. Include file:line, current code, and replacement.
