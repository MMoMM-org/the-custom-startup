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
