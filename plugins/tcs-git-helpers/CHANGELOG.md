# Changelog

## [2.0.0] - 2026-05-11

### Changed (BREAKING)

- **Skill rename for namespace clarity.** Two of this plugin's skills shared bare names with another plugin or were too vague to disambiguate in the `/` menu. Renames:
  - `tcs-git-helpers:setup` → `tcs-git-helpers:git-setup` (collided with `tcs-helper:setup`; the domain prefix also signals what the skill does)
  - `tcs-git-helpers:status` → `tcs-git-helpers:git-audit` (the skill audits branch hygiene and override-consumption events, not just "status")

  Source directories renamed (`plugins/tcs-git-helpers/skills/{setup,status}/` → `{git-setup,git-audit}/`). Test files renamed accordingly (`skill_setup.bats` → `skill_git_setup.bats`, `skill_status.bats` → `skill_git_audit.bats`). All cross-references in scripts, hook templates, references, and audit-log nudges updated.

  **User-visible impact:** anyone who scripted invocations of `/tcs-git-helpers:setup` or `/tcs-git-helpers:status` must update to the new names. Tab-completion via the `/` menu picks up the new names automatically on next plugin refresh.

### Changed

- **Hook version markers now track `plugin.json` automatically.** Previously, installed hooks were stamped with a hardcoded `# tcs-git-helpers: v1.0.0` banner that didn't change when the plugin minor/major-bumped. Users seeing `v1.0.0` after pulling v2.0.0 reasonably suspected the update didn't take. Fixed:

  - Templates (`templates/githooks/{pre-commit,pre-push,commit-msg,post-merge,.config.example,exclude-paths.example}` and `templates/github-actions/pr-title-check.yml`) now contain a `__TCS_GIT_HELPERS_VERSION__` placeholder instead of a literal version.
  - `install_files.sh` and `with_gha.sh` read the version from `.claude-plugin/plugin.json` at install time and substitute the placeholder via `sed`, so installed files always carry a marker matching the installed plugin.
  - `detect_conflicts.sh` reads the same source for `WANT_VERSION`, so the OK / OUTDATED / CONFLICT decision tracks `plugin.json` automatically — no more manual sync at release time.
  - The integration verifier and dogfood scripts switched their hardcoded `v1.0.0` checks to a `v[0-9]+\.[0-9]+\.[0-9]+` semver pattern.
  - The `with-tcs-current` test fixture builds with the live `plugin.json` version (not a stale literal), so the "matching version → OK" path stays correctly exercised across future bumps.

  **Effect for users:** after a plugin upgrade, running `/tcs-git-helpers:git-setup` (with `--update` or `--with-gha` as needed) restamps the installed `.githooks/*` with the new version. The conflict detector reports `OK` once markers match, `OUTDATED` while they don't.

## [1.0.0] - 2026-05-09

### Added

- **Initial release of `tcs-git-helpers`** — Claude Code plugin that machine-enforces git workflow discipline across MiYo repos and TCS itself. Closes the recurring-mistake loop documented in PRD §Problem Statement (push-to-closed-PR, branch-from-unfinished, squash-merge-resume, destructive ops, worktree-exit data loss, bad commit messages, stale local branches).

  **PRD Goals shipped (M1–M12):**

  - **M1 — Block pushes to closed/merged PRs.** `PreToolUse:Bash` denies `git push` when the branch's PR is CLOSED or MERGED; cites `references/squash-merge-trap.md`. `gh` failures fail-open with stderr warning.
  - **M2 — Block branch creation from unfinished work.** Denies `git checkout -b` / `git switch -c` when the working tree is dirty OR the current branch has commits ahead of `origin/<default>` without a PR. Cascading-denial pattern reports both conditions when both fire.
  - **M3 — Block resume of squash-merged branches.** Denies `git checkout <branch>` when `git cherry origin/<default> <branch>` returns all `-` lines (squash-merge fingerprint). Merge-commit merges (branch tip is ancestor of default) allowed.
  - **M4 — Pre-flight branch awareness brief.** `SessionStart` and `.githooks/post-merge` emit a one-line brief: branch (with protected marker), working-tree state, ahead/behind, stale-merged count. Cache-only, no `gh` calls, ≤300ms p99 (58ms baseline → 5× headroom).
  - **M5 — Conventional Commits enforcement.** `.githooks/commit-msg` rejects subjects not matching `<type>(<scope>)?!?: <subject>` with the allowlisted type set. Merge commits and `[skip-format-check]` exempt. Optional `TCS_REQUIRE_SCOPE=1` toggle.
  - **M6 — Stale local branch surfacing.** `.githooks/post-merge` lists local branches whose PRs have merged (non-blocking suggestion). `/tcs-git-helpers:git-audit --cleanup` interactively deletes them; worktree-checked-out branches excluded.
  - **M7 — Block destructive git operations.** `PreToolUse:Bash` denies 14+ patterns: `git reset --hard`, `git clean -f/-fx`, `git branch -D`, `git stash drop`, `git stash clear`, `git reflog expire`, `git commit --no-verify`/`-n`, `git checkout .`/`-- <path>`, `git restore --worktree --source=…`, `git push --force` (without `--force-with-lease`), `git push --delete`, `git -c core.hooksPath …`, `git config core.hooksPath …`. Compound commands (`cd foo && git push --force`) detected via regex on full command string.
  - **M8 — Worktree exit data-loss guard.** `PreToolUse:ExitWorktree` runs the four-check (uncommitted/untracked/unmerged/unpushed) using `git cherry origin/<base> <branch>` to detect commits not yet on default. Granular override `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1`.
  - **M9 — Soft nudges after key git ops.** `PostToolUse:Bash` success-only nudges after `git checkout -b`/`switch -c`, `gh pr create`, first `git push -u`, `gh pr merge`, `git rebase`, `git stash pop`. 60s same-nudge dedup window. No nudge on non-zero exit.
  - **M10 — Plugin distribution and per-repo setup.** `/tcs-git-helpers:git-setup` writes `.githooks/` with version markers (`# tcs-git-helpers: vX.Y.Z`), sets `core.hooksPath`. Detects Husky/lefthook/pre-commit-framework/simple-git-hooks and aborts with migration reference. Lock-file serialized (5min stale reclaim). Does NOT auto-commit. Submodules listed but not recursed.
  - **M11 — Defense in depth — `.githooks/` works without plugin.** Each `.githooks/*` script produces the same exit code and stderr message as the plugin-side equivalent. User-global `~/.claude/hooks/block-main-edits.sh` continues to fire regardless of plugin state.
  - **M12 — Override discipline — single-shot + audit.** Every `CLAUDE_ALLOW_*` env-var is consumed on first matching hook fire (5-second sentinel prevents double-tap), audit-logged to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` with `{ts, repo, branch, hook, env_var, master, command, pattern}`. Audit file rotates at 1MB to `.1`/`.2`. Audit-write failures NEVER block hook decisions.

  **Should-Have features (opt-in):**

  - **S1 — Optional GitHub branch protection.** `setup --with-branch-protection` applies the single-coder preset (no force-push, no deletions, no review requirement) plus `delete_branch_on_merge=true`. Token-scope warnings for excessive scopes; `repo` scope required.
  - **S2 — Optional GHA PR-title check.** `setup --with-gha` copies `templates/github-actions/pr-title-check.yml` into `.github/workflows/` to validate PR titles on `pull_request` (relevant for squash-merge repos where PR title becomes the commit subject).

  **Distribution & rollout:**

  - Plugin layout per SDD §Building Block View: `hooks/` registration, `scripts/lib/*` shared helpers (git_state, config_parser, pattern_match, override, cache, audit_log), `scripts/*` six entry-point hooks, `templates/githooks/*` repo-installable scripts, `templates/github-actions/pr-title-check.yml`, `references/*` knowledge base (14 docs), `skills/{setup,status}/SKILL.md`.
  - macOS-first (CON-1): bash 3.2.57 compatible (no `${var,,}`, no `mapfile`, no `declare -A`, POSIX ERE only — `[[:space:]]+` not `\s+`, `[[:<:]]`/`[[:>:]]` not `\b`).
  - Zero-install: pure-bash `(cmd) & sleep 5; kill $!` timeout pattern (no `coreutils timeout` dependency).
  - `gh` calls fail-open (CON-4): hooks never block on network or rate-limit failure; allow with stderr warning when state is indeterminate.
  - Existing user-global `~/.claude/hooks/block-main-edits.sh` retained as universal baseline; not retired.
  - 12 Architecture Decision Records (ADR-1 through ADR-12) resolved: hook type selection, bash/Python hot/cold split, config parser strategy, cache format, override single-shot sentinel, push-state cache, audit log rotation, test framework, squash-merge detection, setup-conflict abort, setup-active sentinel, and single-coder branch-protection preset.
