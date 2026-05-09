# Requirements Lens — `tcs-git-helpers` (PRD-Phase)

> Augments `docs/XDD/ideas/2026-05-08-tcs-git-safety.md`. Cites brainstorm sections rather than restating. Integrates security-researcher hint (override one-shot + audit log) as US-OV.1 / US-OV.2.

## 1. Personas

### P1 — **Claude (the Agent)** — primary protected entity
The actor whose forgetfulness causes the failure modes (§1). Operates inside the hook surface across many sessions in many repos. No persistent memory of prior incidents. **Cannot self-discipline reliably; must be machine-blocked.** Reads denial reasons + reference paths verbatim.

### P2 — **Marcus (the Operator)** — installer, override-holder, recoverer
Owns repos, installs the plugin, recovers from Claude's failures. Knows the rules (§4.1). Needs visibility (what's blocked, why) and clean override paths (§4.2) without losing the safety net entirely. Pays the cost of false-positive denials in disrupted flow.

### P3 — **Future TCS Adopter (Other Developer)** — v1.0 secondary, v1.x first-class
External marketplace consumer. Doesn't have Marcus's context; sees only README + denial messages + references. Acceptance: a developer with no prior TCS exposure can install, understand a denial, and override correctly.

---

## 2. User Stories by Goal

### G1 — Block pushes to closed/merged PRs
**US-G1.1** *As Claude, when I attempt `git push` on a branch whose PR is CLOSED or MERGED, I want the operation denied with a recovery path so I don't pollute the closed PR.*
- AC1 Push blocked with `permissionDecision: deny`.
- AC2 Denial includes branch, PR number+state, link to `references/squash-merge-trap.md`, override env-var name (§6.2.1).
- AC3 `gh` rate-limit / network failure / no-GitHub-remote → push allowed with stderr warning (fail-open, §7.2).
- AC4 `.githooks/pre-push` produces equivalent denial when plugin disabled (G11 defense in depth).

### G2 — Block branch creation from unfinished work
**US-G2.1** *As Claude, when I run `git checkout -b` while the current branch is **clean but unmerged/un-PR'd** (FM2), I want creation denied so I don't silently abandon prior work.*
- AC1 Hook denies if current branch has commits ahead of `origin/<default>` AND no PR exists.
- AC2 Hook denies if working tree is dirty (separate condition).
- AC3 Denial lists which condition tripped + remediation (open PR, merge, or stash/reset).
- AC4 `CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1` works for one-shot.

**US-G2.2** *As Marcus, when I'm intentionally parking work to start something urgent, I want a granular override that doesn't disable other safety hooks.*
- AC1 The override permits only G2; G1/G3/G7 still active.

### G3 — Block resume of squash-merged branches
**US-G3.1** *As Claude, when I `git checkout <branch>` whose PR was squash-merged, I want it denied so I don't hit `mergeable: CONFLICTING` (FM3).*
- AC1 Hook uses `git cherry` (§7.4), not `merge-base --is-ancestor`.
- AC2 Merge-commit-merged branches NOT flagged.
- AC3 Denial cites `references/squash-merge-trap.md` and recommends "fresh branch from default; cherry-pick if needed."

### G4 — Pre-flight branch awareness
**US-G4.1** *As Claude, at session start I want a one-line brief on branch state so I don't need to remember to run `git status` first.*
- AC1 `SessionStart` hook outputs single-line brief in <300ms (§6.2.3).
- AC2 Brief shows: branch (⚠ if protected), clean/dirty, ahead/behind, stale-merged count.
- AC3 No `gh` calls (cache only, §7.3).
- AC4 Renders even if cache stale; >24h flagged inline.

**US-G4.2** *As Marcus, when I open a session on a repo where the plugin is enabled but `.githooks/` not installed, I want a clear setup hint so I'm not confused.*
- AC1 Brief detects absence of `.githooks/` and surfaces "run /tcs-git-helpers:setup".

### G5 — Conventional Commits
**US-G5.1** *As Marcus, I want commits to fail unless they match Conventional Commits format so the squash-merge commit on default is well-formed.*
- AC1 `commit-msg` regex matches `<type>(<scope>)?!?: <subject>`.
- AC2 Type allowlist from `.githooks/.config`; `TCS_REQUIRE_SCOPE=1` makes scope mandatory.
- AC3 Merge commits and `Merge pull request …` excluded.
- AC4 Override is `[skip-format-check]` in subject — visible in `git log`, not silent.

### G6 — Stale local branches
**US-G6.1** *As Marcus, after `git pull` I want a non-blocking suggestion list of local branches whose PRs have merged so they don't accumulate (FM6).*
- AC1 `post-merge` outputs the list to stderr; doesn't block.
- AC2 `/tcs-git-helpers:status --cleanup` walks the list interactively.
- AC3 Branches checked out in worktrees excluded from cleanup proposals (§7.5).

### G7 — Block destructive ops
**US-G7.1** *As Claude, when I reflexively run `reset --hard`, `clean -f`, `branch -D`, `stash drop`, `reflog expire`, or `--no-verify`, I want denial with a recovery alternative.*
- AC1 Each pattern in §6.2.1 denies by default.
- AC2 Each has a granular env-var override; master `CLAUDE_ALLOW_GIT_BAD_OPS` exists but logs to stderr.
- AC3 Denial cites `references/destructive-ops.md` and offers safer alternative (e.g. `--force-with-lease` over `--force`).
- AC4 Compound commands (`cd foo && git push --force`) caught.

### G8 — Worktree exit guard
**US-G8.1** *As Marcus, when Claude exits a worktree session with uncommitted/untracked/unmerged/unpushed work, I want exit blocked with a clear summary so I don't silently lose work (§6.2.4).*
- AC1 Guard runs at `PreToolUse:ExitWorktree` (resolved per synthesis C1; was open in §6.2.4).
- AC2 Uses `git cherry` for unmerged detection.
- AC3 One-shot override `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1` must be re-set per attempt.

### G9 — Soft nudges
**US-G9.1** *As Claude, after a git op with a common follow-up step, I want a one-line reminder surfaced so I don't forget it (§6.6).*
- AC1 Each trigger in §6.6 emits via stderr; non-blocking.
- AC2 Nudge cites the relevant reference doc by path.
- AC3 Nudges fire only on **successful** Bash exit.

### G10 — Plugin distribution
**US-G10.1** *As Marcus, I want `/tcs-git-helpers:setup` to install hooks per-repo idempotently with conflict detection so re-running is safe (§6.5.1).*
- AC1 Detects existing `.githooks/`, `.husky/`, non-default `core.hooksPath` → prompts.
- AC2 Concurrent runs blocked via `.githooks/.setup.lock` (5-min stale reclaim).
- AC3 Does NOT auto-commit; emits next-step summary.
- AC4 Detects submodules and explicitly states they're not recursed (§7.6).

### G11 — Defense in depth
**US-G11.1** *As Marcus, when the plugin is disabled, I want `.githooks/` to still enforce the most important rules so non-Claude consumers (Docker, CI, my own terminal) remain protected.*
- AC1 `pre-commit`, `pre-push`, `commit-msg`, `post-merge` all functional without the plugin.
- AC2 `.githooks/` files contain `# tcs-git-helpers: vX.Y.Z` marker as line 1.
- AC3 With plugin disabled, user-global `block-main-edits.sh` continues to protect against main edits (§4.3 Phase 4).

### G12 — Optional GitHub branch protection
**US-G12.1** *As Marcus, when I run setup `--with-branch-protection`, I want the planned rules shown for confirmation before any `gh api` write so I don't surprise myself.*
- AC1 Setup prints planned ruleset; waits for confirmation.
- AC2 On confirmation, applies via `gh api`; reports each call's result.
- AC3 Failure (auth/permissions) does not roll back unrelated setup steps.

### OV — Override Discipline (cross-cutting; integrates security hint)
**US-OV.1** *As Marcus, every safety override must be **single-shot** — applies to exactly one tool invocation and clears itself — so a one-time emergency doesn't quietly persist into routine operation.*
- AC1 All `CLAUDE_ALLOW_*` env-vars (G1, G2, G3, G7, G8) are consumed by the hook on first match and the hook reports "override consumed" to stderr.
- AC2 Subsequent matching ops re-deny unless the override is re-set.
- AC3 Master `CLAUDE_ALLOW_GIT_BAD_OPS=1` is also single-shot (no master-bypass-mode).
- AC4 Override never persists across SessionStart (env-var lifecycle is session-only by construction; documented).

**US-OV.2** *As Marcus, every override use must leave an audit trail so I can review post-hoc whether Claude's bypasses were legitimate.*
- AC1 Each override consumption appends one JSONL line to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` with: timestamp, repo path, branch, hook name, env-var, command (truncated), match pattern.
- AC2 `/tcs-git-helpers:status --overrides` (new sub-mode) prints the last N override events for the current repo.
- AC3 Audit file is append-only from the hook's perspective; rotated by size (>1MB) into `.1`/`.2` siblings.
- AC4 Audit failure (e.g. disk full) does NOT block the underlying hook decision — log error to stderr, continue.

---

## 3. Edge-Case Requirements (User-Facing)

- **EC1 — Denial during long workflow.** Denial message must (a) name rule, (b) name override, (c) link reference, (d) be parseable in one read. Cap output ~15 lines.
- **EC2 — Cascading denials.** A single command tripping multiple rules must report **all** matched rules at once, not first-match-only — otherwise Claude solves one and re-trips immediately.
- **EC3 — Setup mid-conflict.** Interrupted `setup` (Ctrl-C, network drop) post-partial-copy must be safe to re-run and show what was already applied. Lock-file expiry covers concurrency; partial-state recovery is not yet specified — **needs requirement**.
- **EC4 — Plugin disabled mid-session.** Disabling the plugin live must not leave half-protected state or spurious denials referencing missing scripts.
- **EC5 — Hook script error vs. denial.** Distinct user signals required. Script crashes must NOT present as legitimate denials (would train Claude to override). Need explicit `[tcs-git-helpers ERROR]` prefix and fail-safe path.
- **EC6 — Override env-var leakage.** Env-vars must not leak across sessions/worktrees (subsumed by US-OV.1 single-shot).
- **EC7 — Reference doc not found.** Hook citing missing `references/foo.md` must still emit useful denial (graceful degradation). → `technical-researcher`
- **EC8 — Audit file unavailable.** Per US-OV.2 AC4, audit failure cannot block hook outcome. Document the precedence.

---

## 4. Persona Tensions

- **Claude convenience vs. Marcus safety.** Safety wins. The plugin is premised on "Claude forgets; rules must bite." Convenience is restored via *granular* one-shot overrides, not by softening defaults.
- **Marcus flow vs. Marcus safety.** False-positive denials disrupt mid-task. Mitigation: granular overrides preferred over master; master logs to stderr + audit (US-OV.2).
- **Plugin-lifecycle coupling.** §4.3 commits to "disable plugin = waive Claude-side protection." A less-attentive P3 might disable to silence a denial. Mitigation: `.githooks/` defense-in-depth (G11) plus user-global `block-main-edits.sh` (Phase 4).
- **Strict vs. degraded mode.** When `gh` is down/rate-limited, hooks fail-open (§7.2). Acceptance: stderr warning is loud enough that Claude/Marcus notices.
- **Audit visibility vs. noise.** Logging every override is loud but necessary; muting it would defeat the purpose. Surface via opt-in `--overrides` sub-mode rather than session-start brief.

---

## 5. Open Requirements Questions (need Marcus's call)

1. **Denial message length cap** — propose ~15 lines max (EC1). Confirm.
2. **Cascading denials (EC2)** — all-at-once vs. first-match-only? I propose all-at-once.
3. **Partial-setup recovery (EC3)** — stepwise state file, or "idempotent re-run from scratch"?
4. **Hook-error vs. hook-deny signal (EC5)** — confirm `[tcs-git-helpers ERROR]` prefix.
5. **Reference docs in target repo** — plugin-internal only, or also into `<repo>/.githooks/references/`?
6. **Brief cadence** — SessionStart only, or also re-render after `post-merge`?
7. **Persona priority for v1.0** — is P3 a v1.0 acceptance gate, or only "shouldn't break"?
8. **Audit retention** — JSONL with 1MB rotation, or other limit? Indefinite history acceptable on `${CLAUDE_PLUGIN_DATA}`?
9. **Override audit scope** — log only granular consumption, or also master `CLAUDE_ALLOW_GIT_BAD_OPS` activations distinctly?
10. **Single-shot mechanism** — env-var consumption requires hook to *unset* the var (impossible across processes) OR by design rely on Claude not re-setting it per call. Flagging for `technical-researcher` to specify the actual single-shot enforcement mechanism.
