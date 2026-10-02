---
title: "tcs-patterns selective install"
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
| specId | 020-tcs-patterns-selective-install |
| title | tcs-patterns selective install |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 36 (34 across the nine Must features, 2 for the Should-Have catalogue entry) |

### SectionStatus

| Section | Status | Detail |
|---------|--------|--------|
| Product Overview | COMPLETE | |
| User Personas | COMPLETE | Three personas, each with a journey |
| User Journey Maps | COMPLETE | Four journeys including the error path |
| Feature Requirements | COMPLETE | 9 Must, 3 Should, 2 Could, 4 Won't |
| Detailed Feature Specifications | COMPLETE | Scan and propose, the most complex feature |
| Success Metrics | COMPLETE | Five KPIs, all measurable without new instrumentation |
| Constraints and Assumptions | COMPLETE | |
| Risks and Mitigations | COMPLETE | Seven risks |
| Open Questions | COMPLETE | Four, all deferred to SDD by design |
| Supporting Research | COMPLETE | Detection study against six repositories |

---

## Product Overview

### Vision

A repository is offered the handful of pattern skills that fit the code actually in it, and
carries nothing it will never use.

### Problem Statement

`tcs-patterns` ships 21 pattern skills and installs all of them, in every repository, regardless
of stack. A TypeScript project receives `go-idiomatic`, `python-project` and `obsidian-plugin`.

The plugin's own manifest has promised otherwise since it shipped — both
`plugins/tcs-patterns/.claude-plugin/plugin.json:4` and `.claude-plugin/marketplace.json:30` read
"install only the patterns relevant to your stack" — and no mechanism has ever delivered it. It is
a promise held by nothing, the same defect class spec 019 documented.

The cost is not what it appears to be. Claude Code **rations the skill listing**, which nothing in
TCS accounted for. A live session on CLI 2.1.286 warns:

```
[WARN] Skill listing over budget: 112 skills, 40191 chars > 30000 budget
       -- descriptions will be truncated.
```

The defaults behind that warning are `skillListingBudgetFraction` 0.01 of the context window
measured in characters -- 8000 on a 200k-class model and 30000 in a 1M-context session, both
observed -- and `skillListingMaxDescChars` 1536 per
description. `tcs-patterns` contributes 5918 of the 21128 characters the six TCS plugins put into
that listing — 28% of the TCS share, roughly 15% of the whole.

**The damage is description quality, not token cost.** Measured 2026-10-02, readings reproducing
to ~3 tokens:

| Measurement | Result |
|---|---|
| Disabling `tcs-patterns` entirely, today | saves ~220 tokens (median of 8 interleaved runs) |
| Raising the listing budget 0.01 → 0.1 | adds 7127 tokens |

The saving is small *because* the listing is already clipped: space freed by removing one
description is immediately consumed by another. The 7127 tokens are the amount of listing being
discarded in every session right now. So the 21 descriptions are best understood as 5918
characters of pressure that shorten every other skill's description — including the routing
contracts written into `tcs-team` on 2026-10-01, which exist precisely to stop the model picking
the wrong skill.

The consequence of not solving it: every skill in the ecosystem is described to the model in
truncated form, and the truncation is invisible — no error, no warning in normal use, and the
model simply routes on less information than was written for it.

### Value Proposition

Three things no alternative delivers together:

1. **Relevance without manual invocation.** A pattern installed into a repository stays in the
   model-facing listing (measured +620 tokens versus absent), so it is still auto-routed. The
   alternative — flagging pattern skills out of the listing inside the plugin — works
   (measured −628 tokens, the entry disappears) but costs auto-routing entirely: a flagged skill
   must be typed by hand every time. Relevance is kept, noise is dropped.
2. **Per-skill control that a plugin can never offer.** `skillOverrides`
   (`on` | `name-only` | `user-invocable-only` | `off`) is ignored for plugin skills — the
   resolver returns `"on"` early when the skill's source is a plugin, measured as zero effect in
   all three plausible key formats. On a repository skill it works precisely: `off` lands within
   4 tokens of not-installed, `name-only` within 3. Installing into the repository therefore hands
   the consumer a dial the plugin cannot expose.
3. **The promise, finally kept.** The manifest's claim becomes true rather than aspirational.

## User Personas

### Primary Persona: Repository owner adopting patterns

- **Demographics:** Working developer, runs Claude Code daily in one or more project repositories,
  comfortable with git and plugin installation, not interested in studying how the skill registry
  is assembled.
- **Goals:** Get the pattern guidance that matches this codebase, in one short interaction, and
  not think about it again until something changes. Success looks like: a handful of relevant
  patterns, no questions they could not answer in two seconds, nothing installed they would have
  to mentally filter out later.
- **Pain Points:** Today the choice is binary — install `tcs-patterns` and take 21 patterns, or
  install nothing. Nothing in the product acknowledges that most of the 21 do not apply, and
  nothing tells them that the irrelevant ones are shortening the descriptions of the relevant
  ones.

### Secondary Personas

**Pattern maintainer.** Edits the 21 pattern bodies and needs a fix to reach the repositories that
installed that pattern. Distinct goal: propagation and knowing which copies are stale. Distinct
pain: with copies distributed across repositories, a bug fixed centrally silently does not reach
anyone, and hand-patching each consumer is the alternative — the exact problem the bundle
versioning pattern was created for in spec 012.

**Inheriting teammate.** Clones a repository where someone else already ran the setup, never runs
it themselves, and simply finds the patterns present. Distinct goal: not being surprised — they
need the selection to be visible and reviewable rather than appearing as unexplained files, and
they must not be prompted to re-do a decision the team already made.

## User Journey Maps

### Primary User Journey: First selection in a repository

1. **Awareness:** They install or update `tcs-patterns` and the plugin tells them there is a setup
   step; or they notice their repository has no pattern skills and look for how to get them.
2. **Consideration:** The alternatives are taking all 21 (the old behaviour), hand-copying the
   two or three they know they want, or skipping patterns entirely. The criterion that matters is
   effort: anything that feels like an interview loses to hand-copying.
3. **Adoption:** They run the setup, see a proposal that is visibly derived from their own
   repository — named files and dependencies, not generic advice — and recognise that it got the
   stack right.
4. **Usage:** They confirm or adjust the selection. The patterns are installed and the setup
   offers to commit them. From then on the relevant patterns route automatically, like any other
   skill.
5. **Retention:** When a pattern they installed changes upstream, the next session says so and
   names the one-line command. Nothing else ever asks them anything.

### Secondary User Journeys

**Updating after an upstream change.** A session begins; the drift advisory names the patterns
whose versions moved and the command to run. They run it, see which files would change, and
accept. Patterns they did not install are never mentioned.

**Consulting a pattern without installing it.** They want one look at a pattern that does not
belong in this repository — reading `event-sourcing` while deciding whether the architecture is
worth it. They ask for it by name and get the full body, with nothing added to the repository and
nothing added to the listing beyond the single catalog entry.

**Error and recovery: the name is already taken.** The repository, or the user's own global skill
directory, already contains a skill under a name the selection wants — `testing` and
`observability` are generic enough for this to be ordinary. The setup detects it before writing
anything, explains which name collides and with what, and does not silently create a second skill
answering to the same name. The user chooses how to resolve it; nothing is overwritten without
their say.

## Feature Requirements

### Must Have Features

#### Feature 1: The plugin stops shipping pattern skills

- **User Story:** As a repository owner, I want the plugin to stop putting 21 pattern descriptions
  into every session so that the skills I actually use are described to the model in full.
- **Acceptance Criteria:**
  - [ ] Given `tcs-patterns` is installed at the new major version, When a session starts, Then the
        plugin contributes no more than 2 skill descriptions to the listing.
  - [ ] Given the pattern catalogue has moved, When the repository's skill and agent inventory is
        walked, Then all 21 patterns are reported as catalogue entries and none as unreachable
        skill files.
  - [ ] Given a pattern body referenced a file outside its own directory, When it is relocated,
        Then every such reference either resolves from the new location or is replaced by an
        inline citation — no reference is left pointing outside the pattern.
  - [ ] Given the relocation is a rename and not a rewrite, When the change is reviewed, Then every
        pattern file is reported by git as a rename with its content unchanged.

#### Feature 2: Scan the repository and propose a selection

- **User Story:** As a repository owner, I want the setup to read my repository and tell me which
  patterns fit it, so that I confirm a decision rather than make one from a list of 21.
- **Acceptance Criteria:**
  - [ ] Given a repository whose stack is decidable from files alone, When the scan runs, Then
        every pattern in the decidable set is proposed with the specific file or dependency that
        justified it.
  - [ ] Given a repository with a workspace layout whose root manifest declares no dependencies,
        When the scan runs, Then signals in nested manifests are still found, and vendored
        dependency directories are not scanned.
  - [ ] Given a repository whose stack none of the 21 patterns address, When the scan runs, Then no
        pattern is proposed and the setup says so plainly rather than proposing a default.
  - [ ] Given a proposal is presented, When the user reads it, Then each entry shows what it costs
        the listing, so the trade-off is visible at the moment of choosing.
  - [ ] Given a pattern applies to nearly every repository with a test suite, When the proposal is
        assembled, Then it is not surfaced as a discriminating recommendation.

#### Feature 3: Ask only what the repository cannot answer

- **User Story:** As a repository owner, I want to be asked at most a few questions, only when the
  answer cannot be read from my code, so that setup feels like initialisation and not an
  interview.
- **Acceptance Criteria:**
  - [ ] Given a repository with no server framework in its runtime dependencies and no test
        framework, When the setup runs, Then zero questions are asked.
  - [ ] Given a repository where intent cannot be inferred, When the setup runs, Then no more than
        three questions are asked in total, each allowing multiple answers.
  - [ ] Given a question's subject is absent from the repository, When the setup runs, Then that
        question is skipped entirely rather than asked and answered "none".
  - [ ] Given every question has been answered, When the selection is assembled, Then each of the
        21 patterns has been decided either by a file signal or by exactly one question — none is
        left undecided and none is decided twice.

#### Feature 4: Install the selection into the repository

- **User Story:** As a repository owner, I want the chosen patterns placed in my repository so that
  they route automatically here and nowhere else.
- **Acceptance Criteria:**
  - [ ] Given a confirmed selection, When installation completes, Then each chosen pattern is
        present in the repository's skill directory with its full supporting material, and nothing
        unchosen is present.
  - [ ] Given installation completes, When the next session starts, Then each installed pattern
        appears in that session's skill listing.
  - [ ] Given installation completes, When the user is shown the result, Then they are offered the
        choice to commit the new files and the setup does not commit on their behalf.
  - [ ] Given the user declines to commit, When the setup finishes, Then the files remain in place
        uncommitted and the setup says so.

#### Feature 5: Refuse to create a duplicate name

- **User Story:** As a repository owner, I want to be told when a pattern's name is already taken,
  so that I never end up with two skills answering to one name.
- **Acceptance Criteria:**
  - [ ] Given a name in the selection already exists as a skill in the repository, When the setup
        reaches the write step, Then nothing is written for that name and the collision is reported
        with both locations.
  - [ ] Given a name in the selection already exists as a skill in the user's global skill
        directory, When the setup reaches the write step, Then the same refusal and report apply.
  - [ ] Given a name in the selection is also a reachable plugin skill, When the setup reaches the
        write step, Then the same refusal and report apply.
  - [ ] Given a collision is reported, When the user resolves it, Then the remaining
        non-colliding patterns can still be installed without re-running the scan.

#### Feature 6: Record what was installed, per pattern

- **User Story:** As a pattern maintainer, I want each repository to record which patterns it holds
  and at which version, so that a fix can be known to have reached it or not.
- **Acceptance Criteria:**
  - [ ] Given patterns are installed, When installation completes, Then a single record in the
        repository names every installed pattern with its version.
  - [ ] Given a pattern is installed later, When installation completes, Then the existing record
        gains that pattern and the other entries are unchanged.
  - [ ] Given the record is read by a second party, When they compare it against the catalogue,
        Then they can determine per pattern whether the installed copy is current, without
        inspecting file contents.

#### Feature 7: Tell the user when an installed pattern has moved on

- **User Story:** As a repository owner, I want a session to tell me when a pattern I installed has
  changed upstream, so that I am not silently running an old copy.
- **Acceptance Criteria:**
  - [ ] Given an installed pattern's version is behind the catalogue, When a session starts, Then
        the advisory names that pattern, both versions, and the command to run.
  - [ ] Given a pattern changed upstream that this repository did not install, When a session
        starts, Then nothing is said about it.
  - [ ] Given all installed patterns are current, When a session starts, Then no pattern advisory
        appears at all.
  - [ ] Given the repository has no installed patterns, When a session starts, Then no pattern
        advisory appears and the user is not prompted to run the setup repeatedly.

#### Feature 8: Update installed patterns

- **User Story:** As a repository owner, I want to bring my installed patterns up to date in one
  step, without being asked to re-make my selection.
- **Acceptance Criteria:**
  - [ ] Given installed patterns are behind, When the update runs, Then only those patterns are
        refreshed and the selection is otherwise unchanged — no scan, no questions.
  - [ ] Given an installed pattern was edited locally, When the update would overwrite it, Then the
        user is told the copy diverged and asked before anything is replaced.
  - [ ] Given the update completes, When the record is read, Then every refreshed pattern's version
        matches the catalogue.

#### Feature 9: Reading a pattern cannot be bypassed by stale distribution

- **User Story:** As a pattern maintainer, I want a changed pattern to be impossible to ship
  without a version change, so that no repository can be stale without being detectable.
- **Acceptance Criteria:**
  - [ ] Given a change to any pattern file, When the change is proposed for merge without a
        corresponding version change, Then the merge is blocked with the reason.
  - [ ] Given a change to any pattern file with its version changed, When the change is proposed
        for merge, Then the gate passes.
  - [ ] Given a change that touches no pattern file, When it is proposed for merge, Then the gate
        does not apply.

### Should Have Features

- **Consulting a pattern without installing it.** A single catalogue entry that serves any of the
  21 bodies on request. Significantly improves the experience for the "one look at it" case and
  preserves what the old all-21 install made possible, at one description's cost instead of 21.
  Not critical: without it the patterns remain readable in the plugin's own files.
  - [ ] Given a pattern is named, When it is requested through the catalogue, Then its full body is
        returned without anything being written to the repository.
  - [ ] Given a name that is not one of the 21, When it is requested, Then the available names are
        listed rather than a silent empty result.
- **Removing a pattern.** Taking a pattern back out, with its record entry, in one step rather than
  by hand.
- **Non-interactive update.** The update path usable without prompts, for a maintainer sweeping
  several repositories.

### Could Have Features

- **Suggesting the per-skill dial.** After installation, pointing out that a rarely-used installed
  pattern can be reduced to a name-only listing entry or switched off without being removed.
- **Explaining the scan.** A mode that reports every signal found and every rule that did not fire,
  for diagnosing a proposal the user disagrees with.

### Won't Have (This Phase)

- **Getting the skill listing under budget.** 40191 characters falls to roughly 34300 against a
  budget between 8000 and 30000 depending on the model. `tcs-team` (4924), `tcs-helper` (4460)
  and `tcs-workflow` (4401) are each
  comparable to `tcs-patterns`, so being under budget requires the same treatment across all four
  or a raised budget fraction. This phase removes the largest single contributor and no more.
- **Judging the 21 patterns on content.** Merging overlapping patterns, or dropping ones nobody
  wants, is a content decision across plugins and not a distribution fix.
- **Changing any pattern's invocability flag.** The patterns stay as they are, bodies untouched
  apart from relocation and the outward references that relocation breaks.
- **Applying this to the other three plugins.** Named as the follow-on, deliberately not started
  here.

## Detailed Feature Specifications

### Feature: Scan the repository and propose a selection

**Description:** The setup derives a proposal from the repository itself. Eight of the 21 patterns
are decidable from files alone and are proposed with their evidence. The remaining 13 express an
architectural *intent* rather than a stack *fact*; for those, file signals decide only whether a
question is worth asking, and three gated questions settle them. The proposal is always shown and
always confirmable — the scan leads, it does not decide.

**User Flow:**

1. User runs the setup in a repository.
2. System walks the repository for manifests and configuration, including nested ones, skipping
   vendored dependency directories.
3. System proposes the patterns decidable from what it found, each with the file or dependency
   that justified it.
4. System asks only those of the three questions whose subject actually exists in the repository.
5. User confirms or adjusts the selection.
6. System checks every chosen name for collisions, then installs, writes the record, and offers to
   commit.

**Business Rules:**

- A pattern is proposed automatically only when a file or dependency decides it. Intent is never
  inferred from a weak signal.
- A question is asked only when its subject is present. Absence skips the question; it does not
  produce a question whose answer is "none of these".
- Each of the 21 is decided exactly once — by a file signal or by one question, never both.
- A runtime dependency and a development dependency are not the same signal. A server framework
  present only to drive a test harness is not a service.
- Nothing is written until every chosen name has been checked for collision.
- The user confirms the final selection. No pattern is installed on a scan's authority alone.

**Edge Cases:**

- A workspace repository whose root manifest declares no dependencies, with the real signals in
  nested manifests → nested manifests are walked; the signal is found.
- A repository with a test directory named for UI but containing no UI assertions → the UI testing
  patterns do not fire; directory names are not evidence.
- A repository using session tokens and password hashing but no federated-identity protocol → the
  OAuth/OIDC pattern does not fire; those libraries are not protocol evidence.
- A repository that hand-rolled an event store with no distinctive dependency → not auto-proposed;
  reachable only through the architecture question, which is why that question exists.
- A repository with no test framework at all → the test-quality question is skipped and no testing
  pattern is proposed.
- A repository in a stack none of the 21 cover → nothing is proposed, stated plainly.
- A repository where both common virtual-environment directory names appear → both are recognised.

## Success Metrics

### Key Performance Indicators

- **Listing contribution:** `tcs-patterns` contributes at most 2 skill descriptions to a session,
  down from 21 — measured by the repository's own skill and agent inventory walk, and confirmed
  against a session's listing.
- **Interaction cost:** a repository with no server framework and no test framework completes setup
  with zero questions; no repository is asked more than three.
- **Detection correctness:** every fixture in the detection suite is classified exactly as
  specified, including each of the seven known traps and at least one stack that must yield
  nothing.
- **Selection size:** a repository ends up with the patterns that match it — measured as the
  installed count being a strict subset of 21 in every validated stack, and the proposal containing
  no pattern the stack contradicts.
- **Propagation:** a change to one pattern raises an advisory only in repositories that installed
  that pattern, and in all of them.

### Tracking Requirements

No new instrumentation is required. Three records already exist or are produced by this work:

| Event | Properties | Purpose |
|-------|------------|---------|
| Setup invoked | existing skill-invocation record | Shows whether the setup is actually reached, via the observability record that spec 019 rolled out |
| Selection installed | the per-pattern record written into the repository | Is itself the evidence of what was chosen and at which version; readable by a second party without inspecting contents |
| Drift advisory raised | installed version versus catalogue version | Confirms propagation works, and that silent staleness is not possible |

---

## Constraints and Assumptions

### Constraints

- **The listing budget is not ours to set.** Both the budget fraction and the 1536-character
  per-description cap are Claude Code defaults. This work reduces pressure on the budget; it
  cannot raise it for anyone.
- **Per-skill control exists only outside plugins.** The per-skill override is ignored for plugin
  skills. Any design that keeps the patterns inside the plugin forfeits it.
- **There is no name shadowing.** A repository skill and a plugin skill with the same name are
  both listed — measured as a 3-token difference between a colliding and a free name, which is
  noise. Collision must be prevented, because it will not be resolved for us.
- **Breaking change.** The patterns stop being plugin skills, so anything that invoked them that
  way stops working. A sweep this session found no agent declaring a pattern as a preload and no
  reference invoking one, so the blast radius is users' habits rather than code.
- **Three pattern files reference material outside their own directory** and will break on
  relocation; one of those references already resolves to nothing from the installed plugin.
- **One pattern is coupled to a plugin-shipped write-time guard** whose detection signal is the
  same one the scan uses. The guard stays in the plugin when the body moves.
- **Version numbers are set by CI, never by hand.**
- **Distribution must follow the established bundle versioning pattern** (spec 012), which already
  has three instances in this repository, rather than inventing a fourth mechanism.
- **Real repository names and paths must not appear in any specification document, commit message
  or test fixture.** They belong only in the gitignored sources file.

### Assumptions

- A developer will accept a short confirmation step in exchange for a relevant selection. If the
  interaction grows past three questions this assumption fails and hand-copying wins.
- Repositories change stack rarely enough that a selection made once stays roughly right, with the
  update path handling upstream change rather than stack change.
- A team wants one shared selection per repository rather than one per developer, which is why
  committing is offered rather than suppressed.
- The eight auto-detectable patterns cover the common cases well enough that most repositories see
  a useful proposal before any question is asked.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| The detection rules were authored and graded by the same party, so "no false positives across six repositories" is self-assessment | High | High | A fixture-based detection suite is an acceptance criterion, not a nice-to-have: one synthetic fixture per rule, every one of the seven traps, and at least one stack that must yield nothing. A second party must be able to run it and see the same verdicts. |
| A wrong proposal teaches the user to distrust the setup and skip it | High | Medium | The proposal always shows its evidence and is always confirmed by the user. Nothing installs on the scan's authority. Patterns with near-zero discriminating power are not surfaced as recommendations. |
| Two skills answer to one name after installation | High | Medium | Collision check against all three namespaces before any write, with the write refused and reported. This is the defect that was fixed in `tcs-team` the day before this spec. |
| Copies distributed across repositories go stale silently | High | Medium | Per-pattern versions in the repository record, a session-start advisory scoped to installed patterns only, and a merge gate that blocks a pattern change without a version change. |
| The user edits an installed pattern and an update overwrites their work | Medium | Medium | Divergence is detected and the user is asked before anything is replaced. |
| Users who relied on invoking patterns from the plugin lose that access | Medium | Medium | The catalogue entry serves any pattern on request without installation. The change ships as a major version with the removal stated. |
| The work is read as "we reduced token cost" and the real benefit is missed | Medium | High | The PRD states the measured saving is ~220 tokens and that the benefit is description quality. No acceptance criterion claims a token saving. |

## Open Questions

Each of these is a design decision with a real trade-off, deliberately left to the SDD rather than
pre-empted here.

- [ ] Do installed patterns carry a name prefix? A prefix prevents collisions structurally but
      costs readability in the slash menu and in per-skill override entries. Plain names read
      better and make collisions possible, which Feature 5 then has to handle.
- [ ] When an installed pattern has been edited locally and the catalogue moves on, what is offered
      besides overwrite and skip — is a diff or a side-by-side worth the machinery?
- [ ] Should the setup offer a selection for a stack it does not recognise, or install nothing? The
      PRD requires it to say so plainly; whether it then offers the stack-independent patterns is
      open.
- [ ] Does the repository record live beside the installed skills or in the plugin's own data
      directory? Beside them is visible and reviewable; elsewhere keeps the skill directory clean.

---

## Supporting Research

### Competitive Analysis

The nearest comparable interactions are initialisation commands that scan a project and propose a
configuration — linter and framework initialisers, and Claude Code's own project initialisation.
What they have in common, and what sets the bar here: they read the project first, propose rather
than interrogate, and keep the questions to the few things the files cannot answer. The failure
mode they avoid is the long questionnaire, which users abandon in favour of hand-editing a config.
That is the standard this setup is held to by Feature 3.

### User Research

A detection study was run against six real repositories with deliberately different stacks: a
TypeScript workspace monorepo containing a tool-server package and a browser-extension package; a
Python web service with server-rendered pages, cookie sessions and a hand-rolled append-only event
store; a Python command-line machine-learning pipeline with no tests at all; a TypeScript editor
plugin with unit tests over pure functions; a Swift desktop application, included as a stack none
of the 21 patterns address; and this plugin ecosystem itself.

Findings that shaped the requirements:

- Eight patterns are decidable from files alone. Thirteen express intent and are not.
- The 13 are settled by three questions, each gated on its subject being present, each allowing
  multiple answers. A repository with no server framework and no tests is asked nothing.
- One pattern fires in nearly every repository with a test suite and therefore carries almost no
  information; one has no repository signal at all and is reachable only by asking.
- Seven specific traps were found, each against a real repository: a near-universal signal with no
  discriminating power; UI testing inferred from a directory name rather than from rendering
  evidence; federated identity inferred from session-token and password-hashing libraries; a
  development dependency read as a runtime one; a workspace root whose manifest declares nothing
  while the real signals sit several directories down; two architectural patterns that are
  routinely hand-rolled with no distinctive dependency; and a virtual-environment check that
  recognised only one of the two common directory names.
- Across the six repositories the rules produced no false positives and missed nothing, and the
  stack that no pattern covers correctly yielded nothing — but this was the rules' author
  assessing its own work, which is why the fixture suite is a requirement and not a formality.

### Market Data

Not applicable. This is internal tooling with a known, single-digit user population; the relevant
quantities are the measured listing figures in the Problem Statement, not market size.
