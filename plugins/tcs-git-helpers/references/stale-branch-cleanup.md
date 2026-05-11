# Stale Branch Cleanup

After a PR merges, the feature branch is "done" but the local and remote
refs persist by default. Without cleanup they accumulate, obscure active
work, and feed the squash-merge-resume failure mode (M3). The post-merge
hook (M6) surfaces stale candidates after each pull; the status skill's
`--cleanup` flag drives interactive deletion.

## What goes wrong

1. **Merged branches accumulate locally.** Each squash-merged PR leaves the
   feature branch behind on disk. `git branch` listings get noisy. Marcus's
   Kado repo had 6 stale local branches (`docs/restructure-documentation`,
   `feat/read-tags-operation`, `feat/search-filter`,
   `chore/github-funding`, `docs/api-reference-add-kado-open-notes`,
   `fix/issue-8-blacklist-crud-semantics`) at brainstorm time — each with
   a merged PR but never deleted.
2. **Stale branches feed the squash-merge trap.** A leftover local
   `feat/foo` branch invites Claude to "resume" it. After squash-merge, the
   per-commit SHAs no longer match anything on default; `gh pr create`
   reports `mergeable: CONFLICTING`. See [squash-merge-trap.md](squash-merge-trap.md).
3. **Remote stale tracking refs.** Even after a remote branch is deleted on
   GitHub, the local `refs/remotes/origin/<branch>` lingers until
   `git fetch --prune` is run.
4. **Ambiguous state for new contributors.** A teammate cloning the repo
   sees a long branch list and cannot tell which branches are alive.

## How to detect

```bash
# Local branches whose tip is reachable from the default branch
# (NB: squash-merged branches are NOT reachable — see squash-merge-trap.md)
git branch --merged origin/$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|origin/||')

# Local branches whose PR is merged (squash-merge-aware)
gh pr list --state merged --limit 100 --json headRefName,number,mergeCommit \
  | jq -r '.[] | "\(.headRefName)\t#\(.number)\t\(.mergeCommit.oid // "no-merge-commit")"'

# Remote tracking refs that point at deleted remote branches (need prune)
git remote prune origin --dry-run

# Worktrees — branches in worktrees should NEVER be deleted from cleanup
git worktree list
```

The post-merge hook (Feature M6) automates this after each `git pull`:

```text
[tcs-git-helpers] post-merge: 6 stale-merged branches detected
  feat/old-thing       (PR #38 merged 2026-04-12)
  fix/another-thing    (PR #40 merged 2026-04-15)
  ...
Run /tcs-git-helpers:git-audit --cleanup to delete interactively.
```

The SessionStart brief (Feature M4) includes the count:

```text
[tcs-git-helpers] feat/foo • clean • 2 ahead • 6 stale-merged
```

## Fix

All cleanup commands below are non-destructive when used as shown. They
refuse to act on unmerged or worktree-bound branches.

**Interactive cleanup via the status skill (preferred):**

```bash
/tcs-git-helpers:git-audit --cleanup
# Lists each stale-merged branch; prompts y/n per branch; excludes any
# branch currently checked out in a worktree (M6 acceptance criterion).
```

**Manual cleanup, one branch at a time:**

```bash
# -d (lowercase) refuses if the branch isn't merged into HEAD or its upstream
git branch -d <merged-branch>
```

`git branch -d` is the **non-destructive** delete: it errors out if the
branch has unmerged work. The destructive sibling `git branch -D` (uppercase)
forces delete regardless of merge state and is denied by the M7 hook.

For a squash-merged branch, `git branch -d` may refuse because the squashed
commit has a different SHA than the branch's tip. In that case, verify the
PR merged status explicitly first:

```bash
gh pr list --head <branch> --state merged --json number,state,mergeCommit
# If merged: SHA on default differs but the diff is empty. Confirm with:
git cherry origin/main <branch>   # all "-" lines means content is on main

# Once confirmed, the branch is safe to delete with -d ... but git -d may
# still refuse. The non-destructive workaround is to first merge the branch's
# tip into HEAD as a no-op, then delete:
git switch main && git pull --ff-only
git merge --ff-only --no-commit <branch> 2>/dev/null || true
git branch -d <branch> 2>/dev/null \
  || echo "Branch <branch> still has unique commits; verify PR merge status"
```

If `-d` still refuses and the PR is genuinely squash-merged, the override
(`CLAUDE_ALLOW_BRANCH_FORCE_DELETE=1`) for `-D` is single-shot. Use it
only after confirming the PR is merged.

**Remote cleanup:**

```bash
# Delete the remote branch (after the PR is merged on GitHub)
git push origin --delete <branch>     # denied by M7; use after confirming merge
# OR rely on GitHub's "Automatically delete head branches" repo setting (S1)
# OR delete via the GitHub UI / gh:
gh api -X DELETE /repos/:owner/:repo/git/refs/heads/<branch>
```

The S1 branch-protection setup (`/tcs-git-helpers:git-setup
--with-branch-protection`) sets `delete_branch_on_merge=true`, which makes
GitHub auto-delete the head branch after each squash-merge. Local cleanup
is still needed.

**Prune remote-tracking refs:**

```bash
git fetch --prune
# OR equivalent
git remote prune origin
```

This removes `refs/remotes/origin/<branch>` for any branch that no longer
exists on the remote. Non-destructive: only removes tracking refs, not
local branches or commits.

## Prevention

**Cleanup-by-default:**

1. **Run `/tcs-git-helpers:git-audit --cleanup` after every PR merge.** Or:
   the post-merge hook surfaces the candidate list automatically; act on it.
2. **Enable `delete_branch_on_merge=true`** on each repo (the S1 setup does
   this). Removes the remote-cleanup step entirely.
3. **Run `git fetch --prune` periodically** (e.g., as part of a daily start-
   of-work routine, or whenever the brief shows stale tracking refs).

**Don't preserve "just-in-case" merged branches.** Once a PR is merged, the
work is on the default branch. The local branch is redundant; if you ever
need to revisit it, the merge commit (or squash) on the default branch has
the full diff, and the PR on GitHub has the discussion.

**Don't keep dead-end branches indefinitely.** If you abandon a branch
without merging, either:

- Open a draft PR and explicitly close it (preserves the work in GitHub for
  future reference), or
- Document the abandonment in a file (architecture decisions, exploration
  notes) and let the local branch stay if reflog matters to you.

The accumulation pattern is the harm; one or two indefinitely-kept branches
are not a problem in themselves.

## Why

Stale branches are individually harmless and collectively a real problem.
The collective failure modes are:

- **Squash-merge resume (M3).** Claude reflexively does `git switch
  feat/old-thing` and adds new commits, then attempts a PR — and hits
  `mergeable: CONFLICTING` because the squash on default has different SHAs.
  Cleanup prevents this by removing the temptation entirely.
- **Status noise.** `git branch` shows 20 branches, only 3 of which are
  alive. The relevant signal (which branch is your current work?) is buried.
- **Brief degradation.** The SessionStart brief surfaces the count; a high
  count is a working signal that cleanup is overdue.

The post-merge hook fires after every `git pull` (which usually follows a
merge), so the stale-list is surfaced immediately after the moment when a
new branch became stale. The status skill's `--cleanup` mode is the
canonical batch-cleanup interface; the post-merge hook is the
"don't-let-it-pile-up" reminder.

References:

- PRD §Feature M6 (stale-branch surfacing post-merge), Feature M3 (squash-merge resume)
- PRD §Feature S1 (delete_branch_on_merge=true)
- SDD §Acceptance Criteria M6
- [squash-merge-trap.md](squash-merge-trap.md) (the failure mode cleanup prevents)
- [branch-lifecycle.md](branch-lifecycle.md) (cleanup is the final step)
