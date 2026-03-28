---
name: go-idiomatic
description: "Use when writing or reviewing Go code — enforces idiomatic error handling, small interface design, standard package layout, goroutine safety, and proper use of defer."
user-invocable: true
argument-hint: "[package or file path to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:go-idiomatic**

Act as an experienced Go developer. Idiomatic Go is simple, explicit, and boring by design. If it feels clever, it is probably wrong.

## Interface

GoViolation {
  kind: IGNORED_ERROR | PANIC_NORMAL_FLOW | FAT_INTERFACE | GOROUTINE_LEAK | CONTEXT_MISSING | INIT_ABUSE
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  violations: GoViolation[]
  hasContextPropagation: boolean
}

## Constraints

**Always:**
- Return and handle errors explicitly — every returned `error` must be checked.
- Accept interfaces, return structs — define interfaces at the call site.
- Propagate `context.Context` as the first argument to any function that does I/O.
- Use `defer` for resource cleanup immediately after acquisition.
- Name packages for what they provide, not what they contain (`package user`, not `package users`).

**Never:**
- Use `panic` for recoverable errors or normal control flow.
- Ignore errors with `_` without a comment explaining why.
- Define large interfaces — prefer single-method interfaces (io.Reader, fmt.Stringer).
- Start goroutines without a clear ownership and shutdown path.
- Use `init()` for logic beyond package-level variable initialization.

## Reference Materials

- `reference/go-patterns.md` — error handling, interface design, goroutine patterns, project layout, tooling

## Workflow

### 1. Scan for Ignored Errors

```bash
grep -n "_\s*=\s*" "$TARGET" 2>/dev/null | grep -v "//"
```

Flag each as IGNORED_ERROR. Check if there is a comment justifying the ignore.

### 2. Scan for Panic

```bash
grep -n "\bpanic(" "$TARGET" 2>/dev/null
```

Flag `panic` outside of `main()` or test helpers as HIGH.

### 3. Check Context

```bash
grep -n "func " "$TARGET" 2>/dev/null | grep -v "context\.Context"
```

Flag functions doing I/O without a `context.Context` parameter as MEDIUM.

### 4. Check Goroutines

```bash
grep -n "go func\|go [a-z]" "$TARGET" 2>/dev/null
```

For each goroutine: is there a `WaitGroup`, channel, or `context` controlling its lifetime?

### 5. Report

Group violations by kind. Include file:line and idiomatic Go replacement.

Read `reference/go-patterns.md` Anti-Patterns table for concrete fixes.
