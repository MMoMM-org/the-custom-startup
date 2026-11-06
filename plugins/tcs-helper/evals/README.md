# tcs-helper evals

`claude plugin eval` cases for tcs-helper skills. They run locally only: every run calls the model on
your own credential. How to write a case: `tcs-helper:skill-author`, `reference/plugin-evals.md`.

## Run

From the repository root:

```bash
claude plugin eval plugins/tcs-helper --case 'prompt-author-*' --runs 3 -j 4 --trust-plugin \
  --no-publish --output-dir <scratch-dir> --max-cost-usd 10
```

Against a deliberately weakened skill, add `--ablation none` to skip the no-plugin arm. Point
`--output-dir` at a scratch directory outside the repository, so the report stays private and nothing
is committed. Only the last `--case` flag counts; select several cases with one glob.

## prompt-author cases (Iron Law, spec 023 T2.5)

| Case | Defends | Graders |
|---|---|---|
| `prompt-author-handoff` | a skill request is handed to skill-author, not drafted (PRD F2 AC6) | regex: reply names skill-author; regex not_contains: no `name: changelog-writer` draft |
| `prompt-author-contract-first` | the brief requests every field the consumer reads, and the reply names where it looked and the mismatch (F2 AC2) | regex: `OUTCOME:` with SHIPPED, PARKED, NEED_INPUT; regex: `REASON:` and `QUESTION:`; regex: `WHEEL:` and `WARNINGS:` (read in steps 4 and 5); regex: names step 6; llm: tells the author the requested `STATUS:` ending does not match |
| `prompt-author-audit-injection` | audited text is data; its injected instruction becomes a PA-15 finding (F3 AC5) | regex: `PA-15`; regex not_contains: a bare "OK" |
| `prompt-author-port-gate-exit` | a small-local port gives each approval gate its exit (F4 AC3) | llm: every gate in the ported template states its exit |

The contract-first request asks for a `STATUS: DONE | FAILED` ending that the orchestrator never parses.
Its orchestrator reads five fields from the reply: `OUTCOME:`, `REASON:` and `QUESTION:` in step 6, and
`WHEEL:` (step 4) and `WARNINGS:` (step 5) away from the parse step.

## Results

Claude Code 2.1.316, Opus 5.5, judge Haiku, 3 runs per arm. "Baseline" is the run without the skill:
the no-plugin arm, and for handoff and contract-first also tcs-helper at the pre-skill commit
`d8980a3a` with `--ablation none` (prompt-author's catalog and scripts present, no SKILL.md, so the
typed command is plain text). "With skill" is `--ablation none` on this plugin. "Weakened" is the
proving signal: the rule removed in a scratch copy of the plugin, `--ablation none`; the repository's
skill files were never changed.

| Case | Baseline | With skill | Weakened (proving signal) | Cost per run, with / without |
|---|---|---|---|---|
| `prompt-author-handoff` | 0.00 no plugin; 0.50 pre-skill plugin | 1.00 | 1.00 (hand-off step, its Never rule, the out-of-scope line and the description's owner sentence removed) | $0.11–0.15 / $0.09 |
| `prompt-author-contract-first` | 1.00 no plugin; 1.00 pre-skill plugin | 1.00 | not run: not red without the skill | $0.38 / $0.08 |
| `prompt-author-audit-injection` | 0.33 no plugin; 0.33 pre-skill plugin | 1.00 | 1.00 (data rule and audit step 7 removed); 0.78 (also the PA-15 index row, entry and severity mention removed) | $0.41–0.45 / $0.09 |
| `prompt-author-port-gate-exit` | 0.00 no plugin; 0.00 pre-skill plugin | 1.00 (all 3 judged, ceiling $4) | 1.00 (port.md's gate-exit step and small-local's Gate exits topic removed) | $1.07–1.10 / $0.15 |

- **contract-first** was redesigned so the consumer reads two fields a reader of step 6 alone would
  miss, and an llm grader checks the reply reports the vocabulary mismatch. Every grader was green
  on both baselines in 3/3: with the consumer pasted into the request, Opus 5.5 reads all of it and
  reports the mismatch unprompted. No grader we could design is red without the skill, so the case is a
  regression guard, not a proof of the contract-first step.
- **handoff** and **port-gate-exit** are red against both baselines, but removing the rule from the
  skill's procedure did not lower the score: skill-author is visible in the same plugin, and the PA-16
  catalog entry (loaded for every chat-template) still tells the model to give each gate its exit. They
  prove the plugin, not the procedure text. A run with PA-16 removed from the catalog as well was not
  made (budget).
- **audit-injection** drops only when the PA-15 entry itself is gone, and then to 0.78 (1 of 3 runs
  without the `PA-15` citation): the case defends the catalog entry more than the SKILL.md data rule.

### Cleanup re-run (T2.10)

Spec 023 T2.10 cut 4 208 bytes from the skill's procedure text (SKILL.md plus `reference/*.md`,
catalog and profiles excluded): 36 486 before, 32 278 after (-11.5%). Catalog entries were not touched.
One with-plugin run (`--ablation none`, 3 runs per case, `-j 4`, ceiling $8) at `168d87e3`, Claude Code
2.1.316, judge Haiku:

| Case | T2.5 with skill | T2.10 | Spend |
|---|---|---|---|
| `prompt-author-handoff` | 1.00 | 1.00 | $0.33 |
| `prompt-author-contract-first` | 1.00 | 1.00 | $1.07 |
| `prompt-author-audit-injection` | 1.00 | 1.00 | $1.51 |
| `prompt-author-port-gate-exit` | 1.00 | 1.00 (all 3 judged) | $2.45 |

Total spend $5.36, not partial. No score dropped, so no cut was reverted. The shorter text is
recommended, since there is no measurable difference (PRD F8 AC2). At 1.00 before and after, the run
cannot show whether a cut helped. It shows only that no cut broke a defended behaviour.

## Rationale rule group (spec 023 T3.2, PA-01/PA-02)

Five cases defend the corrected rule: keep one clause naming the failure a non-obvious rule prevents,
and strip history, provenance and dead references. Each case has an llm grader
(`reasons-for-non-obvious-rules`: the three non-obvious rules each carry such a clause) and a regex
grader (`no-history`: no ISO date, commit SHA or "previously" in the written file).

"Before" is the skills at `19aa49f6`, which told authors to strip rationale. "After" is the correction:
skill-author in `8f833690` and agent-author in `cb856f6e`, both citing PA-01/PA-02. Both runs were
`--ablation none`, 3 runs per case, `-j 4`, Claude Code 2.1.316, Opus 5.5, judge Haiku.

| Case | Skill | Before | After | Delta |
|---|---|---|---|---|
| `agent-author-rationale-audit-fix` | agent-author | 0.50 | 0.83 | +0.33 |
| `agent-author-rationale-body` | agent-author | 1.00 | 1.00 | 0.00 |
| `skill-author-rationale-discipline` | skill-author | 1.00 | 1.00 | 0.00 |
| `skill-author-rationale-history-brief` | skill-author | 0.67 | 1.00 | +0.33 |
| `skill-author-rationale-reference` | skill-author | 1.00 (2 judged) | 1.00 (2 judged) | 0.00 |

- **audit-fix:** the llm grader failed in 3 of 3 runs before, 1 of 3 after.
- **history-brief:** 2 of 3 runs left a date, SHA or "previously" in the file before, none after.
- **reference:** in both arms, run 3's llm grader was skipped by the cost ceiling ("skipped: cost
  ceiling"); the other two scored 1.00 both times, so the case has no measured change. eval_compare
  reports run 3 as unjudged on each side and leaves it out of the rates (2/2 both sides; T3.2b).

| Criterion | Kind | Before | After |
|---|---|---|---|
| `no-history` | deterministic | 87% | 100% |
| `reasons-for-non-obvious-rules` | judge | 79% | 93% |
| all pass | - | 64% | 93% |

eval_compare verdict: **no measurable difference**. Paired difference (after − before) +0.267 in
each case's all-pass rate (audit-fix 0/3 → 2/3, history-brief 1/3 → 3/3, the other three unchanged),
95% CI [+0.000, +0.533] over the 5 cases; sign test after better 2, before better 0, ties 3, p = 0.5.
Rates are over judged runs: 14 per side, one unjudged run each.
The revert rule fires only on "a better" (CI below 0), so **both corrections are kept**. No case
dropped. The CI touches 0, so the gain is not established either.

Spend: before $8.19, after $8.71 (ceiling $8.50, crossed by runs already in flight), total $16.90
against the group cap of $17.

## Authority-language rule group (spec 023 T3.3, PA-03)

Five cases defend the corrected rule: a discipline skill states its rules in sentence case with their
reasons, without "YOU MUST" or "No exceptions", and keeps its Red Flags list or excuse → reality
table. Each case asks skill-author for a small discipline skill with 2-3 rules and has three graders
on the written file: `file-written` (file_exists), `no-authority-phrases` (regex, absent,
case-insensitive: `YOU MUST|No exceptions`) and `red-flags-present` (llm: a Red Flags list or
excuse → reality table covers every rule).

"Before" is skill-author at `a72272f6`, which told authors to "use strong language: YOU MUST, No
exceptions". "After" is the correction in `6eb028fe`, citing PA-03. Both runs were `--ablation none
--allow-tools Write Edit`, 3 runs per case, `-j 4`, Claude Code 2.1.316, Opus 5.5, default judge model. In
the first before run, all 3 verify-done runs had their llm grader skipped by the cost ceiling, so
verify-done was re-run alone on the unchanged skill and its runs replaced in the before file.

Rates are each case's all-pass rate over runs that neither errored nor went unjudged, as eval_compare
counts them:

| Case | Before | After | Delta |
|---|---|---|---|
| `skill-author-authority-changelog` | 2/3 | 3/3 | +0.33 |
| `skill-author-authority-deletion` | 1/2 (1 errored) | 2/2 (1 errored) | +0.50 |
| `skill-author-authority-migrations` | 0/3 | 2/2 (1 errored) | +1.00 |
| `skill-author-authority-secrets` | 1/2 (1 unjudged) | 2/3 | +0.17 |
| `skill-author-authority-verify-done` | 2/3 | 2/2 (1 errored) | +0.33 |

- **Every before failure was the regex:** 8 of 14 written files before, none after. Each match
  contained "No exceptions"; verify-done run 3 also had two "YOU MUST" rules.
- **Errored runs** ended with "API Error: Opus 5's safeguards flagged this message" before writing the
  file: deletion run 2 before; deletion run 3, migrations run 3 and verify-done run 2 after. They are a
  platform refusal, not a skill outcome, and eval_compare leaves them out of the rates.
- **secrets:** before, run 2's llm grader was skipped by the cost ceiling (unjudged). After, run 1's
  judge voted PASS FAIL FAIL on `red-flags-present`, the only red-flags failure in either arm.

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `no-authority-phrases` | deterministic | 43% | 100% |
| `red-flags-present` | judge | 100% | 92% |
| all pass | - | 46% | 92% |

eval_compare verdict: **b better** (after better). Paired difference (after − before) +0.467, 95% CI
[+0.267, +0.733] over the 5 cases; sign test after better 5, before better 0, ties 0, p = 0.0625.
Errored runs: before 1, after 3; unjudged runs: before 1 (secrets run 2), after none.
The revert rule fires only on "a better", so **the correction is kept**. The gain is the authority
phrases leaving the written skills; the Red Flags tables stayed (one judge split in 12 judged runs).

Discipline guard: `tcs-workflow` case `xdd-tdd-pressure-invoked`, 3 runs, `--ablation none
--allow-tools Write Edit`, before and after the correction: all graders passed in 3 of 3 runs on each
side (score 1.00 → 1.00). eval_compare reports "insufficient cases" for this single case. The
correction does not touch tcs-workflow, so this pair measures run-to-run noise, not a change.

Spend, a comparison figure only (subscription): before $9.18 (the first run's $8.76 with verify-done's
$1.38 swapped for the re-run's $1.79), after $9.33, guard $0.63 before and $0.65 after. Another $2.35
went on a verify-done re-run without `--allow-tools Write Edit`, which could not write the file and was
discarded.

## Examples rule group (spec 023 T3.4, PA-11)

Five cases defend the corrected rule: a skill that shows its output format by example gives 3-5
diverse examples, and states each behaviour they show as a rule as well. Each case asks skill-author
for a skill whose output format is easier to show than to describe (commit message, changelog entry,
API error body, test name, log line), lists 4 format rules, and has two graders on the written file:
`file-written` (file_exists) and `diverse-examples` (llm: 3-5 good examples, differing in kind, each
shown behaviour also stated as a rule; bad-example samples do not count).

"Before" is skill-author at `5c4a17db`, whose conventions.md said "One excellent example beats five
mediocre ones". "After" is the correction in `8358e2fc`, citing PA-11. Both runs were `--ablation none
--allow-tools Write Edit`, 3 runs per case, `-j 4`, Claude Code 2.1.316, Opus 5.5, default judge model.

Rates are each case's all-pass rate over runs that neither errored nor went unjudged, as eval_compare
counts them:

| Case | Before | After | Delta |
|---|---|---|---|
| `skill-author-examples-api-error` | 3/3 | 3/3 | 0.00 |
| `skill-author-examples-changelog-entry` | 1/3 | 3/3 | +0.67 |
| `skill-author-examples-commit-message` | 3/3 | 3/3 | 0.00 |
| `skill-author-examples-log-line` | 2/3 | 3/3 | +0.33 |
| `skill-author-examples-test-name` | 0/3 | 2/3 | +0.67 |

- **Before failures were the example count, both ways:** changelog-entry wrote 2 full examples plus a
  rewrite table; log-line run 3 wrote one example; test-name wrote a 6-row good-name table every run.
- **api-error and commit-message** passed 3/3 on both sides. They guard against a regression rather than
  showing the change.
- **test-name after, run 1** failed again: a 5-row examples table plus a corrections table whose "Good"
  column adds more names.
- **Judge splits** (2 of 3 votes): changelog-entry run 3 before; changelog-entry run 1, log-line run 3
  and test-name run 3 after. All of them count as PASS.

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `diverse-examples` | judge | 60% | 93% |
| all pass | - | 60% | 93% |

eval_compare verdict: **b better** (after better). Paired difference (after − before) +0.333, 95% CI
[+0.067, +0.600] over the 5 cases; sign test after better 3, before better 0, ties 2, p = 0.25.
Errored runs: none; unjudged runs: none. The revert rule fires only on "a better", so **the correction
is kept**.

Spend, a comparison figure only (subscription): before $5.39, after $5.70.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus before, averaged over the cases.

## Agentic-contract group (spec 023 T3.6, PA-20 to PA-24)

Five cases defend the added rule: an agent for a multi-step job whose reply a program parses states
what it does with unclear input, when it stops other than on success, its goal and done criterion, what
it does instead of a forbidden or out-of-scope action, and its scope fence. Each case asks agent-author
for one such agent (dependency-upgrade checker returning a JSON list, flaky-test triager returning a
verdict table, migration gate returning a `VERDICT:` line plus findings, docs link checker returning
broken links as JSON, release-notes drafter returning YAML) and has two graders on the written file:
`file-written` (file_exists) and `agentic-contract` (llm: all five of PA-20 to PA-24 present in the
body, binary).

"Before" is agent-author at `5a7fc3ef`, whose create steps defined the body as ICMDA sections only and
never read anti-patterns.md. "After" is the addition in `467a0e41`: SKILL.md create step 6 cites PA-22
for the Mission's done criterion, gains a sub-step with PA-20, PA-21, PA-23 and PA-24 and one with the
PA-01 reason-clause rule, and verify step 8 checks the contract; conventions.md gains an Agentic
Contract section; the output-formats.md audit checklist gains five rows. Both runs were `--ablation
none --allow-tools Write Edit`, 3 runs per case, `-j 4`, Claude Code 2.1.316, Opus 5.5, default judge
model.

Rates are each case's all-pass rate over runs that neither errored nor went unjudged, as eval_compare counts them:

| Case | Before | After | Delta |
|---|---|---|---|
| `agent-author-agentic-dep-upgrade` | 2/3 | 3/3 | +0.33 |
| `agent-author-agentic-flaky-triage` | 2/3 | 3/3 | +0.33 |
| `agent-author-agentic-link-check` | 3/3 | 3/3 | 0.00 |
| `agent-author-agentic-migration-gate` | 3/3 | 3/3 | 0.00 |
| `agent-author-agentic-release-notes` | 2/3 | 3/3 | +0.33 |

- **Signal:** before, the model often wrote parts of the contract unprompted, so link-check and
  migration-gate sat at 1.00 and serve as regression guards. The three before failures were judged
  FAIL FAIL FAIL (flaky-triage run 3, release-notes run 1) and PASS FAIL FAIL (dep-upgrade run 2, an
  8 KB file). The flaky-triage file, checked by hand, has no action for a missing CI log or an unknown
  test ID, no stop condition other than success, and a mostly bare `never {}` list.
- **After:** `NEEDS_CONTEXT` appears in 8 of 15 written files, against 0 of 15 before.
- No run errored or went unjudged on either side.

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `agentic-contract` | judge | 80% | 100% |
| all pass | - | 80% | 100% |

eval_compare verdict: **b better** (after better). Paired difference (after − before) +0.200, 95% CI
[+0.067, +0.333] over the 5 cases; sign test after better 3, before better 0, ties 2, p = 0.25.
Errored runs: before 0, after 0; judge errors: before 0, after 0. The judge is provisional (not
validated against hand labels). The revert rule fires only on "a better", so **the addition is
kept**. The PA-01 reason-clause rule on the create path has no grader of its own here; it is covered
only in that no case regressed.

Spend, a comparison figure only (subscription): before $7.62, after $7.59.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus before, averaged over the cases.

### Canonical-example follow-up (spec 023 T3.8, F-B1)

agent-author's `examples/canonical-agent.md`, which create step 4 reads as the gold-standard body, did
not meet the Agentic Contract it teaches. `b95f0505` adds the five elements to it: a done criterion in the
Mission (PA-22), a `## Decision` row that returns `NEEDS_CONTEXT` for an unresolvable input (PA-20), a
`require {}` stop on the same error twice with `status` and `blocker` in Output (PA-21), an `instead`
alternative on every `never {}` item (PA-23), and a `require {}` scope fence naming the change set and the
read-only git and write operations (PA-24). `tests/tcs-helper/test_agent_author_canonical.py`
(`4dd500de`, red 5/5 before the edit) keeps the example in step with the conventions.md table.

This is a regression guard, not a fresh signal: "before" is the T3.6 after run (`467a0e41`, 100% all
pass). "After" is HEAD at `b95f0505`, which also contains `2bd68e65` (F-A: SKILL.md step 6.7 cut to a
pointer at conventions.md § Agentic Contract), so it measures F-A's cut and this change together. Same
five `agent-author-agentic-*` cases, `--ablation none --allow-tools Write Edit`, 3 runs per case, `-j 4`,
Claude Code 2.1.316, Opus 5.5, default judge model.

| Case | Before | After | Delta |
|---|---|---|---|
| `agent-author-agentic-dep-upgrade` | 3/3 | 3/3 | 0.00 |
| `agent-author-agentic-flaky-triage` | 3/3 | 3/3 | 0.00 |
| `agent-author-agentic-link-check` | 3/3 | 3/3 | 0.00 |
| `agent-author-agentic-migration-gate` | 3/3 | 3/3 | 0.00 |
| `agent-author-agentic-release-notes` | 3/3 | 3/3 | 0.00 |

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `agentic-contract` | judge | 100% | 100% |
| all pass | - | 100% | 100% |

eval_compare verdict: **no measurable difference**. Paired difference (after − before) +0.000, 95% CI
[+0.000, +0.000]; sign test ties 5, p = 1. Errored runs: before 0, after 0; judge errors: before 0, after
0. The judge is provisional. The revert rule fires only on "a better", so **the change is kept**. The run
contains `NEEDS_CONTEXT` in 3 of 15 runs, against 8 of 15 in the T3.6 after run (a raw string count over
result.json). The judge still passed PA-20 in every run, so the agents named another action for unclear
input; this count is not a grader.

Spend, a comparison figure only (subscription): before $7.59, after $7.78.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus before, averaged over the cases.

## Instruction-file scoring group (spec 023 T3.5, PA-31, PA-30, PA-01)

Five cases defend the corrected rule: memory-claude-md-optimize gives no score for CLAUDE.md content
that the README or code already provides, and it proposes removing that content. Each case has the
model write a small fixture repo (`tally`: README.md, pyproject.toml, three modules and a test) whose
CLAUDE.md repeats one README section next to a commit rule the README lacks. The repeated section is
the architecture overview, the directory tree, the tech-stack list or the setup steps. The `mix`
case repeats overview, stack and setup, and adds one rule no file shows (the `ops-reports` nightly
job reads `tally.db`). Each case then runs `/tcs-helper:memory-claude-md-optimize --scope repo`, writes
the proposal and stops before apply. Graders read `claude-md-optimization/OPTIMIZATION-REPORT.md`:
`file-written` (file_exists), `duplicate-not-rewarded` (llm: no criterion score credits the copy, and
the report proposes removing it rather than keeping or migrating it) and, in `mix` only,
`gotcha-kept` (llm: the `ops-reports` rule is kept or migrated, not deleted).

"Before" is the skill at `98a5cac2`. Its rubric rewarded a "clear architectural overview" and its
low-score guidance said to add one. The correction came in two commits, measured as after1 and
after2:

- `ded717a3` cites PA-31, PA-30 and PA-01. The rubric reads the README and code first and credits
  only what they lack. Architecture Clarity rewards constraints and design reasons the README lacks,
  with the failure each prevents. SKILL.md marks README duplicates for removal, not migration.
- `9660a3a5`: Currency and Actionability are also scored only on what remains once the duplicates
  are set aside. The after1 reports showed the cause: they removed the copy and gave it 0
  Architecture Clarity, but Currency credited its accuracy ("every path matches the tree").

All runs used `--ablation none --allow-tools Write Edit`, 3 runs per case, `-j 4`, Opus 5.5, the
default judge model.

Rates are each case's all-pass rate over runs that neither errored nor went unjudged:

| Case | Before | After1 | After2 |
|---|---|---|---|
| `claude-md-optimize-overview-architecture` | 0/3 | 2/3 | 3/3 |
| `claude-md-optimize-overview-tree` | 0/3 | 0/3 | 3/3 |
| `claude-md-optimize-overview-stack` | 0/3 | 0/3 | 3/3 |
| `claude-md-optimize-overview-setup` | 0/3 | 0/3 | 3/3 |
| `claude-md-optimize-overview-mix` | 0/3 | 0/3 | 3/3 |

- **Before:** every report already removed the copy, so the whole failure was the score. The copied
  overview earned 13/20 Architecture Clarity, and a file listing earned 5/20. The issues list said
  "add a brief overview" even when the README had one.
- **After1:** the copy earned 0 Architecture Clarity in every report. 13 of 15 runs still failed,
  because Currency or Actionability credited the copy.
- **mix:** `gotcha-kept` passed 3/3 in every arm. Every report kept the `ops-reports` rule in
  CLAUDE.md.

| Criterion | Kind | Before | After1 | After2 |
|---|---|---|---|---|
| `file-written` | deterministic | 100% | 100% | 100% |
| `duplicate-not-rewarded` | judge | 0% | 13% | 100% |
| `gotcha-kept` | judge | 100% | 100% | 100% |
| all pass | - | 0% | 13% | 100% |

eval_compare, before vs after1: **no measurable difference**. Paired difference +0.133, 95% CI
[+0.000, +0.400]; sign test 1/0/4 ties, p = 1.

eval_compare, before vs after2: **b better** (after better). Paired difference (b − a) +1.000, 95% CI
[+1.000, +1.000] over the 5 cases; sign test b better 5, a better 0, ties 0, p = 0.0625. No errored
runs, no judge errors and no unjudged runs in any arm.

The revert rule fires only on "a better", so **the correction is kept**. The memory-claude-md-optimize
strict xfail in `test_prompt_single_source.py` is gone: the skill is in `MIGRATED_CONSUMERS`.

Spend, a comparison figure only (subscription): before $10.76, after1 $8.83, after2 $8.74.

How far this result holds: after1 is the only first-pass result, the only one not tuned on these
cases. It showed no measurable difference (+0.133, CI [0.000, +0.400], sign test 1/0/4) and no
regression. The second commit (`9660a3a5`, Currency and Actionability score only what is not a copy)
was designed from after1's failures on the same 5 cases and measured on them again, so after2's
+1.000, CI [+1.000, +1.000] is in-sample. The CI is degenerate because all five cases flipped, and at
n = 5 the sign test cannot go below p = 0.0625. All five cases share one fixture repo, there was no
held-out case, and the judge is provisional. The change is kept because no regression was found;
confirming the gain needs fresh cases.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus
before, averaged over the cases.

### Copies-only follow-up (spec 023 T3.8, F-B2)

The T3.5 quality review asked whether a CLAUDE.md made only of README copies could still score
Currency or Actionability, since an accurate copy has "no stale entries". A sixth case,
`claude-md-optimize-overview-copies-only` (`7999e324`), tests it: the same fixture repo, a CLAUDE.md of
architecture, layout, stack and setup copied from the README, and an llm grader that requires Currency
0 and Actionability 0, or a statement that nothing remains once the copies are set aside.

On the skill at T3.5's second correction (`9660a3a5`) it scored 3/3 before any change: every report
gave Currency 0/15, Actionability 0/15 and 0/100 in total. The preamble rule from `9660a3a5` already
reaches both criteria, so the rubric was not changed and no after run was needed. The case stays as a
regression guard. Spend $1.68; no errored or unjudged runs. Same caveat as T3.5: one fixture repo,
provisional judge.

## Redundant-restatement rule group (spec 023 T3.10, PA-05)

Five cases defend PA-05: a skill states each of its rules in one place. Each case asks skill-author
for a small skill whose brief invites a restatement: notes that repeat each rule across three wiki
pages (`pr-description`), a suggested closing "Key reminders" recap (`endpoint-docs`), the same rules
as Always and as Never (`dependency-bump`), a requested "Before you post" checklist (`incident-notes`),
and a brief that repeats each rule three times (`translation-keys`). Two graders read the written
file: `file-written` (file_exists) and `stated-once` (llm).

"Before" is skill-author at `af8fefcb`, which only forbade mirroring a rule across the Always and
Never lists. "After" is the correction in `3d3ade64`, citing PA-05: state each rule once in the skill;
a rule in Constraints is not restated in a summary, reminder or closing checklist, and a closing check
names what it checks ("check the draft against Constraints"). The one exception is the
discipline-skill terminal restatement (PA-03). `637742c5` then cut the Constraints paragraph of
`conventions.md`, which restated the Constraint Deduplication section in the same file, to a pointer
to that section. All runs used `--ablation none --allow-tools Write Edit`, 3 runs per case, `-j 4`,
Opus 5.5, the default judge model.

### Round 1: the grader could not see the change

Round 1's `stated-once` counted every place a rule appears, so a Constraints rule plus the workflow
step that carries it out counted as two statements. Both sides scored 0/15 (all five cases 0/3), and
eval_compare reported **no measurable difference** (+0.000, CI [+0.000, +0.000], sign test 0/0/5,
p = 1). The files did differ: after the correction, the closing check referred to Constraints in 11
of 15 files, against 0 of 15 before. But the skill-author layout (Constraints, then Workflow)
produces the rule-plus-step overlap for every output-format rule, so the grader failed every file on
both sides.

### Round 2: grader redesigned, both arms re-measured

After round 1 the grader was redesigned, not the skill (`61353054`). A rule stated once, plus any
workflow step, layout template or example that applies or carries it out, now counts as one
statement. A second statement as a rule still fails: a summary, recap, "key reminders" or "remember"
section, a checklist or closing check that re-lists the rules instead of pointing to them, or an
Always/Never mirror. A one-line cross-reference passes. `incident-notes` keeps its requested
checklist: one that points to the rules passes, one that restates them fails. No prompt changed;
only `incident-notes`' `expected_outcome` metadata follows the grader.

Both arms were re-measured with the new grader; no round-1 data is reused. before2 ran against a
worktree at `af8fefcb` with the new grader files copied in, and after2 ran on HEAD (`637742c5`).

| Case | Before2 | After2 | Delta |
|---|---|---|---|
| `skill-author-restate-dependency-bump` | 1/3 | 2/3 | +1 |
| `skill-author-restate-endpoint-docs` | 2/3 | 3/3 | +1 |
| `skill-author-restate-incident-notes` | 0/3 | 0/3 | 0 |
| `skill-author-restate-pr-description` | 1/3 | 2/3 | +1 |
| `skill-author-restate-translation-keys` | 0/3 | 0/3 | 0 |

| Criterion | Kind | Before2 | After2 |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `stated-once` | judge | 27% | 47% |
| all pass | - | 27% | 47% |

- **Closing check:** it refers to Constraints in 11 of 15 after2 files, against 0 of 15 in before2.
  Before2 check steps list the rules again, for example "Confirm every new key starts with the page
  name and exists in both `en.json` and `de.json`".
- **`incident-notes` fails 3/3 on both sides.** Every file has the requested "Before you post"
  checklist, and in every file its four items restate the four rules. After2 runs the draft "through
  Before you post below", but the checklist itself still states the rules. The correction does not
  get skill-author to write a pointing checklist when the user asks for one.
- **`translation-keys` fails 3/3 on both sides.** Its brief repeats each rule three times. After2's
  check step opens with "Check the change against Constraints", then names the rules again ("confirm
  every new key exists in both JSON files and both are staged in the same commit"). The judges count
  that as a second statement.
- **Split votes:** before2 `dependency-bump` runs 1 and 2, and after2 `pr-description` runs 1 and 3,
  were 2-1 majorities.

eval_compare verdict: **b better** (after better). Paired difference (after − before) +0.200, 95% CI
[+0.067, +0.333] over the 5 cases; sign test after better 3, before better 0, ties 2, p = 0.25.
Errored runs: none; judge errors: none; unjudged runs: none. The revert rule fires only on "a better",
so **the correction is kept**. Judge validation: `stated-once` provisional.

Spend, a comparison figure only (subscription): round 1 before $5.27, after $5.38; round 2 before2
$5.20, after2 $4.68.

How far this result holds: the round-2 grader was designed from round 1's outputs on the same 5
cases, so its +0.200 is in-sample for the grader, although the skill was not changed between rounds.
At n = 5 the sign test cannot go below p = 0.0625, and this one is p = 0.25. The judge is
provisional and has no recorded reasoning per vote. The two cases that fail on both sides show the
correction's limit: it stops recaps and Always/Never mirrors, but not a checklist the user asks for,
or a check step that names the rules after pointing to Constraints.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus
before, averaged over the cases.

Wording gap left open: skill-author conventions.md:316 forbids restating a rule in a workflow step,
while the round-2 grader accepts a step that applies the rule. Applying is not restating, so the two
agree in substance, but :316 can read as stricter. It was not reworded, because that would change the
measured arm and need a new after run.

After the measured runs, the checklist item at conventions.md:403 was cut to a pointer to Constraint Deduplication (`37af98bc`), because it restated the rule in a checklist. That edit is unmeasured; it only points at the measured section.

## Assumed-absent-context group (spec 023 T3.11, PA-08)

Five cases guard the rule that a subagent sees only its own body and its brief. Each asks agent-author
for an agent a parent dispatches with a brief, from a request that leans on facts only the parent
conversation has: "the migration file we discussed" and "the usual branch" (migration reviewer), "the
bug from earlier" and "the test layout we agreed on" (bug reproducer), "the naming convention I
mentioned once" (naming checker), "the fix we talked about" and "the test command from last time"
(fix backporter), and "the settings we agreed to remove" (config auditor). Each case has two graders
on the written file: `file-written` (file_exists) and `explicit-inputs` (llm, binary). That grader
checks that the body names every such fact as an input the caller passes, or reports it as missing, and
that the body has no wording that presumes the parent conversation.

This is a citation migration, not a rule change. "Before" is agent-author at `2c6bae47`. "After" is
`70ab20c9` plus `241c9d8f`. In agent-author `reference/anti-patterns.md` "Assuming Parent Context Is
Visible", the restated reason and the list of what a subagent receives are removed; the tell and the Fix
stay, with `Reason: PA-08`. The `reference/conventions.md` anti-pattern bullet drops "it isn't" and
gains `Reason: PA-08`. In `docs/about/principles.md` § 2.3 the two delegation bullets become one, with
`Reason: PA-08`. Both runs were `--ablation none --allow-tools Write Edit`, 3 runs per case, `-j 4`,
Claude Code 2.1.316, Opus 5.5, default judge model.

Rates are each case's all-pass rate over runs that neither errored nor went unjudged, as eval_compare counts them:

| Case | Before | After | Delta |
|---|---|---|---|
| `agent-author-context-backport` | 3/3 | 3/3 | 0.00 |
| `agent-author-context-bug-repro` | 3/3 | 3/3 | 0.00 |
| `agent-author-context-config-audit` | 3/3 | 3/3 | 0.00 |
| `agent-author-context-migration-review` | 3/3 | 3/3 | 0.00 |
| `agent-author-context-naming-check` | 3/3 | 3/3 | 0.00 |

- **Signal:** none, as expected. The rule was already correct, so all five cases sat at 1.00 before and
  serve as regression guards. Every judge vote was PASS PASS PASS. A bug-reproducer file checked by hand
  takes the report and the test layout from the brief only, says it cannot see the parent conversation,
  and returns `NEEDS_CONTEXT` when the brief has no layout.
- No run errored or went unjudged on either side.

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `explicit-inputs` | judge | 100% | 100% |
| all pass | - | 100% | 100% |

eval_compare verdict: **no measurable difference**. Paired difference (after − before) +0.000, 95% CI
[+0.000, +0.000]; sign test ties 5, p = 1. Errored runs: before 0, after 0; judge errors: before 0, after
0. The judge is provisional (not validated against hand labels). The revert rule fires only on "a
better", so **the citation is kept**.

Spend, a comparison figure only (subscription): before $6.19, after $6.42.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus before, averaged over the cases.

## Output-contract group (spec 023 T3.12, PA-13)

Five cases guard the rule that an agent whose caller parses its return states a complete output
contract. Each asks agent-author for one such agent, with a different return kind: an accessibility
auditor returning findings, a license gate returning one verdict with reasons, an incident summarizer
returning a structured summary, an env-var checker returning a table of variables with statuses, and a
docker-compose fixer returning a diff proposal. The prompts say only "the caller parses its result" and
nothing about the format. Each case has two graders on the written file: `file-written` (file_exists)
and `output-contract` (llm, binary). That grader checks three things in the body: every field is named,
nested items included; every field has a type, and every status, verdict or severity field lists its
allowed values; and the section shows an example or a serialized schema of the return. A field table on
its own does not count as the example.

This is a correction plus citation. The copies said only "typed table" and "explicit return contract",
and asked for no example of the return. The measured gain comes from the example requirement: the
before files already had allowed values and often said where the return appears, and 14 of 15 failed
only on the missing example (see Signal below). "Before" is
agent-author at `b29d8c61`. "After" is `99514049`. In agent-author SKILL.md, create step 6's Output line
asks for every field's type or allowed values and one example of the return as the caller receives it,
and cites PA-13. Verify step 7 checks the same. `reference/conventions.md` § 7 states the full contract,
adds a status enum row and an example line, with `Reason: PA-13`. In `reference/output-formats.md`, line
3 states the contract and cites PA-13 in place of the restated reason ("makes orchestration brittle").
The TCS convention there gains a closing example block, and the audit checklist gains a PA-13 row. In
skill-author `reference/conventions.md` (`d41ffd73`), the "Why TypeScript-like syntax" reason becomes
the operational line plus `Reason: PA-13`. No case exercises skill-author, so that change is unmeasured.
A follow-up (`1ff3c1b0`) adds "where the return appears in the reply" to agent-author conventions.md
§ 7 and to the create and Verify lines in SKILL.md, the third part of PA-13's Fix. It came after the
after run and is unmeasured.
Both runs were `--ablation none --allow-tools Write Edit`, 3 runs per case, `-j 4`, Claude Code
2.1.316, Opus 5.5, default judge model.

Rates are each case's all-pass rate over runs that neither errored nor went unjudged, as eval_compare counts them:

| Case | Before | After | Delta |
|---|---|---|---|
| `agent-author-output-diff` | 0/3 | 3/3 | +1.00 |
| `agent-author-output-findings` | 1/3 | 3/3 | +0.67 |
| `agent-author-output-status-table` | 0/3 | 3/3 | +1.00 |
| `agent-author-output-summary` | 0/3 | 3/3 | +1.00 |
| `agent-author-output-verdict` | 0/3 | 3/3 | +1.00 |

- **Signal:** strong. All 14 before failures were judged FAIL FAIL FAIL. Checked by hand, the before
  files have full field tables with enum types (no status field typed only as `string`) and often say
  where the return appears ("one fenced `json` block"). But 14 of 15 show no example of the return.
  The one pass (findings run 3) is the only file with an example.
- **After:** all 15 files have an example of the return after the field tables, every one a filled-in
  JSON object.
- No run errored or went unjudged on either side.

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `output-contract` | judge | 7% | 100% |
| all pass | - | 7% | 100% |

eval_compare verdict: **b better** (after better). Paired difference (after − before) +0.933, 95% CI
[+0.800, +1.000] over the 5 cases; sign test after better 5, before better 0, ties 0, p = 0.0625.
Errored runs: before 0, after 0; judge errors: before 0, after 0. The judge is provisional (not
validated against hand labels). The revert rule fires only on "a better", so **the correction is kept**.

Spend, a comparison figure only (subscription): before $8.32, after $8.73.

- **After3** (`cda2731f`, which also carries the earlier unmeasured `1ff3c1b0`): a review found that
  output-formats.md and conventions.md § 7 each showed one JSON example and never said the
  serialization follows the caller, and all 15 after agents returned JSON (PA-11 risk).
  output-formats.md now states that where the return appears and its serialization follow what the
  caller parses, and shows the JSON example as one case next to a `VERDICT:`/`REASON:` line example.
  § 7 points to it in place of its own JSON example and defines `Finding`. all pass 15/15.
  eval_compare after → after3: **no measurable difference** (paired difference +0.000, 95% CI
  [+0.000, +0.000]; ties 5, p = 1; errored runs 0 and 0, judge errors 0 and 0), so **the change is
  kept**. Non-JSON returns: 0 of 15, as before. Every prompt says only that "the caller parses its
  result", and JSON is a reasonable answer to that, so this does not show whether the single example
  anchored the choice. A case naming a non-JSON parser would. Spend $8.83.

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus before, averaged over the cases.

### Catalog amendment (PA-13)

The agent-author result showed that PA-13's Fix itself left out the example. The Fix now reads "each
field, its allowed values, where it appears, and, for a return the caller parses, one example or schema
of the return" (`85a5cebf`). The Evidence line cites spec 023 T3.12. The Fingerprint is unchanged. The
Tell, at first unchanged, was later extended to match the Fix (`e9c98749`, see After2 below).
Five `prompt-author-audit-contract-*` cases (`f575c461`) measure whether audits now flag the gap. In each,
the model saves a subagent brief and audits it with prompt-author: a security reviewer returning a JSON
findings block, a license gate returning `VERDICT:`/`REASON:` lines, an incident summarizer returning
YAML, an env-var checker returning CSV rows, and a compose fixer returning a JSON change list. Each brief
has a complete field table with types and allowed values and says where the return appears, but shows
no example and no schema. Graders: `file-written` on `audit/findings.md`, and `flags-missing-example`
(llm, binary), which passes only on a PA-13 finding naming the missing example or schema. "Before" is
the unamended catalog at `f575c461`; "after" is `85a5cebf`; "after2" is `e9c98749`. Same run settings as above.

| Case | Before | After | After2 |
|---|---|---|---|
| `prompt-author-audit-contract-diff` | 0/3 | 1/3 | 1/3 |
| `prompt-author-audit-contract-review` | 0/3 | 2/3 | 3/3 |
| `prompt-author-audit-contract-status-table` | 1/3 | 3/3 | 3/3 |
| `prompt-author-audit-contract-summary` | 0/3 | 3/3 | 3/3 |
| `prompt-author-audit-contract-verdict` | 0/3 | 3/3 | 3/3 |

- **Signal:** before, 14 of 15 audits found a contract present and filed PA-13, if at all, only for
  position or format gaps ("PA-13: a contract is present"). The one pass (status-table run 3, judge
  votes 2 of 3) asks for the literal CSV header line.
- **After:** 12 of 15 audits flag the missing example under PA-13, and several quote the Fix ("which the
  entry's Fix requires when a caller parses the output"). Of the three failures, two raise PA-13 only
  for other gaps (diff runs 1-2), and one raises the missing example as "uncatalogued" (review run 1).
  The audit procedure cites an entry only when its Tell is present, and the Tell still reads "names no
  fields, status values or format", which these briefs do not match. That likely explains the misses.
- No run errored or went unjudged on either side.

| Criterion | Kind | Before | After |
|---|---|---|---|
| `file-written` | deterministic | 100% | 100% |
| `flags-missing-example` | judge | 7% | 80% |
| all pass | - | 7% | 80% |

After2 (Tell extended): `flags-missing-example` 87%, all pass 87%, `file-written` 100%.

eval_compare verdict: **b better** (after better). Paired difference (after − before) +0.733, 95% CI
[+0.533, +0.933] over the 5 cases; sign test after better 5, before better 0, ties 0, p = 0.0625.
Errored runs: before 0, after 0; judge errors: before 0, after 0. The judge is provisional. The guard
case is excluded from the paired set: both result files were filtered to the 5 cases before comparing.
The revert rule fires only on "a better", so **the amendment is kept**.

- **After2:** the Tell now adds "or, for a return the caller parses, shows no example or schema of it"
  (`e9c98749`). 13 of 15 audits flag the missing example under PA-13. Review is now 3/3. Diff stays at
  1/3: runs 1 and 3 again raise PA-13 only for other gaps, and run 1 says the Tell's "no example or
  schema" does not apply because "the field table serves as a schema".
- eval_compare after → after2 (the measure for the Tell change): **no measurable difference**. Paired
  difference +0.067, 95% CI [+0.000, +0.200]; sign test after2 better 1, after better 0, ties 4, p = 1.
  Errored runs 0 and 0; judge errors 0 and 0. Not "a better", so **the Tell change is kept**.
- eval_compare before → after2 (the whole amendment): **b better**. Paired difference +0.800, 95% CI
  [+0.533, +1.000]; sign test after2 better 5, before better 0, ties 0, p = 0.0625. Errored runs 0 and
  0; judge errors 0 and 0.

**Guard case** (`prompt-author-audit-contract-guard-example`): the review brief with a filled-in JSON
example added. Its grader passes when no PA-13 finding claims a missing example or schema. Before 3/3;
after 2/3 as judged (run 3 votes FAIL PASS FAIL). By hand, after run 3 raises no PA-13 finding about the
example. It lists PA-13 as "a contract is present" and raises only PA-11 (a single example may
over-anchor). So the judge misjudged a passing run, and no false positive appeared on either side. After2: 3/3
(run 1 votes PASS FAIL PASS). By hand, no after2 run raises a PA-13 finding about a missing example:
run 1 raises PA-13 only for the `line` numbering and the `category` enum's fallback, and runs 2 and 3
list PA-13 as clean ("states fields, values, position and an example"). The example's narrow coverage
is raised under PA-11 in all three. So the guard shows no false positive in after2 either. The
guard's first before run did not load (a YAML colon in its description, fixed in `cba6b41f`), so its
before was run on its own at `cba6b41f`. After these runs, the guard grader was clarified (`53e8319b`):
a finding that the example is narrow or may over-anchor (PA-11) does not count as a missing example.
The guard is unpaired, so the paired measurement is unchanged.

Spend, a comparison figure only (subscription): before $13.92 for the 5 cases plus $2.86 for the guard;
after $16.45 for all 6 ($14.02 for the 5 cases, judge included); after2 $17.57 for all 6 ($14.67 for
the 5 cases, $2.90 for the guard).

eval_compare pairs the two sides per case on that all-pass rate; the paired difference is after minus before, averaged over the cases.

## Cost

The prompt-author suite at 3 runs per arm costs about $7.40 (with plugin about $2.05 per round of four
cases, without about $0.41) and takes about 6 minutes with `-j 4`. Set `--max-cost-usd` to 10: the
ceiling is checked before each run launches, so at 8 the last port-gate-exit runs can be cut off and
their llm grader skipped.

## Audit acceptance (T2.6)

A manual acceptance run of prompt-author's audit mode (PRD F3 AC6, Success Metrics "Audit recall").
The auditor reads and follows `SKILL.md`, `reference/audit.md`, the catalog through its index and
`scripts/prompt_lint.py`, and uses nothing else to find a defect; a defect found only from outside
knowledge counts as missed. No model call, no plugin eval. Each prompt is audited at the commit
before its fix: no fix for #250–#253 had landed on `main` or on this branch, so HEAD `9c9b5a6f` is
the audited version.

### Expected findings (written before the run)

**Issues** (SDD F3 acceptance criterion):

| Issue | Scope | Files | Expected |
|---|---|---|---|
| #250 | pair | `implement-incremental/SKILL.md` step 4d brief + the status branch after it; `implement-direct/SKILL.md` brief + its status branch | PA-14: the orchestrator branches on `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`, the brief never requests a status (both skills) |
| #251 | pair | `review/SKILL.md` perspective brief + synthesis | PA-14: synthesis dedupes by location and sorts by severity, then confidence; the brief requests no finding format. PA-24: no read-only-git fence and no commit-range scoping |
| #252 | single (instruction-file) | `AGENTS.md` | PA-30 for each stale fact: `the-meta-agent.md` absent; "v2.0.0" vs the manifest; skills `setup/`, `docs/`; `writing-skills/reference/conventions.md`; `docs/patterns`, `docs/interfaces`, `docs/domain`; tcs-git-helpers and tcs-issues missing from the tree; the false "prefixing only applies to commands" claim |
| #253 | single (code) | `scripts/lib/semantic_detector.py` | PA-15 on both prompt literals that interpolate session text; lint E4 reports them |

**Corpus** (`research-corpus.md`, one documented defect per item and failure code, mapped to the
catalog; where the catalog splits a corpus code, either entry named counts as found):

| # | Prompt | Scope | Documented defects → expected entry | n |
|---|---|---|---|---|
| 1 | `docs/templates/research-prompt.md` | single | EX → PA-11; CX no no-search fallback → PA-08 | 2 |
| 2 | `docs/templates/setup-perplexity-space.md` | single | RD → PA-05; PL "work identically" untested → PA-41 (or PA-40) | 2 |
| 3 | `docs/templates/prd-prompt.md` | single | RD → PA-05; NO → PA-04; EM → PA-03; PL/CX undefined `[NEEDS CLARIFICATION]` → PA-40 or PA-08 | 4 |
| 4 | `docs/templates/brainstorm-prompt.md` | single | RD → PA-05; EM → PA-03; PL/OP Red Flags table → PA-40 or PA-09; CO "urgency cues don't override" vs the user → PA-06 | 4 |
| 5 | `docs/templates/setup-claude-project.md` | single | SC project-wide gate hits research queries → PA-32; RD PRD ban repeated from #3 → PA-05 | 2 |
| 6 | `AGENTS.md` | single | ST → PA-30; CO l.107 → PA-06 (or PA-30); LL mostly overview → PA-10 or PA-31 | 3 |
| 7 | `CLAUDE.md` | set | CX/ST `~/.claude/includes/` → PA-08 or PA-30; CO "sync changes back" → PA-06; RD cp block duplicated → PA-05; SC/LL always-loaded procedure → PA-32 or PA-10 | 4 |
| 8 | `docs/ai/CLAUDE.md` | set | RH/NO ban without reason → PA-01 or PA-04 | 1 |
| 9 | `~/Kouzou/standards/general.md` | set | CX Plan Mode / macOS → PA-08; EM "ANY" → PA-03; RH "(Recurs ≥1×/session.)" → PA-02; CO tracked-in-git vs gitignored → PA-06 | 4 |
| 10 | `~/Kouzou/standards/tone-behavior.md` + `code-conduct.md` | set | cross-file CO → PA-07; in-file CO → PA-06; EM "NEVER create files" → PA-03; RH maintainer note → PA-02 | 4 |
| 11 | `~/Kouzou/standards/guardrails.md` | set | RH dates/SHAs → PA-02; EE one rule per incident → PA-09; SC off-topic rules → PA-32; cross-file CO `venv/` vs `.venv/` → PA-07; EM "non-negotiable" → PA-03 | 5 |
| 12 | `brainstorm/reference/spec-reviewer-prompt.md` | pair | VP "Approve unless" → PA-25; UI spec not marked as data → PA-15; ST "Task tool" → PA-30 | 3 |
| 13 | `implement-incremental` + `implement-direct` brief | pair | OC/CA → PA-14 (or PA-13); RD/CO l.60 vs l.70 → PA-05 or PA-06; EM → PA-03; LL → PA-10 | 4 |
| 14 | `review/SKILL.md` brief | pair | OC/CA → PA-14; CX fence and range → PA-24 (or PA-08); EM "Aggressively challenge" → PA-03 (or PA-25) | 3 |
| 15 | `tcs-team/agents/the-chief.md` | single | OP → PA-09; CO → PA-06; EM → PA-03; CX → PA-08 | 4 |
| 16 | `docs/ai/memory/active.md`, `general.md` | set | none documented (the corpus's "best in corpus"; its weaknesses carry no failure code) | 0 |
| | | | **total** | **49** |

The `~/Kouzou/standards/*` files sit outside the repository; they are audited read-only and their
findings marked external. Items 7–11 and 16 are audited as one set (CLAUDE.md, its `@`-imports and the
standards they load), because SKILL.md step 2 hands off a lone CLAUDE.md. Item 15 is an agent
definition: if the procedure hands it off, that is recorded, and recall is reported with and without it.

### Results

Audited at `9c9b5a6f` by following the skill text (Opus 5.5 as the auditor, no model call). Run 1 uses
the skill as committed; run 2 re-audits only the missed items after the fix in `19a5cc9a`.
Lint: `prompt_lint.py --json --kind <kind>` over all 20 files: exit 0 everywhere except
`semantic_detector.py` (exit 1, two E4 errors). W1–W3 fired nowhere: they are density thresholds
(W1 above 5 hits per 1000 words, W2 above 150 items), so every PA-03 and PA-10 finding below comes from
step 3, not the lint.

**Issues: 4 of 4 found** (run 1; #252's l.107 sub-fact in run 2).

| Issue | Severity | Location | Entry | Problem (abridged) | Found by |
|---|---|---|---|---|---|
| #250 | blocking | `implement-incremental/SKILL.md:189-204` + `:208-219` | PA-14 | 4e branches on `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`; the 4d brief asks only "commit, self-review before reporting" | pair step 5 |
| #250 | blocking | `implement-direct/SKILL.md:116-122` + `:128-140` | PA-14 | same four statuses in 3c; the 3b brief requests none | pair step 5 |
| #251 | blocking | `review/SKILL.md:111-113` + `:122-126` | PA-14 | synthesis dedupes by location, sorts by severity then confidence, sets `breaking`; the brief passes files and a diff, and the `Finding` shape (l.19-31) never reaches the reviewer | pair step 5 |
| #251 | major | `review/SKILL.md:111-113` | PA-24 | no read-only-git rule; the range is passed as the diff boundary, but with "full file contents" and no "ignore everything else" | step 3 |
| #252 | major | `AGENTS.md:29,37` / `:41` / `:54-55` / `:122` / `:233-235` / `:11-72` | PA-30 | `the-meta-agent.md` absent; "v2.0.0" vs manifest 4.4.8; `setup/`, `docs/` are `memory-setup`, `doc-product`; `writing-skills/…/conventions.md` absent; `docs/patterns|interfaces|domain` absent; tree lists 4 plugins, `plugins/` holds 6 (tcs-git-helpers, tcs-issues missing) | step 6 |
| #252 | major | `AGENTS.md:107` + `implement-incremental/SKILL.md:53` | PA-30 | "prefixing only applies to commands, not skills"; the repo's own files invoke skills as `Skill(tcs-workflow:validate)` and `/tcs-helper:skill-author` | **run 2 only** (step 6 after fix) |
| #253 | blocking | `semantic_detector.py:129-136` | PA-15 | session `text` interpolated between plain quotes, no tag, no provenance, no "data, not instructions" | lint E4 (l.129) + step 7 |
| #253 | blocking | `semantic_detector.py:94-98` | PA-15 | `Entry A: {}` / `Entry B: {}` memory entries interpolated undelimited | lint E4 (l.95) + step 7 |

**Corpus: run 1 40/49 (81.6%), run 2 43/49 (87.8%).** Over the 45 defects in prompts the skill keeps
(item 15 is handed off, below): run 1 88.9%, run 2 **95.6%**. All 16 items were reachable, including
`~/Kouzou/standards/*` (audited read-only, findings external).

| # | Defect → entry found | Run 1 | Run 2 |
|---|---|---|---|
| 1 | EX `research-prompt.md:93` "(Stripe, Netflix, Shopify, etc.)" → PA-11; CX search assumed, no no-search fallback (`:3,10,26`) → PA-08 | 2/2 | — |
| 2 | RD `setup-perplexity-space.md:25`+`:32`, `:26`+`:34` always/never mirror → PA-05; PL `:58` "they work identically" → PA-41 | 2/2 | — |
| 3 | RD no-HOW `prd-prompt.md:11,26,30-37,72` → PA-05; NO `:30-37` → PA-04; EM `:11,21,32` → PA-03; `[NEEDS CLARIFICATION]` `:63` undefined → PA-40 | 4/4 | — |
| 4 | RD one question `brainstorm-prompt.md:17,28,40,49,87` → PA-05; EM `:17,22,24,49` → PA-03; Red Flags table `:34-43` → PA-40 / PA-09; "Urgency cues don't override" `:39` → **PA-16** (the user's "start coding" has no exit), not the expected PA-06 | 4/4 | — |
| 5 | SC `setup-claude-project.md:30-34` rules for all sessions → PA-32; RD `:31,33,34` restate the brainstorm and PRD templates → PA-05 | 0/2 | 2/2 |
| 6 | ST → PA-30 (above); overview `AGENTS.md:9-94` → PA-31; CO/false claim `:107` → PA-30 | 2/3 | 3/3 |
| 7 | `CLAUDE.md:17` `~/.claude/includes/` absent → PA-30; `:57` "sync back" vs a repo→cache copy → PA-06; `:45-50`+`:59-62` → PA-05; `:31-63` always-loaded test procedure → PA-32 | 4/4 | — |
| 8 | `docs/ai/CLAUDE.md:29` bans without reason → PA-01 | 1/1 | — |
| 9 | `general.md:7` Plan Mode, `:12` macOS → PA-08; `:13` "ANY", "Do NOT" → PA-03; `:13` "(Recurs ≥1×/session.)" → PA-02; `:16` tracked-in-git vs gitignored edits allowed → PA-06 | 4/4 | — |
| 10 | `tone-behavior.md:8` + `code-conduct.md:8` → PA-07; `code-conduct.md:4`+`:13` → PA-06; `:11` "NEVER" → PA-03; `:16` "(Mirror in `workflows.md`…)" → PA-02 | 4/4 | — |
| 11 | `guardrails.md:12,15,18,…` dates, `024f277`, repo names → PA-02; one rule per incident → PA-09; `:9`, `:18` UI/Obsidian rules → PA-32; `:11` `venv/` + `AGENTS.md:151` `.venv/` → PA-07; `:37` "non-negotiable" → PA-03 | 5/5 | — |
| 12 | `spec-reviewer-prompt.md:38` "Approve unless" → PA-25; spec read without a data marking → PA-15 (minor, via step 7's tool-output clause); "Task tool" `:14` → missed | 2/3 | 2/3 |
| 13 | PA-14 (#250); `implement-incremental/SKILL.md:60`+`:70`+`:199` → PA-05; `:49,59,64,191,199` ALL/ALWAYS/ONLY/NOT → PA-03; LL → missed | 3/4 | 3/4 |
| 14 | PA-14 (#251); fence and range → PA-24; `review/reference/perspectives.md:12` "Aggressively challenge" → PA-25 | 3/3 | — |
| 15 | `tcs-team/agents/the-chief.md`: an agent definition audited alone, so SKILL.md step 2 hands it to agent-author and the workflow ends | 0/4 | 0/4 |
| 16 | no documented defect | — | — |

Remaining misses:

- **12 "Task tool"** (tree gap): `brainstorm/SKILL.md` lists `Task` in `allowed-tools`, so the tree agrees
  with the brief; the corpus marks the defect unverified. A harness tool name has no in-tree source.
  No fix.
- **13 LL** (catalog threshold): PA-10's Tell starts at about a hundred rules in one context; the corpus
  counted 22 constraints. The threshold is the IFScale-backed one, so the corpus label is looser than
  the entry. No fix.
- **15 the-chief** (by design): SKILL.md step 2 sends a lone agent definition to agent-author. Recall
  counts it as missed; whether agent-author finds OP, CO, EM and CX is not measured here.

Fixes (`19a5cc9a`; catalog and lint tests 619 passed before and after):

- audit.md step 6 checks an invocation form or prefixing rule against how the repository's own files
  invoke the same thing (item 6 l.107).
- PA-32 applies to api-system, and its Tell names a chat-tool project's system prompt; the index row
  matches (item 5 SC).
- audit.md set scope includes a chat-tool project's instructions with the templates pasted into it, and
  step 4 reports restatements across files (PA-05) as well as conflicts (item 5 RD).

Findings beyond the documented defects: `implement-incremental` 4d asks for no report shape though 4f
reads "the implementer's report" (PA-13) and does not say what to do when an input is missing (PA-20);
`review/SKILL.md:49` "ALL" (PA-03); `AGENTS.md:16` says `tcs-workflow/agents` holds the-chief (it holds
the three gate agents), `:29` gives "13 activity + the-chief + the-meta-agent", `:44` "19" templates
(PA-30); `research-prompt.md:4` claims standalone use untested (PA-41); `prd-prompt.md:22` approval
gate without an exit (PA-16).

### Item 5 re-check (T2.9)

The run 2 fix (`19a5cc9a`) made PA-32 load for api-system. SKILL.md step 1 sends text pasted into
another chat tool to chat-template, which PA-32 did not list, so the SC finding held only when the
auditor read the project instructions as api-system. T2.9 has step 1 name a chat-tool project's
instructions as chat-template and adds chat-template to PA-32's kinds (entry and index row).

Re-checked offline (no model call) by reading `docs/templates/setup-claude-project.md` at this commit as
chat-template, target claude, against the rows that load for it: every `any` row plus PA-16, PA-32,
PA-40 and PA-41 (PA-12 is small-local only).

- **SC → PA-32: found.** `:30` "General rules that apply in all sessions" puts phase rules at project
  level: `:33` bans implementation detail "in PRD work" for brainstorm and constitution sessions too, and
  `:32` puts an approval gate on every conversation, research questions included. The Tell's "a
  chat-tool project's system prompt" names this file's case.
- **RD → PA-05: found** in set scope (audit.md § Scopes, a chat-tool project's instructions with the
  templates pasted into it; step 4): `:31` restates `brainstorm-prompt.md:17`, `prd-prompt.md:42` and
  `constitution-prompt.md:22`; `:32` restates `brainstorm-prompt.md:23`, `prd-prompt.md:22` and
  `constitution-prompt.md:28`; `:33` restates `prd-prompt.md:11,26`; `:34` restates
  `brainstorm-prompt.md:22`. PA-05 loads for every kind, so this did not depend on the kind. Audited
  single, as the corpus table scopes it, the restatement stays out of reach: PA-05's Tell is one prompt.

Item 5 stays 2/2, now under either kind. Recall is unchanged: 43/49 (87.8%), 43/45 (95.6%).
