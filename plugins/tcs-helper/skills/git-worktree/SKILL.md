---
name: git-worktree
description: "Use when starting parallel feature work, managing multiple branches simultaneously, or switching between branches without losing working state."
user-invocable: true
argument-hint: "[branch-name] [--path custom/path] [--cleanup branch-name] [--list]"
allowed-tools: Bash, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:git-worktree**

Create and manage isolated git worktrees for parallel feature work.

## Interface

```
State {
  mode: "create" | "cleanup" | "list"  // parsed from arguments
  branch: string                        // target branch name
  repoName: string                      // basename of git root
  worktreePath: string                  // resolved target path
  customPath: string | null             // from --path flag
  yolo: boolean                         // YOLO=true env var
  exists: boolean                       // worktree already registered
}
```

## Constraints

**Always:**
- Replace `/` with `-` when using branch name as part of a directory name
- Surface git error output verbatim on failure
- Show the resolved path before running any destructive command

**Never:**
- Delete a branch without asking (unless YOLO=true and user explicitly passed `--delete-branch`)
- Force-remove a dirty worktree without confirmation in normal mode
- Create a worktree inside the current repo root


## Workflow

### 1. Parse arguments and detect mode

```
match ($ARGUMENTS) {
  empty | branch-name  => mode: "create"
  "--list" | "list"    => mode: "list"
  "--cleanup <branch>" => mode: "cleanup", extract branch name
}
```
- Extract `--path <value>` if present, store as `customPath`
- Check `YOLO` env var: if `YOLO=true`, set `yolo: true`

### 2. List mode

```bash
git worktree list --porcelain
```

Parse output and display as a table:

```
Path                                 Branch          Status
───────────────────────────────────  ──────────────  ──────
/path/to/repo                        main            clean
/path/to/worktrees/repo-feat-xyz     feat/xyz        dirty
```

Status is `dirty` if the worktree has uncommitted changes (`git -C <path> status --porcelain` returns output), otherwise `clean`.

Exit after displaying.

### 3. Resolve create path

```bash
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
```

- If `customPath` set: use that as `worktreePath`
- Otherwise: `worktreePath = ../worktrees/${REPO_NAME}-${branch}`
  - Replace `/` with `-` in branch name (e.g. `feat/xyz` → `feat-xyz`)

### 4. Detect existing worktree

```bash
git worktree list | grep -F "${branch}"
```

If a worktree for this branch is already registered:
- **YOLO mode**: reuse the existing path, skip to conclude
- **Normal mode**: AskUserQuestion:
  > "Worktree for `{branch}` already exists at `{existing-path}`.
  > Reuse it, or create a new one at `{worktreePath}-2`?"
  > [Reuse / New]

  If New: append `-2` (then `-3`, etc.) until the path is free.

### 5. Create worktree

```bash
git worktree add "{worktreePath}" "{branch}"
```

If `{branch}` does not exist locally, `git worktree add` creates it. No extra flags needed.

**YOLO mode**: run without confirmation.

**Normal mode**: skip confirmation (path is shown in Step 3, that is sufficient).

On error (e.g. branch checked out elsewhere): surface the git error message and stop.

### 6. Cleanup mode

Extract branch name and resolve path. Walk the porcelain records — do **not** grep
adjacent lines. Each record is `worktree` / `HEAD` / `branch`, optionally with
`locked` or `prunable` in between, so the two lines are never neighbours and both
`grep -A1` and `grep -B1` return nothing:

```bash
WORKTREE_PATH=$(git worktree list --porcelain | awk -v b="refs/heads/${branch}" '
  /^worktree / { p = substr($0, 10) }
  $0 == "branch " b { print p; found = 1; exit }
  END { if (!found) exit 1 }
')
```

If no path comes back, the branch has no worktree — report that and stop, rather
than proceeding with an empty path.

Remove the worktree (from outside it), then prune stale registrations:

```bash
git worktree remove "$WORKTREE_PATH"
git worktree prune
```

**If removal is refused** (`contains modified or untracked files`): stop. Those files
exist nowhere else — no commit, no reflog, nothing to recover from. Never force-remove
on your own initiative, and never auto-force in YOLO mode: YOLO covers speed on
recoverable operations, not the destruction of the only copy of something.

Show what is at stake, then ask:

```bash
git -C "$WORKTREE_PATH" status --porcelain -uall
```

AskUserQuestion:

> Worktree removal refused — these files were never committed:
>
> {file list}
>
> 1. Commit them to `{branch}` before cleanup
> 2. Move them to the main repo root
> 3. Delete them (unrecoverable)

Carry out the choice, then remove the worktree.

Then ask about branch deletion — always after the worktree is gone, since git
refuses to delete a branch that is still checked out in a live worktree:
- **YOLO mode**: skip branch deletion (safe default)
- **Normal mode**: AskUserQuestion: "Also delete branch `{branch}`?" [Yes / No]
  - If Yes: `git branch -d {branch}`. If that fails with "not fully merged", report
    the unmerged state and ask before escalating to `git branch -D`.

### 7. Conclude

**Create**: announce result:
> "Worktree created at `{worktreePath}` on branch `{branch}`.
> Run `/guide` to orient in the new worktree."

**Cleanup**: announce:
> "Worktree at `{path}` removed."
> (+ "Branch `{branch}` deleted." if applicable)

### Entry Point

```
match (mode) {
  "list"    => step 2, exit
  "cleanup" => steps 6, 7
  "create"  => steps 3, 4, 5, 7
}
```
