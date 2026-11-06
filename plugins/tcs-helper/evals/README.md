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
