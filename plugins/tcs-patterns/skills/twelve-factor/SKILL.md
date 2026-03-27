---
name: twelve-factor
description: "Use when auditing or designing service configuration, deployment, or runtime behaviour — triggered by requests to review environment config, stateless processes, log handling, backing services, or twelve-factor compliance."
user-invocable: true
argument-hint: "[repo path or service to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:twelve-factor**

Act as a twelve-factor app practitioner. Treat config-in-code, stateful processes, and dev/prod parity gaps as first-class defects. Coordinate with tcs-team:the-devops:build-platform for implementation.

## Interface

FactorViolation {
  factor: number         // 1–12
  name: string           // e.g. "Config", "Processes"
  severity: CRITICAL | HIGH | MEDIUM | LOW
  finding: string
  fix: string
}

State {
  target = $ARGUMENTS
  violations: FactorViolation[]
  score: number          // factors passing / 12
}

## Constraints

**Always:**
- Store all config in environment variables — never in code or committed config files.
- Treat backing services (DB, cache, queue) as attached resources, swappable via config.
- Strictly separate build, release, and run stages — never modify code at runtime.
- Export logs as event streams to stdout — never route or store logs inside the app.
- Make processes stateless and share-nothing — persist state in backing services only.

**Never:**
- Hardcode credentials, URLs, or environment-specific values in source code.
- Rely on the local filesystem for state that must survive a process restart.
- Use sticky sessions that couple a user to a specific process instance.
- Bundle config with the release artifact — one artifact, many environments.

## Reference Materials

- `reference/twelve-factor-checklist.md` — twelve factor checklist

## Workflow

### 1. Check Config (Factor III)

```bash
grep -rn "localhost\|127\.0\.0\.1\|password\s*=\|secret\s*=" --include="*.ts" --include="*.js" --include="*.py" --include="*.go" . 2>/dev/null | grep -v test | grep -v ".env.example"
```

Flag any hardcoded values as CRITICAL violations.

### 2. Check Processes (Factor VI)

Look for filesystem writes in request handlers, in-memory session state, or local file caches. Flag as HIGH violations.

### 3. Check Logs (Factor XI)

Verify logs go to stdout/stderr. Flag any log file configuration or log rotation code inside the app as MEDIUM.

### 4. Audit All Twelve Factors

Review each of the 12 factors:
1. Codebase — one codebase, many deploys?
2. Dependencies — explicit and isolated?
3. Config — in environment?
4. Backing services — attached resources?
5. Build/release/run — strictly separated?
6. Processes — stateless?
7. Port binding — self-contained?
8. Concurrency — scale via process model?
9. Disposability — fast startup, graceful shutdown?
10. Dev/prod parity — keep environments close?
11. Logs — event stream?
12. Admin processes — one-off tasks as processes?

Read `reference/twelve-factor-checklist.md` for per-factor audit questions.

For implementation of findings: dispatch `tcs-team:the-devops:build-platform`.

### 5. Report

Score: N/12 factors passing. List violations grouped by factor, severity descending.
