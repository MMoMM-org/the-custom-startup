# PR Title vs Commit Messages

On a squash-merge repo, the **PR title** becomes the commit message on the
default branch. Per-commit messages on the feature branch are collapsed and
discarded. This makes the PR title the single most important message in the
workflow, and the most commonly under-cared-for one.

## What goes wrong

1. **Carefully-crafted commit messages, careless PR title.** Claude writes
   ten meaningful conventional-commit messages on `feat/foo` (`feat(parser):
   handle …`, `test(parser): cover …`, etc.), then opens a PR with a default
   title like "Update parser" or worse, the branch name `feat/foo`. On
   squash-merge, the default branch gets `Update parser` as the only record
   of the work — all the rich per-commit context is gone.
2. **PR title not in Conventional Commits format.** The `commit-msg` hook
   accepts every per-commit message because they conform; but the PR title
   doesn't, so the squashed default-branch commit fails the format and
   pollutes changelog/release tooling.
3. **Mismatch between PR title and the work it represents.** The PR was
   opened for one task, work was added for another, and the title was never
   updated. The squashed commit lies about what it contains.

## How to detect

```bash
# Look at the last N commits on the default branch — each one is a squashed PR
git log --oneline -20 origin/main

# A repo using squash-merge has one commit per merged PR; each commit message
# matches the (final) PR title at merge time. If you see "Update X" or a
# branch-name-like subject, that's a PR-title hygiene gap.

# Compare the PR title to its squash-merge commit
gh pr view <number> --json title,mergeCommit,state
git show <merge-sha> --format=%s --no-patch
```

The post-PR-create nudge (Feature M9) reminds Claude after `gh pr create` or
the first push to verify the PR title matches Conventional Commits format.

If the repo opted into the GitHub Actions PR-title check
(`templates/github-actions/pr-title-check.yml`, Feature S2), the workflow
fails the PR until the title conforms.

## Fix

**Before merge — edit the PR title.** This is the canonical fix and is fully
non-destructive:

```bash
gh pr edit <number> --title "feat(scope): <imperative subject>"
```

The PR title can be edited any time before the PR is merged; the squash-merge
will use whatever the title is at merge time.

**After merge — accept the result.** Once the PR is squash-merged, the commit
on the default branch is part of shared history. Rewriting it would require a
force-push to the default branch, which is **destructive** and is denied by:

- the M7 destructive-ops hook (any `--force` to a protected branch)
- GitHub branch protection (`allow_force_pushes=false`, set by Feature S1)

The non-destructive recovery is forward-only: write a follow-up commit (or
PR) clarifying the previous one, and adjust the PR-title habit going forward.

```bash
# Forward-only correction — a new conventional commit on a new branch
git switch <default> && git pull --ff-only
git switch -c chore/clarify-history
git commit --allow-empty -m "chore(docs): clarify intent of <prev-sha>

The squash-merged commit titled \"Update parser\" actually implemented
the parser-error refactor. Recording the correction here for changelog
tooling that scans the default branch."
```

## Prevention

**Treat the PR title as the commit-message contract.** When opening a PR on
a squash-merge repo, write the title as if it were the commit on default —
because that is what it becomes.

```bash
# Use Conventional Commits format for the PR title
gh pr create \
  --title "feat(parser): handle empty input without panicking" \
  --body "Fixes #142. Adds explicit empty-input branch and tests."

# Or open with --fill to use the latest commit message as a starting template,
# then edit the title to taste before merge
gh pr create --fill
gh pr edit <number> --title "<conventional-commits subject>"
```

**Per-commit messages are scratch space on squash-merge repos.** This is
counter-intuitive and worth stating: the messages of individual feature-branch
commits **do not appear on the default branch** after squash-merge. Use them
to communicate during PR review and for your own reflog navigation; do not
agonize over them.

**Enable the PR-title check workflow.** Run
`/tcs-git-helpers:setup --with-gha` to install
`templates/github-actions/pr-title-check.yml`. The workflow fails on any PR
whose title does not match the Conventional Commits regex, surfacing the
problem before merge instead of after.

**Read [conventional-commits.md](conventional-commits.md)** for the format
spec the PR title must satisfy.

## Why

GitHub's squash-merge UI takes the PR title (not the head commit's subject,
not a concatenation of branch commits) as the squashed commit's subject by
default. The body field of the squash dialog defaults to the per-commit
messages concatenated, but most reviewers (and Claude) accept the default
title without thinking — so what they typed at PR-open time is what lands on
default forever.

This is **not** how merge-commit or rebase-merge strategies work:

- **Merge commit:** keeps every per-commit message; PR title only used for
  the merge-commit subject.
- **Rebase merge:** keeps every per-commit message verbatim, no merge commit.
- **Squash merge:** discards per-commit messages; PR title becomes the sole
  default-branch commit.

For single-coder workflows on small features (the MiYo and TCS norm),
squash-merge gives a clean linear default-branch history with one commit per
feature. The trade-off is that the PR title carries all the weight. See
[rebase-vs-merge.md](rebase-vs-merge.md) for the broader strategy choice.

References:

- PRD §Feature M5 (commit format), Feature M9 (post-PR-create nudge), Feature S2 (GHA check)
- SDD §Acceptance Criteria M9 (nudge after `gh pr create`)
- [conventional-commits.md](conventional-commits.md)
- GitHub docs: "About merge methods on GitHub" / squash-merge defaults
