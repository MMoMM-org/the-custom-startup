# Branch Lifecycle

The full life of a feature branch: **Create → Work → Push → PR → Merge → Cleanup**.
Most Claude-side mistakes (M2, M9) come from skipping or short-circuiting one of
these steps — typically branching off the default while a previous branch is
clean-but-unmerged, which silently orphans the prior work.

## What goes wrong

1. **Branch from unfinished work (M2 — most common failure).** The current branch
   is clean (no dirty tree) but has commits ahead of `origin/<default>` and no
   PR. Claude reflexively runs `git checkout -b feat/next` and the prior work
   becomes orphaned: no PR, no merge, just a local ref nobody is reviewing.
2. **Branch from a dirty tree.** Working tree has modified or untracked files.
   `git checkout -b` either carries the dirt across (confusing) or refuses
   (when files conflict), leaving the user in an unclear half-state.
3. **Long-lived feature branches drift.** A feature branch sits for days while
   the default branch advances. By the time a PR opens, the diff is huge and
   merge conflicts proliferate.
4. **The PR step gets skipped.** Claude commits and pushes directly, intending
   "I'll open the PR later". Later never arrives; the branch lingers; squash
   semantics never trigger.
5. **Cleanup never happens.** PR merges, branch stays both locally and on
   remote, contributing to the stale-branch problem covered in
   [stale-branch-cleanup.md](stale-branch-cleanup.md).

## How to detect

```bash
# Branches with commits not yet on default — candidates for orphaning
git branch --no-merged origin/$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|origin/||')

# Current branch state — ahead/behind counts
git status --short --branch

# Does the current branch have an open PR?
gh pr list --head "$(git branch --show-current)" --state open --json number,state

# Stale-merged candidates (PR closed, branch still here)
gh pr list --head "$(git branch --show-current)" --state merged --json number,state
```

The status skill automates this view:

```bash
/tcs-git-helpers:status            # full report
/tcs-git-helpers:status --brief    # one-line summary
```

The hook surface raises the same signal: the M2 denial reason names the
unfinished-state condition explicitly (working-tree dirty, current branch
ahead-of-default with no PR, or both — see EC2 cascading-denial pattern).

## Fix

All recovery procedures below are non-destructive. They preserve the prior
branch and any unpushed commits.

**If the previous branch is clean-but-unmerged and you want to keep it:**

```bash
# Stay on the previous branch and push it first
git push -u origin "$(git branch --show-current)"
gh pr create --fill        # or with explicit --title/--body
# Then return to default and branch off cleanly
git switch <default>       # main or master
git pull --ff-only
git switch -c feat/next-task
```

**If the previous branch was a dead-end you genuinely want to abandon:**

```bash
# Leave it where it is. Do NOT branch -D. The local branch is harmless
# and reflog still has its commits if you change your mind.
# Open a PR with [skip-ci]/draft and close it explicitly:
git push -u origin <abandoned-branch>
gh pr create --draft --title "wip(scope): <short subject>" --body "Abandoned; closing."
gh pr close <number> --comment "Abandoned in favor of <new-branch>"
```

**If you already created the new branch and the previous one is orphaned:**

```bash
git switch <orphan-branch>          # commits are still there locally
git push -u origin <orphan-branch>  # publish so it's visible
gh pr create --fill                 # then deal with it via PR review
git switch <new-branch>             # resume the work in flight
```

**If the working tree was dirty when you tried to branch:**

```bash
# Commit (preferred — even WIP commits are recoverable on feature branches)
git add -A && git commit -m "wip: <short subject>"
# OR stash with a descriptive message
git stash push -m "wip: <topic> $(date +%Y-%m-%d)"
# Then branch cleanly
git switch <default>
git pull --ff-only
git switch -c feat/next-task
# If you stashed, pop on the new branch when ready
git stash pop
```

See [working-tree-hygiene.md](working-tree-hygiene.md) for stash-vs-branch
trade-offs.

## Prevention

**Lifecycle discipline (one branch = one feature, one PR, one merge):**

1. **Create** from current default: `git switch main && git pull --ff-only && git switch -c feat/<topic>`
2. **Work** with small commits — squash-merge collapses them on the default
   branch anyway, so individual commit messages are scratch space (see
   [pr-vs-commit-messages.md](pr-vs-commit-messages.md))
3. **Push** early, even before the work is "done", so the branch is visible
4. **PR** as soon as the shape is clear (draft is fine); the PR title is the
   contract for the squash-merge commit message — see
   [conventional-commits.md](conventional-commits.md)
5. **Merge** via squash on GitHub (default for single-coder workflow)
6. **Cleanup** locally and on remote — see [stale-branch-cleanup.md](stale-branch-cleanup.md)

**Tooling:** running `/tcs-git-helpers:setup` installs the hooks that block
branch-from-unfinished-work (M2) and surface stale branches after each pull
(M6). Once installed, the most common slip — `git checkout -b` while a
previous branch is unmerged — is denied with a recovery citation.

**Branch naming** (from `~/Kouzou/standards/git-conventions.md`):

- `feat/<topic>` — new features
- `fix/<topic>` — bug fixes
- `refactor/<area>` — restructuring without behavior change
- `docs/<topic>` — documentation only
- `chore/<topic>` — tooling, dependencies, housekeeping

## Why

The branch-from-unfinished-work failure is **the most common Claude mistake**
documented in the brainstorm (PRD §Problem Statement). Claude has no
persistent session memory: when a task switches focus, "what branch am I on?"
and "is the previous task finished?" are not naturally re-evaluated. The
M2 hook makes the question machine-checked instead of memory-checked.

Branch-per-feature is also a precondition for the squash-merge model GitHub
defaults to: a clean 1-PR-1-feature mapping makes the squashed commit on the
default branch a meaningful unit of history. Skip the PR step and you lose
that mapping; reuse a branch after squash-merge and you hit the conflict
described in [squash-merge-trap.md](squash-merge-trap.md).

References:

- PRD §Feature M2 (block branch creation from unfinished work)
- PRD §Feature M9 (post-branch-create nudge cites this doc)
- SDD §Acceptance Criteria M2
- `~/Kouzou/standards/git-conventions.md` (branch naming)
