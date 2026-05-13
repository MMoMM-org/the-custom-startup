# tcs-git-helpers Plugin

Git workflow discipline for Claude Code — machine-enforces the recurring git mistakes Claude makes across repos: pushes to closed PRs, branches off unfinished work, squash-merge resume, destructive ops, worktree-exit data loss, and more.

See [CHANGELOG.md](CHANGELOG.md) for version history. Hooks load natively from `hooks/hooks.json` via Claude Code's plugin system — no manual installation step.

Claude has no persistent memory across sessions and reflexively reproduces a small set of expensive git mistakes. This plugin closes that loop with structured `permissionDecision: deny` denials, granular single-shot overrides, audit logging, and reference docs cited from the denial messages themselves.

## Skills

| Skill | Description |
|-------|-------------|
| `/tcs-git-helpers:git-setup` | Per-repo install — writes `.githooks/`, sets `core.hooksPath`, detects and aborts on Husky/lefthook/pre-commit/simple-git-hooks conflicts. Optional `--with-branch-protection` (GitHub single-coder preset) and `--with-gha` (PR-title check workflow). |
| `/tcs-git-helpers:git-audit` | Per-repo health check — branch state, stale-merged branches, override audit. `--cleanup` to interactively delete stale branches; `--overrides` to review recent override consumption events. |

## Hooks

Hooks are **natively loaded** by Claude Code from `hooks/hooks.json` when the plugin is enabled. No installation step required.

| Event | Script | Purpose |
|-------|--------|---------|
| `PreToolUse(Bash)` | `block-bad-git-ops.sh` | Deny 14+ destructive git/gh patterns: push to closed PR, branch from unfinished work, squash-merge resume, `reset --hard`, `clean -f`, `branch -D`, `--force` (without `--force-with-lease`), `--no-verify`, `stash drop/clear`, `reflog expire`, `checkout .`, `restore --worktree`, `push --delete`, `core.hooksPath` overrides |
| `PreToolUse(Edit\|Write\|NotebookEdit)` | `pre-edit-branch-check.sh` | Block edits to `main`/`master` unless the path is in `.gitignore` |
| `PreToolUse(Edit\|Write\|NotebookEdit)` | `protect-git-internals.sh` | Block edits to `.git/` internals |
| `PreToolUse(ExitWorktree)` | `worktree-exit-guard.sh` | Four-check guard before worktree exit — uncommitted, untracked, unmerged, unpushed |
| `PostToolUse(Bash)` | `nudge-hook.sh` | Soft, success-only nudges after `git checkout -b`, `gh pr create`, first `git push -u`, `gh pr merge`, `git rebase`, `git stash pop` (60s same-nudge dedup) |
| `SessionStart` | `session-start-brief.sh` | One-line branch awareness brief — branch, working-tree state, ahead/behind, stale-merged count (cache-only, ≤300ms p99, no `gh` calls) |

## How It Works

`/tcs-git-helpers:git-setup` installs a self-contained bundle into `.githooks/` that works independently of the Claude Code plugin:

- **Self-contained install:** Four hooks (`pre-commit`, `pre-push`, `commit-msg`, `post-merge`) plus two shared libraries (`lib-bundle.sh`, `lib-config-parser.sh`) are copied directly into the target repo's `.githooks/` directory. The hooks require no environment variables from the harness and work in any shell.
- **Bundle versioning:** A version marker file `.githooks/tcs-git-helpers-version` (e.g., `h1`) tracks the bundle's code version independently of the plugin's semantic version. This allows users to stay on older plugin versions while receiving hook improvements.
- **Drift detection:** When you run hook-dependent skills (`/tcs-git-helpers:git-audit --cleanup`, `--default`, or `--json`), the skill checks if the installed bundle matches its expectations. If the versions differ, a prompt informs you to re-run `/tcs-git-helpers:git-setup` to update the hooks. This check fires at skill invocation time, not at session start, keeping your SessionStart brief silent.
- **Updates:** Run `/tcs-git-helpers:git-setup` again to refresh all four hooks and the version marker atomically.

## Defense in Depth

The installed hooks enforce their rules **even when the Claude Code plugin is disabled**:

| Hook | Enforces |
|------|----------|
| `pre-commit` | Working-tree hygiene, `.orig` leak detection |
| `pre-push` | Push-to-closed-PR, force-push to protected branch |
| `commit-msg` | Conventional Commits format (allowlisted types; merge commits exempt; `[skip-format-check]` escape; optional `TCS_REQUIRE_SCOPE=1`) |
| `post-merge` | Stale-merged branch surfacing + branch awareness brief |

Each hook carries a banner comment identifying its bundle version (e.g., `# tcs-git-helpers: h1`); `/tcs-git-helpers:git-setup` stamps the banner at install time.

## Overrides

Every safety rule has a single-shot env-var override. Set the env-var, run the command once, and the override is consumed automatically (5-second sentinel prevents double-tap):

```bash
CLAUDE_ALLOW_RESET_HARD=1 git reset --hard origin/main
CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push
CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1 git checkout -b feat/new
CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1   # exit worktree with dirty tree
```

The master override `CLAUDE_ALLOW_GIT_BAD_OPS=1` exists as a tripwire-style escape but emits a loud stderr warning recommending the granular form. All consumption events are appended to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` (rotated at 1MB). Audit-write failures NEVER block hook decisions.

## References

Cited from denial messages by absolute plugin path. See [references/INDEX.md](references/INDEX.md) for the full by-topic and by-failure-mode index.

| Reference | Topic |
|-----------|-------|
| `squash-merge-trap.md` | Push-to-closed-PR, squash-merge fingerprint, cherry-pick recovery |
| `branch-lifecycle.md` | Full branch Create → Work → PR → Merge → Cleanup loop |
| `conventional-commits.md` | Format spec, allowlisted types, skip-format-check escape |
| `destructive-ops.md` | Full destructive-op set and granular overrides |
| `worktree-discipline.md` | Worktree usage, four-check exit guard, recovery |
| `migrating-from-husky.md` | Removal procedures for Husky, lefthook, pre-commit-framework, simple-git-hooks |
| `force-push-safety.md` | `--force` vs `--force-with-lease`, protected-branch behaviour |
| `rebase-vs-merge.md` | When each is appropriate, what each rewrites, post-rebase verification |
| `stale-branch-cleanup.md` | How stale branches accumulate and how `--cleanup` surfaces them |
| `working-tree-hygiene.md` | Clean-tree discipline, stash vs branch, `.orig` leak detection |
| `pr-vs-commit-messages.md` | Why PR title becomes the commit on squash-merge |
| `sandbox-and-git-config.md` | Claude Code sandbox interactions, `core.hooksPath` deny semantics |
| `gh-token-hygiene.md` | Required scopes for `--with-branch-protection`, excessive-scope detection |
| `best-practices.md` | Overview philosophy and four core principles |

## Tests

```bash
bats plugins/tcs-git-helpers/tests/bats/
plugins/tcs-git-helpers/tests/e2e/dogfood.sh
```

## Maintenance

**Hook bundle version contract:** Any change to files under `templates/githooks/` (the four hook scripts, shared libraries, or the version marker file) MUST be accompanied by a bump to `templates/githooks/tcs-git-helpers-version`. The CI check at `scripts/ci/check-hook-bundle-version.sh` enforces this and fails the build on mismatch.

The rationale: hook bundles are installed into user repos independently and are versioned separately from the plugin's semantic version. Without this strict contract, drift between what a user has installed and what the plugin expects can silently accumulate. The version marker lets skills detect and surface outdated bundles at runtime.

**GitHub branch-protection rule requirement:** The `Hook bundle version check` CI gate must be marked as a required status for PR merge. This cannot be automated in code — it must be configured in the repository's GitHub branch-protection settings under Settings → Branches → Branch protection rules. Without it, changes to hook code can bypass the version-bump check.

## Attribution

Patterns absorbed via re-implementation from [Boucle-framework](https://github.com/Bande-a-Bonnot/Boucle-framework) (`git-safe`, `branch-guard`, `worktree-guard`). Conventional Commits per the [1.0.0 spec](https://www.conventionalcommits.org/en/v1.0.0/). GitHub branch protection via the [Branch Protection API](https://docs.github.com/rest/branches/branch-protection).

## Installation

```bash
/plugin marketplace add MMoMM-org/the-custom-startup
/plugin install tcs-git-helpers@the-custom-startup
```

Then, in each repo where you want the `.githooks/` defense-in-depth layer:

```bash
/tcs-git-helpers:git-setup
```

The setup skill detects existing tooling (Husky, lefthook, pre-commit framework, simple-git-hooks) and aborts with a migration reference rather than silently coexisting. It does NOT auto-commit — review the `.githooks/` diff and commit manually.

## License

MIT — see repository root.
