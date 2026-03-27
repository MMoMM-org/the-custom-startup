# Conflict Detection Reference

Detailed algorithm for file conflict detection in parallel agent dispatch.

Inspired by centminmod batch-operations patterns: explicit phase separation and conflict grouping before any dispatch begins.

---

## Core Principle

**Group before dispatch.** Never dispatch agents speculatively and resolve conflicts after the fact. All conflict analysis must complete — and HIGH risk pairs must be resolved — before the first agent is dispatched.

---

## Risk Matrix

| Condition | Risk Level | Action |
|-----------|-----------|--------|
| Task A and Task B both write the **same file** | HIGH | Offer: worktree isolation / serialize / proceed anyway |
| Task A and Task B write **different files in the same directory** | MEDIUM | Note in report; dispatch proceeds |
| Task A and Task B have **no shared write paths or directories** | NONE | Dispatch freely |
| Task B **reads a file Task A writes** | DEPENDENCY | Re-order to serial: A then B |

### HIGH Risk — Examples

```
T1 writes: src/auth/session.ts
T2 writes: src/auth/session.ts
=> HIGH: same file
```

```
T1 writes: db/migrations/001_users.sql
T3 writes: db/migrations/001_users.sql
=> HIGH: same file (even if content differs — migrations are append-only by convention)
```

### MEDIUM Risk — Examples

```
T1 writes: src/auth/session.ts
T2 writes: src/auth/middleware.ts
=> MEDIUM: same directory (src/auth/), different files
```

```
T1 writes: tests/unit/auth_test.ts
T2 writes: tests/unit/user_test.ts
=> MEDIUM: same directory (tests/unit/), different files
```

### NONE Risk — Examples

```
T1 writes: src/auth/session.ts
T2 writes: src/payments/invoice.ts
=> NONE: disjoint directories
```

```
T1 writes: frontend/components/Button.tsx
T2 writes: backend/routes/health.py
=> NONE: disjoint subsystems
```

### DEPENDENCY — Examples

```
T1 writes: src/db/schema.ts  (defines UserRecord type)
T2 reads:  src/db/schema.ts  (imports UserRecord)
=> T2 dependsOn T1 — serialize: T1 must complete first
```

---

## Conflict Detection Algorithm

```
Phase 1: Extract write targets for all tasks (see below)
Phase 2: Detect sequential dependencies (read-after-write)
Phase 3: Build conflict matrix for remaining parallel pairs
Phase 4: Group tasks by risk level
Phase 5: Resolve HIGH risk pairs with user input (or YOLO auto-proceed)
Phase 6: Dispatch approved groups
```

### Phase 1: Write Target Extraction

#### Pattern-Based Inference

Scan each task description for the following signals:

**Explicit path indicators:**
- Quoted paths: `"src/auth/session.ts"`, `'lib/utils.js'`
- Backtick paths: `` `components/Button.tsx` ``
- Extension patterns: `.ts`, `.tsx`, `.js`, `.py`, `.go`, `.rs`, `.sql`, `.md`, `.json`, `.yaml`, `.toml`

**Verb indicators (the task WILL write these paths):**
- "create `<path>`"
- "write to `<path>`"
- "edit `<path>`"
- "update `<path>`"
- "modify `<path>`"
- "add to `<path>`"
- "generate `<path>`"
- "scaffold `<path>`"
- "implement `<path>`"

**Structural indicators (infer paths from module/feature names):**
- "add auth module" → likely `src/auth/` or `lib/auth/`
- "create users migration" → likely `db/migrations/` or `prisma/migrations/`
- "write Button component" → likely `src/components/` or `components/`

#### Confirmation Search

After inference, confirm or expand with a targeted file search:

```bash
# Check if an inferred path exists
if command -v fd &>/dev/null; then
  fd --type f "<filename_pattern>" <scope_dir>
else
  find <scope_dir> -type f -name "<filename_pattern>"
fi

# Search for references to an inferred module
if command -v rg &>/dev/null; then
  rg --files-with-matches "<module_name>" <scope_dir>
else
  grep -rl "<module_name>" <scope_dir>
fi
```

Use confirmed paths when available; fall back to inferred paths when files don't exist yet (new file creation).

#### Target Classification

For each path found:
- **Write target**: task description includes a write verb + the path
- **Read target**: task description includes "read", "import", "use", "reference" + the path, with no write verb
- **Ambiguous**: no clear verb — classify as write target (conservative)

---

## Conflict Matrix Construction

```
conflicts = []

for each pair (A, B) where A.id < B.id:
  sharedWrites = intersection(A.writeTargets, B.writeTargets)

  if sharedWrites is not empty:
    conflicts.append({taskA: A.id, taskB: B.id, risk: HIGH, sharedPaths: sharedWrites})
    continue

  sharedDirs = intersection(parent_dirs(A.writeTargets), parent_dirs(B.writeTargets))

  if sharedDirs is not empty:
    conflicts.append({taskA: A.id, taskB: B.id, risk: MEDIUM, sharedPaths: sharedDirs})
    continue

  conflicts.append({taskA: A.id, taskB: B.id, risk: NONE, sharedPaths: []})
```

Where `parent_dirs(paths)` returns the immediate parent directory of each path.

---

## Dependency Detection Algorithm

```
dependencies = []

for each pair (A, B):
  for each path in A.writeTargets:
    if path in B.readTargets:
      dependencies.append({before: A.id, after: B.id, path: path})
  for each path in B.writeTargets:
    if path in A.readTargets:
      dependencies.append({before: B.id, after: A.id, path: path})
```

Re-order execution groups:
1. Build a directed graph from dependency edges.
2. Topological sort to produce execution order.
3. Tasks with no dependencies on each other → parallel group.
4. Tasks with dependencies → serial groups, ordered by topological sort.

---

## HIGH Risk Resolution Options

When a HIGH risk pair is detected, present exactly three options:

### Option 1: Worktree Isolation

Create a git worktree per conflicting task, dispatch each agent to its own worktree, merge manually after:

```bash
git worktree add ../worktree-T1 HEAD
git worktree add ../worktree-T2 HEAD
# Dispatch T1 in ../worktree-T1, T2 in ../worktree-T2
# After both complete:
# git diff ../worktree-T1/<path> ../worktree-T2/<path>
# Manually merge the file
# git worktree remove ../worktree-T1
# git worktree remove ../worktree-T2
```

Best for: tasks that make substantive, non-overlapping changes to the same file.

### Option 2: Serialize Tasks

Run conflicting tasks sequentially. The first task completes and commits; the second task receives the updated file as its starting point.

Best for: tasks that build on each other's output (but were initially assumed independent).

### Option 3: Proceed Anyway

Dispatch in parallel, accept that merge conflicts will need resolution afterward.

Best for: tasks making changes to clearly different sections of the same file (e.g., different functions in a large module).

---

## centminmod Batch-Operations Inspiration

The centminmod batch-operations pattern enforces strict phase separation:

1. **Analysis phase** — scan all targets, build full conflict map; no work starts
2. **Grouping phase** — sort tasks into: parallel groups, serial chains, isolated tasks
3. **Approval phase** — user reviews grouped plan before any execution
4. **Execution phase** — dispatch approved groups; parallel within group, serial across groups
5. **Collection phase** — gather all results before presenting any

Key insight: treating parallel dispatch as a **planned batch operation** (not a fire-and-forget) makes conflict recovery predictable and user-controlled.
