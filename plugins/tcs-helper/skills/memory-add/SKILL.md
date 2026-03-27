---
name: memory-add
description: Capture and route session learnings to the correct scope and category file. Run after any session where corrections or new knowledge emerged. Auto-triggers on: reflect, remember, learned, note this, add to memory, route this.
user-invocable: true
argument-hint: "[learning text] | --review-yolo"
allowed-tools: Read, Write, Edit, Bash
---

## Persona

**Active skill: tcs-helper:memory-add**

Capture learnings from this session and route each to the correct scope and category file.

## Interface

```
State {
  learnings: Learning[]       // from queue or argument or manual
  routed: RoutedLearning[]    // scope + category + file + content
  skipped: Learning[]         // duplicates detected
  unclassified: Learning[]    // needs user decision
  yolo: boolean               // YOLO=true env var detected
}
```

## Workflow

### Step 1 — Detect mode

- If argument is `--review-yolo`: go to YOLO Review workflow (see below)
- Check `YOLO` environment variable: if `YOLO=true`, set `yolo: true`
- If `$ARGUMENTS` provided: add as manual learning(s)
- Otherwise: read queue from `~/.claude/projects/<encoded-cwd>/learnings-queue.json`
  - If queue is empty and no arguments: ask "What did you learn this session?"

### Step 2 — Classify each learning (AI reasoning)

For each learning, classify using these keyword signals:

| Keywords | Category | Target |
|---|---|---|
| naming, convention, style, format, indent, case | general | docs/ai/memory/general.md |
| build, CI, deploy, script, command, tool, api, client | tools | docs/ai/memory/tools.md |
| domain, entity, rule, model, business, contract | domain | docs/ai/memory/domain.md |
| decided, chose, decision, tradeoff, architecture, why | decisions | docs/ai/memory/decisions.md |
| working on, focus, sprint, current, this week | context | docs/ai/memory/context.md |
| bug, error, fix, workaround, issue, broken, resolved | troubleshooting | docs/ai/memory/troubleshooting.md |
| personal, always prefer, never use, my workflow | global | ~/.claude/includes/ |

If unclassified → AskUserQuestion: "Which file should this go to? [show list of options]"

### Step 3 — Determine scope

- `personal` / `workflow` → global scope: `~/.claude/includes/memory-<category>.md`
- Explicitly project-scoped fact → project memory (if configured in CLAUDE.md)
- Default → repo scope: `docs/ai/memory/{category}.md`

### Step 4 — Deduplication check

For each learning, Read the target file.
If a semantically identical fact already exists (same meaning, possibly different wording): skip silently, add to `skipped[]`.
Cross-scope duplicates are NOT checked here (handled by memory-cleanup).

### Step 5 — Write (or stage if YOLO)

**Normal mode:** Append to target file:
```
<!-- YYYY-MM-DD -->
- [learning text]
```
Then update `memory.md` index: change `[updated: YYYY-MM-DD]` for the affected file.

**YOLO mode (`YOLO=true`):** Do NOT write to target files. Instead, append to `docs/ai/memory/yolo-review.md`:
```markdown
- [ ] **Target:** `docs/ai/memory/tools.md`
  [learning text]
  *(YYYY-MM-DD)*
```

### Step 6 — Report

Show summary:
- ✓ Routed N learnings: [file → count]
- · Skipped N (duplicates)
- ? Unclassified: [if any, already resolved via AskUserQuestion]

Clear processed items from queue file.

---

## YOLO Review Workflow (`--review-yolo`)

1. Read `docs/ai/memory/yolo-review.md`
2. If file doesn't exist or is empty: report "No pending YOLO entries"
3. For each unchecked entry: show target file and content
4. AskUserQuestion: "Accept all / Select / Skip all"
5. For accepted entries: write to target file using normal append format
6. Remove accepted entries from yolo-review.md (leave rejected ones, or clear if all accepted)
7. Report: N entries written, N rejected

## Always
- Read the target file before appending (deduplication check)
- Add date comment before new entries
- Update memory.md index last-updated date after any repo-scope write
- Exit 0 and report clearly even when nothing was routed

## Never
- Write to target files in YOLO mode (only to yolo-review.md)
- Silently fail — always report what was done and what was skipped
- Create new memory files that aren't in the 6 standard categories (use existing files or ask)
