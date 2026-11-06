---
title: "prompt-author: write, audit, port and measure LLM prompts beyond skills and agents"
status: approved
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

---

## Product Overview

### Vision
Every LLM prompt in a TCS repository, whether skill, subagent brief, API system prompt, instruction file or a template for another vendor's model, is written and checked against one shared, evidence-graded failure catalog, and every change to a prompt can be measured on its target before it ships.

### Problem Statement
Prompt quality failures that skill-author and agent-author already fix for skills and agents recur in every other prompt the repo contains, and nothing checks those prompts today.

Evidence (research-corpus.md, experiment/results.md):
- **16 real prompts audited, every one with at least one failure.** Emphasis/caps in 8, in-file contradictions in 6, prompts assuming context the reader does not have in 6, redundant restatement in 5, stale facts in instruction files in 3.
- **Contract gaps fail every run.** The repo's implementer brief and review brief never request the output the orchestrator parses (#250, #251). In the experiment both scored **0%** on that contract across all runs. Any explicit authoring by Opus or Sonnet scored 97–100%.
- **The authoring rules contradict current vendor guidance.** The rules the repo does have are partly wrong:
  - "Strip rationale" is stated five times in skill-author and agent-author. Anthropic, OpenAI and Google all recommend giving the reason.
  - "YOU MUST / No exceptions" is recommended for discipline skills. Anthropic and OpenAI name such language as a cause of overtriggering.
  - "One excellent example beats five" contradicts the vendors' 3–5 diverse examples.
- **The rules exist as copies.** The description rule is stated 8 times and the purity rule 5 times across skills, with no sync check. A correction has to be made in every copy or the copies drift.
- **Porting has no guidance.** For prompts sent to a non-Claude model the repo has no porting guidance, and three cross-environment templates carry Claude Code idioms into other tools (#3/#4 in the corpus). In the experiment's port to a small local model, no prompt authored by Opus or Sonnet beat the existing prompt (best 43% vs 50%). Both failure modes were rules the small model followed too literally.
- **Instruction files are stale.** AGENTS.md is stale against the tree (#252). A prompt in code interpolates untrusted session text without delimiters (#253).

Consequence of not solving: the same defects keep being written. The user's assumption that the problem is Opus, and that switching the authoring model would fix it, does not hold. The experiment found no measurable Opus-vs-Sonnet difference, so changing the model does not fix it.

### Value Proposition
- **One catalog, every prompt kind.** The rules skill-author and agent-author apply become available for every other prompt kind, so a correction is made once and reaches all consumers.
- **Evidence-graded rules.** Each rule says what it prevents and how strong its evidence is, so a rule contradicted by vendor guidance or by measurement gets corrected instead of copied.
- **The contract the caller depends on comes first.** The experiment shows this is what decides agentic prompts; length and polish do not.
- **Measurement instead of judgement.** A prompt change is checked on the target model (Claude, or a local Ollama model) before it ships, or explicitly labelled "not evaluated on target".

## User Personas

### Primary Persona: Prompt author (repo maintainer working with Claude)
- **Demographics:** Solo developer/maintainer of a Claude Code plugin ecosystem. Expert in Claude Code; writes prompts mostly by directing Claude. Also writes prompts for other tools (Perplexity spaces, Claude.ai projects, ChatGPT, local Ollama models).
- **Goals:** Prompts that behave as intended on their actual target the first time, with a short reason for every non-obvious rule. Defects found before a run fails, not after. A way to tell whether a rewrite actually helped.
- **Pain Points:** Claude-written prompts look thorough but miss the one contract the caller parses. They are 3–10× longer than necessary and carry emphasis, mirrored rules and incident history. CLAUDE.md and AGENTS.md drift from the tree unnoticed. Ported templates keep Claude Code idioms. There is no cheap before/after measurement outside `plugin eval`.

### Secondary Personas

**Catalog maintainer (TCS skill maintainer).** Same person in a different role, with a distinct goal.
- **Demographics:** Maintains skill-author, agent-author, memory-claude-md-optimize and the docs in docs/about/.
- **Goals:** Change a prompting rule once and have every authoring skill apply it. Know which rules are vendor-backed, measured, practitioner opinion or unverified.
- **Pain Points:** Rules are duplicated across skills without sync. Contested rules (strip rationale, authority language) sit next to sound ones with nothing marking them. repo ADR-4 constrains one of them.

**Orchestrating agent (Claude in a workflow).** Not a human, but a real consumer.
- **Demographics:** Claude running a TCS workflow (implement, review, parallel-agents, xdd) that writes subagent briefs at runtime.
- **Goals:** Briefs that return exactly what the next workflow step branches on.
- **Pain Points:** The brief templates it fills in omit the return contract, scope fence or finding format (#250, #251). Nothing tells it what a good brief must contain.

## User Journey Maps

### Primary User Journey: Write a new prompt for a named target
1. **Awareness:** The author needs a prompt outside skills/agents: an API system prompt, a subagent brief inside a skill, a chat template for another tool, a prompt string in code, or an AGENTS.md/GEMINI.md.
2. **Consideration:** Alternatives are writing it ad hoc with Claude (status quo), skill-author/agent-author (wrong scope), or a vendor prompt improver (single vendor, no repo rules).
3. **Adoption:** The author invokes prompt-author, or is nudged to it when writing a file of a known prompt kind.
4. **Usage:** The skill asks for kind, target model, consumer, and what the consumer does with the output. It drafts the output contract first and the rest against the catalog. It runs the lint, then offers an eval kit and a local run.
5. **Retention:** The prompt passes its eval on the first run more often than ad hoc prompts. The defect classes the author used to find by hand stop recurring.

### Secondary User Journeys

**J2: Audit an existing prompt or prompt set.**
1. The author points the skill at one prompt, a set of co-loaded files (CLAUDE.md + imports + standards), or a dispatch site plus the site that parses its result.
2. The skill lints mechanically, then reviews against the catalog. Findings carry location, catalog entry, severity and suggested fix.
3. Cross-file findings (contradictions between co-loaded files, contract asymmetry between producer and consumer) are reported as such.
4. The author accepts or rejects fixes. Accepted fixes are applied and can be measured (J4).

**J3: Port a prompt to another model or vendor.**
1. The author names the source prompt and the target: OpenAI, Google, a small local model, or a different Claude environment.
2. The skill applies the target's porting profile: placement, format, examples, negatives and emphasis. It removes idioms that only work in the source environment.
3. The ported prompt is lint-checked and evaluated on the target if the target is reachable locally. Otherwise it ships with a kit labelled "not evaluated on target".

**J4: Measure a prompt change.**
1. The author has a current and a proposed version (from J1–J3 or by hand).
2. The skill produces a case set with deterministic graders first and binary judge graders where needed. Both versions run on the same cases on the target.
3. The report states the paired difference, the per-criterion result and whether the judge criteria are validated.
4. The author decides from the measurement. When no difference is found, the shorter version is preferred.

**J5: Correct a catalog rule (catalog maintainer).**
1. The maintainer changes or adds one catalog entry, with its evidence grade.
2. Every consuming skill reads the change from the single source. A check fails if any consumer still carries a copy of the old rule.
3. If the change alters a consumer's behaviour, that consumer is measured before and after (J4). A regression reverts the change for that consumer.

**J6: Write a subagent brief at runtime (orchestrating agent).**
1. A workflow step dispatches a subagent.
2. The brief template it fills in already carries the contract entries from the catalog: return status vocabulary, finding format, scope fence, what to do when unclear, when to stop.
3. The next step parses the result without a missing-field fallback.

**Error/recovery paths** (covered in feature acceptance criteria):
- The target is not reachable, or reaching it needs a key or consent the author has not given → kit only, labelled "not evaluated on target"; never a silent substitute run.
- The lint fails internally → it reports the failure and does not block the author's write.
- The judge is not validated for a criterion → the report marks that criterion provisional.

## Feature Requirements

### Must Have Features

#### Feature 1: Shared failure catalog (single source of truth)
- **User Story:** As a catalog maintainer, I want every prompting rule stated once with its failure, fix, scope and evidence grade, so that a correction reaches every authoring skill and contested rules are visible as contested.
- **Acceptance Criteria:**
  - [ ] Given the catalog, When any entry is read, Then it states a name, the observable tell, the failure it prevents (one clause), the fix, which prompt kinds and targets it applies to, and an evidence grade from {vendor guidance, published research, measured here, practitioner, unverified} *(research added 2026-11-05)*
  - [ ] Given the research and experiment of this spec, When the catalog ships, Then it contains at least these entries:
    - the corpus modes (emphasis, contradiction in-file and cross-file, assumed absent context, redundant restatement, contract asymmetry, stale facts, port leakage, scope mismatch, history noise, long instruction list, over-prescription, missing output contract, example over-anchoring, untrusted input)
    - the experiment modes (gate without an exit; small models copying the turn shape of an example)
    - the agentic entries (stopping conditions, behaviour when unclear, goal over script, refusal with an approved alternative)
  - [ ] Given the three contradicted rules (strip rationale, YOU MUST/No exceptions, one example), When they appear in the catalog, Then they are stated in corrected form:
    - one clause naming the failure a non-obvious rule prevents, with history and provenance stripped
    - no authority language, a restated terminal constraint allowed
    - 3–5 diverse examples, each behaviour also stated as a rule
    - Each corrected entry cites its vendor sources
  - [ ] Given the description authority rule (`MUST BE USED`), When it appears in the catalog, Then it is marked contested with a pointer to repo ADR-4 and its wording is unchanged
  - [ ] Given any consuming skill, When the repo's tests run, Then a test fails if that skill copies a catalog rule's fingerprint verbatim instead of referring to the catalog; paraphrased copies are removed during the migration against the research-internal.md (A) list and checked in review *(amended 2026-11-05, SDD-ADR-2 trade-off)*
  - [ ] Given the catalog, When an agent loads it, Then it is read on demand, never imported into every context (declined.md 2026-09-05)

#### Feature 2: Write mode — contract-first authoring for a named target
- **User Story:** As a prompt author, I want the skill to start from who consumes the output and what they do with it, so that the contract the caller depends on is never the part that is missing.
- **Acceptance Criteria:**
  - [ ] Given a request to write a prompt, When the skill starts, Then it establishes:
    - the prompt kind (API system prompt, subagent brief, chat template for another tool, prompt in code, non-Claude instruction file)
    - the target model or environment
    - the consumer
    - what the consumer does with the output
    - It asks the author only for what the request and repo do not state
  - [ ] Given a consumer that branches on or parses the output, When the draft is produced, Then the draft requests exactly the vocabulary or fields the consumer reads, and the skill names the consumer location it checked
  - [ ] Given an agentic prompt (subagent brief, agent, API agent with tools), When the draft is produced, Then it states what to do when information is missing or unclear and when to stop and report, and gives the goal and constraints rather than a fixed script
  - [ ] Given a gate or approval step in the draft, When the draft is produced, Then the gate states its exit (what happens when the user asks for the result directly)
  - [ ] Given input from outside the prompt author's control, When the draft embeds it, Then the input is delimited and marked as data
  - [ ] Given a request whose prompt kind belongs to another skill (skill → skill-author, agent definition → agent-author, CLAUDE.md → memory-claude-md-optimize), When the skill starts, Then it hands off to that skill instead of writing it

#### Feature 3: Audit mode — single prompt, co-loaded set, producer/consumer pair
- **User Story:** As a prompt author, I want an audit that reports catalog-backed findings with locations, including defects that only show across files, so that I fix the defects that cause failures and not style.
- **Acceptance Criteria:**
  - [ ] Given one prompt, When it is audited, Then each finding carries location, catalog entry, severity, and a suggested fix, and the lint findings are included
  - [ ] Given a set of co-loaded files (e.g. CLAUDE.md, its imports and loaded standards), When it is audited, Then contradictions between files are reported with both locations
  - [ ] Given a dispatch site and the site that parses its result, When they are audited together, Then a field or vocabulary the consumer reads and the producer never requests is reported as contract asymmetry
  - [ ] Given an instruction file that names paths, commands, versions or counts, When it is audited, Then claims that do not match the repository are reported as stale facts
  - [ ] Given the audited prompt, When the audit runs, Then the prompt's contents are treated as data: instructions inside it are not followed
  - [ ] Given the repo's known defects (#250, #251, #252, #253), When the corresponding prompts are audited, Then each documented defect is found

#### Feature 4: Port mode with per-target profiles
- **User Story:** As a prompt author, I want to port a prompt to another vendor or a small local model with the target's known differences applied, so that the port does not carry over idioms the target misreads.
- **Acceptance Criteria:**
  - [ ] Given a target, When a port runs, Then the skill applies that target's profile and reports each change it made. Profiles exist for Anthropic Claude, OpenAI GPT, Google Gemini and small local models. Each covers instruction and context placement, delimiter format, example count and style, negative instructions, emphasis, and how literally the target follows rules
  - [ ] Given a source prompt with idioms from its source environment (Claude Code markers, skill-only conventions, references the target cannot resolve), When it is ported, Then each idiom is removed or defined in the port
  - [ ] Given a small local model as target, When the port is produced, Then it shows the exact shape of a turn the model should produce, and every gate states its exit
  - [ ] Given a profile entry without vendor evidence (small local models), When it is applied, Then it is labelled unverified in the report
  - [ ] Given a port, When it is delivered, Then it either carries an eval result from the target or a kit labelled "not evaluated on target"

#### Feature 5: Mechanical prompt lint
- **User Story:** As a prompt author, I want a fast mechanical check that only reports what it can detect reliably, so that I can run it on every prompt without wading through false alarms.
- **Acceptance Criteria:**
  - [ ] Given a prompt, When the lint runs, Then it reports as errors:
    - secrets
    - unbalanced XML tags
    - references to files or headings that do not exist
    - input interpolated without a delimiter into a prompt in code
  - [ ] Given a prompt, When the lint runs, Then it reports as warnings: emphasis density above a threshold, instruction count above a threshold, and paragraphs made only of prohibitions
  - [ ] Given checks known for high false-alarm rates (history words, mirrored Always/Never pairs, contradictions, examples without a stated rule), When they are needed, Then they are routed to review or the judge, not reported by the lint
  - [ ] Given the repo's current prompt files, When the lint runs on all of them, Then its errors contain no more than one false alarm, and every error-level suppression is visible in the file it applies to
  - [ ] Given frontmatter descriptions with `MUST BE USED`, When the lint runs, Then they are not flagged (repo ADR-4)
  - [ ] Given the lint fails internally, When it runs, Then it exits with a distinct code and the caller reports "lint failed" and continues; nothing is blocked *(amended 2026-11-05: no hook runs the lint)*
  - [ ] Given a file to lint, When the lint runs, Then it never executes the file's code

#### Feature 6: Eval kit and local before/after run
- **User Story:** As a prompt author, I want the skill to build a case set with graders and run two prompt versions on the target, so that I know whether a change helped before it ships.
- **Acceptance Criteria:**
  - [ ] Given a prompt and its intended behaviour, When an eval kit is created, Then it contains:
    - cases that include the prompt's known failure modes
    - one prompt-injection case if the prompt handles untrusted input
    - deterministic graders wherever a criterion is checkable without a model
    - binary PASS/FAIL judge criteria with explicit PASS and FAIL conditions otherwise
  - [ ] Given two prompt versions and a target that is Claude or a local Ollama model, When the run executes, Then both versions run on the same cases, and the report gives the per-criterion pass rate per version, the paired difference with its uncertainty, and the cost
  - [ ] Given judge criteria, When they are used, Then the judge is neither the author model nor the target model, the graded output is marked as material, and the report marks each judge criterion validated or provisional
  - [ ] Given a judge criterion to validate, When the author labels a blinded sample of outputs, Then agreement is computed and a criterion below 85% is reported as not validated
  - [ ] Given a target that needs a key or an external provider, When an eval is requested, Then nothing is sent without explicit per-run consent naming the provider, and without consent the kit is delivered labelled "not evaluated on target". A Claude run is never substituted silently
  - [ ] Given any run, When it executes, Then it has a cost ceiling, no report is published externally, keys never appear in output, and results go to session-local scratch space, not the repository
  - [ ] Given a paired difference whose uncertainty interval includes zero, When the report is written, Then it says "no measurable difference" rather than declaring a winner

#### Feature 7: Migration of the existing authoring skills to the catalog, with measured corrections
- **User Story:** As a catalog maintainer, I want skill-author, agent-author and memory-claude-md-optimize to use the shared catalog with the corrected rules, and each correction measured, so that the corrections improve the skills and a regression is caught.
- **Acceptance Criteria:**
  - [ ] Given the three skills, When the migration is complete, Then each cites the catalog for every rule it shares, with at most a one-line operational rule; reasons and evidence stay in the catalog *(amended 2026-11-07, Phase 3 drift check: a bare PA link left the operational rule out of reach on paths that never open the catalog)*
  - [ ] Given each skill, When a corrected rule changes its guidance, Then the skill's eval runs before and after the change, and a drop beyond noise reverts the correction for that skill and records why
  - [ ] Given memory-claude-md-optimize's scoring, When it is migrated, Then it no longer rewards a generic architecture overview, only content the README and code do not already give
  - [ ] Given agent-author, When it is migrated, Then it gains the agentic entries (stopping conditions, behaviour when unclear, goal over script, refusal with alternative) through the catalog
  - [ ] Given the description authority rule, When the migration is complete, Then `MUST BE USED` guidance in agent-author is unchanged

### Should Have Features

#### Feature 8: Cut test for authored prompts
- **User Story:** As a prompt author, I want the skill to report a draft's size against the version it replaces and to keep only additions with a stated purpose, so that prompts do not grow 3–10× without measured benefit.
- **Acceptance Criteria:**
  - [ ] Given a draft that replaces an existing prompt, When it is delivered, Then the report states both sizes, and each added section names the failure it prevents
  - [ ] Given two versions with no measurable difference in an eval, When the skill recommends one, Then it recommends the shorter

#### Feature 9: Write-time nudge for known prompt kinds
- **User Story:** As a prompt author, I want a reminder when I write a file of a known prompt kind, so that I use prompt-author without having to remember it.
- **Acceptance Criteria:**
  - [ ] Given a write to an AGENTS.md, GEMINI.md, `*.prompt.md` or a `prompts/` file, When the write completes, Then a one-line reminder names prompt-author, and it does not block the write
  - [ ] Given a write to a SKILL.md or agent file, When the write completes, Then the existing reminders keep naming their own skills; CLAUDE.md gets no reminder *(amended 2026-11-05: no CLAUDE.md reminder exists)*

### Could Have Features

- **Feature 10: Prompt discovery in TypeScript code.** Find system prompts in template literals, warn-only, with misses stated.
- **Feature 11: Pairwise judging in both orders.** For comparisons where a binary criterion cannot express the difference.
- **Feature 12: Brief template audit for all workflow skills.** Run the audit over every brief in tcs-workflow and report one list.

### Won't Have (This Phase)

- **No change to `MUST BE USED` or repo ADR-4.** Changing it needs its own measured trigger/overtrigger study and a superseding ADR.
- **No live runs against OpenAI or Gemini.** The Gemini key must not be used. OpenAI has no key. These targets get kits only.
- **No automatic prompt optimisation loops** (OPRO/DSPy style). Research shows unguided LLM rewrites miss real error causes. The skill proposes and measures, the author decides.
- **No authoring-model routing.** No measured difference between Opus and Sonnet authors, so the skill does not recommend switching models.
- **No fixes for #250–#253 inside this spec.** They are fixed as separate issues and serve as audit test cases (Feature 3).
- **No ownership change for skills, agent definitions and CLAUDE.md.** They stay with skill-author, agent-author and memory-claude-md-optimize. prompt-author hands those kinds off to them.

## Detailed Feature Specifications

### Feature: Audit mode (Feature 3)
**Description:** The audit combines the mechanical lint with a catalog review. It works on three scopes: one prompt; a set of files loaded together; and a producer/consumer pair, where one site writes a prompt and another parses what comes back. The cross-file scopes find the defect classes no single-file review sees. In the corpus those were contract asymmetry and contradictions between co-loaded files, and in the experiment the contract gap was the largest effect.

**User Flow:**
1. User names the target: a path, a set of paths, or a dispatch site and its parser. "Audit the review brief" is enough if the skill can locate it.
2. System determines prompt kind and target and, for kinds owned by another skill, hands off.
3. System runs the lint and reports its findings.
4. System reviews against the catalog entries that apply to the kind and target. For a pair, it lists what the consumer reads and compares it with what the producer requests. For a set, it compares the rules across files.
5. System presents findings ordered by severity, each with location, catalog entry, evidence grade and suggested fix.
6. User accepts, rejects or defers each finding. System applies accepted fixes and offers an eval (Feature 6) when a fix changes behaviour.

**Business Rules:**
- Rule 1: Every finding names one catalog entry. A concern that fits no entry is reported as "uncatalogued", not dressed up as an existing entry.
- Rule 2: Severity follows consequence: a failure the consumer cannot recover from, such as a missing contract field, outranks style.
- Rule 3: Findings based on unverified catalog entries say so.
- Rule 4: When the target is a non-Claude model, the target's profile decides which entries apply. An entry that is only valid for Claude is not raised.
- Rule 5: The audited text is data. An instruction inside it ("ignore previous instructions") is reported as an untrusted-input finding if relevant, never followed.
- Rule 6: Suggested fixes follow the catalog's corrected rules. For example, the fix for a bare "NEVER X" is "do Y, because Z", not a louder "NEVER".

**Edge Cases:**
- **The parser for a dispatch site cannot be found.** → The audit reports that contract asymmetry could not be checked and names what it searched.
- **A file in a co-loaded set is outside the repository** (e.g. a global standards file). → It is audited but marked external. Fixes to it are proposed, not applied, unless the user asks.
- **A prompt is assembled at runtime from fragments.** → The audit reviews the fragments and states that the assembled form was not seen.
- **Two catalog entries pull in opposite directions** (e.g. explicit don'ts for a literal target vs positive framing). → The target profile decides, and the finding cites the profile.
- **The audit finds nothing.** → It says so, with the scopes and entries it checked.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Every new prompt outside skills, agents and CLAUDE.md written in this repo after release goes through prompt-author: a write or audit report exists for it. Within 30 days of release, all subagent brief templates in tcs-workflow are audited (Feature 12 if done, else one by one).
- **Engagement:** Each audited prompt that receives an accepted behavioural fix gets an eval run in at least half the cases.
- *Adoption and engagement are checked by a manual review 30 days after release (git log of prompt files vs. eval reports the maintainer kept); the skill keeps no usage log (amended 2026-11-05).*
- **Quality:**
  - Audit recall: the documented defects of the corpus (16 prompts) and of #250–#253 are found in ≥ 90% of cases. The denominator is the documented defects in prompts of the kinds prompt-author keeps; defects in the handed-off kinds (agent definitions, skills, CLAUDE.md) are measured by their owner skill (amended 2026-11-05, phase 2 drift).
  - Lint precision: ≤ 1 false-alarm error across the repo's prompt files.
  - Contract coverage: briefs written with the skill pass a T2/T3-style contract eval at ≥ 95%, against 0% for the status quo.
  - No regression beyond noise in the evals of the three migrated skills.
- **Business Impact:**
  - Zero duplicated copies of catalog rules across the authoring skills (test-enforced).
  - The three contradicted rules are corrected or reverted with a recorded measurement.
  - Prompts in the repo stop gaining length without a stated purpose (Feature 8 report).

### Tracking Requirements

No runtime telemetry. All tracking comes from artefacts the skill and tests produce.

| Event | Properties | Purpose |
|-------|------------|---------|
| Audit completed | prompt kind, target, scope (single/set/pair), findings per catalog entry and severity, accepted/rejected/deferred counts | Audit recall vs known defects; which entries fire; adoption |
| Lint run | file, errors and warnings per check, suppressions | Lint precision; false-alarm tracking |
| Eval run | versions compared, target, cases, per-criterion pass rates, paired difference, cost, judge validation state | Contract coverage; regression check for migrated skills; engagement |
| Port completed | source/target, profile changes applied, evaluated on target or kit only | Port coverage; how often targets are unreachable |
| Catalog consistency test | consumers checked, duplicate rule copies found | Single-source KPI |
| Migration measurement | skill, rule corrected, before/after eval result, kept or reverted | Rule-correction KPI |

---

## Constraints and Assumptions

### Constraints
- Plugins ship shell plus Python standard library only; no third-party packages.
- **Eval cases use the repo's accepted formats** (`case.yaml`, or `prompt.md` with `graders/`). `evals.json` was declined.
- `plugin eval` always runs with `--no-publish` and a cost ceiling; its default publishes reports, including prompts, to claude.ai.
- The Gemini key must not be used. Live targets are Claude via the local CLI and Ollama on the host. Every external send needs per-run consent naming the provider.
- The shared catalog is never `@`-imported into every context (declined 2026-09-05).
- repo ADR-4 holds: `MUST BE USED` in descriptions is not changed.
- A new plugin skill ships with at least one eval shown to fail without it (skill-author Iron Law).
- **Local testing copies single skill directories.** A shared catalog outside one skill directory must still work under local testing and after marketplace install. How is SDD scope; that it works is a requirement.
- Bash 3.2 and BSD/GNU differences apply to any shell part (active.md).

### Assumptions
- **The maintainer is the main human user.** Other TCS users benefit through the corrected authoring skills.
- **Ollama stays reachable** on the host for local small-model evaluation. Without it, small-model targets get kits only.
- The current vendor guidance (Anthropic, OpenAI, Google, fetched 2026-11-04) is representative for the next model generation. Profiles carry their source date so they can be rechecked.
- **One labeller is enough** to validate judge criteria at this scale, with the validation state shown in every report.
- **`plugin eval` can measure the migrated skills before and after.** Its condition was met (declined.md); the exact comparison mechanics are SDD scope.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A corrected rule (rationale clause, no authority language) makes a discipline skill less compliant | High | Medium | Feature 7 measures each correction per skill and reverts on regression. Repeating a terminal constraint stays allowed |
| The catalog itself grows into a long instruction list, the failure it warns about | Medium | High | Entries are loaded per kind and target, not all at once; each entry is one tell, one clause, one fix; the cut test applies to the catalog too |
| The LLM judge is miscalibrated while passing its hand-built controls (happened: T1 judge 3/10) | High | Medium | Feature 6 requires label-based validation and marks unvalidated criteria provisional; deterministic graders are preferred |
| Overlap with skill-author is seen as redundant (skill-evaluate U1) | Medium | Medium | Explicit hand-off for kinds owned by other skills; prompt-author covers only kinds outside skill-author's scope; the overlap argument is recorded in the SDD |
| A shared reference breaks after marketplace install or under local testing | High | Medium | Stated as a constraint; verified in a real install before release |
| Authored prompts follow rules too literally on small models (gates without exit, copied turn shapes) | Medium | High (measured) | Catalog entries plus the small-model profile; port mode always evaluates on Ollama when reachable |
| Eval runs leak prompts or keys (published report, telemetry, logs) | High | Low | Constraints above; secret scan before sending; no-publish enforced; results in session scratch space |
| Porting profiles go stale as vendors change guidance | Medium | Medium | Each profile entry carries source and date; unverified entries are labelled |

## Open Questions

- [x] Lint scope → low-false-alarm checks are errors, the others are warnings or go to review (user, 2026-11-05)
- [x] Eval scope → kit plus local runs on Claude and Ollama; other vendors kit only (user, 2026-11-05)
- [x] Rule corrections → applied during migration, measured per skill, reverted on regression (user, 2026-11-05)
- [x] Should the skill recommend an authoring model? → No; no measured difference (experiment/results.md)
- [x] Who owns CLAUDE.md? → memory-claude-md-optimize, using the catalog; prompt-author hands off (this PRD, Won't Have)

No open questions remain for the PRD. These are deferred to the SDD: where the catalog lives and how consumers reference it; the lint thresholds; the comparison mechanics for `plugin eval`.

---

## Supporting Research

### Competitive Analysis
- **Vendor prompt improvers** (Anthropic prompt improver, OpenAI prompt optimizer):
  - Each works for one vendor only and knows no repo rules.
  - The figures are self-reported (+30% on one Claude 3 Haiku task).
  - OpenAI's dataset-backed mode is being shut down (read-only 2026-10-31, off 2026-11-30).
- **Automatic optimisation** (APE, OPRO, DSPy): needs a metric and a dataset. "Are LLMs Good Prompt Optimizers?" (arXiv 2402.02101) finds unguided rewrites miss real error causes. Lesson: propose and measure, do not auto-optimise.
- **Vendor guidance converges** on giving reasons, soft language, diverse examples and delimiters. It diverges on placement in long contexts, format (OpenAI: JSON poor) and negatives (OpenAI 4.1 literalism). This divergence is why per-target profiles exist (research-external.md §1).
- **Instruction-file studies:** ETH's AGENTS.md study (arXiv 2602.11988) found that LLM-generated instruction files slightly hurt and overviews do not help, while tooling instructions are followed. That supports "include only what the README lacks" and the stale-fact check.

### User Research
- **Corpus audit of 16 real prompts** in and around the repo (research-corpus.md). Failure frequency table; seven new failure modes (redundant restatement, contract asymmetry, stale facts, port leakage, scope mismatch, cross-file contradiction, verdict prior). The good prompts state one-clause reasons, calibrate what is not an issue, and use fixed output schemas.
- **Opus-vs-Sonnet authoring experiment** (experiment/results.md): 5 tasks, 3 authorings per model, 385 target runs, $7.97.
  - No measurable model difference.
  - Explicit authoring fixes missing contracts (T2/T3: status quo 0% vs 97–100%).
  - Authored prompts are 3–10× longer without gain where the status quo already had the contract.
  - Small-model port: no authored prompt beat the status quo; both models' prompts failed through rules followed too literally.
  - Judge validation: one of three semantic criteria was invalid despite passing hand-built controls.
- **Internal rule inventory** (research-internal.md): where each existing rule lives, how often it is copied, and which rules vendor guidance contradicts.
- **Practitioner input on agent prompts** (Gravity blog, user-supplied): stopping conditions, behaviour when unclear, goal over script, refusal with an alternative. These are adopted as catalog entries graded "practitioner".

### Market Data
Not applicable for an internal tooling skill. Relevant external numbers:
- **IFScale** (arXiv 2507.11538): instruction-following decays with instruction count; the best model reaches ~68% at 500 instructions; small models decay exponentially.
- **Spotlighting** (arXiv 2403.14720): marking where content came from cut prompt-injection success from >50% to <2%.
- **Formatting fragility** (arXiv 2310.11324): changing a prompt's format without changing its meaning moved accuracy by up to 76 points.
