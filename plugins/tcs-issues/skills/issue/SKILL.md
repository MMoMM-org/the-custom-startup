---
name: issue
description: "Use when creating, listing, closing, or commenting on GitHub issues — when the user says 'create an issue', 'open an issue', 'list issues', 'close issue #N', 'comment on an issue', or runs /issue. New issues are placed on the repo's GitHub Projects (v2) board with status and labels. For issue lifecycle, not parent/child sub-issue linking (see /link-issue)."
user-invocable: true
argument-hint: "[create | list | close | comment] [issue number] [options]"
allowed-tools: Bash, Read, AskUserQuestion
---

## Persona

**Active skill: tcs-issues:issue**

Manage the GitHub issue lifecycle from the CLI. Creating an issue is not just `gh issue
create` — a new issue is placed on the repo's Project (v2) board with a status and labels so
it shows up where work is tracked. Read live state via `gh`, confirm before every write, and
report the issue number and URL so the user can act on it.

## Interface

```
IssueDraft {
  title: string
  body: string
  labels: string[]
  epic: number | null       // parent issue; linked via the link-issue sub-issue recipe
}

State {
  args = $ARGUMENTS
  mode: create | list | close | comment
  owner: string
  repo: string
  projectNumber: number | null
}
```

**In scope:** Creating an issue (with board placement + status + labels), listing/filtering
issues, closing an issue (optionally with a comment), and commenting on an issue.

**Out of scope:** Parent/child sub-issue linking (that is `/link-issue`); moving board items
between columns after creation; merging PRs; editing issue bodies in bulk.

## Constraints

**Always:**
- Auto-detect `owner/repo` from git via `gh repo view`; never ask the user for it.
- Read live issue/board state via `gh` — do not rely on session memory.
- Confirm with the user before any write (create, close, comment, board edit), showing the
  exact issue and content first.
- On project ambiguity (multiple or none), `AskUserQuestion` — never guess which board.

**Never:**
- Create or close an issue without explicit confirmation.
- Invent labels, milestones, or assignees the user did not supply or confirm.
- Link parent/child relationships here — delegate to `/link-issue`.

## Reference Materials

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

Resolve `mode` from `$ARGUMENTS` (first token). If absent, infer from the request; if still
ambiguous, `AskUserQuestion` (Create / List / Close / Comment).

match (mode) {
  create  => steps 3, 4
  list    => step 5
  close   => step 6
  comment => step 7
}

### 3. Create the issue

Gather `IssueDraft` from the request. Ask for any missing `title`; `body`, `labels`, and
`epic` are optional. Show the draft and confirm before writing.

```bash
gh issue create --repo "<owner>/<repo>" --title "<title>" --body "<body>" \
  $( [ -n "<labels>" ] && printf -- '--label %q ' <each label> )
```

Capture the printed issue URL and number.

### 4. Place it on the Project board

Resolve the board the same way `/pickup` does — explicit arg → `[tcs] project` in
startup.toml → auto-detect:

```bash
_extract_project() {
  sed -n '/^\[tcs\]/,/^\[/p' "$1" | grep '^project' | head -1 | sed 's/project[[:space:]]*=[[:space:]]*//' | tr -d '"'"'"' '
}
TCS_PROJECT=""
[ -f "$HOME/.claude/startup.toml" ] && { _v=$(_extract_project "$HOME/.claude/startup.toml"); [ -n "$_v" ] && TCS_PROJECT="$_v"; }
[ -f ".claude/startup.toml" ] && { _v=$(_extract_project ".claude/startup.toml"); [ -n "$_v" ] && TCS_PROJECT="$_v"; }
```

If no project resolves, auto-detect with `gh project list --owner <owner> --format json`. On
multiple or none, `AskUserQuestion`. With a `projectNumber`, add the new issue and set status:

```bash
gh project item-add <projectNumber> --owner <owner> --url <issueUrl> --format json   # capture .id
gh project field-list <projectNumber> --owner <owner> --format json                  # Status field id + option id
gh project item-edit --id <itemId> --project-id <projectId> \
  --field-id <statusFieldId> --single-select-option-id <optionId>                     # default: Todo
```

If the user named an `epic`, hand off: tell them to run `/link-issue link <newIssue> under
<epic>` (this skill does not link). Then emit the create result block.

### 5. List issues

```bash
gh issue list --repo "<owner>/<repo>" --json number,title,state,labels,assignees,url \
  $( [ -n "<state>" ]    && echo --state "<state>" ) \
  $( [ -n "<label>" ]    && echo --label "<label>" ) \
  $( [ -n "<assignee>" ] && echo --assignee "<assignee>" )
```

Default `--state open`. Emit the list result block (one issue per line).

### 6. Close an issue

Resolve the issue number from `$ARGUMENTS`. Confirm. Optional closing comment via `--comment`.

```bash
gh issue close <number> --repo "<owner>/<repo>" $( [ -n "<comment>" ] && echo --comment "<comment>" )
```

### 7. Comment on an issue

Resolve the issue number and comment body (ask if missing). Confirm, then:

```bash
gh issue comment <number> --repo "<owner>/<repo>" --body "<body>"
```

### 8. Report

Read [reference/output-format.md](reference/output-format.md) and emit the block for the mode.
