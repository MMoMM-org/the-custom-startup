---
name: finish-branch
description: "Use when a feature branch is ready to merge, push as a PR, or keep for later. Also handles worktree cleanup when running inside a git worktree."
user-invocable: true
argument-hint: "[--option 1|2|3] (skip interactive if known)"
allowed-tools: Bash, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:finish-branch**

Complete the current feature branch: verify tests, choose disposition, clean up.

## Interface

```
State {
  branch: string           // current branch name
  base: string             // merge target (origin/HEAD or "main")
  testCmd: string | null   // resolved test command
  testsPassed: boolean     // result of test run
  option: 1 | 2 | 3        // 1=merge 2=pr 3=keep
  yolo: boolean            // YOLO=true env var
  yoloFinish: string       // YOLO_FINISH env var ("pr" | "merge" | "")
  inWorktree: boolean      // running inside a git worktree
  worktreePath: string     // captured in Step 1, before any directory change
}
```

Discarding is not one of the options — it is a separate path, reached only when
the user explicitly asks for it. See § Discarding the work.

## Constraints

**Always:**
- Capture `WORKTREE_PATH` in Step 1, before any `checkout` or branch deletion. Every later step needs a value that those operations invalidate.
- Remove the worktree *before* deleting the branch. Git refuses to delete a branch that is checked out in a live worktree.
- Require typed `discard` confirmation before deleting any branch.
- Block options 1 and 2 when tests are failing.

**Never:**
- Offer discarding as a menu option. It is destructive and belongs behind an explicit request.
- Force-remove a worktree on your own initiative. Untracked files in a worktree exist nowhere else — no commit, no reflog, no recovery.
- Treat a confirmation to delete a *branch* as consent to delete *uncommitted files*. They are different things; the branch confirmation does not cover work that was never committed.
- Delete a branch without confirmation, even in YOLO mode.
- Proceed to merge/PR without at least attempting test detection.

## Workflow

### 1. Capture branch context

Everything here must be captured **now**, while still inside the workspace. Steps 6
and 7 change directory and delete the branch, which invalidates all of it.

```bash
BRANCH=$(git branch --show-current)
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's#.*/##')
[ -z "$BASE" ] && BASE="main"

# Worktree detection: compare the per-worktree git dir against the shared one.
GIT_DIR_ABS=$(cd "$(git rev-parse --git-dir)" && pwd -P)
GIT_COMMON_ABS=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
if [ "$GIT_DIR_ABS" = "$GIT_COMMON_ABS" ]; then IN_WORKTREE=no; else IN_WORKTREE=yes; fi

# Capture the worktree root now — Step 6 changes directory before Step 7 needs it.
WORKTREE_PATH=$(git rev-parse --show-toplevel)
MAIN_ROOT=$(git -C "$GIT_COMMON_ABS/.." rev-parse --show-toplevel)
```

If `BRANCH` is empty (detached HEAD): surface an error and stop — finish-branch requires a named branch.

### 2. Detect test command

Priority order:

1. `.claude/startup.toml` `[tcs]` section:
```bash
STARTUP_TOML=".claude/startup.toml"
TEST_CMD=""
if [ -f "$STARTUP_TOML" ]; then
  _val=$(sed -n '/^\[tcs\]/,/^\[/p' "$STARTUP_TOML" | grep '^test_cmd' | head -1 | sed 's/test_cmd[[:space:]]*=[[:space:]]*//' | tr -d '"'"'"')
  [ -n "$_val" ] && TEST_CMD="$_val"
fi
```

2. Language file detection (checked in order, first match wins):
```bash
if [ -z "$TEST_CMD" ]; then
  if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
    TEST_CMD="source venv/bin/activate && pytest"
  elif [ -f "package.json" ]; then
    TEST_CMD=$(node -e "const p=require('./package.json'); process.stdout.write(p.scripts&&p.scripts.test||'')" 2>/dev/null)
    [ -z "$TEST_CMD" ] && TEST_CMD="npm test"
  elif [ -f "go.mod" ]; then
    TEST_CMD="go test ./..."
  fi
fi
```

3. No test command found: AskUserQuestion:
   > "No test command detected. Enter your test command, or leave blank to skip tests (this will limit you to keeping the branch as-is)."

### 3. Run tests

If `TEST_CMD` is set: run it and capture exit code and output.

- **Tests pass** (exit 0): all three options are available.
- **Tests fail** (non-zero): display failure output, then:
  > "Tests failed. Only option 3 (keep as-is) is available."
  - `testsPassed = false`

If the test command was skipped (blank input): treat as failing — option 3 only.

### 4. YOLO shortcut

Check env vars before prompting:

```bash
YOLO="${YOLO:-false}"
YOLO_FINISH="${YOLO_FINISH:-}"
```

- `YOLO=true` AND `YOLO_FINISH=pr` AND `testsPassed=true` → jump to Option 2 (no prompt).
- `YOLO=true` AND `YOLO_FINISH=merge` AND `testsPassed=true` → jump to Option 1 (no prompt).
- Otherwise: continue to Step 5.

YOLO never reaches the discard path — there is no `YOLO_FINISH` value for it.

### 5. Present options

AskUserQuestion with the following choices (disable 1 and 2 if `testsPassed=false`):

```
Branch: {branch}  →  Base: {base}

Choose how to finish this branch:

  1. Merge locally    — checkout {base}, pull, merge {branch}, run tests, clean up
  2. Push + PR        — push to origin, open a pull request
  3. Keep as-is       — no changes, just report the branch name

{if testsPassed=false}
  ⚠  Tests failed — options 1 and 2 are disabled.
{end}
```

Present exactly these options. Throwing the work away is not among them: the branch
has just gone green, and offering deletion next to merge advertises destroying
finished work. If the user wants that, they will say so — see § Discarding the work.

If `--option N` was passed as `$ARGUMENTS`: skip the prompt and use that option directly (still validate that 1/2 are blocked when tests failed).

### 6. Execute option

#### Option 1 — Merge locally

Worktree removal must run from outside the worktree, so move to the main repo root first:

```bash
cd "$MAIN_ROOT"
git checkout "$BASE"
git pull
git merge "$BRANCH"
```

Run tests again after merge (reuse `TEST_CMD`). If post-merge tests fail: surface output and stop — do not delete anything. Nothing has been pushed, so the merge is local and recoverable. Prompt the user to resolve conflicts or failures manually.

If post-merge tests pass, clean up the worktree **first** (Step 7), then delete the branch:

```bash
git branch -d "$BRANCH"
```

Order matters: git refuses to delete a branch still checked out in a live worktree.

Report: "Branch `{branch}` merged into `{base}` and deleted."

#### Option 2 — Push + PR

```bash
git push -u origin HEAD
```

Then open the pull request with the forge's own tooling — `gh pr create --fill` where
the GitHub CLI is available, otherwise the creation URL most forges print in the
`git push` output. Follow the repo's PR template and conventions if present.

```bash
if command -v gh >/dev/null 2>&1; then
  gh pr create --fill
else
  echo "No gh CLI — open the PR via the URL printed by the push above."
fi
```

Capture and report the PR URL.

Keep the worktree — the user iterates on PR feedback there.

Report: "PR created: {url}"

#### Option 3 — Keep as-is

Report: "Branch `{branch}` kept. No changes made." — plus the worktree path when `IN_WORKTREE=yes`.

No cleanup.

### 7. Worktree cleanup

**Runs for Option 1 and for a confirmed discard.** Options 2 and 3 always preserve
the worktree.

Skip entirely when `IN_WORKTREE=no`.

Use the `WORKTREE_PATH` captured in Step 1. Do **not** re-derive it here — by this
point the caller has changed directory, and for a discard the branch is already
gone, so a lookup by branch name returns nothing and cleanup silently no-ops.

If you must resolve some *other* worktree by branch name, walk the porcelain
records rather than grepping adjacent lines — `worktree` and `branch` are separated
by `HEAD`, and optionally `locked`/`prunable`, so neither `grep -B1` nor `grep -A1`
finds anything:

```bash
git worktree list --porcelain | awk -v b="refs/heads/$BRANCH" '
  /^worktree / { p = substr($0, 10) }
  $0 == "branch " b { print p; found = 1; exit }
  END { if (!found) exit 1 }
'
```

Remove it:

```bash
git worktree remove "$WORKTREE_PATH"
git worktree prune
```

**If removal is refused** (`contains modified or untracked files`): stop. Those files
exist nowhere else — no commit, no reflog, nothing to recover from. Never reach for
`--force` on your own initiative, and never treat an earlier branch-deletion
confirmation as consent here: uncommitted files were never on the branch, so that
confirmation never covered them.

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
> 2. Move them to `{MAIN_ROOT}`
> 3. Delete them (unrecoverable)

Carry out the choice, then remove the worktree.

## Discarding the work

Reached only when the user explicitly asks to throw the work away — never from the
Step 5 menu, and never in YOLO mode.

Confirm first, naming everything that will be destroyed:

```
This will permanently delete:
- Branch {branch}
- All commits: {commit list}
{if inWorktree}- Worktree at {worktreePath}{end}

Type 'discard' to confirm.
```

Only if the input matches exactly `discard` (case-sensitive):

```bash
cd "$MAIN_ROOT"
git checkout "$BASE"
```

Then clean up the worktree (Step 7 — including its uncommitted-files prompt, which
this confirmation does not replace), and only then delete the branch:

```bash
git branch -D "$BRANCH"
```

Report: "Branch `{branch}` discarded."

If the input does not match: abort with "Deletion cancelled." Change nothing.
