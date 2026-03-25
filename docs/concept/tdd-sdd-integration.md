# TDD + SDD Integration Concept

**Status:** Concept document — approved design for TCS v2
**Session:** 2026-03-24

---

## Core Insight

SDD (Solution Design Documents) and TDD (Test-Driven Development) are not competing methodologies — they operate at different abstraction layers and are naturally complementary.

- **SDD defines contracts** — interface signatures, data models, behavior contracts (preconditions, postconditions, error conditions), integration points
- **TDD verifies contracts** — each SDD contract becomes a failing test that defines the implementation target before any code is written

Neither methodology replaces the other. SDD without TDD produces designs that may never be correctly implemented. TDD without SDD produces tests that may be testing the wrong things.

---

## The Binding Layer: The PLAN

The PLAN (from `/specify-plan`) is where SDD and TDD connect. Each PLAN task is anchored to a SDD contract and structured as a TDD cycle:

```
SDD contract:
  UserRepository.findByEmail(email: string) → User | null

PLAN task:
  RED:      write test: findByEmail('exists@test.com') returns User
            write test: findByEmail('missing@test.com') returns null
            run tests — confirm they FAIL for the right reason
  GREEN:    write minimal implementation to pass
            run tests — confirm they PASS, no regressions
  REFACTOR: clean up, improve names, add edge cases, keep green
```

The SDD contract provides the *what* (interface + behavior). The TDD cycle provides the *discipline* (fail first, minimal code, then clean up).

---

## What the SDD Produces as TDD Targets

When writing an SDD, every interface definition implicitly creates TDD targets:

| SDD element | TDD target |
|---|---|
| Function signature | Input/output boundary test |
| Data model | Shape validation test |
| Behavior contract | Happy path + edge case tests |
| Error condition | Error handling test |
| Integration point | Contract/mock boundary test |

A well-written SDD makes the test list obvious. A PLAN written from a good SDD has no ambiguity about what each RED phase should test.

---

## Workflow Integration

```
/brainstorm
    → design approved (interfaces sketched)

/specify
    → PRD: what to build and why
    → SDD: interfaces, contracts, data models, error conditions
           (each contract = future TDD target)
    → PLAN: tasks structured as RED / GREEN / REFACTOR cycles
            each task references its SDD section

/implement (per phase)
    → for each task:
        1. /tdd enforces iron law: no implementation code without failing test
        2. RED:     write test anchored to SDD contract, run, confirm failure
        3. GREEN:   write minimal implementation, run, confirm pass
        4. REFACTOR: clean up, keep green
    → /verify: evidence-before-claims gate after each task

/test      → full suite + quality checks
/review    → TDD compliance check + code quality
```

---

## Iron Law (from TDD skill)

> **NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST**

If implementation code is written before a test:
1. Delete it.
2. Write the failing test.
3. Start over.

No exceptions. No "too simple to test." No "I'll test after."

### Rejected Rationalizations

| Excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests-after = "what does this do?" Tests-first = "what should this do?" |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "TDD is dogmatic" | TDD IS pragmatic. Finds bugs before commit, prevents regressions. |

---

## What Changes in `/specify-plan`

The plan-writing skill must produce TDD-structured tasks. Each implementation task should include:
- The SDD section it implements (e.g., `[ref: SDD/Section 2.3 — UserRepository]`)
- Explicit RED / GREEN / REFACTOR steps
- Expected test file path and test names

Plans that lack RED steps are incomplete.

---

## What Changes in `/implement`

The implementation orchestrator enforces TDD before dispatching tasks:
1. Invokes `tcs-workflow:tdd` sub-skill before each task
2. Confirms the test file exists and fails before allowing GREEN work
3. After GREEN, triggers REFACTOR checkpoint
4. Calls `/verify` before marking a task complete

---

## Relationship to `/test`

`/tdd` and `/test` serve different purposes:

| `/tdd` | `/test` |
|---|---|
| Per-task discipline | Suite-level verification |
| RED-GREEN-REFACTOR cycle | Run all tests, fix failures |
| Called during implement | Called after implement |
| Enforces test-first | Enforces no regressions |

Both are mandatory. `/tdd` is embedded in the implementation loop. `/test` is the exit gate.
