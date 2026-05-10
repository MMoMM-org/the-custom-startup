# Force-Push Safety

`git push --force` is the canonical "I lost work because Claude ran a single
command" failure. The safer form is `--force-with-lease`. Even safer: don't
force-push at all on a shared or protected branch. The M7 hook denies bare
`--force` and the S1 branch-protection preset denies force-push to default
entirely.

## What goes wrong

1. **`git push --force` overwrites remote history blindly.** Any commits the
   remote had that you didn't have locally are gone from the remote. If a
   teammate pushed to the same branch in the meantime, their work is silently
   discarded. CI/CD pipelines that ran on the discarded SHAs become
   detached from any reachable commit.
2. **`--force` on a protected branch.** GitHub rejects with
   `protected branch hook declined`. The local rebase that motivated the
   force-push remains, but the remote is unchanged. (This is a denial-of-loss,
   not a denial-of-service — the hook is doing its job.)
3. **`--force-with-lease` without scoping.** The lease form refuses to
   overwrite if the remote has commits you haven't seen. But: a `git fetch`
   between rebase and push silently advances your view of the remote, so the
   lease no longer guards against the very race it was added to prevent.
4. **Force-push to a shared feature branch.** Even if the branch is not
   protected, force-pushing a branch teammates have checked out leaves them
   with parallel histories on next `git pull`.

## How to detect

```bash
# Did your local history just rewrite SHAs? reflog has the trail.
git reflog show <branch> -20

# Did the remote have commits you no longer have? Compare reflog vs current
# tip; or before pushing, fetch and inspect the divergence
git fetch origin
git log --oneline --left-right --graph "@{u}...HEAD" | head -20

# Was a force-push attempted and denied? look for the hook's denial reason
# in stderr; or check the M7 audit log
cat "${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl" | grep force-push
```

The M7 destructive-ops hook denies bare `--force` (without `--force-with-lease`)
and emits a denial citing this reference doc. Server-side, branch protection
rejects all force-pushes (with or without lease) to protected branches.

## Fix

All recoveries below are non-destructive. They restore the lost SHAs from
local reflog or via teammate cooperation; they never use `--force` to "fix"
a previous force-push.

**You force-pushed locally, want to recover the discarded commits:**

```bash
# Reflog still has the pre-force-push tip — use it as a recovery anchor
git reflog show <branch>
# Find the SHA before the force-push (e.g. <branch>@{2}); inspect it
git log --oneline <branch>@{2} -10
# Cherry-pick the commits onto a new branch (preferred, non-destructive)
git switch -c rescue/<topic>
git cherry-pick <old-sha-1>..<old-sha-N>
```

**A teammate force-pushed and you have the old SHAs locally:**

```bash
# Your local branch still has the pre-force-push tip; the remote is rewritten
git fetch origin
git log --oneline --left-right --graph "@{u}...HEAD" | head -20
# Cherry-pick anything you had that the remote no longer carries onto a new
# branch and open a PR to merge it back
git switch -c rescue/<topic>
git cherry-pick <local-only-sha-1>..<local-only-sha-N>
git push -u origin rescue/<topic>
gh pr create --fill
```

**A teammate force-pushed and you don't have the old SHAs:**

Ask the teammate to recover from their reflog (above) and re-push under a
recovery branch. Their reflog is local-only — you cannot retrieve the
discarded commits without their help.

**You attempted `--force` and the M7 hook denied it:**

Reconsider the goal:

- **"I want my local rebase published"** — use `git push --force-with-lease`
  (allowed by the hook for non-protected branches; denied on protected ones
  by the server).
- **"I want to drop a commit from the branch"** — use `git revert <sha>` (a
  new commit that undoes the change) instead of rewriting history.
- **"The remote has bad merges"** — open a PR with the corrective commits;
  merge or revert through the normal review path.

```bash
# Preferred: lease form, allowed by the hook
git push --force-with-lease

# Even safer: lease scoped to the SHA you expect upstream to be at
git push --force-with-lease="<branch>:<expected-remote-sha>"
```

## Prevention

**Never use bare `--force`.** The M7 hook denies it; the override is
single-shot and audit-logged (`CLAUDE_ALLOW_FORCE_PUSH=1`). Use
`--force-with-lease` instead.

**`--force-with-lease` semantics** — a compare-and-swap:

- Reads the remote's current SHA for the branch.
- Compares against your local "what I last saw the remote at".
- Pushes only if they match. Otherwise refuses with
  `stale info` and you re-fetch + re-evaluate before retry.

This protects against the canonical "teammate pushed while I was rebasing"
race. It does **not** protect against:

- A `git fetch` between your rebase and your push (lease updates silently —
  use `--force-with-lease=<branch>:<expected-sha>` for explicit scoping).
- Force-pushing to a branch a teammate has checked out (their next `git
  pull` will produce parallel histories — communicate first).

**Do not force-push (any form) to a shared branch.** Communicate first;
prefer a new branch + new PR over rewriting an in-flight branch.

**Branch protection (Feature S1)** sets `allow_force_pushes=false` on the
default branch. Even with the lease form, GitHub rejects. This is
intentional: the default branch is the project's shared history.

**The M7 hook denies all of these by default** unless the corresponding
single-shot override is set:

```text
git push --force                  → denied (CLAUDE_ALLOW_FORCE_PUSH=1)
git push -f                       → denied (same; --force shorthand)
git push --force-with-lease       → ALLOWED (lease form is the safe default)
git push origin :<branch>         → denied (CLAUDE_ALLOW_FORCE_PUSH=1; delete via push)
git push --delete origin <branch> → denied (CLAUDE_ALLOW_FORCE_PUSH=1)
```

## Why

`--force` is the most-cited cause of remote work-loss in shared repos because
it conflates two operations: "publish my local history" and "discard whatever
the remote currently has". On a single-coder repo (the MiYo and TCS norm),
the work-loss usually happens to **your own** prior commits — the rebase
discarded a commit you wanted to keep, and force-push made the remote forget
it too.

`--force-with-lease` was added in git 1.8.5 (2013) precisely as the
"compare-and-swap" version of force-push: refuse if the remote moved.
Force-with-lease has the same intent ("publish my rewritten history") with
guarded semantics. The M7 hook treats them differently: the lease form is
allowed; the bare form requires explicit override.

Branch protection (`allow_force_pushes=false`) is the server-side belt to the
client-side suspenders. The M7 hook can be overridden; the GitHub setting
cannot (for non-admin users; admins can bypass with `enforce_admins=false`,
which is the S1 default to retain Marcus's emergency hatch).

References:

- PRD §Feature M7 (destructive-ops hook denies bare `--force`)
- PRD §Feature S1 (branch protection sets `allow_force_pushes=false`)
- SDD §Acceptance Criteria M7
- [rebase-vs-merge.md](rebase-vs-merge.md) (rebasing pre-push is the common
  trigger for force-push)
