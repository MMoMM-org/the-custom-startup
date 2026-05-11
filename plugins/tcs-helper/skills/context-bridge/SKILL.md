---
name: context-bridge
description: Use PROACTIVELY before the user runs /clear or /compact to checkpoint the current session so the SessionStart hook can auto-restore continuity in the next session. MUST BE USED when the user says "before /clear", "before /compact", "save session state", "session handoff to self", "checkpoint before context reset", "preserve context across compact", "snapshot the session", or "I'm about to clear/compact".
allowed-tools: Read, Write, Bash, Grep, Glob, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:context-bridge**

Act as a session-state archivist that captures continuity-critical state before a context reset (`/clear` or `/compact`) and recommends which of the two better fits the next planned work. The companion SessionStart hook restores the snapshot automatically in the next session — this skill only writes it.

## Interface

CheckpointSnapshot {
  created: ISO-8601 string
  branch: string
  recommendation: clear | compact
  recommendation_reason: string
  where_i_left_off: string
  open_todos: [TodoItem]
  in_flight_specs: [string]
  active_files: [FileRef]
  recent_decisions: [string]
  next_steps: [string]
}

TodoItem {
  status: pending | in_progress | completed
  content: string
}

FileRef {
  path: string
  reason: string
}

State {
  checkpoint_path = ".claude/.session-checkpoint.md"
  recommendation: clear | compact
}

**In scope:** Persisting state from the current session to the repo-local checkpoint file. Classifying whether `/clear` or `/compact` better fits the next planned work.

**Out of scope:** Invoking `/clear` or `/compact` (the user runs the command). Restoring the snapshot (handled by the SessionStart hook in tcs-helper).

## Constraints

**Always:**
- Write the checkpoint file before announcing the recommendation — the user relies on it being there when they run `/clear` or `/compact`.
- Ground the recommendation in observable signals (open in-progress TODOs, branch dirtiness, recent edits, user-stated next step).
- State the recommended slash command prominently in the final message — the user must see `/clear` or `/compact` clearly.
- Verify `.claude/.session-checkpoint.md` is gitignored; if not, append the pattern to `.gitignore` and tell the user.

**Never:**
- Invoke `/clear` or `/compact` yourself — only the user can.
- Embed full file contents, secrets, env vars, or large code blocks in the checkpoint — use `path:line` references and one-line summaries only.
- Overwrite an existing checkpoint silently if it was written within the last 5 minutes — surface a confirmation via AskUserQuestion.
- Skip writing the file because data feels incomplete — partial state beats no state.

## Workflow

### 1. Gather Session State

Collect signals in parallel:

1. **Git state**: `git rev-parse --abbrev-ref HEAD`, `git status --short`, `git log --oneline -5`.
2. **Open todos**: read the current TaskList; record items with status `pending` or `in_progress`.
3. **In-flight specs**: `Glob` for `docs/XDD/specs/*/README.md` and note any with phase != completed.
4. **Active files**: identify 3–7 files the user/assistant has been editing or referencing most recently in this turn-window. Note `path` + 1-line `reason`.
5. **Recent decisions**: scan the recent conversation for explicit choices the user made or constraints they stated.
6. **Next step**: what the user said they want to do next. If unclear after scanning, AskUserQuestion: "What's the immediate next step after /clear or /compact?"

### 2. Classify clear vs compact

Apply the decision table — first match wins:

| Signal pattern | Recommendation |
|----------------|----------------|
| User said "switching to different task" or "done with this" | clear |
| Branch is clean AND no in-progress TODOs AND no in-flight specs | clear |
| Active in-flight spec OR dirty branch OR in-progress TODOs OR pending edits | compact |
| Conversation has grown large but user wants to continue same feature | compact |
| Genuinely ambiguous | AskUserQuestion: "Continuing same work (compact) or switching scope (clear)?" |

Record both the recommendation and a one-line reason.

### 3. Write Checkpoint File

Path: `.claude/.session-checkpoint.md` relative to repo root (discover root with `git rev-parse --show-toplevel`).

Pre-write checks:
1. Create `.claude/` directory if missing.
2. If the file already exists and was written < 5 minutes ago, AskUserQuestion: "Overwrite existing checkpoint?" before proceeding.
3. Verify `.claude/.session-checkpoint.md` is gitignored. If not, append the pattern to `.gitignore` (root) and note it in the final message.

Write the file using this template (Markdown with YAML frontmatter):

```markdown
---
created: <ISO-8601 timestamp>
branch: <branch name>
recommendation: <clear | compact>
recommendation_reason: <one line>
---

# Session Checkpoint

## Where I left off
<1–3 sentences capturing the situation in the user's terms>

## Open TODOs
- [in_progress] <content>
- [pending] <content>

## In-flight specs
- <docs/XDD/specs/NNN-name> — phase <N> — <one-line status>

## Active files
- <path:line> — <why this file matters>

## Recent decisions
- <one-line decision>

## Next steps
1. <imperative step>
2. <imperative step>
```

Sections that have no entries: render the heading and the line `_(none)_`.

### 4. Announce Recommendation

Output to the user (concise — they're about to context-switch):

1. Confirmation that the checkpoint was written, with the absolute path.
2. The recommendation in a single line: `Recommendation: /compact — <reason>` or `Recommendation: /clear — <reason>`.
3. The next action they should take (the exact slash command to run).
4. If `.gitignore` was updated, mention it.

Do not invoke the slash command. Do not summarize the whole checkpoint — they can read the file. Stop after the announcement.
