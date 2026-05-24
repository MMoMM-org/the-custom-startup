# Changelog

## [2.2.2] - 2026-05-24

### Fixed

- **SessionStart brief now reaches the user.** Previously, the brief was emitted as plain text on stdout — for SessionStart hooks, Claude Code routes plain stdout into Claude's `additionalContext` only, so the user never saw it (including the `hooks vX → vY; run /tcs-git-helpers:git-setup --update` drift hint). The script now emits a JSON hook response:
  - `systemMessage` — user-visible TUI notice, populated **only when something is actionable** (drift, setup missing, or stale-merged > 0).
  - `hookSpecificOutput.additionalContext` — Claude-only context with the same actionable content, plus a protected-branch nudge on `main`/`master` so Claude knows not to create or edit non-gitignored files there.
  - When nothing is actionable, the script exits 0 silently — no stdout, no notice, no Claude context. Idle sessions stay quiet.

### Changed

- **Removed info-only segments from the brief.** The `clean / dirty (N modified)`, `N ahead / N behind / up to date / no upstream`, and `N stale-merged` / `(cache Nh old)` segments were rendered into a line that never reached the user and duplicated information Claude already has via `gitStatus`. Dropping them removes ~62ms of `git status` + `git rev-list` work per session start and shrinks the script.
- **Protected-branch ⚠ prefix removed in favour of an explicit Claude nudge.** The `⚠` was purely decorative and was never visible to the user (same channel issue as above). The hard guards (`block-bad-git-ops.sh` pre-commit/pre-push, the `block-main-edits.sh` PreToolUse hook downstream) already prevent risky operations on protected branches. The new `additionalContext` nudge replaces the silent decoration with an instruction Claude can act on.

### Fixed (test-side)

- **`tests/e2e/dogfood.sh` scenario 7** now asserts the brief tag on `HOOK_STDOUT` (where the brief has always been written) instead of `HOOK_STDERR`. The scenario was failing pre-change due to this assertion error.
- **`tests/e2e/dogfood.sh` scenario 9** now also copies `lib-bundle.sh` into the test repo's `.githooks/` alongside `post-merge`. Since v2.1.0 the post-merge hook sources its sibling `lib-bundle.sh` (the bundle is part of every real install), so the one-off fixture must mirror that layout — without the copy, the hook bails with `lib-bundle.sh missing in .githooks/`. The scenario was silently failing on every dogfood run since v2.1.0.

### Fixed (install_files banner)

- **Installed `.githooks/*` banners now carry the canonical `v` prefix.** The hook templates substituted `__TCS_GIT_HELPERS_VERSION__` with the bare semver (`2.2.2`), but every consumer in the project — `detect_conflicts.sh`, the C07 / C08 / C21 fixture and bats assertions, `tests/integration/verify-tcs-rollout.sh`, and the dogfood S1 banner check — expected `v2.2.2`. Concrete impact:
  - `detect_conflicts.sh` reported all post-v2.0.0 installs as "no marker found" (CONFLICT path) because its grep required `v`, so users running `/tcs-git-helpers:git-setup --update` saw the per-file-diff workflow instead of the cleaner OUTDATED path.
  - The C21 bats test had been failing on every run since v2.0.0.

  Fix: prepend `v` to the placeholder in all seven templates (`templates/githooks/{pre-commit,pre-push,commit-msg,post-merge,.config.example,exclude-paths.example}` plus `templates/github-actions/pr-title-check.yml`). New banners render as `# tcs-git-helpers: v2.2.2`.

- **`detect_conflicts.sh` now accepts both banner forms** (`v<semver>` and bare `<semver>`) for backwards compatibility with v2.0.0 – v2.2.1 installs. The OUTDATED path is reached cleanly for those legacy banners, and `--update` refreshes them to the canonical form. Comparison normalizes by stripping a single leading `v` from both sides.

## [2.1.0] - 2026-05-13

### Added

- **Self-contained hook bundle with independent versioning.** The installed `.githooks/` hooks now depend on zero environment variables and can be versioned independently of the plugin's semantic version, allowing users to stay on older plugin versions while receiving bug fixes to hooks. Implementation:

  - All hooks and their shared libraries are now copied into `.githooks/` at install time (no runtime references to `~/.claude/plugins/cache/...`).
  - Four installed files form an atomic bundle: `pre-commit`, `pre-push`, `commit-msg`, `post-merge`, plus two shared libs (`lib-bundle.sh`, `lib-config-parser.sh`).
  - Bundle versioning uses a new marker file `<repo>/.githooks/tcs-git-helpers-version` (e.g., `h1`), separate from the plugin's semantic version.
  - `/tcs-git-helpers:git-setup` installs the marker at bundle-version time; `--update` refreshes all four hooks and the marker together.
  - Drift detection (when installed bundle is older than skills expect) fires at skill-invocation time (`/tcs-git-helpers:git-audit --cleanup`, `--default`, `--json`), not SessionStart (CON-5 — keeps sessions silent).

- **Bug fix: `--cleanup` now refreshes stale-branch cache against live GitHub.** Previously, `cmd_cleanup` read a cached list that could be stale by hours. Now it calls `gh pr list` on every invocation (when possible) to surface recently-merged PRs before prompting for deletion. If `gh` fails or times out, the function falls back to the last-good cache gracefully.

### Changed

- **Maintainer contract: hook-bundle version bumps are CI-gated.** The CI check at `scripts/ci/check-hook-bundle-version.sh` now fails the build if any file under `templates/githooks/` or `templates/lib/` changes without a corresponding bump to `templates/githooks/tcs-git-helpers-version`. This ensures the bundle-version marker stays in sync with actual hook code, preventing drift between what users have installed and what the plugin expects.

## [2.0.1] - 2026-05-11

### Fixed

- **Hook version markers now track `plugin.json` automatically.** Previously, installed hooks were stamped with a hardcoded `# tcs-git-helpers: v1.0.0` banner that didn't change when the plugin minor/major-bumped. Users seeing `v1.0.0` after pulling v2.0.0 reasonably suspected the update didn't take. Fixed:

  - Templates (`templates/githooks/{pre-commit,pre-push,commit-msg,post-merge,.config.example,exclude-paths.example}` and `templates/github-actions/pr-title-check.yml`) now contain a `__TCS_GIT_HELPERS_VERSION__` placeholder instead of a literal version.
  - `install_files.sh` and `with_gha.sh` read the version from `.claude-plugin/plugin.json` at install time and substitute the placeholder via `sed`, so installed files always carry a marker matching the installed plugin.
  - `detect_conflicts.sh` reads the same source for `WANT_VERSION`, so the OK / OUTDATED / CONFLICT decision tracks `plugin.json` automatically — no more manual sync at release time.
  - The integration verifier and dogfood scripts switched their hardcoded `v1.0.0` checks to a `v[0-9]+\.[0-9]+\.[0-9]+` semver pattern.
  - The `with-tcs-current` test fixture builds with the live `plugin.json` version (not a stale literal), so the "matching version → OK" path stays correctly exercised across future bumps.
  - Detector's `OUTDATED` message no longer claims "older than" — markers can now legitimately be newer than expected too, so the wording is "does not match expected".
  - Dogfood `.githooks/*` markers in this repo bumped to `v2.0.1` to stay in sync with `plugin.json` (the one manual sync that remains — installed copies in user repos are substituted automatically on `--update`).

  **Effect for users:** after a plugin upgrade, running `/tcs-git-helpers:git-setup --update` restamps the installed `.githooks/*` with the new version. The conflict detector reports `OK` once markers match.

## [2.0.0] - 2026-05-11

### Changed (BREAKING)

- **Skill rename for namespace clarity.** Two of this plugin's skills shared bare names with another plugin or were too vague to disambiguate in the `/` menu. Renames:
  - `tcs-git-helpers:setup` → `tcs-git-helpers:git-setup` (collided with `tcs-helper:setup`; the domain prefix also signals what the skill does)
  - `tcs-git-helpers:status` → `tcs-git-helpers:git-audit` (the skill audits branch hygiene and override-consumption events, not just "status")

  Source directories renamed (`plugins/tcs-git-helpers/skills/{setup,status}/` → `{git-setup,git-audit}/`). Test files renamed accordingly (`skill_setup.bats` → `skill_git_setup.bats`, `skill_status.bats` → `skill_git_audit.bats`). All cross-references in scripts, hook templates, references, and audit-log nudges updated.

  **User-visible impact:** anyone who scripted invocations of `/tcs-git-helpers:setup` or `/tcs-git-helpers:status` must update to the new names. Tab-completion via the `/` menu picks up the new names automatically on next plugin refresh.

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
