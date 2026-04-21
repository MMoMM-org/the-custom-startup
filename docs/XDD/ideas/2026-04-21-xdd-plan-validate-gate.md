# Feedback: enforce `validate` as a gate after `xdd-plan`

**Plugin:** `tcs-workflow`
**Skills affected:** `xdd` (orchestrator), `validate` (perspective config)
**Type:** Enhancement — closes a brownfield plan-authoring gap

---

## Problem

In the current XDD flow, `xdd-plan` generates tasks from PRD + SDD.
When a task modifies an **existing file**, the PLAN inherits whatever
picture of that file the SDD paints — including any blind spots.
Nothing in the PRD → SDD → PLAN chain cross-checks the PLAN against
the live target files before `/implement` runs.

The symptom class is anything that depends on the target's current
state: section-name collisions (`Phase N`, `Step N`, headings),
insertion anchors that moved, constraint bullets that duplicate or
contradict existing ones, error-table rows that overlap, interface
signatures the SDD simplified. All of these only surface at
implementation time, when the cost of correction is highest — PRD,
SDD, and PLAN are already committed and referenced.

## Concrete Occurrence

- **Feature:** voice-transcription pre-step for an inbox orchestrator.
- **SDD said:** "add a new Phase 0 before Phase A in inbox-orchestrator."
- **Target file actually had:** pre-existing `### Phase 0 — Resume
  detection` at the exact insertion point.
- **Plan wrote:** "T4.1 Insert Phase 0 in inbox-orchestrator workflow."
- **At implement time:** collision surfaced, forced sub-phase rename
  (`0a`/`0b`), plan/code naming diverged, extra commits to document
  the divergence.

One `Read` of the orchestrator during plan validation would have
caught it.

## Why the Fix Belongs in `xdd` + `validate`, Not `xdd-plan`

- Single responsibility stays clean: `xdd-plan` writes plans,
  `validate` checks them. Don't mix authoring with auditing.
- `validate` already has an **Alignment** perspective whose stated
  purpose is *"verify that documented patterns actually exist in code —
  no hallucinated implementations where a spec describes something
  code doesn't do."* That's the exact symptom.
- The `xdd` orchestrator already invokes `validate` at SDD time (for
  Constitution when present); adding a PLAN-time call is the
  symmetrical completion of that pattern.
- The gate lives on the orchestrator, so users who go through `/xdd`
  can't skip it. Users who call `xdd-plan` directly can still bypass —
  that's a feature, not a bug (direct callers know what they're doing).

## Proposal — two tiny edits

### (1) `skills/xdd/SKILL.md` — add validation step after PLAN

Current Step 6 (Write PLAN):

```markdown
Invoke `Skill(tcs-workflow:xdd-plan)`.

Focus: task sequencing and dependencies. Scope: what and in what
order — defer duration estimates.

AskUserQuestion: Finalize specification (recommended) | Revisit PLAN
```

Proposed:

```markdown
Invoke `Skill(tcs-workflow:xdd-plan)`.

Focus: task sequencing and dependencies. Scope: what and in what
order — defer duration estimates.

After `xdd-plan` returns, invoke `Skill(tcs-workflow:validate)` with
the spec ID. Surface Alignment findings — plan tasks that modify
existing files may reference targets whose current state has drifted
from the SDD's picture.

AskUserQuestion: Finalize specification (recommended) | Revisit PLAN
```

### (2) `skills/validate/reference/perspectives.md` — include Alignment in Spec Validation

Current perspective-selection table (line 98):

```markdown
| **Spec Validation** | ✅ Completeness, 🔗 Consistency, 📐 Coverage + ambiguity detection |
```

Proposed:

```markdown
| **Spec Validation** | ✅ Completeness, 🔗 Consistency, 📍 Alignment, 📐 Coverage + ambiguity detection |
```

Without this second edit, Step 6's `validate` call would run but
skip the one perspective that actually catches the bug.

---

## Open Design Question — for TCS-side brainstorm

Alignment-after-PLAN is useful when the plan touches existing files.
For **greenfield** features (plan only has `Create new file X`
tasks), running Alignment is noise — there's no code to align
against yet.

Two ways to handle that:

### Option A — silent no-op

`validate` Alignment pass sees only `Write` / "create new file"
tasks in the plan → emits no findings, no warnings. Zero changes to
`xdd-plan`. Simplest. Minor cost: the validate run still executes
the perspective, just finds nothing.

### Option B — explicit Brownfield marker

`xdd-plan` annotates tasks that touch existing files with a new
metadata tag, analogous to the existing `[ref: ...]` / `[activity:
...]` annotations:

```markdown
- [ ] T4.1 Insert Phase 0 in inbox-orchestrator `[modifies: tomo/dot_claude/agents/inbox-orchestrator.md]`
```

validate's Alignment perspective then only audits tasks carrying the
`[modifies: ...]` tag. Requires a small schema extension in
`xdd-plan/reference/task-structure.md` and validate learns to look
for the tag. Marginally more work, much more explicit.

**Tradeoff**: A is zero-risk and ships today. B is a cleaner
long-term contract but costs a spec bump to the plan task format.

---

## Labels

- `skill: xdd` / `skill: validate`
- `type: enhancement`
- `scope: brownfield-authoring`
- `design-question: open` (A vs B)

## Repro

Any XDD plan that adds `### Phase N` / `### Step N` / `## Heading` /
new constraint bullet to an existing agent, script, or doc **without
the SDD having inventoried the target's current layout** risks this
class of drift. Tomo's XDD-009 Phase 4 is one instance; the pattern
generalizes to every brownfield XDD feature.
