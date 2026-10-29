---
title: "Phase 2: Model ladder and plan tag"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Model ladder and plan tag

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-4, ADR-5, ADR-6]`
- `[ref: SDD/Runtime View; Complex Logic]` — starting-rung table
- `[ref: SDD/Implementation Examples; Escalation]` — escalation pseudocode, including the counter reset, the cap, fable failure and "nobody can be asked"
- `[ref: SDD/Implementation Examples; Step 6 confirmation]` — the cost sentence text
- `[ref: SDD/Cross-Cutting Concepts; System-Wide Patterns]` — Decisions Log row formats
- `[ref: SDD/Runtime View; Error Handling]`

**Key Decisions**:
- The ladder file (`xdd/reference/model-ladder.md`) is the single source; the classifier and both loops link it, never restate it. It owns the cost sentence.
- Aliases only (`haiku`, `sonnet`, `opus`, `fable`); opus@max = `opus` + `effort: max`.

**Dependencies**:
- Phase 1 (T1.1's spike answers shape the substitution rule's wording).

---

## Tasks

Establishes the one definition of "stronger model" that every consumer reads, and the per-task annotation that selects a tier.

- [x] **T2.1 `xdd/reference/model-ladder.md`** `[activity: domain-modeling]`

  1. Prime: Read the starting-rung table, escalation pseudocode, error table and log row formats `[ref: SDD/Runtime View; Complex Logic]` `[ref: SDD/Implementation Examples; Escalation]`; read T1.1's findings.
  2. Test: Write `tests/test_model_ladder.py` —
     - the five rungs in order; only the four aliases and no full model ID; opus@max defined as `opus` with `effort: max` and the 2.1.292 minimum; "effort unsupported" falls back to `opus` and is logged;
     - starting rungs per ADR-4 for both decomposition tiers, including absent+Direct's first escalation to opus and `hard → opus`;
     - exactly two escalation triggers (complexity BLOCKED; two review FAILs in a row at one rung), the count reset on escalation, and the three non-escalating BLOCKED reasons; one rung at a time;
     - the cap: at the highest reachable rung the trigger reports BLOCKED;
     - consent before every fable dispatch not covered by a confirmed frontier spec tier; a `frontier` tag in a non-frontier spec with nobody to ask runs at `hard`;
     - "nobody can be asked" defined as YOLO=true or no answer / an error from the question; then BLOCKED at opus@max;
     - fable failure or dismissed consent prompt: planned task → opus@max and continue; escalated task → BLOCKED; fable off for the run;
     - the cost sentence exactly once; the four Decisions Log row formats.
  3. Implement: Write the reference file to satisfy the tests, in the style of `xdd/reference/classifier.md`.
  4. Validate: `pytest -q tests/test_model_ladder.py` passes; skill-author reference conventions respected.
  5. Success:
     - [x] Ladder and starting rungs defined `[ref: PRD/AC-4.1]` `[ref: PRD/AC-4.2]` `[ref: PRD/AC-4.3]` `[ref: PRD/AC-4.4]` `[ref: PRD/AC-4.5]`
     - [x] Escalation, cap and consent rules defined `[ref: PRD/AC-5.1]` … `[ref: PRD/AC-5.7]` `[ref: PRD/AC-3.3]`
     - [x] Substitution rules defined `[ref: PRD/AC-6.1]` … `[ref: PRD/AC-6.4]`

- [x] **T2.2 `[model: tier]` plan annotation** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd-plan/reference/task-structure.md` (Metadata table, lines 81-86), the Task interface in `xdd-plan/SKILL.md` (lines 16-25) and the Metadata Reference in `xdd-plan/template.md` (lines 78-83) `[ref: SDD/Building Block View; Directory Map]`.
  2. Test: Write `tests/test_plan_model_tag.py` — the metadata table has a `[model: routine|hard|frontier]` row stating it overrides the spec's model tier; the xdd-plan Task interface has `model?`; the plan manifest template's Metadata Reference lists it.
  3. Implement: Add the row, the interface field and the manifest line.
  4. Validate: Tests pass; skill-author audit of `xdd-plan/SKILL.md` clean.
  5. Success: `[ref: PRD/AC-3.1]`; `[ref: PRD/AC-3.2]`

- [x] **T2.3 Phase Validation** `[activity: validate]`

  - Gate task. Run the full Python suite. Read `model-ladder.md` against ADR-3 to ADR-6 once more; confirm no other file restates the rungs.
