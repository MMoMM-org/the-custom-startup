---
title: "Complexity-tier dispatch for xdd and implement"
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

| Field | Value |
|-------|-------|
| specId | 017-complexity-tier-dispatch |
| title | Complexity-tier dispatch for xdd and implement |
| status | COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 24 |
| openQuestions | 3 (all non-blocking; listed in Open Questions) |

### SectionStatus

| Section | Status | Detail |
|---------|--------|--------|
| Product Overview | COMPLETE | |
| User Personas | COMPLETE | |
| User Journey Maps | COMPLETE | |
| Feature Requirements | COMPLETE | 5 Must, 2 Should, 2 Could, 5 Won't |
| Detailed Feature Specifications | COMPLETE | Classifier is the most complex feature |
| Success Metrics | COMPLETE | |
| Constraints and Assumptions | COMPLETE | |
| Risks and Mitigations | COMPLETE | |
| Open Questions | COMPLETE | 3 open, none blocking SDD |
| Supporting Research | COMPLETE | Two upstreams compared |

---

## Product Overview

### Vision

Every change that goes through TCS produces a real specification artifact, because the ceremony is proportional to the change — a one-line fix costs two short documents and no plan, while a new subsystem still earns the full decomposition.

### Problem Statement

TCS applies identical specification ceremony to every change. `/xdd` runs PRD → SDD → PLAN, and `/implement` runs a phase loop with a per-task two-stage review chain, whether the task is a new plugin or a typo in a hook message. There is no cheaper path.

The consequence is not that small work is over-documented. It is that **small work escapes the workflow entirely** — because the only available alternatives are "three documents and a phase loop" or "nothing", and for a one-line fix a rational author picks nothing. Skipping produces no artifact at all, which is strictly worse than a smaller artifact: no requirements, no design record, no decision log, nothing for the next reader.

This is measurable in this repository today:

- **The repo's own memory bank records the failure.** The `feedback_spec_first` memory exists because M3 was built ad-hoc and its specification was never completed. A cheaper tier is the structural fix for the pressure that produced that.
- **16 specs exist under `docs/XDD/specs/`, and the repo has shipped far more than 16 changes.** Everything below that bar went unspecified.
- **Spec status drifts because closing a heavyweight spec is itself heavyweight.** The `verify-spec-status-via-git` memory exists because pre-2026-05-21 specs show stale `Ready` in their README long after shipping.
- **`grep -riE "tier|dark factory" plugins/tcs-workflow/skills --include=SKILL.md` returns nothing.** There is no notion of complexity tiers anywhere in the workflow.

### Value Proposition

A tiered workflow is chosen over the current one-size ceremony because it changes the economics of the decision an author faces. Today the choice is *full ceremony or nothing*, and "nothing" wins for small work. With tiers the choice becomes *proportional ceremony or nothing*, and proportional wins — because it is cheap enough that skipping it saves almost nothing while losing the artifact.

Two independent upstreams converged on this shape within months of each other (`rsmdt/the-startup`, `obra/superpowers`), which is the strongest available evidence that it is the right shape rather than a local preference.

## User Personas

### Primary Persona: The TCS maintainer

- **Demographics:** Solo maintainer or small team; expert in the codebase; runs `/xdd` and `/implement` several times a week; strong opinions about process debt because they pay it personally.
- **Goals:** Ship a fix in an afternoon without abandoning the process. Be able to answer "why is this code like this?" six months later from an artifact rather than from memory. Keep the spec index honest.
- **Pain Points:** Opening a three-document spec for a one-line change feels absurd, so it does not happen. Then the change ships unrecorded, and the spec index quietly stops describing reality. Closing a spec after shipping is another chunk of work, so specs rot on `Ready`.

### Secondary Personas

**The orchestrating agent.** The agent running `/xdd` or `/implement`. Needs an unambiguous, cheap rule for which path to take and where to record it — not a judgement call it must re-derive from the raw request every time. Its pain point today is that no cheaper path exists to route to, so it either runs the full loop or the user abandons the workflow before it starts.

**The downstream reader.** Anyone (human or agent) arriving at a spec directory months later — a reviewer, a future maintainer, a drift-sweep run. Needs to know which tier a spec was built at, so that "there is no `plan/` here" reads as *a recorded decision* rather than *an interrupted run*. This persona is the reason tier must be recorded rather than merely inferred.

## User Journey Maps

### Primary User Journey: Shipping a small fix without abandoning the process

1. **Awareness:** The maintainer hits a bug that is one function and one test. They know `/xdd` exists and know that using it means three documents; they have skipped it for work like this before.
2. **Consideration:** They weigh "run the workflow" against "just fix it". Today the workflow costs a PRD, an SDD, a PLAN with phases, and a phase loop with two reviewers per task — so "just fix it" wins and the artifact is never created.
3. **Adoption:** They run `/xdd` because they have learned the classifier will recognise a fix and route it to Direct: two short documents, no plan, and an implementation path with no phase loop.
4. **Usage:** They answer the PRD and SDD prompts briefly. The classifier reports *Direct — change_type=fix, one acceptance criterion, modifies existing surface only* and offers the three tiers with Direct highlighted. They accept. `/implement` detects no plan artifact, routes to the direct path, and runs TDD, approval and drift checks without the per-task review chain.
5. **Retention:** The change shipped with a real artifact for roughly the cost of skipping. Next small fix, they run `/xdd` again — which is the outcome this feature exists to produce.

### Secondary User Journeys

**A large change is correctly recognised as large.** The maintainer starts a multi-plugin feature. The classifier sees several features, several components, and parallel work flagged in the design, and recommends Factory. The maintainer accepts, gets full decomposition, and nothing about the heavyweight path has been weakened — the tier system must not make big work cheaper, only small work possible.

**A reader meets a Direct spec.** A reviewer opens a spec directory with a PRD, an SDD and no `plan/`. The README records `Decomposition tier: Direct` with the classifier's rationale, so the absence of a plan reads as intentional. Without this the reader must guess whether decomposition was skipped deliberately or the run was interrupted.

**The classifier is wrong and the human overrides it.** The classifier recommends Direct for a change the maintainer knows is risky. They pick Incremental. The override and its reason are logged, so a later reader sees both what the classifier said and why the human disagreed.

## Feature Requirements

### Must Have Features

The minimum for this to be valuable: a tier model, a classifier, a way to record the tier, a dispatcher that honours it, and gates that hold everywhere.

#### Feature 1: Three-tier decomposition model

Tiering applies to **decomposition only**. Requirements and solution documents are written at every tier — what varies is the third artifact.

- **User Story:** As a TCS maintainer, I want the ceremony to scale to the size of my change, so that small work has a path through the workflow instead of around it.
- **Acceptance Criteria:**
  - [ ] Given a change classified Direct, When the specification completes, Then a requirements document and a solution document exist and no decomposition artifact is written
  - [ ] Given a change classified Incremental, When the specification completes, Then a phase-based plan artifact exists alongside requirements and solution
  - [ ] Given a change classified Factory, When the specification completes, Then a parallel-unit decomposition artifact exists alongside requirements and solution
  - [ ] Given any tier, When the specification completes, Then requirements and solution documents are present — no tier omits them
  - [ ] Given a Direct specification, When a reader opens the spec directory, Then the absence of a plan is explained by the recorded tier rather than being ambiguous

#### Feature 2: Complexity classifier

- **User Story:** As an orchestrating agent, I want a cheap deterministic rule for which tier a change needs, so that I recommend a tier without the recommendation itself becoming ceremony.
- **Acceptance Criteria:**
  - [ ] Given completed requirements and solution documents, When the classifier runs, Then it produces exactly one recommended tier
  - [ ] Given the classifier has run, When it presents its recommendation, Then it states the signals that drove it in terms the user can check against their own documents
  - [ ] Given the same pair of documents, When the classifier runs twice, Then it recommends the same tier both times
  - [ ] Given a classifier recommendation, When the user is asked to confirm, Then all three tiers are offered and the recommendation is highlighted rather than pre-applied
  - [ ] Given the user selects a tier other than the recommendation, When the choice is recorded, Then both the recommendation and the override are captured
  - [ ] Given the classifier runs, When it completes, Then it required no additional user input beyond the documents already written

#### Feature 3: Tier recorded in the spec lifecycle

- **User Story:** As a downstream reader, I want the chosen tier recorded in the spec's own metadata, so that I can tell a deliberate omission from an interrupted run.
- **Acceptance Criteria:**
  - [ ] Given a tier has been chosen, When the specification is written, Then the tier is recorded in the spec's lifecycle metadata as a first-class field
  - [ ] Given a tier has been chosen, When the decision is logged, Then the log entry records the date, the chosen tier, the classifier's recommendation, and the rationale
  - [ ] Given a spec created before this feature exists, When it is read, Then it reports an absent tier rather than failing or being assigned one silently

#### Feature 4: Implementation dispatch by tier

- **User Story:** As a TCS maintainer, I want implementation to follow the tier my specification was built at, so that I do not get a phase loop for a change that has no phases.
- **Acceptance Criteria:**
  - [ ] Given a spec with no decomposition artifact, When implementation starts, Then it routes to the direct execution path
  - [ ] Given a spec with a phase-based plan, When implementation starts, Then it routes to the phase-loop execution path
  - [ ] Given a spec with a parallel-unit decomposition, When implementation starts, Then it routes to the factory execution path
  - [ ] Given a spec whose recorded tier and present artifacts disagree, When implementation starts, Then the mismatch is reported to the user before any work is dispatched
  - [ ] Given implementation dispatch occurs, When the route is chosen, Then the user is shown which route was selected and what triggered it

#### Feature 5: Gates that hold at every tier

Two guarantees are tier-independent. Everything else may vary.

- **User Story:** As a TCS maintainer, I want the test-first discipline and the approval gate to survive at every tier, so that a cheaper path is cheaper in ceremony but not in safety.
- **Acceptance Criteria:**
  - [ ] Given any tier including Direct, When implementation work is about to be dispatched, Then the test-first gate runs and can block
  - [ ] Given any tier including Direct, When implementation work is about to be dispatched, Then the user has an explicit approval point before code is written
  - [ ] Given the Direct tier, When implementation completes, Then a drift check against the requirements and solution documents runs
  - [ ] Given the Direct tier and a project constitution exists, When implementation completes, Then the constitution check runs and a blocking violation prevents completion
  - [ ] Given the Direct tier, When implementation runs, Then the per-task spec-compliance and code-quality review chain does not run

### Should Have Features

**Escalation out of Direct.** When work classified Direct decomposes into more units than the tier is meant to carry, the direct path recommends re-specifying at a higher tier rather than silently growing into an unstructured phase loop. This is what stops Direct becoming the dumping ground for everything (Risk 2).

**Tier-aware spec status reporting.** Spec status output includes the tier, so a reader scanning the index sees tier alongside phase. Valuable but not required for the workflow to function.

### Could Have Features

**Backfilling tiers onto existing specs.** The 16 existing specs could be annotated with the tier they would have been classified as. Informational only.

**Classifier accuracy review.** Periodically compare recommended tier against the tier actually used, to tune the heuristic. Requires accumulated data that does not exist yet.

### Won't Have (This Phase)

- **Scaling the requirements and solution documents themselves.** Considered and rejected — see Supporting Research. Documents are written at every tier; only decomposition varies.
- **A fourth tier, or user-defined tiers.** Three tiers, fixed. More tiers multiply the surface to specify, gate and explain without evidence that a fourth is needed.
- **Automatic tier selection with no confirmation.** The classifier recommends; the human decides. Both upstreams kept a confirmation point and so does this.
- **User-invocable tier sub-skills.** Users invoke the entry point, not the tier. A user who picks their own tier from the `/` menu bypasses the classifier, which defeats it.
- **Deleting artifacts on tier change.** Changing tier leaves prior artifacts in place, flagged. Cleanup stays manual — automatic deletion of specification content is not a risk worth taking to save a manual step.

## Detailed Feature Specifications

### Feature: Complexity classifier

**Description:** The classifier reads the requirements and solution documents a specification has already produced, extracts a small fixed set of signals from them, and maps those signals to one of three tiers. It runs at the decomposition step — after both documents exist — which is what makes it cheap: it reads artifacts rather than interrogating the user, so it costs no additional conversation turns.

Running it *after* the documents is the design's load-bearing choice. A classifier that ran on the raw request would have to guess at scope before anything was written, would be non-deterministic across phrasings of the same request, and would need its own clarifying questions — becoming the ceremony it exists to avoid.

**User Flow:**

1. User completes the requirements phase.
2. User completes the solution phase.
3. System reads both documents and extracts classification signals.
4. System presents the recommended tier together with the signals that produced it.
5. User confirms the recommendation or selects a different tier.
6. System records the tier, the recommendation, and the rationale in the spec's decision log.
7. System produces the decomposition artifact for the chosen tier — or, for Direct, none.

**Business Rules:**

- Rule 1: The classifier runs only after both requirements and solution documents exist. It never runs on the raw request.
- Rule 2: The classifier's output is a recommendation, never an application. Tier is not set until the user confirms.
- Rule 3: The signals must be derivable from the documents alone, with no additional user input.
- Rule 4: The same documents always produce the same recommendation.
- Rule 5: Every tier decision is logged with its rationale, whether it accepted or overrode the recommendation.
- Rule 6: An override never deletes artifacts already written at another tier; superseded artifacts are flagged, not removed.
- Rule 7: Change type, breadth of surface touched, and explicitly flagged parallel work are all classification inputs. Acceptance-criteria count alone never escalates a tier — a long list of criteria against one component is still one component's worth of work.

**Edge Cases:**

- Scenario 1: Requirements and solution exist but are nearly empty (a stub spec) → Expected: recommend Direct, since no evidence of breadth exists; the user may override upward.
- Scenario 2: A refactor touching many components → Expected: not Direct. Change type says "fix-like", but breadth warrants phase boundaries; breadth wins.
- Scenario 3: Many acceptance criteria against a single component → Expected: Incremental, not Factory. Criteria count alone does not justify parallel-unit overhead.
- Scenario 4: The user overrides Direct upward after decomposition was already skipped → Expected: run the higher tier's decomposition; nothing has been lost, because Direct wrote no artifact to conflict with.
- Scenario 5: The user overrides downward from a tier whose artifacts already exist → Expected: leave the artifacts in place, flag them as superseded in the decision log, and proceed at the lower tier.
- Scenario 6: A spec's recorded tier and its actual artifacts disagree at implementation time → Expected: report the mismatch before dispatching any work; this usually means an interrupted specification run.
- Scenario 7: Work classified Direct turns out to need more delivery units than Direct carries → Expected: recommend re-specifying at a higher tier rather than improvising phases.

## Success Metrics

### Key Performance Indicators

This is internal developer tooling for a small team, so the metrics are counts observable from the repository, not product analytics.

- **Adoption:** New specs created at Direct tier. Target: at least half of new specs in the first two months are Direct — if none are, the tier is not cheap enough to change behaviour, and the feature has failed even if it works.
- **Engagement:** Ratio of merged pull requests that have an associated spec, before versus after. This is the metric that matters most: the feature exists to raise it.
- **Quality:** Specs reaching `Implemented` rather than rotting on `Ready`. Target: no spec shipped after this feature is left stale, since the direct path is short enough to finish.
- **Business impact:** Reduction in unspecified changes — changes shipped with no artifact of any kind. Target: zero for changes that touch plugin behaviour.

### Tracking Requirements

All tracking is artifact-based; nothing new needs to be instrumented.

| Event | Properties | Purpose |
|-------|------------|---------|
| Tier chosen | Date, spec ID, recommended tier, chosen tier, rationale | Measures adoption per tier and the classifier's agreement rate |
| Classifier overridden | Date, spec ID, recommendation, choice, reason | Tunes the heuristic; a high override rate means the thresholds are wrong |
| Spec finalized | Date, spec ID, tier, shipping notes | Measures the quality metric — did specs at this tier get closed out? |
| Spec created | Date, spec ID, tier | Denominator for adoption |
| Tier mismatch reported | Date, spec ID, recorded tier, artifacts found | Detects interrupted runs and dispatcher defects |

## Constraints and Assumptions

### Constraints

- **The test-first gate cannot be weakened.** `xdd-tdd` states an iron law; a tier that dropped it would put two parts of the workflow in direct contradiction.
- **The repo's spec-first rule must survive unchanged.** Recorded in the memory bank as `feedback_spec_first`. The chosen model satisfies this literally — every change still gets requirements and a solution — which is why it was chosen.
- **Backwards compatibility with 16 existing specs.** None have a tier. Reading them must not fail.
- **Changes are confined to `tcs-workflow`.** One plugin, one version bump.
- **No new runtime dependencies.** The classifier reads Markdown that already exists.
- **The classifier must not become ceremony.** Any design where classification costs a conversation turn has failed its own purpose.

### Assumptions

- **Small changes are the common case.** If most work were genuinely Factory-scale, a cheaper tier would relieve no pressure. The gap between 16 specs and the repo's actual commit history is the evidence.
- **Authors skip the process because of cost, not because they reject it.** The M3 episode recorded in the memory bank supports this: the spec was intended and started, then never completed.
- **Signals extractable from requirements and solution documents are sufficient to classify.** Both upstreams operate this way successfully.
- **The maintainer will accept the classifier's recommendation most of the time.** If not, the override rate will show it and the thresholds get tuned — which is why override rate is tracked.
- **Three tiers is the right number.** Both upstreams independently arrived at three.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The classifier becomes ceremony itself — more questions, more turns | High | Medium | Constrain it to signals derivable from existing documents with no additional user input; make that a testable acceptance criterion, not an aspiration |
| Direct becomes the default dumping ground; everything gets classified small | High | Medium | Escalation out of Direct when the work exceeds what the tier carries; track override rate and tier distribution to detect drift |
| Recorded tier and actual artifacts diverge | Medium | Medium | Detect and report the mismatch at implementation dispatch before any work is dispatched |
| A cheaper tier is read as permission to skip specs entirely | High | Low | The tier still produces requirements and a solution; the spec-first rule is unchanged, and Direct is a path *through* the workflow, not around it |
| Three tiers make the workflow harder to explain than one | Medium | Medium | The entry points stay unchanged — users still run `/xdd` and `/implement`; tier sub-skills are not user-invocable, so the surface a user sees does not grow |
| Existing specs break when read by tier-aware tooling | Medium | Low | Absent tier is a valid state that reads cleanly; no backfill required |
| Two upstreams' vocabularies get mixed in the implementation | Low | Medium | Adopt one vocabulary (Direct / Incremental / Factory) and use it consistently; the rejected alternative is recorded in Supporting Research so the choice is not silently revisited |

## Open Questions

None of these block the SDD; all can be settled during design.

- [ ] Should the escalation threshold out of Direct be a fixed number of delivery units, or a judgement the direct path makes and explains? Upstream uses a fixed number.
- [ ] Should tier appear in the spec status table as a distinct field, or only in the decision log? The decision log is required either way.
- [ ] Do the existing 16 specs get a recorded tier retroactively, or stay tier-absent? Recommendation is to leave them absent, since a backfilled tier is a guess presented as a record.

---

## Supporting Research

### Competitive Analysis

Two upstream repositories solved this independently, within roughly three months of each other. That convergence — not either implementation on its own — is the evidence that the shape is right.

**`rsmdt/the-startup` — explicit tier dispatch (v3.7.0/v3.8.0, May 2026).** Nine commits over five days restructured both halves of the workflow. `specify` gained a complexity classifier and a decomposition phase; `implement` was split into `implement-direct`, `implement-incremental` and `implement-factory` and reduced to a dispatcher. Two details of that implementation were adopted here:

1. **The dispatcher routes by artifact detection, not by re-classification.** The tier is decided once, at specification time, and is then *materialised as artifacts*. The dispatcher looks at which decomposition artifact exists and routes accordingly. This makes dispatch trivial, deterministic, and impossible to disagree with the specification.
2. **The classifier runs after the documents exist.** It reads them rather than interrogating the user, which is what keeps it from becoming ceremony.

Upstream also renamed its middle tier from "Standard" to "Incremental" (`cd7ee80`) and hid the tier sub-skills from user invocation (`564e281`). Both are adopted.

**`obra/superpowers` — ceremony scaling in brainstorming (v6.3.0, August 2026).** Classifies requests as spike, bounded, or architectural; small tasks skip the two-document ritual. Different vocabulary, same core idea, and the same non-negotiable: *"Every path still stops for your approval before implementation."*

**Where they disagree, and what TCS chose.** These two do not scale the same thing. `rsmdt` keeps requirements and solution at every tier and scales only decomposition. `superpowers` scales the documents themselves, so a spike skips them.

TCS adopts the `rsmdt` model — tier the plan only — for three reasons:

1. **The spec-first rule stays literally true.** The repository's own rule, recorded in the memory bank, is that nothing is implemented without going through the specification workflow. Under this model every change still produces requirements and a design. The rule needs no rewrite, which matters because rewriting a rule while relieving the pressure that people break it under is how a rule quietly dies.
2. **The classifier gets real inputs.** Classifying after the documents exist means reading evidence rather than guessing from a request's phrasing. The superpowers model must classify before anything is written.
3. **The artifact is the point.** The problem being solved is *no artifact at all*. A tier that skips the documents optimises the wrong thing — it makes the cheap path cheaper by removing exactly what the feature exists to preserve.

The cost of this choice is honest and worth stating: a one-line fix still costs two short documents, where the superpowers model would cost one. That is the price of keeping the spec-first rule intact, and it is accepted deliberately.

### User Research

No formal research; the user is the maintainer, and the evidence is the repository's own history:

- The `feedback_spec_first` memory exists because M3 was built ad-hoc and its spec was never completed — recorded as a correction, meaning the intent to specify was there and the cost defeated it.
- The `verify-spec-status-via-git` memory exists because specs show stale `Ready` status long after shipping — closing a heavyweight spec is itself heavyweight, so it does not happen.
- 16 specs exist against a far larger change history.

Together these describe one failure mode with three symptoms: ceremony priced above what small work will bear.

### Market Data

Not applicable — internal developer tooling for a single team. The relevant signal is upstream convergence, covered in Competitive Analysis.
