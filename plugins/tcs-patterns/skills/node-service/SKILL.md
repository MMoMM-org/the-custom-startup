---
name: node-service
description: "Use when building or reviewing Node.js services — enforces async/await hygiene, unhandled rejection handling, graceful shutdown, and event loop safety."
user-invocable: true
argument-hint: "[service source path to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:node-service**

Act as a Node.js service reliability engineer. Every unhandled rejection is a ticking bomb; every sync operation in a hot path is a latency cliff.

## Interface

NodeViolation {
  kind: UNHANDLED_REJECTION | SYNC_IN_HOT_PATH | MISSING_SHUTDOWN | CALLBACK_PROMISE_MIX | ERROR_SWALLOW
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  violations: NodeViolation[]
  hasGracefulShutdown: boolean
}

## Constraints

**Always:**
- Register `process.on("unhandledRejection", ...)` and `process.on("uncaughtException", ...)` at startup.
- Implement graceful shutdown: handle SIGTERM, drain connections, close DB pools.
- Use `async/await` consistently — never mix with `.then()/.catch()` in the same function.
- Use `Promise.all` / `Promise.allSettled` for concurrent async operations — never `await` in a loop.

**Never:**
- Use sync fs, crypto, or compression APIs (`readFileSync`, `pbkdf2Sync`) in request handlers.
- Swallow errors with empty catch blocks.
- Mix callbacks and promises — pick one pattern per module.
- Let the process exit on unhandled rejection without logging diagnostics.

## Workflow

### 1. Check Error Boundaries

```bash
grep -n "unhandledRejection\|uncaughtException\|process.on" "$TARGET" 2>/dev/null
```

Flag missing global handlers as HIGH.

### 2. Check Graceful Shutdown

```bash
grep -n "SIGTERM\|SIGINT\|server.close\|drain" "$TARGET" 2>/dev/null
```

Flag missing shutdown handlers as HIGH for production services.

### 3. Scan for Sync APIs

```bash
grep -rn "Sync(" --include="*.js" --include="*.ts" "$TARGET" 2>/dev/null
```

Flag sync calls in request handlers or middleware as HIGH. Sync calls at startup are acceptable.

### 4. Scan for Promise Anti-Patterns

```bash
grep -n "await.*for\|\.then\|new Promise" "$TARGET" 2>/dev/null | head -30
```

Flag `await` inside loops and `.then()/.catch()` mixed with `async/await`.

### 5. Report

Group violations by kind, severity descending. Include file:line and concrete fix.
