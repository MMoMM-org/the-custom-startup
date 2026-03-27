---
name: receive-review
description: "Structured code review response workflow. Process each review item with technical rigor — classify as Accept/Push Back/Defer/Question before acting."
user-invocable: true
argument-hint: "[paste review comments or provide PR URL]"
allowed-tools: Read, Bash, AskUserQuestion, WebFetch
---

## Persona

**Active skill: tcs-workflow:receive-review**

Act as a disciplined code review responder. For every review item, classify before acting. Apply fixes with evidence. Push back only with technical citations — never on preference.

**Review Input**: $ARGUMENTS

## Interface

```
Classification = Accept | Push Back | Defer | Question

ReviewItem {
  id: string              // e.g. R1, R2, R3
  location?: string       // file:line if given
  concern: string         // what the reviewer flagged
  proposed_fix?: string   // reviewer's suggested fix
  classification: Classification
}

ItemResult {
  item: ReviewItem
  classification: Classification
  action: string          // what was done or written
  status: resolved | listed | pending
}

State {
  input = $ARGUMENTS
  items: ReviewItem[]
  results: ItemResult[]
  mode: interactive | yolo
}
```

## Constraints

**Always:**
- Parse all review items before acting on any.
- Classify every item before applying a fix or writing a response.
- Push Back responses must cite a specific `file:line` or spec reference. "I prefer X" is not a valid reason.
- Accept path: apply fix first, then invoke `Skill(tcs-workflow:verify)` before marking resolved.
- Defer: record the item in `docs/ai/memory/context.md` under `## Deferred Review Items` with the reason.
- Output a structured summary table when all items are processed.

**Never:**
- Apply a fix without first classifying the item as Accept.
- Push Back without a concrete technical reference.
- Mark an item resolved before running verify on Accept fixes.
- Skip items — every item in the input must appear in the summary table.

## YOLO Mode

When `[ "${YOLO:-false}" = "true" ]`:
- Auto-classify unambiguous items and apply Accept fixes without prompting.
- For ambiguous items (conflicting signals, no clear code reference), default to Question.
- List Push Back and Defer items in the summary for manual follow-up rather than halting.
- Still invoke `Skill(tcs-workflow:verify)` after applying fixes.

## Workflow

### Step 1 — Parse Input

Detect input format from $ARGUMENTS:

```
match ($ARGUMENTS) {
  starts with "http" | github.com   => fetch with WebFetch or `gh pr view --comments <url>`
  /^\d+$/                           => run `gh pr view --comments $ARGUMENTS`
  blank                             => AskUserQuestion "Paste your review comments or provide a PR URL/number."
  default                           => treat as pasted review text
}
```

Extract each review item. Assign sequential IDs: R1, R2, R3...

For each item record:
- `location` — file path and line number if mentioned (e.g. `src/api.ts:42`)
- `concern` — what the reviewer flagged, in their words
- `proposed_fix` — their suggested fix, if given

If fewer than 1 item is found, ask: "I could not parse any review items. Can you paste the review comments directly?"

### Step 2 — Classify Items

**Interactive mode** — present each item in turn:

```
Item R1 — [location if known]
Concern: [concern]
Proposed fix: [proposed_fix or "none given"]

Classify:
  (A) Accept — apply the fix
  (P) Push Back — provide technical counterargument
  (D) Defer — record for later with reason
  (Q) Question — ask reviewer for clarification
  (auto) Let me suggest a classification
```

If user selects `auto`, apply this heuristic:

```
match (item) {
  proposed_fix is valid and aligns with codebase  => Accept
  proposed_fix contradicts spec or existing code   => Push Back
  out of scope for current branch                  => Defer
  concern is ambiguous or missing context          => Question
}
```

Confirm the suggestion before proceeding.

**YOLO mode** — auto-classify all items using the heuristic above without prompting. Present a summary of classifications and proceed.

### Step 3 — Process by Classification

Process each item according to its classification:

#### Accept

1. Read the relevant file(s) to understand context.
2. Apply the fix using Edit or Bash as appropriate.
3. Invoke `Skill(tcs-workflow:verify)` to confirm the fix does not break anything.
4. On verify pass: mark `status = resolved`.
5. On verify fail: halt that item, set `status = pending`, note the failure in the summary.

#### Push Back

Write a technical counterargument. It must include:
- The specific `file:line` or spec/doc reference that conflicts with the proposed change.
- A clear explanation of why the change would break or contradict that reference.
- A proposed alternative if one exists.

Template:
```
R[n] Push Back: [one-sentence summary]

This change conflicts with [file:line | spec reference]:
  > [relevant excerpt]

[Explanation of the conflict.]

[Alternative approach, if any.]
```

Mark `status = listed`.

#### Defer

Record in `docs/ai/memory/context.md` under `## Deferred Review Items`:

```markdown
### R[n] — [short title] ([date])
- Location: [file:line or "general"]
- Concern: [concern]
- Reason deferred: [reason]
- Branch: [current branch from `git branch --show-current`]
```

Create the section if it does not exist. Append if it does.

Mark `status = listed`.

#### Question

Formulate a clarifying question for the reviewer. The question must:
- Reference the specific location or context of the concern.
- Ask exactly what is unclear (not a generic "can you clarify?").

Template:
```
R[n] Question for reviewer:

Regarding [location or topic] — [specific question that resolves the ambiguity].
```

Mark `status = listed`.

### Step 4 — Output Summary

After all items are processed, output the structured summary table:

```
## Review Response Summary

| Item | Location | Concern (short) | Classification | Action Taken | Status |
|------|----------|-----------------|----------------|--------------|--------|
| R1   | src/api.ts:42 | Null check missing | Accept | Fix applied, verify passed | resolved |
| R2   | general | Rename variable | Push Back | Conflicts with spec §3.2 | listed |
| R3   | auth flow | Add rate limiting | Defer | Out of scope for this branch | listed |
| R4   | README.md | Clarify setup step | Question | Asked for clarification | listed |

**Accepted & Resolved:** [count]
**Pushed Back:** [count] — see counterarguments above
**Deferred:** [count] — recorded in docs/ai/memory/context.md
**Questions:** [count] — see questions above for reviewer
```

### Step 5 — Conclude

If all items have `status = resolved`:
```
All items processed and resolved. Run `/finish-branch` if work is complete.
```

If any items have `status = listed`:
```
[N] items require follow-up (see summary above).
When reviewer responds to questions or deferred items are ready, re-run `/receive-review` with the new comments.
```

## Integration Notes

- **`review`** generates findings that feed into this skill as review items.
- **`verify`** is invoked automatically on the Accept path — do not skip it.
- **`finish-branch`** is the natural next step when all items are resolved.
- Deferred items in `docs/ai/memory/context.md` persist across sessions for future follow-up.
