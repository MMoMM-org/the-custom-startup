# Changelog

## [2.2.19] - 2026-09-04

### Fixed

- **The cache reader and the cache writer used different directories (issue #24, F-002).**
  The path was derived independently in eight places with three different defaults, and they
  diverged exactly when `CLAUDE_PLUGIN_DATA` is unset — which is the normal case, because the
  harness sets it only for code it spawns itself. Git-spawned hooks (`core.hooksPath`) and
  Bash-tool subprocesses get nothing.

  Observed on the development machine before the fix: `post-merge` had written
  `~/.claude/plugins/data/tcs-git-helpers-the-custom-startup/cache/` minutes earlier, while
  `session-start-brief.sh` and `git_status_audit.py` were reading a four-day-old file under
  `~/.claude/plugin-data/cache/`. There is no error in that state — the reader simply serves
  old data, so `git-audit --json` and the SessionStart stale-branch count were both quietly wrong.

  All resolvers now follow one rule, the one `lib-bundle.sh` already used because it is the only
  resolver that must work with no environment at all:

      CLAUDE_PLUGIN_DATA set → $CLAUDE_PLUGIN_DATA
      otherwise              → $HOME/.claude/plugins/data/tcs-git-helpers-<repo basename>

  which reconstructs the harness's own path shape. The plugin-side copy lives in the new
  `scripts/lib/plugin_data.sh`, sourced by `lib/cache.sh` and `lib/audit_log.sh`;
  `git_status_audit.py` mirrors it in Python. `lib-bundle.sh` keeps its own copy, unavoidably —
  it is installed byte-verbatim into consumer repos and cannot source plugin files.

  `tests/bats/cache-path-parity.bats` executes every resolver under both conditions and asserts
  they agree, and fails on any new competing default appearing in the tree. That test is what
  keeps the copies from drifting again.

- **`audit_log.sh` used a third variant** (`…/plugins/data/tcs-git-helpers`, no repo suffix).
  Nothing had ever been written there; override audit events landed in the suffixed directory
  via the harness variable. Now on the shared rule.

- **`test_degraded_mode_no_plugin_data` asserted a behaviour the hook never had.** It checked
  that "no cache files were written anywhere" by looking in `~/.claude/plugin-data/cache` — the
  wrong directory. The hook does write when `CLAUDE_PLUGIN_DATA` is unset; it derives the path.
  The test passed because it looked where nothing was, and the writes it missed went into the
  developer's real `$HOME`. Renamed to `test_derives_cache_path_when_plugin_data_unset` and now
  asserting the derived path, with `HOME` stubbed in `githooks_post_merge.bats`,
  `githooks_pre_push.bats` and `lib-bundle.bats` so fixtures stop escaping the test sandbox.

- **A `CLAUDE_PLUGIN_DATA` ending in `/` split the resolvers again.** `pathlib` collapses a
  trailing slash and `printf` does not, so the shell writer and the Python reader produced paths
  differing by one character — the same class of split this release closes. Both shell resolvers
  now strip trailing slashes, and `cache-path-parity.bats` covers that input.

  Found by the parity suite itself: it passed on ubuntu and failed on macOS, because macOS
  exports `TMPDIR` with a trailing slash and the fixtures inherited it.

  Hook bundle version `h3` → `h4`: `lib-bundle.sh` changed, so installed repos should re-run
  `/tcs-git-helpers:git-setup --update`.

### Migration

- An orphaned cache may remain at `~/.claude/plugin-data/cache/<hash>-stale-cache.{tsv,json}`.
  It is inert and safe to delete; the next merge regenerates the cache at the canonical path.
  No re-install needed — the hooks were always writing to the right place.

## [2.2.18] - 2026-09-04

### Fixed

- **Heredoc bodies and command substitutions no longer trip false denials (issue #23).**
  PR #42 moved dispatch off whole-string matching onto per-clause matching over a
  quote-stripped command, which fixed the common case — a commit message or PR body that
  merely *describes* a destructive op. Two data regions were still carried through into the
  matched string:
  - **Heredoc bodies.** A heredoc body is not quoted, so nothing stripped it. `git commit -F -
    <<EOF` with a message mentioning `git reset --hard` was denied. `_strip_heredocs` now
    blanks the body while keeping the line that opens it, and runs *before* quote stripping so
    a quoted delimiter (`<<'EOF'`) survives long enough to match its own terminator.
  - **Command substitutions containing quotes.** The inner `"` of `$(printf "…")` was read as
    the closing quote of the outer argument, desyncing the stripper and leaking the rest of the
    line. `_strip_quoted` is now a small state machine with a nesting stack.

  **Substitutions are not blanked, deliberately.** `$( … )` executes, so `echo "$(git reset
  --hard)"` really does reset — its content stays in scope and only its own quoting is
  stripped. Likewise a heredoc fed to a shell (`bash <<EOF`) is code, and is left intact. Both
  distinctions are pinned by tests, because the tempting simplification — blank the whole
  region — fails OPEN.

- **`nudge-hook.sh` matched the raw command too**, so the same literals produced spurious
  advisory nudges. It now clausifies once and matches per clause, like the blocking hook.

## [2.2.16] - 2026-09-02

### Changed (test-side)

- **Removed 45 tests that could only pass, and replaced them with 8 that can fail (issue #90).**
  The suite was full of the string-presence trap: asserting that a source file *contains* a
  phrase proves only that the source is the source. Those tests were wrong in both directions —
  they broke on a harmless rewording, and they passed whenever the code said the right words
  while behaving wrongly. Net count 837 → 800.
  - `skill_git_setup.bats` — dropped the 21-test `A11..A31 "body documents X"` block
    (`grep -qi 'submodule'`, `grep -qiE 'not.*commit|no.*auto.*commit|...'`, and
    `SKILL.md has at least 80 lines`). Replaced with two checks that derive their expectation
    from the skill itself: every `${CLAUDE_PLUGIN_ROOT}/…` helper it invokes must exist, and
    every `references/*.md` it cites must exist. A renamed helper now fails the build instead
    of silently leaving the skill pointing at nothing.
  - `skill_git_audit.bats` — dropped 15, including greps for the words `branch`, `stale`,
    `suggestion`, `worktree` and a `≥ 30 lines` proxy. Replaced with a derived check that asks
    the python backend for its own interface (`git_status_audit.py --help`) and requires the
    skill to document every flag it reports — so a new backend flag cannot ship undocumented.
    The "does not re-implement git state-gathering inline" check is kept and relabelled: it
    asserts an *absence*, which is a lint, not a behavioural test.
  - `docs_smoke.bats` — dropped the four `README has '## Skills'` style greps and the
    `CHANGELOG has '## [1.0.0]'` grep. Headings are prose for humans; the link-integrity check,
    which resolves every path the README claims exists, stays.
  - `hooks-runtime-contract.bats` — dropped the four `sources lib-bundle.sh via dirname` greps.
    Section 11 already demonstrates dirname-relative resolution by observation for the two
    hooks that hard-exit; added three tests covering what `pre-commit` and `commit-msg`
    actually guarantee, since they soft-source the lib and had no such coverage: without
    `lib-bundle.sh` they still allow a clean feature-branch commit, still block a commit on
    `main`, and still accept a conventional subject.
  - `hooks-runtime-contract.bats` Section 9 (no `CLAUDE_PLUGIN_` in hook templates) is retained
    and relabelled as a lint — an absence check, deliberately kept.

### Fixed (test-side)

- **`fixtures_sanity.bats` now derives the gh-stub scenario list instead of hard-coding four
  names.** The old test listed `closed-pr`, `merged-pr`, `no-auth`, `rate-limited` and checked
  the fixture README mentions them — it could never notice a scenario added to the stub and left
  undocumented. Two already had: `merged-pr-no-sha` and `stale-3-branches`, both in active use
  by `block-bad-git-ops.bats`, `hooks-runtime-contract.bats` and `githooks_post_merge.bats`.
  Truth now comes from the stub (response directories plus the failure-mode `case` labels), and
  both scenarios are documented in `gh_stubs/README.md`.

## [2.2.14] - 2026-09-01

### Fixed

- **The destructive-op guard failed open on Linux/glibc (silent, since v1.0).** Seven
  patterns in `scripts/lib/pattern_match.sh` — and two nudge patterns in
  `scripts/nudge-hook.sh` — used the word-boundary classes `[[:<:]]` / `[[:>:]]`.
  Those are a **BSD/macOS regex extension**. Under glibc, `regcomp` rejects them
  (`Invalid character class name`), so `[[ =~ ]]` exits **2** — and every caller
  reads a non-zero exit as "no match". The result: on Linux and in Docker
  containers, `git reset --hard`, `git branch -D`, `git stash drop`,
  `git reflog expire`, `git commit --no-verify`, `git push --delete` and the whole M1
  closed-PR push check were **allowed without a word of warning**. `git clean -fd`
  and the other boundary-free patterns kept working, which is why the hole went
  unnoticed. Replaced every occurrence with the portable trailing-boundary idiom
  `([^[:alnum:]_]|$)`, which is equivalent on both engines. Match behaviour on
  macOS is unchanged; Linux now denies what it always should have.
- **`tests/e2e/dogfood.sh` scenario 10 had the same defect.** Its bash-4-feature
  detector fed `[[:>:]]` to `grep -E`, so on GNU grep the pattern errored out and
  the scenario could never report a hit — a lint that silently lints nothing.

### Added (tests)

- Two regression guards in `lib_pattern_match.bats`: every `PATTERN_` constant must
  **compile** on the running platform (catches the fail-open directly), and no
  `PATTERN_` constant may use `[[:<:]]` / `[[:>:]]` (catches it on macOS too, where
  the broken form still compiles). Both were verified to fail against the old code.

### Fixed (test-side)

- **Three tests could not distinguish "tool absent" from "tool present" on Linux.**
  `_guard_gh` / `_guard_jq` / post-merge-without-`gh` simulated an unavailable tool
  with `PATH=/bin`, which only works on macOS — on Linux `/bin` is a symlink to
  `/usr/bin`, so `gh` and `jq` were still resolvable and the guards never fired.
  New `_minimal_path` helper in `tests/bats/lib/helpers.bash` builds a PATH holding
  symlinks to exactly the named tools.
- **The CON-9 evidence test asserted one platform's behaviour as universal.** It
  claimed PCRE `\s+` "does NOT match" — true on BSD, false on glibc, where `\s` is
  a supported extension. Reframed to assert the *platform split* that CON-9 exists
  to guard against, plus a new case pinning the `[[:>:]]` compile failure on glibc.

## [2.2.6] - 2026-06-03

### Fixed

- **`pre-push` hook no longer fails open on MERGED/CLOSED PRs (M1 false-negative).** The repo-side `.githooks/pre-push` hook is meant to block pushes to branches whose GitHub PR is CLOSED or MERGED (PRD M1 AC1–AC5). But its lookup ran `gh pr list --head <branch> --json … --limit 1` **without `--state all`** — and `gh pr list` defaults to `--state open`. So a closed or merged PR (exactly the case the hook exists to catch) was invisible: the query returned `[]`, the hook classified it as `NO_PR`, and the push was allowed. Added `--state all`, matching the canonical query in `scripts/lib/git_state.sh` (the Claude-side `block-bad-git-ops.sh` path was already correct; only the git-level template hook had drifted).
- **Test-stub fidelity: the gh stub now emulates `gh pr list`'s state filtering.** The fixture stub (`tests/fixtures/gh_stubs/gh`) previously returned its canned `pr-list` response regardless of the `--state` flag, so the three `pre-push` block-tests (`merged`, `closed`, standalone-closed) passed *vacuously* — they never exercised the missing `--state all` and so never caught the bug. The stub now mirrors real `gh`: an explicit `--state` returns the canned response verbatim (all existing fixtures unaffected), while a call with **no** `--state` flag filters to OPEN/DRAFT only. With this fidelity restored, those three existing tests fail against the unpatched hook and pass against the fix — converting false-greens into genuine regression guards (project-memory: test-stubs-mirror-real-wire-format).
  - **Action for installed repos:** the fix is in the template; existing installs carry the old hook until re-installed. Run `/tcs-git-helpers:git-setup --update` to refresh `.githooks/`.

## [2.2.5] - 2026-06-03

### Fixed (test-side)

- **Removed 10 stale bats assertions that drifted from shipped reality (no production change).**
  - `plugin_manifest.bats` asserted `plugin.json` version `1.0.0`; versions are auto-bumped on merge, so it now asserts semver *shape* instead of a hardcoded literal.
  - Version-marker tests (`githooks_{commit_msg,pre_commit,pre_push,post_merge}.bats`, `gha_pr_title_check.bats`) grepped the source templates for a concrete `vN.N.N`, but templates intentionally carry the `v__TCS_GIT_HELPERS_VERSION__` placeholder that `install_files.sh` substitutes at install time (the substituted form is already covered by the e2e/rollout tests). The regex now accepts the placeholder or a concrete version, and uses ERE for BSD-grep portability.
  - `docs_smoke.bats` required `## Overview` / `## Basic Usage` sections and an `M1..M12` PRD-goal dump that spec-006 (docs-rewrite) intentionally removed; the test now tracks the current `## Skills` / `## Hooks` information architecture.

## [2.2.4] - 2026-06-03

### Fixed

- **NO_VERIFY no longer false-positives on sibling commands (spec-015).** The bypass guard's pattern `git[[:space:]]+commit.*(--no-verify|-n[[:>:]])` used an unbounded `.*` that bridged from `git commit` to a `-n` flag belonging to a *different* command chained in the same string — so legitimate compounds like `git commit -m "done" && echo -n ok`, `git commit -m "x" ; head -n 5 f`, or `git commit -m "x" | grep -n foo` were wrongly denied. Because bash does not set `REG_NEWLINE`, `.` also matched newlines, so multi-line compounds were affected too. The detection now runs through a new `_match_no_verify` helper that splits the (quote-stripped) command on shell separators (`&&`, `||`, `|`, `;`, `&`, newline) and matches the **unchanged** `PATTERN_NO_VERIFY` against each clause individually, so the `.*` can no longer reach a sibling command's flag.
  - **Preserved**: genuine `git commit --no-verify` / `git commit -n` (including chained forms like `git add . && git commit -n`) still deny; `-n` / `--no-verify` text inside a quoted `-m "..."` message is still exempt (via the existing `_strip_quoted`).
  - `PATTERN_NO_VERIFY` is byte-identical; only the call site changed. Added unit + dispatcher regression tests and bypass-corpus entries covering the sibling-command cases.

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
