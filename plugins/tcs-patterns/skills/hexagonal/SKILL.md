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
  kind: PATTERN | HOUSE_STYLE   // PATTERN blocks; HOUSE_STYLE is advice
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
- Separate what the *pattern* requires from what this skill *recommends* when reporting. A house-style deviation is not a pattern violation, and reporting it as one costs the audit credibility.
- Define ports as interfaces in the domain/application layer.
- Place all framework-specific code (HTTP, DB, messaging) in adapters.
- Ensure driven adapters are configurable from outside — the application never constructs them internally. Parameter injection is this skill's default; a configurator function or a lookup broker also satisfies the pattern.
- Require a test interactor at every port — a test driver on the driving side, a fake on the driven side. **A port that nothing tests is a line on a diagram, not a boundary.**

**Never:**
- Import framework types (Express, TypeORM, Axios) into domain or application layers.
- Let the domain core instantiate adapters — always inject through ports.
- Flag a missing port for an internal abstraction. A port represents a conversation with something *outside* the hexagon. If nothing external will ever sit behind the interface, it is not a port and demanding one is port proliferation.
- Treat nested hexagons as compliance. The boundary belongs at the technology or team-authority edge; inner hexagons duplicate the test wall, and the duplicate decays until the boundary stops being real.

## What the Pattern Requires

The pattern has exactly two zones — **inside** and **outside** — and one rule: nothing outside reaches past a port. It says nothing about how either zone is structured internally.

It is also symmetric. The left/right asymmetry is an implementation detail about *who knows whom*: driving adapters know the application and call the driving ports it exposes; the application knows its driven adapters only as injected values satisfying interfaces it defines. Driving ports are its **provided interface** (API), driven ports its **required interface** (SPI).

| Term | Meaning |
|---|---|
| **Actor** | Anything with behavior outside the boundary — a person, a database, another program, a test |
| **Driving** (primary) | Initiates a conversation with the application |
| **Driven** (secondary) | The application calls it |
| **Interactor** | The actor or its adapter — whichever touches the port directly. Not every actor needs an adapter; tests and program-to-program callers can meet a port's interface as-is |
| **Configurator** | Whatever knows all the players and introduces them — the composition root. In tests, the test case is both configurator and driving actor |

The domain/use-case layering, the naming conventions, and the file organization in the deep-dive references are **this skill's house style**, not the pattern. Cockburn names every port for the intention of the conversation (`ForPlacingOrders`, `ForStoringTickets`); we keep intention names for driving ports and role nouns (`OrderRepository`) for driven ports. A codebase using `For...` on the driven side is following the source convention — leave it alone.

## Reference Materials

- `reference/hexagonal-layers.md` — layer definitions, dependency rules, example directory structures
- `reference/worked-example.md` — one feature traced through every layer, with tests and file map
- `reference/testing-hex-arch.md` — fakes, `createTestDb`, the swappability test
- `reference/cqrs-lite.md` — when reads must JOIN across aggregates
- `reference/cross-cutting-concerns.md` — placing auth, logging, transactions, error formatting
- `reference/incremental-adoption.md` — introducing hex arch into an existing codebase

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

For each adapter, confirm a corresponding port interface exists. A driven adapter reaching into the application without one is a HIGH violation.

Judge in the other direction too — **too many ports is also a defect**:

| Observation | Verdict |
|---|---|
| Adapter talks to an external system, no port | HIGH — missing boundary |
| Port wraps an internal domain abstraction nothing external will implement | MEDIUM — port proliferation, remove it |
| Several ports for one aggregate or one external capability | MEDIUM — collapse them |
| A hexagon boundary inside another hexagon | MEDIUM — the inner test wall will decay; use modules |

The test is not "does every adapter have a port" but "does every port mark a real boundary" — one per aggregate for persistence, one per external capability otherwise.

### 4. Verify Ports Are Real

For each port, find its test interactor: a test driver exercising a driving port, a fake implementing a driven port. A port with neither is unenforced — nothing stops business logic drifting into an adapter or technology detail into the domain, and the next refactor will not notice.

Flag untested ports as HIGH. This check catches leaks the import-direction scan in step 2 cannot see.

### 5. Report

Group violations by layer. Include file:line and a concrete fix for each.

Group by `kind` first: **pattern violations** block, **house-style deviations** are advice. A codebase can be a correct hexagonal architecture and still not match this skill's naming or folder conventions — reporting the second as the first costs the audit its credibility.
