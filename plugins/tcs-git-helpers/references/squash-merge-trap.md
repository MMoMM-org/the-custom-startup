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

Two checks, run together. The branch-tip ancestry check is the **primary reliable signal**; `git cherry` is a supplementary signal that's authoritative only in the single-commit case.

**Primary check — branch-tip ancestry:**

```bash
git merge-base --is-ancestor "<branch_tip>" "origin/<default>"
```

This works regardless of how many commits the branch had or how it was merged.

- Exit 0 (true) → branch tip **is** in default's history → merge-commit (`--no-ff`) case → SAFE to resume.
- Exit 1 (false) → branch tip is orphan from default's history → squash-merge or rebase-merge case → DANGEROUS to resume.

If the PR is known to be merged (e.g., via `gh pr view`) and this check returns false, the branch was squash-merged or rebase-merged — that's the trap.

**Supplementary check — `git cherry`:**

```bash
git cherry "origin/<default>" "<branch>"
```

Each output line is one of:

- `+ <sha>` — patch is **not** yet applied to default
- `- <sha>` — patch is **already** applied to default (possibly under a different SHA)

`git cherry` compares **patch-IDs**, not SHAs. It is **authoritative when it returns all `-` lines on a single-commit branch**: every commit's content is in default, so resuming work is dangerous. On multi-commit branches it is **inconclusive**: a squash collapses N commits into one, and the squash commit's combined-diff patch-ID generally does not match any individual branch commit's patch-ID — so `git cherry` can return `+` lines and miss the squash. See "Why" below.

Verdict from the output (single-commit branch only):

- All `+` lines → branch has unmerged work; safe to resume.
- All `-` lines → every patch is already in default; **DANGEROUS** to resume (squash-merge trap).
- Mixed → some patches applied, some not; also dangerous (recovery via cherry-pick to fresh branch).

For multi-commit branches, **always rely on the ancestry check** to decide.

**Advisory cross-check — parent count of the merge commit (when `gh` is available):**

```bash
pr_num=$(gh pr list --head "<branch>" --state merged --json number --jq '.[0].number')
merge_sha=$(gh pr view "$pr_num" --json mergeCommit --jq '.mergeCommit.oid')
git rev-list --parents -n 1 "$merge_sha" | awk '{print NF-1}'
# 1 parent → squash or rebase merge
# 2 parents → merge-commit
```

Advisory only. Decisions gate on `merge-base --is-ancestor` (with `git cherry` corroborating in the single-commit case), never on `gh` alone (it can be unauthenticated, rate-limited, or offline).

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

   Resolve any conflicts per cherry-pick. If a commit's content is already on default (the squash trap case), `git cherry-pick` will report "nothing to commit" — skip it with:

   ```bash
   git cherry-pick --skip   # Git ≥ 2.32 (June 2021)
   # On older Git (e.g., macOS system Git): git reset HEAD && git cherry-pick --continue
   ```

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
- **Run `/tcs-git-helpers:git-audit --cleanup`** to surface stale local branches whose PRs have already merged. The skill filters out branches checked out in worktrees so it never proposes a deletion that would error.
- **Trust the hooks.** `block-bad-git-ops.sh` denies `git checkout <merged-branch>` when the branch tip is not an ancestor of default AND `git cherry` reports all-`-` — the canonical single-commit squash-trap signal. The denial cites this document. (Multi-commit squashes may evade the `git cherry` half of the check; the ancestry signal remains the primary reliable cross-check, and hooks are a backstop, not a full substitute for the post-merge cleanup discipline above.)

## Why

Squash-merge collapses N branch commits into **one fresh commit** on the default branch. The new commit has:

- A new SHA (it didn't exist before the merge).
- Content (combined diff) identical to the sum of the N original branch commits' diffs.
- A patch-ID computed from **that combined diff**, not from any individual branch commit.

`git cherry` walks the branch's commits one by one and asks, for each, *"is this commit's patch-ID already represented in default's history?"* What it finds depends on the commit count:

- **Single-commit branch (N = 1):** the squash commit's combined diff is identical to the sole branch commit's diff, so the patch-IDs match. `git cherry` returns `-` for that commit, and the all-`-` reading correctly flags the squash. This is the canonical signal — and the only case where `git cherry` is reliable for squash detection.
- **Multi-commit branch (N > 1):** the squash commit's patch-ID is computed from the *combined* diff and generally does **not** match any individual branch commit's patch-ID. `git cherry` may report `+` lines for every branch commit, even though every line of their content is already on default under the squash. The all-`-` signal is therefore **not** a complete detector — it can miss multi-commit squashes entirely.

That's why ancestry — `git merge-base --is-ancestor <branch_tip> origin/<default>` — is the primary signal. It works regardless of N:

- Squash-merge or rebase-merge → branch tip is **not** an ancestor of default (the original SHAs were discarded; only their content survives, under new SHAs).
- Merge-commit (`--no-ff`) merge → branch tip **is** an ancestor (the merge commit has two parents; one is the branch tip, so the original SHAs live on in default's history).

Combined with PR-merged confirmation (e.g., `gh pr view --state merged`), a "branch tip not ancestor of default" reading on a merged branch is exactly the squash/rebase trap. `git cherry` corroborates in the single-commit case; for N > 1, the ancestry check stands on its own.

In short: `merge-base --is-ancestor` tells us whether the original SHAs are in default's history; `git cherry` tells us whether the patches are there, but only reliably when N = 1. We deny resume-on-branch when ancestry is false on a merged branch — that's the squash/rebase case where reusing the branch causes the trap.

The canonical detection logic is the `_is_branch_dangerously_merged` algorithm — see SDD `docs/XDD/specs/011-tcs-git-helpers/solution.md` lines 945-1020 for the bash implementation, traced walkthrough across the three branch scenarios (squashed / merge-committed / active), and the rationale for gating on ancestry rather than `git cherry` alone.

---

## See also

- [`branch-lifecycle.md`](branch-lifecycle.md) — post-merge branch hygiene.
- [`pr-vs-commit-messages.md`](pr-vs-commit-messages.md) — squash-merge implication: PR title becomes the commit subject on default.
- SDD `docs/XDD/specs/011-tcs-git-helpers/solution.md` lines 945-1020 — `_is_branch_dangerously_merged` algorithm, canonical source of detection logic.
- Boucle-framework `worktree-guard` — origin of the `git cherry`-based detection used here: <https://github.com/Bande-a-Bonnot/Boucle-framework>
