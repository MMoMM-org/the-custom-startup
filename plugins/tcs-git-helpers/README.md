# tcs-git-helpers Plugin

Git workflow discipline for Claude Code — machine-enforces the recurring git mistakes Claude makes across repos: pushes to closed PRs, branches off unfinished work, squash-merge resume, destructive ops, worktree-exit data loss, and more.

## Version 1.0.0

First release. Ships a coherent set of `PreToolUse` / `PostToolUse` / `SessionStart` hooks plus a per-repo `.githooks/` template set, a `setup` skill, and a `status` skill. Defense-in-depth: hooks installed via `core.hooksPath` keep enforcing rules even when the plugin is disabled.

See [CHANGELOG.md](CHANGELOG.md) for full details.

## Overview

Claude has no persistent memory across sessions and reflexively reproduces a small set of expensive git mistakes. This plugin closes that loop with structured `permissionDecision: deny` denials, granular single-shot overrides, audit logging, and reference docs cited from the denial messages themselves.

The 12 PRD Goals (M1–M12) covered by this plugin:

- M1 — Block pushes to closed/merged PRs (cite PR state; cite squash-merge trap reference)
- M2 — Block branch creation from unfinished work (clean-but-unmerged OR dirty tree)
- M3 — Block resume of squash-merged branches (`git cherry` detection; cherry-pick recovery)
- M4 — Pre-flight branch awareness brief at SessionStart and after `post-merge` (≤300ms p99, no `gh` calls)
- M5 — Conventional Commits enforcement in `commit-msg` (allowlisted types; merge commits exempted)
- M6 — Stale local branch surfacing after `post-merge` and via `/tcs-git-helpers:git-audit --cleanup`
- M7 — Block destructive git operations (`reset --hard`, `clean -f`, `branch -D`, `--force`, `--no-verify`, …)
- M8 — Worktree exit data-loss guard (uncommitted/untracked/unmerged/unpushed four-check)
- M9 — Soft nudges after key git ops (PR title, base freshness, rebase verification, stash hygiene)
- M10 — Plugin distribution and per-repo setup (idempotent, conflict-detecting, lock-serialized)
- M11 — Defense in depth — `.githooks/` enforces the same rules with the plugin disabled
- M12 — Override discipline — single-shot env-var overrides + JSONL audit trail

Two Should-Have features (S1 optional GitHub branch protection, S2 optional GHA PR-title check) are opt-in via `setup --with-branch-protection` and `setup --with-gha`.

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

## Basic Usage

The plugin runs invisibly via Claude Code hooks. You will only notice it when:

1. **Claude tries something risky** — the operation is denied with a structured message naming the rule, the override env-var, and a reference doc path. Example:

   ```
   [tcs-git-helpers] DENIED: push to closed PR #42 (state=CLOSED)
   Recovery: open a fresh branch and PR, or cherry-pick onto main.
   See: references/squash-merge-trap.md
   Override (single-shot): CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
   ```

2. **A SessionStart brief appears** — one line summarizing branch, working-tree state, ahead/behind counts, and stale-merged branch count.

3. **A PostToolUse nudge appears** — one-line reminder after `git checkout -b`, `gh pr create`, `gh pr merge`, `git rebase`, `git stash pop`.

4. **You run a slash command:**
   - `/tcs-git-helpers:git-setup` — install/update `.githooks/` in the current repo
   - `/tcs-git-helpers:git-audit` — show repo state, stale branches, override audit
   - `/tcs-git-helpers:git-audit --cleanup` — interactively delete stale-merged branches
   - `/tcs-git-helpers:git-audit --overrides` — review recent override consumption events

### Overrides

Every safety rule has a single-shot env-var override. Set the env-var, run the command once, and the override is consumed automatically. Examples:

```bash
CLAUDE_ALLOW_RESET_HARD=1 git reset --hard origin/main
CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push
CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1 git checkout -b feat/new
```

The master override `CLAUDE_ALLOW_GIT_BAD_OPS=1` exists as a tripwire-style escape but emits a loud stderr warning recommending the granular form. All consumption events are appended to `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` (rotated at 1MB).

## References

External:
- [the-custom-startup marketplace](https://github.com/MMoMM-org/the-custom-startup)
- [Boucle-framework prior art](https://github.com/Bande-a-Bonnot/Boucle-framework) — `git-safe`, `branch-guard`, `worktree-guard` patterns absorbed via re-implementation
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [GitHub Branch Protection API](https://docs.github.com/rest/branches/branch-protection)

Internal (plugin-local; cited from denial messages by absolute plugin path):
- `references/squash-merge-trap.md` — push-to-closed-PR, squash-merge fingerprint, cherry-pick recovery
- `references/branch-lifecycle.md` — full branch Create → Work → PR → Merge → Cleanup loop
- `references/conventional-commits.md` — format spec, allowlisted types, skip-format-check escape
- `references/destructive-ops.md` — full destructive-op set and granular overrides
- `references/worktree-discipline.md` — worktree usage, four-check exit guard, recovery
- `references/migrating-from-husky.md` — removal procedures for Husky, lefthook, pre-commit, simple-git-hooks
- `references/force-push-safety.md` — `--force` vs `--force-with-lease`, protected-branch behaviour
- `references/rebase-vs-merge.md` — when each is appropriate, what each rewrites, post-rebase verification
- `references/stale-branch-cleanup.md` — how stale branches accumulate and how `--cleanup` surfaces them
- `references/working-tree-hygiene.md` — clean-tree discipline, stash vs branch, `.orig` leak detection
- `references/pr-vs-commit-messages.md` — why PR title becomes the commit on squash-merge
- `references/sandbox-and-git-config.md` — Claude Code sandbox interactions, `core.hooksPath` deny semantics
- `references/gh-token-hygiene.md` — required scopes for `--with-branch-protection`, excessive-scope detection
- `references/best-practices.md` — overview philosophy and four core principles

See [references/INDEX.md](references/INDEX.md) for the full by-topic and by-failure-mode index.

## License

MIT — see repository root.
