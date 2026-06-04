---
name: link-issue
description: "Use when linking a GitHub issue as a sub-issue (child) of a parent, unlinking a sub-issue, listing an issue's children or parent epic, or bulk-backfilling every sub-issue link from `Part of #N` / `Epic: #N` references across the board — when the user says 'make #9 a sub-issue of #33', 'link issue under epic', 'unlink sub-issue', 'list sub-issues', 'show children of', 'sync sub-issues', 'backfill the epics', 'link all the children', or runs /link-issue. Uses the GitHub sub-issue GraphQL API."
user-invocable: true
argument-hint: "[link <child> under <parent> | unlink <child> | list <parent> | sync]"
allowed-tools: Bash, Read, AskUserQuestion
---

## Persona

**Active skill: tcs-issues:link-issue**

Manage native GitHub sub-issue (parent ↔ child) relationships. The relationship lives behind
the GraphQL API and keys on node-IDs, not issue numbers — so the work is: resolve numbers to
node-IDs, run the right mutation or query, then report the linked pair. Confirm before any
link or unlink write.

## Interface

```
State {
  args = $ARGUMENTS
  mode: link | unlink | list | sync
  owner: string
  repo: string
  parent: number | null
  child: number | null
}
```

**In scope:** Linking a child issue under a parent, unlinking a child, listing a parent's
children plus its own parent, and `sync` — backfilling native links for every `Part of #N`
reference across the board in one idempotent pass.

**Out of scope:** Creating issues (that is `/issue`); reordering children; closing issues;
board status changes.

## Constraints

**Always:**
- Auto-detect `owner/repo` from git via `gh repo view`; never ask the user for it.
- Resolve issue numbers to node-IDs immediately before any GraphQL call — numbers do not work.
- Confirm the parent/child pair with the user before `link` or `unlink`.
- For `sync`, show the full preview (epics → children, plus anomalies) and get one confirmation
  before applying any link.
- Read live state via `gh` — do not rely on session memory.

**Never:**
- Run a link/unlink/sync mutation without explicit confirmation.
- Pass issue numbers where the GraphQL API expects node-IDs.
- Hand-roll the bulk discovery/link loop inline — `sync` runs the bundled script.

## Reference Materials

- [GraphQL Recipes](reference/graphql.md) — the verified mutations and queries
- [Output Format](reference/output-format.md) — result blocks for each mode
- `scripts/sync_subissues.py` — discovery + idempotent bulk-link backend for `sync`

## Workflow

### 1. Preflight

```bash
command -v gh >/dev/null || { echo "gh not found — install GitHub CLI."; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Not authenticated — run: gh auth login"; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not inside a git repo."; exit 1; }
gh repo view --json owner,name -q '.owner.login + "/" + .name'
```

Stop on any hard failure. Set `owner` and `repo` from the last line.

### 2. Route by mode

Resolve `mode` and the issue numbers from `$ARGUMENTS`. If `mode` is ambiguous, `AskUserQuestion`
(Link / Unlink / List).

match (mode) {
  link   => steps 3, 4
  unlink => steps 3, 5
  list   => step 6
  sync   => step 7
}

### 3. Resolve node-IDs

For each issue number involved, resolve its node-ID:

```bash
gh issue view <number> --repo "<owner>/<repo>" --json id -q .id
```

### 4. Link child under parent

Confirm the pair (`<child> → child of <parent>`). Read
[reference/graphql.md](reference/graphql.md) and run the `addSubIssue` mutation with the
resolved parent and child node-IDs. Emit the link result block.

### 5. Unlink child from parent

Confirm. Read [reference/graphql.md](reference/graphql.md) and run the `removeSubIssue`
mutation with the resolved node-IDs. Emit the unlink result block.

### 6. List children and parent

Read [reference/graphql.md](reference/graphql.md) and run the children/parent query for the
target issue's node-ID. Emit the list result block (parent line + one child per line with
number, title, state).

### 7. Sync — backfill every declared sub-issue link

Run the backend dry-run (discover all OPEN issues, parse `Part of #N` / `Epic: #N` /
`Parent: #N`, compute the idempotent plan — skips pairs already linked, flags anomalies):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/link-issue/scripts/sync_subissues.py" \
  --owner <owner> --repo <repo> --out "$TMPDIR/subissue-plan.json"
```

Show the printed preview. If the plan is empty, report "already fully linked" and stop.
Otherwise `AskUserQuestion` to confirm (surfacing any anomalies), then apply:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/link-issue/scripts/sync_subissues.py" \
  --apply "$TMPDIR/subissue-plan.json"
```

Emit the sync result block (linked count + any failures). The script calls `gh` without a
shell, so its GraphQL `!` markers are safe — do not reimplement the loop inline.
