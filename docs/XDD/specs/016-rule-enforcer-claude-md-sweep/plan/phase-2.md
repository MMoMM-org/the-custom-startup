---
title: "Phase 2: Batch mode in SKILL.md + parity & security tests"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Batch mode in SKILL.md + parity & security tests

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy]` and `[ref: SDD/Runtime View B1-B9]`
- `[ref: SDD/Implementation Examples]` — Step 0 dispatch + Step-8 reuse
- `[ref: SDD/Architecture Decisions ADR-1, ADR-3]`
- `[ref: SDD/System-Wide Patterns/Security]`
- `[ref: PRD/Feature 1 & 4; PRD/Constraints & Assumptions]`

**Key Decisions**:
- ADR-1: Step 0 mode guard; frontmatter `argument-hint` + `Glob`/`Grep`; interactive
  path (Steps 1–8) byte-unchanged (CON-6).
- ADR-3: B9 feeds `Candidate ≅ TriageState` into the **unchanged** Step 8 → slug gates,
  templates, collision checks inherited (CON-2). Batch confirm replaces per-file confirm.
- CON-3: SKILL.md stays ≤500 lines — procedural detail already lives in Phase 1 refs.

**Dependencies**: Phase 1 complete (reference files + self-test exist).

---

## Tasks

This phase wires the batch pipeline into the skill without disturbing the interactive
flow, and proves two properties by test: batch classification matches interactive
(parity), and attacker-influenced scanned text cannot escape the slug/path gates.

- [x] **T2.1 Step 0 mode dispatch + frontmatter + interactive-untouched guard** `[activity: skill-authoring]`

  1. Prime: Read `[ref: SKILL.md rule-enforcer frontmatter + Entry Point L245-251]`,
     `[ref: SDD/Implementation Examples/Step 0 dispatch]`, `[ref: SDD/ADR-1]`.
  2. Test (RED): A rule-sentence `$ARGUMENTS` still routes to Step 1 (interactive);
     empty / `--scan` / `--from-file <p>` routes to batch. Existing interactive
     self-tests (`test_examples_md.sh`, `test_skill_scaffold.sh`) still pass unchanged.
  3. Implement: Add `### 0. Mode dispatch` to SKILL.md; update frontmatter
     `argument-hint: "[rule description] | --scan | --from-file <path>"` and add
     `Glob`, `Grep` to `allowed-tools`.
  4. Validate: Interactive self-tests green; `wc -l SKILL.md` ≤ 500.
  5. Success: Dual-mode dispatch works; interactive path unchanged `[ref: PRD/CON-6; SDD/ADR-1]`.

- [x] **T2.2 Batch pipeline skeleton B1–B9 in SKILL.md** `[activity: skill-authoring]`

  1. Prime: Read `[ref: SDD/Runtime View B1-B9]`, `[ref: SDD/Complex Logic]`,
     `[ref: SKILL.md Step 8 hand-off L142-234]`, and the Phase 1 reference files.
  2. Test (RED): Skeleton lazy-loads `scan-sources.md` + `extraction-heuristics.md`;
     B5 resolves via `mechanism-matrix.md` (SSOT, no duplicated table); B9 dispatches
     through the existing Step 8 block; judgment-only rules go to a guidance list, not
     memory-add (ADR-2).
  3. Implement: Add the thin batch workflow (B1–B9) to SKILL.md, referencing the Phase 1
     files for detail; render the consolidated table + "Left as guidance" sub-table.
  4. Validate: `wc -l SKILL.md` ≤ 500; no matrix fork; Step 8 block untouched.
  5. Success: B1–B9 present and delegate correctly `[ref: PRD/Feature 1&4; SDD/ADR-3; CON-1,CON-2,CON-3]`.

- [x] **T2.3 Parity test: batch inference == interactive mechanism** `[activity: testing]`

  1. Prime: Read `[ref: examples.md 5 worked cases]`, `[ref: SDD/Acceptance Criteria/Classification]`.
  2. Test (RED): For each of the 5 `examples.md` cases, batch inference (Q2/Q3/Q4 →
     matrix) yields the same mechanism the interactive flow documents; a wrong mapping fails.
  3. Implement: Create `plugins/tcs-helper/skills/rule-enforcer/test_batch_parity.sh`
     (bash 3.2) driving the documented inference against expected mechanisms.
  4. Validate: All 5 cases pass.
  5. Success: Matrix parity proven `[ref: PRD/SM-4; SDD/Acceptance Criteria]`.

- [x] **T2.4 Security: malicious-slug fixture + `--from-file` path confinement** `[activity: testing]`

  1. Prime: Read `[ref: SKILL.md slug-validation gates L181-184, L212-215]`,
     `[ref: SDD/System-Wide Patterns/Security]`.
  2. Test (RED): A fixture memory file containing `rule: ../../etc/evil` is caught by the
     slug gate (row flagged, nothing written); `--from-file ../outside` and absolute
     paths outside the allowed set are rejected before any read; personal `~/.claude`
     content is paraphrased, never pasted into a generated artifact.
  3. Implement: Create `plugins/tcs-helper/skills/rule-enforcer/test_batch_security.sh`
     + fixtures under a test fixtures dir; add the `--from-file` confinement check to the
     Step 0 / B1 skeleton.
  4. Validate: All security assertions pass; no fixture path escapes.
  5. Success: Slug gate + path confinement + privacy hold `[ref: SDD/CON-5; SDD/Security]`.

- [x] **T2.5 Phase 2 Validation** `[activity: validate]`

  - Run all rule-enforcer self-tests (`test_examples_md.sh`, `test_batch_q3_labels.sh`,
    `test_batch_parity.sh`, `test_batch_security.sh`). `shellcheck` clean on new `.sh`.
    Confirm SKILL.md ≤ 500 lines and interactive path regressions are zero.
