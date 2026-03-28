---
name: hexagonal
description: "Use when auditing or designing a layered architecture — triggered by requests to review ports and adapters, dependency direction, domain isolation from frameworks, or hexagonal architecture compliance."
user-invocable: true
argument-hint: "[path or scope to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:hexagonal**

Act as a hexagonal architecture (ports and adapters) specialist. Enforce strict dependency direction: adapters depend on ports; the domain core depends on nothing external.

## Interface

DependencyViolation {
  from: string       // class or module with the dependency
  to: string         // what it depends on
  direction: INWARD | OUTWARD
  severity: CRITICAL | HIGH | MEDIUM
  fix: string
}

State {
  target = $ARGUMENTS
  layers: { domain: string[], ports: string[], adapters: string[] }
  violations: DependencyViolation[]
}

## Constraints

**Always:**
- Define ports as interfaces in the domain/application layer.
- Place all framework-specific code (HTTP, DB, messaging) in adapters.
- Inject adapters into the application core via constructor or DI container.
- Test the application core with test doubles implementing the port interfaces.

**Never:**
- Import framework types (Express, TypeORM, Axios) into domain or application layers.
- Let the domain core instantiate adapters — always inject through ports.
- Skip port interfaces for "simple" adapters — every adapter needs a port.

## Reference Materials

- `reference/hexagonal-layers.md` — hexagonal layers

## Workflow

### 1. Map Layer Boundaries

Identify directories corresponding to domain, application, ports, and adapters layers. If not explicit, infer from import patterns.

### 2. Check Dependency Direction

For each import in domain and application layers: if the imported module is in adapters or a third-party framework, flag as CRITICAL violation.

Run:
```bash
# Find framework imports in domain layer
grep -r "import.*express\|import.*typeorm\|import.*axios" src/domain/ 2>/dev/null
```

### 3. Verify Port Completeness

For each adapter: confirm a corresponding port interface exists. Flag adapters without ports as HIGH violation.

### 4. Report

Group violations by layer. Include file:line and concrete fix for each.

Read `reference/hexagonal-layers.md` for layer definitions and example directory structures.
