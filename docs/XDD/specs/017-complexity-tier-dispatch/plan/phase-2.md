---
title: "Phase 2: Classification in xdd"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Classification in xdd

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; Example: The classification rules]` — the five signals, the ordered rules, and the traced walkthrough over four real specs
- `[ref: SDD/Complex Logic]` — the seven-step classify-and-route algorithm
- `[ref: SDD/Architecture Decisions; ADR-7]` — why the classifier is a reference file of `xdd`, not its own skill
- `[ref: SDD/Constraints; CON-8]` — zero extra conversation turns
- `[ref: PRD/Detailed Feature Specifications]` — business rules 1–7 and edge cases 1–7

**Key Decisions**:
- **ADR-7** — `xdd/reference/classifier.md`. One caller, so no extraction; progressive disclosure, so not inlined in `SKILL.md`.
- **ADR-1** — classification happens at step 6, *after* both documents exist. It never runs on the raw request.
- **Recommendation, never application** — the tier is not set until the user confirms (PRD business rule 2).

**Dependencies**:
- Phase 1 complete — this phase records the tier through `xdd-meta`, which must be able to carry it.
- Independent of Phase 3; the two touch disjoint files and may run concurrently.

---

## Tasks

Gives `xdd` the ability to recommend a tier from the documents it has already produced, and to record what was chosen and why.

- [ ] **T2.1 Classification rules, executable and traced** `[activity: domain-modeling]`

  1. Prime: Read the rules table and traced walkthrough `[ref: SDD/Implementation Examples; Example: The classification rules]`, and PRD business rules 1–7 plus edge cases 1–3 `[ref: PRD/Detailed Feature Specifications]`.
  2. Test: Write `tests/test_classifier_rules.py` encoding the ordered rules as a pure function over the five signals, and assert the SDD's traced table reproduces exactly — spec 015 → Direct, spec 014 → Direct, spec 012 → Incremental, spec 017 → Incremental. Then the edge cases: an empty stub → Direct; a `doc` change across four components → Incremental (breadth beats change type); an unparseable `component_count` → treated as 0 and still classifies. Add a determinism test: the same signals classify identically across repeated calls.
  3. Implement: Write `plugins/tcs-workflow/skills/xdd/reference/classifier.md` — signals table (source and how to compute each), ordered rules first-match-wins, the reserved Factory branch marked explicitly as not implemented `[ref: SDD/ADR-3]`, the rationale output format, override handling, and decision-logging guidance.
  4. Validate: `.venv/bin/python -m pytest tests/test_classifier_rules.py -q` passes. Cross-read the reference file against the test — if they disagree, the *rules* are wrong, not the traced expectations `[ref: plan/README.md; Deviation Protocol]`.
  5. Success:
     - [ ] The same documents always produce the same recommendation `[ref: PRD/AC Feature 2.3]`
     - [ ] The four traced specs classify as the SDD documents `[ref: SDD/Implementation Examples]`
     - [ ] Breadth vetoes Direct regardless of change type `[ref: PRD/Edge case Scenario 2]`
     - [ ] An unparseable signal degrades to its conservative value rather than blocking `[ref: PRD/AC Edge Case 2]`
     - [ ] The reserved Factory branch is present and marked unimplemented, so adding a tier later changes no contract `[ref: PRD/AC Feature 1.3]`

- [ ] **T2.2 `xdd` step 6 classifies, confirms, records, and routes** `[activity: docs]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd/SKILL.md` step 6 as it stands (it invokes `xdd-plan` unconditionally), and the seven-step algorithm that replaces it `[ref: SDD/Complex Logic]`.
  2. Test: Structural assertions over the rewritten `SKILL.md` — step 6 reads `reference/classifier.md`; it presents the five signals before asking; the confirmation offers both tiers with the recommendation highlighted; the Direct branch invokes no decomposition skill; the Incremental branch invokes `xdd-plan` exactly as today; `reference/classifier.md` appears in Reference Materials. Assert no `AskUserQuestion` was added beyond the single tier confirmation `[ref: SDD/Constraints; CON-8]`.
  3. Implement: Rewrite step 6 per the algorithm. Preserve steps 1–5 and 7 byte for byte — the PRD and SDD phases are explicitly untouched `[ref: SDD/Implementation Boundaries]`.
  4. Validate: Run the `tcs-helper:skill-author` audit on `xdd`; SKILL.md stays under the size limits and keeps PICS structure `[ref: SDD/Constraints; CON-7]`.
  5. Success:
     - [ ] Exactly one recommended tier is produced once both documents exist `[ref: PRD/AC Feature 2.1]`
     - [ ] The signals that produced it are displayed `[ref: PRD/AC Feature 2.2]`
     - [ ] Both tiers are offered, recommendation highlighted, never pre-applied `[ref: PRD/AC Feature 2.4]`
     - [ ] Classification costs no user input beyond the confirmation `[ref: PRD/AC Feature 2.6]`
     - [ ] A Direct run writes no decomposition artifact `[ref: PRD/AC Feature 1.1]`
     - [ ] An Incremental run produces `plan/README.md` and phase files `[ref: PRD/AC Feature 1.2]`
     - [ ] Requirements and solution are written at both tiers `[ref: PRD/AC Feature 1.4]`

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/python -m pytest tests/ -q` — all green.
  - Walk the SDD's primary sequence diagram by hand against the rewritten step 6: scaffold → PRD → SDD → classify → confirm → record → route. Confirm every arrow exists in the skill text `[ref: SDD/Runtime View]`.
  - Verify override handling: choosing the non-recommended tier records both the recommendation and the override `[ref: PRD/AC Feature 2.5]`, and a downgrade leaves prior artifacts in place flagged stale, never deleted `[ref: PRD/Won't Have; PRD/Edge case Scenario 5]`.
  - Verify against PRD Feature 1 and Feature 2 acceptance criteria.
