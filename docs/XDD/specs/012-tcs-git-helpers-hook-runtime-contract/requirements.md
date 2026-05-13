---
title: "tcs-git-helpers hook runtime contract & plugin-update propagation"
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

- [x] Problem is validated by evidence (not assumptions) — empirical 3-context env probe completed this session, see Supporting Research
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

A user who installs `tcs-git-helpers` once never has to think about it again — the plugin's git hooks continue to do what they promise, across plugin updates, without silent failure modes that erode trust in the tool.

### Problem Statement

The `tcs-git-helpers` plugin templates `.githooks/post-merge` (and three other hooks) into user repositories. Those installed hooks **depend on environment variables (`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`) that are set by the Claude Code harness when *it* spawns plugin code, but are *not* propagated to processes spawned by `git`**. As a result:

- The `post-merge` hook silently exits before writing the stale-branch cache on every real `git merge` — verified empirically: `~/.claude/plugins/data/tcs-git-helpers-*/cache/` contains many files written by harness-spawned plugin hooks (e.g. `*-pr-state.json` from `nudge-hook.sh`), but **zero** `*-stale-cache.{tsv,json}` files from the only path that writes them (the git-spawned `post-merge`).
- Downstream: `/tcs-git-helpers:git-audit --cleanup` reports "No stale-merged branches to clean up" even when `git branch --merged main` shows several. Users lose confidence in the audit tool and accumulate dead branches.
- A separate but related fragility: even if the env-var contract were fixed, **plugin-version updates do not propagate to installed hooks**. The hook is templated once at `/tcs-git-helpers:git-setup` time with no re-install on plugin update; bug fixes in `lib/cache.sh` go un-deployed until each user manually re-runs git-setup in every repo.

Both failure modes are **invisible** — they don't error, they just produce wrong answers. Users have no way to discover the tool isn't doing its job unless they cross-check with raw `git` commands.

### Value Proposition

Users get a tool whose results match reality. The stale-branch cleanup feature actually works. Plugin updates propagate safely. When something *does* go wrong (missing dependency, permission error), the user sees a clear stderr message instead of silent no-op.

For maintainers: one consistent runtime contract across all installed hooks (`post-merge`, `pre-commit`, `commit-msg`, `pre-push`) eliminates a class of "works on harness, fails on git" bugs.

## User Personas

### Primary Persona: TCS plugin user (per-repo developer)

- **Demographics:** Software developer working in a TCS-managed repository on macOS. Comfortable with git CLI but expects plugin tooling to "just work" without env-var debugging. Installs `tcs-git-helpers` once via `/tcs-git-helpers:git-setup`, then forgets about it.
- **Goals:**
  - Run `/tcs-git-helpers:git-audit --cleanup` and trust the answer.
  - Merge feature branches and have stale ones surface for cleanup automatically.
  - Update the plugin (1.x → 2.x) without having to re-run setup in every repo.
- **Pain Points:**
  - Currently the cleanup command silently lies about state (says "none" when there are stale branches).
  - No visible signal when the post-merge cache write fails.
  - Re-running git-setup across multiple repos after every plugin update is unrealistic for users with many repos.

### Secondary Persona: tcs-git-helpers maintainer

- **Demographics:** Plugin author. Writes templates, lib code, install logic. Cares about whether a fix shipped in v2.0.2 actually reaches users.
- **Goals:** Ship `lib/cache.sh` fixes and have them apply to every repo that has the plugin installed, with predictable lag (or none).
- **Pain Points:** Today, a hook bug fix in the plugin can be in the cache for weeks before any user sees the new behavior, because the installed hook is frozen and the user has no signal to re-install.

## User Journey Maps

### Primary User Journey: Run `--cleanup` after merging several PRs

1. **Awareness:** User merges PRs #10–#18 over the course of a sprint. Their local branches accumulate.
2. **Consideration:** They notice `git branch` is getting long. The plugin's SessionStart brief mentions "N stale-merged" → confirms the tool is tracking this.
3. **Adoption:** They invoke `/tcs-git-helpers:git-audit --cleanup` trusting the brief's count.
4. **Usage:** The command lists the stale branches. The user types `y` for each they want gone.
5. **Retention:** The numbers match what they see in `git branch --merged main`. They keep using the tool.

**Today's broken version of step 4:** cleanup says "No stale-merged branches to clean up" even when there are several. User stops trusting the brief.

### Secondary User Journey: Plugin update from 2.0.1 → 2.0.2

1. **Awareness:** User pulls the latest TCS marketplace; sees `tcs-git-helpers 2.0.2` available.
2. **Consideration:** Reads the changelog; sees a bug fix to the stale-cache write path.
3. **Adoption:** Plugin auto-installs (cache dir refreshes).
4. **Usage:** Next merge fires. Either (a) the new fix is in effect, OR (b) the user receives a visible prompt to re-run setup. *Not* silent staleness.
5. **Retention:** No mystery about "why didn't the fix help me."

## Feature Requirements

### Must Have Features

#### Feature 1: post-merge hook reliably writes the stale-branch cache after every merge

- **User Story:** As a per-repo developer, I want the post-merge hook to update the stale-branch cache on every merge, so that subsequent `--cleanup` runs reflect reality.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a repo with `tcs-git-helpers` installed via git-setup and a local branch B whose PR is merged on GitHub, When `git merge` completes (any kind: feature into main, fast-forward, or no-ff merge commit), Then the stale-branch cache files (`<repo-hash>-stale-cache.tsv` and `<repo-hash>-stale-cache.json`) exist on disk within the same `git merge` invocation.
  - [ ] Given the merge described above, When the cache files are inspected, Then the entry for branch B is present with the correct `pr_number` and `merged_at` fields.
  - [ ] Given the harness env vars `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` are both unset in the calling shell (the real production condition for git hooks), When `git merge` runs the post-merge hook, Then the cache write still succeeds.
  - [ ] Given the hook write succeeds, When `gh` CLI is not authenticated, Then the hook degrades gracefully with a stderr explanation rather than writing a corrupt cache.

#### Feature 2: `git-audit --cleanup` reports state that matches `git`

- **User Story:** As a per-repo developer, I want `--cleanup` to reflect the same merged-branch reality `git` itself reports, so that I can trust the tool as my source of truth.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given local branches X and Y are listed by `git branch --merged main` and have closed-merged PRs on GitHub, When `/tcs-git-helpers:git-audit --cleanup` runs, Then both X and Y appear in the cleanup candidate list.
  - [ ] Given the cache is stale (older than 24h) or empty, When `--cleanup` runs, Then the command refreshes the cache against live `gh` state before reporting candidates (it does not trust an empty/stale cache).
  - [ ] Given `gh` is unavailable or unauthenticated, When `--cleanup` runs, Then the command reports the degraded state and falls back to whatever cache content exists (rather than reporting "none" misleadingly).

#### Feature 3: plugin-version updates propagate safely

- **User Story:** As a per-repo developer, I want plugin updates to take effect in my installed hooks without requiring me to manually re-run git-setup in every repo, OR I want to receive a clear prompt asking me to do so.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the plugin was at version V1 when `git-setup` was run in repo R, and the plugin updates to V2 in the cache, When the user starts a new Claude Code session that includes repo R, Then the user is given some visible mechanism (auto-refresh OR explicit prompt) such that the installed hook is no longer silently running V1 code while V2 is the active plugin version.
  - [ ] Given an installed hook references plugin code that has moved or been removed in the plugin cache (e.g., version dir deleted), When the hook runs, Then it does not silently produce wrong output — it either still functions correctly or emits a clear stderr error message naming the missing dependency.
  - [ ] Given the user re-runs `/tcs-git-helpers:git-setup` in a repo after a plugin update, When the install completes, Then the version banner in every installed hook matches the current `plugin.json` version.

#### Feature 4: skills that depend on hooks check hook version at invocation time

- **User Story:** As a per-repo developer, I want skills that consume hook-produced state to tell me when the installed hook is too old to satisfy what the skill is asking it to do, so that I never silently get wrong answers because of a stale hook install.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the post-merge hook is installed with version banner `hX` and the currently active plugin expects hook version `hY` where `Y > X`, When the user invokes any skill that reads hook-produced state (e.g. `/tcs-git-helpers:git-audit --cleanup`, `/tcs-git-helpers:git-audit --json`, the SessionStart brief that reads the stale cache), Then the skill emits an inline message naming the version drift and suggesting `/tcs-git-helpers:git-setup` to re-install — and does NOT continue producing potentially-incorrect output as if the hook were current.
  - [ ] Given a skill's drift check passes (banner equals expected hook version), When the skill runs, Then no drift-related output is produced — the check is silent on the happy path.
  - [ ] Given a skill does not depend on hook-produced state, When the user invokes it, Then the drift check is not performed (no noise, no latency for unrelated commands).
  - [ ] Given the post-merge hook is not installed at all (e.g. user never ran git-setup in this repo), When a hook-dependent skill is invoked, Then the skill emits a distinct "hook not installed" message (different from "hook version drift") naming `/tcs-git-helpers:git-setup` as the action to take.

#### Feature 5: silent failure modes eliminated

- **User Story:** As a per-repo developer, I want any condition that prevents a hook from working correctly to produce a visible signal, so that I can fix the cause instead of silently getting wrong results.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the post-merge hook hits any guard that prevents the cache write (missing dependency, permission error, unresolved data dir), When the hook completes, Then a single-line stderr warning explains *which* guard tripped and *what the user can do* — no silent `return 0`.
  - [ ] Given the post-merge hook would degrade gracefully (e.g., `gh` unauthenticated), When it completes, Then the existing graceful-degradation messages remain (so users distinguish "broken setup" from "expected degradation").
  - [ ] Given the hook completes successfully, When it completes, Then stdout remains empty (preserving the existing contract that stdout must not pollute git's merge output).

#### Feature 6: all installed hooks + lib are one versioned bundle

- **User Story:** As a maintainer, I want the runtime-contract fix and the versioning model applied uniformly across all four installed hooks (`post-merge`, `pre-commit`, `commit-msg`, `pre-push`) and any lib code they share, so that the entire installed code unit is treated atomically and we never ship a partially-updated installation.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given any of the four installed hooks runs during git operations, When it needs lib functionality or writes to the data dir, Then it resolves both successfully without depending on `CLAUDE_PLUGIN_*` env vars being set (same runtime-contract guarantee as Feature 1).
  - [ ] Given a single shared `HOOK_BUNDLE_VERSION` (or equivalent — SDD names it) exists in the plugin, When any installed hook is templated into a repo by git-setup, Then every installed hook in that repo carries the same version stamp.
  - [ ] Given the maintainer changes any installed-hook template or any shared lib code, When the PR ships, Then the `HOOK_BUNDLE_VERSION` is also bumped — enforced by a CI check that diffs the relevant paths against the version constant.
  - [ ] Given the `HOOK_BUNDLE_VERSION` in the plugin no longer matches the installed banner in the repo, When ANY hook-dependent skill runs (per Feature 4), Then the user is prompted to re-run `/tcs-git-helpers:git-setup` — re-installing all four hooks together, not selectively.
  - [ ] Given a regression test that asserts the runtime-contract behavior, When it is run against each of the four hooks in turn, Then all four pass.

### Should Have Features

*(Intentionally empty after PRD resolution. The fix is atomic — the four-hook unified treatment originally listed as Should Have was promoted to Must Have via Feature 6 when Q4 resolved to the "one versioned bundle" model. A partial fix would be incoherent under this design.)*

### Could Have Features

#### Feature 7: install-state inspection command

- **User Story:** As a per-repo developer, I want a way to ask the plugin "is your install in this repo healthy?" without merging anything, so that I can diagnose issues proactively.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a repo with hooks installed, When the user runs an install-inspection command (e.g., `/tcs-git-helpers:git-setup --check` or `/tcs-git-helpers:git-audit --install-state`), Then the output reports: which hooks are installed, their version banners, whether the cache write path can resolve, and whether they match the current plugin version.

#### Feature 8: telemetry of cache-write success

- **User Story:** As a maintainer, I want to know empirically (across the user base) whether the cache write path is succeeding, so that we catch regressions of this class of bug earlier.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a privacy-preserving telemetry mechanism exists in the plugin, When the post-merge hook completes, Then the success/failure outcome is recorded in a local rolling log that the maintainer can request when triaging.

### Won't Have (This Phase)

- A `current` version symlink in the plugin cache. Out of scope — that's a Claude Code harness concern, not something this plugin should patch around.
- Migration tooling for users on plugin versions older than the one that ships this fix. Users on truly old versions re-run `git-setup` once.
- Changes to the harness-side env-var contract (`CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA`). We accept the contract as-is and design around it.
- Fixing `nudge-hook.sh` or any other harness-spawned plugin hook — those already work; the bug is specifically in git-spawned hooks.
- Per-hook independent versioning. Decided in Q4: single shared `HOOK_BUNDLE_VERSION` covers all installed hooks + their lib as one atomic unit.
- Auto-updating the installed hooks behind the user's back. Decided in Q1/Q5: drift is surfaced via a prompt from any skill that depends on hook state, and the user runs `/tcs-git-helpers:git-setup` themselves.

## Detailed Feature Specifications

### Feature: post-merge hook reliably writes the stale-branch cache after every merge

**Description:** The `post-merge` git hook, templated into the user's repo at `.githooks/post-merge` by `/tcs-git-helpers:git-setup`, must complete its full job — including writing the `<repo-hash>-stale-cache.{tsv,json}` files to the data dir — every time `git merge` invokes it, in any shell environment where the harness env vars (`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`) are not set. This is the standard production condition; harness-set env vars only happen when the harness directly spawns the hook, which never happens for git-driven hooks.

**User Flow:**
1. User runs `git merge feature-branch` (or `git pull` triggering a merge)
2. Git completes the merge
3. Git invokes `.githooks/post-merge`
4. The hook computes its dependencies (cache lib path, data dir path) without relying on harness env vars
5. The hook queries `gh pr list --state merged --limit 100`, cross-references against local branches, writes the cache atomically, and emits the existing stderr suggestion line if any stale branches were found
6. Hook exits 0 regardless of write success, so the merge is never blocked

**Business Rules:**
- Rule 1: The hook MUST NOT block a merge. Exit 0 always, even on internal failure. (Preserves existing contract.)
- Rule 2: When `gh` is missing, the hook degrades gracefully (no error, no warning louder than a single stderr line). (Preserves existing contract.)
- Rule 3: When `gh` is present but unauthenticated, the hook emits the existing stderr "auth missing" message and exits 0. (Preserves existing contract.)
- Rule 4: When any condition prevents the cache write that would have otherwise occurred (e.g., disk full, unresolvable data dir), the hook emits a single-line stderr warning naming the cause. (Replaces silent `return 0`.)
- Rule 5: STDOUT remains empty in all paths. (Preserves existing contract.)

**Edge Cases:**
- Scenario 1: User has set `CLAUDE_PLUGIN_DATA` themselves in their shell rc. → Expected: hook respects the user's override (env var wins over derived default).
- Scenario 2: Two repos on the same machine share the same basename (e.g., both checkouts named `the-custom-startup`). → Expected: data dir path collision is *not regressed* relative to today — cache files within still use repo-path SHA hashes so they don't collide; document any new collision exposure if the chosen architecture introduces it.
- Scenario 3: Plugin cache dir for the previously-installed version has been deleted by the harness. → Expected: hook still produces correct results, OR emits a clear "missing dependency, re-run git-setup" stderr message — never silent.
- Scenario 4: User cloned a repo that already has `.githooks/post-merge` committed from a teammate using an older plugin version. → Expected: hook either functions correctly against the user's current plugin install, or emits a clear "version mismatch" stderr message on first run.

## Success Metrics

### Key Performance Indicators

- **Adoption:** N/A — this is a fix to existing functionality, not a new opt-in feature. Adoption is implicit (every user of the plugin gets the fix).
- **Engagement:**
  - **Cache-write success rate:** % of `post-merge` invocations that successfully write the cache, measured on the maintainer's own machine (and any opted-in telemetry). **Target: ≥ 99%** (only legitimate degradation modes — no `gh`, no auth — should miss).
  - **Cleanup correctness rate:** % of `--cleanup` invocations whose candidate list matches `git branch --merged main` ∩ closed-PR set. **Target: 100%** when `gh` is authenticated.
- **Quality:**
  - **Silent-failure rate:** number of `post-merge` invocations that fail to write the cache *without* producing a stderr signal. **Target: 0.** Today: effectively 100%.
  - **Cross-version regression rate:** % of `pre-commit`, `commit-msg`, `pre-push` hooks that pass the same runtime-contract regression test as `post-merge`. **Target: 100%.**
- **Business Impact:** maintainer trust in the tool (qualitative — measured by whether the maintainer stops cross-checking with raw `git` before using `--cleanup`).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `post_merge_invocation` | `outcome` (cache_written / gracefully_degraded / silent_failure / loud_failure), `degradation_reason` (none / no_gh / no_auth / no_jq / other), `duration_ms`, `stale_count` | Measure cache-write success rate; detect regressions of the silent-failure class. |
| `cleanup_invocation` | `candidate_count`, `cache_was_refreshed` (true if `refresh_stale_cache` was called during this invocation), `gh_authenticated` | Measure cleanup correctness rate; detect cases where stale cache misled the user. |
| `hook_version_drift_detected` | `skill_name` (which skill noticed), `installed_hook_version`, `expected_hook_version`, `user_action_after_prompt` (ran_setup / dismissed / other) | Measure how often skill-side drift checks fire and whether users act on the prompt. |

Tracking is local-only (rolling log in the data dir or stderr — no network). Maintainer can request the log file from a user when triaging a bug report.

---

## Constraints and Assumptions

### Constraints

- **Plugin packaging model is fixed.** Versions live in `~/.claude/plugins/cache/<source>/<plugin>/<version>/`. No `current` symlink. The Claude Code harness manages this layout; we don't get to change it.
- **Env-var contract is fixed.** `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` are set by the harness when it directly spawns plugin code; they are not propagated to `git`-spawned subprocesses. This is the documented harness behavior, not a bug we can fix upstream in scope.
- **Bash 3.2 compatibility required** (per existing `tcs-git-helpers` constraints in earlier SDD — macOS ships bash 3.2 in `/bin/bash`).
- **STDOUT contract preserved.** `git` interleaves hook stdout with its own output during merge; anything we write would pollute the user's terminal. Hooks must continue to use stderr only.
- **Hook must never block a merge.** Exit 0 always.
- **No network calls outside the existing `gh pr list` batched call.** Per `011-tcs-git-helpers` performance constraint.
- **Maintainer contract — single bundle version.** Any change to any installed-hook template OR to any lib code that the installed hooks depend on MUST be accompanied by a bump to the single `HOOK_BUNDLE_VERSION` (or equivalent — SDD names the artifact). This is enforced by a CI check, not honor-system.
- **Installed code references nothing in the plugin cache at runtime.** The four installed hooks plus their lib live entirely under `<repo>/.githooks/` (or `<repo>/.git/hooks/` — SDD decides). No `${CLAUDE_PLUGIN_ROOT}` lookups; no `source $HOME/.claude/plugins/cache/...`. The installation is self-contained per-repo.

### Assumptions

- The harness will continue to set `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` when it spawns plugin code directly (PostToolUse:Bash, SessionStart, etc.). We can rely on this for any solution component that runs in those contexts.
- Users have `gh` CLI installed and authenticated in the common case; the degraded-no-gh path is the rare case.
- Plugin updates from 2.0.x → 2.0.y will continue to keep the versioned cache dir structure. (If the harness ever introduces a `current` symlink, Option B/C become trivially easier — not blocking.)
- The user identifies repos by directory basename (collision risk for same-basename repos is pre-existing and not regressed by this fix).
- Repo top-level paths are stable during a session (no mid-session worktree moves that would change what `git rev-parse --show-toplevel` returns).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Chosen solution shape (A/B/C — to be decided in SDD) has a hidden regression we don't catch | High | Medium | Regression test asserting the env-var contract behavior — actually run a `git merge` in a throwaway test repo and verify cache files appear. Run on every PR. |
| Plugin update mid-session leaves the user with an inconsistent install state for a window of time | Medium | High | Whichever solution shape we pick must include a fail-loud path when the install state is detected as inconsistent. Silent staleness is the failure mode we are explicitly eliminating. |
| Solution adds runtime cost to every `git merge` (cache-refresh latency) | Medium | Low | The existing implementation already calls `gh pr list` once per merge (single batched call). Any new resolution work should reuse that envelope, not add another network round-trip. |
| Solution introduces a new persistent file (e.g., an `install-config` manifest) that users may accidentally commit or distribute | Low | Medium | Place any new persistent state under the harness's `~/.claude/plugins/data/` dir, not under the user's repo. Document the file shape and lifecycle. |
| Two repos with the same basename collide in the data dir | Low | Low (pre-existing) | Out of scope; document the limitation in the SDD if the chosen solution shape would amplify it. |
| Fix is shipped only for `post-merge`, the other three installed hooks ship the same latent bug | High | Medium | Resolved by Q4 — Feature 6 (now Must Have) makes the multi-hook scope explicit AND treats them as one versioned bundle. SDD must address all four hooks even if PLAN ships them as separate tasks. |
| Maintainer forgets to bump `HOOK_BUNDLE_VERSION` when changing an installed hook or shared lib | High | High (humans forget) | CI check that diffs the relevant paths against the version constant in every PR — fails the build on mismatch. Constraint codified in PRD; SDD specifies the lint rule. |
| User runs `git merge` *before* the next session (so the skill-side drift check never fires) and gets stale-cache results from an outdated hook | Medium | Medium | The first skill invocation after the merge surfaces the drift (Feature 4). Worst case: one stale-data answer between merge and first audit invocation. Document the latency in user-facing docs. |

## Open Questions

These decisions are explicitly deferred to the SDD phase, where the trade-offs can be evaluated against concrete implementation shapes (Options A–D and any others surfaced during architecture work).

- [x] **Q1 — Update model. RESOLVED 2026-05-13 (via Q5).** Fail-loud-prompt-reinstall, with the prompt produced by the skills that depend on the hook, at skill-invocation time. No auto-refresh of hook state. Auxiliary cache state (the stale-branch cache itself) is refreshed by the skill on each invocation when the hook version matches.
- [x] **Q2 — Hook independence vs current-plugin-code. RESOLVED 2026-05-13.** The installed hook(s) MUST NOT reference the plugin cache at runtime. Acceptable physical layouts (SDD picks): (a) hook fully inlined — single file in `.githooks/` or `.git/hooks/` containing everything it needs, or (b) hook + lib copied as siblings into `.githooks/` (or `.git/hooks/`) where the hook sources its sibling lib from a relative path. Either way: the hook is self-contained per-repo; nothing it loads at runtime lives in `~/.claude/plugins/cache/...`.
- [x] **Q3 — Versioning granularity. RESOLVED 2026-05-13.** Option D from the README: independent hook-bundle version (NOT the plugin version), load-bearing. SDD chooses the exact representation (single `HOOK_BUNDLE_VERSION` constant in the install script, a `templates/githooks/VERSION` file, etc.), but the contract is: one version number identifies the installed-code unit, and skills read it from a known place in the installed hook(s) to drive drift detection per Feature 4.
- [x] **Q4 — Scope. RESOLVED 2026-05-13.** Broader pattern: the four installed hooks (`post-merge`, `pre-commit`, `commit-msg`, `pre-push`) plus any lib code they need are treated as **one versioned unit**. Any change to any installed-hook code OR any shared lib MUST bump the single shared hook-bundle version. One version mismatch → re-install all of it. No per-hook versions; no skip-some-hooks-on-update. The "broader pattern" framing also applies to any future hooks the plugin installs.
- [x] **Q5 — Drift-prompt placement and loudness. RESOLVED 2026-05-13.** The drift check fires at **skill invocation time**, not at SessionStart. Each skill that depends on hook-produced state (today: `git-audit` in all modes that read the stale-cache; potentially others) declares the hook version it requires, compares it to the installed banner, and on mismatch tells the user inline ("the post-merge hook in this repo is at vX; this command needs vY — run `/tcs-git-helpers:git-setup` to update"). Rationale: SessionStart noise is ignored; an in-context prompt at the moment the user actually depends on the hook is the only signal that lands. Skills that don't depend on hooks don't perform the check, so users who never touch hook-dependent tooling aren't bothered. This also fully resolves Q1 (the update model is fail-loud-prompt-reinstall, scoped to skill invocations).

---

## Supporting Research

### Competitive Analysis

Not applicable — this is an internal-tooling fix, not a market-facing feature.

For reference: other Claude Code plugins that install repo-side hooks (none in the TCS marketplace presently) would face the same constraint. The patterns chosen here should be reusable.

### User Research

**Empirical 3-context env-var probe** (conducted this session in `/Volumes/Moon/Coding/the-custom-startup/`):

| Context | How invoked | `CLAUDE_PLUGIN_ROOT` | `CLAUDE_PLUGIN_DATA` | Notes |
|---|---|---|---|---|
| A — Harness-spawned plugin hook | PostToolUse:Bash via `hooks.json` (`nudge-hook.sh`) | SET | SET | Proof: existing `~/.claude/plugins/data/tcs-git-helpers-the-custom-startup/cache/*.json` files written successfully by this path. |
| B — Git-spawned hook during real `git merge` | Hook in `.git/hooks/post-merge`, fired by `git merge --no-ff` in a throwaway repo | `<unset>` | `<unset>` | Plus `CLAUDE_CODE_SESSION_ID` and `CLAUDECODE=1` *do* propagate; just not the plugin-scoped vars. |
| C — Direct Bash tool invocation | `env \| grep CLAUDE_` | `<unset>` | `<unset>` | Same as a normal user terminal. |

**Cache-state inspection**: `find ~/.claude/plugins/data/tcs-git-helpers-* -name "*.json"` shows many `pr-state.json` and `nudge-verify-*` entries written by harness-spawned `nudge-hook.sh`, but **zero** `*-stale-cache.{tsv,json}` files — the only path that writes those is the git-spawned `post-merge` hook, which silently exits before reaching the write step in every production invocation.

**Downstream confirmation**: `/tcs-git-helpers:git-audit --cleanup` returned "No stale-merged branches to clean up" in the same session that `git branch --merged main` listed 6 merged-but-not-deleted local branches and `git branch -r --merged origin/main` listed 19 on remote. The cache-only data path produces wrong answers.

### Market Data

Not applicable.

### Codebase References

- `templates/githooks/post-merge:204-207` — silent `return 0` on missing `CLAUDE_PLUGIN_DATA`.
- `templates/githooks/post-merge:38-45` and `60-62` — silent skip of `lib/cache.sh` source when `CLAUDE_PLUGIN_ROOT` is unset.
- `scripts/git_status_audit.py:457-480` (`cmd_cleanup`) — reads cache only, never calls `refresh_stale_cache()` (defined in the same file at line 349, used only from tests).
- `scripts/nudge-hook.sh:110` — working defensive pattern `${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugin-data}/cache`, applied because nudge-hook runs in both harness and standalone contexts.
- `scripts/lib/cache.sh:24-26` (`_cache_dir`) — already has the env-var fallback pattern; the bug is that the *hook* never gets to call it because it never sources the lib.
- `skills/git-setup/lib/install_files.sh:81-97` — existing template-substitution paved path (`__TCS_GIT_HELPERS_VERSION__` → `vX.Y.Z`). Solution options can reuse this mechanism.
