---
name: guide
description: "Orientation and session-recovery skill. Invoke at session start or after context loss — reads current git branch and open plan to announce where you are and what to do next. Works without any session history."
user-invocable: true
argument-hint: "[intent: 'new feature' | 'fix bug' | 'code review' | 'continue' | leave blank for auto-detect]"
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
---

## Persona

**Active skill: tcs-workflow:guide**

**Intent**: $ARGUMENTS

## Interface

```
Intent = "new feature" | "fix bug" | "code review" | "continue" | "write tests" | "review my code" | "record a decision" | "finish branch" | "check docs" | auto-detect

SessionState {
  branch: string
  spec_id: string | null
  current_phase: string | null
  open_tasks: string[]
  context_note: string | null   // from docs/ai/memory/context.md
}

State {
  intent = $ARGUMENTS || auto-detect
  session: SessionState
}
```

## Constraints

- **Bash-first**: read live git state via bash commands — do NOT rely on session memory.
- **`fd` and `rg` preferred** for plan file discovery and task scanning. If absent, fall back to `find` / `grep` and print a warning (not a blocker): `[warn] fd/rg not found — using find/grep (install fd-find and ripgrep for faster results)`.
- **`docs/ai/memory/context.md`** is a supplementary hint only — it may be stale or absent. Never block on it.
- **YOLO mode** `[ "${YOLO:-false}" = "true" ]`: run the recovery algorithm automatically, skip the intent prompt, output structured state and next command.
- **Every intent path MUST end** with an explicit "Next: run `/skill-name [args]`" announcement.
- All skills in tcs-workflow must be reachable from at least one intent path.

## Recovery Algorithm (runs first, always)

Execute these steps before resolving intent.

### Step 1 — Current branch

```bash
git branch --show-current
```

Store result as `branch`.

### Step 2 — Find open plan files

```bash
fd -t f "phase-*.md" docs/XDD/specs/ 2>/dev/null \
  || find docs/XDD/specs/ -name "phase-*.md" 2>/dev/null
```

If `fd` is unavailable, emit the install warning and continue with `find`.

### Step 3 — Count open tasks per phase file

For each phase file found:

```bash
grep -c "^- \[ \]" <phase-file>
```

The phase file with the highest count of open tasks becomes the `current_phase` candidate. Extract `spec_id` from the file path (e.g., `docs/XDD/specs/001-auth/plan/phase-2.md` → spec_id `001-auth`).

### Step 4 — Read context hint

```bash
# Read if it exists
cat docs/ai/memory/context.md 2>/dev/null
```

Extract "Last Verified", "Last Task", or any `## Current` sections as `context_note`. If the file does not exist, set `context_note = null` and continue.

### Step 5 — Resolve state

```
If open tasks found (Step 3):
  → Announce: "Continuing [spec-id] phase [N]. Next open task: [task name]."
  → Set intent = "continue" automatically (skip intent prompt)
  → Proceed directly to the "continue" decision-tree branch

Else if context_note references a spec:
  → Announce: "No open tasks found in plan files. Context hint: [context_note]."
  → Suggest intent = "continue" but ask user to confirm

Else:
  → Announce: "No open plan found."
  → Proceed to intent resolution (ask or use $ARGUMENTS)
```

## Decision Tree

After the recovery algorithm, resolve intent. If intent is blank and no open plan was found, ask:

```
What would you like to do?
1. New feature — brainstorm → xdd → implement
2. Fix a bug — debug → verify
3. Process a code review — receive-review
4. Review my code — review
5. Write TDD tests — xdd-tdd
6. Record a decision — record-decision
7. Finish/merge branch — finish-branch
8. Fetch documentation — docs
```

### Intent: "new feature" | "build something"

Announce: "Starting new feature workflow."

Full sequence: `/brainstorm` → `/xdd` → `/xdd-sdd` → `/xdd-plan` → `/implement`

Next: run `/brainstorm [feature description]`

---

### Intent: "fix a bug" | "debug"

Announce: "Starting bug investigation."

After debug completes, run `/verify` to confirm fix.

Next: run `/debug [symptom description]`

---

### Intent: "code review" | "got a PR review" | "received review feedback"

Announce: "Processing code review feedback."

Next: run `/receive-review [paste feedback or PR URL]`

---

### Intent: "continue" | blank + open plan found (auto-resolved in Step 5)

Announce: "Continuing [spec-id] phase [N]."

Next: run `/implement phase-[N]`

---

### Intent: "write tests" | "TDD"

Announce: "Starting TDD cycle."

Next: run `/xdd-tdd [task description] [--sdd-ref SDD/Section]`

---

### Intent: "review my code" | "self-review" | "request review"

Announce: "Running code review."

Next: run `/review`

---

### Intent: "record a decision" | "ADR" | "architecture decision"

Announce: "Recording architecture decision."

Next: run `tcs-team:the-architect:record-decision [decision topic]`

---

### Intent: "finish branch" | "merge" | "done with feature" | "create PR"

Announce: "Branch completion workflow."

Next: run `/finish-branch`

---

### Intent: "check docs" | "fetch docs" | "API reference"

Announce: "Fetching documentation."

Next: run `tcs-helper:docs [topic]`

---

## Concluding Note

> Every skill ends by announcing the next step. If you ever lose orientation, run `/guide` again.
