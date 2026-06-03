---
title: "NO_VERIFY rule: stop false-positives on sibling-command flags"
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
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision
A commit-bypass guard that fires **only** when the developer actually tries to bypass git
hooks — never on a legitimate commit that happens to chain an unrelated command.

### Problem Statement
The `tcs-git-helpers` `NO_VERIFY` rule is meant to block `git commit --no-verify` / `git commit -n`
(which skip `.githooks/`). The detection pattern is `git[[:space:]]+commit.*(--no-verify|-n[[:>:]])`.
The unbounded `.*` bridges from `git commit` to **any** later `-n` token in the same command
string, even when that token belongs to a different, chained subcommand
(`git commit -m "done" && echo -n ok`, `git commit ...; head -n 5`, `git commit ... | grep -n foo`).
Because bash does not set `REG_NEWLINE`, `.` also matches newlines, so multi-line compound
commands match too.

Evidence (verified 2026-06-01 against `lib/pattern_match.sh` v2.2.3, exercising the real
`_strip_quoted` → `_match_command` path):

| Command | Result | Correct? |
|---------|--------|----------|
| `git commit --no-verify` | DENY | ✅ |
| `git commit -n` | DENY | ✅ |
| `git commit -m "done" && echo -n ok` | DENY | ❌ false-positive |
| `git commit -m "msg" ; head -n 5 f` | DENY | ❌ false-positive |
| `git commit ...\n echo -n ok` (newline) | DENY | ❌ false-positive |
| `git commit -m "fixed -n, ok"` | ALLOW | ✅ |

Consequence: a developer doing nothing wrong is hard-blocked from committing and must either
restructure their command or reach for the `CLAUDE_ALLOW_NO_VERIFY=1` override — eroding trust
in the guard and conditioning users to keep an override handy (which weakens the real protection).

### Value Proposition
Precision. The guard keeps blocking genuine bypass attempts but stops punishing innocent
compound commands, so developers don't learn to routinely disable it.

## User Personas

### Primary Persona: Committing developer (human or agent)
- **Role / expertise:** Engineer or AI coding agent running git via a shell, frequently chaining
  commands (`&&`, `;`, `|`, newlines) in a single invocation.
- **Goals:** Commit work and run the hooks; never silently bypass verification.
- **Pain Points:** A correct commit is denied because an unrelated `-n` (e.g. `echo -n`,
  `head -n`) appears later in the same command line. The error message points at `--no-verify`,
  which is confusing because no bypass was attempted.

### Secondary Personas
_None — the guard has a single relevant actor._

## User Journey Maps

### Primary User Journey: Commit with a chained sibling command
1. **Awareness:** Developer assembles a one-liner: stage, commit, then echo/inspect output.
2. **Consideration:** They expect the commit to run hooks normally.
3. **Adoption:** They submit the command through the tool that triggers the PreToolUse guard.
4. **Usage:** Guard inspects the command, isolates the `git commit` clause, finds no real
   bypass flag, and allows it. Hooks run as intended.
5. **Retention:** Because the guard never false-blocks, developers leave it enabled and trust it.

### Secondary User Journeys
_None._

## Feature Requirements

### Must Have Features

#### Feature 1: Sibling-command isolation for NO_VERIFY detection
- **User Story:** As a committing developer, I want the bypass guard to ignore `-n` flags that
  belong to other commands chained after `git commit`, so that legitimate compound commands are
  not blocked.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a command `git commit -m "done" && echo -n ok`, When the NO_VERIFY rule evaluates it, Then it does NOT match (commit is allowed)
  - [ ] Given a command `git commit -m "msg" ; head -n 5 file`, When the rule evaluates it, Then it does NOT match
  - [ ] Given a command `git commit -m "x" | grep -n foo`, When the rule evaluates it, Then it does NOT match
  - [ ] Given a compound command where `git commit` and a later `echo -n` are separated by a newline, When the rule evaluates it, Then it does NOT match

#### Feature 2: Genuine-bypass detection preserved
- **User Story:** As a repo maintainer, I want real bypass attempts to keep being blocked, so
  that the guard still protects `.githooks/`.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given `git commit --no-verify -m "x"`, When the rule evaluates it, Then it MATCHES (denied)
  - [ ] Given `git commit -n -m "x"`, When the rule evaluates it, Then it MATCHES (denied)
  - [ ] Given `git commit -m "x" --no-verify`, When the rule evaluates it, Then it MATCHES (denied)
  - [ ] Given a real bypass chained after another command, e.g. `git add . && git commit -n`, When the rule evaluates it, Then it MATCHES (denied)

#### Feature 3: Message-body exemption preserved
- **User Story:** As a committing developer, I want `-n` text inside my commit message to be
  ignored, so that descriptive messages are not misread as bypass flags.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given `git commit -m "fixed -n, all good"`, When the rule evaluates it, Then it does NOT match
  - [ ] Given `git commit -m "see --no-verify docs"`, When the rule evaluates it, Then it does NOT match

### Should Have Features
- The fix should remain bash 3.2 compatible and POSIX-ERE only (no PCRE), consistent with the
  existing `pattern_match.sh` constraints.
- Regression tests should be added to the existing bats suite so the false-positive cannot recur.

### Could Have Features
- A short note in the rule's reference doc explaining that the guard scopes to the `git commit`
  clause only.

### Won't Have (This Phase)
- Full shell-grammar parsing of arbitrary command structures (subshells, command substitution
  edge cases). The fix targets the common sibling-command separators; exotic nesting remains a
  documented limitation with the existing `CLAUDE_ALLOW_NO_VERIFY=1` escape hatch.
- Changes to any rule other than NO_VERIFY.

## Detailed Feature Specifications

### Feature: Sibling-command isolation for NO_VERIFY detection
**Description:** The NO_VERIFY check must consider only the portion of the command string that
constitutes the `git commit` invocation, not tokens belonging to commands chained before or
after it via shell separators.

**User Flow:**
1. Developer submits a compound command containing a `git commit` clause plus other clauses.
2. Guard isolates the `git commit` clause (bounded by `;`, `&&`, `||`, `|`, newline).
3. Guard checks that clause for a genuine `--no-verify` / `-n` flag.
4. System allows or denies based on the clause alone.

**Business Rules:**
- Rule 1: A `-n` / `--no-verify` token counts only if it is part of the `git commit` clause.
- Rule 2: `-n` text inside a quoted `-m "..."` message never counts (existing behavior).
- Rule 3: A genuine bypass anywhere in the command still denies (a `git commit -n` clause is a
  bypass regardless of what precedes it).

**Edge Cases:**
- Scenario: `git commit` clause itself spans a quoted message containing separators
  (`git commit -m "a; b && c"`) → Expected: separators inside quotes do not split the clause; no
  false match.
- Scenario: real bypass `git add . && git commit --no-verify` → Expected: still denied.
- Scenario: sibling `-n` on a newline after the commit → Expected: not matched.

## Success Metrics

### Key Performance Indicators
- **Quality:** 0 false-positive denials across the documented sibling-command corpus; 100% of
  the genuine-bypass corpus still denied.
- **Regression safety:** New bats cases for both corpora pass; existing suite stays green.

### Tracking Requirements
| Event | Properties | Purpose |
|-------|------------|---------|
| NO_VERIFY deny | command string (already logged via override-audit path) | Confirm denials correspond to real bypass attempts only |

---

## Constraints and Assumptions

### Constraints
- bash 3.2 compatible (macOS default shell); no associative arrays, no `mapfile`.
- POSIX ERE only — never PCRE (existing CON-9 in `pattern_match.sh`).
- Fix is confined to `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` and its dispatcher
  use in `block-bad-git-ops.sh`, plus tests/fixtures.

### Assumptions
- Sibling commands are delimited by the common shell separators `;`, `&&`, `||`, `|`, and
  newline; this covers the observed false-positive cases.
- The existing `_strip_quoted` helper continues to handle the quoted-message-body case and can
  be composed with the new clause-isolation logic.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Clause isolation accidentally lets a real bypass slip through | High | Low | Genuine-bypass corpus in bats must stay 100% denied; add the chained-bypass case explicitly |
| New parsing breaks on quoted separators (`-m "a; b"`) | Medium | Medium | Compose with `_strip_quoted` first, then split; add an edge-case test |
| Over-engineering toward full shell parsing | Medium | Medium | Scope to documented separators; keep `CLAUDE_ALLOW_NO_VERIFY=1` as escape hatch for exotic nesting |

## Open Questions
- [ ] None blocking. Exact isolation technique (clause-split vs. bounded regex) is an SDD decision.

---

## Supporting Research

### Competitive Analysis
N/A — internal developer-tooling guard.

### User Research
Empirical reproduction on 2026-06-01 against the live v2.2.3 library established the
false-positive set and the preserved-behavior set (see Problem Statement table). The PreToolUse
guard even blocked the initial test command because it literally contained
`git commit ... && echo -n`, a live demonstration of the defect.

### Market Data
N/A.
