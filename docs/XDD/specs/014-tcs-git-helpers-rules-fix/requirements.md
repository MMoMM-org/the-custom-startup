---
title: "tcs-git-helpers Rule Fixes — Squash-Merge-Trap Nuance + Inline Override Support"
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

## Product Overview

### Vision

tcs-git-helpers protects against real squash-merge-traps without false-positive blocks on
legitimate follow-up work, and its documented override mechanism works for both human shells
and Claude Bash invocations.

### Problem Statement

Two defects in `plugins/tcs-git-helpers/` cause real workflow friction and misdirect users:

**Defect 1 — False-positive push block on legitimate follow-up branches.**
The closed-PR push guard fires on any branch whose GitHub PR is CLOSED or MERGED, regardless
of whether the user has added new commits since the merge. This is correct when the user's HEAD
equals the merged state (a ghost branch that would push nothing new), but is wrong when the
user has added N new commits and intends to open a second PR from the same branch. The result:
every legitimate follow-up push attempt is denied, forcing a disruptive workaround of
creating a fresh branch to continue work. This was directly observed during spec/013
implementation (PR #31 merged; 28 subsequent implementation commits all blocked).

**Defect 2 — Override path documented in deny messages does not work for Claude.**
Deny messages instruct users to prepend `CLAUDE_ALLOW_X=1` to their command as an inline
override. This works from a human's terminal shell, but not from Claude's Bash tool. The
PreToolUse hook fires in Claude Code's own process environment before the Bash subshell
executes — so `CLAUDE_ALLOW_X=1 git push` as a Bash command sets the variable only in the
subshell, which the hook never sees. The hook reads its own environment, so the override is
silently ignored and the deny stands, making the documented escape hatch non-functional for
Claude.

**Consequences of not fixing**: Users and Claude must route around the tool rather than trust
it — either by creating unnecessary throw-away branches (Defect 1) or by manually disabling
hooks at the shell level before launching Claude (Defect 2). Both reduce confidence in
tcs-git-helpers as reliable guardrails.

### Value Proposition

These fixes make tcs-git-helpers accurate rather than merely restrictive. The squash-merge-trap
guard remains in place for the exact scenario it was designed for; it simply stops firing on
branches where the user has demonstrably added new work. The override mechanism, once correct,
means the tool's documented escape hatch is trustworthy — users can read the deny message and
follow its instructions without a hidden gotcha.

---

## User Personas

### Primary Persona: Marcus (TCS Plugin Maintainer and Daily User)

- **Role:** Solo developer and maintainer of the TCS plugin ecosystem; uses tcs-git-helpers on
  every repository in the stack.
- **Goals:** Git guardrails that protect against real mistakes without requiring workflow
  gymnastics; override paths that are predictable and documented honestly.
- **Pain Points:** Creating a fresh branch solely to satisfy a rule that misidentified his
  situation as dangerous; reading a deny message that advertises an override that silently fails.

### Secondary Persona: Claude (AI Assistant Invoking Git Commands)

- **Role:** Issues git commands through the Bash tool under Marcus's direction; reads deny
  messages and follows their instructions to apply overrides.
- **Goals:** Override paths that work from within the Bash tool, not just from a pre-launched
  shell environment; accurate deny messages that do not lead to repeated failed attempts.
- **Pain Points:** Inline `CLAUDE_ALLOW_X=1 git push` commands blocked despite following the
  documented override format; no way to distinguish "this override is broken" from
  "this override is correctly denied."

---

## User Journey Maps

### Primary User Journey: Continuing Work on a Branch After Its PR Merged

1. **Context:** Marcus merged a documentation PR on `spec/013-rule-enforcer` via squash-merge.
   He then adds 28 implementation commits to the same branch.
2. **Trigger:** He runs `git push` to open a new PR for the implementation work.
3. **Current (broken) state:** The push is denied — "PR is CLOSED/MERGED." He creates a new
   branch `spec/013-rule-enforcer-impl` as a workaround, losing branch history continuity.
4. **Post-fix state:** The guard detects that HEAD is ahead of the merged commit. It emits an
   informational note ("PR was merged; new commits will require a new PR") and allows the push.
   No branch gymnastics required.

### Secondary User Journey: Claude Applying an Inline Override

1. **Context:** A push is denied by a guard with a message suggesting `CLAUDE_ALLOW_X=1 git push`.
2. **Current (broken) state:** Claude prepends the env-var, sends the Bash command. The hook
   runs before the command executes, sees no env-var in its own environment, denies again.
   Claude loops or escalates unnecessarily.
3. **Post-fix state:** The hook reads the Bash tool's command string from the tool input,
   finds the `CLAUDE_ALLOW_X=1` prefix, treats it as a valid override consumption, and allows
   the operation. One attempt, one success.

---

## Feature Requirements

### Must Have Features

#### Feature M1: HEAD-Ahead-of-Merged Detection (Squash-Merge-Trap Nuance)

- **User Story:** As a developer whose branch has an already-merged PR, I want the push guard
  to allow my push when I have added new commits since the merge, so that I can open a new PR
  without creating a fresh branch.

- **Acceptance Criteria (Gherkin Format):**

  - [ ] Given a branch whose GitHub PR is MERGED or CLOSED, and the branch HEAD equals the
    commit state already present on main as a result of the merge, When the developer runs
    `git push`, Then the push is denied with a squash-merge-trap warning.

  - [ ] Given a branch whose GitHub PR is MERGED or CLOSED, and the branch HEAD is ahead of
    the merged commit state by one or more commits, When the developer runs `git push`, Then
    the push is allowed and an informational message is emitted on stderr noting that the
    previous PR was merged and a new PR will be required.

  - [ ] Given a branch with no associated GitHub PR (open or otherwise), When the developer
    runs `git push`, Then the closed-PR guard does not fire and push proceeds normally through
    any remaining checks.

#### Feature M2: Bash Tool Command String Override Scanning

- **User Story:** As Claude executing git commands through the Bash tool, I want the override
  mechanism to work when I prepend `CLAUDE_ALLOW_X=1` to a command, so that I can follow the
  deny message's instructions and succeed in one attempt.

- **Acceptance Criteria (Gherkin Format):**

  - [ ] Given `CLAUDE_ALLOW_X=1` is exported in the user's shell environment before launching
    Claude, When the hook fires, Then the override is consumed from the environment and the
    operation proceeds — existing shell-level override behavior is unchanged.

  - [ ] Given the user's shell environment does NOT have `CLAUDE_ALLOW_X=1` set, and the
    Bash tool command string begins with `CLAUDE_ALLOW_X=1 ` (space-delimited prefix),
    When the hook fires and reads the tool input command string, Then the override prefix is
    recognized, the operation is allowed, and the override is consumed exactly once.

  - [ ] Given the hook fires but no tool input is available on stdin (e.g., the hook was
    invoked manually or in a context without JSON tool input), When the override check runs,
    Then the hook falls back to environment-variable-only evaluation without error.

  - [ ] Given both the environment variable and the command-string prefix are present,
    When the hook fires, Then the operation is allowed — the most restrictive matching rule
    (e.g., a granular rule-specific override beats a master override) still applies, and the
    override is not consumed twice or in an inconsistent order.

### Should Have Features

#### Feature S1: Deny Message Accuracy Post-M2

- **User Story:** As a user reading a deny message, I want the override instruction to
  accurately reflect how the override works, so that I can follow it without hitting a
  hidden failure mode.

- **Acceptance Criteria (Gherkin Format):**

  - [ ] Given M2 has shipped, When a deny message is emitted that references the
    `CLAUDE_ALLOW_X=1` override path, Then the message wording is consistent with the
    actual mechanism (inline env-var prefix works for both human shell and Claude Bash
    invocations), and no existing deny-message test assertions fail after the update.

### Could Have Features

N/A — internal tooling fix; no speculative enhancements in scope.

### Won't Have (This Phase)

- Refactoring `_check_and_consume_override` beyond the command-string scan addition.
- Adding new override rules or override targets not currently in the codebase.
- Changes to tcs-git-helpers hooks other than `block-bad-git-ops.sh` and `override.sh`.
- Any changes to plugins outside of `tcs-git-helpers`.

---

## Detailed Feature Specifications

### Feature M1: HEAD-Ahead-of-Merged Detection

**Description:** The closed-PR push guard currently stops at "this branch has a MERGED or
CLOSED PR" and denies unconditionally. After this fix, it performs a second check: is the
branch's current HEAD equivalent to the state left on main by the merge (a ghost branch), or
has the developer added commits on top (a continuing branch)? Only the former is a genuine
squash-merge-trap; the latter is a normal follow-up workflow and must be allowed.

**User Flow:**
1. Developer pushes a branch that has a merged or closed PR.
2. Guard detects the PR state.
3. Guard compares HEAD to the merge result on main.
4. If equal: deny with squash-merge-trap message (existing behavior preserved).
5. If HEAD is ahead: allow, emit informational stderr note about needing a new PR.

**Business Rules:**
- Rule 1: The squash-merge-trap denial must remain fully intact for the ghost-branch case
  (HEAD == merged state). No regression in protection.
- Rule 2: "Ahead" means the branch has at least one commit not present in main's ancestry
  as of the merge. The comparison must be robust to fast-forward merges and squash merges.
- Rule 3: The informational message on allow is emitted to stderr only; it must not interfere
  with the push operation itself.
- Rule 4: If the GitHub PR query fails or returns no PR, the guard must fall through without
  blocking (preserve current no-PR behavior).

**Edge Cases:**
- Detached HEAD state: The branch name cannot be determined, so no PR lookup is possible.
  The guard must exit cleanly without crashing, treating this as "no PR found."
- Multiple PRs on the same branch name (e.g., one closed, one open): The guard uses the
  first result returned by the GitHub API query. This behavior is unchanged by M1; document
  it as known.
- Branch renamed after PR merge: If the local branch name no longer matches the remote
  tracking branch, the PR lookup may return no results. Treat as "no PR" and allow through.

### Feature M2: Bash Tool Command String Override Scanning

**Description:** The `_check_and_consume_override` function checks whether a given override
env-var is active. After this fix, it also examines the command string from the Bash tool's
JSON tool input (passed via stdin by the Claude Code PreToolUse hook contract) for
`CLAUDE_ALLOW_X=1`-style prefixes. If found, the override is accepted as valid — without
requiring the env-var to be present in the hook's own process environment.

**User Flow:**
1. Claude receives a deny message instructing it to prepend `CLAUDE_ALLOW_X=1` to its command.
2. Claude reissues the Bash command with the prefix: `CLAUDE_ALLOW_X=1 git push origin branch`.
3. Claude Code fires the PreToolUse hook, passing the command string in JSON tool input.
4. The hook reads the tool input, parses the command string, finds the prefix.
5. Override is consumed; the guard allows the operation.

**Business Rules:**
- Rule 1: The env-var path remains the canonical override for human shell use. Tool-input
  scanning is additive, not a replacement.
- Rule 2: The command-string scan is anchored to the beginning of the command string.
  A `CLAUDE_ALLOW_X=1` token that appears mid-command or after shell operators is NOT
  recognized as a valid override. This prevents injection via crafted command strings.
- Rule 3: The master override `CLAUDE_ALLOW_GIT_BAD_OPS=1` must also be detectable via
  tool-input scanning, using the same prefix-anchored pattern.
- Rule 4: Backward compatibility — existing callers of `_check_and_consume_override` that
  pass no tool input must continue to work; only the env-var is evaluated in that case.
- Rule 5: stdin is consumed at most once per hook invocation. If multiple guards call
  `_check_and_consume_override` in sequence, the tool input must be parsed and cached at
  the start of the hook, not re-read from stdin each time.

**Edge Cases:**
- Shell quoting tricks: A command like `git push' && CLAUDE_ALLOW_X=1; '` must NOT be
  parsed as a valid override. The regex must anchor to the very start of the command string
  and require whitespace immediately after the variable assignment — no shell metacharacters
  between the variable and the git command.
- Multi-line commands (heredoc, line continuation): Only the first logical line is scanned
  for the override prefix. Multi-line expansion is not followed.
- Missing or malformed JSON on stdin: The hook must handle absent, empty, or non-JSON stdin
  gracefully, falling back to env-var evaluation without error output.

---

## Success Metrics

### Key Performance Indicators

- **Quality (M1):** Zero false-positive denials on branches with at least one commit added
  after their PR merged. Measured by test suite covering the three acceptance-criteria
  scenarios plus the edge cases defined above.
- **Quality (M2):** 100% of `CLAUDE_ALLOW_X=1 git push` commands issued by Claude via the
  Bash tool succeed (allow) when the override prefix is correctly prepended. Measured by
  test suite covering all four M2 acceptance criteria.
- **Regression (M1):** The existing squash-merge-trap deny scenario continues to deny with
  no change to message content. Zero regressions in existing test suite.
- **Adoption:** Implicit — M1 and M2 are behavior changes to tcs-git-helpers; all consumers
  receive them automatically on next version update. No explicit adoption metric required.

### Tracking Requirements

This is an internal developer tooling fix with no external telemetry infrastructure. Success
is validated by test results and manual workflow verification.

| Event | Properties | Purpose |
|-------|------------|---------|
| M1 guard — allow (new) | branch name, ahead-by count | Confirms the allow path fires on legitimate follow-up pushes |
| M1 guard — deny (existing) | branch name | Confirms squash-merge-trap protection unchanged |
| M2 override — consumed via tool input | rule key, command prefix length | Confirms inline override path works end-to-end |

All events are emitted as stderr log lines by the hook itself; no external analytics system
is required.

---

## Constraints and Assumptions

### Constraints

- **bash 3.2 compatibility:** The existing codebase targets bash 3.2 (macOS system shell).
  All new guard logic must be expressible in bash 3.2 — no associative arrays, no
  `mapfile`, no process substitution where not already used.
- **Backward compatibility:** `_check_and_consume_override`'s existing call signature must
  not change. Callers that pass only a rule key and env-var name must continue to work.
- **Scope boundary:** Only `block-bad-git-ops.sh` and `override.sh` (and their tests) are
  in scope. No other hooks or scripts are touched in this phase.
- **No new dependencies:** The fix must not introduce new CLI tools beyond what is already
  used by tcs-git-helpers (`gh`, `git`, `jq`).

### Assumptions

- The Claude Code PreToolUse hook receives the Bash tool's command string in a JSON
  `tool_input` field available to the hook process (via stdin or a defined env-var).
  This is the documented hook contract; the implementation will confirm the exact field path.
- `gh` CLI is available and authenticated in the environment where pushes occur (existing
  assumption in the closed-PR guard; unchanged).
- A "merged commit state" can be determined by comparing the branch HEAD to `git merge-base`
  results against the default branch. The exact comparison strategy is an SDD concern;
  the PRD requires only that the behavior matches the acceptance criteria.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Regex too loose — shell quoting tricks parse as valid override | High — attacker or confused user bypasses guard | Low — internal tooling, single user | Anchor pattern to command string start; require bare `KEY=1 ` with no shell metacharacters in the prefix segment; add explicit test for quoting edge case |
| HEAD-ahead detection is slow on repos with large main branches | Medium — hook adds latency to every push | Low — `git merge-base --is-ancestor` is O(history), not O(file-count); most branches are recent | Cap ancestor traversal depth; use `--is-ancestor` rather than log-walking; measure in test environment |
| stdin consumed by first guard call — later calls lose tool input | High — M2 silently fails for subsequent guard checks | Medium — multiple guards fire per hook invocation | Cache parsed tool input at hook entry point; pass parsed value to each `_check_and_consume_override` call rather than re-reading stdin |
| Multiple PRs on same branch confuses ahead-of-merged comparison | Low — edge case; existing behavior retained | Low | Document known limitation; use first-returned PR as before |

---

## Open Questions

None. All decisions are pre-recorded in the spec README Decisions Log. This PRD is
authoritative for implementation scope.

---

## Supporting Research

### Competitive Analysis

N/A — internal tooling fix.

### User Research

Evidence is direct: Problem 1 was observed during spec/013 implementation (PR #31 merged;
28 subsequent commits blocked on push; workaround branch `spec/013-rule-enforcer-impl`
created). Problem 2 was discovered when attempting to use the advertised override path from
Claude's Bash tool and confirming via hook contract documentation that env-vars set inline
in a Bash command are not visible to the PreToolUse hook.

### Market Data

N/A — internal tooling fix.
