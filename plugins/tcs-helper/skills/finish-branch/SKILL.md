---
name: finish-branch
description: "Branch completion workflow. Run when a feature branch is ready to ship. Verifies tests pass, then offers: merge locally, push and create PR, keep as-is, or discard. Handles worktree cleanup automatically."
user-invocable: true
argument-hint: "[--option 1|2|3|4] (skip interactive if known)"
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
  option: 1 | 2 | 3 | 4   // 1=merge 2=pr 3=keep 4=discard
  yolo: boolean            // YOLO=true env var
  yoloFinish: string       // YOLO_FINISH env var ("pr" | "merge" | "")
  inWorktree: boolean      // running inside a git worktree
}
```

## Constraints

**Always:**
- Run tests before presenting options.
- Require typed "discard" confirmation before deleting any branch.
- Block options 1 and 2 when tests are failing.
- Clean up the worktree registration for options 1 and 4.

**Never:**
- Delete a branch without confirmation.
- Skip the discard confirmation even in YOLO mode.
- Proceed to merge/PR without at least attempting test detection.

## Workflow

### Step 1 — Capture branch context

```bash
BRANCH=$(git branch --show-current)
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's#.*/##')
[ -z "$BASE" ] && BASE="main"
IN_WORKTREE=$(git rev-parse --git-common-dir 2>/dev/null | grep -v "^\.git$" && echo "yes" || echo "no")
```

If `BRANCH` is empty (detached HEAD): surface an error and stop — finish-branch requires a named branch.

### Step 2 — Detect test command

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
   > "No test command detected. Enter your test command, or leave blank to skip tests (this will limit you to keep-as-is and discard)."

### Step 3 — Run tests

If `TEST_CMD` is set: run it and capture exit code and output.

- **Tests pass** (exit 0): all four options are available.
- **Tests fail** (non-zero): display failure output, then:
  > "Tests failed. Only options 3 (keep as-is) and 4 (discard) are available."
  - `testsPassed = false`

If test command was skipped (blank input): treat as failing — options 3 and 4 only.

### Step 4 — YOLO shortcut

Check env vars before prompting:

```bash
YOLO="${YOLO:-false}"
YOLO_FINISH="${YOLO_FINISH:-}"
```

- `YOLO=true` AND `YOLO_FINISH=pr` AND `testsPassed=true` → jump to Option 2 (no prompt).
- `YOLO=true` AND `YOLO_FINISH=merge` AND `testsPassed=true` → jump to Option 1 (no prompt).
- Otherwise: continue to Step 5.

### Step 5 — Present options

AskUserQuestion with the following choices (disable 1 and 2 if `testsPassed=false`):

```
Branch: {branch}  →  Base: {base}

Choose how to finish this branch:

  1. Merge locally    — checkout {base}, pull, merge {branch}, run tests, delete branch
  2. Push + PR        — push to origin, open gh pr create
  3. Keep as-is       — no changes, just report the branch name
  4. Discard          — delete branch (and worktree if applicable)

{if testsPassed=false}
  ⚠  Tests failed — options 1 and 2 are disabled.
{end}
```

If `--option N` was passed as `$ARGUMENTS`: skip the prompt and use that option directly (still validate that 1/2 are blocked when tests failed).

### Step 6 — Execute option

#### Option 1 — Merge locally

```bash
git checkout "$BASE"
git pull
git merge "$BRANCH"
```

Run tests again after merge (reuse `TEST_CMD`). If post-merge tests fail: surface output and stop — do not delete the branch. Prompt the user to resolve conflicts or failures manually.

If post-merge tests pass:

```bash
git branch -d "$BRANCH"
```

If worktree: remove registration (see Step 7).

Report: "Branch `{branch}` merged into `{base}` and deleted."

#### Option 2 — Push + PR

```bash
git push -u origin HEAD
```

Then:

```bash
gh pr create --fill
```

The `--fill` flag pre-populates title and body from commit messages; the user can edit interactively.

Capture and report the PR URL from `gh pr create` output.

Report: "PR created: {url}"

#### Option 3 — Keep as-is

Report: "Branch `{branch}` kept. No changes made."

No cleanup.

#### Option 4 — Discard

AskUserQuestion:
> "Type **discard** to permanently delete branch `{branch}`{if inWorktree: " and remove its worktree"}.
> This cannot be undone."

If input matches exactly `discard` (case-sensitive):

```bash
git checkout "$BASE"
git branch -D "$BRANCH"
```

If worktree: remove registration (see Step 7).

Report: "Branch `{branch}` discarded."

If input does not match `discard`: abort with "Deletion cancelled."

### Step 7 — Worktree cleanup (options 1 and 4 only)

Detect worktree path:

```bash
WORKTREE_PATH=$(git worktree list --porcelain | grep -B1 "branch refs/heads/${BRANCH}" | grep "^worktree" | awk '{print $2}')
```

If path found and it is not the main repo root:

```bash
git worktree remove "$WORKTREE_PATH"
```

If removal fails due to untracked/modified files: force-remove only after confirming with AskUserQuestion (unless option 4 and user already confirmed discard — then force without second prompt).
