# Working-Tree Hygiene

A clean working tree is the contract for safe branch operations. Most
"branch from unfinished work" denials (M2) and stash-pop nudges (M9) trace
back to the working tree being in a state Claude didn't pre-flight.

## What goes wrong

1. **New branch from a dirty tree.** `git switch -c feat/next` while the
   tree has modified or untracked files. Either the changes are carried
   into the new branch (confusing — they belong to the old context) or
   `switch` refuses (when files conflict with the target branch). Either
   way, the user is in a half-state.
2. **`git stash pop` leaves `.orig` files behind.** A stash with conflicts
   produces `<file>.orig` markers next to each conflicted file. They are
   ignored by `.gitignore` defaults but show up in subsequent `git status`
   as untracked files.
3. **Switching branches with uncommitted work.** `git switch <branch>`
   carries uncommitted changes across branches when they don't conflict.
   This is git's documented behavior, but it surprises Claude (who expects
   branches to be isolated states).
4. **Stash drop loses irrecoverable WIP.** `git stash drop` is denied by
   the M7 hook because dropped stashes are gone — they don't go to reflog;
   they go to nowhere.
5. **`git checkout .` / `git checkout -- <path>` discards work without
   confirmation.** Both forms are denied by the M7 hook for this reason.

## How to detect

```bash
# Are there any modifications or untracked files?
git status --short

# Detail of changes (non-destructive, read-only)
git diff --stat
git diff --stat --cached    # staged changes

# After a stash pop with conflicts, look for .orig files
find . -name '*.orig' -not -path './.git/*'

# What stashes exist? (git stash drop is denied; this is the audit view)
git stash list

# Worktree state — branches checked out elsewhere
git worktree list
```

The post-stash-pop nudge (Feature M9) reminds Claude to verify `.orig`
cleanup and cites this doc. The M2 denial reason for branch-from-dirty-tree
names the modified-or-untracked condition explicitly.

The SessionStart brief includes the dirty-tree marker:

```text
[tcs-git-helpers] feat/foo • dirty (3 modified, 1 untracked) • 2 ahead • 0 stale-merged
⚠ tree dirty — commit, stash, or restore before branching
```

## Fix

All recovery procedures preserve the work; none discard it silently.

**Want to keep the work on the current branch:**

```bash
# Commit (preferred — even WIP commits are recoverable on feature branches;
# squash-merge will collapse them on the default branch anyway)
git add -A
git commit -m "wip(scope): <short subject>"
```

WIP commits are not a sin. On a squash-merge repo, they vanish from the
default branch's history at merge time. On the feature branch, they give you
reflog-navigable checkpoints.

**Want to set the work aside without committing:**

```bash
# Stash with a descriptive message (NOT just "git stash" — the auto-message
# is uninformative and stashes accumulate without context)
git stash push -m "wip: <topic> $(date +%Y-%m-%d)"

# Verify the stash exists
git stash list

# When ready to resume:
git stash pop                # applies + removes the stash entry
# OR keep the stash safe and just preview it:
git stash show -p stash@{0}  # read-only diff
git stash apply stash@{0}    # applies but keeps the stash entry
```

Stash entries are individually addressable (`stash@{0}`, `stash@{1}`, etc.).
Use `stash list` and `stash show` liberally; they are read-only.

**Stash conflict produced `.orig` files:**

```bash
# Identify
find . -name '*.orig' -not -path './.git/*'

# Resolve the conflicts in the actual files first (the .orig is just a backup)
# Once the conflicts are resolved and committed, delete the .orig files:
find . -name '*.orig' -not -path './.git/*' -delete
```

Deleting `.orig` files is non-destructive — they are backups created by the
merge; removing them does not affect the merged result.

**Discard a single file's uncommitted changes (unwanted edit):**

```bash
# git restore operates on individual files and is non-destructive at the
# repo level (it only changes the named files). Prefer over git checkout .
git restore <path>          # restore from index (most common)
git restore --staged <path> # un-stage but keep working-tree changes
```

`git restore <path>` is allowed; `git checkout .` and `git checkout -- <path>`
are denied by the M7 hook because their broad form is too easy to mis-target.

**Switch branches without losing the changes:**

```bash
# Carry the dirty changes (git's default — works only when there are no conflicts)
git switch <branch>

# OR safer: stash first, switch, pop on the new branch
git stash push -m "wip: $(git branch --show-current) → <branch>"
git switch <branch>
git stash pop
```

## Prevention

**Pre-flight before each branch operation:**

```bash
git status --short             # zero output = clean
git status --short --branch    # zero output below the branch line = clean
```

If output is non-empty, choose one before proceeding:

1. **Commit** — even WIP, on a feature branch, is fine.
2. **Stash with message** — `git stash push -m "..."`.
3. **Restore individual files** — `git restore <path>` if you genuinely
   want to discard that one edit.

**Never use `git stash drop` or `git stash clear`.** Both are denied by the
M7 hook because dropped stashes are unrecoverable. If you have stale
stashes, use `git stash list` to audit and `git stash apply stash@{N}` +
review before deciding any are safe to discard.

**Never use `git checkout .` or `git checkout -- <path>`.** Both are denied
by the M7 hook. Use `git restore <path>` (more explicit, less prone to
mis-target).

**Never use `git clean -f` or `git reset --hard` to "tidy up".** Both are
denied by the M7 hook. Untracked files belong to the user's intent until
proven otherwise.

**The hooks pre-flight for you.** The pre-edit-branch-check hook (Feature
M2) denies `git switch -c` and `git checkout -b` when the working tree is
dirty AND the base branch is wrong. The combination of "dirty tree" and
"creating new branch" is the canonical Claude reflex; the hook turns it
into a reflex-resistant decision point.

## Why

Working-tree state is the implicit input to nearly every git operation.
`git switch`, `git checkout`, `git pull`, `git merge`, `git rebase`,
`git cherry-pick` all behave differently with a clean tree vs a dirty one,
and most of them silently carry uncommitted changes across operations
where doing so is surprising.

The "always commit, even WIP" recommendation runs counter to a common
instinct ("commits should be meaningful"), but on squash-merge repos the
per-commit messages don't survive merge anyway — so on a feature branch,
WIP commits are free reflog-navigable checkpoints with no downstream cost.

The M9 stash-pop nudge exists because Marcus has been bitten by `.orig`
files leaking past merges and showing up in subsequent commits. Verifying
post-pop is cheap (one find command); leaving them in is corrosive over
time.

The M7 hook denies `stash drop`, `stash clear`, `checkout .`, `checkout --
<path>`, `clean -f`, and `reset --hard` because each of them is a single
command that can lose work irrecoverably. None of them have non-destructive
sibling forms that the hook would block, so the override (single-shot, env-
var) is the only path to use them — and that path is audit-logged.

References:

- PRD §Feature M2 (branch from dirty tree denied)
- PRD §Feature M7 (destructive ops on working tree denied)
- PRD §Feature M9 (post-stash-pop nudge cites this doc)
- SDD §Acceptance Criteria M2, M7, M9
- [branch-lifecycle.md](branch-lifecycle.md) (clean tree is precondition for branching)
