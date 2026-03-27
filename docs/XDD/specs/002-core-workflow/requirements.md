---
title: "M1 — Core Workflow Rebuild"
status: draft
version: "1.1"
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

## Implementation Principles (Cross-Cutting)

These principles apply to every skill and agent built in M1:

- **Script-first:** Use bash/python scripts for mechanical work (file ops, detection, formatting). Reserve AI for reasoning, generation, and review. Prefer `rg` (ripgrep) over grep, `fd` over find — these are required tools.
- **Modern CLI tools required:** `rg` (ripgrep), `fd`, and `fzf` must be available. Skills that search files must use `rg`/`fd` rather than `grep`/`find`. Any interactive picker uses `fzf`.
- **skill-author for all skills/agents:** Every new skill and agent in M1 must be created using `/tcs-helper:skill-author`. No hand-crafting SKILL.md or agent markdown outside of that workflow.
- **Agent offloading:** Where a step can be delegated to a subagent with a well-scoped prompt, do it. Use the cheapest model that can handle the complexity.
- **Minimal skill context:** Each SKILL.md should be under ~25 KB. Move reference material to `reference/` subdirs, loaded on demand.
- **YOLO mode:** Every interactive confirmation must be skippable when `YOLO=true`. Skills that write files should support unattended operation.
- **docs/ai/ location:** Cached external content (docs, session context) lives in `docs/ai/` as established in M2. Gitignored subdirs for transient content.
- **Handover announcements:** Every skill ends by announcing the next step. The user should never have to guess where to go next.

---

## Product Overview

### Vision

Provide a single, coherent plugin (`tcs-workflow`) that enforces rigorous SDD+TDD methodology discipline — spec-before-code, test-before-implementation, evidence-before-completion, structured reviews, and parallel agent dispatch — so that any developer can produce professional-grade software systematically without relying on memory or willpower.

### Problem Statement

`tcs-start` covers the high-level workflow (brainstorm → specify → implement → review) but leaves critical gaps:

1. **No SDD binding.** Plans are written without explicit references to SDD contracts. Tasks have no traceable link from design intent to implementation target.
2. **No test discipline gate.** `/implement` dispatches tasks without enforcing RED-GREEN-REFACTOR. Tests are written ad-hoc, after code, or skipped.
3. **No verification gate.** Success claims are made without evidence — "tests pass" written before running tests.
4. **No review rigor.** Receiving a code review has no structured workflow; feedback is accepted or rejected informally.
5. **No parallel dispatch pattern.** Running parallel agents is improvised every time, with no shared idiom for context, safety, or conflict avoidance.
6. **Plugin identity mismatch.** The name `tcs-start` suggests an onboarding tool, not the core workflow plugin.
7. **Session context loss.** After compaction or a new session, there is no single re-entry point to recover orientation. The user must reconstruct current state manually.
8. **Absorbed content inaccessible.** The best patterns from superpowers, citypaul/.dotfiles, and centminmod exist in external repos and must be manually recalled.

Consequence: workflow discipline degrades over sessions as the methodology is only partially automated.

### Value Proposition

After M1, `tcs-workflow` is the single workflow entry point for TCS. `/guide` orients any user — new or returning after context loss — in seconds. Every implementation task is anchored to an SDD contract and enforces RED-GREEN-REFACTOR before code is written. The absorbed patterns from the best external skill repos are available as first-class skills. YOLO mode enables fully unattended runs.

---

## User Personas

### Primary Persona: Marcus (Solo Developer — TCS Author)

- **Role:** Full-stack developer, framework author
- **Technical expertise:** Expert-level — writes the skills he uses
- **Goals:** Build production software systematically; never skip TDD; ensure every session leaves the codebase better than it started
- **Pain Points:**
  - Has to mentally recall which discipline applies to which workflow step
  - RED-GREEN-REFACTOR is broken because nothing enforces it before code is written
  - After context compaction, loses track of current phase and next steps
  - Review responses are improvised; parallel dispatch is inconsistent

### Secondary Persona: Experienced Developer (New TCS User)

- **Role:** Senior developer adopting TCS for the first time on their own project
- **Technical expertise:** High — comfortable with CI/CD, TDD, code review, but unfamiliar with TCS skill names and flow
- **Goals:** Follow the TCS workflow without reading the full docs; understand when to use which skill
- **Pain Points:**
  - Doesn't know the skill names or the correct sequence
  - Unsure when to invoke `/xdd` vs `/xdd-sdd` vs `/xdd-plan`
  - Needs a fast on-ramp that doesn't require memorising the entire plugin

### Tertiary Persona: Small Team Member (Contributor)

- **Role:** Developer on a team where TCS is the agreed workflow standard
- **Technical expertise:** Varies — may be junior or mid-level
- **Goals:** Follow the team's TCS workflow; contribute with consistent quality; understand review feedback in structured terms
- **Pain Points:**
  - Receives a PR comment and doesn't know the formal TCS response pattern
  - Needs to run parallel exploration but is worried about merge conflicts
  - Wants to add TDD evidence to a PR without knowing the exact format

---

## User Journey Maps

### Primary Journey: Feature Implementation Session

Every journey begins and can restart with `/guide`:

1. **Orient:** Developer invokes `/guide`. Skill asks for intent, resolves to the correct skill sequence, announces: "You're starting a new feature. Begin with `/brainstorm`."
2. **Design:** `/brainstorm` explores the idea; ends with: "Design approved. Next: `/specify` to write the PRD."
3. **Specify:** `/xdd-prd` → PRD. `/xdd-sdd` → SDD with interface contracts. Ends with: "SDD complete. Next: `/xdd-plan` to create RED/GREEN/REFACTOR tasks."
4. **Plan:** `/xdd-plan` generates tasks anchored to SDD contracts. Ends with: "Plan ready. Next: `/implement phase-1`."
5. **Implement:** `/implement` dispatches fresh subagents per task, TDD-enforced. Ends with: "Phase complete. Run `/verify` then `/review`."
6. **Verify:** `/verify` confirms evidence for all completed tasks.
7. **Review:** `/review` dispatches a subagent reviewer with BASE_SHA/HEAD_SHA context. Ends with: "Review complete. If feedback exists, run `/receive-review`."
8. **Respond:** `/receive-review` processes each review item with classify-then-respond. Ends with: "All items processed. Run `/finish-branch`."
9. **Close:** `/finish-branch` offers merge/PR/keep/discard. Branch cleaned up.

**Re-entry after context loss:** Developer types `/guide`. Skill detects current branch, checks for open plan phases, and announces: "You were in the middle of phase 2 of plan 002-core-workflow. Next task: [task name]. Run `/implement phase-2` to continue."

### Secondary Journey: Returning After Session Break

1. Developer starts a new session on an existing branch.
2. Invokes `/guide` with no argument.
3. Guide reads `docs/ai/memory/context.md` and the open plan files.
4. Announces current state and next action.

### Tertiary Journey: Parallel Exploration

1. Developer needs to compare two approaches.
2. Invokes `/parallel-agents` with two independent task descriptions.
3. Both agents run in isolated worktrees (via `/git-worktree`).
4. Results are compared; the better approach is merged forward.

---

## Feature Requirements

### Must Have Features

#### Feature 1: Plugin Rename — tcs-start → tcs-workflow

- **User Story:** As a developer, I want `tcs-workflow` to be the plugin name so that the name reflects the plugin's purpose as the core workflow engine.
- **Notes:** Hard rename — no backward-compat shims. Multiple plugins coexist (superpowers, tcs-helper, original tcs-start as legacy); tests verify tcs-workflow works, not that tcs-start is absent.
- **Acceptance Criteria:**
  - [ ] Given the plugin is installed, When a developer types `/tcs-workflow:brainstorm`, Then the brainstorm skill executes
  - [ ] Given the plugin manifest, When checked, Then `name` is `tcs-workflow` throughout plugin.json and all SKILL.md frontmatter
  - [ ] Given AGENTS.md and README, When checked, Then all references use `tcs-workflow`, not `tcs-start`
  - [ ] Given install.sh, When run, Then it installs the plugin under the name `tcs-workflow`

#### Feature 2: tcs-workflow:xdd-tdd — RED-GREEN-REFACTOR Iron Law

- **User Story:** As a developer implementing a task, I want the tdd skill to enforce the RED-GREEN-REFACTOR cycle so that no production code is written without a failing test first — including code written by dispatched subagents.
- **Notes:** TDD enforcement applies to all code-writing agents dispatched from any TCS skill. The citypaul tdd-guardian pattern applies: the skill delegates enforcement to a lightweight guardian agent rather than embedding all logic in the SKILL.md. This lowers skill context and allows model selection (cheap model for mechanical enforcement).
- **Acceptance Criteria:**
  - [ ] Given a task with an SDD contract reference, When `/xdd-tdd` is invoked, Then it requires a failing test before any implementation file is written
  - [ ] Given a failing test exists, When implementation is written, Then the skill confirms tests pass before allowing REFACTOR
  - [ ] Given a rationalization like "too simple to test", When the skill is active, Then it presents the iron law rejection table and blocks progression
  - [ ] Given `/implement` dispatches a subagent, When the subagent's task has a RED step, Then the subagent receives TDD enforcement context and cannot mark its task done without test evidence
  - [ ] Given no failing test exists, When implementation code is present, Then the skill instructs: delete implementation, write test, start over
  - [ ] Given YOLO=true, When `/xdd-tdd` runs, Then enforcement proceeds unattended — no interactive prompts, violations written to `docs/ai/memory/yolo-review.md` as checkbox items for deferred review

#### Feature 3: tcs-workflow:verify — Evidence-Before-Completion Gate

- **User Story:** As a developer completing a task, I want `/verify` to require actual command output before claiming success so that success claims are never made without running verification.
- **Acceptance Criteria:**
  - [ ] Given a task is about to be marked complete, When `/verify` is invoked, Then it requires at least one of: test run output, build output, lint output, or manual verification record
  - [ ] Given no evidence has been provided, When `/verify` is called, Then it blocks completion and lists the required evidence commands
  - [ ] Given evidence shows failures, When provided, Then `/verify` blocks and shows which failures must be resolved
  - [ ] Given all evidence passes, When `/verify` completes, Then it produces a structured evidence summary suitable for a commit message or PR description
  - [ ] Given YOLO=true, When `/verify` runs, Then it executes verification commands automatically and writes the evidence summary to `docs/ai/memory/context.md`

#### Feature 4: tcs-workflow:receive-review — Code Review Response Workflow

- **User Story:** As a developer receiving a code review, I want a structured workflow so that each piece of feedback is evaluated technically before accepting, pushing back, or deferring.
- **Acceptance Criteria:**
  - [ ] Given a PR review or comment list, When `/receive-review` is invoked, Then it processes each item with a classify-then-respond pattern
  - [ ] Given a review item, When classified, Then it is tagged as: Accept | Push Back | Defer | Question
  - [ ] Given an Accept classification, When the fix is applied, Then `/verify` is invoked before the item is marked resolved
  - [ ] Given a Push Back classification, When a counterargument is written, Then the skill requires a technical reason (not preference)
  - [ ] Given all items are processed, When the summary is produced, Then it lists Accepted, Pushed Back, Deferred with reasons for each
  - [ ] Given YOLO=true, When `/receive-review` runs, Then items are classified and Accepted items fixed automatically; Push Back and Defer items are listed for manual follow-up

#### Feature 5: tcs-workflow:parallel-agents — Explicit Parallel Dispatch

- **User Story:** As a developer needing parallel work, I want a structured pattern for dispatching multiple independent agents so that context, safety, and conflict avoidance are consistent.
- **Notes:** Incorporates centminmod batch-operations patterns: explicit parallel/sequential phasing and conflict grouping.
- **Acceptance Criteria:**
  - [ ] Given 2+ independent tasks, When `/parallel-agents` is invoked, Then it validates tasks are truly independent before dispatching
  - [ ] Given tasks with shared file writes, When the skill runs, Then it warns about conflict risk and suggests worktree isolation
  - [ ] Given dispatched agents complete, When results are collected, Then the skill presents a structured merge/discard decision for each output
  - [ ] Given a task description, When the agent is dispatched, Then it receives exactly the context it needs — no session history bleed
  - [ ] Given sequential dependency detected, When tasks are submitted, Then the skill re-orders them and explains why
  - [ ] Given YOLO=true, When `/parallel-agents` runs, Then agents are dispatched without confirmation prompts

#### Feature 6: tcs-workflow:guide — Flowchart-Style Orientation Skill (Re-invokable)

- **User Story:** As a developer at any point in a workflow — including after session context loss — I want to invoke `/guide` to immediately know where I am and what to do next without re-reading documentation.
- **Notes:** Guide is the universal re-entry point. It reads current branch state and open plan files to reconstruct context. Every skill ends by suggesting `/guide` for orientation if unsure. Guide is user-invocable (not a background hook) so it can be called on demand.
- **Acceptance Criteria:**
  - [ ] Given a developer with no context, When `/guide` is invoked, Then it reads the current branch and open plan files and announces current state: phase, last completed task, next action
  - [ ] Given an intent like "new feature", When the skill resolves the path, Then it outputs the full sequence: brainstorm → xdd → xdd-sdd → xdd-plan → implement → test → review
  - [ ] Given an intent like "I got a code review", When resolved, Then it routes to `/receive-review`
  - [ ] Given an intent like "my tests are failing", When resolved, Then it routes to `/debug`
  - [ ] Given a session after context compaction, When `/guide` is invoked with no argument, Then it detects the open plan and announces: "Continuing [spec-name] phase [N]. Next: [task]. Run `/implement phase-N` to resume."
  - [ ] Given the decision tree, When any path is followed, Then every skill in tcs-workflow is reachable from at least one path
  - [ ] Given every other skill completes, When it concludes, Then it announces the next step and notes that `/guide` can be invoked for orientation

#### Feature 7: Enhanced tcs-workflow:brainstorm — Spec-Review Loop

- **User Story:** As a developer completing a brainstorm, I want an optional spec-review subagent so that the design is validated before committing to specification.
- **Acceptance Criteria:**
  - [ ] Given a design is approved in brainstorm, When the skill concludes, Then it offers to dispatch a spec-review subagent before invoking `/specify`
  - [ ] Given the spec-review subagent runs, When it finds gaps, Then it presents them as structured clarification prompts (not rejections)
  - [ ] Given spec-review finds no gaps, When it completes, Then it hands off cleanly to `/specify` with the design context and announces: "Design validated. Run `/specify` to write the PRD."

#### Feature 8: Enhanced tcs-workflow:debug — Iron-Law Anti-Shortcut Discipline

- **User Story:** As a developer debugging, I want the debug skill to enforce root-cause investigation before allowing fixes so that symptoms are never patched without understanding the cause.
- **Acceptance Criteria:**
  - [ ] Given a bug is reported, When `/debug` is invoked, Then it requires a hypothesis before any fix is attempted
  - [ ] Given a shortcut impulse (retry, force-pass, skip test), When detected, Then the skill presents the anti-shortcut table and blocks
  - [ ] Given a root cause is identified, When the fix is written, Then `/verify` is invoked to confirm the fix resolves root cause, not just symptom
  - [ ] Given debug resolves, When it concludes, Then it announces: "Bug resolved. Run `/verify` to confirm, then `/review` if on a feature branch."

#### Feature 9: Enhanced tcs-workflow:review — Dispatch with SHA Context

- **User Story:** As a developer requesting a code review, I want the skill to dispatch subagents with precise BASE_SHA/HEAD_SHA context so that reviewers see only the relevant diff.
- **Acceptance Criteria:**
  - [ ] Given a branch ready for review, When `/review` is invoked, Then it resolves BASE_SHA and HEAD_SHA automatically from git
  - [ ] Given the SHA pair, When the subagent is dispatched, Then it receives the diff bounded by those SHAs
  - [ ] Given the review completes, When issues are returned, Then they are categorized by severity: Critical | Important | Suggestion
  - [ ] Given review completes, When it concludes, Then it announces: "Review complete. Run `/receive-review` to process feedback."

#### Feature 10: Enhanced tcs-workflow:implement — Fresh-Subagent + Two-Stage Review + TDD Enforcement

- **User Story:** As a developer executing a plan, I want each task dispatched to a fresh subagent with TDD enforced before code, spec compliance reviewed before code quality, so that over-building, under-building, and test-skipping are all caught.
- **Notes:** Model selection per task: mechanical isolated tasks → cheap model; multi-file integration → standard model; design/judgment → most capable. Subagents hand off work via TaskTool where applicable.
- **Acceptance Criteria:**
  - [ ] Given a plan phase, When `/implement` runs a task, Then it dispatches a fresh subagent with only the context that task needs
  - [ ] Given the subagent's task has RED steps, When the subagent starts, Then it receives TDD enforcement context before writing any implementation
  - [ ] Given the subagent completes, When spec compliance review runs, Then it checks: nothing missing AND nothing added beyond spec
  - [ ] Given spec compliance passes, When code quality review runs, Then it checks: correctness, naming, test coverage, simplicity
  - [ ] Given either review finds issues, When the subagent fixes them, Then the same reviewer re-reviews before moving to the next task
  - [ ] Given all tasks complete, When the phase ends, Then the skill announces: "Phase complete. Run `/verify` then `/review`."
  - [ ] Given YOLO=true, When `/implement` runs, Then all task dispatches and reviews proceed without confirmation prompts

#### Feature 11: Enhanced tcs-workflow:xdd-plan — RED/GREEN/REFACTOR Task Structure + SDD Binding

- **User Story:** As a developer writing a plan, I want every implementation task to include explicit RED/GREEN/REFACTOR steps anchored to an SDD contract so that TDD is embedded in the plan, not bolted on during implementation.
- **Acceptance Criteria:**
  - [ ] Given an SDD contract, When a plan task is generated, Then it includes: `[ref: SDD/Section X.Y]`, RED (test names + expected failures), GREEN (minimal implementation path), REFACTOR (cleanup criteria)
  - [ ] Given a plan task without RED steps, When `/implement` reads it, Then it flags the task as incomplete and prompts to add RED steps before dispatching
  - [ ] Given a plan task without an SDD reference, When `/implement` reads it, Then it warns and requires confirmation that the task is intentionally self-contained
  - [ ] Given plan is complete, When it concludes, Then it announces: "Plan ready. Run `/implement phase-1` to begin."

#### Feature 12: tcs-helper:git-worktree — Isolated Branch Workspaces

- **User Story:** As a developer starting feature work, I want a skill to create isolated worktrees so that multiple features can be worked in parallel without branch switching.
- **Acceptance Criteria:**
  - [ ] Given a feature branch name, When `/git-worktree` is invoked, Then it creates a worktree at a predictable path with the branch checked out
  - [ ] Given an existing worktree, When the skill is invoked again, Then it detects the conflict and offers to reuse or create a new one
  - [ ] Given a worktree is no longer needed, When cleanup is invoked, Then it removes the worktree directory and optionally deletes the branch
  - [ ] Given YOLO=true, When `/git-worktree` creates a worktree, Then it proceeds without confirmation prompts

#### Feature 13: tcs-helper:finish-branch — Branch Completion Workflow

- **User Story:** As a developer finishing a feature, I want a structured decision workflow so that branches are consistently merged, PR'd, kept, or discarded with appropriate cleanup.
- **Acceptance Criteria:**
  - [ ] Given a feature branch, When `/finish-branch` is invoked, Then tests are run before presenting options
  - [ ] Given failing tests, When the skill runs, Then it blocks and does not offer merge/PR options
  - [ ] Given passing tests, When options are presented, Then exactly four are shown: merge locally | push and create PR | keep as-is | discard
  - [ ] Given discard is chosen, When confirmed with typed "discard", Then the branch and worktree are deleted
  - [ ] Given a PR is created, When the skill completes, Then it returns the PR URL
  - [ ] Given YOLO=true and option pre-specified (e.g., `YOLO_FINISH=pr`), When `/finish-branch` runs, Then it proceeds without confirmation

#### Feature 14: tcs-helper:docs — On-Demand Documentation Fetcher with Cache

- **User Story:** As Claude Code working in a TCS session, I want to fetch and cache current Claude Code documentation so that I'm working from accurate, up-to-date API knowledge — not stale embeddings.
- **Notes:** Primary consumer is Claude itself (for hooks, tools, MCP, permissions reference). Check for a running MCP docs server before direct WebFetch. Cache to `docs/ai/external/claude/` (gitignored). Cache is scoped per-repo.
- **Acceptance Criteria:**
  - [ ] Given a docs topic (e.g., "hooks", "MCP", "tool permissions"), When `/docs` is invoked, Then it first checks if an MCP docs server is available; if yes, delegates to it; if no, fetches directly via WebFetch
  - [ ] Given a fetched page, When content is returned, Then it is cached to `docs/ai/external/claude/<topic>.md` and the cache timestamp is recorded
  - [ ] Given a cached file, When `/docs` is invoked for the same topic, Then it returns the cached version unless `--refresh` is passed or cache is older than 7 days
  - [ ] Given an unknown topic, When the skill runs, Then it lists available topic categories (from a known topic index)
  - [ ] Given the cache directory, When present, Then it is listed in `.gitignore`

#### Feature 15: tcs-team:the-architect/record-decision — ADR Agent

- **User Story:** As a developer making an architectural decision, I want an ADR agent to produce a well-structured Architecture Decision Record placed under the project's configured docs base directory.
- **Notes:** All TCS-managed artifacts live under a single configurable base (`docs_base` in `startup.toml`). Default `docs_base = "docs/XDD"`. Under it: `<docs_base>/adr/`, `<docs_base>/specs/`, `<docs_base>/ideas/`. No legacy `.start/specs/` fallback — new path only. In most projects the default `docs/XDD` base is sufficient; a custom base (e.g. `docs/XDD/project`) is available but not required.
- **Acceptance Criteria:**
  - [ ] Given a decision to record, When the ADR agent is invoked, Then it produces a record with: Title, Status, Context, Decision, Consequences
  - [ ] Given no `startup.toml` override, When an ADR is written, Then it is placed in `docs/XDD/adr/` with a sequential number prefix (e.g., `ADR-001-*.md`)
  - [ ] Given a `startup.toml` with `docs_base = "docs/project"`, When an ADR is written, Then it is placed in `docs/project/adr/`
  - [ ] Given specs or ideas, When written by any TCS skill, Then they follow the same `<docs_base>/specs/` and `<docs_base>/ideas/` convention
  - [ ] Given an existing ADR is superseded, When the agent records the new decision, Then the old ADR status is updated to "Superseded" and links to the new one
  - [ ] Given the record is written, When the agent concludes, Then it announces the file path and suggests running `/guide` if context is unclear

#### Feature 16: tcs-workflow:tdd-guardian Agent (citypaul pattern)

- **User Story:** As a developer using any TCS skill that dispatches code-writing subagents, I want a lightweight guardian agent to enforce TDD compliance within each subagent so that the enforcement is consistent, token-efficient, and model-selectable.
- **Notes:** This is the citypaul tdd-guardian pattern translated to TCS. A dedicated guardian agent (not embedded in the SKILL.md) holds the TDD rules and is dispatched alongside every code-writing subagent. Cheap model (haiku) for the guardian since enforcement is mechanical.
- **Acceptance Criteria:**
  - [ ] Given any TCS skill that dispatches a code-writing subagent, When the subagent is dispatched, Then the tdd-guardian agent is also dispatched with it as a gating check
  - [ ] Given the tdd-guardian receives a task, When it evaluates the subagent's proposed approach, Then it blocks if no test plan is present
  - [ ] Given a test plan exists, When the tdd-guardian approves, Then the code-writing subagent proceeds
  - [ ] Given YOLO=true, When the tdd-guardian runs, Then violations are logged to `docs/ai/memory/context.md` and the subagent proceeds (no blocking in YOLO mode)

#### Feature 17: CoD (Chain of Draft) Mode — Default On

- **User Story:** As a developer using `/analyze` or any token-heavy research skill, I want Chain of Draft mode to be on by default so that token usage is minimized for codebase searches and analysis tasks.
- **Notes:** CoD is the centminmod notation for token-efficient reasoning. Default-on (not a flag). Can be disabled with `--no-cod` for verbose output. Apply to `/analyze` and `/debug` primary research phases.
- **Acceptance Criteria:**
  - [ ] Given `/analyze` is invoked, When codebase research runs, Then it uses CoD notation by default (abbreviated reasoning, structured output)
  - [ ] Given `--no-cod` is passed, When the skill runs, Then it uses standard verbose output
  - [ ] Given `/debug` is invoked in its investigation phase, When searching for root cause, Then CoD mode applies to the search steps
  - [ ] Given CoD output is produced, When the user reads it, Then it is structured and interpretable (not cryptic abbreviations)

### Should Have Features

- **Progress-guardian pattern in `/implement`:** Plan-file progress tracking across sessions from citypaul — track task state so a new session can resume exactly where the previous one left off. Delegates to a progress-tracking agent (not embedded in skill). Medium priority.
- **PR requirements checklist:** citypaul-style TDD compliance checklist appended to PR description by `/review`. Verifies test coverage claims before creating the PR.

### Could Have Features

- **batch-operations conflict grouping in `/parallel-agents`:** More sophisticated grouping of file-conflict risk from centminmod patterns. Useful but initial parallel agent support already handles the common cases.

### Won't Have (This Phase)

- **tcs-patterns plugin** — domain knowledge skills (DDD, hexagonal, etc.) are M3
- **tcs-helper:evaluate and import-skill** — post-M1 additions
- **Backward-compatible tcs-start aliases** — hard rename, single user
- **Any MCP integration** — M4 scope
- **Memory system changes** — M2 complete

---

## Detailed Feature Specifications

### Feature: tcs-workflow:implement (Enhanced)

**Description:** The implementation orchestrator gains fresh-subagent-per-task execution, TDD enforcement (via tdd-guardian) before each task, and a two-stage post-task review loop (spec compliance → code quality). Model selection is per task complexity.

**User Flow:**
1. Developer invokes `/implement phase-N`
2. Skill reads all tasks in the phase, creates task list
3. For each task:
   a. Validate task has RED/GREEN/REFACTOR steps and SDD reference — if not, prompt to add
   b. Select model: mechanical task (1-2 files, clear spec) → haiku; integration task → sonnet; design/judgment → opus
   c. Dispatch tdd-guardian agent alongside fresh implementer subagent
   d. Subagent may ask questions before starting — answer before proceeding
   e. Guardian confirms test plan before implementation begins
   f. Subagent implements: RED → GREEN → REFACTOR
   g. Spec compliance reviewer (sonnet): all spec requirements met, nothing extra
   h. If gaps: implementer fixes, reviewer re-checks
   i. Code quality reviewer (sonnet): correctness, naming, simplicity, test coverage
   j. If issues: implementer fixes, reviewer re-checks
   k. Task marked complete; move to next
4. After all tasks: final full-implementation review dispatched
5. Skill announces: "Phase complete. Run `/verify` then `/review`."

**Business Rules:**
- GREEN cannot start until RED tests exist and fail for the right reason
- Spec compliance review must pass before code quality review begins
- BLOCKED subagent: not retried with same model without changed context or scope
- No subagent inherits session history — context is curated per task
- YOLO=true: all confirmations skipped; violations logged to `docs/ai/memory/context.md`

**Edge Cases:**
- Task without SDD reference → prompt: "No SDD reference. Add one or confirm self-contained."
- Subagent reports DONE_WITH_CONCERNS → coordinator reads concerns before dispatching reviewer
- Reviewer finds correct deviation from spec → escalate to user with both sides

---

### Feature: tcs-workflow:guide (Re-entry Orientation)

**Description:** Guide is the universal orientation skill. It can be invoked cold (start of session), mid-session (after confusion), or post-compaction (to recover context). It reads git state and open plan files — no session memory required.

**User Flow:**
1. Developer invokes `/guide` (with or without intent argument)
2. Guide runs a bash script: `git branch --show-current`, reads open plan phase files, checks `docs/ai/memory/context.md` for last-known state
3. If open plan phase exists: announces "Continuing [spec-name] phase [N]. Last completed: [task]. Next: [task]. Run `/implement phase-N` to resume."
4. If no open phase: presents intent menu and resolves to skill sequence
5. Every path ends with a specific next action

**Business Rules:**
- Guide never asks more than one clarifying question before routing
- Guide output is short — orientation, not documentation
- Every other skill ends by suggesting guide if orientation is needed

---

## Success Metrics

### Key Performance Indicators

- **Discipline compliance:** Every implementation session uses TDD enforcement before production code. Zero "I'll write tests later" sessions.
- **Verification coverage:** Every completed task has a `/verify` evidence block.
- **Guide adoption:** After context loss, developer re-orients in ≤1 guide invocation.
- **Plugin coherence:** All workflow invocations go through `tcs-workflow:*`. No reaching for superpowers or citypaul skills directly.
- **Token efficiency:** CoD mode reduces analyze/debug token usage by an estimated 30-40% vs. verbose mode.
- **Skill completeness:** All 17 Must Have features ship and are used in at least one real session.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `/xdd-tdd` invoked | task name, guardian outcome | Confirm TDD used per task |
| `/verify` invoked | task name, evidence type | Confirm evidence-first discipline |
| `/receive-review` invoked | item count, accept/pushback ratio | Track review quality |
| `/guide` invoked | trigger context (cold/mid/post-compact), resolved path | Identify orientation gaps |
| tdd-guardian blocked | task name, reason | Track TDD violations caught before code written |

---

## Constraints and Assumptions

### Constraints

- All skills must be plain markdown (SKILL.md) — no runtime dependencies beyond Claude Code's built-in tools
- Skills must work on macOS with bash 3.2 (no `declare -A`, no bash 4+ features)
- Plugin rename must not break the existing `/implement` → `/xdd-plan` → `/xdd` call chain
- Each SKILL.md must stay under ~25 KB (progressive disclosure via `reference/` subdirs)
- Python scripts must use a venv — never `pip install --break-system-packages` (PEP 668 / macOS externally managed Python)
- `docs/ai/external/claude/` must be gitignored before the docs skill writes to it
- superpowers, tcs-helper, and legacy tcs-start plugins may coexist during the transition — tcs-workflow must not conflict with their skill names
- `rg` (ripgrep), `fd`, and `fzf` must be installed — skills that search files depend on them. Skills must check for presence and fail gracefully with install instructions if absent.
- Every new skill and agent must be authored via `/tcs-helper:skill-author`, not hand-crafted

### Assumptions

- Primary user is Marcus; the rename requires no external migration
- The SDD and PLAN for each feature will be written in this branch before implementation begins
- All source material (superpowers, citypaul, centminmod) analysis is complete in `docs/concept/overlap-analysis.md`
- `startup.toml` is the canonical config file; single `docs_base` key covers all artifact paths (adr, specs, ideas). No legacy `.start/specs/` detection or fallback.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Plugin rename breaks install.sh, uninstall.sh, README | High | Medium | Grep all tcs-start refs before committing rename; test install/uninstall end-to-end |
| tdd-guardian adds latency per task | Medium | High | Use cheapest model (haiku) for guardian; guard is mechanical, not reasoning-heavy |
| `/guide` state detection gets stale if plan files are not updated | Medium | Medium | Guide reads actual plan files (live state), not cached session data |
| Enhanced `/implement` too verbose for simple tasks | Medium | Medium | Provide `--fast` flag: skip two-stage review for single-file mechanical tasks |
| CoD output too terse for complex debug sessions | Low | Medium | `--no-cod` escape hatch; CoD is default, not forced |
| `docs/ai/external/claude/` accidentally committed | Medium | Low | gitignore added as part of docs skill acceptance criteria |

---

## Open Questions

All open questions resolved. No outstanding items.

---

## Supporting Research

### Competitive Analysis

Source repos analyzed in `docs/concept/overlap-analysis.md`:
- **obra/superpowers:** TDD discipline, verification gate, parallel dispatch, receiving review, subagent-driven development — ABSORB/MERGE
- **citypaul/.dotfiles:** tdd-guardian agent pattern, RED/GREEN/REFACTOR task format, ADR agent, progress-guardian — ABSORB/MERGE
- **centminmod/my-claude-code-setup:** CoD mode, batch operations, docs fetcher — ABSORB

### User Research

Requirements validated directly with Marcus across multiple sessions. Extended to cover additional personas for broader TCS adoption.

### Market Data

Not applicable for internal framework. Generalizable design principles noted in persona section.
