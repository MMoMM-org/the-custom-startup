---
name: mutation-testing
description: "Use when strengthening test suites — runs mutation analysis to find tests that pass without actually verifying behavior, and guides writing assertions that kill surviving mutants."
user-invocable: true
argument-hint: "[test directory or module to analyse]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:mutation-testing**

Act as a mutation testing specialist. Every surviving mutant is a test gap. Treat a mutation score below 85% as a failing test suite.

## Interface

Mutant {
  id: string
  file: string
  operator: string        // e.g. ArithmeticOperator, BooleanLiteral
  original: string
  mutated: string
  status: KILLED | SURVIVED | TIMEOUT | NO_COVERAGE
}

State {
  target = $ARGUMENTS
  tool: string            // stryker | mutmut | cargo-mutants | go-mutesting
  mutants: Mutant[]
  score: number           // percentage killed
  survivors: Mutant[]
}

## Constraints

**Always:**
- Target mutation score ≥ 85% before marking a module's tests complete.
- For each surviving mutant: read the mutant, understand what it changes, add an assertion that would catch it.
- Run mutation testing on the most critical domain logic first.
- Document timeout mutants — they may indicate missing test boundaries.

**Never:**
- Accept surviving mutants in domain core logic without explicit justification.
- Write tests purely to increase mutation score — test real behavior, not mutants.
- Run mutation testing on generated or framework code — scope to your business logic.

## Workflow

### 1. Detect Tool

```bash
# Check installed mutation tools
command -v stryker npx 2>/dev/null && echo stryker
command -v mutmut 2>/dev/null && echo mutmut
cargo mutants --version 2>/dev/null && echo cargo-mutants
```

Select tool based on project language.

### 2. Run Analysis

```bash
# Stryker (JS/TS)
npx stryker run 2>&1 | tail -30

# mutmut (Python)
mutmut run && mutmut results 2>&1 | head -50
```

Collect surviving mutants list.

### 3. Triage Survivors

For each surviving mutant:
1. Show the mutation (original → mutated)
2. Explain what behavior the test suite missed
3. Propose the specific assertion needed to kill it

### 4. Report

Present score, survivor list with kill instructions, and priority order (domain core first).
