---
title: "Phase 3: Measured Migration of the Authoring Skills"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Measured Migration of the Authoring Skills

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Directory Map — C6 migration]`
- `[ref: SDD/Architecture Decisions SDD-ADR-4]` — eval case first, proving signal, revert on regression
- `[ref: SDD/Acceptance Criteria PRD F7]`
- `[ref: research-internal.md (A) rule inventory and (F) proposed changes]` — exact file:line of each copy
- `[ref: research-internal.md (A)]` — the file:line list of paraphrased rule copies each task here must replace with a citation. T1.4 found no verbatim fingerprint copies (allow-list empty), so the fingerprint test cannot show these copies red; the per-consumer "cites an ID" strict xfails and the spec-compliance reviewer's file:line check do instead (deviation recorded 2026-11-05)

**Key Decisions**:
- One rule group per task, with at least 5 eval cases per group (varied tasks for the same rule), each run 3 times. Each task follows the same five beats:
  1. eval case, run on the current skill (before);
  2. proving signal;
  3. correction plus the switch to citations;
  4. run again (after);
  5. keep, or revert for that skill.
- A drop beyond noise means `eval_compare.py` reports "a better" (before better) over ≥ 5 cases, i.e. the paired CI over cases lies below 0. "insufficient cases" is not a pass: add cases. Then the correction is reverted for that skill. The catalog entry stays and records where it was reverted.
- The `MUST BE USED` text in agent-author is not touched (pinned by T1.4).
- Testing a migrated skill locally needs prompt-author copied too.

**Dependencies**:
- Phase 1 (catalog, catalog test with per-consumer strict xfails).
- Phase 2 T2.3 (eval_compare.py) and T2.4 (prompt-author exists, so the `../prompt-author/` links resolve).

---

## Tasks

Makes the three authoring skills consume the shared catalog with the corrected rules, each correction measured.

- [x] **T3.1 Description rules → citations (no behaviour change)** `[activity: skill-authoring]` `[component: C6]`

  1. Prime: Read the 8 description-rule and 5 purity-rule copies `[ref: research-internal.md (A) rows "Description = triggers only", "Front-load trigger", "Strip rationale"]` and PA-50–PA-52.
  2. Test: Red = the strict xfails for skill-author and agent-author in test_prompt_single_source.py ("cites an ID"): they fail as soon as citations exist (XPASS), so removing the markers is part of green. List the copies to replace from research-internal.md (A) before editing.
  3. Implement: Replace each copy in skill-author and agent-author with a citation of PA-51/PA-52, and PA-50 where authority language is mentioned. The `MUST BE USED` sentences stay verbatim.
  4. Validate: T1.4 passes for these entries; remove the strict-xfail markers for skill-author and agent-author in the per-consumer citation check. Run agent-author's `evals/pressure-scenarios.md` description scenarios once by hand and record the verdicts. The wording is unchanged in effect, so no eval delta is expected.
  5. Success: The description rules are stated once, in harness.md `[ref: PRD/F7 AC1; PRD/F7 AC5]`

- [x] **T3.2 Rationale rule group (PA-01, PA-02)** `[activity: skill-authoring]` `[component: C6]`

  1. Prime: Read the "strip rationale" copies `[ref: research-internal.md (A) row 1; (F)1-2]` and the discipline-skill exception at skill-author conventions:356-366.
  2. Test: Create `plugins/tcs-helper/evals/skill-author-rationale-clause/`:
     - Task: write a discipline skill with three non-obvious rules.
     - Graders: an llm grader checks that each non-obvious rule carries a one-clause reason; a regex grader requires no dates, commit SHAs or "previously".

     Run it before, prove the signal, and record the score.
  3. Implement: Apply (F)1-2 in skill-author conventions and common-failures, and in agent-author anti-patterns, output-formats and the reject checklist. Replace the copies (research-internal.md (A) row 1 file:lines) with citations of PA-01/PA-02.
  4. Validate: Run after, then eval_compare before vs after. Keep, or revert per skill. Record both scores in evals/README.md.
  5. Success: The correction is measured, then kept or reverted with the reason recorded `[ref: PRD/F7 AC2]`

- [x] **T3.2b Ceiling-skipped graders are unjudged, not failed** `[activity: backend-tooling]` `[component: C4]` `[ref: SDD/Error Handling; SDD-ADR-4]` — before T3.3

  1. Prime: prompt_eval_stats.build_report and eval_compare's reading of plugin-eval result.json; the T3.2 before/after result.json, where a grader skipped by the cost ceiling ("skipped: cost ceiling") is stored as `passed: false, scored: true`.
  2. Test (red first): a fixture result.json where one run's llm grader is skipped by the ceiling. The run counts as unjudged: excluded from that criterion's rate and from the all-pass rate. The report lists unjudged runs per side. A skip on one side only cannot produce "a better". A fixture where every run of a case is unjudged yields "insufficient cases" if fewer than 5 judged cases remain.
  3. Implement: in the plugin-eval reader, recognise the skipped-by-ceiling marker and map it to unjudged. Use the exact field and text taken from the T3.2 result.json files.
  4. Validate: full tcs-helper tests are green. Re-running `eval_compare.py compare` on the T3.2 files (offline) gives the reference case 2/2 on both sides. Record the corrected figures in the T3.2 README section.
  5. Success: a ceiling skip can no longer fake a regression `[ref: SDD-ADR-4]`

- [ ] **T3.3 Authority-language rule group (PA-03)** `[activity: skill-authoring]` `[component: C6]`

  1. Prime: Read skill-author conventions:301-318 and persuasion-principles.md `[ref: research-internal.md (F)3-4]`.
  2. Test: Create `plugins/tcs-helper/evals/skill-author-no-authority-language/`:
     - Task: write a discipline skill.
     - Graders: a regex grader requires that "YOU MUST" and "No exceptions" do not appear; an llm grader requires that the Red Flags / excuse→reality table is present.

     Run it before, prove the signal, and record the score.
  3. Implement: Merge conventions:301-307 and :311-318 into a citation of PA-03. In persuasion-principles.md, mark the Authority principle "unverified for current models" with the vendor counter-evidence. Keep the Red Flags tables.
  4. Validate: Run after, compare, keep or revert, and record. Additionally run the tcs-workflow discipline eval `xdd-tdd-pressure-invoked` once before and once after (`xdd-tdd-pressure` scores 0 in both arms, so it carries no signal), because those skills were written under the old rule.
  5. Success: The correction is measured, and discipline compliance is not regressed beyond noise `[ref: PRD/F7 AC2; PRD/Risks row 1]`

- [ ] **T3.4 Examples rule group (PA-11)** `[activity: skill-authoring]` `[component: C6]` `[parallel: true]` — T3.4–T3.6 run in parallel, but their edits to `plugins/tcs-helper/evals/README.md` are merged one at a time

  1. Prime: Read skill-author conventions:124 `[ref: research-internal.md (F)6]`.
  2. Test: Create `plugins/tcs-helper/evals/skill-author-diverse-examples/`:
     - Task: write a skill whose output format needs examples.
     - Grader: an llm grader requires 3–5 examples that differ in kind, with each shown behaviour also stated as a rule.

     Run it before, prove the signal, and record the score.
  3. Implement: Replace the rule at conventions:124 with a citation of PA-11.
  4. Validate: Run after, compare, keep or revert, and record.
  5. Success: The correction is measured `[ref: PRD/F7 AC2]`

- [ ] **T3.5 memory-claude-md-optimize scoring (PA-30, PA-31)** `[activity: skill-authoring]` `[component: C6]` `[parallel: true]`

  1. Prime: Read scoring-rubric.md:35-49 and :72-86 `[ref: research-internal.md (A) rubric rows; (F)7]` and the ETH findings `[ref: research-external.md §4]`.
  2. Test: Create `plugins/tcs-helper/evals/claude-md-optimize-no-overview-reward/`:
     - Fixture: a repo whose README already gives the architecture overview, and a CLAUDE.md that repeats it.
     - Grader: an llm grader requires that the score does not reward the overview and that the optimizer proposes removing it.

     Run it before, prove the signal, and record the score.
  3. Implement: Change the rubric to reward only what README and code lack, citing PA-31. The rationale scoring cites PA-01.
  4. Validate: Run after, compare, keep or revert, and record.
  5. Success: The rubric no longer rewards a generic overview; the memory-claude-md-optimize strict-xfail marker is removed `[ref: PRD/F7 AC3]`

- [ ] **T3.6 agent-author agentic entries (PA-20–PA-24)** `[activity: skill-authoring]` `[component: C6]` `[parallel: true]`

  1. Prime: Read the agent-author conventions and output-formats, and the Gravity table `[ref: research-external.md § Agent prompts vs one-shot prompts]`.
  2. Test: Create `plugins/tcs-helper/evals/agent-author-agentic-contract/`:
     - Task: write an agent for a multi-step job with a parsed return.
     - Grader: an llm grader requires stated behaviour when unclear, stop conditions, the goal rather than a fixed script, a refusal with an alternative, and a scope fence (PA-24).

     Run it before, prove the signal, and record the score.
  3. Implement: Add citations of PA-20–PA-24 where agent-author defines what an agent body contains. This is an addition, not a correction. The create path (agent-author SKILL.md create steps) never reads anti-patterns.md, so state the PA-01 reason-clause rule there too (T3.2 review finding); it is measured by this group's after run.
  4. Validate: Run after, compare, keep or revert, and record.
  5. Success: agent-author gains the agentic entries through citation `[ref: PRD/F7 AC4]`

- [ ] **T3.7 Docs and local-testing procedure** `[activity: technical-writing]` `[component: C6]`

  1. Prime: Read docs/about/principles.md:43 and :146, and the CLAUDE.md "Testing Skills During Development" section.
  2. Test: T1.4's PA-token check covers `docs/about/`: write the PA-50 citation in principles.md:43 first with a wrong ID and watch the dead-ID check fail, then correct it.
  3. Implement:
     - principles.md:146: remove the stale eval claim, pointing to `plugins/*/evals/`.
     - principles.md:43: mark description authority language as contested, citing PA-50 and repo ADR-4.
     - CLAUDE.md: add that testing skill-author, agent-author or memory-claude-md-optimize locally also needs prompt-author copied.
     - Update the tcs-helper README with the new skill.
  4. Validate: `pytest -q tests/test_docs_links.py tests/test_claude_md_imports.py tests/tcs-helper/test_prompt_single_source.py` passes.
  5. Success: The docs no longer contradict the catalog `[ref: SDD/Implementation Boundaries "Can Modify"]`

- [ ] **T3.8 Phase Validation** `[activity: validate]`

  - All per-consumer strict xfails are removed and pass. The spec-compliance reviewer confirms every research-internal.md (A) copy location now cites instead of restating.
  - `pytest -q -rs` and `prompt_lint.py --repo` pass.
  - evals/README.md has before/after scores, kept/reverted and cost for T3.2–T3.6.
  - Any reverted group is recorded in its catalog entry ("reverted for <skill>: <reason>") and in the spec README Decisions Log.
  - Success: every shared rule is cited, not restated `[ref: PRD/F7 AC1; PRD/Success Metrics Business Impact]`
