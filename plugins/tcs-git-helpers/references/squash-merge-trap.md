# Squash-merge trap

> Why you can't keep working on a branch after it's been squash-merged.

## What goes wrong

A feature branch's PR was merged with **squash-merge** (or rebase-merge), then work continues on the same local branch. The user — or Claude, between sessions — runs more commits, tries to push, or opens a new PR from the branch.

What happens next:

- The original branch commits and the new commit on the default branch have **different SHAs but identical content**. Squash-merge collapsed N commits into 1 fresh commit on `main`/`master`.
- Old commits' patches no longer apply cleanly to the new default state. The PR shows `mergeable: CONFLICTING` even though the content is "already there".
- A `git push` to the closed PR's branch **pollutes the closed PR** (new commits show up under the merged PR's UI, confusing reviewers and history).
- A reflexive `git rebase origin/<default>` to "fix the conflicts" turns into a manual conflict-resolution session for changes that were never meant to be re-applied.

The trap is that the branch *looks* fine locally — it has commits, it has a name, `git status` is clean — but its commits are already represented (under different SHAs) on the default branch.

## How to detect

Two checks, run together. Neither alone is sufficient.

**Primary check — `git cherry`:**

```bash
git cherry "origin/<default>" "<branch>"
```

Each output line is one of:

- `+ <sha>` — patch is **not** yet applied to default
- `- <sha>` — patch is **already** applied to default (possibly under a different SHA)

`git cherry` compares **patch-IDs**, not SHAs, so it correctly identifies content that was reapplied via squash or rebase.

Verdict from the output:

- All `+` lines → branch has unmerged work; safe to resume.
- All `-` lines → every patch is already in default; **DANGEROUS** to resume (squash-merge trap).
- Mixed → some patches applied, some not; also dangerous (recovery via cherry-pick to fresh branch).

**Cross-check — branch-tip ancestry:**

```bash
git merge-base --is-ancestor "<branch_tip>" "origin/<default>"
```

This distinguishes squash/rebase merges from merge-commit (`--no-ff`) merges. Both produce all-`-` lines from `git cherry`, but only merge-commit preserves the original branch SHAs in default's history.

- Exit 0 (true) → branch tip **is** in default's history → merge-commit case → SAFE to resume.
- Exit 1 (false) → branch tip is orphan from default's history → squash/rebase case → DANGEROUS.

A second cross-check — parent count of the merge commit — can be used as advisory confirmation when `gh` is available:

```bash
pr_num=$(gh pr list --head "<branch>" --state merged --json number --jq '.[0].number')
merge_sha=$(gh pr view "$pr_num" --json mergeCommit --jq '.mergeCommit.oid')
git rev-list --parents -n 1 "$merge_sha" | awk '{print NF-1}'
# 1 parent → squash or rebase merge
# 2 parents → merge-commit
```

This is advisory only. Decisions gate on `git cherry` + `merge-base --is-ancestor`, never on `gh` alone (it can be unauthenticated, rate-limited, or offline).

## Fix

**Cherry-pick onto a fresh branch.** Non-destructive — the original branch and its reflog are preserved for forensics.

1. **Identify commits to preserve** — only commits unique to the branch, not yet in default:

   ```bash
   git log "<branch>" --not "origin/<default>" --oneline
   ```

2. **Create a fresh branch from the current default tip:**

   ```bash
   git fetch origin
   git checkout "origin/<default>" -b "<branch>-resumed"
   ```

3. **Cherry-pick the desired commits** in order:

   ```bash
   git cherry-pick <sha-1> <sha-2> <sha-3>
   ```

   Resolve any conflicts per cherry-pick. If a commit's content is already on default (the squash trap case), `git cherry-pick` will report "nothing to commit" — skip it with `git cherry-pick --skip`.

4. **Push the new branch and open a new PR:**

   ```bash
   git push -u origin "<branch>-resumed"
   gh pr create
   ```

5. **Leave the old branch alone until the new PR merges.** Do **not** auto-delete it; the reflog and branch ref are the recovery net if anything goes wrong with the cherry-pick. After the new PR merges and you've confirmed the new history is correct, the old branch can be deleted normally (`git branch -d` — non-force).

## Prevention

- **Delete the local branch after its PR merges:** `git branch -d <branch>`. The `-d` (lowercase) form refuses to delete unmerged work, so it's safe to run reflexively after a merge.
- **Enable GitHub's "automatically delete head branches"** for the repo. New repos default to this; check existing repos with:

  ```bash
  gh repo view --json deleteBranchOnMerge
  ```

  Toggle via repo settings or `gh api -X PATCH repos/<owner>/<repo> -f delete_branch_on_merge=true`.
- **Run `/tcs-git-helpers:status --cleanup`** to surface stale local branches whose PRs have already merged. The skill filters out branches checked out in worktrees so it never proposes a deletion that would error.
- **Trust the hooks.** `block-bad-git-ops.sh` denies `git checkout <merged-branch>` when `git cherry` says all-`-` AND the branch tip is not an ancestor of default — exactly the squash-trap signal. The denial cites this document.

## Why

Squash-merge collapses N branch commits into **one fresh commit** on the default branch. The new commit has:

- A new SHA (it didn't exist before the merge).
- Content identical to the sum of the N original branch commits.
- A patch-ID computed from that content.

Patch-IDs are content-addressed: the squash commit's patch-ID matches the sum of the original branch commits' patch-IDs taken together — but for the per-commit detection we care about, `git cherry` walks the branch's commits one by one and asks *"is this commit's patch-ID already represented in default's history?"*. For a squash-merged branch, the answer is yes for every commit, even though no original SHA appears in default. That's the detection signal: all `-` lines.

Merge-commit merges (`--no-ff`) are different: they keep every original branch SHA in default's history (the merge commit has two parents, one of which is the branch tip). `git cherry` still reports all `-` lines (the patches are applied), but `git merge-base --is-ancestor <branch_tip> origin/<default>` returns true. That's the false-positive case the cross-check eliminates — without it, we'd wrongly flag every safely-merged branch as "dangerous".

In short: `git cherry` tells us *the patches are there*; `merge-base --is-ancestor` tells us *the SHAs are there too*. We deny only when the first is true and the second is false. That's exactly the squash/rebase case where reusing the branch causes the trap.

---

## See also

- [`branch-lifecycle.md`](branch-lifecycle.md) — Cleanup section: post-merge branch hygiene.
- [`pr-vs-commit-messages.md`](pr-vs-commit-messages.md) — squash-merge implication: PR title becomes the commit subject on default.
- Boucle-framework `worktree-guard` — origin of the `git cherry`-based detection used here: <https://github.com/Bande-a-Bonnot/Boucle-framework>
