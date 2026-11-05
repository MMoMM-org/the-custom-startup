# Results: Opus- vs Sonnet-authored prompts

Run 2026-11-04/05. 30 authorings (3 per arm x 5 tasks, 2 arms) + 5 status-quo prompts, 385 target runs, $7.97 total. No target, grader or judge errors; every authoring returned a tagged prompt. Design: PLAN.md. Raw runs: `~/.cache/spec023-runs/` (not committed).

**Judge criteria are not yet validated** (PLAN.md § Judge: ~20 user labels per criterion pending). Rows marked *judge* are provisional.

## Answer

**No measurable difference between Opus and Sonnet as prompt authors.** On four of five tasks both arms pass at the same rate; on T5 they fail in different ways and the 95% CI of the difference spans -27 to +47 points. The large effect in this experiment is *any explicit authoring vs the prompts currently in the repo*: where the status-quo prompt lacks a contract the orchestrator depends on (T2, T3) it fails every run, and both models write that contract unprompted.

## All-criteria pass rate

| Task | Opus (O, n) | Sonnet (S, n) | Status quo (Q, n) | O-S, 95% CI (bootstrap, clustered by prompt) |
|---|---|---|---|---|
| T1 research system prompt, haiku | 90% (60) | 92% (60) | 90% (20) | -2% [-13, +10] |
| T2 implementer brief, sonnet agentic | 100% (30) | 100% (30) | **0%** (10) | 0 |
| T3 review brief, sonnet agentic | 97% (30) | 100% (30) | **0%** (10) | -3% [-13, 0] |
| T4 CLAUDE.md, haiku agentic | 100% (15) | 100% (15) | 60% (5) | 0 |
| T5 PRD interview port, qwen3.5 local | 43% (30) | 33% (30) | 50% (10) | +10% [-27, +47] |

Per prompt (all-pass / cases): T1 O1 17/20, O2 18, O3 19, S1 19, S2 18, S3 18, Q 18. T5 O1 6/10, O2 2, O3 5, S1 1, S2 4, S3 5, Q 5. Variance *between authorings of the same model* (T5: 2/10 to 6/10 for Opus) is as large as any between-model gap.

## Where each prompt fails

| Task | Criterion | O | S | Q | Reading |
|---|---|---|---|---|---|
| T2 | status_parseable / status_correct | 100 / 100 | 100 / 100 | 0 / 0 | Q never asks for DONE/NEEDS_CONTEXT/...; both authors add it (#250) |
| T3 | findings_structured | 97 | 100 | 0 | Q asks no location/severity/confidence (#251) |
| T3 | teammate_not_flagged | 100 | 100 | 90 | Q has no scope fence (#251, active.md) |
| T4 | used_documented_test_cmd | 100 | 100 | 60 | Q = no CLAUDE.md; agent follows the README's wrong command |
| T5 | one_question_per_turn | 53 | 83 | 60 | Opus-authored prompts let the model bundle questions |
| T5 | final doc delivered (all_sections) | 77 | 53 | 90 | Sonnet-authored prompts keep the section-approval gate after the user says "write it now" |
| T5 | markers_resolved | 73 | 40 | 80 | follows from no final doc |
| T1 | *judge* no_unsupported_fact | 90 | 92 | 95 | provisional |
| T5 | *judge* no_implementation_detail | 97 | 93 | 100 | provisional |

T5 sensitivity — counting a follow-up that elaborates the same question ("For example, ...?", "Is it ...?") as one question: all-pass O 16/30, S 10/30, Q 5/10. Conclusion unchanged.

## Observations for the PRD

1. **Contracts, not polish, decide agentic prompts.** T2/T3 Q fail on exactly the interface the caller parses. Both models write the contract when the request names the caller's behaviour. A catalog rule "state the output contract your caller branches on" covers the observed failures; length and style do not.
2. **Authored prompts are 3-10x longer than status quo** (T1 6.4-8.6 KB vs 0.6; T2 5.2-7.1 vs 0.2; T5 4.3-7.0 vs 2.8) with no gain where Q already had the contract (T1, T5). Length is cost without measured benefit there.
3. **Porting to a small local model (T5) is where authoring is weakest**: no authored prompt beats the status quo. Both failure modes are rules the target follows *too literally* — an approval gate with no user override (S), an example-question style the model copies (O). Candidate catalog entries: every gate needs an exit ("if the user asks for the result, deliver it"); for small models, show the exact turn shape.
4. **Ceilings.** T4 (all authored 100%) and T1 (all arms ~90%) do not discriminate between authors; T4's fixture is too easy, T1's haiku target follows any reasonable research prompt.
5. **The status quo is not uniformly bad**: Q ties or beats authored prompts on T1 and T5. The repo's weak prompts are the short subagent briefs, not the long chat prompts.

## Instrument changes

Pilot fixes (5) are in PLAN.md § Pilot outcome. Two changes after the freeze, both regraded from stored outputs and both flipping only False→True:

| Date | Task | Change | Regrade diff |
|---|---|---|---|
| 2026-11-05 | T1 | `counterarguments_nonempty` also accepts "strongest case", "counter-case", "weaker than", "goes wrong", "complications", "failure modes", "limitations", "where the obvious ..." labels — the request asks for "the strongest arguments against the obvious conclusion" and authors label that part this way. Bare "wrong" excluded ("Why SHA-256 is wrong here" is the main argument). | 10 runs (O 8, S 2); each inspected by hand before the change; O3/t1-17 "Where I'm least sure" stays FAIL |
| 2026-11-05 | T5 | `count_questions` ignores `?` inside `[NEEDS ...]` markers — they are part of a draft, not a question to the user | 3 runs (O 1, S 2) |

The T1 fix removed an apparent Opus deficit (O 77% → 90%): before it, the headline would have read "Sonnet writes better research prompts". It was a grader artefact.

## Limits

- n = 3 authorings per arm; between-authoring variance is large (T5), so a small real difference would not be detected.
- Target family = author family for T1-T4.
- Judge criteria unvalidated until the labels are in; judge passed 5/5 hand-built controls (PLAN.md § Judge).
- T5 uses a simulated user (haiku) with an 8-turn limit; the "write it now" request arrives at turn 7 for every arm.
