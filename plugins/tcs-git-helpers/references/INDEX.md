# tcs-git-helpers — References Index

This is the `tcs-git-helpers` references library — the same docs that hook denial
messages and the `/tcs-git-helpers:git-audit` skill cite by relative path. Each
entry is a self-contained markdown file that follows a five-part structure:
*What goes wrong → How to detect → Fix → Prevention → Why*. The prose is aimed
at Claude (the agent reading the denial), not at the human terminal user, but
Marcus also reads them when reviewing audit logs.

When a hook denies something, it links the most relevant reference in the
denial reason. Use this INDEX as a router when the citation is missing or when
you need to look up a related topic.

Start at [best-practices.md](best-practices.md) for the philosophy and the
core principles that the rest of these docs apply to specific failure modes.

---

## By topic

### Branch lifecycle
- [branch-lifecycle.md](branch-lifecycle.md) — the full Create → Work → PR → Merge → Cleanup loop, with the four "unfinished" states that block branching off main. *Covers PRD M2, M9.*
- [stale-branch-cleanup.md](stale-branch-cleanup.md) — how stale-merged branches accumulate and how `post-merge` + `--cleanup` surface them. *Covers PRD M6, M9.*
- [worktree-discipline.md](worktree-discipline.md) — when to use `git worktree`, the four-check exit guard, and recovery for accidental worktree removal. *Covers PRD M8.*

### Commits & messages
- [conventional-commits.md](conventional-commits.md) — format spec, allowlisted types, the `[skip-format-check]` escape hatch, and merge-commit exemption rule. *Covers PRD M5.*
- [pr-vs-commit-messages.md](pr-vs-commit-messages.md) — why PR title becomes the commit on squash-merge, and how to keep them aligned without double-typing. *Covers PRD M5, M9.*

### History rewriting
- [squash-merge-trap.md](squash-merge-trap.md) — Marcus's original finding: why a squash-merged branch shows `mergeable: CONFLICTING`, and the cherry-pick recovery. *Covers PRD M1, M3.*
- [rebase-vs-merge.md](rebase-vs-merge.md) — when each is appropriate, what each rewrites, and how to verify the result. *Covers PRD M9.*
- [force-push-safety.md](force-push-safety.md) — the canonical `--force` vs `--force-with-lease` distinction and why protected branches deny even the lease form. *Covers PRD M7 (force-push patterns).*

### Cleanup & destructive ops
- [destructive-ops.md](destructive-ops.md) — the full Boucle-parity set: `reset --hard`, `clean -f`, `branch -D`, `stash drop/clear`, `reflog expire`, `checkout .`, `--no-verify`, and the granular overrides for each. *Covers PRD M7, M12.*
- [working-tree-hygiene.md](working-tree-hygiene.md) — clean-tree discipline, the stash-vs-branch decision, and how `.orig` files leak after merges. *Covers PRD M9 (stash-pop nudge).*

### Setup & tooling
- [migrating-from-husky.md](migrating-from-husky.md) — why setup aborts when Husky / lefthook / pre-commit / simple-git-hooks is detected, and the per-tool removal procedure. *Covers PRD M10.*
- [sandbox-and-git-config.md](sandbox-and-git-config.md) — Claude Code sandbox interactions with `git config core.hooksPath`, why `git -c core.hooksPath=…` is denied, and override semantics. *Covers PRD CON-7, M10, M7.*
- [gh-token-hygiene.md](gh-token-hygiene.md) — required scopes for `--with-branch-protection`, how setup detects excessive scopes, and the `gh auth refresh` recovery. *Covers PRD S1.*

### Landing
- [best-practices.md](best-practices.md) — overview of why this plugin exists and the four core principles all references apply.

---

## By failure mode

| Symptom Claude observed | Read this | PRD |
|---|---|---|
| `git push` denied: PR is CLOSED or MERGED | [squash-merge-trap.md](squash-merge-trap.md) | M1 |
| `git checkout -b` denied: current branch is unfinished | [branch-lifecycle.md](branch-lifecycle.md) | M2 |
| `git checkout <branch>` denied: branch was squash-merged | [squash-merge-trap.md](squash-merge-trap.md) | M3 |
| Edit/Write denied on `main` / `master` | [branch-lifecycle.md](branch-lifecycle.md) | M2, M11 |
| Stale local branches piling up after merges | [stale-branch-cleanup.md](stale-branch-cleanup.md) | M6 |
| `git reset --hard` / `git clean -f` / `git branch -D` denied | [destructive-ops.md](destructive-ops.md) | M7 |
| `git push --force` denied (recommend `--force-with-lease`) | [force-push-safety.md](force-push-safety.md) | M7 |
| ExitWorktree denied with uncommitted/untracked/unmerged/unpushed work | [worktree-discipline.md](worktree-discipline.md) | M8 |
| `commit-msg` rejected — bad Conventional Commits format | [conventional-commits.md](conventional-commits.md) | M5 |
| PR title differs from commit message after squash-merge | [pr-vs-commit-messages.md](pr-vs-commit-messages.md) | M5, M9 |
| `git rebase` finished — what to verify | [rebase-vs-merge.md](rebase-vs-merge.md) | M9 |
| `git stash pop` left `.orig` files behind | [working-tree-hygiene.md](working-tree-hygiene.md) | M9 |
| Setup aborted: existing Husky / lefthook / pre-commit / simple-git-hooks | [migrating-from-husky.md](migrating-from-husky.md) | M10 |
| `git -c core.hooksPath=…` denied / sandbox refused | [sandbox-and-git-config.md](sandbox-and-git-config.md) | M7, CON-7 |
| `setup --with-branch-protection` warned about token scopes | [gh-token-hygiene.md](gh-token-hygiene.md) | S1 |

---

## How references are cited

Hook denial messages cite by absolute plugin path so the reference resolves
regardless of the caller's working directory:

```
See: ${CLAUDE_PLUGIN_ROOT}/references/squash-merge-trap.md
```

When reading a denial, replace `${CLAUDE_PLUGIN_ROOT}` mentally with the
plugin install path (typically `~/.claude/plugins/cache/the-custom-startup/tcs-git-helpers/<version>/`).
The `references/` directory is **plugin-internal only** — it is not copied
into target repos. That is intentional: single source of truth, updates
propagate via plugin update.
