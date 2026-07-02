---
title: "rule-enforcer Batch/Extraction Mode (CLAUDE.md + Memory Sweep)"
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
| specId | 016-rule-enforcer-claude-md-sweep |
| title | rule-enforcer Batch/Extraction Mode (CLAUDE.md + Memory Sweep) |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 18 |

---

## Product Overview

### Vision
Let a maintainer point `rule-enforcer` at a repo's written rules (`CLAUDE.md` + memory
files) and, in a single confirm, convert every *mechanically enforceable* rule into a
deterministic hook, CI check, or git guard — turning "documented intentions" into
"enforced guarantees."

### Problem Statement
The existing `rule-enforcer` skill triages **one** rule at a time through four
interactive questions (Q1 recurrence, Q2 detectability, Q3 intervention point, Q4
style) before handing off to an author skill. For a maintainer who has accumulated
rules over months, the cost is **O(rules × 4 AskUserQuestion round-trips)**. This
repo alone carries a root `CLAUDE.md` with `@`-imports, six `docs/ai/memory/*.md`
category files, and a 25-entry global auto-memory index. Re-triaging each written
rule one at a time is prohibitively slow, so the backlog of "rules I wrote down but
never mechanized" never gets cleared. The project's own doctrine states memory is
only the layer-1 defense and mechanical enforcement is the escalation
(`mechanism-matrix.md`) — yet there is no efficient path to perform that escalation
in bulk. The consequence: written rules keep being silently violated because they
were never turned into deterministic guards.

### Value Proposition
Batch mode collapses the interaction cost from `O(N × 4 prompts)` to `O(1 confirm)`
by **inferring** Q2/Q3/Q4 non-interactively and **skipping** Q1 (recurrence is
presumed — a rule that is already written down is evidence it recurs). It reuses the
existing `mechanism-matrix.md` as the single source of truth for classification and
the existing author-skill hand-offs for generation, so it adds a fast front-end
without forking any downstream logic. Crucially, it **deduplicates against
enforcement that already exists** (e.g. `tcs-git-helpers` hooks), so the maintainer
sees a trustworthy, noise-free proposal rather than re-proposals of rules already
guarded.

## User Personas

### Primary Persona: The Rule-Accumulating Maintainer
- **Demographics:** Solo developer / small-team lead, high technical expertise,
  power-user of Claude Code who curates `CLAUDE.md` and a memory bank across many
  repos.
- **Goals:** Ensure the rules they have written down are actually enforced, not just
  documented; clear the backlog of un-mechanized rules with minimal effort; trust
  that the tool won't generate duplicate or false-positive guards.
- **Pain Points:** The one-rule-at-a-time interactive flow is too slow to run over an
  accumulated rule set; no way to see "which of my written rules could be
  mechanized"; fear that a naive bulk tool would generate block-hooks for
  judgment-only rules or re-propose already-enforced rules.

### Secondary Personas
- **The New-Repo Onboarder:** Runs TCS setup (`memory-setup` /
  `memory-claude-md-optimize`) on a fresh repo and wants a single post-setup sweep to
  mechanize everything mechanizable before starting work. Goal: start from "enforced"
  rather than "documented." Pain point: doesn't yet know which rules are
  mechanizable.
- **The Global-Config Owner:** Keeps cross-repo rules in `~/.claude/`. Goal: a global
  rule becomes a global guard, not a repo-local one (scope-correct hand-off). Pain
  point: a naive scan would mis-scope global rules to a single repo or leak personal
  content into committed artifacts.

## User Journey Maps

### Primary User Journey: Sweep-and-Mechanize
1. **Awareness:** The maintainer realizes their `CLAUDE.md`/memory rules are
   documented but not enforced, or `memory-claude-md-optimize` points them at
   `/rule-enforcer --scan`.
2. **Consideration:** They weigh the interactive one-rule flow (too slow for N rules)
   against a batch sweep. Batch wins on effort.
3. **Adoption:** They run `/rule-enforcer --scan`. The scan is read-only — nothing is
   written yet, which lowers the risk of trying it.
4. **Usage:** They review one consolidated proposal table (source, quote, inferred
   mechanism, style, dedup status), optionally deselect rows, then give a single
   confirm. Selected rules are handed off to the existing author skills and written.
5. **Retention:** They re-run the sweep periodically to catch newly-written rules;
   each run shows already-enforced rules as evidence the tool respects prior work.

### Secondary User Journeys
- **Optimizer Hand-off:** While running `memory-claude-md-optimize`, the user sees a
  pointer: "N always/never/must rules may be mechanically enforceable — run
  `/rule-enforcer --scan` after this optimization applies." They finish the
  optimization (rules land in the Memory Bank), then run the scan against the now-
  canonical files.
- **Single-File Hand-off (automated caller):** A caller invokes
  `/rule-enforcer --from-file <path>` against one explicit file, bypassing the global
  scan entirely.

## Feature Requirements

### Must Have Features

#### Feature 1: Read-Only Rule Sweep
- **User Story:** As the rule-accumulating maintainer, I want to scan my `CLAUDE.md`
  and memory files for enforceable rules without changing anything, so that I can see
  the candidate set risk-free.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a repo with `CLAUDE.md`, nested `**/CLAUDE.md`, and `docs/ai/memory/*.md`,
    When the user runs the scan, Then all those files are discovered and read, and
    their `@`-imports are followed transitively. *(AC-1, AC-2)*
  - [ ] Given the scan runs, When it completes, Then no file has been written and no
    hook installed until the single confirm. *(AC-3)*
  - [ ] Given a scanned file with zero enforceable rules, When the scan completes,
    Then an explicit "no mechanizable rules found in X" line is shown (not silence,
    not an empty table). *(AC-12, EC-3)*

#### Feature 2: Non-Interactive Classification Against the Matrix
- **User Story:** As the maintainer, I want each enforceable rule automatically
  classified into the correct enforcement mechanism, so that I don't answer four
  questions per rule.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a candidate rule, When it is classified, Then it is tagged
    `deterministically-enforceable` or `judgment-only`, and only enforceable rules
    enter the proposal. *(AC-4)*
  - [ ] Given an enforceable rule, When it is classified, Then Q2/Q3/Q4 are inferred
    non-interactively and the mechanism is resolved via the **same**
    `mechanism-matrix.md` the interactive flow uses (no duplicated mapping). *(AC-5)*
  - [ ] Given batch classification, When any rule is processed, Then Q1 (recurrence)
    is skipped entirely. *(AC-6)*
  - [ ] Given the five worked cases in `reference/examples.md`, When run through batch
    inference, Then each yields the same mechanism the interactive flow would produce.
    *(AC / SM-4)*

#### Feature 3: Deduplication Against Existing Enforcement
- **User Story:** As the maintainer, I want rules that are already enforced by an
  installed hook to be flagged and excluded, so that the proposal is trustworthy and
  I never generate a duplicate guard.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given rules already covered by installed hooks (e.g. edit-on-main, git bad-ops,
    skill-author-on-edit), When the scan runs, Then each is marked `already-enforced`
    and excluded from generated output by default. *(AC-11, EC-2, SM-3)*
  - [ ] Given a rule this batch (or a prior run) already installed a hook for, When
    the scan runs again, Then it is recognized as `already-enforced` and not
    re-proposed. *(EC-2)*
  - [ ] Given the same rule reached via two `@`-import paths or present in two scopes,
    When the scan runs, Then it appears once, at the broadest applicable scope. *(EC-5,
    EC-6)*

#### Feature 4: Consolidated Proposal + Single Confirm + Hand-off
- **User Story:** As the maintainer, I want one table of all proposals and one
  confirm, then automatic generation, so that mechanizing N rules costs a single
  decision.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given enforceable rules were found, When the proposal is shown, Then all rows
    appear in one consolidated table citing source `file:line`, extracted text,
    inferred Q3, inferred Q4, resolved mechanism, and dedup status. *(AC-7, AC-8,
    SM-6)*
  - [ ] Given the proposal, When the user decides, Then a single confirmation gate
    governs the whole batch with at minimum `Apply all`, `Select subset`, and
    `Cancel`, and the user can deselect individual rows before applying. *(AC-9)*
  - [ ] Given the user accepts, When hand-off runs, Then each selected rule is passed
    to the **existing** author skills (hook-development, skill-author, memory-add, CI
    / pre-push renderers) with no re-implementation of authoring logic. *(AC-10)*
  - [ ] Given a rule whose inference confidence is low, When it is shown, Then it is
    marked `needs-review` and defaults to deselected (or to the safest mechanism),
    never silently generating a block hook. *(EC-8)*

### Should Have Features
- **Graceful hand-off degradation:** When a target author skill/plugin is not
  installed, the affected mechanism bucket degrades to a memory rule (with confirm)
  and the rest of the batch still proceeds — skip-and-report, never hard-abort.
- **Judgment-only transparency:** Non-enforceable lines are listed under a
  "Left as guidance" sub-table (with reason), not silently dropped.
- **Overlap/conflict surfacing:** When two rules overlap at different strengths (e.g.
  global "warn" vs repo "block"), collapse into one proposal and surface the conflict
  for resolution at confirm time. *(EC-4)*

### Could Have Features
- **Scope selector:** `--scope repo|project|global` to widen/narrow the scan set.
- **Subset paging:** When more than a few rules need individual deselection, page the
  selection interaction.
- **Grouped artifact preview:** After the set is approved but before any write, show a
  single grouped preview of all rendered artifacts with one final write-confirm.

### Won't Have (This Phase)
- **Rewriting or "improving" non-deterministic/judgment rules** — batch mode filters
  them out; it does not try to make "write good code" enforceable. *(OOS-1)*
- **Auto-apply without the single explicit confirm** — no `--yes`-by-default. *(OOS-2)*
- **Duplicating or forking the classification mapping** — the matrix stays SSOT.
  *(OOS-3)*
- **Re-implementing author-skill logic** — hand-off only. *(OOS-4)*
- **Editing / migrating the scanned memory files themselves** — that is
  `memory-claude-md-optimize`'s job; batch mode only reads them. *(OOS-5)*
- **Per-rule interactive Q1 triage** — that is the existing single-rule mode. *(OOS-6)*
- **Persisting scan/triage state to disk** — the batch run is stateless within one
  invocation. *(OOS-7)*
- **Fixing the pre-existing `/enforce-rule` vs `/rule-enforcer` naming drift** —
  noted, out of scope for this spec.

## Detailed Feature Specifications

### Feature: Consolidated Proposal + Single Confirm + Hand-off
**Description:** After the read-only sweep and non-interactive classification, batch
mode presents every enforceable rule in one table, takes one confirm (with optional
per-row deselection), and hands each accepted rule to the existing author skills.

**User Flow:**
1. User runs the scan against the default source set (repo + project) or an explicit
   file / scope.
2. System discovers files, follows `@`-imports, extracts candidate instructions,
   filters to enforceable, infers Q2/Q3/Q4, resolves mechanisms via the matrix, and
   deduplicates against installed enforcement.
3. System presents one consolidated table plus a "Left as guidance" sub-table.
4. User reviews, optionally deselects rows, and gives a single confirm.
5. System hands each accepted rule to the appropriate existing author skill and
   reports what was written, skipped, or already enforced.

**Business Rules:**
- Rule 1: When classification yields `judgment-only`, then the rule is excluded from
  generated output and listed as guidance (it does not trigger a per-rule
  memory-add).
- Rule 2: When a rule is `already-enforced`, then it is excluded from output by
  default and shown for transparency.
- Rule 3: When inference confidence is low, then the row is `needs-review` and
  defaults to deselected.
- Rule 4: When a target skill/plugin is unavailable, then that mechanism bucket
  degrades to a memory rule and the rest of the batch proceeds.
- Rule 5: When scanning `~/.claude/`, then generated committed artifacts must
  paraphrase rule intent and must not paste personal content or personal-file
  provenance.

**Edge Cases:**
- Looks-enforceable-but-fuzzy (e.g. "don't inline `python3 -c` because of zsh `!`") →
  Expected: classified into a high-false-positive tier, proposed with a warning or
  demoted to nudge/memory, never a silent block hook. *(EC-1)*
- Zero enforceable rules across all files → Expected: report "nothing to do," no
  AskUserQuestion. *(EC-3)*
- All detectable rules already enforced → Expected: show the already-enforced table as
  evidence; no new output.
- File not found / empty scope → Expected: report which paths were probed, exit
  cleanly, suggest `memory-setup` if the whole scope is empty.
- Protected/structural content (routing rules, category comments, `@`-import lines) →
  Expected: not mis-extracted as candidates. *(EC-7)*

## Success Metrics

### Key Performance Indicators
- **Adoption (effort reduction):** For a repo with N enforceable rules, user
  interactions drop from ~`N × 4` to a single-digit prompt count regardless of N.
  *(SM-1)*
- **Engagement (recall):** Of the deterministically-enforceable rules a human
  reviewer identifies in a repo's corpus, batch mode proposes ≥ 80% without the user
  naming any rule. *(SM-5)*
- **Quality (precision / dedup):** Zero false-positive block-hooks in confirmed
  output; 100% of already-enforced rules flagged and excluded; zero duplicate/
  competing hooks generated. *(SM-2, SM-3)*
- **Quality (matrix parity):** For any rule, batch-inferred mechanism equals the
  interactive-mode mechanism given the same Q2/Q3/Q4. *(SM-4)*
- **Business impact (mechanization backlog):** The count of written-but-unmechanized
  rules in a repo trends toward zero after repeated sweeps.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Scan run | source files read, candidates found, enforceable count, dedup hits | Measure recall (SM-5) and effort reduction (SM-1) |
| Proposal shown | rows proposed, needs-review count, judgment-only count | Validate precision and transparency |
| Confirm decision | apply-all / subset / cancel, rows deselected | Measure whether single-confirm holds for the common path |
| Hand-off result | per mechanism: written / skipped / degraded-to-memory / already-enforced | Validate dedup (SM-3) and graceful degradation |

---

## Constraints and Assumptions

### Constraints
- **SKILL.md size budget:** The existing skill is near its ≤500-line budget;
  batch-mode procedural detail must live in lazy-loaded `reference/` files, not inline.
- **Matrix is SSOT:** Classification must reuse `mechanism-matrix.md` verbatim — no
  parallel mapping.
- **Hand-off only:** All generation goes through existing author skills/templates;
  batch mode adds no writer of its own.
- **Privacy/compliance:** Personal content under `~/.claude/` must never be echoed
  into committed artifacts or hand-off arguments.
- **No new destructive capability:** The sweep is read-only until the single confirm;
  the existing slug-validation gates must remain load-bearing.

### Assumptions
- Users curate their rules in `CLAUDE.md` + `docs/ai/memory/*` (and optionally
  `~/.claude/`), so those files are the authoritative rule source to scan.
- A rule already written down is sufficient evidence of recurrence (justifies
  skipping Q1).
- The existing author skills and templates remain the correct generation targets and
  are usually installed.
- `memory-claude-md-optimize` runs before the sweep when both are used, so the sweep
  reads canonical, relocated files.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| False-positive block hooks from fuzzy rules | High | Medium | High-false-positive tier + needs-review default-off + judgment-only filter (EC-1, EC-8) |
| Dedup misses → duplicate/competing hooks | High | Medium | Live-inspect `.githooks/` + `hooks.json` as authoritative; catalog as hint layer; dedup by mechanism+pattern, not text (EC-2) |
| Q1-skip/inference contradicts existing skill constraints | Medium | High | New ADR documenting batch mode as a deliberate exception; mode-gated so interactive path is untouched (AC-6) |
| Personal `~/.claude/` content leaks into committed files | High | Low | Paraphrase intent, never paste; surface scanned sources at confirm; global scan opt-in |
| Crafted/malicious rule text triggers path traversal | High | Low | Reuse existing slug-validation gates; add malicious-fixture test |
| N sequential prompts erode the single-confirm promise | Medium | Medium | One table + one confirm + optional grouped preview; deselection paged only when needed |

## Open Questions
- [ ] Should the default `--scan` include `~/.claude/` (global) at all, or require
  explicit `--scope global`? (Working default: exclude global unless requested.)
- [ ] Recall threshold for SM-5 — is 80% the right bar, or higher for a curated repo?
- [ ] Should overlapping global-vs-repo rules always prefer the broader scope
  automatically, or always surface for user choice?

---

## Supporting Research

### Competitive Analysis
The aihero.dev article "How to use Claude Code hooks to enforce the right CLI"
provides the closing prompt "Take the instructions in your CLAUDE.md and turn them
into deterministic Claude Code hooks," which inspired this feature. That prompt only
covers the narrow `PreToolUse`+`Bash`+`exit 2` case and offers no classification,
dedup, or multi-mechanism routing. Batch mode generalizes it across the full
mechanism matrix (7 intervention points + CI + pre-push) and adds deduplication and a
single-confirm UX.

### User Research
Grounded scan of this repo's own corpus (root `CLAUDE.md` + `@`-imported
`general.md` + six `docs/ai/memory/*.md` + 25-entry global auto-memory) confirms a
real mix of: (a) cleanly enforceable rules with no hook yet (venv /
`--break-system-packages`, `fd`/`rg` preferences), (b) rules already enforced by
`tcs-git-helpers` (edit-on-main, git bad-ops, skill-author-on-edit), and (c)
judgment-only rules ("English for all code", "DRY/YAGNI", "commit after each task").
The feature's requirements are shaped directly by this observed distribution.

### Market Data
Not applicable — internal developer tooling within the TCS plugin ecosystem.
