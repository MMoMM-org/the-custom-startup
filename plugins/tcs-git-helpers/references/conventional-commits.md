# Conventional Commits

Format spec, type allowlist, and the `[skip-format-check]` escape hatch
enforced by the `commit-msg` hook (M5). Inherits the format from
`~/Kouzou/standards/git-conventions.md` and broadens the type allowlist.

## What goes wrong

1. **Non-conformant commit message rejected.** A commit subject like
   `update parser` (no type) or `Feature: add login` (wrong format) fails the
   `commit-msg` hook with exit 1 and the commit is aborted. The working tree
   is unchanged; nothing destructive happens.
2. **Squash-merge produces messy default-branch history.** When a repo
   squash-merges PRs, the **PR title** becomes the single commit on default —
   not the per-commit messages on the feature branch. A PR titled
   `WIP fix bug?` lands as a permanent commit on `main`. See
   [pr-vs-commit-messages.md](pr-vs-commit-messages.md).
3. **Allowlist drift.** A repo's `.githooks/.config` set `TCS_REQUIRE_SCOPE=1`
   or restricted `TCS_ALLOWED_COMMIT_TYPES`, and a previously-fine type is
   now rejected.

## How to detect

The `commit-msg` hook output names the rule that tripped:

```text
[tcs-git-helpers] DENIED: Conventional Commits format
Subject: update parser
Reason: Type not in allowlist or missing/malformed scope.
Allowed types: feat fix docs style refactor test chore perf revert build ci
Format: <type>(<scope>)?!?: <subject>
```

For PR titles (the squash-merge commit-message contract), the GitHub Actions
workflow `templates/github-actions/pr-title-check.yml` (Feature S2) validates
on every `pull_request` event and fails the workflow with the same regex.

Locally, you can dry-run the check:

```bash
# Read your last commit subject and re-check it manually
git log -1 --pretty=%s | grep -E '^(feat|fix|docs|style|refactor|test|chore|perf|revert|build|ci)(\([a-z0-9._-]+\))?!?: .+'
```

## Fix

**Before push — amend the most recent commit message:**

```bash
git commit --amend -m "feat(scope): <imperative subject ≤72 chars>"
```

`--amend` is non-destructive when the commit has not been pushed: it rewrites
your local HEAD, the reflog still has the old version, and no remote is
affected.

**After push, before merge — push a new commit instead of force-pushing:**

```bash
# Add the corrective message as a new commit (squash-merge will collapse anyway)
git commit --allow-empty -m "chore(scope): clarify previous commit"
git push
```

Avoid `git push --force` and `git push --force-with-lease` here unless you
specifically need to rewrite history; force-push is denied on protected
branches and discouraged on shared branches — see
[force-push-safety.md](force-push-safety.md).

**For the PR title (squash-merge contract) — edit on GitHub before merge:**

```bash
# Edit via gh CLI
gh pr edit <number> --title "feat(scope): <imperative subject>"
```

The PR title is the single most important message on a squash-merge repo
because it becomes the only commit on default. See
[pr-vs-commit-messages.md](pr-vs-commit-messages.md).

**Emergency escape — use the override marker:**

If a commit genuinely cannot match the format (cherry-pick from upstream,
externally-mandated subject, etc.), include `[skip-format-check]` in the
subject. The hook accepts the commit and the marker remains visible in
`git log` for audit.

```bash
git commit -m "Revert commit abc123 [skip-format-check]"
```

## Prevention

**Format spec** (from `~/Kouzou/standards/git-conventions.md`):

```text
<type>(<scope>)?!?: <subject>
```

- **Type** (required, lowercase) — one of:
  `feat fix docs style refactor test chore perf revert build ci`
  (the `commit-msg` hook default; see `templates/githooks/commit-msg`).
  Custom allowlists possible per-repo via `.githooks/.config`'s
  `TCS_ALLOWED_COMMIT_TYPES`.
- **Scope** (optional, lowercase) — short noun like `parser`, `auth`,
  `tcs-git-helpers`. Required when `TCS_REQUIRE_SCOPE=1` is set in
  `.githooks/.config`.
- **`!`** (optional) — denotes a breaking change.
- **Subject** — imperative mood (`add`, `fix`, `update`, not `added`/`fixed`),
  no trailing period, ≤72 characters.

**Examples that pass:**

```text
feat(auth): add OAuth provider for GitHub
fix(parser): handle empty input without panicking
docs(tcs-git-helpers): update setup walkthrough
chore: bump dependencies                      # scope optional unless required
feat(api)!: drop legacy /v1 endpoint          # breaking change
revert: feat(auth): add OAuth provider        # revert pattern
```

**Examples that fail:**

```text
update parser                # no type
Fix: bug                     # capitalized type
feat(): empty scope          # malformed scope
feat(auth) add login         # missing colon
feat(auth): Added login.     # past tense + trailing period
```

**Body and footer** (optional, for non-trivial changes):

```text
feat(auth): add OAuth provider for GitHub

Adds GitHub provider alongside the existing Google and GitLab providers.
Stores tokens in the same KeyChain entry; refresh logic shared via
auth/oauth/refresh.go.

Refs #142
```

**Merge-commit exemption:** the hook auto-skips format checks when
`MERGE_HEAD` exists or the subject begins with `Merge branch ` /
`Merge pull request ` — these are git-generated and out of scope.

## Why

Conventional Commits is the agreed-upon format across the MiYo ecosystem and
TCS itself. Two reasons it matters here:

1. **Squash-merge implication.** GitHub's squash-merge collapses all per-commit
   messages on a feature branch into one default-branch commit — using the **PR
   title** as the message. If PR titles are not Conventional Commits, the
   default branch becomes unreadable and changelog tooling breaks.
2. **Automation.** Tools like changelog generators, semantic-release, and
   commit-based filtering all assume the format. Even without those tools
   today, conformant history is cheap insurance.

The allowed-types list is broader than the original Conventional Commits 1.0
spec (which lists only `feat`/`fix`) because TCS includes `docs`, `style`,
`refactor`, `test`, `chore`, `perf`, `revert`, `build`, and `ci` as
first-class change categories. The repo can narrow this list via
`.githooks/.config`'s `TCS_ALLOWED_COMMIT_TYPES`.

References:

- PRD §Feature M5 (commit-msg hook enforcement)
- SDD §Acceptance Criteria M5
- `~/Kouzou/standards/git-conventions.md` (canonical format spec)
- [pr-vs-commit-messages.md](pr-vs-commit-messages.md) (squash-merge implication)
- `templates/githooks/commit-msg` (default allowlist source)
