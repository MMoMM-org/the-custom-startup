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

Extract branch name and resolve path:

```bash
git worktree list --porcelain | grep -A1 "branch refs/heads/${branch}" | grep "^worktree" | awk '{print $2}'
```

Remove the worktree:

```bash
git worktree remove "{path}"
```

If removal fails due to untracked/modified files, retry with `--force` only after:
- **YOLO mode**: auto-force
- **Normal mode**: AskUserQuestion: "Worktree has uncommitted changes. Force remove?" [Yes / No]

Then ask about branch deletion:
- **YOLO mode**: skip branch deletion (safe default)
- **Normal mode**: AskUserQuestion: "Also delete branch `{branch}`?" [Yes / No]
  - If Yes: `git branch -d {branch}` (use `-D` if `-d` fails with "not fully merged")

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
