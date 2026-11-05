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
- The earlier 0.67 for port-gate-exit was a skipped llm grader under a $5 suite ceiling; at $4 for
  the case alone every run was judged and scored 1.00.

## Cost

The prompt-author suite at 3 runs per arm costs about $7.40 (with plugin about $2.05 per round of four
cases, without about $0.41) and takes about 6 minutes with `-j 4`. Set `--max-cost-usd` to 10: the
ceiling is checked before each run launches, so at 8 the last port-gate-exit runs can be cut off and
their llm grader skipped. T2.4/T2.5 spent $9.04 before this round; the redesign and proving-signal
round spent $10.81.
