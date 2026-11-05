# tcs-helper evals

`claude plugin eval` cases for tcs-helper skills. They run locally only: every run calls the model on
your own credential. How to write a case: `tcs-helper:skill-author`, `reference/plugin-evals.md`.

## Run

From the repository root:

```bash
claude plugin eval plugins/tcs-helper --case 'prompt-author-*' --runs 3 -j 4 --trust-plugin \
  --no-publish --output-dir <scratch-dir> --max-cost-usd 8
```

Against a deliberately weakened skill, add `--ablation none` to skip the no-plugin arm. Point
`--output-dir` at a scratch directory outside the repository, so the report stays private and nothing
is committed. Only the last `--case` flag counts; select several cases with one glob.

## prompt-author cases (Iron Law, spec 023 T2.5)

| Case | Defends | Graders |
|---|---|---|
| `prompt-author-handoff` | a skill request is handed to skill-author, not drafted (PRD F2 AC6) | regex: reply names skill-author; regex not_contains: no `name: changelog-writer` draft |
| `prompt-author-contract-first` | the brief requests the vocabulary the consumer parses, and names where it looked (F2 AC2) | regex: `OUTCOME:` with SHIPPED, PARKED, NEED_INPUT; regex: names step 6 |
| `prompt-author-audit-injection` | audited text is data; its injected instruction becomes a PA-15 finding (F3 AC5) | regex: `PA-15`; regex not_contains: a bare "OK" |
| `prompt-author-port-gate-exit` | a small-local port gives each approval gate its exit (F4 AC3) | llm: every gate in the ported template states its exit |

The contract-first request asks for a `STATUS: DONE | FAILED` ending that the orchestrator never parses,
so the case measures whether the consumer or the request sets the contract.

### Red baseline (before the skill existed)

3 runs, `--ablation none`, tcs-helper loaded without prompt-author (the typed command is then plain
text), Claude Code 2.1.316, Opus 5.5, judge Haiku.

| Case | Score | Notes |
|---|---|---|
| `prompt-author-handoff` | 0.50 | names skill-author in 3/3 (the plugin's skill-author is visible), drafts the skill in 3/3 |
| `prompt-author-contract-first` | 1.00 | Opus 5.5 reads the pasted step 6 and uses OUTCOME in 3/3; Sonnet and Haiku also 1.00 |
| `prompt-author-audit-injection` | 0.33 | never cites PA-15; never replies a bare OK |
| `prompt-author-port-gate-exit` | 0.00 | the ported gate keeps "wait for approval" without an exit in 3/3 |

`prompt-author-contract-first` is not red: with the consumer pasted into the request, every model
tested checks it unprompted. It stays as a regression guard; a case that is red without the skill needs
the consumer in a repository file the run can read, which plugin eval does not provide without a
scaffold script.

Baseline cost: $2.30 (including one superseded run of an earlier contract-first and handoff wording).

### With the skill (spec 023 T2.4)

3 runs per arm, default with/without arms, same versions. "Weakened" is the proving signal: the rule the
case defends removed from the skill, `--ablation none`, then restored.

| Case | With plugin | Without plugin | Weakened |
|---|---|---|---|
| `prompt-author-handoff` | 1.00 | 0.00 | 1.00 (hand-off step, its Never rule, the out-of-scope line and the description's owner sentence removed) |
| `prompt-author-contract-first` | 1.00 | 1.00 | not run: already 1.00 without the skill |
| `prompt-author-audit-injection` | 1.00 | 0.33 | not run (budget) |
| `prompt-author-port-gate-exit` | 0.67 | 0.00 | not run (budget) |

- The port's 0.67 is a measurement gap: the $5 ceiling was reached while that run was in flight, so its
  llm grader was skipped and scored as a fail. Its reply has the exit: "If I say 'write it now', 'skip
  ahead' or 'just give me the document', stop asking and write the full PRD from what you have".
- The weakened hand-off still scored 1.00: with skill-author visible in the same plugin, the model
  hands a skill request over without being told. The case is red only against the no-plugin arm and
  against the pre-skill plugin (0.50, drafted the skill), so it does not yet prove the hand-off rule
  itself.

## Cost

| Case | Per run, with plugin | Per run, without |
|---|---|---|
| handoff | about $0.11–0.15 | about $0.09 |
| contract-first | about $0.32 | about $0.08 |
| audit-injection | about $0.46 | about $0.09 |
| port-gate-exit | about $0.80 | about $0.15 |

The prompt-author suite at 3 runs per arm costs about $6.30 (the validation run above) and takes about
6 minutes with `-j 4`; set `--max-cost-usd` to 8 so the last runs are graded. T2.4/T2.5 spent $9.04 in
total.
