---
name: link-issue
description: "Use when linking a GitHub issue as a sub-issue (child) of a parent, unlinking a sub-issue, or listing an issue's children or parent epic — when the user says 'make #9 a sub-issue of #33', 'link issue under epic', 'unlink sub-issue', 'list sub-issues', 'show children of', or runs /link-issue. Uses the GitHub sub-issue GraphQL API."
user-invocable: true
argument-hint: "[link <child> under <parent> | unlink <child> | list <parent>]"
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
  mode: link | unlink | list
  owner: string
  repo: string
  parent: number | null
  child: number | null
}
```

**In scope:** Linking a child issue under a parent, unlinking a child, and listing a parent's
children plus its own parent.

**Out of scope:** Creating issues (that is `/issue`); reordering children; closing issues;
board status changes.

## Constraints

**Always:**
- Auto-detect `owner/repo` from git via `gh repo view`; never ask the user for it.
- Resolve issue numbers to node-IDs immediately before any GraphQL call — numbers do not work.
- Confirm the parent/child pair with the user before `link` or `unlink`.
- Read live state via `gh` — do not rely on session memory.

**Never:**
- Run a link/unlink mutation without explicit confirmation.
- Pass issue numbers where the GraphQL API expects node-IDs.

## Reference Materials

- [GraphQL Recipes](reference/graphql.md) — the verified mutations and queries
- [Output Format](reference/output-format.md) — result blocks for each mode

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
