---
title: "Phase 1: Foundation — reference files, ADR, label-drift self-test"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Foundation — reference files, ADR, label-drift self-test

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Cross-Cutting Concepts/Pattern Documentation]` — the 3 new reference files
- `[ref: SDD/Implementation Examples]` — label-drift self-test example
- `[ref: SDD/Architecture Decisions ADR-2, ADR-4, ADR-5]`
- `[ref: PRD/Feature 2 & 3]` — classification + dedup requirements

**Key Decisions**:
- ADR-2 (Q1-skip / Q2-filter) is documented as a standalone ADR file this phase.
- ADR-4: `extraction-heuristics.md` owns the 7 canonical Q3 **bare labels** in a marked
  block; the self-test couples them to the matrix headings.
- ADR-5: `installed-enforcement-catalog.md` is a hint layer only; live inspection is
  authoritative (implemented in Phase 2).
- CON-1: the matrix is NOT modified — reference files consume it, never fork it.

**Dependencies**: None (foundation). Phase 2 depends on all Phase 1 files existing.

---

## Tasks

This phase establishes the knowledge base the batch workflow reads (scan sources,
extraction heuristics, dedup catalog), records the ADR exception, and locks the
Q3-label↔matrix-heading coupling with an executable self-test.

- [x] **T1.1 ADR: Q1-skip & non-interactive inference exception** `[activity: documentation]`

  1. Prime: Read the interactive `Never` constraints and Step 6 lookup
     `[ref: SKILL.md rule-enforcer L47-51, L116-124]` and `[ref: SDD/ADR-2]`.
  2. Test: Manual review — ADR states the exception, scope (batch mode only), and why
     the interactive `Never: Skip the Q1 short-circuit` still holds for interactive mode.
  3. Implement: Write ADR to `docs/XDD/adr/` (auto-numbered) documenting: batch mode
     skips Q1 (recurrence presumed) and infers Q2/Q3/Q4; Q2=No becomes a filter, not a
     memory-add hand-off.
  4. Validate: ADR renders; cross-links to spec 016; supersedes nothing.
  5. Success: Exception documented with rationale + trade-offs `[ref: PRD/Risks; SDD/ADR-2]`.

- [x] **T1.2 `reference/scan-sources.md` (default source set)** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/Runtime View B1]`, `[ref: PRD/AC-1]`, and the optimizer's
     discovery model `[ref: memory-claude-md-optimize/SKILL.md discovery step]`.
  2. Test: File lists repo + project sources (`CLAUDE.md`, nested `**/CLAUDE.md`,
     `docs/ai/memory/*.md`) and the opt-in `--scope global` set (`~/.claude/…`); states
     `@`-import-follow policy and protected/structural exclusions (EC-7).
  3. Implement: Create `plugins/tcs-helper/skills/rule-enforcer/reference/scan-sources.md`.
  4. Validate: Every path referenced exists or is clearly marked optional/global.
  5. Success: Default = repo+project, global opt-in `[ref: PRD/Open Questions; SDD/CON-5]`.

- [x] **T1.3 `reference/extraction-heuristics.md` (filter + Q3 labels + Q4 defaults)** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/Runtime View B3-B4]`, `[ref: mechanism-matrix.md headings]`,
     `[ref: examples.md 5 worked cases]`, and `[ref: SDD/ADR-4]`.
  2. Test: (a) enforceable-vs-judgment filter cues present; (b) the 7 canonical Q3
     **bare labels** appear verbatim inside `<!-- Q3-LABELS-START -->…<!-- Q3-LABELS-END -->`;
     (c) Q4 defaults documented (Block/Nudge/Auto-fix per SDD); (d) high-false-positive
     tier described (EC-1) and low-confidence→needs-review (EC-8).
  3. Implement: Create the file, linking to `examples.md` rather than re-encoding the matrix.
  4. Validate: No `(Q3,Q4)→mechanism` mapping duplicated (CON-1); labels are bare
     (no `(e.g. …)` suffix).
  5. Success: Filter + cues + defaults + label block `[ref: PRD/Feature 2; SDD/ADR-2, ADR-4]`.

- [x] **T1.4 `reference/installed-enforcement-catalog.md` (hint layer)** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `[ref: plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh]`,
     `[ref: pre-edit-branch-check.sh]`, `[ref: hooks.json]`, and `[ref: SDD/ADR-5]`.
  2. Test: Catalog maps each already-enforced *concept* (no-edit-on-main, git bad-ops,
     `--no-verify`) → owning hook + covered phrasings; header states it is a hint layer
     and live inspection is authoritative. NOTE (alignment finding 4c): skill-author-on-
     creation is a **memory rule** (`feedback_skill-author-on-creation`), NOT a
     git-helpers hook — list it under a separate "memory-enforced" note, not as a hook
     dedup entry.
  3. Implement: Create the file.
  4. Validate: Entries match the actual scripts as of this spec; drift caveat present.
  5. Success: Dedup hint layer complete `[ref: PRD/Feature 3; SDD/ADR-5]`.

- [x] **T1.5 `test_batch_q3_labels.sh` (label-drift self-test)** `[activity: testing]`

  1. Prime: Read `[ref: SDD/Implementation Examples/label-drift self-test]` and
     `[ref: test_examples_md.sh]` for the existing self-test pattern.
  2. Test (RED): With a deliberately wrong label in `extraction-heuristics.md`, the
     script exits non-zero naming the missing heading; with correct labels it exits 0.
  3. Implement: Create `plugins/tcs-helper/skills/rule-enforcer/test_batch_q3_labels.sh`
     (bash 3.2 compatible) reading the Q3-LABELS block and asserting each `## Q3 = <label>`
     exists in `mechanism-matrix.md`.
  4. Validate: Runs clean against T1.3 output; fails loudly on drift.
  5. Success: Coupling enforced by test `[ref: SDD/ADR-4; SDD/Risks/Technical Debt]`.

- [x] **T1.6 Phase 1 Validation** `[activity: validate]`

  - Run `test_batch_q3_labels.sh` (green). Confirm all 3 reference files + ADR exist,
    the matrix file is unchanged (`git diff` empty for it), and no mapping was duplicated.
