---
title: "Observability: log what actually loads and fires"
status: complete
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
| specId | 018-observability-load-and-fire-log |
| title | Observability: log what actually loads and fires |
| status | COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 32 |

### SectionStatus

| Section | Status | Detail |
|---|---|---|
| Product Overview | COMPLETE | |
| User Personas | COMPLETE | |
| User Journey Maps | COMPLETE | |
| Feature Requirements | COMPLETE | |
| Detailed Feature Specifications | COMPLETE | |
| Success Metrics | COMPLETE | |
| Constraints and Assumptions | COMPLETE | |
| Risks and Mitigations | COMPLETE | |
| Open Questions | COMPLETE | All 4 decided at review; recorded with their trade-offs and the rejected alternative |
| Supporting Research | COMPLETE | |

---

## Product Overview

### Vision

Replace reasoning about what Claude Code loads and runs with a local record of what it actually did.

### Problem Statement

Structural decisions about this repo's memory bank, skills and hooks are currently made by reasoning
about the loader rather than by observing it — and that reasoning has been measurably wrong.

Three documented cases, all in the session that produced this spec:

1. An observer mechanism was believed to be interactive-only, based on three failed runs and a call
   site. It was actually gated on an environment flag. Four runs and roughly an hour were spent
   before the real cause was read out of the binary.
2. `.claude/rules/` frontmatter was believed to use a `paths:` key. It is `globs:`. The wrong key
   does not fail — it silently converts a conditional rule into an always-loaded one, i.e. it
   inverts the cost the author intended.
3. A subagent asked to report which rules were in its context answered "NONE", then obeyed one of
   those rules in the next run. **Agent self-report is not a measurement.**

The concrete blocked decision is [#147](https://github.com/MMoMM-org/the-custom-startup/issues/147):
the user auto-memory holds 39 entries, none of which reach a subagent, and the operational gotchas
live there *because they recur*. #147 must decide what moves where — and cannot, because nobody can
say which instruction files actually reach a prompt, or what the always-loaded layer really costs.
The memory bank's 24 KB budget is an estimate of size, not evidence of delivery.

A second, independent pain: when a session feels slow, the only built-in signal is a threshold-gated
console line, `Slow PreToolUse hooks: <ms>ms for <tool> (<n> hooks)`. It is an aggregate over all
hooks sharing a matcher, it is not persisted, and it cannot name the offending hook. With ~3 hook
invocations per tool call across this repo's three plugins, "which hook is slowing me down" is
currently unanswerable.

Consequence of not solving it: every structural memory decision stays a guess, #147 stays blocked,
and slow hooks stay unattributable — while the repo keeps shipping rules whose delivery nobody has
verified.

### Value Proposition

The alternative on offer today is third-party observability dashboards. All of them require standing
infrastructure (a server, a database, a browser UI, sometimes Docker), and **none of them covers
instruction loading at all** — they visualise tool calls.

This solution is different in three ways that matter here:

- It answers the question this repo actually has ("which instruction files reach a prompt, and
  why"), using a first-party hook event that no surveyed project uses.
- It requires no server, no database and no network. The record is a local append-only file.
- It costs nothing while switched off: with no hook registered, the harness skips the work entirely.

## User Personas

### Primary Persona: Framework maintainer

- **Demographics:** the owner of this repo; expert Claude Code user; author of six plugins, 30+
  skills and 19 agents; works on macOS with `zsh`.
- **Goals:** make memory-bank and plugin structure decisions on evidence; know which of the shipped
  skills are ever actually used; keep the always-loaded context small without breaking delivery.
- **Pain Points:** every routing decision rests on inference about a loader that has surprised them
  three times; a 24 KB budget they can measure in bytes but not in effect; no way to tell a skill
  that never fires from one that fires invisibly.

### Secondary Personas

**Plugin consumer** — a developer in another repo who installs the TCS plugins.

- **Demographics:** ordinary Claude Code user; has not read this spec; may not know the plugins ship
  hooks at all.
- **Goals:** get the plugins' behaviour; be surprised by nothing else.
- **Pain Points:** a plugin update that silently starts recording their Bash command lines would be
  a breach of trust, and they would have no reason to look for it.

**Session diagnostician** — the maintainer or a teammate while a session is misbehaving.

Distinct from the maintainer persona by goal, not by person: this persona is not deciding structure,
they are attributing a symptom ("this got slow", "my rule did not fire") to a cause, under time
pressure, and they need an answer within one session rather than over a week of data.

## User Journey Maps

### Primary User Journey: Answer a routing question with numbers

1. **Awareness:** a structural decision stalls — #147 asks what to move into a layer agents can see,
   and the honest answer is "we do not know what reaches them today".
2. **Consideration:** the alternatives are to reason about the loader again (wrong three times), to
   ask an agent what it sees (proven unreliable), or to record what happens.
3. **Adoption:** the maintainer turns the record on in their own repo with one explicit switch.
4. **Usage:** they work normally for a week. Every instruction load, skill invocation and agent
   dispatch appends a line. They then read a report: which files loaded, under which reason, how
   often, and how many bytes the always-loaded layer really costs.
5. **Retention:** the record stays on because it is nearly free and because the next structural
   question — and there is always one — starts with data instead of an argument.

### Secondary User Journeys

**Find the hook that is slowing the session down.** The diagnostician notices latency, sees the
built-in aggregate warning naming a tool but not a hook, switches on per-hook timing *for the
investigation*, reproduces the slowness, reads the per-hook durations, fixes or removes the culprit,
and switches timing back off. The instrument is temporary by design: an always-present timing layer
taxes every tool call for the life of every session, and most sessions never need it.

**Install the plugins and notice nothing.** The consumer installs or updates the TCS plugins. No
recording starts, no file is created, no command line is captured. If they later want the capability
they enable it themselves, deliberately, in their own configuration.

**Recovery: the record is empty when it should not be.** A user opens the log and finds nothing, or
finds it stopped days ago. They run a self-check that reports whether the hook is registered,
whether the harness is emitting, where the file is, and when it was last written — rather than
guessing, which is the failure mode this whole spec exists to eliminate.

## Feature Requirements

### Must Have Features

#### Feature 1: Instruction-load record

- **User Story:** As the framework maintainer, I want every instruction file load recorded with its
  reason, so that I can decide memory-bank routing from evidence rather than inference.
- **Acceptance Criteria:**
  - [ ] Given the record is enabled, When a session starts and loads the CLAUDE.md hierarchy, Then
        one entry per loaded file is appended, each carrying the file path, its scope, the load
        reason, and a timestamp.
  - [ ] Given a rule file scoped to a file pattern, When a matching file is read during the session,
        Then an entry is appended distinguishing that lazy load from a session-start load.
  - [ ] Given an imported file, When it is pulled in by another instruction file, Then the entry
        identifies the importing parent, so nested loading can be told apart from direct loading.
  - [ ] Given the record is disabled, When a session runs normally, Then no entry is written and no
        measurable work is performed for the feature.
  - [ ] Given a session ends, When the maintainer reads the record, Then they can tell which
        instruction files never loaded at all during that session.

#### Feature 2: One record, one schema

- **User Story:** As the framework maintainer, I want all four sources in a single line-oriented
  record, so that I can ask questions that span them without joining formats.
- **Acceptance Criteria:**
  - [ ] Given entries from different sources, When they are written, Then each carries a field
        naming its kind, plus a shared session identifier and timestamp in a single common format.
  - [ ] Given any entry, When it is read back by a standard line-oriented tool, Then it parses
        without a bespoke reader.
  - [ ] Given a long field, When it exceeds the size limit, Then it is truncated and the entry is
        explicitly flagged as truncated rather than silently shortened.
  - [ ] Given the record grows past its size threshold, When the next entry is written, Then older
        content is rotated out and total growth stays bounded without any scheduled job.

#### Feature 3: Safe by default, detailed by choice

- **User Story:** As a plugin consumer, I want the recording to be off unless I turn it on, so that
  updating a plugin never starts capturing my command lines.
- **Acceptance Criteria:**
  - [ ] Given a freshly installed or updated plugin, When a session runs, Then nothing is recorded
        and no record file is created.
  - [ ] Given a user enables recording without opting into detail, When a Bash tool call is
        recorded, Then the invoked program is retained but its arguments are not.
  - [ ] Given a user has not opted into detail, When any entry is written, Then it contains no file
        contents, no configured hook command strings, and no prompt or response text.
  - [ ] Given detail mode is enabled, When entries are written, Then the additional fields appear —
        and enabling it required an explicit, separate action from enabling recording at all.
  - [ ] Given any configuration, When entries are written, Then the record is stored outside the
        repository working tree, so it cannot be committed by a wildcard `git add`.
  - [ ] Given any configuration, When the feature operates, Then no data is transmitted off the
        machine — verified by inspection: no component performs a network call, and the design
        introduces no client, endpoint or service.

#### Feature 4: The report that answers the question

- **User Story:** As the framework maintainer, I want a report over the record, so that #147 has a
  denominator instead of an estimate.
- **Acceptance Criteria:**
  - [ ] Given a record covering normal work, When the report runs, Then it lists every instruction
        file that loaded, how often, and under which reasons.
  - [ ] Given the same record, When the report runs, Then it names the instruction files that are
        configured but never loaded.
  - [ ] Given the same record, When the report runs, Then it states the measured byte cost of the
        always-loaded layer, distinguished from conditionally loaded content.
  - [ ] Given an empty or stale record, When the report runs, Then it says so plainly and reports
        whether recording is currently enabled, rather than presenting an empty result as a finding.

### Should Have Features

#### Feature 5: Skill and agent firing record

- **User Story:** As the framework maintainer, I want skill invocations and agent dispatches in the
  same record, so that I can see which of the shipped skills and agents are ever actually used.
- **Acceptance Criteria:**
  - [ ] Given recording is enabled, When a skill is invoked, Then an entry names the skill.
  - [ ] Given recording is enabled, When a subagent is dispatched, Then an entry names its type and
        links it to the dispatching session.
  - [ ] Given a report over such a log, When it runs, Then it distinguishes skills that fired from
        skills that exist but never fired — the second set being the point. *(Satisfied by the same
        mechanism as F8; validation flagged the overlap. It stays because it is what makes F5 worth
        shipping, and is cross-traced to SDD-AC-18 rather than duplicated.)*

#### Feature 6: Hook duration, measured directly

- **User Story:** As the session diagnostician, I want to measure how long hooks actually take, so
  that I can tell whether hooks are the problem before diagnosing further.
- **What changed, and why:** the original story asked for this "without installing anything into the
  hook path" — a route that would have captured the harness's own telemetry from a redirected
  diagnostic run. A verification spike (T1.4, spec 018 README) found that route requires a locally
  running OTLP receiver, because `OTEL_LOGS_EXPORTER=console` is inert in the shipped harness. A
  receiver is itself standing infrastructure — exactly what this spec's Won't-Have list rules out
  ("no server component") — so the promise of zero installation is given up. Feature 6 now shares its
  mechanism with Feature 7: a timing wrapper installed only for the duration of an investigation and
  removed afterward.
- **Acceptance Criteria:**
  - [ ] Given a hook has been wrapped for an investigation, When it runs, Then its own duration is
        recorded, distinct from any other hook sharing its event.
  - [ ] Given the wrapper is not installed, When an ordinary session runs, Then no hook timing is
        captured and nothing extra runs in the hook path.
  - [ ] Given the wrapper is installed for an investigation, When it is configured, Then the
        configuration is documented together with an explicit statement of what it records and
        where — entirely local; nothing is transmitted anywhere.
  - [ ] Given a hook's duration is recorded, When the report shows it, Then the figure is labelled as
        that one hook's own duration, never as a total shared across hooks.

### Could Have Features

#### Feature 7: Per-hook attribution for an investigation

- **User Story:** As the session diagnostician, I want to attribute a slow batch to an individual
  hook, so that I can fix the right one.
- **Acceptance Criteria:**
  - [ ] Given a slow batch has been identified, When per-hook attribution is switched on, Then each
        hook's own duration is recorded separately.
  - [ ] Given attribution is switched on, When a hook runs, Then its exit status, its output and its
        ability to block are unchanged — the instrument must be transparent to the hook protocol.
  - [ ] Given attribution is switched off again, When sessions run, Then the wrapper is removed from
        hook registration and nothing remains in the hook execution path.
  - [x] Given the cheaper alternative of separating hooks so that each has its own matcher, When
        attribution is designed, Then that option is evaluated first and the reason for the choice
        recorded. **Satisfied.** T1.4 (spec 018 README) found that separating hooks onto distinct
        matchers does not produce separate measurement groups — arrangement B registered two entries
        under two distinct matcher strings and the harness still collapsed them into one
        `hook_execution_complete` record with `num_hooks=2`. Per-command matchers cannot serve as the
        mechanism; `timed-wrapper.sh` is used instead.

#### Feature 8: Usage report against the inventory

- **User Story:** As the framework maintainer, I want firing counts joined against the shipped
  inventory, so that "which of our 30+ skills are actually used" becomes answerable.
- **Acceptance Criteria:**
  - [ ] Given a record and the shipped inventory, When the report runs, Then it reports coverage as
        a fraction, naming the unused entries.
  - [ ] Given a skill that is listed but never chosen, When the report runs, Then it appears as
        unused rather than as absent, because a hook can only supply the numerator.

### Won't Have (This Phase)

- A live dashboard, web UI, server, database or Docker component. Every surveyed prior-art project
  has one; all of them are heavier than the question warrants.
- Any transmission off the machine, and any dependency on an external observability backend.
- A permanently installed per-hook timing layer. Measurement showed even a wrapper merely toggled off
  via an env var still taxes every hook invocation, because it remains a process registered in the
  path. The timing wrapper this spec ships (Features 6 and 7) is installed and then removed from hook
  registration for the duration of one investigation — never left in place switched off.
- Restructuring the memory bank. This spec produces the evidence; #147 makes that decision.
- Recording prompt or response text.
- Shipping the capability to plugin consumers in this phase. It stays repo-local configuration until
  it has answered a real question here; see Open Questions.

## Detailed Feature Specifications

### Feature: Safe by default, detailed by choice

**Description:** Recording is governed by two independent switches — one that turns recording on at
all, and one that adds sensitive detail. Both default to off. This mirrors the harness's own posture,
where telemetry is off by default and command-line detail requires a second, separate opt-in.

**User Flow:**
1. User enables recording for their own repo or user configuration.
2. System begins appending entries, with sensitive fields reduced.
3. User optionally enables detail mode as a separate action.
4. System begins including the additional fields, in that configuration only.

**Business Rules:**
- Rule 1: The shipped plugin default is "off". A default is not a personal preference — it is
  everyone's preference, and the consumer never asked for it.
- Rule 2: Redaction is implemented by this feature, never inherited. The harness's own detail
  switches govern only its own telemetry export; the payload our hooks receive arrives complete and
  unredacted regardless of them. A design that assumes otherwise silently records everything.
- Rule 3: Reduced mode keeps identity, timing and verb; it drops content and arguments. Concretely
  it keeps which program ran, not with which arguments; which file loaded, not what was in it.
- Rule 4: The record lives outside the repository tree, so exclusion from version control is
  structural rather than a matter of ignore-file discipline.
- Rule 5: Any retained free-text field is bounded in length, and truncation is marked in the entry.

**Edge Cases:**
- A user enables detail mode in a repo containing client work → the record still never leaves the
  machine, and deletion is a single removal of a known path, documented alongside the switch.
- Recording is enabled but the destination is unwritable → the session is unaffected; recording
  failure must never alter a hook's exit status, because a hook's exit status can block a tool call.
- A hook payload is malformed or unexpected → the entry records what it could and continues. The
  instrument must fail open; this repo has already been bitten by instrumentation that failed closed.
- Two sessions run concurrently in the same repo → entries from both are distinguishable by session
  identifier, and neither loses lines to the other.

## Success Metrics

### Key Performance Indicators

- **Adoption:** the record is enabled in this repo and stays enabled across a normal working week
  without anyone wanting to switch it off.
- **Engagement:** #147 is decided using the report, and the decision cites measured counts rather
  than estimates.
- **Quality:** recording overhead stays below roughly one millisecond per hook invocation, and below
  ten percent of the fastest real hook's own runtime. Beyond that the instrument distorts what it
  measures — and could itself trigger the harness's slow-hook warning.
- **Business Impact:** at least one concrete structural decision changes as a result of the data —
  a file moved, a rule re-scoped, or an unused skill retired. If a week of data changes nothing, the
  instrument has failed and should be switched off.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Instruction file loaded | path, scope, load reason, parent, triggering file, session, timestamp | The denominator #147 needs; distinguishes always-loaded from conditionally loaded |
| Skill invoked | skill name, session, timestamp | Which shipped skills are ever used |
| Agent dispatched | agent type, agent id, parent, session, timestamp | Which agents are used, and nesting |
| Hook duration (investigation only) | hook identity, matcher, duration, exit status | Whether a specific hook is the latency problem — the mechanism for both F6 and F7 after T1.4 found that batch capture from the harness would require a locally running collector |
| Recording state | enabled, detail mode, record location, last write | Lets the report distinguish "nothing happened" from "nothing was recorded" |

---

## Constraints and Assumptions

### Constraints

- **Target platform is macOS.** `/bin/bash` there is 3.2 and `date` is BSD, which has no nanosecond
  format — the obvious timestamp approach yields a non-numeric value and corrupts arithmetic
  silently. Any timing must avoid it.
- **The invoking shell is not necessarily bash.** Measured in this very environment: the tool shell
  is `zsh` while bash is also installed. Scripts must declare their interpreter explicitly.
- **Locale affects number formatting.** In a comma-decimal locale, formatted durations corrupt
  silently — an error already recorded in this repo's memory bank from a previous incident.
- **This is a plugin repository.** Anything shipped becomes other people's default.
- **Hook stdout and exit status are protocol.** Stdout is parsed, and an exit status of 2 blocks the
  tool call. Instrumentation must be transparent to both.
- **The underlying fields are experimental.** They are absent from the documented frontmatter and
  event lists and were read out of the shipped binary; the contract may move.
- **No new runtime dependency.** No collector process, no database, no service.

### Assumptions

- The `InstructionsLoaded` event, present since CLI 2.1.69, remains available; if it is withdrawn
  the primary feature has no substitute and the spec would need reopening.
- The harness continues to skip instruction-load hook work when no such hook is registered, which is
  what makes "costs nothing while off" true rather than aspirational.
- A week of ordinary work produces enough variety to be representative. If the week is unusual, the
  report is about that week — the record does not become truth by being written down.
- Reduced mode carries enough signal to answer #147. This is the assumption the first week tests:
  if the report cannot distinguish the cases that matter without command arguments, detail mode is
  widened deliberately and the gap is documented rather than pre-empted.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The instrument distorts the thing it measures — timing overhead inflates fast hooks and trips the harness's own slow-hook warning | High | Medium | A stated overhead budget, measured rather than assumed; per-hook timing is temporary and installed only for an investigation |
| A secret lands in the record via a Bash command line | High | Medium | Detail mode off by default; reduced mode keeps the program but not its arguments; the record never leaves the machine and its deletion is documented |
| A shipped default starts recording in consumers' repos | High | Low | Off by default in the plugin; enabling is an explicit local action; covered by its own acceptance criterion |
| The experimental contract changes and recording silently stops | Medium | Medium | The self-check reports whether recording is actually happening; an empty record is reported as "not recording", never as a finding |
| The record grows without bound | Medium | Medium | Size-based rotation with a fixed number of generations, following the existing precedent in this repo |
| Instrumentation failure breaks a hook and therefore a tool call | High | Low | Recording failures are swallowed; the wrapped hook's exit status, output and blocking behaviour pass through unchanged |
| A week of data changes no decision | Medium | Low | Named as the failure condition in the success metrics, with switching off as the response |

## Open Questions

All four decisions were taken at PRD review on 2026-09-06. None remain open; they are recorded here
with their trade-offs so the SDD implements a choice rather than rediscovering one.

- [x] **Where the record lives — per repo, outside the working tree.** Follows the existing
      precedent in this repo (spec 011, ADR-7): a per-repo directory under the plugin data location,
      never inside the tree. Keeps separate projects' records separate, and makes exclusion from
      version control structural rather than a matter of ignore-file discipline. Rejected: a single
      cross-repo record, which would answer "which skills do I ever use" more directly but mix
      client contexts into one file.
- [x] **Distribution — repo-local configuration for this phase, not shipped in a plugin.** #147
      needs the evidence here, not in consumers' repos. Shipping would bind us to a schema and a set
      of defaults before either has been used in anger, and every later change would become a
      breaking change for people who never asked for the feature. Revisit once the record has
      answered a real question.
- [x] **Harness hook timing — targeted diagnostic runs only.** ~~The no-infrastructure export mode
      writes to the terminal, which is unacceptable in an interactive session. Feature 6 therefore
      applies to deliberately started diagnostic runs with output redirected to a file, not to
      everyday sessions.~~ **Superseded 2026-09-06** (T1.4, spec 018 README): the "no-infrastructure
      export mode" does not exist — `OTEL_LOGS_EXPORTER=console` is inert in the shipped harness, and
      the only working export needs a locally running OTLP receiver, which this spec's Won't-Have
      list rules out. Feature 6 instead applies the same targeted-investigation posture to
      `timed-wrapper.sh`: installed only for a deliberate investigation, removed afterward, never run
      by default. Rejected, unchanged: filtering the noise out of interactive output, which adds a
      filter that can break and floods the terminal when it does.
- [x] **Detail level in this repo — start reduced.** Begin without command arguments or file
      contents. Widen only if the report proves too thin — at which point we will know *which* field
      was actually missing, rather than having recorded everything on the assumption that some of it
      would matter.

---

## Supporting Research

### Competitive Analysis

Four projects and one guide were surveyed. None covers instruction loading; all the dashboard-shaped
ones require standing infrastructure. `disler/claude-code-hooks-multi-agent-observability` (server,
SQLite, Vue UI; no licence file; feature-frozen since February 2026),
`TechNickAI/claude_telemetry` (replaces the `claude` command — ruled out as invasive; no commits in
roughly ten months), `simple10/agents-observe` (Docker and React), `NirDiamant/claude-watch`
(licence inconsistent between README and repository). `karanb192/claude-code-hooks` is the only
project found that touches the instruction-load event at all, for security scanning rather than
observability. Conclusion: build, do not adopt — the load-bearing primitive is a first-party event
nobody else is using.

### User Research

The evidence is this repo's own history rather than external interviews: three loader beliefs shown
wrong by measurement within a single session, an agent that reported "NONE" and then obeyed the rule
it had not seen, and 39 auto-memory entries recorded precisely because they recur, none of which
reach a subagent.

### Market Data

Not applicable — internal developer tooling for one repository and its consumers. The relevant
population is the maintainer plus the plugins' installed base.
