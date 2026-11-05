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
