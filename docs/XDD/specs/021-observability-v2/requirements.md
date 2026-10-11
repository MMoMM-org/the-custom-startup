---
title: "Observability v2: typed skills, named subagents and git commands leave a record"
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
| specId | 021-observability-v2 |
| title | Observability v2: typed skills, named subagents and git commands leave a record |
| status | COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 35 |

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
| Open Questions | COMPLETE | Decisions taken before drafting are in the README Decisions Log |
| Supporting Research | COMPLETE | Full findings in `research.md` |

---

## Product Overview

### Vision

Every skill run, every subagent dispatch and every git command that changes a repository leaves a
local record that names what ran and who ran it, without recording what a person typed.

### Problem Statement

The observability record from specs 018 and 019 has three blind spots. In each one a mechanism runs
and leaves no trace, so the record reports absence where it has no evidence either way.

1. **Typed skills are invisible ([#165](https://github.com/MMoMM-org/the-custom-startup/issues/165)).**
   A skill the user types as `/plugin:skill` is never recorded; only skills the model chooses are.
   In this repository 0 of 8 typed invocations left a record. In Hashi, a repository driven almost
   entirely by typed commands, 23 typed invocations left 0 records, so its report printed `0/84`
   where the truth was `1/84`. For the many skills built to be typed, "never fired" cannot be told
   apart from "only ever typed".
2. **Named subagents are uncreditable ([#166](https://github.com/MMoMM-org/the-custom-startup/issues/166)).**
   A subagent dispatched with a name in an interactive session is recorded under that name
   (`impl-t41`, `spec-T2-3`), not under its type. 57 records in this repository name no inventory
   entry. The per-source figure printed `9/84`; the true figure, including the typed route, is
   `12/84`. Verified still live on 2026-10-11 with Claude Code 2.1.296.
3. **Commands are unattributable ([#172](https://github.com/MMoMM-org/the-custom-startup/issues/172)).**
   Nothing records which commands a session or subagent runs. During spec-020 a branch reset appeared
   in the reflog while three agents were live. One reported running it although its tools made that
   impossible; another reported being idle. Which agent ran it cannot be determined from any record.
   The guard bypass behind it ([#171](https://github.com/MMoMM-org/the-custom-startup/issues/171))
   was found only because someone read that reflog line by chance.

If this stays unsolved, coverage figures keep understating real use, so keep/drop/rework decisions
about skills and agents rest on wrong numbers. The next destructive git operation by an agent will
again be unattributable.

### Value Proposition

- **The existing record becomes trustworthy for the questions it was built to answer.** Coverage
  counts every route a skill can be invoked by and every dispatch under its real type.
- **An incident becomes traceable.** For any command that changes a repository, the record names the
  session and, inside a subagent, the agent, at the moment it was attempted. That includes attempts
  a guard then refused.
- **Nothing sensitive is added to the record.** What a person typed, a command's arguments and any
  value in a command line stay out of the record in every mode.
- **No new infrastructure.** It is the same opt-in, per-repository local file, switched on the same
  way.

## User Personas

### Primary Persona: Framework maintainer

- **Demographics:** owner of this repository; expert Claude Code user; maintains six plugins, 65
  skills and the agents that ship with them; macOS, `zsh`.
- **Goals:** decide which skills and agents to keep, drop or rework from evidence of where they
  actually ran; trust the per-repository coverage figure without cross-checking transcripts by hand.
- **Pain Points:** the report undercounts, and every correction so far has meant a manual join
  against session transcripts (#165, #166); a skill used only by typing looks unused.

### Secondary Personas

#### Incident investigator

- **Demographics:** the same person in a different role, after something went wrong: a lost branch
  tip, a popped stash, an unexpected reset. Works from the reflog and the record, often days later.
- **Goals:** name the session and agent that ran a given git command, and see whether it carried a
  guard override.
- **Pain Points:** the reflog shows the effect without an actor; agents' own reports are unreliable;
  the guard's override log says an override was used but not by whom.

#### Repository operator

- **Demographics:** whoever registered observability in a repository (spec 019's Operator), for
  example in Hashi or Kokoro; may be the maintainer or a collaborator.
- **Goals:** bring a registered repository up to the new version with one known command; never lose
  the recording that already works.
- **Pain Points:** an updated bundle that silently reports "current" for a repository whose
  registration is still the old one.

#### Plugin consumer who has not opted in

- **Demographics:** anyone with the plugins installed who never registered observability.
- **Goals:** a plugin update never starts recording anything, least of all their commands.
- **Pain Points:** none today; this persona exists so the guarantee is tested, not assumed.

## User Journey Maps

### Primary User Journey: Maintainer reviews coverage

1. **Awareness:** a report shows a skill as never fired that the maintainer remembers typing.
2. **Consideration:** the alternative is a manual join against transcripts, which works but costs an
   investigation each time.
3. **Adoption:** the maintainer updates the plugins and refreshes the registration in each tracked
   repository.
4. **Usage:** the maintainer runs the report; typed skills and named dispatches count under their
   real names, and the report says which route each firing came by.
5. **Retention:** the figure needs no correction, so it can be quoted in a keep/drop decision.

### Secondary User Journeys

#### Investigator attributes a git command

1. **Awareness:** the reflog shows a reset, stash pop or force-delete nobody admits to.
2. **Consideration:** the alternative is reading every live agent's transcript and trusting
   self-reports.
3. **Adoption:** recording is already on in the repository.
4. **Usage:** the investigator finds the command by time and verb in the record; it names the
   session, and the agent type and identity if a subagent ran it, plus any override it carried.
5. **Retention:** the answer is quick enough to look up after every surprise.

#### Operator brings a repository up to date

1. **Awareness:** after the plugin update, the setup status for the repository reports that its
   registration is outdated, naming what is missing.
2. **Consideration:** re-running setup is the only path; nothing updates on its own.
3. **Adoption:** the operator runs setup for that repository.
4. **Usage:** the new hooks are added beside the existing ones; the existing recording keeps working
   throughout.
5. **Retention:** the status reports current only when the repository's own registration is complete.

#### Consumer updates the plugins without opting in

1. **Awareness:** a routine plugin update.
2. **Consideration:** none.
3. **Adoption:** none; no registration exists.
4. **Usage:** sessions run as before.
5. **Retention:** nothing is recorded and nothing new runs.

## Feature Requirements

### Must Have Features

#### Feature 1: Typed skill invocations are recorded (#165)

- **User Story:** As the framework maintainer, I want a skill I typed to be recorded like one the
  model chose, so that "never fired" means never fired.
- **Acceptance Criteria:**
  - [ ] Given recording is on, When the user types `/<plugin>:<skill>` and it resolves to a skill,
    Then one skill record is written naming that skill and the route `typed`
  - [ ] Given recording is on, When the model invokes a skill through the skill tool, Then its
    record carries the route `tool`
  - [ ] Given a typed invocation with arguments, When it is recorded, Then the record says that
    arguments were present and never contains their text, in reduced and in detail mode
  - [ ] Given a typed command that does not resolve to anything, When it is submitted, Then no
    skill record is written
  - [ ] Given a typed command that resolves to something other than a skill (a custom command, an
    MCP prompt), When it runs, Then it is not counted as a skill firing

#### Feature 2: Subagent dispatches are recorded with their type (#166)

- **User Story:** As the framework maintainer, I want every subagent dispatch recorded under the
  type that ran, so that a named dispatch counts for the agent it actually was.
- **Acceptance Criteria:**
  - [ ] Given recording is on, When a subagent is dispatched with a name in an interactive session,
    Then a dispatch record names both the type and the given name
  - [ ] Given recording is on, When a subagent is dispatched without a name, Then the dispatch
    record names its type
  - [ ] Given a dispatch record and the later subagent-start record for the same subagent, When the
    report reads them, Then it counts one firing for the type, not one for the type and one for the
    name
  - [ ] Given a dispatch, When it is recorded, Then the task prompt is never recorded and the
    description is recorded only in detail mode

#### Feature 3: Git commands that change a repository are attributed (#172)

- **User Story:** As the incident investigator, I want every git command that can change a
  repository recorded with who attempted it, so that a destructive operation names its actor.
- **Acceptance Criteria:**
  - [ ] Given recording is on, When a session runs a git command that is not on the read-only list,
    Then one record names the git subcommand, the flag names used and the session
  - [ ] Given the command runs inside a subagent, When it is recorded, Then the record also names
    the agent's type and identity
  - [ ] Given the command runs in the main session, When it is recorded, Then the record says so
    rather than leaving the agent fields ambiguous
  - [ ] Given a command carrying a guard override token, When it is recorded, Then the record
    names each override and whether it stood in first position, and never records its value
  - [ ] Given a command a guard then refuses, When it was attempted, Then it is still recorded
  - [ ] Given a read-only git command (`status`, `log`, `diff`, `show`, and the rest of the list),
    When it runs, Then nothing is recorded
  - [ ] Given a git subcommand not on the read-only list, including one nobody anticipated, When it
    runs, Then it is recorded
  - [ ] Given a command line with values (tokens in assignments, credentials in URLs, header values,
    messages, paths), When it is recorded, Then none of those values appear in the record, in
    reduced or detail mode
  - [ ] Given a compound command with several git invocations, When it runs, Then each one that is
    not read-only is recorded
  - [ ] Given a non-git command, When it runs, Then nothing is recorded

#### Feature 4: The report credits every route and shows git activity by caller

- **User Story:** As the framework maintainer, I want the report to count typed skills and named
  dispatches correctly and to list git activity per caller, so that its figures need no manual
  correction.
- **Acceptance Criteria:**
  - [ ] Given typed and tool-route skill records, When coverage is computed, Then both count toward
    the skill and the report can show the route split
  - [ ] Given a named dispatch, When coverage is computed, Then it counts for its type
  - [ ] Given git records, When the report runs, Then it lists them by session and agent, with the
    subcommand and any overrides
  - [ ] Given records written before this change (no route, spawn names in place of types), When
    the report runs, Then it states that those records cannot be credited by type rather than
    inventing an attribution
  - [ ] Given a repository with no git records, When the report runs, Then it says no git activity
    was recorded and does not imply none happened

#### Feature 5: Registered repositories update without losing recording

- **User Story:** As the repository operator, I want setup to add the new recording beside the
  existing one and to tell me when a repository is behind, so that no repository silently stays on
  the old registration.
- **Acceptance Criteria:**
  - [ ] Given a repository registered by the previous version, When setup runs, Then the new hooks
    are added and every existing hook keeps working
  - [ ] Given several of our hooks on the same event with different scopes, When setup runs again,
    Then each is kept, none is duplicated and none is removed
  - [ ] Given the shared bundle is current but a repository's registration lacks a new hook, When
    the status is checked for that repository, Then it reports the repository as outdated and names
    what is missing
  - [ ] Given a foreign hook on the same event, When setup runs, Then it is left untouched
  - [ ] Given setup is removed from a repository, When removal runs, Then every hook of ours is
    removed and recorded data is kept

#### Feature 6: The record is protected at rest

- **User Story:** As the incident investigator, I want the record readable only by its owner and
  free of argument text, so that recording commands does not create a new exposure.
- **Acceptance Criteria:**
  - [ ] Given recording writes for the first time in a repository, When the file and its directory
    are created, Then only the owning user can read them
  - [ ] Given an existing record file readable by others, When the next record is written, Then its
    permissions are tightened to owner-only
  - [ ] Given a skill invoked through the tool with arguments, When it is recorded in reduced mode,
    Then the arguments are not in the record

### Should Have Features

#### Feature 7: The git guard costs almost nothing on non-git commands

- **User Story:** As the framework maintainer, I want the tcs-git-helpers guard to finish almost
  immediately for commands that are not git, so that adding a second hook on every command does not
  make sessions slower than today.
- **Acceptance Criteria:**
  - [ ] Given a non-git command, When the guard runs, Then it allows it and adds at most 5 ms at the
    median on macOS
  - [ ] Given any command the guard denies today, When it runs, Then the guard still denies it

### Could Have Features

#### Feature 8: Typed custom commands and MCP prompts are recorded

- **User Story:** As the framework maintainer, I want typed commands that are not skills recorded as
  their own kind of firing, so that repository-local commands such as Hashi's `/miyo-inbox` show up
  as used.
- **Acceptance Criteria:**
  - [ ] Given recording is on, When a typed command resolves to a custom command or an MCP prompt,
    Then one record names it and its kind, separate from skill records

### Won't Have (This Phase)

- **The full command line, argument values or prompt text, in any mode.** Decided 2026-10-11:
  subcommand and flag names are enough to attribute an operation.
- **Read-only git commands.** They change nothing.
- **The guard's verdict in the git record.** Hooks run in parallel; one cannot see another's
  decision. The record shows the attempt; whether it went through is answered by the guard's own log
  and the reflog.
- **Retroactive attribution of historical named records** through a join against session
  transcripts.
- **Tamper resistance.** An agent with shell access can edit or redirect the record; a record is
  evidence something happened, and a missing record is not proof it did not.
- **Fixing the guard bypass** ([#171](https://github.com/MMoMM-org/the-custom-startup/issues/171))
  or changing what the guard blocks.
- **Recording other shell commands** than git.
- **A dashboard, server, database, network transmission or pooled records** (unchanged from 018/019).
- **Shipping recording to plugin consumers by default** (unchanged from 018/019).
- **Checking whether container sync copies the record** (`sync-docker`), considered and not taken
  on 2026-10-11.

## Detailed Feature Specifications

### Feature: Git commands that change a repository are attributed

**Description:** When recording is on in a repository, every attempt to run a git command that is
not read-only produces one record per git invocation. The record names what kind of operation was
attempted and by whom, and nothing of what the command was applied to.

**User Flow:**
1. A session or one of its subagents is about to run a shell command.
2. If the command contains no git invocation, the system does nothing further.
3. For each git invocation in the command, the system decides whether its subcommand is on the
   read-only list; read-only invocations are skipped.
4. For each remaining invocation, the system records the subcommand, the flag names, the override
   tokens with their position, the session and, inside a subagent, the agent's type and identity.
5. The command then proceeds to the guards, which may still refuse it.

**Business Rules:**
- Rule 1: Recording happens before any guard decides, so an attempt is recorded whether or not it
  goes through.
- Rule 2: Only names are recorded: the git subcommand, flag names (`--hard`, `-D`, `--force`) and
  override variable names. Values of flags, positional arguments, assignments, URLs, messages and
  paths are never recorded.
- Rule 3: The read-only list is closed and explicit; every subcommand not on it is recorded.
- Rule 4: An override counts as in first position only when it would take effect as the guard reads
  it today; the record states position as observed, not as a judgement.
- Rule 5: A record failure never changes the outcome or output of the command or of any guard.
- Rule 6: When the git subcommand cannot be determined (for example, it is built at run time), the
  invocation is recorded as undetermined rather than skipped.

**Edge Cases:**
- Git invoked with global options before the subcommand (`git -C <dir> reset`) → recorded with the
  subcommand, not the option.
- Several git invocations chained in one command → one record each.
- Git mentioned inside a quoted message or a heredoc body (`git commit -m "explain git reset"`) →
  only the real invocation is recorded.
- A command run through a shell wrapper (`bash -c '…'`) → the git invocations inside it are
  recorded.
- A subcommand whose read-only status depends on its flags (`branch` lists, `branch -D` deletes;
  `stash list` reads, `stash pop` writes) → recorded unless the specific form is read-only.
- Recording is off → nothing happens, at the same cost as for any non-git command.

## Success Metrics

### Key Performance Indicators

- **Adoption:** every repository registered under 019 reports current within 7 days of the release,
  after one setup run each.
- **Engagement:** over the first 14 days after adoption in this repository, every typed skill
  invocation and every named dispatch found in the session transcripts has a matching record (target:
  100%, checked by the same transcript join used in #165 and #166).
- **Quality:**
  - The per-source coverage for this repository equals the transcript-derived figure, with 0
    unresolved agent records written after adoption.
  - 0 records contain a flag value, positional argument, assignment value or URL credential (checked
    by scanning the record).
  - The added cost on a non-git command is at most 5 ms at the median on macOS; a git record adds at
    most 15 ms.
- **Business Impact:** the next destructive git operation by an agent can be attributed to a
  session and agent from the record alone; the maintainer can quote per-repository coverage in a
  keep/drop decision without a manual correction.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Skill fired | skill, route (typed / tool), arguments present, session | Coverage by skill and route (F1, F4, Engagement) |
| Subagent dispatched | type, given name, session, dispatching agent if any | Credit named dispatches to their type (F2, F4, Quality) |
| Git operation attempted | subcommand, flag names, override names and position, session, agent type and identity or main session | Attribution (F3, Business Impact) |
| Registration status checked | repository, missing hooks | Adoption across registered repositories (F5) |
| Hook cost measured (opt-in timing) | hook, duration | Performance budget (Quality) |

---

## Constraints and Assumptions

### Constraints

- Recording stays opt-in per repository and off by default; detail mode stays a second, separate
  switch. Nothing turns either on during an update or at session start.
- Registration lives only in a repository's untracked local settings, never in shared settings.
- Records stay on the machine, per repository, outside the repository's tree.
- No prompt or response text, no file contents, no argument values (018 rules, tightened here for
  git and typed arguments).
- A recording failure never changes a hook's exit status or output.
- Must run on macOS's default bash 3.2 and on Linux; no new runtime dependency.
- Each registered hook costs about 3–5 ms per matching event even when recording is off (019); the
  git hook matches every shell command, so its non-git path must stay at that floor.
- The bundle installs independently of tcs-git-helpers and may not depend on its code.

### Assumptions

- Claude Code keeps the hook payloads measured on 2.1.296: a typed skill raises an expansion event
  naming the command; a subagent's tool calls carry its type and identity; a dispatch carries the
  type and the given name. The docs give no version for these fields.
- The expansion event names a plugin skill in a form the report can match against the inventory
  (with or without the plugin prefix); the SDD verifies this before relying on it.
- Interactive named subagents keep recording the spawn name at subagent start; the dispatch record
  is what makes them creditable.
- The maintainer re-runs setup in each registered repository after the release.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A secret reaches the record through an unforeseen command shape | High | Low | Record names only, never values (Rule 2); a test corpus of credential-bearing commands; record scan in the quality metric |
| The new hook on every shell command slows sessions | Medium | Medium | Non-git fast path at the 3–5 ms floor; the guard fast path (F7) removes more than the new hook adds |
| Claude Code changes a payload field and records go silently wrong | Medium | Medium | Record nothing rather than something wrong (018 CON-9); the report states an empty source as empty |
| Re-running setup drops an existing hook | High | Low | Per-scope registration with tests that run setup repeatedly over mixed registrations (F5) |
| Typed and tool routes double-count one invocation | Medium | Low | Each route records only its own invocation; the report counts firings by skill (F1, F4) |
| Readers mistake the git record for proof of what ran | Medium | Medium | Report wording: records show attempts; absence is not proof (Won't Have, tamper resistance) |

## Open Questions

- [x] How much of a git command is recorded? → names only, never values or the full line (2026-10-11).
- [x] Which git commands? → everything except a read-only list (2026-10-11).
- [x] Typed skills as a new kind or a route? → same skill record with a route (2026-10-11).
- [x] Which side findings are in scope? → file permissions, `args` in reduced mode, guard fast path;
  container sync check not taken (2026-10-11).

---

## Supporting Research

### Competitive Analysis

018 surveyed third-party Claude Code observability dashboards: all need standing infrastructure and
none records instruction loading. They were not re-surveyed for this spec. The tcs-git-helpers
override log is the only in-house precedent for recording commands. It is complementary: it records
that an override was consumed, not who used it.

### User Research

- Payload probe, 2026-10-11, Claude Code 2.1.296 (README § Context).
- Transcript joins in #165 (8 typed invocations here, 23 in Hashi, all unrecorded) and #166 (122
  agent records, all resolvable by transcript, 57 under spawn names).
- The spec-020 reset incident (#172) and the stash-pop incident (#156): both unattributable from
  records.
- Four research passes: requirements, technical, security and performance (`research.md`).

### Market Data

Not applicable: this is internal tooling for one maintainer's plugin ecosystem.
