# Changelog

## [1.0.0] - 2026-05-09

### Added

- **Initial release of `tcs-git-helpers`** — Claude Code plugin that machine-enforces git workflow discipline across MiYo repos and TCS itself. Closes the recurring-mistake loop documented in PRD §Problem Statement (push-to-closed-PR, branch-from-unfinished, squash-merge-resume, destructive ops, worktree-exit data loss, bad commit messages, stale local branches).

  **PRD Goals shipped (M1–M12):**

  - **M1 — Block pushes to closed/merged PRs.** `PreToolUse:Bash` denies `git push` when the branch's PR is CLOSED or MERGED; cites `references/squash-merge-trap.md`. `gh` failures fail-open with stderr warning.
  - **M2 — Block branch creation from unfinished work.** Denies `git checkout -b` / `git switch -c` when the working tree is dirty OR the current branch has commits ahead of `origin/<default>` without a PR. Cascading-denial pattern reports both conditions when both fire.
  - **M3 — Block resume of squash-merged branches.** Denies `git checkout <branch>` when `git cherry origin/<default> <branch>` returns all `-` lines (squash-merge fingerprint). Merge-commit merges (branch tip is ancestor of default) allowed.
  - **M4 — Pre-flight branch awareness brief.** `SessionStart` and `.githooks/post-merge` emit a one-line brief: branch (with protected marker), working-tree state, ahead/behind, stale-merged count. Cache-only, no `gh` calls, ≤300ms p99 (58ms baseline → 5× headroom).
  - **M5 — Conventional Commits enforcement.** `.githooks/commit-msg` rejects subjects not matching `<type>(<scope>)?!?: <subject>` with the allowlisted type set. Merge commits and `[skip-format-check]` exempt. Optional `TCS_REQUIRE_SCOPE=1` toggle.
  - **M6 — Stale local branch surfacing.** `.githooks/post-merge` lists local branches whose PRs have merged (non-blocking suggestion). `/tcs-git-helpers:status --cleanup` interactively deletes them; worktree-checked-out branches excluded.
  - **M7 — Block destructive git operations.** `PreToolUse:Bash` denies 14+ patterns: `git reset --hard`, `git clean -f/-fx`, `git branch -D`, `git stash drop`, `git stash clear`, `git reflog expire`, `git commit --no-verify`/`-n`, `git checkout .`/`-- <path>`, `git restore --worktree --source=…`, `git push --force` (without `--force-with-lease`), `git push --delete`, `git -c core.hooksPath …`, `git config core.hooksPath …`. Compound commands (`cd foo && git push --force`) detected via regex on full command string.
  - **M8 — Worktree exit data-loss guard.** `PreToolUse:ExitWorktree` runs the four-check (uncommitted/untracked/unmerged/unpushed) using `git cherry origin/<base> <branch>` to detect commits not yet on default. Granular override `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1`.
  - **M9 — Soft nudges after key git ops.** `PostToolUse:Bash` success-only nudges after `git checkout -b`/`switch -c`, `gh pr create`, first `git push -u`, `gh pr merge`, `git rebase`, `git stash pop`. 60s same-nudge dedup window. No nudge on non-zero exit.
  - **M10 — Plugin distribution and per-repo setup.** `/tcs-git-helpers:setup` writes `.githooks/` with version markers (`# tcs-git-helpers: vX.Y.Z`), sets `core.hooksPath`. Detects Husky/lefthook/pre-commit-framework/simple-git-hooks and aborts with migration reference. Lock-file serialized (5min stale reclaim). Does NOT auto-commit. Submodules listed but not recursed.
  - **M11 — Defense in depth — `.githooks/` works without plugin.** Each `.githooks/*` script produces the same exit code and stderr message as the plugin-side equivalent. User-global `~/.claude/hooks/block-main-edits.sh` continues to fire regardless of plugin state.
  - **M12 — Override discipline — single-shot + audit.** Every `CLAUDE_ALLOW_*` env-var is consumed on first matching hook fire (5-second sentinel prevents double-tap), audit-logged to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` with `{ts, repo, branch, hook, env_var, master, command, pattern}`. Audit file rotates at 1MB to `.1`/`.2`. Audit-write failures NEVER block hook decisions.

  **Should-Have features (opt-in):**

  - **S1 — Optional GitHub branch protection.** `setup --with-branch-protection` applies the single-coder preset (no force-push, no deletions, no review requirement) plus `delete_branch_on_merge=true`. Token-scope warnings for excessive scopes; `repo` scope required.
  - **S2 — Optional GHA PR-title check.** `setup --with-gha` copies `templates/github-actions/pr-title-check.yml` into `.github/workflows/` to validate PR titles on `pull_request` (relevant for squash-merge repos where PR title becomes the commit subject).

  **Distribution & rollout:**

  - Plugin layout per SDD §Building Block View: `hooks/` registration, `scripts/lib/*` shared helpers (git_state, config_parser, pattern_match, override, cache, audit_log), `scripts/*` six entry-point hooks, `templates/githooks/*` repo-installable scripts, `templates/github-actions/pr-title-check.yml`, `references/*` knowledge base, `skills/{setup,status}/SKILL.md`.
  - macOS-first: bash 3.2.57 compatible (no `${var,,}`, no `mapfile`, no `declare -A`, POSIX ERE only — `[[:space:]]+` not `\s+`, `[[:<:]]`/`[[:>:]]` not `\b`).
  - Zero-install: pure-bash `(cmd) & sleep 5; kill $!` timeout pattern (no `coreutils timeout` dependency).
  - Existing user-global `~/.claude/hooks/block-main-edits.sh` retained as universal baseline; not retired.
