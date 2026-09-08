---
title: "Observability rollout across active repositories"
status: draft
version: "1.0"
spec: 019
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
|---|---|
| specId | 019-observability-rollout-across-active-repos |
| title | Observability rollout across active repositories |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 26 |

### SectionStatus

| Section | Status | Detail |
|---|---|---|
| Product Overview | COMPLETE | |
| User Personas | COMPLETE | Single human operator; three distinct roles, not three people |
| User Journey Maps | COMPLETE | Four journeys including uninstall and the foreign-entry error path |
| Feature Requirements | COMPLETE | Four Must, one Should, one Could, five Won't |
| Detailed Feature Specifications | COMPLETE | Setup and removal, the highest-risk feature |
| Success Metrics | COMPLETE | Decidability of #153's two questions, with a stated collection period. Corrected 2026-09-08: an earlier version attributed all of this to #147, which asks something narrower |
| Constraints and Assumptions | COMPLETE | |
| Risks and Mitigations | COMPLETE | |
| Open Questions | COMPLETE | Three decided at review, one carried |

---

## Product Overview

### Vision

Point the recorder spec-018 built at the repositories where work actually happens, and make the
answer it produces readable in one place without ever pooling four contexts into one file.

### Problem Statement

spec-018 delivered a correct instrument and left it measuring the wrong place.

The recorder runs in one repository — the one that *ships* the skills and agents, not one where they
are *used*. That is not a small sampling problem, it is a structural one. The firing-coverage figure
divides a numerator gathered from consumer repositories by a denominator globbed from the shipping
repository's own inventory. Records from consumer repositories never reach the shipping repository's
log at all, so the numerator is empty by construction and the fraction **structurally undercounts**.
The single observed session reported 1 of 83 entries as fired. That number is not a low result; it
is not a result.

Two figures from that session are sound at any sample size, and they are the evidence that the
instrument works: the always-loaded instruction layer costs 7038 bytes in every session, and 15
skills in one plugin are structurally unreachable — nested too deep to be discoverable at all, so
they cannot fire regardless of usage.

Everything else is waiting on data that cannot be gathered from where the recorder currently sits.
**Which issues this actually serves — corrected 2026-09-08 after an alignment audit.** An earlier
version of this document said "#147 asks which memory files and skills are worth keeping". It does
not, and the error mattered because the success criterion was built on it.

- **#153** is this work's own issue and owns both halves of the report. It states the dependency
  precisely: "#147 cannot be decided without a denominator."
- **#147** audits which user auto-memory entries belong where subagents can see them. Its deciding
  question is *must this fire for every agent on every run* — not how often something was used. It
  needs the **instruction-load** half of the report as its denominator, and nothing more.
- **#155** owns the 15 structurally unreachable skills, which the coverage report names rather
  than fixes.

So the skill-and-agent firing coverage this spec is largely about serves **#153 and #155**. Only
the instruction-load half reaches #147, and only as an input to a decision made on other grounds.
Today the underlying question is answered by
reasoning about the loader, which spec-018 documented as having been measurably wrong three separate
times in the session that produced it.

### Value Proposition

A decision about what to delete, keep or rework, made from a record of what actually loaded and
fired across the four repositories where the work happens — instead of from an inventory of what
exists and an assumption about what gets used.

---

## User Personas

There is exactly one human here. Enumerating "people" would therefore produce a single persona and
hide the fact that this person does three things with genuinely different goals, at different times,
with different failure modes. The personas below are **roles**, and they are mutually exclusive in
that sense: no two share a goal, and each fails differently.

### Primary Persona: The Operator

**Role:** installs and removes the recording configuration in a target repository.

- **Goals:** turn recording on in a chosen repository in one deliberate act; be certain nothing else
  in that repository's configuration was disturbed; be able to undo it later without archaeology.
- **Pain Points:** a setup that silently overwrites configuration they did not author. A setup with
  no removal path, leaving entries to be picked out of several files by hand months later. A setup
  that claims success while having written nothing usable.
- **Frequency:** rare and deliberate — four times initially, occasionally thereafter.

### Secondary Personas

**The Subject** — the same person, working normally in a target repository while recording runs.

- **Goals:** work exactly as before. Notice nothing.
- **Pain Points:** measurable slowdown in ordinary sessions. Recording that quietly stops working
  and is discovered weeks later, when the collection period was the whole point. Recorded material
  turning up somewhere it was not expected, such as a commit.
- **Frequency:** continuous, passive, for the whole collection period.

**The Analyst** — the same person, weeks later, deciding what to keep.

- **Goals:** see, for each shipped skill and agent, in which target repositories it fired and in
  which it did not; and reach a keep/drop/rework decision on that basis.
- **Pain Points:** a report that pools four repositories into one figure, which cannot answer "does
  this fire in both places it should". A report that presents a merged freshness or installation
  state as if it applied everywhere, hiding that one repository stopped recording months ago. A
  report that requires the four locations to be typed out every time.
- **Frequency:** once at the end of the collection period; occasionally during it, to confirm the
  recording is still alive.

---

## User Journey Maps

### Primary User Journey: Turning recording on in a repository

1. The Operator invokes setup, naming a target repository.
2. The system reports what it found there: whether recording is already configured, whether entries
   it does not own are present, and which of the two record locations applies.
3. The Operator confirms.
4. The system writes the registration and the switch into the target's local, untracked
   configuration layer, leaving every entry it did not author untouched.
5. The system reports what it changed, and how to undo it.
6. The Operator records the target in the locations list so the report can find it later.

### Secondary User Journeys

**Recording, passively.** The Subject opens a session in a target repository and works. Records
accumulate. Nothing else changes. Periodically the Subject or Analyst asks whether recording is
still alive in each target, and gets a per-repository answer rather than a single verdict.

**Evaluating.** The Analyst runs the report with no arguments. It reads every configured location,
reports per repository what loaded and fired there, and adds one cross-repository figure: which
shipped skills and agents fired *anywhere*, and which fired nowhere. The Analyst decides.

**Turning recording off.** The Operator invokes removal, naming a target. The system removes only
the entries it authored, leaves foreign entries in place, and says so. Existing records are not
deleted — stopping recording and discarding what was recorded are separate acts.

**Error path — foreign entries.** Setup finds, at the location it would write to, entries it does
not own that would conflict. It changes nothing, reports precisely what it found and where, and
exits without treating this as a failure. The Operator resolves it and re-runs.

---

## Feature Requirements

### Must Have Features

#### Feature 1: Deliberate setup into a target repository

- **User Story:** As the Operator, I want to turn recording on in a repository I name, so that the
  recorder runs where I actually work rather than only where it was built.
- **Acceptance Criteria:**
  - [ ] Given a target repository, When setup runs, Then recording is configured there and the
        system reports which entries it added
  - [ ] Given a target whose configuration contains entries the system did not author, When setup
        runs, Then those entries are still present and unmodified afterwards
  - [ ] Given a target where setup has already run, When setup runs again, Then nothing is changed
        and the system reports that it was already configured
  - [ ] Given a target whose configuration file cannot be parsed, When setup runs, Then nothing is
        written and the system reports the file as unreadable
  - [ ] Given a target where setup would write, When setup runs, Then it writes only to a location
        that version control ignores, so the change cannot be committed or pushed
  - [ ] Given any target, When setup completes, Then the report of what changed includes how to undo
        it
  - [ ] Given a target that is not a repository, When setup runs, Then it reports this and writes
        nothing

#### Feature 2: Removal

- **User Story:** As the Operator, I want to remove recording from a repository, so that turning it
  on is a reversible decision rather than a permanent one.
- **Acceptance Criteria:**
  - [ ] Given a target where setup previously ran, When removal runs, Then the entries setup
        authored are gone and the system reports which were removed
  - [ ] Given a target containing both authored and foreign entries, When removal runs, Then only
        the authored ones are removed
  - [ ] Given a target where setup never ran, When removal runs, Then nothing is changed and the
        system says so, without reporting an error
  - [ ] Given a target with existing records, When removal runs, Then the records still exist —
        stopping recording never deletes what was recorded

#### Feature 3: A list of where the records are

- **User Story:** As the Analyst, I want the report to already know where every record lives, so
  that evaluating four repositories does not mean typing four locations every time.
- **Acceptance Criteria:**
  - [ ] Given several configured targets, When the report runs with no arguments, Then it reads all
        of them
  - [ ] Given a target whose records live in the container layout and one whose records live in the
        host layout, When both are configured, Then both are read correctly
  - [ ] Given a configured target whose record does not exist yet, When the report runs, Then that
        target is reported as not yet recording and the other targets are still reported
  - [ ] Given the list itself, When it is stored, Then version control ignores it, because it holds
        real repository names and paths
  - [ ] Given a repository that is worked on in both layouts, When it is configured, Then both of
        its record locations can be expressed

#### Feature 4: A report that spans repositories without pooling them

- **User Story:** As the Analyst, I want to see which skills fired in which repositories, so that I
  can tell "used everywhere", "used in one place" and "used nowhere" apart.
- **Acceptance Criteria:**
  - [ ] Given records from several repositories, When the report runs, Then instruction loads and
        byte costs are reported per repository, each identified
  - [ ] Given records from several repositories, When the report runs, Then it also states, for
        each shipped skill and agent, whether it fired in any repository and in which
  - [ ] Given a shipped skill that fired in one repository and not another, When the report runs,
        Then both facts are visible rather than summed into one figure
  - [ ] Given one repository recording actively and another whose newest record is months old, When
        the report runs, Then each repository's recording state is reported separately and the stale
        one is identified as stale
  - [ ] Given the timing wrapper installed in one repository only, When the report runs, Then it
        does not present timing as available for the others
  - [ ] Given records from several repositories where the same file name exists in more than one,
        When the report runs, Then those are counted as distinct files rather than merged

### Should Have Features

#### Feature 5: An honest liveness check across all configured targets

- **User Story:** As the Subject, I want to ask whether recording is still working everywhere, so
  that a silent failure does not cost me the collection period.
- **Acceptance Criteria:**
  - [ ] Given several configured targets, When the check runs, Then each is reported individually as
        recording, not recording, or never configured
  - [ ] Given a target that is configured but has produced nothing, When the check runs, Then it is
        distinguished from one that is not configured at all

### Could Have Features

#### Feature 6: Assisted discovery when adding a target

- **User Story:** As the Operator, I want the system to suggest record locations it can find, so
  that adding a target is less error-prone than typing a path.
- **Acceptance Criteria:**
  - [ ] Given a request to add a target, When discovery runs, Then any location it proposes is shown
        for confirmation and never added silently
  - [ ] Given locations that were produced by tests rather than by real sessions, When discovery
        proposes candidates, Then the Operator can reject them, because a proposal is not an addition

### Won't Have (This Phase)

- **Registering the recorder for every repository at once.** It would remove the per-repository
  decision that makes this safe, and it charges every session in every repository a per-event cost
  whether or not that repository ever wanted recording.
- **Anything that enables recording without a person asking for it** — no prompt at session start,
  no enabling as a side effect of an update, no default-on.
- **Pooling the records into one shared file.** spec-018 rejected this and the reasoning is
  unchanged; this spec merges for a report, never at rest.
- **Recording Bash tool calls.** Unchanged from spec-018, where it was scoped to the writer and
  declared out of scope.
- **Deleting records.** Removal stops recording. Discarding what was recorded stays a separate,
  manual act.

---

## Detailed Feature Specifications

### Feature: Deliberate setup into a target repository

**Description:** A person names a repository and asks for recording to be turned on there. The
system inspects that repository, reports what it found, changes only what it owns, and tells the
person how to undo it. It is invoked deliberately and never runs on its own.

**User Flow:**

1. The Operator invokes setup with a target repository.
2. The system determines whether the target is a repository, which of the two record layouts
   applies, and whether recording is already configured.
3. The system inspects the location it would write to and classifies what it finds: nothing, its own
   previous work, or entries authored by something else.
4. The system reports all of that before changing anything.
5. The Operator confirms.
6. The system writes, preserving everything it did not author.
7. The system reports what changed and how to reverse it.

**Business Rules:**

- Rule 1: The system writes only to a configuration layer that version control ignores. A
  registration that can be committed can reach someone who never asked for it.
- Rule 2: Entries the system did not author are never modified or removed — not by setup, not by
  removal.
- Rule 3: Finding foreign entries is a stop condition, not a failure. The system reports and exits
  without an error, because there is nothing wrong with the target — only something the system
  declines to decide on the Operator's behalf.
- Rule 4: Ownership is established by an explicit marker the system writes, never by a file or entry
  merely existing. Re-running is decided on content, not on a flag.
- Rule 5: Setup is idempotent. Running it twice leaves the same state as running it once.
- Rule 6: The system's own artifacts are excluded from its own conflict detection, so a first run
  cannot report itself as a pre-existing foreign installation.
- Rule 7: Before modifying an existing configuration, the previous content is preserved so the
  Operator can recover it. Version control is not a fallback here — the target location is ignored
  by version control by design.

**Edge Cases:**

- The target is not a repository → report it, write nothing.
- The configuration file exists but cannot be parsed → write nothing, report it as unreadable.
  Never repair a file the system did not author.
- The configuration file does not exist → create it containing only what the system authored.
- Setup has already run with an older version of the entries → recognise its own marker, update, and
  report that it updated rather than that it installed.
- Foreign entries are present at the same location → report precisely what and where, change
  nothing, exit without error.
- The Operator runs setup twice concurrently → the second run must not interleave with the first.
- The target is the shipping repository itself, where recording is already configured by hand →
  recognised as already configured, not duplicated.

---

## Success Metrics

Success is **decidability**, not activity. A criterion phrased as "recording works" would be met on
the first day and would leave this feature where spec-018 left it: correct, and answering nothing.

### Key Performance Indicators

- **Coverage of the question:** after the collection period, the report states for every shipped
  skill and agent whether it fired in any target repository, and in which. Target: every inventory
  entry classified, none unknown.
- **Adoption:** all four intended repositories recording, verifiable individually rather than in
  aggregate. Target: 4 of 4.
- **Continuity:** no target silently stops recording without it being noticed. Target: the liveness
  check identifies any target whose newest record is older than the collection period's start.
- **Decision quality:** the resulting evidence is sufficient to classify each shipped skill and
  agent as keep, drop or rework — closing **#153**'s coverage question and giving **#155** the
  usage half of its case. Separately, the instruction-load half supplies the denominator **#147**
  says it cannot be decided without; #147 itself is then decided on its own criterion, which is
  whether an entry must reach every agent on every run, not how often it was loaded.
- **Invisibility:** the Subject reports no perceptible change to ordinary sessions.

### Tracking Requirements

The recorder built in spec-018 already emits everything below; this spec adds no new event types.
What it adds is reading them from more than one place.

| Event | Properties | Purpose |
|---|---|---|
| Instruction file loaded | which file, why it loaded, its parent, its size, which repository | Answers what the always-loaded layer costs, per repository |
| Skill fired | which skill, which repository | The numerator of the coverage question |
| Agent dispatched | which agent type, which repository | The numerator of the coverage question |
| Recording self-check | the switch states, a probe value, which repository | Distinguishes "recorded nothing" from "was not recording" — per repository |

---

## Constraints and Assumptions

### Constraints

- **A registered hook costs time whether or not it records.** Measured on the maintainer's platform
  at roughly 3–5 ms per matching event with recording switched off, and this is a floor rather than
  an implementation defect: two candidate causes were measured and refuted. Any design that
  registers the recorder more widely than necessary spends this in repositories that never wanted it.
- **Records live in two different places depending on how a session runs**, and the two cannot be
  found by the same means. One is discoverable; the other is only knowable if the repository is
  already known.
- **The configuration of most target repositories is version-controlled and shared.** Any
  registration written to the shared layer would travel to anyone who clones the repository.
- **The record's location is ignored by version control**, so restoring a damaged configuration file
  from version control is not available for the layer this spec writes to.
- **No new runtime dependency.** The parsing and reading this needs must use what is already
  available.
- **Solo operation.** One person operates all four target repositories today, which is what makes a
  local, untracked configuration sufficient. Should that change, the sharing question reopens.

### Assumptions

- The four target repositories continue to be worked in during the collection period. If work moves
  elsewhere, the data answers less than intended — this is the failure mode that produced this spec.
- The shipped inventory does not change so drastically during the collection period that the
  denominator is no longer comparable to what was measured.
- Records accumulate slowly enough that the existing size limits are not reached within the
  collection period, and if they are, the existing rotation keeps the record usable.
- The person reading the report is the person who generated it, on the machine that holds the
  records. The report is not a document that travels.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Setup damages a configuration file the Operator cares about | High | Low | Write only to an untracked layer; never modify foreign entries; preserve previous content before writing; refuse to touch an unparseable file |
| A registration is committed and reaches someone who never asked for recording | High | Low | Write only where version control ignores; verify this per target rather than assuming it |
| A target silently stops recording and the collection period is wasted | High | Medium | Per-repository liveness reporting, never a merged verdict; the Analyst can check during the period, not only at its end |
| The report merges repositories in a way that reads as fact but is not | Medium | High if unaddressed | Report per repository by default; merge only the one figure that is meaningful merged, and identify it as such |
| Locations produced by tests are mistaken for real repositories | Medium | Medium | The locations list is explicit; anything discovered is proposed for confirmation, never added silently. This risk is not hypothetical — three such locations exist today |
| The per-event cost becomes noticeable in ordinary work | Medium | Low | Register in named repositories only; keep the measured cost visible in the documentation rather than implied |
| The collection period ends without anyone evaluating | Medium | Medium | Success is defined as a decision, not as data; the period has a stated end |
| The shipping repository's own records are mixed into the inventory denominator | Medium | Medium | The denominator stays one repository's shipped inventory; the numerator is the union across targets |

---

## Open Questions

Three were decided at review on 2026-09-08 and are recorded with their trade-offs so the SDD
implements a choice rather than rediscovering one. One is carried.

- [x] **Where the registration is written — the untracked local layer, not the shared one.** Found
      by checking rather than assumed: the shared layer is version-controlled in three of the four
      targets. The untracked layer is present in all four and demonstrably supports what is needed.
      Rejected: the shared layer, which is the more obvious choice and would have made recording
      reachable by anyone cloning the repository.
- [x] **How widely the recorder is registered — named repositories only.** Rejected: registering it
      for every repository at once, which resolves paths more cleanly but charges every session in
      every repository the per-event cost, and is unproven for two of the three events this needs.
- [x] **What the report merges — per repository by default, with one cross-repository figure.**
      The one analysis that genuinely gains from merging is also the only one that needs no
      repository identity. Rejected: merging everything, which makes freshness and installation
      state read as facts about all repositories when they are facts about one.
- [ ] **How long the collection period runs before the evaluation happens.** Needs a date, not a
      feeling. Without one, "evaluate later" is the failure mode this spec exists to correct.

---

## Supporting Research

### Competitive Analysis

Not applicable in the usual sense: this is internal instrumentation for a single operator, competing
with nothing. The relevant comparison is against the alternative already in use — reasoning about
the loader without measuring it — which spec-018 documented as having been measurably wrong three
times in a single session, including a case where an agent asked which rules were in its context
answered "none" and then obeyed one of them in the next run.

### User Research

The operator's own working pattern is the research, and it is what produced this spec: the
repository where the instrument was installed is not a repository where much work happens, and four
others are. That was stated directly and is the correcting premise for spec-018's deferral of
distribution.

### Market Data

Not applicable.
