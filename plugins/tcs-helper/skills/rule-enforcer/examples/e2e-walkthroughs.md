# Rule Enforcer — End-to-End Walkthroughs

Two full-path scenarios to validate the rule-enforcer skill in a live session.
Execute these manually in a fresh Claude Code session after the skill is indexed.

For each scenario, capture the actual AskUserQuestion option text, the actual
Step 6 mechanism output, and the final Step 8 path taken. Record results in
`self-test-results.md`.

---

## Scenario A: Primary Journey — intercept hook → triage → CI scaffolding

### Setup

- Fresh Claude Code session (rule-enforcer skill indexed).
- Intercept hook installed (Phase 1 T1.3 — UserPromptSubmit hook that detects
  recurrence-signal phrases).

### Steps

**Step 1 — Trigger via natural language prompt**

User submits:
> `I keep forgetting to bump marketplace.json`

**Expected**: The intercept hook detects the phrase `keep forgetting` and injects
a suggestion line before Claude processes the prompt:

```
[rule-enforcer] Recurrence signal detected ('keep forgetting'). Consider /enforce-rule "I keep forgetting to bump marketplace.json" to triage.
```

Claude responds to the original prompt normally. The suggestion line is visible
in the session output.

**Step 2 — Invoke the skill directly**

User runs:
> `/enforce-rule "I keep forgetting to bump marketplace.json"`

**Expected**: Skill announces itself, echoes the rule, and asks Q1.

**Step 3 — Answer Q1: Recurring**

Select: `Recurring — I've seen this before (memory has failed me)`

**Expected**: Skill proceeds to Q2.

**Step 4 — Answer Q2: Yes**

Select: `Yes — there is a specific tool call, git boundary, or CI event I can name`

**Expected**: Skill proceeds to Q3.

**Step 5 — Answer Q3: PR/merge to main**

Select the option matching `PR/merge to main` (with or without parenthetical).

**Expected**: Skill proceeds to Q4.

**Step 6 — Answer Q4: Auto-fix**

Select: `Auto-fix — fix it for me automatically without asking`

**Expected**: Step 6 looks up matrix row `Q3 = PR/merge to main` × `Q4 = Auto-fix`
and resolves mechanism = `CI workflow (auto-PR or commit: detects and patches the violation automatically)`.

**What to capture**: Copy the exact mechanism string the skill outputs at Step 6.

**Step 7 — Confirm**

Skill presents the mechanism for confirmation. Select: `Proceed`

**Expected**: Step 8 executes.

**Step 8 — CI scaffolding preview**

**Expected**:
- Skill reads both CI templates from `plugins/tcs-helper/skills/rule-enforcer/templates/`
- Renders a preview of the workflow YAML and the detection/remediation shell script
- Presents an AskUserQuestion with options including `Write`, `Refine`, `Cancel`

**What to capture**: Copy the AskUserQuestion option labels verbatim.

**Step 9 — Cancel**

Select: `Cancel`

**Expected outcome**: No files written. Session ends cleanly. Preview was
human-readable. No errors or stack traces anywhere in the session.

### What to verify

- [ ] Intercept hook fired and injected the suggestion line
- [ ] Q1–Q4 were asked in order, no skips
- [ ] Mechanism at Step 6 = `CI workflow (auto-PR or commit: detects and patches the violation automatically)`
- [ ] Step 8 rendered a human-readable YAML preview
- [ ] Cancel left the repo clean (no new files)

---

## Scenario B: Secondary Journey — direct invocation (no trigger phrase)

### Setup

- Same fresh session (intercept hook may or may not be installed — irrelevant,
  since no trigger phrase is used in this scenario).

### Steps

**Step 1 — Invoke the skill directly with a non-trigger-phrase rule**

User runs:
> `/enforce-rule "tag commits by phase number for traceability"`

**Expected**: No intercept-hook suggestion fires (no recurrence-signal phrase).
Skill announces itself, echoes the rule, and asks Q1.

**Step 2 — Answer Q1: First time**

Select: `First time — I haven't tried memory yet`

**Expected**: Q1 short-circuit fires. Skill skips Q2–Q4 entirely and routes
directly to the memory-add hand-off. This is the "No-judgment short-circuit"
path — a first-time occurrence belongs in memory, not in enforcement escalation.

**What to capture**: Confirm that Q2, Q3, Q4 are NOT asked.

**Step 3 — memory-add hand-off**

**Expected**: Step 8 invokes:
> `Skill(tcs-helper:memory-add)` with `type=feedback` and a strong-language hint

The rule is passed to memory-add prefixed with `MUST`, `NEVER`, or `ALWAYS`
to maximize enforcement weight. Example:
> `ALWAYS tag commits by phase number for traceability`

**What to capture**: Copy the exact hand-off arguments the skill passes to
`tcs-helper:memory-add`.

**Step 4 — Confirm hand-off**

User confirms the memory-add invocation.

**Expected outcome**: `tcs-helper:memory-add` invokes correctly and saves the
rule to the appropriate memory file. Session ends without errors.

### What to verify

- [ ] No intercept-hook suggestion line appeared (no trigger phrase)
- [ ] Q2, Q3, Q4 were skipped after Q1 = First time
- [ ] Step 8 routed to `tcs-helper:memory-add` (not a hook or CI skill)
- [ ] Strong-language prefix (`MUST`/`NEVER`/`ALWAYS`) was applied to the rule
- [ ] memory-add completed successfully
