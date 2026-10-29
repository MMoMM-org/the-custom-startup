---
title: "Phase 3: Classifier and implement loops"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Classifier and implement loops

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2]` — classifier section and step 6
- `[ref: SDD/Implementation Examples; Model-tier rules]` — signals, rules, traced walkthroughs
- `[ref: SDD/Implementation Examples; Step 6 confirmation]` — prose, not a second tool mention
- `[ref: SDD/Architecture Decisions; ADR-4, ADR-5, ADR-6]` — consumed through `model-ladder.md`
- `[ref: SDD/Risks and Technical Debt; Technical Debt; Implementation Gotchas]`

**Key Decisions**:
- Step 6 keeps one confirmation round; the tool name appears there once (the Finalize gate). The CON-8 test stays unchanged and green.
- Both loops link `../xdd/reference/model-ladder.md` and read `model_tier` from the `xdd-meta` read they already make; neither restates the rungs. The dispatcher is untouched.

**Dependencies**:
- Phase 1 (model_tier readable) and Phase 2 (ladder, tag).

---

## Tasks

Delivers the user-visible behaviour: the classifier recommends a model tier, and both implement loops dispatch and escalate by it.

- [x] **T3.1 Model-tier section in `classifier.md`** `[activity: domain-modeling]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd/reference/classifier.md` and `tests/test_classifier_rules.py` `[ref: SDD/Implementation Examples; Model-tier rules]`.
  2. Test: Extend `tests/test_classifier_rules.py` — an independent Python copy of the four model-tier rules reproduces the five traced walkthroughs in the SDD; lockstep string tests, sliced to the "Model Tier" section by heading, check the four signals, the ordered rules, the lowering defaults for undeterminable signals, override logging with the free-text reason or "no reason given", and that it recommends and never applies.
  3. Implement: Add the "Model Tier" section (inputs, rules, edge cases, rationale examples, decision logging) to `classifier.md`; link `model-ladder.md` for the cost sentence.
  4. Validate: Tests pass; existing decomposition-rule tests unchanged and green.
  5. Success: `[ref: PRD/AC-1.1]`; `[ref: PRD/AC-1.4]`; `[ref: PRD/AC-1.5]`

- [x] **T3.2 xdd step 6 confirms both tiers in one round** `[activity: domain-modeling]`

  1. Prime: Read step 6 of `plugins/tcs-workflow/skills/xdd/SKILL.md` and the step-6 tests in `tests/test_classifier_rules.py:222-300`, including the strings that must survive verbatim `[ref: SDD/Implementation Examples; Step 6 confirmation]` `[ref: SDD/Risks and Technical Debt; Implementation Gotchas]`.
  2. Test: Add tests — step 6 extracts both tiers' signals without asking; the `**Ask** the user to choose` bullet names the headers "Decompose" and "Model"; the frontier option takes the cost sentence from `model-ladder.md`; Record writes both Status rows and a Decisions Log row per tier. `test_xdd_adds_no_question_beyond_the_tier_confirmation` stays unchanged and green.
  3. Implement: Edit step 6 (Extract, Recommend, Surface, Ask, Record) for both tiers in prose, never writing the tool name again; update the State/Interface to carry the model tier.
  4. Validate: Tests pass; skill-author audit of `xdd/SKILL.md` clean.
  5. Success: `[ref: PRD/AC-1.2]`; `[ref: PRD/AC-1.3]`; `[ref: PRD/AC-2.1]`

- [x] **T3.3 implement-incremental dispatches and escalates by the ladder** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read steps 4b (lines 166-173), 4e, 4f, 4g and the YOLO note (line 264) of `plugins/tcs-workflow/skills/implement-incremental/SKILL.md`; read `model-ladder.md` `[ref: SDD/Runtime View; Complex Logic]`. The file is over the orchestrator size budget; keep edits compact.
  2. Test: Write `tests/test_implement_incremental_ladder.py` — 4b links the ladder, reads `model_tier` and the `[model:]` tag, and keeps today's haiku/sonnet/opus rules for routine and absent; 4e escalates on complexity only and names the three non-escalating reasons; 4f and 4g count consecutive failures per task across both, escalate on the second and reset; the highest reachable rung reports BLOCKED instead of repeating; fable consent is asked before dispatch and nobody-to-ask stops at opus@max; a fable error continues a planned task on opus@max and blocks an escalated one; every escalation and substitution is logged via xdd-meta; the stale "4b (model selection confirmation)" YOLO reference is gone.
  3. Implement: Edit the skill accordingly; keep 4c (tdd-guardian) and the 4f-before-4g order untouched.
  4. Validate: Tests pass; skill-author audit of the changed sections clean; existing implement tests green.
  5. Success: `[ref: PRD/AC-3.1]` `[ref: PRD/AC-3.2]` `[ref: PRD/AC-3.3]` `[ref: PRD/AC-4.1]` `[ref: PRD/AC-4.2]` `[ref: PRD/AC-4.3]` `[ref: PRD/AC-4.5]` `[ref: PRD/AC-5.1]` … `[ref: PRD/AC-5.7]` `[ref: PRD/AC-6.1]` … `[ref: PRD/AC-6.4]`

- [x] **T3.4 implement-direct dispatches and escalates by the ladder** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read steps 3b (line 114) and 3c (line 133) of `plugins/tcs-workflow/skills/implement-direct/SKILL.md`; read `model-ladder.md`.
  2. Test: Write `tests/test_implement_direct_ladder.py` — 3b links the ladder and reads `model_tier` (it does not restate the mapping table); 3c's "stronger model" is replaced by one-rung escalation on complexity, with the cap, the consent and nobody-to-ask rules, and the fable-failure rule, all by reference to the ladder; escalations and substitutions are logged.
  3. Implement: Edit the skill accordingly. Direct has no review chain, so the review-failure trigger does not apply.
  4. Validate: Tests pass; skill-author audit clean.
  5. Success: `[ref: PRD/AC-4.4]` `[ref: PRD/AC-4.5]` `[ref: PRD/AC-5.1]` `[ref: PRD/AC-5.2]` `[ref: PRD/AC-5.3]` `[ref: PRD/AC-5.4]` `[ref: PRD/AC-5.5]` `[ref: PRD/AC-5.6]` `[ref: PRD/AC-5.7]` `[ref: PRD/AC-6.1]` … `[ref: PRD/AC-6.4]`

- [x] **T3.5 Phase Validation** `[activity: validate]`

  - Gate task. Run the full Python suite. Run `Skill(tcs-workflow:validate)` drift mode for spec 022 against the changed skills.
