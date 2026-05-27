# Destructive operations

> Why `reset --hard`, `clean -f`, `branch -D`, `stash drop`, `reflog expire`,
> `checkout .` and friends are denied — and what to do instead.

## What goes wrong

Reflexive use of destructive git operations silently destroys work that was
never meant to be lost. The pattern is consistent across sessions: an agent
sees an unexpected file, an apparently-stuck merge, or a noisy working tree,
and reaches for the operation that "cleans things up" — without first
asking whether the noise is actually data.

The full set of operations the plugin denies, with the loss they cause:

- `git reset --hard [<ref>]` — discards working-tree changes **and** the
  index. If the index had staged hunks not yet committed, they are gone.
  The reflog still has the previous HEAD, but staged-but-uncommitted hunks
  do **not** appear in the reflog.
- `git checkout .` / `git checkout -- <path>` — overwrites the working tree
  for the listed paths from the index. No reflog. No backup. Modern git
  prefers `git restore`, but this form is still common in muscle memory.
- `git restore --staged <path>` / `git restore --worktree --source=<ref> <path>`
  — the modern equivalents of the above. Same data-loss profile, denied
  for the same reason.
- `git clean -f` / `-fd` / `-fx` / `-fdx` — deletes untracked files. The
  `-x` form also deletes ignored files (often `.env`, build caches, local
  notes, downloaded fixtures). No git history of any of it; once gone,
  gone.
- `git branch -D <branch>` — force-deletes a branch even if it has unmerged
  commits. The branch *ref* is gone immediately; only the reflog (30-day
  default expiry) remains.
- `git stash drop` / `git stash drop stash@{N}` / `git stash clear` — the
  stash refs are removed. Stashes do not appear in the regular reflog
  after they are dropped (they live in `refs/stash`'s own log, but
  `stash clear` truncates that too).
- `git reflog expire --expire=now` / `git reflog expire --all` — kills the
  recovery net itself. After this, none of the above operations have a
  way back.
- `git push --force` (without `--force-with-lease`) — overwrites remote
  refs unconditionally; if a teammate (or the agent's other session) had
  pushed in between, those commits are gone from the remote.
- `git commit --no-verify` / `git commit -n` — skips the `pre-commit` and
  `commit-msg` hooks. The commit lands without the format and content
  checks the repo configured.
- `git push origin --delete <branch>` / `git push origin :<branch>` —
  remote branch deletion. The branch ref on the remote is gone; if the
  branch was the only ref pointing at a chain of commits, those commits
  become unreachable on the remote and will be GC'd within ~30 days.
- `gh api repos/OWNER/REPO/git/refs/heads/BRANCH -X DELETE` —
  remote ref deletion via the GitHub REST API. Bypasses git push entirely
  (no pre-push hooks, no `--force-with-lease` safety) and leaves no local
  reflog trace. Both `-X DELETE` and `--method DELETE` forms are caught,
  in any argument order. Tag refs (`git/refs/tags/`) are caught too.

The trap is that each of these has *one* legitimate use case (a `reset
--hard` to recover from your own reflog after a known-good checkpoint;
`branch -D` of a squash-merged branch; `--force-with-lease` to a feature
branch you own). The plugin does not deny the legitimate cases — it
denies the *reflexive* cases. The granular override lets you proceed when
you've thought about it.

## How to detect

The Claude-side hook (`block-bad-git-ops.sh`, M7) matches the full command
string against POSIX ERE patterns (one rule per operation). When a pattern
matches, the hook emits a `permissionDecision: deny` JSON response with a
denial reason citing this file and the granular override env var.

Patterns are documented in
`plugins/tcs-git-helpers/tests/fixtures/commands/destructive_corpus.txt`.
The corpus is the source of truth — every rule has positive (deny) and
negative (allow) test cases.

To audit historical override usage:

```bash
/tcs-git-helpers:git-audit --overrides
```

The skill reads `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` and prints
one line per consumption event. Each line records `{timestamp, var,
command, cwd, branch}` (per ADR-7). Marcus reviews this monthly.

To detect post-fact whether a destructive op already ran in this session,
look at the operation's recovery surface:

```bash
git reflog                    # the previous HEAD before reset --hard
git fsck --lost-found         # dangling commits / blobs after branch -D, stash drop
git stash list                # before stash drop is observed gone
```

The reflog window is 30 days for reachable refs and 90 days for unreachable
(default `gc.reflogExpire` and `gc.reflogExpireUnreachable`). After that,
`git gc` removes them. Untracked files deleted by `git clean -f` are not
in any reflog and are not recoverable from git.

## Fix

Every destructive op has a non-destructive alternative for the case that
motivated reaching for it. Use the alternative; if it doesn't fit, that is
the signal to think rather than to override.

**Instead of `git reset --hard <ref>`:**

```bash
# Discard one path's changes
git restore <path>
# Or, with the modern split form:
git restore --source=<ref> --worktree <path>

# Stash the entire working tree (recoverable)
git stash push -u -m "snapshot before reset"

# Or commit-then-revert (fully recoverable, fully auditable)
git add -A && git commit -m "wip: snapshot"
# … then revert by checking out the previous commit:
git checkout <previous-sha>
```

**Instead of `git checkout .` / `git checkout -- <path>`:**

```bash
git restore <path>           # per-file
git restore .                # whole working tree
```

`git restore` without `--staged` and without `--source` is denied too if
it covers the whole tree — see the corpus. The non-destructive form is
to scope it to a path you actually intend to discard.

**Instead of `git clean -f`:**

```bash
git clean -n                 # dry-run: list what would be deleted
git clean -nd                # dry-run including untracked dirs
git clean -ndx               # dry-run including ignored files
```

Then for each file the dry-run lists, decide: keep (add to `.gitignore`
or commit it) or delete with `rm` after confirming it's not data.

**Instead of `git branch -D <branch>`:**

```bash
git branch -d <branch>       # refuses if unmerged; the safe form
```

If `-d` refuses, the branch has unmerged commits. Either merge them
(open a PR), cherry-pick them onto a fresh branch, or push the branch
to the remote so it has a backup before deletion.

**Instead of `git stash drop`:**

The stash list is append-only and weighs essentially nothing. Leave the
stash. If you need to free name space, `git stash list` and identify
specific entries to apply (`git stash apply stash@{N}`). Stashes you
don't apply do not affect anything.

**Instead of `git reflog expire`:**

There is no legitimate reflexive use. The reflog is the recovery net for
all the operations above. `git gc --auto` already handles routine
cleanup within `gc.reflogExpire` and `gc.reflogExpireUnreachable`
windows. Manual expire is for a privacy-driven rewrite of history (e.g.
removing a credential committed by mistake), and is the *last* step
after a force-push to a freshly-rewritten branch — never the first.

**Instead of `git push --force`:**

```bash
git push --force-with-lease                # default form
git push --force-with-lease=<branch>:<sha> # belt-and-braces
```

`--force-with-lease` refuses to push if the remote moved since your last
fetch. See [`force-push-safety.md`](force-push-safety.md) for the
distinction and the protected-branch denial that fires regardless of
lease form.

**Instead of `git commit --no-verify`:**

Fix what the hook is complaining about. If `commit-msg` rejected the
format, see [`conventional-commits.md`](conventional-commits.md). If
`pre-commit` rejected staged content, the hook's own stderr explains
which check failed.

**Instead of `git push origin --delete <branch>` / `:<branch>`:**

After a PR merges, GitHub auto-deletes the head branch if the repo has
"automatically delete head branches" enabled (see
[`stale-branch-cleanup.md`](stale-branch-cleanup.md)). Otherwise, delete
via `gh pr ...` or the GitHub UI — both keep an audit trail. Direct
remote-ref deletion bypasses that trail.

## Prevention

- **Install both hook layers.** The Claude-side hook (M7) catches the
  pattern at the agent's source; the repo-side `.githooks/` (M11) catches
  the same operation when invoked from a terminal, Docker container, or
  CI runner. Defense in depth — see [`best-practices.md`](best-practices.md)
  §2.
- **Never set `CLAUDE_ALLOW_GIT_BAD_OPS=1` (the master override).** It is
  a tripwire; the granular `CLAUDE_ALLOW_<RULE>=1` overrides exist for
  exactly the case where you have thought about it. The master form
  emits a loud stderr warning every time it's consumed.
- **Audit overrides monthly.** `/tcs-git-helpers:git-audit --overrides`. If
  the same granular override appears repeatedly, the lesson is in the
  corresponding reference doc, not in the override.
- **`~/.gitconfig` aliases that wrap denied commands are a gap.** The
  Claude-side regex sees the alias literal (`git pf` is not `git push`).
  The repo-side `.githooks/pre-push` still fires, so the operation still
  fails — but the agent does not get the rich denial reason. If you add
  an alias for a destructive op, also add the same denial pattern to the
  config; better yet, do not alias destructive ops.

## Why

The destructive-ops set is borrowed wholesale from Boucle-framework's
`git-safe` tool, which enumerated the patterns after observing the same
recurring loss across single-developer workflows. Boucle's analysis is the
upstream source for this rule set:

- Boucle `git-safe`:
  <https://github.com/Bande-a-Bonnot/Boucle-framework/blob/main/tools/git-safe>

The plugin re-implements rather than vendors (CON-5), but the pattern set
is 1:1. Two extensions beyond Boucle:

1. **`git -c core.hooksPath=…` denied** — adding the bypass-vector for the
   `.githooks/` layer itself. See
   [`sandbox-and-git-config.md`](sandbox-and-git-config.md).
2. **Granular override per rule** — Boucle had a single master kill
   (`GIT_SAFE_DISABLED=1`); the plugin replaces it with one
   `CLAUDE_ALLOW_<RULE>=1` per rule (ADR-5), with a 5-second sentinel
   to prevent double-tap consumption and a JSONL audit log (ADR-7).

The principle behind the deny set is the same in every case: **the
operation has a recovery cost that exceeds its convenience cost, and the
recovery is not always possible.** A reflog-based recovery requires that
the operation happened recently and that the reflog has not been
expired; an `fsck --lost-found` recovery requires that GC has not run.
Both windows close. The denial is the cheapest reminder.

---

## See also

- [`best-practices.md`](best-practices.md) — §3 non-destructive recovery, §4 audit overrides.
- [`force-push-safety.md`](force-push-safety.md) — the `--force-with-lease` distinction.
- [`working-tree-hygiene.md`](working-tree-hygiene.md) — stash-vs-branch decision.
- [`branch-lifecycle.md`](branch-lifecycle.md) — when `branch -d` is enough.
- [`squash-merge-trap.md`](squash-merge-trap.md) — the one case where `branch -D` is the right answer.
- Boucle `git-safe` upstream: <https://github.com/Bande-a-Bonnot/Boucle-framework/blob/main/tools/git-safe>
