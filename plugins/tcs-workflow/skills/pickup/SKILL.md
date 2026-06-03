---
name: pickup
description: "Use when starting or resuming a work session from the GitHub Project board — when the user says 'pick up work', 'what am I working on', 'what's next', 'start from the board', 'resume from the board', or runs /pickup. For orienting from the GitHub Projects (v2) board rather than from local git or plan state."
user-invocable: true
argument-hint: "[project number | issue number | leave blank to resolve from the board]"
allowed-tools: Bash, Read, Grep, AskUserQuestion
---

## Persona

**Active skill: tcs-workflow:pickup**

Orient a coding session from the GitHub Project (v2) board. The board cannot push into the
local CLI, so this skill pulls: find the work item, load its context, create a branch,
propose a plan — then hand control back to the user. It does not implement.

## Interface

```
WorkItem {
  repo: string              // owner/name
  issue: number | null      // null for draft items (skipped)
  title: string
  status: string            // "Todo" | "In Progress" | "Done" | custom
  fields: { [name: string]: string }   // Priority, Track, Area, "Blocked by", ...
}

Context {
  body: string
  labels: string[]
  epic: { number: number, title: string } | null
  blockers: { ref: string, open: boolean }[]   // refs incl. cross-repo owner/repo#N
}

State {
  args = $ARGUMENTS
  owner: string
  repo: string
  projectNumber: number
  target: WorkItem | null
  context: Context | null
  branch: string | null
}
```

**In scope:** Reading the board, loading the chosen item's context, one optional
`Todo → In Progress` flip, and creating a feature branch.

**Out of scope:** Implementing the work; closing issues; merging PRs; moving items to Done;
adding items to the board (these are GitHub's built-in server-side Project workflows).

## Constraints

**Always:**
- Resolve the project by priority: explicit `$ARGUMENTS` number → `[tcs] project` in
  startup.toml → auto-detect. On ambiguity (multiple/none), `AskUserQuestion` — never guess.
- Read live state via `gh`; do not rely on session memory.
- Require a clean working tree before creating a branch — abort if dirty, do not branch.
- End by proposing a numbered plan and stopping with "Say Go to start."

**Never:**
- Implement, edit, or commit code — this skill orients and stops.
- Write to the board except the single `Todo → In Progress` flip in Step 3.
- Post issue comments or any other GitHub write without asking first.
- Move items to Done / add items / link PRs — those run server-side already.

## Reference Materials

- [Output Format](reference/output-format.md) — orientation block template + worked example

## Workflow

### 1. Preflight

```bash
command -v gh >/dev/null || { echo "gh not found — install GitHub CLI."; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Not authenticated — run: gh auth login"; exit 1; }
gh auth status 2>&1 | grep -q "project" || echo "[warn] token may lack 'project' scope — if board reads fail, run: gh auth refresh -s project"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not inside a git repo."; exit 1; }
```

Stop on any hard failure.

### 2. Resolve repo and project

```bash
gh repo view --json owner,name -q '.owner.login + "/" + .name'
```

Set `owner` and `repo`. Resolve `projectNumber` in priority order:

```bash
# startup.toml resolution — bash 3.2 compatible, repo overrides global
_extract_project() {
  sed -n '/^\[tcs\]/,/^\[/p' "$1" | grep '^project' | head -1 | sed 's/project[[:space:]]*=[[:space:]]*//' | tr -d '"'"'"' '
}
TCS_PROJECT=""
[ -f "$HOME/.claude/startup.toml" ] && { _v=$(_extract_project "$HOME/.claude/startup.toml"); [ -n "$_v" ] && TCS_PROJECT="$_v"; }
[ -f ".claude/startup.toml" ] && { _v=$(_extract_project ".claude/startup.toml"); [ -n "$_v" ] && TCS_PROJECT="$_v"; }
```

match (resolution) {
  $ARGUMENTS is a number          => use it as projectNumber
  TCS_PROJECT set (owner/number)  => split on "/", use the number with that owner
  neither                         => auto-detect (below)
}

Auto-detect: `gh project list --owner <owner> --format json`. If exactly one project, use it.
If multiple or none, present them with `AskUserQuestion` and let the user choose (offer to
record the choice in `.claude/startup.toml` under `[tcs] project`).

### 3. Read board items and pick the target

```bash
gh project item-list <projectNumber> --owner <owner> --format json
```

Each item is flattened: `.status`, `.title`, `.priority`, `.track`, `.area` are top-level;
the linked issue is `.content.number` / `.content.type` / `.content.repository`. Custom
fields (e.g. `priority`) appear only when set — treat missing fields as unset.

Skip draft items (`.content.type == "DraftIssue"` or no `.content.number`).
Filter to `.status == "In Progress"`.

match (in-progress count) {
  exactly 1   => that item is `target`
  more than 1 => AskUserQuestion to choose among them
  zero        => list `Todo` items, AskUserQuestion to pick one, then flip it (below)
}

**Todo → In Progress flip** (the only board write). Resolve field/option IDs, then edit:

```bash
gh project field-list <projectNumber> --owner <owner> --format json   # find Status field id + "In Progress" option id
gh project item-edit --id <itemId> --project-id <projectId> \
  --field-id <statusFieldId> --single-select-option-id <inProgressOptionId>
```

### 4. Load context for the target issue

```bash
gh issue view <issue> --repo <owner>/<repo> --json number,title,body,labels,url
```

- **Epic**: scan the body for `Part of #<N>`, `Epic: #<N>`, or `Parent: #<N>`; if found,
  `gh issue view <N>` for its title. Also accept a native sub-issue parent if present.
- **Blockers**: a Project `Blocked by` field is optional and often absent — use it only if
  present in the Step 3 JSON. Always scan the body for `Blocked by #<N>` and cross-repo
  `owner/repo#<N>` references. For each blocker found, check state with `gh issue view`. If
  any is still **open**, warn prominently. If none found, report "Blocked by: none".

### 5. Create the branch

```bash
[ -z "$(git status --porcelain)" ] || { echo "Working tree dirty — commit or stash, then re-run. Not branching."; exit 1; }
```

Branch name `<type>/<issue>-<slug>` from `main`:
- `type`: label `bug` → `fix`; label `documentation`/`docs` → `docs`; otherwise → `feature`.
- `slug`: lowercased issue title, non-alphanumerics → `-`, collapsed, trimmed, ~50 chars.

```bash
git checkout main && git pull --ff-only 2>/dev/null; git checkout -b "<type>/<issue>-<slug>"
```

### 6. Propose a plan and STOP

Read [reference/output-format.md](reference/output-format.md) and emit the orientation block:
chosen item (`<repo>#<issue>`, title, Priority/Track/Area), blocked-by status, created
branch, and a compact numbered plan derived from the issue body. End with **"Say Go to
start."** Suggest `/implement` or `/brainstorm` for the actual work. Do not proceed.
