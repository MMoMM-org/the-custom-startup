# Worktree discipline

> When to use `git worktree`, the four-check exit guard, and how to recover
> work when an exit went sideways.

## What goes wrong

Exiting a Claude Code worktree session can silently destroy unfinished
work. A worktree shares the parent repo's `.git/` (refs, objects,
reflog) but has its own working tree, index, and `HEAD`. The exit path
removes the working tree directory and — if invoked via
`git worktree remove --force` — also the branch. Anything that lived
*only* in the worktree dies with the directory:

- Uncommitted changes in the working tree.
- Staged hunks in the worktree's index.
- Untracked files (notes, scratch scripts, downloaded fixtures).
- Local-only branches whose tip has not been pushed to a remote.
- Stashes — wait, no: stashes live in `.git/refs/stash` of the parent
  repo, not in the worktree, so `stash push` *before* exit survives.
  But `stash pop` inside the worktree restores changes that then die
  when the worktree dies.

The Claude-side trigger is `ExitWorktree` (a deferred tool surfaced via
`ToolSearch`). The session lifecycle for a worktree is bounded — the
session can also end involuntarily via `/clear`, compaction, or a
window close, in which case there is no exit hook at all and the
working tree state is whatever Claude last committed.

The worktree pattern is genuinely useful (parallel feature branches in
parallel sessions, no stash juggling). But it shifts the data-loss
window from "between sessions" to "at exit", which is at least
detectable with a hook. Without the four-check guard, it is silent.

## How to detect

**Active worktrees:**

```bash
git worktree list
# /Volumes/Moon/Coding/repo            abc1234 [main]
# /Volumes/Moon/Coding/repo-feat-foo   def5678 [feat/foo]
```

The first entry is the main checkout. Subsequent entries are
worktrees, each with its own path, current commit, and branch.

**State of a single worktree (run from inside the worktree directory):**

```bash
git status --porcelain               # uncommitted (modified) + untracked
git status --short --branch          # also shows ahead/behind vs upstream
git ls-files --others --exclude-standard   # untracked only
git rev-list --count @{u}..HEAD 2>/dev/null # unpushed commits (0 if no upstream)
```

The M8 worktree-exit guard (`worktree-exit-guard.sh`, PreToolUse:
ExitWorktree, ADR-1) checks four conditions before allowing exit:

1. **Uncommitted** — `git status --porcelain` non-empty.
2. **Untracked** — files in the worktree not in any `.gitignore`.
3. **Unmerged** — `git cherry "origin/$DEFAULT" "$BRANCH"` reports `+`
   lines (commits with patches not yet on default; see
   [`squash-merge-trap.md`](squash-merge-trap.md) for the cherry-pick
   semantics).
4. **Unpushed** — `git rev-list --count @{u}..HEAD` > 0, or no upstream
   set.

Any non-clean state denies the exit and cites this file.

## Fix

If you exited and lost data, recovery depends on which states were dirty
at exit and how the exit happened.

**Branch deleted, commits unreachable:**

```bash
# The reflog is your first stop — it survives branch deletion within
# the gc.reflogExpireUnreachable window (default 90 days for unreachable
# refs).
git reflog
# Spot the commit you want by message and SHA.
git checkout -b <branch>-recovered <sha>
```

**Branch tip is gone but commits are dangling:**

```bash
# fsck surfaces dangling commits and blobs that have no ref pointing
# at them.
git fsck --lost-found
# Output names dangling commits by SHA. Inspect each:
git show <sha>
# Recreate a branch from the one you want:
git checkout -b <branch>-recovered <sha>
```

**Untracked files in the deleted worktree:**

There is no recovery from git. Untracked files were never committed,
never staged, never in any reflog. If macOS Time Machine ran a backup
since they were created, the OS-level backup is the only path back.

**Stashes:**

Stashes live in `.git/refs/stash` of the parent repo (worktrees share
this). Exiting the worktree does not delete stashes. `git stash list`
from the parent repo (or any other worktree of the same repo) shows
them. Apply with `git stash apply stash@{N}` from a fresh working tree.

**Worktree dir was removed but branch survives:**

If the worktree was unregistered without `--force` and the branch still
exists, the easiest recovery is to just re-create the worktree:

```bash
git worktree add ../repo-feat-foo-resumed feat/foo
```

The branch's commits are intact in the parent repo's object store; only
the working-tree dir was lost.

## Prevention

- **Push before exit.** A worktree branch with an upstream and zero
  ahead-count is in zero data-loss territory regardless of exit path.
  The guard's "unpushed" check is the cheapest discipline.
- **Commit before exit, even WIP.** `git commit -m "wip: snapshot"` is
  a one-line save point. Reflog covers it for 30+ days; rewriting the
  commit later (squash, fixup, amend on the worktree branch only) costs
  nothing.
- **Never run `git worktree remove --force` reflexively.** The non-force
  form refuses to remove a worktree with uncommitted changes — that's
  the same safety the guard provides, at the git level. `--force`
  bypasses it.
- **Trust the guard.** If `ExitWorktree` denies, the four-check found
  something. Do not reach for the override; investigate the dirty state
  first. The override is a deliberate "I have just `git stash`'d / just
  pushed" signal, not a "make this dialog go away" button.
- **Do not stash inside a worktree about to be removed.** The stash
  *itself* survives (in the parent repo), but the act of `stash pop` in
  a fresh worktree to restore the changes assumes you remember which
  stash entry, which working tree it came from, and what the branch
  context was. Push the WIP commit instead — it carries that context
  intrinsically.

## Why

Boucle-framework's `worktree-guard` documented the exit data-loss
pattern after observing the same loss across multi-worktree workflows.
The plugin re-implements 1:1 (CON-5):

- Boucle `worktree-guard`:
  <https://github.com/Bande-a-Bonnot/Boucle-framework/blob/main/tools/worktree-guard>

ADR-1 chose `PreToolUse:ExitWorktree` (rather than `SessionEnd`) because
the former is *blockable* — `permissionDecision: deny` from a PreToolUse
hook stops the operation. `SessionEnd` is informational; by the time it
fires, the worktree is gone. The deferred-tool surface (`ExitWorktree`,
`EnterWorktree`) is documented in Claude Code's hook events reference.

The four checks are not negotiable. Each closes a different data-loss
path:

- Uncommitted closes the working-tree path.
- Untracked closes the "files Claude created but never staged" path.
- Unmerged closes the "branch carries content not yet on default" path
  — this is the same `git cherry` test used by the squash-merge trap
  detection.
- Unpushed closes the "remote has no copy" path.

Worktrees are the right tool when you genuinely need parallel working
trees (e.g., testing two branches against each other, or running a
long build on one branch while editing another). They are the wrong
tool when the goal is just "switch branches" — `git switch <branch>`
does that, with no exit hazard. The plugin does not deny worktree use;
it denies *unsafe exit*.

A note on involuntary exits (compaction, `/clear`, window close): the
guard does not fire in those cases. The mitigation is upstream of the
exit — push regularly, commit WIP. The session-start brief (M4) on the
next session reports the worktree state; if the brief shows
"unpushed=N, ahead=M" for a worktree, you know there is unsaved
context. See [`branch-lifecycle.md`](branch-lifecycle.md) for the
brief contents.

---

## See also

- [`branch-lifecycle.md`](branch-lifecycle.md) — the four "unfinished" states; same vocabulary.
- [`squash-merge-trap.md`](squash-merge-trap.md) — the `git cherry` semantics underlying the unmerged check.
- [`destructive-ops.md`](destructive-ops.md) — `git branch -D` and `worktree remove --force` are the destructive paths.
- [`best-practices.md`](best-practices.md) — §1 pre-flight branch state.
- Boucle `worktree-guard` upstream: <https://github.com/Bande-a-Bonnot/Boucle-framework/blob/main/tools/worktree-guard>
