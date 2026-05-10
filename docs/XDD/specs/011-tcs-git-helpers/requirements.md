---
title: "tcs-git-helpers — Git Workflow Discipline Plugin for Claude Code"
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
| specId | 011-tcs-git-helpers |
| title | tcs-git-helpers — Git Workflow Discipline Plugin for Claude Code |
| status | DRAFT |
| sections | 11 sections, all COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 38 testable criteria across 13 features |
| openQuestions | 5 open questions for stakeholder review (see §Open Questions) |

---

## Product Overview

### Vision
A Claude Code plugin that machine-enforces git workflow discipline so Claude (the AI agent) cannot reliably reproduce its most expensive recurring mistakes across all MiYo repos and beyond.

### Problem Statement

Marcus operates seven git repositories in the MiYo ecosystem (Kado, Hakobi, Tomo, Kokoro, Kouzou, Seigyo, Hashi) plus the TCS plugin repository itself. Claude — the AI coding agent — has no persistent memory across sessions and reflexively makes a recurring set of git workflow mistakes. Each mistake costs Marcus minutes-to-hours of recovery work.

**Documented incidents and current evidence:**

| Failure Mode | Evidence |
|---|---|
| Pushes to closed/merged PRs | Recurring incident type; pollutes closed PRs |
| New branches from unfinished work | Most common form: branch is *clean but unmerged*, Claude branches from main → prior work orphaned silently. Less common: branch from dirty working tree |
| Squash-merge branch reuse | Marcus has documented finding: PR shows `mergeable: CONFLICTING` because squash rewrote SHAs; recovery requires cherry-pick onto fresh branch |
| Edits/commits attempted on main/master | Existing `~/.claude/hooks/block-main-edits.sh` denies, but Claude keeps blundering instead of pre-flighting |
| Bad commit/merge messages | Existing `commit-msg` only checks length; Conventional Commits not enforced |
| Stale local branches | Kado currently has 6 local branches whose PRs were merged but were never cleaned up: `docs/restructure-documentation`, `feat/read-tags-operation`, `feat/search-filter`, `chore/github-funding`, `docs/api-reference-add-kado-open-notes`, `fix/issue-8-blacklist-crud-semantics` |
| Destructive git ops | Reflexive `reset --hard`, `clean -f`, `branch -D`, `stash drop`, `reflog expire`, `--no-verify` — often invoked to "fix" a state that should have been investigated first (prior art: Boucle-framework `git-safe`) |
| Worktree exit data loss | Exiting a Claude Code worktree session can delete branches and uncommitted/unpushed work without warning (prior art: Boucle-framework `worktree-guard`) |

**Live incident captured during brainstorm:** While designing this very plugin, Claude was about to write the spec file from `main` until Marcus manually prompted a branch switch. Even when designing the safety net, Claude forgets to pre-flight.

**Cost measure:** Marcus estimates roughly 30 minutes per week recovering from these mistakes across all repos. The recovery is high-cognitive-load (cherry-picking, force-with-lease patterns, audit-trail reconstruction) and disrupts focus.

**Why existing protections are insufficient:**
- `~/.claude/hooks/block-main-edits.sh` only covers main-branch edits, not pushes/branches/destructive ops
- Kado's `.githooks/pre-commit` and `commit-msg` are repo-local, not distributed; commit-msg is length-only
- Other MiYo repos lack any `.githooks/` setup
- No machine enforcement around branch lifecycle (open PR state, squash-merge detection)

### Value Proposition

For Marcus and (future) TCS adopters, `tcs-git-helpers` delivers:

1. **Machine-enforced rules** — Claude cannot rely on remembering git discipline; the plugin denies catastrophic ops at the tool layer
2. **Defense in depth** — `.githooks/` files committed to each repo continue protecting Docker, CI, and other contributors even when the plugin is disabled
3. **Granular overrides + audit** — every safety bypass is single-shot and logged, so emergencies don't silently persist into routine
4. **Distributed via TCS** — one plugin install protects every repo Marcus enables it in
5. **Best-practices knowledge base** — `references/` docs are cited from denial messages so Claude (and Marcus) can act on root-cause understanding, not just blocked operations

Compared to Boucle-framework's three separate tools (`git-safe`, `branch-guard`, `worktree-guard`): unified plugin, integrated with TCS conventions, richer denial messages with reference links, granular per-violation overrides instead of binary disable.

## User Personas

### Primary Persona: Claude (the Agent)
- **Demographics:** AI coding agent (model claude-opus-4-7 and successors); software engineering proficiency; no persistent memory across sessions; operates inside Claude Code's hook surface
- **Goals:** Complete user-assigned coding tasks correctly and quickly; avoid catastrophic git operations that lose work; recover gracefully when mistakes happen
- **Pain Points:** Forgets workflow rules between sessions; reflexively reaches for destructive commands when investigation would be safer; cannot self-discipline reliably without external enforcement; relies on external state (hooks, denial reasons, reference docs) to inform safe behavior

### Secondary Persona: Marcus (the Operator)
- **Demographics:** Senior software engineer; primary repo owner across MiYo ecosystem and TCS; deeply familiar with git internals; uses Claude Code daily across 7+ repos; macOS-first
- **Goals:** Ship features quickly without paying recovery cost for Claude's git mistakes; retain ability to override safety rules in legitimate emergencies; audit Claude's bypass behavior post-hoc
- **Pain Points:** Estimated 30 minutes per week recovering from Claude's recurring git mistakes; same mistakes recur across sessions; existing hooks are partial and inconsistent across repos

### Secondary Persona: Future TCS Adopter (Other Developer)
- **Demographics:** Developer adopting TCS plugin ecosystem from public marketplace; varying levels of git proficiency; no prior MiYo context
- **Goals:** Get the same Claude-discipline protections that Marcus has; understand denials and overrides without prior context
- **Pain Points:** External marketplace consumers see only README + denial messages + references, not Marcus's design context — content must be self-contained
- **v1.0 priority:** "shouldn't break for them" only. First-class onboarding deferred to v1.1.

## User Journey Maps

### Primary User Journey: Claude encounters a safety hook
1. **Awareness:** During task execution, Claude attempts a `git push` (or similar) via the Bash tool
2. **Consideration:** PreToolUse hook intercepts; evaluates against rule set; returns `permissionDecision: deny` with structured reason
3. **Adoption:** Claude reads the denial: rule name, branch state, recovery steps, reference doc path, override env-var name
4. **Usage:** Claude either (a) follows recovery steps (e.g., cherry-pick to fresh branch), (b) reads cited reference doc and adapts approach, or (c) sets the granular override env-var and re-attempts (single-shot consumption)
5. **Retention:** Subsequent attempts on similar patterns are denied unless override is re-set; pattern re-encountered in next session because no persistent memory — denial pathway re-traversed reliably

### Secondary User Journey: Marcus installs the plugin in a new repo
1. **Awareness:** Marcus opens a Claude Code session in a repo that lacks `.githooks/` integration
2. **Consideration:** SessionStart brief surfaces "no .githooks/ — run /tcs-git-helpers:setup"; Marcus decides to install
3. **Adoption:** Marcus runs `/tcs-git-helpers:setup`; skill detects existing tooling (Husky/lefthook/etc.), conflicts, or clean state; copies templates with version markers; sets `core.hooksPath`
4. **Usage:** Marcus reviews the diff, commits the `.githooks/` files. Subsequent Claude sessions are protected. Marcus runs `/tcs-git-helpers:status` periodically to surface stale branches and override audit
5. **Retention:** Plugin updates trigger marker mismatch; `setup --update` shows per-file diff; Marcus reviews and accepts

### Secondary User Journey: Marcus uses an emergency override
1. **Awareness:** Claude is denied `git push` because the branch's PR is closed; Marcus knows it's intentional (backporting a fix to a closed line)
2. **Consideration:** Marcus instructs Claude to set `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1` and re-attempt
3. **Adoption:** Hook detects env var, allows push, consumes the override (one-shot), appends audit JSONL line, emits "override consumed" stderr
4. **Usage:** Subsequent push attempts re-deny unless override is re-set
5. **Retention:** Marcus reviews `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` weekly via `/tcs-git-helpers:status --overrides`; spots patterns of legitimate vs reflexive bypass

## Feature Requirements

### Must Have Features

These cover the 12 documented failure modes and the cross-cutting override-discipline goal. v1.0 ships all of them.

#### Feature M1: Block pushes to closed/merged PRs
- **User Story:** As Claude, when I attempt `git push` on a branch whose PR is CLOSED or MERGED, I want the operation denied with a recovery path so I don't pollute the closed PR.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given a local branch with a CLOSED PR on the origin remote, When Claude runs `git push`, Then the operation is denied with `permissionDecision: deny` and the denial cites PR number+state
  - [ ] Given a local branch with a MERGED PR, When Claude runs `git push`, Then the operation is denied and the denial links to `references/squash-merge-trap.md`
  - [ ] Given `gh` is unauthenticated or rate-limited, When Claude runs `git push`, Then the operation is allowed with a stderr warning (fail-open)
  - [ ] Given `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1` is set, When Claude runs `git push`, Then the operation is allowed once, the override is logged to audit, and stderr reports "override consumed"
  - [ ] Given the plugin is disabled but `.githooks/pre-push` is installed, When Marcus runs `git push`, Then `.githooks/pre-push` produces equivalent denial via exit code 1

#### Feature M2: Block branch creation from unfinished work
- **User Story:** As Claude, when I run `git checkout -b` while the current branch is *clean but unmerged/un-PR'd* OR while the working tree is dirty, I want creation denied so I don't silently abandon prior work.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given the current branch is clean but has commits ahead of `origin/<default>` AND no PR exists for the branch, When Claude runs `git checkout -b feat/new`, Then the operation is denied citing "current branch unfinished"
  - [ ] Given the working tree has uncommitted changes, When Claude runs `git switch -c feat/new`, Then the operation is denied citing "working tree dirty"
  - [ ] Given `CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1` is set, When Claude runs the branch-creation command, Then the operation is allowed once and override is logged
  - [ ] Given the override permits only this violation type, When Claude separately attempts a denied push, Then the push is still denied (granular overrides do not cross-bypass)

#### Feature M3: Block resume of squash-merged branches
- **User Story:** As Claude, when I `git checkout <branch>` whose PR was squash-merged, I want it denied so I don't hit `mergeable: CONFLICTING`.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given a local branch whose PR was squash-merged (detected via `git cherry origin/<default> <branch>` returning all `-` lines), When Claude runs `git checkout <branch>`, Then the operation is denied citing `references/squash-merge-trap.md` with cherry-pick recovery instructions
  - [ ] Given a local branch whose PR was merge-commit merged (branch tip is ancestor of `origin/<default>`), When Claude runs `git checkout <branch>`, Then the operation is allowed (false-positive avoidance)
  - [ ] Given `CLAUDE_ALLOW_RESUME_MERGED_BRANCH=1` is set, When Claude runs `git checkout <merged-branch>`, Then the operation is allowed once and logged

#### Feature M4: Pre-flight branch awareness brief
- **User Story:** As Claude, at session start AND after a successful pull/merge, I want a one-line brief on branch state so I don't need to remember to run `git status` first and so I notice when state changed mid-session.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given Claude Code starts a session in a git repo with the plugin enabled, When the SessionStart event fires, Then a one-line brief is emitted with branch (warning marker if protected), working-tree state, ahead/behind counts, and stale-merged branch count, completing in under 300ms
  - [ ] Given Claude or Marcus runs `git pull` or a merge, When `.githooks/post-merge` completes and refreshes the stale-branch cache, Then a brief is re-emitted to stderr (cache is already warm; re-emit cost <50ms)
  - [ ] Given the stale-branch cache is older than 24h, When the brief renders, Then the brief includes a staleness indicator
  - [ ] Given the SessionStart hook makes no `gh` network calls, When measured, Then the brief uses only local-git and cache-read operations
  - [ ] Given a repo has the plugin enabled but no `.githooks/` installed, When the brief renders, Then it surfaces "run /tcs-git-helpers:setup"

#### Feature M5: Conventional Commits enforcement
- **User Story:** As Marcus, I want commits to fail unless they match Conventional Commits format so the squash-merge commit on default is well-formed.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given a commit message subject not matching `<type>(<scope>)?!?: <subject>` (where type is in the allowlist), When `git commit` runs, Then `commit-msg` hook rejects with exit code 1
  - [ ] Given `TCS_REQUIRE_SCOPE=1` in `.githooks/.config`, When a commit is attempted with type-only (no scope), Then the hook rejects
  - [ ] Given a merge commit (subject begins `Merge branch …` / `Merge pull request …` OR `MERGE_HEAD` exists), When `git commit` runs, Then `commit-msg` hook accepts (merges excluded from format check)
  - [ ] Given the commit subject contains `[skip-format-check]`, When `git commit` runs, Then `commit-msg` hook accepts (override visible in `git log`)

#### Feature M6: Stale local branch surfacing
- **User Story:** As Marcus, after `git pull` I want a non-blocking suggestion list of local branches whose PRs have merged so they don't accumulate.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `.githooks/post-merge` runs after `git pull`, When local branches with merged PRs exist, Then a suggestion list is emitted to stderr without blocking the merge
  - [ ] Given Marcus runs `/tcs-git-helpers:status --cleanup`, When stale-merged branches exist, Then they are listed and Marcus is prompted to delete each interactively
  - [ ] Given a stale-merged branch is currently checked out in a worktree, When `--cleanup` runs, Then that branch is excluded from the deletion candidates

#### Feature M7: Block destructive git operations
- **User Story:** As Claude, when I reflexively run a destructive git operation, I want denial with a recovery alternative.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given Claude runs any of `git reset --hard`, `git clean -f/-fx`, `git branch -D`, `git stash drop`, `git stash clear`, `git reflog expire`, `git commit --no-verify`, `git commit -n`, `git checkout .`, `git checkout -- <path>`, `git restore --worktree --source=…`, `git push --force` (without `--force-with-lease`), `git push --delete`, `git -c core.hooksPath …`, or `git config core.hooksPath …`, When the Bash tool is invoked, Then the operation is denied
  - [ ] Given each pattern has a granular env-var override (e.g., `CLAUDE_ALLOW_RESET_HARD=1`), When the appropriate override is set, Then the operation is allowed once and audit-logged
  - [ ] Given `CLAUDE_ALLOW_GIT_BAD_OPS=1` (master override) is set, When Claude runs any destructive op, Then the operation is allowed once with loud stderr warning ("⚠ MASTER OVERRIDE — strongly prefer granular `CLAUDE_ALLOW_<X>=1`") and audit logs `master=true`
  - [ ] Given a compound command like `cd foo && git push --force`, When the Bash tool is invoked, Then the destructive subcommand is detected via regex on the full command string

#### Feature M8: Worktree exit data-loss guard
- **User Story:** As Marcus, when Claude exits a worktree session with uncommitted/untracked/unmerged/unpushed work, I want exit blocked with a clear summary so I don't silently lose work.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given Claude attempts to exit a worktree via the `ExitWorktree` tool with uncommitted or untracked changes in the worktree, When the PreToolUse:ExitWorktree hook runs, Then the exit is denied citing the four-check summary (uncommitted/untracked/unmerged/unpushed)
  - [ ] Given commits exist on the worktree's branch that are not yet applied to default (verified via `git cherry origin/<base> <branch>` returning `+` lines), When ExitWorktree is invoked, Then the exit is denied
  - [ ] Given `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1` is set, When ExitWorktree is invoked, Then the exit is allowed once and the override is consumed; subsequent attempts re-deny unless re-set

#### Feature M9: Soft nudges after key git ops
- **User Story:** As Claude, after a git op with a common follow-up step, I want a one-line reminder surfaced so I don't forget it.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given Claude successfully runs `git checkout -b <name>` or `git switch -c <name>`, When the PostToolUse:Bash hook fires, Then a stderr nudge suggests verifying the base is up-to-date and cites `references/branch-lifecycle.md`
  - [ ] Given Claude successfully runs `gh pr create` or first `git push -u origin <branch>`, When the PostToolUse hook fires, Then a stderr nudge suggests confirming the PR title matches Conventional Commits format (squash-merge implication) and cites `references/pr-vs-commit-messages.md`
  - [ ] Given Claude successfully runs `gh pr merge`, When the PostToolUse hook fires, Then a stderr nudge suggests `/tcs-git-helpers:status --cleanup`
  - [ ] Given Claude successfully runs `git rebase` (any variant), When the PostToolUse hook fires, Then a stderr nudge suggests verifying resulting history with `git log --oneline -10` and cites `references/rebase-vs-merge.md`
  - [ ] Given Claude successfully runs `git stash pop`, When the PostToolUse hook fires, Then a stderr nudge suggests verifying `.orig` cleanup and cites `references/working-tree-hygiene.md`
  - [ ] Given the Bash command had a non-zero exit status, When the PostToolUse hook fires, Then no nudge is emitted (nudges fire only on success)
  - [ ] Given the same nudge has already been emitted within 60 seconds for the current repo, When the PostToolUse hook fires for a matching command, Then no nudge is emitted (dedup window per OQ9)

#### Feature M10: Plugin distribution and per-repo setup
- **User Story:** As Marcus, I want `/tcs-git-helpers:setup` to install hooks per-repo idempotently with conflict detection so re-running is safe.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `/tcs-git-helpers:setup` runs in a repo with no existing hook tooling, When setup completes, Then `.githooks/` files are written with version markers, `core.hooksPath` is configured, and a summary lists what was installed
  - [ ] Given the repo has Husky / lefthook / pre-commit framework / simple-git-hooks installed, When setup runs, Then it aborts with a migration-doc reference (`references/migrating-from-husky.md` or equivalent)
  - [ ] Given the repo has `.git/hooks/` files that are not `.sample` files, When setup runs, Then it warns and asks for confirmation before proceeding (existing files won't fire because of `core.hooksPath` override)
  - [ ] Given two concurrent `setup` invocations on the same repo, When both attempt to write, Then `.githooks/.setup.lock` PID-file serializes (stale lock >5min reclaimed)
  - [ ] Given setup completes, When inspected, Then NO automatic commit is made; Marcus reviews and commits manually
  - [ ] Given the repo contains submodules, When setup runs, Then it explicitly notes submodules are not recursed and lists them

#### Feature M11: Defense-in-depth — `.githooks/` works without plugin
- **User Story:** As Marcus, when the plugin is disabled, I want `.githooks/` to still enforce the most important rules so non-Claude consumers (Docker, CI, my own terminal) remain protected.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given the plugin is disabled but `.githooks/` is installed, When `git commit`/`push`/`pull`/`merge` runs, Then each `.githooks/*` script produces the same exit code (0=allow, non-zero=deny) and the same stderr denial message as the plugin-side equivalent for the same input
  - [ ] Given `.githooks/` files are inspected, When opened, Then each contains `# tcs-git-helpers: vX.Y.Z` as the first comment line
  - [ ] Given the plugin is disabled and Claude attempts to edit a file on `main`, When the Write/Edit tool is invoked, Then user-global `~/.claude/hooks/block-main-edits.sh` continues to deny

#### Feature M12: Override discipline — single-shot + audit
This consolidates the cross-cutting US-OV.1 and US-OV.2.

- **User Story (12.a):** As Marcus, every safety override must be **single-shot** — applies to exactly one tool invocation and clears itself — so a one-time emergency doesn't quietly persist into routine operation.
- **User Story (12.b):** As Marcus, every override use must leave an audit trail so I can review post-hoc whether Claude's bypasses were legitimate.

- **Acceptance Criteria (Gherkin):**
  - [ ] Given any `CLAUDE_ALLOW_*` env-var is set, When the matching hook fires for the FIRST time, Then the override is consumed (operation allowed, env-var unset in hook context) and stderr reports "override consumed"
  - [ ] Given the override has been consumed, When a second matching operation is attempted, Then the operation is re-denied unless the override is re-set
  - [ ] Given any override is consumed, When the hook completes, Then a JSONL line is appended to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` with `{ts, repo, branch, hook, env_var, master, command, pattern}`
  - [ ] Given the audit file exceeds 1MB, When the next write occurs, Then the file is rotated to `.1` (and existing `.1` to `.2`) and a new file is started
  - [ ] Given the audit file is unwritable (disk full, permission), When the override consumption proceeds, Then the underlying hook decision is NOT blocked; the failure is logged to stderr
  - [ ] Given Marcus runs `/tcs-git-helpers:status --overrides`, When invoked in a repo, Then the last N override events for the current repo are printed in human-readable form

### Should Have Features

These improve the experience but are not v1.0 launch-blocking.

#### Feature S1: Optional GitHub branch protection (single-coder preset)
- **User Story:** As Marcus, when I run setup `--with-branch-protection`, I want planned single-coder-appropriate protection rules shown for confirmation before any `gh api` write.
- **Preset rules (locked per OQ2 — single-coder workflow, NO review requirement):**
  1. `allow_force_pushes = false` (no-force-push to default)
  2. `allow_deletions = false` (no-deletions of default)
  3. `required_linear_history = false` (allow merge commits AND squash; Marcus chooses per-PR)
  4. `enforce_admins = false` (Marcus retains override; this is a tripwire not a wall)
  5. `required_status_checks` is set ONLY if the repo has CI workflows (auto-detected via `.github/workflows/`); otherwise omitted
  6. `required_pull_request_reviews` is **NOT** set — single-coder mode; PR review enforcement would block all merges. Re-evaluate in v1.1 when multi-contributor mode lands
  7. Plus: `gh api -X PATCH repos/.../delete_branch_on_merge=true` to enable auto-delete-head-branches setting
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `setup --with-branch-protection` is invoked, When the skill runs, Then the planned ruleset (above) is printed and Marcus is prompted to confirm
  - [ ] Given `gh` token has only `repo` scope, When setup proceeds, Then the API calls are made silently
  - [ ] Given `gh` token has excessive scopes (`admin:org`, `delete_repo`, `admin:repo_hook`, etc.), When setup runs, Then a warning is emitted and Marcus is asked to confirm interactively
  - [ ] Given the token is missing `repo` scope, When setup runs, Then setup aborts with `gh auth refresh -s repo` instructions
  - [ ] Given an `gh api` call fails (auth error or permission denied), When the failure occurs, Then the failure is reported per call but does not roll back unrelated setup steps
  - [ ] Given the repo has no `.github/workflows/` directory, When setup applies protection, Then `required_status_checks` is omitted (no CI to enforce)
  - [ ] Given `delete_branch_on_merge` is already `true` on the repo, When setup runs, Then the PATCH is a no-op (idempotent)

#### Feature S2: GitHub Actions PR-title check (opt-in template)
- **User Story:** As Marcus, when my repo squash-merges PRs, I want a GHA workflow that validates PR title matches Conventional Commits format (since the title becomes the commit on default).
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `setup --with-gha` is invoked, When the skill runs, Then `templates/github-actions/pr-title-check.yml` is copied to `.github/workflows/`
  - [ ] Given the GHA template runs on `pull_request`, When a PR title doesn't match the configured Conventional Commits regex, Then the workflow fails

### Could Have Features

Nice-to-haves under consideration for v1.1+ if they align with adopter feedback.

- **`.git-safe` per-repo allowlist file** (Boucle pattern) — committed file with per-pattern allows; expands beyond env-var overrides
- **Cross-repo orchestration skill** — run `setup` across all known MiYo repos in one shot
- **Multi-account `gh` host detection** — `gh auth status --hostname <host>` gating before `--with-branch-protection`
- **Telemetry / `${CLAUDE_PLUGIN_DATA}/perf.log`** — hooks log their own runtime for regression detection
- **`if` permission-rule filter exploration** — push some pattern logic into Claude Code's matcher engine for performance

### Won't Have (This Phase)

Explicitly out of scope for v1.0; documented in §Open Questions or `references/` for future revisit.

- **Auto-delete merged branches** — v1.0 only suggests via `post-merge` and `--cleanup`; auto-delete needs more guardrails (concurrent sessions, worktrees)
- **Conventional-changelog / release-please integration** — separate tooling stack
- **Telemetry / violation tracking dashboards** — `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` is local-only in v1.0
- **AI-driven commit-message generation** — orthogonal concern
- **Per-repo custom validators beyond `.githooks/.config`** — plugin-extension surface deferred
- **Aggressive force-push detection beyond bare `--force`** — legitimate `--force-with-lease` flows must work
- **First-class onboarding for P3 (Future TCS Adopter)** — v1.0 = "shouldn't break"; v1.1 = polished docs, error messages, marketplace landing
- **Resolution of `/tcs-helper:finish-branch` triggering in wrong repo** — separate skill-discoverability concern; tracked in spec README

## Edge-Case Requirements

User-facing edge-case requirements that span multiple features. Numbered (EC1-EC8) so SDD and PLAN can cross-reference precisely.

| ID | Edge Case | Requirement |
|---|---|---|
| **EC1** | Denial message during long workflow | Denial message must (a) name rule, (b) name override env-var, (c) link reference doc, (d) be parseable in one read. Cap output ~15 lines. |
| **EC2** | Cascading denials | A single command tripping multiple rules must report **all** matched rules at once, not first-match-only — otherwise Claude solves one and re-trips immediately. |
| **EC3** | Setup mid-conflict | Interrupted `setup` (Ctrl-C, network drop) post-partial-copy must be safe to re-run via the `.githooks/.setup.lock` PID-file (5min stale reclaim). Setup is idempotent — re-running from scratch is the recovery. No stepwise state file needed in v1.0. |
| **EC4** | Plugin disabled mid-session | Disabling the plugin live must not leave half-protected state or spurious denials referencing missing scripts. `.githooks/` continues to enforce git-side; user-global `block-main-edits.sh` continues to enforce main edits. |
| **EC5** | Hook script error vs hook denial | Distinct user signals required. Script crashes must NOT present as legitimate denials (would train Claude to override). Use prefix `[tcs-git-helpers] DENIED:` for legitimate denials, `[tcs-git-helpers] ERROR:` for script failures. |
| **EC6** | Override env-var leakage | Env-vars must not leak across sessions/worktrees. Subsumed by US-OV.1 single-shot semantics — env-var consumption + 5s sentinel file ensures one-time effect. |
| **EC7** | Reference doc not found | Hook citing missing `references/foo.md` must still emit useful denial (graceful degradation). Denial includes rule + override even if reference path is broken; stderr warns separately. |
| **EC8** | Audit file unavailable | Per US-OV.2 AC4, audit failure (disk full, permission denied) cannot block the underlying hook decision. Hook proceeds with allow/deny per its rule; audit-write failure is logged to stderr only. |

## Detailed Feature Specifications

### Feature: M2 — Block branch creation from unfinished work (most-common failure mode)

**Description:** When Claude attempts to create a new branch via `git checkout -b` or `git switch -c`, the plugin inspects the current branch's state and denies if work would be silently abandoned. Two conditions trigger denial: (a) working tree is dirty, OR (b) current branch is clean but has unmerged work without a PR (the most common pattern observed in Marcus's incidents).

**User Flow:**
1. Claude is on `feat/foo`, has committed everything (clean tree), but `feat/foo` has not been pushed/PR'd
2. Claude runs `git checkout -b feat/bar` to start a new task
3. PreToolUse:Bash hook intercepts; the internal branch-state module checks current branch:
   - Working tree clean? Yes → not condition (a)
   - Branch ahead of `origin/<default>`? Yes → has unmerged commits
   - PR exists for branch? No → condition (b) triggered
4. Hook returns `permissionDecision: deny` with reason explaining the unfinished state and listing options:
   - Open a PR for `feat/foo` first
   - Merge `feat/foo` to default
   - If parking intentional: set `CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1`
5. Claude either resolves the prior branch or sets the override

**Business Rules:**
- Rule 1: Working tree dirty (any untracked or modified file not in gitignore) → DENY with "working tree dirty" reason
- Rule 2: Current branch has commits ahead of `origin/<default>` AND no open PR → DENY with "current branch unfinished" reason
- Rule 3: Both conditions can fire simultaneously; denial reason lists ALL applicable conditions (cascading-denial pattern, EC2)
- Rule 4: Granular override `CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1` consumes single-shot; subsequent attempts re-deny
- Rule 5: Override does not bypass other rules (M1 push-to-closed-PR, M3 squash-merge resume, M7 destructive-ops still active)
- Rule 6: When current branch IS the default branch (main/master), branching off is always allowed (branching from clean default is the desired pattern)

**Edge Cases:**
- **`git checkout -b` from main with dirty tree:** condition (a) fires → DENY (dirty tree should be stashed/committed first)
- **`git checkout -b` from main with clean tree:** no condition fires → ALLOW (intended pattern)
- **`git checkout -b` from feat/foo where feat/foo HAS an open PR:** condition (b) does not fire → ALLOW (work is in flight, branching off is fine)
- **`git checkout -b` from feat/foo where PR was just merged:** branch is "merged" but local tip may have additional unmerged work → still DENY via condition (b) (Marcus must verify nothing is left)
- **`git checkout -b` while a rebase is in progress** (`.git/rebase-merge/` or `.git/rebase-apply/`): bypass branch checks (per §7.1 of brainstorm); rebase replays may temporarily produce ambiguous states
- **`git checkout -b` while in detached HEAD:** treated as condition (b) since no current-branch ref to evaluate; allow with warning, recommend creating from `origin/<default>` explicitly

### Feature: M12 — Override discipline (single-shot + audit)

**Description:** Every safety override (granular env-vars `CLAUDE_ALLOW_<RULE>=1` and master `CLAUDE_ALLOW_GIT_BAD_OPS=1`) is single-shot: consumed on first matching hook invocation, requires re-set per attempt. Every consumption appends an audit JSONL line. Marcus reviews via `/tcs-git-helpers:status --overrides`.

**User Flow:**
1. Claude or Marcus encounters a denial; the denial message names the specific override env-var
2. Override env-var is set (e.g., `CLAUDE_ALLOW_RESET_HARD=1 git reset --hard origin/main`)
3. Hook detects env-var, allows operation
4. Hook unsets env-var (within hook process scope), writes sentinel to `${CLAUDE_PLUGIN_DATA}/cache/override-consumed-<env-var>` with 5-second window
5. Hook appends JSONL line to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl`
6. Hook emits stderr "override consumed: CLAUDE_ALLOW_RESET_HARD"
7. Subsequent matching operation re-denies unless override is re-set; sentinel prevents double-tap within 5s

**Business Rules:**
- Rule 1: All overrides are single-shot. No "session-mode" or "permanent allow" exists in v1.0
- Rule 2: Master override `CLAUDE_ALLOW_GIT_BAD_OPS=1` is also single-shot AND emits a loud stderr warning recommending granular alternatives
- Rule 3: Audit JSONL line includes `master:true` flag for master-override events to enable separate counting
- Rule 4: Audit file rotates at 1MB to `.1`/`.2`; older rotations are NOT auto-deleted (Marcus may archive/delete manually)
- Rule 5: Audit-write failure (disk full, permission) NEVER blocks the underlying hook decision (US-OV.2 AC4); failure is logged to stderr
- Rule 6: Override consumption is recorded even when the underlying operation subsequently fails (e.g., the `git push` itself errors after the hook allows); the audit reflects intent, not outcome

**Edge Cases:**
- **Override env-var set but operation doesn't match the rule:** hook detects the set env-var but does not match the rule → emits stderr warning ("⚠ env var set but no matching rule fired") and leaves env-var alone
- **Two granular overrides set simultaneously:** each consumed independently per-rule
- **Master + granular both set:** granular wins (more specific); master not consumed; audit reflects granular
- **5-second sentinel window expires mid-script:** rare; second consumption proceeds and is logged as separate event
- **Audit file is on a network filesystem and is slow:** hook writes asynchronously where possible; if write hangs, falls through after timeout (logged)
- **`/tcs-git-helpers:status --overrides` invoked when audit file missing:** prints "no overrides recorded yet" and exits 0
- **Marcus manually edits audit file:** outside scope; integrity not enforced (v1.0 trust model: Marcus is trusted operator)

## Success Metrics

### Key Performance Indicators

**Adoption:**
- All 7 MiYo repos plus TCS itself have the plugin enabled and `.githooks/` installed within 2 weeks of v1.0 release (target: 8/8 = 100%)
- Time from `/tcs-git-helpers:setup` invocation to first hook fire in a repo: <60 seconds (target p99)

**Engagement:**
- Hook firing recorded daily in audit log; Marcus checks `/tcs-git-helpers:status` weekly (target: ≥4 weekly checks/month)
- Override usage: <5% of hook fires use any `CLAUDE_ALLOW_*` env-var (excluding documented legitimate flows)
- Master-override (`CLAUDE_ALLOW_GIT_BAD_OPS`) usage: <10% of all override events (granular preferred)

**Quality:**
- Zero closed-PR pollution incidents (push to merged/closed PR succeeded) for 30 days post-rollout
- Zero squash-merge-reuse incidents (`mergeable: CONFLICTING` PR caused by branch reuse) for 30 days
- Zero worktree-exit data-loss incidents for 30 days
- Hook false-positive rate: <2% of hook fires are spurious denials per Marcus's review (target via audit + manual labeling)
- SessionStart hook p99 latency ≤300ms (per §6.2.3 of brainstorm)

**Business Impact (Marcus's recovery time):**
- Recovery time spent on git mistakes drops from estimated ~30min/week to ~5min/week within 30 days of full rollout (target: -83%)

### Tracking Requirements

| Event | Properties | Purpose |
|---|---|---|
| `hook_fired` | timestamp, repo, branch, hook_name, decision (allow/deny/warn), pattern_matched, latency_ms | Measure hook coverage and performance per goal |
| `override_consumed` | timestamp, repo, branch, hook_name, env_var, master (bool), command (truncated), pattern_matched | M12 audit trail; KPI source for override usage |
| `setup_run` | timestamp, repo, mode (default/--update/--with-branch-protection/--with-gha), conflicts_detected[], action_taken | Adoption tracking; conflict-detection accuracy |
| `cache_state` | timestamp, repo, cache_age_hours, branch_count_total, stale_merged_count | Cache-freshness telemetry; SessionStart-readiness |
| `recovery_event` | timestamp, repo, recovery_type (cherry-pick/rebase/reflog/manual), incident_pattern (M1/M2/M3/...) | Manual log by Marcus to validate "recovery time" KPI |
| `gh_call` | timestamp, hook_name, gh_command, exit_code, latency_ms, fail_open (bool) | Performance + rate-limit budget tracking |

Storage: JSONL files under `${CLAUDE_PLUGIN_DATA}/audit/` and `${CLAUDE_PLUGIN_DATA}/perf.log` (latter Should-Have, deferred). v1.0 is local-only — no remote telemetry.

---

## Constraints and Assumptions

### Constraints

- **macOS-first deployment** — Marcus's primary platform; bash 3.2.57 is the macOS default `/bin/bash`. All hook scripts MUST be bash 3.2 compatible (no `${var,,}`, no `mapfile`/`readarray`, no associative arrays `declare -A`)
- **SessionStart hook hard limit: 300ms p99** — exceeding this degrades Claude Code session boot perceptibly
- **`gh` calls fail-open** — hooks NEVER block the user on `gh` network or rate-limit failures; degraded mode allows operation with stderr warning
- **No Boucle source vendoring** — `git-safe`, `branch-guard`, `worktree-guard` patterns are absorbed via re-implementation (license + integration with TCS conventions)
- **Plugin lifecycle = trust signal** — disabling the plugin is interpreted as "user consciously waiving Claude-side protection." `.githooks/` defense-in-depth keeps repo-side protection active
- **Compliance:** none (Marcus is single trusted operator; no organizational compliance requirements in v1.0)
- **No `.git/config` writes from hooks** — sandbox blocks them; warnings are filtered as harmless via `git_safe()` helper

### Assumptions

- **Marcus's `gh` token has `repo` scope** — verified today; sufficient for branch-protection PUT and `delete_branch_on_merge` PATCH
- **Repos use GitHub** — `gh`-dependent features (M1 PR-state check, S1 branch-protection) require GitHub remote; non-GitHub repos use degraded mode
- **No `coreutils timeout` dependency** — `.githooks/pre-push` and any timeout-needing site uses pure-bash `(cmd) & sleep 5; kill $!` pattern unconditionally (no version-detection branch). Locked per OQ1.
- **Claude Code hook events are stable** — `PreToolUse:Bash`, `PreToolUse:Edit|Write|NotebookEdit`, `PreToolUse:ExitWorktree`, `SessionStart`, `PostToolUse:Bash` are documented and supported in current Claude Code versions
- **`${CLAUDE_PLUGIN_DATA}` survives plugin updates** — per Claude Code docs (cache file persistence)
- **Marcus uses the plugin's setup skill at least once per repo** — no auto-install on plugin enable; explicit setup required

## Cross-Repo Rollout

The plugin will be deployed to Marcus's repos in five waves. Waves 1-3 are required for v1.0; waves 4-5 are post-launch:

| Wave | Scope | Activities |
|---|---|---|
| **1** | TCS itself (this repo) | Build plugin, dogfood validation, all phase-6 E2E tests pass against TCS |
| **2** | Kado (real migration test) | Plugin overlays existing `.githooks/`; auto-detect `_outbox/` exception → `.githooks/exclude-paths`; verify Kado's CI green; clean up the 6 known stale-merged branches |
| **3** | Hakobi, Tomo, Kokoro, Kouzou, Seigyo, Hashi | Fresh installs (less overlap risk than Kado); each repo confirmed protected via `/tcs-git-helpers:status` |
| **4** (optional) | Repos opting into GitHub Actions PR-title check | `setup --with-gha` per repo |
| **5** (optional) | Repos opting into branch protection | `setup --with-branch-protection` per repo |

**Adoption KPI:** all 8 repos (TCS + 7 MiYo) have plugin enabled and `.githooks/` installed within 2 weeks of v1.0 release. Tracked manually by Marcus.

User-global `~/.claude/hooks/block-main-edits.sh` is **NOT** retired during rollout — it remains as universal baseline that fires regardless of plugin state, providing belt-and-suspenders protection against main edits even in repos without the plugin enabled.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Hook bug → false denials disrupt flow | High | Medium | Granular per-violation overrides; audit log surfaces patterns; bats-core perf+regression test suite in PLAN |
| Hook bug → false allows lose protection | High | Low | Defense-in-depth `.githooks/` catches git-side; user-global `block-main-edits.sh` baseline |
| SessionStart performance regression beyond 300ms | Medium | Medium | CI perf test (Performance §1 baseline 58ms gives 5× headroom); cache-only no-`gh` mandate |
| Plugin disabled, repo unprotected | Medium | Low | `.githooks/` committed in repo continues to fire; user-global hook protects main edits |
| `gh` rate-limit shared with Marcus's manual usage | Medium | Low | Caching (60s push-state, 5min PR-history); batched `post-merge` query; fail-open on rate-limit |
| Hooks bypassed via shell alias / function | Medium | Medium | `.githooks/` git-side catches what Bash hook misses; documented limitation in `references/destructive-ops.md` |
| `.config` parser injection vulnerability | Low | Low | Strict allowlist + `printf -v` (no eval/source); test corpus of injection attempts; security-researcher review |
| Audit log fills disk | Low | Low | 1MB rotation to `.1`/`.2`; failure does not block hooks |
| Husky/lefthook conflict mishandled by setup | Medium | Medium | Setup detects 5+ tools and aborts with migration doc; `references/migrating-from-husky.md` |
| `WorktreeRemove` event semantics differ from expected | Medium | Low | Resolved: use `PreToolUse:ExitWorktree` (blockable, Boucle-validated) per integration research C1 |
| `mergeMethod` API field unavailable | Medium | Confirmed | Resolved: use parent-count check via `git rev-list --parents` per integration research C2 |
| `coreutils timeout` missing on macOS | n/a | n/a | Resolved: pure-bash `(cmd) & sleep 5; kill $!` used unconditionally (OQ1) — no dependency, no risk |

## Open Questions

All critical and important questions have been resolved in this review (2026-05-09). Remaining items deferred to SDD/PLAN.

### Resolved (Marcus reviewed 2026-05-09)

- [x] **OQ1 — `timeout(1)` strategy:** **DECIDED → bash-only fallback.** No `coreutils` prerequisite. `.githooks/pre-push` and any other timeout-needing site uses `(cmd) & sleep 5; kill $!` pattern. Zero-install UX.
- [x] **OQ2 — Branch-protection preset for `--with-branch-protection`:** **DECIDED → single-coder preset (no review requirement).** Marcus is sole contributor across MiYo repos; review-required would block all PRs. Preset rules: `no-force-push` + `no-deletions` + `require-up-to-date-before-merge` + (optional) `require-status-checks-to-pass`. Excluded: `required-pull-request-reviews`, `dismiss-stale-reviews`. Reflected in S1 acceptance criteria below.
- [x] **OQ3 — `references/` install location:** **DECIDED → plugin-internal only.** Single source of truth; updates ride with plugin updates; drift avoided.
- [x] **OQ4 — Brief cadence:** **DECIDED → SessionStart + after post-merge.** Both triggers; cache is already updated by `post-merge` so re-emit is cheap. Reflected in M4 acceptance criteria below.
- [x] **OQ5 — P3 (Future TCS Adopter) v1.0 acceptance gate:** **DECIDED → soft gate.** v1.0 = "shouldn't break for P3"; first-class onboarding deferred to v1.1+. TCS is a custom marketplace, so adopters explicitly come to the repo.

### Deferred (resolved in SDD or PLAN)

- [ ] **OQ6 — Husky/lefthook policy:** Abort + documented migration confirmed (per integration research §5).
- [ ] **OQ7 — Multi-account `gh` host detection:** v1.1 candidate.
- [ ] **OQ8 — Telemetry:** v1.0 is local-only; perf.log is Should-Have (deferred).
- [ ] **OQ9 — PostToolUse nudge dedup window:** Recommend 60s same-nudge dedup; confirm in SDD.
- [ ] **OQ10 — `PostToolUse:Bash` JSON exit-status presence:** Runtime probe in PLAN.
- [ ] **OQ11 — PR/branch rename timing:** Defer to implementation; current branch `feat/tcs-git-safety` will rename to `feat/tcs-git-helpers` before merge.
- [ ] **OQ12 — `if` permission-rule filters in `hooks.json`:** SDD-phase exploration; potentially simplifies dispatch.

---

## Supporting Research

### Competitive Analysis

**Boucle-framework** (`github.com/Bande-a-Bonnot/Boucle-framework`) — closest prior art. Three separate tools:
- `git-safe` — destructive-ops prevention; pattern set absorbed into M7
- `branch-guard` — protected-branches enforcement; configurability absorbed into M11 / `.config`
- `worktree-guard` — exit-time data-loss prevention; absorbed into M8 with `git cherry` for squash-merge detection

**Differences vs. tcs-git-helpers:**
- Boucle is three independent tools; we ship as one coherent plugin
- Boucle uses exit code 2; we use modern `permissionDecision: deny` JSON with structured reasons + reference links
- Boucle uses `GIT_SAFE_DISABLED`-style binary disables; we use granular per-violation single-shot overrides + audit
- Boucle is single-purpose; we add nudges, references, optional GHA + branch protection, worktree-aware status skill

**Husky / lefthook / pre-commit framework** — adjacent ecosystem. v1.0 setup detects and aborts (via M10) rather than coexists; documented in `references/migrating-from-husky.md`.

**`commitlint`, `commitizen`** — adjacent commit-message tooling. Not absorbed; M5 reimplements minimal Conventional Commits validation in pure bash for the per-commit hot path (no Node.js dependency).

### User Research

- **Brainstorm session 2026-05-08** — full session captured at `docs/XDD/ideas/2026-05-08-tcs-git-safety.md`; iterative discovery with Marcus over multiple turns; gap-reviewed, spec-reviewer-approved
- **Live-incident observation** — Claude attempted to write spec from `main` during the brainstorm itself; Marcus had to manually intervene. Documented in `docs/XDD/ideas/...md` §1 "Live Incident Captured During Brainstorm"
- **Kado repo state inspection** — 6 stale local branches with merged PRs visible at brainstorm time; concrete evidence of the accumulation problem
- **Existing Marcus hooks** — `~/.claude/hooks/block-main-edits.sh`, `MiYo/Kado/.githooks/{pre-commit,commit-msg}` — partial baseline coverage; gaps motivate this plugin's expanded scope

### Market Data

Not applicable in v1.0 — internal TCS plugin, not a market-facing product. Future v1.1+ public-marketplace adoption: deferred; no market-sizing exercise undertaken.

Internal proxy metric: 7 MiYo repos × Marcus's recurring-incident estimate × time recovery ≈ 30min/week recovery cost. Plugin pays back in <2 weeks of operation if 80% of incidents are prevented.

---

*Generated 2026-05-08. PRD ready for SDD phase.*
