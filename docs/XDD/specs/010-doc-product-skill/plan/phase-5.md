---
title: "Phase 5: Dogfood and Validation"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Dogfood and Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Success Metrics — KPIs]` — adoption + quality + self-reported targets
- `[ref: PRD/Open Questions]` — v2 deferrals to capture during dogfood
- `[ref: SDD/Quality Requirements]` — performance, usability, reliability targets

**Key Decisions**:
- v1 adoption target: ≥3 TCS / MiYo repos with `doc-product`-generated docs.
- `miyo-tomo` is mandatory (worst-state benchmark).
- The skill must dogfood itself: `tcs-helper` plugin's own user-facing docs are produced via `doc-product` once v1 is functional.
- Issues found during dogfood: classify as v1-blockers (must fix before declaring v1 done) vs v2-backlog (capture in spec README + memory).

**Dependencies**:
- Phases 1–4 complete (full skill functional).

---

## Tasks

This phase delivers v1 readiness validation by running the skill against three real targets and confirming each reaches a passing reader-test or has explicit deferrals documented. Verifiable outcome: a "v1 readiness report" comment on the spec PR listing each dogfood target's outcome.

- [ ] **T5.1 Dogfood: miyo-tomo (worst-state benchmark)** `[activity: dogfood]` `[parallel: true]`

  1. **Prime**: Read `miyo-tomo/README.md` (current 198-line state) and identify the worst pain points. Confirm `claude` CLI authenticated.
  2. **Test**: Full skill flow against miyo-tomo: `plan` produces a proposed `docs/` tree matching expectations; `extract` runs against any settings source (or returns a clear "no settings source detected" if there isn't one); `write` drafts at least the installation page; `review` runs against the result and produces a gap report.
  3. **Implement**: Run the skill end-to-end on a feature branch in miyo-tomo (don't commit yet; capture artefacts as comments on the spec PR). Record (a) outcomes of each mode, (b) any gaps in the reader-test, (c) any errors / surprises that should be classified.
  4. **Validate**: Final reader-test on the produced docs achieves PASS, OR specific gaps are documented as v2-backlog (recorded in spec README open questions). The miyo-tomo improvement is the primary v1 validation case.
  5. **Success**:
     - [ ] Skill ran end-to-end against miyo-tomo without unrecoverable error `[ref: PRD/KPI Adoption]`
     - [ ] Reader-test final outcome PASS or documented gap-acceptance `[ref: PRD/KPI Quality]`
     - [ ] All issues found are classified (v1-blocker vs v2-backlog vs not-an-issue)

- [ ] **T5.2 Dogfood: tcs-helper plugin's own user-facing docs** `[activity: dogfood]` `[parallel: true]`

  1. **Prime**: Inspect `plugins/tcs-helper/` to identify what user-facing docs already exist (likely none — author docs live elsewhere).
  2. **Test**: Run plan + extract + write + review against the TCS plugin from the user perspective. Specifically: a TCS plugin user would want to know how to install the plugin into their Claude Code, how to invoke individual skills, and how to troubleshoot when a skill doesn't trigger.
  3. **Implement**: Same as T5.1 against `plugins/tcs-helper/` (treat as a self-contained "repo" within the monorepo for the purposes of this dogfood).
  4. **Validate**: Reader-test PASS on the produced tcs-helper user docs, or gaps documented.
  5. **Success**:
     - [ ] Skill ran end-to-end against tcs-helper user docs `[ref: PRD/KPI Adoption]`
     - [ ] Reader-test final outcome PASS or documented gap-acceptance

- [ ] **T5.3 Dogfood: One Other MiYo Repo (Marcus selects)** `[activity: dogfood]` `[parallel: true]`

  1. **Prime**: Marcus selects from MiYo: hashi / kokoro / seigyo / shuu / hakobi / satori. Pick the one with the most painful current docs state (via quick eyeball: README size, presence of `docs/` tree).
  2. **Test**: Same as T5.1 against the selected repo.
  3. **Implement**: Same.
  4. **Validate**: Reader-test PASS or gaps documented.
  5. **Success**:
     - [ ] Skill ran end-to-end against the selected MiYo repo
     - [ ] Reader-test final outcome PASS or documented gap-acceptance

- [ ] **T5.4 Issue Triage and v2 Backlog Capture** `[activity: validate]`

  1. **Prime**: Aggregate findings from T5.1, T5.2, T5.3.
  2. **Test**: Each issue from dogfood has a classification: (a) v1-blocker — must fix before declaring v1 done, (b) v2-backlog — captured for next iteration, (c) false-positive — no action. Verify each v1-blocker has a fix tracked in this phase or a follow-up commit.
  3. **Implement**:
     - For each v1-blocker: open a checkbox in the appropriate earlier phase file's Deviations section, fix on a sub-branch, validate, and check off here.
     - For each v2-backlog: append to `docs/XDD/specs/010-doc-product-skill/README.md` Open Questions table with `(v2)` tag.
     - For false-positives (e.g. reader-test marks a clear doc as ambiguous): document in a section of this phase file titled "Reader-Test Calibration Notes" so future tuning has the context.
  4. **Validate**: All blockers fixed; all v2 items recorded; spec README Open Questions table updated.
  5. **Success**:
     - [ ] Zero unaddressed v1-blockers
     - [ ] All v2-backlog items recorded in spec README

- [ ] **T5.5 Self-Reported v1 Retrospective** `[activity: validate]`

  - Marcus writes a brief retrospective in `~/.claude/projects/.../memory/` (or the project memory) covering:
    - Did the skill save time vs hand-authoring docs? (per PRD KPI "Self-reported value")
    - Did reader-test catch at least one real gap?
    - What was painful?
    - What should v2 prioritise?
  - Cross-link the retrospective from spec README's decisions log.

- [ ] **T5.6 Phase 5 Validation and v1 Sign-Off** `[activity: validate]`

  - Verify all phases 1-5 closure criteria met.
  - Verify all PRD critical gates pass (per `requirements.md` validation checklist).
  - Verify all SDD critical gates pass (per `solution.md` validation checklist).
  - Verify all PLAN critical gates pass (per `plan/README.md`).
  - If everything green: update spec README phase to "Ready" and propose merging the spec branch.
  - If any blocker: document in Deviations and surface to Marcus.

---

## Reader-Test Calibration Notes

(Captures false-positive patterns observed during dogfood, for future prompt tuning.)

---

## Deviations

### Deviation 1: rename skill `doc-product` → `claude-docs` (2026-05-07)

**v1-blocker** found during initial dogfood. Marcus's feedback: the slash
command `/doc-product` was unintuitive — `/claude-docs` reads more clearly
as "documentation produced via Claude" and matches the broader naming
pattern users expect when invoking a `claude` CLI ecosystem skill.

**Fix:** rename the skill identity throughout while preserving the spec ID:
- Skill directory: `plugins/tcs-helper/skills/doc-product/` →
  `plugins/tcs-helper/skills/claude-docs/` (via `git mv` to preserve history)
- `SKILL.md` frontmatter: `name: doc-product` → `name: claude-docs`
- Active-skill announcement: `tcs-helper:doc-product` → `tcs-helper:claude-docs`
- All `/doc-product {plan|write|extract|review}` slash command references in
  the four mode files, gap-report template, lib-personas.sh, write-mode.test.sh
- Prose references "the doc-product skill" in error messages and template
  intros → "the claude-docs skill"
- **Output directory `docs/` is unchanged** — the skill still writes user-
  facing documentation to a target repo's `docs/` tree (no namespace change)
- **Spec ID `010-doc-product-skill` preserved** as a stable historical
  reference; the spec is *about* the skill formerly known as doc-product

**Validation:** all 13 test files green (369 assertions, 0 failures, 2
skipped on platforms without optional deps). Skill-author audit PASS on
the renamed `SKILL.md`.

**Spec body not retroactively rewritten.** PRD/SDD/per-phase plan files
continue to refer to "doc-product" — they describe v1 as it was specified.
This deviation note + the `tcs-helper` 3.4.1 CHANGELOG entry are the
canonical record of the rename. Future spec readers should treat
`/claude-docs` as the current invocation and `doc-product` as historical.

- [x] T5.4 v1-blocker: rename skill `doc-product` → `claude-docs`
