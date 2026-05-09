# Rebase vs Merge

Both integrate one branch's history into another, but they produce
different results: rebase rewrites SHAs to make a linear story; merge
preserves both histories and adds a merge commit. tcs-git-helpers does not
mandate either policy, but it does make safe use of both possible.

## What goes wrong

1. **Rebasing a shared branch.** You rebase `feat/foo` onto `main`, the SHAs
   change, you push. Anyone else who had `feat/foo` checked out now has a
   different (parallel) history; their next `git pull` produces a confusing
   merge commit or a conflict where there should be none.
2. **Merging when rebase was wanted.** A long-lived feature branch
   periodically merges from `main` to "stay current". The result is a series
   of merge commits cluttering the branch history; the eventual PR diff
   includes a tangle of mainline commits interleaved with feature commits.
3. **Mixing strategies inconsistently.** Some PRs rebased, others merged,
   others squash-merged — `git log --graph` becomes unreadable and `git
   bisect` paths become unpredictable.
4. **Rebase conflict resolved incorrectly.** Each commit in the rebase
   replays separately; resolving conflicts at one commit can hide the
   resolution at another. The final tip can compile and pass tests while
   intermediate commits do not, breaking `git bisect`.

## How to detect

```bash
# Visualize history shape — linear or branching?
git log --graph --all --oneline -30

# Rebased branches show no merge commits inside the branch range; merged
# branches show one or more "Merge branch …" commits

# Did you just rebase? Reflog has the trail
git reflog show HEAD -10 | grep -E 'rebase|cherry-pick'

# Is your branch's history ahead of where you expected? Compare with upstream
git log --oneline --left-right --graph "@{u}...HEAD" | head -20

# Detect a stuck rebase
ls .git/rebase-merge .git/rebase-apply 2>/dev/null && echo "rebase in progress"
```

The post-rebase nudge (Feature M9) reminds Claude after `git rebase`
completes to verify the resulting history with `git log --oneline -10` and
cites this doc.

## Fix

All recoveries below are non-destructive. They preserve the pre-rebase
history via the reflog or local-only branch backups; they never use
`--force` to "fix" a bad rebase.

**Rebase produced a broken or undesired history:**

```bash
# Reflog has the pre-rebase tip; inspect and reset back via --keep
git reflog show HEAD -20
# Find the entry just before "rebase started" — typically HEAD@{N}
# --keep refuses if doing so would discard local changes; safer than --hard
git reset --keep HEAD@{<N>}
```

`git reset --keep` is the non-destructive sibling of `git reset --hard`. It
is allowed (the M7 hook denies `--hard` only; `--keep` is fine).

**Mid-rebase conflict, want to bail:**

```bash
git rebase --abort   # returns to the pre-rebase tip; non-destructive
```

**Mid-rebase conflict, want to skip a problematic commit:**

```bash
git rebase --skip    # drops the current replayed commit; verify result with reflog
```

**You rebased a shared branch and a teammate has the old SHAs:**

You cannot un-rebase remotely without force-pushing to undo your push (which
re-introduces the same shared-branch problem). Instead:

```bash
# Communicate first. Then have the teammate recover via:
git fetch origin
git switch <branch>
git pull --rebase    # replays their local commits onto the new remote tip
```

If the teammate has uncommitted work, they should stash, then `pull --rebase`,
then `stash pop`.

**Wrong strategy already used (e.g., merge commits clutter a branch):**

Don't rewrite. Accept the history as-is and adjust the strategy going
forward. If the merge commits are visually annoying but functionally
correct, leave them. If the resulting default-branch commit is the squash
of the PR (squash-merge repo), the per-branch shape doesn't matter.

## Prevention

**Choose strategies by purpose, not by aesthetic:**

| Situation | Strategy | Why |
|---|---|---|
| Bring `main` into your local feature branch before first push | `git rebase main` | Linear history, single PR diff |
| Bring `main` into a feature branch teammates have pulled | `git merge main` | Don't rewrite shared history |
| Integrate a finished feature into `main` | squash-merge (UI) | Single commit per feature on default |
| Multi-commit feature where each commit matters historically | merge-commit (UI) | Preserves per-commit messages on default |
| Hot-fix replay across release branches | `git cherry-pick` | Surgical, non-destructive |

**Rules of thumb:**

- **Rebase your own local branch onto current default before the first push.**
  This is the safe rebase: nobody else has the old SHAs.
- **Never rebase a branch others have pulled.** Communicate, merge, or use a
  recovery branch instead.
- **Never rebase the default branch.** It is shared by definition.
- **Squash-merge implies the PR title is the commit-message contract** — see
  [pr-vs-commit-messages.md](pr-vs-commit-messages.md).
- **Verify after every rebase.** Run `git log --oneline -10` to confirm the
  shape and `git status` to confirm a clean tree. The M9 nudge prompts this.

**Bisect-safety for rebases:** when rebasing a branch you intend to bisect,
verify each replayed commit compiles and tests pass. The interactive `exec`
form runs a command after each commit:

```bash
git rebase -i main --exec "make test"   # fails the rebase if any commit breaks tests
```

If a commit in the middle of the rebase breaks the build, the rebase pauses;
fix and `git rebase --continue` (preferred) or `git rebase --abort` if the
fix is non-trivial.

## Why

The rebase-vs-merge debate is genuinely a project policy choice; both
produce correct history. The danger isn't the strategy — it's mixing them
inconsistently or applying them on shared branches.

For TCS and the MiYo ecosystem, the convention is:

- **Default branch:** squash-merge from PRs (single commit per feature).
- **Feature branches:** rebase-onto-default before first push for linear
  per-PR history; never rebase after the branch has been pulled by another
  session/contributor.
- **Recovery branches:** cherry-pick, never rebase (cherry-pick is
  intentional, surgical, and reflog-friendly).

The M9 post-rebase nudge exists because rebases are the most common source
of "I rewrote history and now I can't push" surprises. Verifying with `git
log --oneline -10` immediately after the rebase catches most of them before
they become force-push pressure (see
[force-push-safety.md](force-push-safety.md)).

References:

- PRD §Feature M9 (post-rebase nudge cites this doc)
- SDD §Acceptance Criteria M9 (post-rebase verification)
- [force-push-safety.md](force-push-safety.md) (the common rebase fallout)
- [pr-vs-commit-messages.md](pr-vs-commit-messages.md) (squash-merge implication)
