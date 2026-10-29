---
title: "Model-tier classification and a frontier rung for implement"
status: draft
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
A specification says how hard its work is, and the implement workflow runs each task on the
cheapest model that can do it, climbs to a stronger one only on evidence, and never spends money
outside the user's plan without the user having agreed to it.

### Problem Statement
TCS already picks models, but without a plan behind the choice:

1. **Nothing measures depth.** The xdd classifier's five signals (`change_type`, `feature_count`,
   `ac_count`, `component_count`, `parallel_markers`) measure breadth, which decides decomposition.
   Which model a task needs depends on uncertainty, novelty and how long the work runs, and nothing
   records that.
2. **"Stronger model" is undefined.** `implement-incremental` step 4e says "re-dispatch with
   upgraded model" and `implement-direct` says "re-dispatch with a stronger model", but neither
   names the rungs. The ladder in step 4b stops at `opus`, and `implement-direct` has no initial
   model choice at all.
3. **The frontier model costs real money.** Fable 5.1 costs $10/$50 per million input/output
   tokens against Opus 5.5's $4/$20, 2.5 times as much. Depending on plan and seat, it bills usage
   credits instead of plan limits. In `claude -p` and SDK sessions Claude Code bills it without
   asking. A workflow that escalates on its own can therefore spend money outside the plan
   without anyone noticing.
4. **Fable may not be there.** An account may not be entitled, may not have consented to usage
   credits, or the model may be overloaded. Today nothing in TCS would notice, and a task could
   run on a weaker model while the spec claims otherwise.

Consequence of not solving it: the hardest tasks either never get the frontier model, or they
get it silently and at the user's cost.

### Value Proposition
- The spec carries the expected difficulty, so the implement run that follows does not have to
  guess it again.
- Effort comes before model: Opus at maximum effort is tried before Fable, at less than half the
  price.
- Spending outside the plan is always a decision the user made, with the cost in front of them.
- A spec stays executable on a machine without Fable, and its record says what actually ran.

## User Personas

### Primary Persona: The TCS maintainer
- **Demographics:** Solo developer who maintains the TCS plugins and drives `/xdd` and
  `/implement` interactively in Claude Code; expert with the workflow and its cost model.
- **Goals:** Hard specs get a model that can carry them; routine work stays cheap; every model
  choice can be traced afterwards.
- **Pain Points:** Escalation today is ad hoc ("stronger model" with no ladder); Fable can only be
  chosen by hand; nothing records which model did a task.

### Secondary Personas
- **The TCS adopter without Fable:** Uses TCS in another repository on a plan or account that
  does not offer Fable, or has not consented to usage credits. Needs every spec, including one
  classified `frontier`, to run end to end on what the account offers, with no errors and no
  surprise charges.

## User Journey Maps

### Primary User Journey: Classifying and implementing a hard spec
1. **Awareness:** After writing PRD and SDD, the maintainer reaches the decomposition step of
   `/xdd`.
2. **Consideration:** The classifier shows the decomposition tier and the model tier with the
   signals behind each, and, for `frontier`, one sentence on what Fable costs and how it bills.
3. **Adoption:** The maintainer confirms or overrides both tiers in the same question.
4. **Usage:** `/implement` dispatches each task at the rung its tier and any `[model: …]` tag
   call for. A task that reports a complexity block, or fails review twice in a row, is re-dispatched one
   rung higher, automatically up to Opus at maximum effort. Before any escalation to Fable the
   maintainer is asked.
5. **Retention:** The spec's Decisions Log shows the tier, every escalation and every
   substitution, so the next spec's classification can be checked against what happened.

### Secondary User Journeys
- **Running without Fable (adopter):** The adopter implements a spec classified `frontier`. Fable
  is unavailable, so each frontier task runs on the best rung available, and the Decisions Log
  records the substitution. The run completes.
- **Unattended run (maintainer):** The maintainer runs `/implement` in YOLO mode or `claude -p`.
  No one can be asked, so escalation stops at Opus at maximum effort, and a task that still
  fails is reported as blocked instead of being sent to Fable.
- **Legacy spec (both personas):** A spec written before this feature has no model tier.
  `/implement` selects models exactly as today. Only an escalation, when one happens, follows the
  ladder.

## Feature Requirements

### Must Have Features

#### Feature 1: Model-tier classification
- **User Story:** As the TCS maintainer, I want the xdd classifier to recommend a model tier
  (`routine`, `hard` or `frontier`) next to the decomposition tier, so that the spec states how
  demanding its work is before implementation starts.
- **Acceptance Criteria:**
  - [ ] **AC-1.1** Given a spec with `requirements.md` and `solution.md`, When the decomposition step runs, Then the classifier recommends exactly one model tier and names the signals that produced it, read from those two documents only
  - [ ] **AC-1.2** Given the decomposition step, When the user is asked to confirm, Then both tiers are confirmed in one question round, and the step asks nothing else
  - [ ] **AC-1.3** Given the confirmation question, When it is shown, Then the `frontier` option carries one sentence on Fable's cost relative to Opus and that it can bill usage credits
  - [ ] **AC-1.4** Given a signal that cannot be determined from the documents, When the classifier runs, Then it takes the value that lowers the tier and names it in the rationale
  - [ ] **AC-1.5** Given the user picks a tier other than the recommendation, When it is recorded, Then the override is logged with the user's free-text reason, or "no reason given" when there is none

#### Feature 2: Model tier recorded in the spec
- **User Story:** As the TCS maintainer, I want the confirmed model tier recorded where tools can
  read it, so that `/implement` uses it without asking again.
- **Acceptance Criteria:**
  - [ ] **AC-2.1** Given a confirmed model tier, When it is recorded, Then the spec README Status table has a `Model tier` row and the Decisions Log has a row with recommendation, choice and rationale
  - [ ] **AC-2.2** Given a spec with a `Model tier` row, When its metadata is read, Then the model tier is reported alongside the decomposition tier
  - [ ] **AC-2.3** Given a spec with no `Model tier` row, a placeholder or an unknown value, When its metadata is read, Then the model tier reads as absent without error, and every existing spec still reads cleanly

#### Feature 3: Per-task model override
- **User Story:** As the TCS maintainer, I want to tag a single plan task `[model: routine|hard|frontier]`,
  so that one hard task in an otherwise routine spec gets the right rung, and the reverse.
- **Acceptance Criteria:**
  - [ ] **AC-3.1** Given a plan task with a `[model: …]` tag, When the task is dispatched, Then its tier comes from the tag instead of the spec's model tier
  - [ ] **AC-3.2** Given a plan task with an unknown `[model: …]` value, When it is dispatched, Then the spec's tier applies and the unknown value is reported
  - [ ] **AC-3.3** Given a task tagged `[model: frontier]` in a spec whose tier is not `frontier`, When it is about to be dispatched, Then the user is asked first, with the same cost sentence as Feature 1; a consented task counts as planned, and the task runs at the `hard` rung when the user declines or no one can be asked

#### Feature 4: A defined model ladder used by both implement tiers
- **User Story:** As the TCS maintainer, I want one named ladder, haiku → sonnet → opus →
  opus at maximum effort → fable, so that "stronger model" means the same thing everywhere.
- **Acceptance Criteria:**
  - [ ] **AC-4.1** Given a `routine` task, When it is dispatched, Then the rung is chosen as step 4b chooses it today
  - [ ] **AC-4.2** Given a `hard` task, When it is dispatched, Then it starts no lower than opus
  - [ ] **AC-4.3** Given a `frontier` task in a spec whose `frontier` tier the user confirmed, When it is dispatched, Then it starts on fable
  - [ ] **AC-4.4** Given a Direct-tier spec, When `/implement` dispatches its work, Then it applies the same ladder and tier mapping as an Incremental spec
  - [ ] **AC-4.5** Given a spec with no model tier, When it is implemented, Then model selection is identical to today's

#### Feature 5: Escalation on evidence, Fable only with consent
- **User Story:** As the TCS maintainer, I want a task to climb the ladder only when it has shown it
  needs to, and to reach Fable only when I agree, so that cost follows evidence and I keep control
  of spending outside my plan.
- **Acceptance Criteria:**
  - [ ] **AC-5.1** Given a task that reports a complexity block, or fails spec-compliance or code-quality review twice in a row at the same rung, When it is re-dispatched, Then it moves up exactly one rung and its failure count starts again
  - [ ] **AC-5.2** Given the next rung is at most opus at maximum effort, When escalation triggers, Then it happens without asking
  - [ ] **AC-5.3** Given the next rung is fable, When escalation triggers in an interactive session, Then the user is asked, with the cost sentence, before any dispatch
  - [ ] **AC-5.4** Given the next rung is fable, When no one can be asked (YOLO or a non-interactive session), Then the task is not sent to fable and is reported as blocked at opus at maximum effort
  - [ ] **AC-5.5** Given any escalation, When it happens, Then the Decisions Log records the task, the reason, and the rung before and after
  - [ ] **AC-5.6** Given a task blocked for a reason other than complexity (missing context, too large, wrong plan), When it is handled, Then no escalation happens
  - [ ] **AC-5.7** Given a task at the highest rung it may reach, When it fails review twice in a row or reports a complexity block, Then it is reported blocked to the user instead of being retried

#### Feature 6: Fable is never a hard dependency
- **User Story:** As the TCS adopter without Fable, I want a `frontier` spec to run on what my
  account offers, so that a classification never stops my workflow.
- **Acceptance Criteria:**
  - [ ] **AC-6.1** Given a planned frontier task whose fable dispatch fails because Fable is unavailable or refused, When the task is handled, Then it is re-dispatched on opus at maximum effort, and the run continues
  - [ ] **AC-6.2** Given such a substitution, When it happens, Then the Decisions Log records the requested rung, the rung that ran, and the reason
  - [ ] **AC-6.3** Given a spec classified `frontier`, When it is read on a machine without Fable, Then nothing in the workflow refuses to start
  - [ ] **AC-6.4** Given an escalated task whose fable dispatch fails, or whose Claude Code consent prompt is dismissed, When the task is handled, Then it is reported blocked, and fable is not tried again for the rest of the run

### Should Have Features
- **Verify the rung that actually ran.** After each dispatch, record the model that actually
  served the task. This also covers silent substitutions (an allowlist or overload fallback) that
  do not fail the dispatch. The spike confirmed the served model is observable: `message.model`
  in the subagent transcript.

### Could Have Features
- **Main-session hint.** When a spec is classified `frontier`, the completion summary of `/xdd`
  suggests `/model fable` for the main session that will orchestrate `/implement`. It is a hint
  only; TCS cannot set the main session's model.

### Won't Have (This Phase)
- Setting the main session's model. Only the user can do that, with `/model` or at startup.
- Sending a task to Fable without a person's consent, in any mode.
- Cost budgets, spend tracking or price lookups at run time. The cost sentence is static text.
- Changing the `model:` frontmatter of existing agents (tcs-team, reviewers, tdd-guardian).
- A Factory decomposition tier, or any model tier beyond the three named.
- Escalating the reviewer agents; the ladder applies to the implementing subagent only.

## Detailed Feature Specifications

### Feature: Escalation on evidence, Fable only with consent
**Description:** Each task starts at the rung its tier maps to. A task climbs only when it has
produced evidence that its rung is too weak. Climbs within the plan's included models are
automatic. The step to Fable always needs a person.

**User Flow:**
1. System dispatches the task at its starting rung.
2. Task reports a complexity block, or fails review twice in a row at the same rung.
3. System re-dispatches one rung higher and logs the escalation.
4. If the next rung is fable, system asks the user, showing the cost sentence.
5. User agrees (task runs on fable) or declines (task is reported blocked at opus at maximum effort).

**Business Rules:**
- Rule 1: The ladder is haiku → sonnet → opus → opus at maximum effort → fable. Effort is raised before the model is changed.
- Rule 2: The tier mapping is a floor, not a ceiling. No tier: as today (step 4b in Incremental, the session's model in Direct). `routine`: step 4b in Incremental, sonnet in Direct. `hard`: opus. `frontier`: fable.
- Rule 3: Confirming a spec's `frontier` tier at classification, with the cost sentence shown, is the consent for that spec's planned frontier dispatches. Every other route to fable asks at the time.
- Rule 4: Escalation triggers only on a complexity block or two failed reviews in a row at the same rung (Rule 7). Other block reasons follow today's handling.
- Rule 5: No escalation skips a rung.
- Rule 6: When no one can be asked, fable is never dispatched by escalation. No one can be asked when YOLO is set, or when the question returns no answer (a non-interactive session).
- Rule 7: Two review failures in a row at the same rung trigger an escalation; the count starts again on the new rung. At the highest rung a task may reach, the same trigger reports it blocked, so a review loop always ends.
- Rule 8: When fable fails for a planned frontier task, the task continues on opus at maximum effort. When it fails for an escalated task, the task is blocked. Either way, fable is not tried again in that run.
- Rule 9: Every escalation and every substitution is logged in the spec's Decisions Log.

**Edge Cases:**
- A task already at fable fails again → Expected: reported blocked to the user; no further rung (Rule 7).
- Fable consent given for one task → Expected: applies to that task only; the next escalation to fable asks again.
- A `frontier` spec run in YOLO mode → Expected: planned frontier tasks run on fable (consent was given at classification); escalations to fable do not happen.
- Fable dispatch substituted silently by Claude Code → Expected: recorded; the spike showed the served model is observable.
- A haiku task fails twice in a row → Expected: it climbs to sonnet, not straight to opus; two more failures there climb it to opus.
- A spec with no model tier escalates → Expected: from the rung the task ran on; in Direct, where the session's model was inherited, the first step is opus.

## Success Metrics

### Key Performance Indicators
- **Adoption:** Every spec created after release records a model tier.
- **Engagement:** Escalations happen on evidence only: no escalation without a complexity block or two failed reviews in a row.
- **Quality:** Zero fable dispatches without consent, whether given at classification or at the time. Zero workflow failures caused by Fable being unavailable.
- **Business Impact:** Fable spend stays limited to tasks that were classified or escalated to it. The override rate on model-tier recommendations is visible, so the signals can be tuned.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Model tier recorded | spec, recommendation, choice, override reason | Override rate; tune signals |
| Task escalated | spec, task, trigger, rung before, rung after | Evidence-only escalation; escalation frequency |
| Fable consent asked | spec, task, answer | Consent coverage; how often Fable is declined |
| Rung substituted | spec, task, requested rung, rung that ran, reason | No-Fable robustness; honesty of the record |

All four are rows in the spec's Decisions Log; no separate telemetry is required.

---

## Constraints and Assumptions

### Constraints
- The classifier must add no conversation turn: the decomposition step keeps exactly one confirmation question round (spec 017, CON-8, enforced by a test).
- Specs without a model tier must read and implement exactly as today (spec 017, CON-5).
- The TDD gate and the review chain are unchanged.
- TCS can choose a model only for subagents, never for the main session.
- Subagent dispatch accepts the aliases `haiku`, `sonnet`, `opus` and `fable`; per-dispatch effort needs Claude Code 2.1.292 or later.
- Changes stay in the tcs-workflow plugin, with one version bump.

### Assumptions
- Opus at maximum effort closes a meaningful share of the gap to Fable on tasks that block at plain Opus.
- Prices and billing (Fable $10/$50, Opus $4/$20 per MTok; usage credits on some plans) hold long enough for a static cost sentence to stay accurate; the sentence names the ratio, not a price list.
- A failed or refused fable dispatch is visible to the orchestrator as a failure, not only as a silent substitution.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claude Code substitutes a model silently, so the log claims fable when opus ran | Medium | Medium | Mitigated: the orchestrator compares the requested alias with `message.model` in the subagent transcript and logs a mismatch (spike, 2026-10-29) |
| Consent behaviour of a fable subagent inside an interactive session differs from the docs (unconfirmed) | Medium | Medium | Not testable on a plan that includes Fable (spike); parked in #242. The nobody-can-be-asked rule prevents unattended fable dispatch |
| Depth signals mis-classify, sending routine specs to `hard` | Medium | Medium | Recommendation only; user confirms; override rate tracked |
| Cost sentence goes stale as prices change | Low | Medium | State the ratio and billing route, not prices; one place to update |
| Extra question text crowds the single confirmation round | Low | Low | Cost sentence appears once, on the `frontier` option only |

## Open Questions

- [x] Three tiers or two → three (`routine`, `hard`, `frontier`)
- [x] Spec-level field or per-task tag → both; the tag overrides the spec
- [x] Where the cost disclosure lives → in the classifier's confirmation question
- [x] Automatic escalation → automatic up to opus at maximum effort; fable always asks
- [x] Which depth signals, and their thresholds → SDD ADR-2
- [x] How the orchestrator observes the model that actually ran → `message.model` in the subagent transcript (spike, 2026-10-29)

---

## Supporting Research

### Competitive Analysis
Not applicable; this is internal workflow tooling. The relevant precedent is TCS's own spec 017,
whose decomposition classifier sets the contract this feature extends: recommend, never apply;
the user confirms; record in the Status table, the Decisions Log and the metadata read.

### User Research
- Issue #158 (maintainer) states the problem, the proposal sketch and the four open questions,
  answered on 2026-10-28.
- Repository survey: model choice exists only in agent frontmatter (17 × sonnet, 1 × haiku) and
  in `implement-incremental` step 4b; there is no model concept at spec or plan level, and no
  mention of Fable, effort or fallback.

### Market Data
Claude Code documentation (2026-10-28): Fable 5.1 $10/$50, Opus 5.5 $4/$20, Sonnet 5.5 $2/$10,
Haiku 5.5 $0.10/$0.50 per MTok. Fable can bill usage credits; interactive sessions ask for
consent, and `claude -p` and SDK sessions bill without asking. The Agent tool's `model` accepts
`sonnet`, `opus`, `haiku` and `fable`; per-dispatch `effort` (low to max) since 2.1.292.
