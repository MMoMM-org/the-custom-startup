---
title: "Phase 4: Write-Time Nudge, Install Check and End-to-End Validation"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Write-Time Nudge, Install Check and End-to-End Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions SDD-ADR-8]`
- `[ref: SDD/Implementation Gotchas]` — installed-layout verification
- `[ref: SDD/Acceptance Criteria]` — the full list used in T4.4
- `[ref: PRD/Success Metrics]`

**Key Decisions**:
- CLAUDE.md gets no reminder (SDD-ADR-8). The SKILL.md and agent reminders stay unchanged.
- The install check runs against a scratch `CLAUDE_CONFIG_DIR`, never the user's real plugin cache.

**Dependencies**:
- Phases 1–3 complete.

---

## Tasks

Closes the loop: users are nudged to the skill, the installed layout is proven, and the whole flow runs end to end on real prompts.

- [x] **T4.1 Write-time nudge** `[activity: backend-tooling]` `[component: C7]`

  1. Prime: Read `plugins/tcs-helper/scripts/authoring_reminder.py`, `tests/tcs-helper/test_authoring_reminder.py` and SDD-ADR-8.
  2. Test: Extend test_authoring_reminder.py:
     - AGENTS.md, GEMINI.md, `x.prompt.md` and `prompts/a.md` each give exactly one reminder naming prompt-author;
     - CLAUDE.md gives none;
     - the SKILL.md and agent reminders are unchanged;
     - malformed stdin gives exit 0 (fail open).
  3. Implement: Add the PROMPT_FILE pattern and its reminder text.
  4. Validate: The tests pass. The hook never blocks.
  5. Success: The nudge fires on the four patterns without blocking `[ref: PRD/F9 AC1, AC2]`

- [x] **T4.2 Installed-layout verification** `[activity: validate]` `[parallel: true]`

  1. Prime: Read the SDD Deployment View and the gotcha "Verify the installed layout once before release".
  2. Test: Expected result: a consumer skill in an installed copy resolves `../prompt-author/reference/catalog/core.md`.
  3. Implement:
     - Build the installed layout in scratch: try `claude plugin` install from the local marketplace path into a scratch `CLAUDE_CONFIG_DIR`; if that needs a login, copy `plugins/tcs-helper/` to `<scratch>/plugins/cache/the-custom-startup/tcs-helper/<ver>/`, mirroring the cache.
     - Resolve every `../prompt-author/` link of every consumer skill on disk inside that copy (a script, not a model).
     - Optional model check: without `--disable-slash-commands` (it disables skills) and with the plugin enabled explicitly, ask for PA-01 via skill-author's link.
     - Remove the scratch dir afterwards.
  4. Validate: Every link resolves on disk. Record the commands and the result in the spec README Decisions Log.
  5. Success: The cross-skill links survive install `[ref: PRD/Constraints "must still work under local testing and after marketplace install"]`

- [x] **T4.3 End-to-end run on real prompts** `[activity: validate]`

  1. Prime: Read PRD journeys J1–J4.
  2. Test: The expected outcomes are the PRD acceptance criteria for F2, F3, F4 and F6, as listed in the traceability table below.
  3. Implement: With the installed skill, run three journeys:
     - **J2 + J4:** audit `docs/templates/setup-perplexity-space.md` (corpus #2), accept fixes, then build the kit and run before/after on `claude:haiku`.
     - **J3 + J4:** port `docs/templates/prd-prompt.md` to `ollama:qwen3.5:35b-a3b`, then before/after on Ollama. This uses the T5 setup, so compare against experiment/results.md.
     - **J1:** write a brief for a fixture orchestrator that parses a status, then run a T2-style contract kit of ≥ 10 cases on it (contract-coverage KPI ≥ 95%).

     Validate the judge on one criterion with ~20 labels from the user (T2.2 flow). Ask for consent before every run.
  4. Validate: The reports exist, each with verdict, judge validation state and cost. The templates themselves are not committed changed unless the user approves (Technical Debt: docs/templates are out of scope).
  5. Success: Every journey completes, with its labelled report or "not evaluated on target" kit `[ref: PRD/User Journey Maps J1-J4; PRD/F4 AC5]`

  - Results (2026-11-07; outputs in the session scratchpad, nothing published, docs/templates unchanged):
    - J1: brief for a fixture orchestrator, 12-case contract kit x 2 runs on claude:haiku, contract coverage 100% (KPI >= 95%).
    - J2: audit of setup-perplexity-space.md, fixes applied to a copy; 7 cases x 3 runs on claude:haiku: no measurable difference (all-pass 100% vs 95%, paired -0.048, CI [-0.143, +0.000]); runner recommends the smaller version a. Judge for recommendation_tradeoff validated on 20 user labels: 16 of 18 decided agree (89%), but it passed all 20, including both items the user labelled FAIL (leniency evidence 0/2); labels were given on excerpts, the judge saw full text.
    - J3: port of prd-prompt.md to ollama:qwen3.5:35b-a3b, 15 cases x 1 run: no measurable difference (all-pass 73% vs 93%, paired +0.200, CI [+0.000, +0.400], sign 3/0/12); runner recommends the smaller port. one_question 40% -> 100% is the main gain. The experiment's T5 had Q 50%, O 43%, S 33% all-pass; this kit uses scripted user turns and simpler graders, so the levels are not comparable, only the direction. Judge criterion no_implementation_detail stays provisional.
    - T4.3a was added on the way: the judge parse accepted no same-line verdict, which booked 40% of qwen2.5 replies as judge errors.

- [x] **T4.3a Judge verdict as the last word of the last line** `[activity: backend-tooling]` `[component: C4]` `[ref: SDD/Implementation Gotchas (judge parse, l.~538)]` — blocks T4.3 J2/J3

  1. Prime: prompt_eval.py `parse_verdict`, its tests, and SDD line ~538. Evidence: T4.3 J2 c1, where 4 of 10 qwen2.5 judge replies ended "... reason. PASS" and were booked as judge errors.
  2. Test (red first): `... reason. PASS` and `... reason. FAIL` on the last non-empty line parse as PASS/FAIL. Still errors: `**PASS**`, `pass`, a verdict-first line (`PASS because ...`), and a last line containing both PASS and FAIL. The existing last-line-only cases stay as they are.
  3. Implement the parser change and amend the SDD rule in the same commit.
  4. Validate: the prompt_eval tests are green. Re-parse the T4.3 J2 c1 grade.json replies offline: 0 of 10 are judge errors.
  5. Success: the default Ollama judge's replies parse without weakening the ambiguity checks `[ref: PRD/F6 AC3]`

- [x] **T4.4 Final validation and release readiness** `[activity: validate]`

  - Run `pytest -q -rs`, `prompt_lint.py --repo` and the full `plugins/tcs-helper/evals` suite (`--no-publish`, a ceiling above the expected cost). Tests and lint pass; no eval case falls below its Phase 3 level apart from noise (amended 2026-11-08: several measured cases never reached 3/3 in Phase 3).
  - Run the skill-author audit on prompt-author once more.
  - Update docs/ai/memory (tools.md: lint and runner gotchas; decisions.md: the catalog as single source) via /memory-add. The commands themselves stay in the skill and evals/README.md: memory-add routes recipes out of memory.
  - Spec README: the Status table; finalize via xdd-meta after merge. Do not merge without the user's explicit OK.
  - Check the traceability table below; every row has implementing evidence on the branch (final validation).

## PRD → task traceability

| PRD criterion | Task(s) |
|---|---|
| F1 entry fields; minimum entries; corrected rules; PA-50 contested | T1.1 |
| F1 restated rule fails a test; read on demand, never imported | T1.4, T3.8 |
| F2 intake and hand-off (AC1, AC6) | T2.4, T2.5 (handoff) |
| F2 consumer contract, agentic, gate exit, delimiting (AC2–AC5) | T2.4, T2.5 (contract-first, port-gate-exit), T4.3 J1 |
| F3 findings, set/pair, stale facts, data-not-instructions (AC1–AC5) | T2.4, T2.5 (audit-injection), T4.3 J2 |
| F3 known defects #250–#253 (AC6) | T2.6 |
| F4 profiles, idioms, small-local, unverified labels, delivery label | T1.2, T2.4, T4.3 J3 |
| F5 all criteria | T1.3 |
| F6 kit, report, judge rules, labels, consent, safety, no-difference | T2.1, T2.2, T2.4 (eval-loop.md), T4.3 |
| F7 citations, measured corrections, overview, agentic, MUST BE USED unchanged | T3.1–T3.8, T1.4 (pin) |
| F8 sizes and PA per added section; smaller on no difference | T2.4, T2.1 |
| F9 nudge | T4.1 |
| Success metric: contract coverage ≥ 95% | T4.3 J1 |
| Constraint: works after install and under local testing | T4.2, T3.7 |
| Success metric: audit recall ≥ 90% | T2.6 |
| Success metric: lint ≤ 1 false alarm | T1.3 |
| Success metric: zero duplicated rules | T3.8 |

## Phase 4 results

- T4.1 write-time nudge for prompt files; T4.2 cross-skill links survive a real install; T4.3a judge parse accepts a same-line verdict.
- T4.3 end-to-end: J1 contract coverage 100%; J2 and J3 no measurable difference, smaller version recommended; judge validated 16/18 with leniency evidence 0/2.
- T4.4: pytest 2333 passed, 2 skipped; prompt_lint --repo only the 2 known-open errors; skill-author audit of prompt-author PASS (4 minor wording findings, fixed in 496fb662; the agentic.md Sources grade reasons were restored afterwards, because T1.2 puts each grade's reason there).
- Full eval suite, 51 cases x 3 runs with the plugin ($84.91 notional): 42/51 cases pass, 91% of runs. Misses at or above their Phase 3 level: audit-contract-diff 1/3, examples-test-name 2/3, restate-dependency-bump 2/3, restate-translation-keys 0/3, restate-incident-notes 1/3, authority-secrets 2/3 (one Opus safeguard error). Slightly below: audit-contract-review 2/3 (3/3), rationale-history-brief 2/3 (3/3), rationale-discipline 1/3 (3/3).
- Open: rationale-discipline `no-history` fires on a sample commit SHA inside the written skill's example output table, confirmed in a re-run with --keep-temp, a grader false positive; restate-translation-keys and restate-incident-notes stay low as recorded in T3.10.
