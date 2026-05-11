# tcs-git-helpers — Best Practices Overview

This is the landing page for the `tcs-git-helpers` references library. It
explains *why* the plugin exists and the principles every other reference doc
applies. For fast lookup of a specific failure mode, jump to
[INDEX.md](INDEX.md).

---

## Why this exists

Claude has no persistent memory across sessions. Marcus operates several
repos (TCS itself plus the MiYo ecosystem — Kado, Hakobi, Tomo, Kokoro,
Kouzou, Seigyo, Hashi) and has observed that the same handful of git
mistakes recur across sessions, no matter how clearly the rules are written
in `CLAUDE.md`. The agent is the failure source, not the operator.

The recurring mistakes are:

1. **Pushes to closed/merged PRs** — re-pushing to a PR that has already
   been squash-merged or closed. Pollutes the closed PR or causes a dirty
   re-open.
2. **New branches from main while the previous branch is unfinished** — the
   most common pattern. The current branch is *clean* (everything committed)
   but **not yet PR'd or merged**, and the agent reflexively branches off
   main again. The previous work sits orphaned forever.
3. **Resuming squash-merged branches** — the agent checks out a branch whose
   PR was squash-merged, makes more commits, opens a PR, and gets
   `mergeable: CONFLICTING`. See [squash-merge-trap.md](squash-merge-trap.md)
   for Marcus's original finding.
4. **Edits and commits on main** — even with `block-main-edits.sh` in user-
   global hooks, the agent keeps trying instead of pre-flighting branch
   state.
5. **Bad commit and PR messages** — no Conventional Commits enforcement
   means the squash-merge commit on main is whatever the PR title happens
   to be.
6. **Stale local branches** — branches whose PRs were merged accumulate
   silently. (At the time of writing, Kado has six.)
7. **Reflexive destructive operations** — `reset --hard`, `clean -f`,
   `branch -D`, `stash drop`, `reflog expire`, `--no-verify`, and so on.
   Often invoked to "fix" a state that should have been investigated first.
8. **Worktree-exit data loss** — exiting a worktree session with uncommitted
   or unpushed work silently destroys it.

`CLAUDE.md` instructions are read at session start but cannot stop the
agent at the moment of error. Hooks can. This plugin closes the loop with
machine-enforced denials, granular single-shot overrides, and these
reference docs cited from the denial messages themselves.

---

## Core principles

The plugin follows four principles. Every reference doc is an application
of one or more of them.

### 1. Pre-flight branch state, every time

Before any branch-creating, commit-making, or push operation, the agent must
know the answers to:

- What branch am I on, and is it protected?
- Is the working tree clean?
- Does the current branch have a PR? What state is the PR in?
- Is the current branch ahead of `origin/<default>` with commits that have
  not yet been merged or PR'd?
- Has any branch been squash-merged but is still checked out locally?

The plugin surfaces these answers at every entry point: the SessionStart
brief (M4), the post-merge re-emit (M4), and the PreToolUse denial reasons
(M1, M2, M3). The agent does not need to remember to run `git status`. The
plugin runs the equivalent before the operation can proceed.

See [branch-lifecycle.md](branch-lifecycle.md) for the canonical lifecycle
states and [stale-branch-cleanup.md](stale-branch-cleanup.md) for the
cleanup half.

### 2. Defense in depth — plugin and `.githooks/` enforce the same rules

The Claude-side hooks (in `${CLAUDE_PLUGIN_ROOT}/scripts/`) fire only when
the plugin is enabled. That is intentional coupling: disabling the plugin is
a conscious decision to waive Claude-side protection.

But disabling the plugin must not strip protection from `git` itself. The
per-repo `.githooks/` layer (installed via `core.hooksPath`) catches the
same operations from any caller — Claude, Marcus's terminal, Docker
containers, CI runners. If the plugin is disabled, the agent can no longer
issue a denial reason, but `.githooks/pre-push` will still exit non-zero on
a push to a closed PR.

The two layers carry version markers (`# tcs-git-helpers: vX.Y.Z`) so the
setup skill can detect drift on `--update`.

See [migrating-from-husky.md](migrating-from-husky.md) for the prerequisite
(no other hook tooling) and [sandbox-and-git-config.md](sandbox-and-git-config.md)
for why `git -c core.hooksPath=…` is itself a denied pattern (it is the
trivial bypass).

### 3. Non-destructive recovery only

Every reference's *Fix* section presents a recovery path that does **not**
require a destructive operation. The plugin specifically denies the most
common reflexive responses:

- `git reset --hard` — destroys working tree and index
- `git checkout .` / `git checkout -- <path>` — discards working changes silently
- `git clean -f` / `git clean -fx` — deletes untracked files
- `git branch -D` — force-deletes; reflog recovery only
- `git stash drop` / `git stash clear` — destroys stash entries
- `git reflog expire` — kills the recovery net itself
- `git push --force` (without `--force-with-lease`) — overwrites remote unconditionally

If a reference suggests `git reset --hard`, that is a bug. The recovery
should always be: stash, branch, cherry-pick, revert, or
`--force-with-lease` to a non-protected branch. See
[destructive-ops.md](destructive-ops.md) for the full pattern set and
[force-push-safety.md](force-push-safety.md) for the lease-form distinction.

### 4. Granular overrides with audit, not master overrides

Every safety rule has a single-shot env-var override (`CLAUDE_ALLOW_<OP>=1`).
The override is consumed by the first matching invocation and cleared.
Subsequent operations re-deny unless the override is re-set. There is also
a master override (`CLAUDE_ALLOW_GIT_BAD_OPS=1`), but it is a tripwire — it
emits a loud stderr warning recommending the granular form on every use.

Every override consumption is appended to
`${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` with branch, repo, hook,
env-var, and the original command. Marcus reviews this log via
`/tcs-git-helpers:git-audit --overrides`. The audit is the discipline layer:
overrides are allowed, but not invisible.

If you find yourself reaching for the master override or for the same
granular override repeatedly, the lesson is in the reference doc, not in
the override.

---

## When to consult which reference

A prose router. If you got here from a denial message, the citation in the
message is the canonical entry point — start there. If you arrived from
INDEX.md or from a teammate's mention, the following narrative may help.

**You tried to push and got "PR is CLOSED" or "PR is MERGED."** This is
almost always the squash-merge trap. The squash on main is a single new
commit; your local branch's commits are no longer on main even though
their content is. Read [squash-merge-trap.md](squash-merge-trap.md) and
either cherry-pick onto a fresh branch (to keep going) or
`git checkout main && git branch -D <merged-branch> && git pull` (to abandon).
Note the destructive `branch -D` is the only acceptable use of that
operation — the work is already on main under a different SHA.

**You tried to branch off main and got "current branch unfinished."** Your
current branch has commits ahead of `origin/<default>` and no PR. Either
finish it (open a PR) or explicitly stash it (the override env-var is the
"explicit" form). Read [branch-lifecycle.md](branch-lifecycle.md) and
[working-tree-hygiene.md](working-tree-hygiene.md).

**You tried to check out a branch and got "branch was squash-merged."**
Same root cause as the push case — the branch's PR squash-merged, so the
patches are on main under different SHAs. `git cherry origin/<default> <branch>`
returned all `-` lines, which is the unambiguous detection. The fix is the
same as case 1.

**A `commit-msg` hook rejected your message.** You did not match the
Conventional Commits allowlist. Read
[conventional-commits.md](conventional-commits.md) for the format and
[pr-vs-commit-messages.md](pr-vs-commit-messages.md) for the squash-merge
implication (PR title becomes the commit on default — keep them aligned).

**You ran a destructive command and got denied.** Read
[destructive-ops.md](destructive-ops.md) for the granular override and the
non-destructive recovery. Do not reach for `CLAUDE_ALLOW_GIT_BAD_OPS=1` —
the master override emits an audit-loud warning and recommends the
specific form.

**ExitWorktree denied your exit.** The four-check (uncommitted, untracked,
unmerged, unpushed) found something. Read
[worktree-discipline.md](worktree-discipline.md) — the answer is almost
always to push or commit first. Stashing in a worktree about to be removed
is a data-loss path; the stash lives in the repo's `.git/refs/stash`, not in
the worktree.

**Setup refused to install because Husky / lefthook / pre-commit /
simple-git-hooks already exists.** This is to prevent silent coexistence
where two tools fight over `core.hooksPath`. Read
[migrating-from-husky.md](migrating-from-husky.md) for the per-tool
removal sequence.

**Setup warned about excessive `gh` token scopes.** You probably ran
`gh auth login` in admin mode at some point. Read
[gh-token-hygiene.md](gh-token-hygiene.md) for the minimum-scope
recommendation and the `gh auth refresh -s repo` recovery.

**You ran `git -c core.hooksPath=…` or tried to set `core.hooksPath` from
the command line and got denied.** That is the canonical bypass; the
plugin denies it. Read
[sandbox-and-git-config.md](sandbox-and-git-config.md) for the rationale.

For everything else, the [INDEX.md](INDEX.md) router is the fastest route
to the matching reference.

---

## A note on tone

These references are written for Claude (the agent) first, Marcus second.
The agent reads them in the middle of a denied operation, often without
larger session context. Each reference is structured to answer four
questions in order:

1. What was I trying to do that got denied?
2. What did the plugin observe that triggered the denial?
3. What is the non-destructive way forward?
4. How do I avoid hitting this denial next time?

The fifth section (*Why*) exists so the agent can judge edge cases instead
of blindly following the prevention rule. References to upstream sources
(Boucle-framework, Conventional Commits, GitHub branch protection docs)
live in the *Why* section.
