---
title: "Observability denials report"
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
The repository owner can see, per repository and per week, which of the agent's tool calls were denied or blocked and by what, and can tell a rule that needs an allowlist entry or a fix from a rule that is doing its job, without reading transcripts by hand.

### Problem Statement
TCS guard hooks deny agent actions every week: in the local transcripts of this machine, 641 hook denies across Claude Code 2.1.114–2.1.332, `tcs-git-helpers` alone 271 times with rules such as `BRANCH_FROM_UNFINISHED` (148) and `DESTRUCTIVE_CHECKOUT` (94). Add to that 206 rejected permission prompts, 63 auto-mode classifier blocks and a few hundred sandbox-style failures (research.md). None of it is recorded anywhere a person reviews:

- The observability recorder sees only `PreToolUse`. Hooks run in parallel, so it cannot see another hook's decision; spec 021 records a denied command as an attempt, never as a denial.
- Claude Code offers no event for a hook deny, a settings deny rule or a rejected prompt; `PermissionDenied` covers only the auto-mode classifier.
- The only trace is the session transcript, 5 GB here, which nobody reads.

Consequence: the review loop the enterprise coding-agent guide asks for (run a baseline, review denials and blocks, then add allowlist entries instead of weakening denies) cannot happen. A rule that fires 148 times a month on legitimate work looks the same as one that never fires, and the cheap reaction to friction is the override or a weaker rule.

### Value Proposition
- Uses data that already exists: no new recording, no wait of weeks before the first report, history back to the oldest transcript.
- Fits the existing `report.py` run and its per-source sections, so it sits next to the load, fire and git views the owner already reads.
- States its own limits: what cannot be seen and which counts are low-confidence, instead of implying completeness.

## User Personas

### Primary Persona: Repository owner tuning guard rules
- **Demographics:** Maintains TCS plugins and the repositories they run in; expert in git, shell and Claude Code configuration; runs `report.py` from a terminal.
- **Goals:** Find denials that repeat on legitimate work and fix them with an allowlist entry or a narrower rule; confirm that denials of dangerous actions keep happening (the rule is doing its job); see the effect of a rule change week by week.
- **Pain Points:** Denials leave no reviewable trace; counting them means grepping gigabytes of JSONL with ad-hoc scripts that miss duplicates and noise (research.md: 58 duplicate hook denies, 666 false "Operation not permitted" hits); cannot tell main-session friction from subagent friction.

### Secondary Personas

#### Incident reviewer
- **Demographics:** The same owner, or a teammate, after something went wrong (an unwanted push, a blocked deployment); comfortable with transcripts but needs a starting point.
- **Goals:** Find when and in which session a given kind of denial happened, to open that transcript and reconstruct what the agent tried.
- **Pain Points:** Transcripts are per session, unindexed and large; there is no list of "denials of kind X, with session and time".

## User Journey Maps

### Primary User Journey: Review denials after a baseline period
1. **Awareness:** After two to four weeks with a new guard or rule, the owner wants to know whether it causes friction, or a session hit a denial that felt wrong.
2. **Consideration:** Alternatives are grepping transcripts by hand or reading `git-audit` override events, which show overrides but not denials.
3. **Adoption:** The owner sets `denials = true` for the repositories they want covered in the untracked locations config, once.
4. **Usage:** Runs the report; reads per source the denials by category, by hook and rule, main session vs subagent, the weekly trend and the top repeated denials with their override counts; picks candidates and fixes rules or adds allowlist entries.
5. **Retention:** Runs the report again after the change and checks the weekly trend for that rule.

### Secondary User Journeys

#### Reconstruct an incident
1. **Awareness:** Something unexpected happened or was blocked.
2. **Usage:** The reviewer runs the report for the period, finds the denial kind in the top list, takes its most recent session id and time, and opens that transcript.

#### Section not enabled or nothing found
1. **Usage:** The owner runs the report for a source without `denials = true`, or with no transcripts in reach, or with no denials in the period.
2. **Outcome:** The section says which of these it is, and what to change, instead of showing zero or nothing.

## Feature Requirements

### Must Have Features

#### Feature 1: Per-source opt-in and enablement state
- **User Story:** As the repository owner, I want transcript reading to happen only for repositories I enabled, so that turning on a report never reads sessions I did not choose.
- **Acceptance Criteria:**
  - [ ] Given a source without `denials = true`, When the report runs, Then its denials section states "not enabled" and how to enable it, and no transcript of that source is read
  - [ ] Given a source with `denials = true` and no transcript in reach of any of its homes, When the report runs, Then the section states that no transcripts were found and names the places searched
  - [ ] Given `denials` with a value other than true or false, When the report runs, Then it stops with a config error naming the source and the value, as for every other invalid key in that file

#### Feature 2: Denial classification
- **User Story:** As the repository owner, I want each denied or blocked tool call counted under what denied it, so that I can act on the right rule or setting.
- **Acceptance Criteria:**
  - [ ] Given an error tool result whose text is a hook deny, When it is classified, Then it counts as "hook deny"; for `tcs-git-helpers` each listed rule is counted under that hook and rule, and for other known hook messages under that hook
  - [ ] Given a hook deny whose message matches no known hook, When it is classified, Then it counts as "hook deny, unattributed" and is not dropped
  - [ ] Given a rejected permission prompt on an AskUserQuestion or ExitPlanMode call, When it is classified, Then it is not counted as a denial
  - [ ] Given a rejected permission prompt on any other tool, When it is classified, Then it counts as "prompt rejected" with the tool name
  - [ ] Given an auto-mode classifier block in the current or the earlier wording, When it is classified, Then it counts as "classifier block" with its reason category
  - [ ] Given a built-in safety check, a "permission to use … has been denied" result, a worktree isolation block, an "Operation not permitted" failure or a network 403 tunnel failure, When it is classified, Then each counts under its own category, and sandbox-style categories are marked low-confidence
  - [ ] Given the same tool result present more than once in a transcript (copies that are not user entries), When counted, Then it counts once
  - [ ] Given a tool result that is not an error, When scanned, Then it is never counted, whatever its text contains

#### Feature 3: Denials summary per source and period
- **User Story:** As the repository owner, I want per repository the counts per category, hook and rule for a period, split by main session and subagent, with a weekly trend, so that I can see where friction is and whether it changes.
- **Acceptance Criteria:**
  - [ ] Given an enabled source, When the report runs without a period option, Then the section covers the last 28 days and shows the period's start and end
  - [ ] Given denials in the period, When the section renders, Then it shows counts per category and, for hook denies, per hook and rule, each split into main session and subagent
  - [ ] Given denials in the period, When the section renders, Then it shows one row per calendar week of the period with the count per category
  - [ ] Given several sources, When the report renders, Then each source has its own denials section and no total is pooled across sources
  - [ ] Given sessions run in a worktree of the repository, When counted, Then they count for that repository

#### Feature 4: Top repeated denials
- **User Story:** As the repository owner, I want the most frequent denials listed with how often each was overridden, so that I can pick allowlist and rule-fix candidates first.
- **Acceptance Criteria:**
  - [ ] Given denials in the period, When the section renders, Then it lists up to 10 most frequent denial kinds (category, hook, rule, tool) with their count, ordered by count
  - [ ] Given a listed `tcs-git-helpers` rule with override events in the period, When the section renders, Then the row shows the override count next to the deny count
  - [ ] Given a listed denial kind, When the section renders, Then the row shows the most recent session id and time it happened

#### Feature 5: Explicit empty and partial states
- **User Story:** As the repository owner, I want the section to say plainly when it found nothing or could not read everything, so that a silent section is never mistaken for "no denials".
- **Acceptance Criteria:**
  - [ ] Given an enabled source with transcripts but no denial in the period, When the section renders, Then it says no denials were found in the period and that this is not proof none happened, naming what is not observable
  - [ ] Given a transcript line that cannot be parsed, When scanned, Then it is skipped, counted, and the section reports the number of skipped lines
  - [ ] Given transcripts from Claude Code versions outside the range the classification was checked against, When the section renders, Then it names those versions and says their denials may be unclassified

#### Feature 6: No transcript content in the output
- **User Story:** As the repository owner, I want the report to show only kinds, counts, rule names, tool names, versions, session ids and times, so that it never repeats prompts, commands, file paths or messages from my sessions.
- **Acceptance Criteria:**
  - [ ] Given denials whose tool input contains commands, paths or text, When the section renders, Then none of that text appears in the output
  - [ ] Given override events with a command field, When override counts render, Then the command field never appears in the output
  - [ ] Given a classifier block whose reason carries free text after its category, When it renders, Then only the bracketed category appears

#### Feature 7: Documented observability limits
- **User Story:** As the repository owner, I want one place that says which denial types the report can and cannot see and how reliable each count is, so that I read the numbers correctly.
- **Acceptance Criteria:**
  - [ ] Given the observability documentation, When the owner reads the denials part, Then it lists each category with its confidence and lists as not observable: settings deny-rule denials, prompts answered "no" after an ask decision as a distinct kind, denials in sessions whose transcripts were removed, and sandbox blocks that do not surface as a tool error
  - [ ] Given the documentation, When the owner reads how to enable the section, Then it shows the `denials = true` line and states that transcripts are read locally and only for enabled sources

### Should Have Features

#### Feature 8: Adjustable period
- **User Story:** As the repository owner, I want to set the period's length or start, so that I can compare before and after a rule change.
- **Acceptance Criteria:**
  - [ ] Given a period option of N weeks, When the report runs, Then the section covers the last N calendar weeks
  - [ ] Given a start date, When the report runs, Then the section covers from that date to now
  - [ ] Given an invalid period value, When the report runs, Then it stops with a message naming the value and the expected form, before any source is read

### Could Have Features

#### Feature 9: Claude Code version breakdown
- **User Story:** As the repository owner, I want counts per Claude Code version range, so that I can tell a real trend from a change in how Claude Code writes denials.
- **Acceptance Criteria:**
  - [ ] Given denials from several Claude Code versions, When requested, Then the section shows counts per category per version range

### Won't Have (This Phase)
- A recorder adapter for the `PermissionDenied` event: classifier blocks are already recognisable in transcripts.
- Deny records written by the TCS hooks themselves; the recorder still records no guard verdict (spec 021 Won't Have stands).
- Attributing a denial to a settings deny rule: no distinct transcript shape exists.
- Any transcript content in the output, and any transcript data leaving the machine.
- Totals pooled across sources (019 ADR-7).
- Editing allowlists, rules or settings from the report; the report proposes candidates, a person changes rules.
- Reading transcripts for any purpose other than this section, including the broader "transcript join" that spec 021 ruled out.

## Detailed Feature Specifications

### Feature: Denial classification
**Description:** Each error tool result in an enabled source's transcripts, main session and subagent, is checked against an ordered list of known denial shapes. The first match gives its category and, where the shape carries them, hook, rule, tool and classifier reason category. Results that match no shape are not denials and are ignored; hook-deny-shaped results with an unknown message are kept as unattributed.

**User Flow:**
1. Owner enables a source and runs the report.
2. System finds that source's transcripts in each of its homes, keeps the lines in the period that belong to the repository or its worktrees, and classifies error tool results.
3. Owner reads the section: categories, hooks and rules, weekly trend, top repeats with override counts, limits.

**Business Rules:**
- Rule 1: Only error tool results count; matching text in successful output never counts.
- Rule 2: A tool result counts once, however many copies the transcript holds.
- Rule 3: A `tcs-git-helpers` deny listing several rules counts once per rule under the rule view and once in the category total.
- Rule 4: Prompt rejections of AskUserQuestion and ExitPlanMode are not denials.
- Rule 5: A session belongs to the repository its working directory is in; a worktree under the repository counts as the repository.
- Rule 6: Sandbox-style categories ("Operation not permitted", network 403) are marked low-confidence, because the same text has other causes.
- Rule 7: Output carries no prompt, command, path or message text (Feature 6).

**Edge Cases:**
- A transcript written while the report runs → Expected: read what is complete; a partial last line is skipped and counted.
- A deny message that changed wording between Claude Code versions → Expected: both wordings classify to the same category; an unknown wording of a hook deny counts as unattributed.
- A source with several homes that are the same directory (bind mount) → Expected: transcripts are read once.
- A session that switches working directory between repositories → Expected: each line counts for the repository of its own working directory.
- A period with no transcripts at all vs a period with transcripts and no denials → Expected: two different messages.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Enabled for every repository listed in this machine's locations config within two weeks of release.
- **Engagement:** The owner runs the denials review at least every four weeks; at least one rule change or allowlist entry traced to a top-repeated denial within the first two review cycles.
- **Quality:** On this machine's transcripts, at most 5 % of hook-deny-shaped results end as "unattributed"; zero transcript content in the output (checked by test); a 28-day report over the enabled sources finishes in under 60 seconds.
- **Business Impact:** Fewer overrides of the rules that were fixed, visible as a falling override count for those rules over the following four weeks.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Report section rendered | source, enabled state, period, counts per category, unattributed count, skipped-line count | Quality KPI: unattributed share and parse health per run |
| Top repeated denial listed | category, hook, rule, deny count, override count | Engagement and Business Impact: candidates and their override trend |
| Unknown Claude Code version seen | version | Quality: when the classification needs an update |

These are the report's own output, read by the owner; nothing is sent anywhere.

---

## Constraints and Assumptions

### Constraints
- Local and offline: reads files on this machine only; nothing leaves it.
- Privacy rules of specs 018 and 021 apply to the output: no prompt, response, argument, path or message text (021 CON-13, 018 Won't Have).
- Per-source sections, no pooled totals (019 ADR-7); runs inside the existing `report.py`.
- The transcript format is internal to Claude Code and changes between versions (Claude Code sessions docs); the classification must tolerate shapes it does not know.
- Works on macOS and Linux homes, including several homes per source.

### Assumptions
- Session transcripts stay on disk for the review period (Claude Code may clean up old sessions).
- The `tcs-git-helpers` deny format (`DENIED: N rule(s) matched` followed by `[RULE]` lines) stays stable; TCS controls it.
- `tcs-git-helpers` override events stay in its audit file with the rule's override variable name.
- The owner is the only person whose transcripts are on the machine being reported.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A Claude Code update changes deny wording, counts drop silently | High | Medium | Unknown versions named in the section; hook-deny-shaped unknown text kept as unattributed; unattributed share is a tracked KPI |
| Report leaks transcript content | High | Low | Output limited to kinds, counts, names, ids, times; tests assert no content |
| Sandbox counts mislead (EPERM with other causes) | Medium | High | Marked low-confidence; documented |
| Reading 5 GB makes the report slow | Medium | Medium | Period limit and per-source opt-in; 60-second KPI |
| Transcripts removed by Claude Code cleanup shorten the history | Low | Medium | Section shows the oldest transcript date found; documented as a limit |
| Owner reads "no denials" as "nothing was blocked" | Medium | Medium | Empty state names what is not observable (Feature 5) |

## Open Questions

- [x] Data source → transcripts, read narrowly (README Decisions Log)
- [x] Opt-in → per source, `denials = true` in the locations config
- [x] Default period → 28 days, adjustable
- [x] Override usage → per rule, count only
- [x] Subagents → counted, shown separately
- [ ] Hook messages other than `tcs-git-helpers` (e.g. "Dangerous flag detected", "rm -rf on critical directory blocked", the main-edit block): which hook owns each, for attribution — to settle in the SDD from the hook sources

---

## Supporting Research

### Competitive Analysis
Claude Code itself offers no denial history: hook events cover only auto-mode classifier blocks (`PermissionDenied`), and settings deny rules, rejected prompts and hook denies leave no event (research.md, Claude Code hooks docs). The enterprise coding-agent guide (ch. 6) prescribes the review loop but leaves tooling to the operator.

### User Research
Measured on this machine's transcripts (research.md): 6189 files, 5.17 GB, Claude Code 2.1.71–2.1.332; 641 hook denies, 206 rejected prompts (160 of them AskUserQuestion or ExitPlanMode), 63 classifier blocks, 312 "Operation not permitted" and 50 network 403 errors. Top `tcs-git-helpers` rules: `BRANCH_FROM_UNFINISHED` 148, `DESTRUCTIVE_CHECKOUT` 94, `FORCE_BRANCH_DELETE` 74, `REMOTE_BRANCH_DELETE` 52. Most "permission to use … denied" (56 of 71) and worktree isolation blocks (159 of 169) come from subagents.

### Market Data
Not applicable: internal tooling for TCS-managed repositories.
