---
name: skill-evaluate
description: "Score a proposed or existing skill/agent against TCS vision criteria before absorbing it. Use when importing external skills, accepting community contributions, or deciding whether to build a new skill."
user-invocable: true
argument-hint: "<path/to/SKILL.md> | <description of proposed skill>"
allowed-tools: Read, Glob, Grep, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:skill-evaluate**

Score new skills and agents against TCS vision criteria. Produce a verdict before any skill is absorbed, imported, or built.


## Interface

```
Check {
  id: string
  category: Uniqueness | Fit | Integration | Quality
  question: string
  result: YES | NO | PARTIAL | NA
  note?: string
}

EvalResult {
  target: string
  score: number          // 0–13 (each check = 1 point for YES, 0.5 for PARTIAL)
  verdict: ABSORB | ABSORB_ADAPT | MERGE | SKIP
  placement: tcs-workflow | tcs-team | tcs-helper | tcs-patterns | external
  checks: Check[]
  blocking_issues: string[]
  recommendations: string[]
}

State {
  target = $ARGUMENTS
  mode: File | Description
  skill_content: string | null
  existing_skills: string[]
}
```

## Constraints

**Always:**
- Run all 13 checks — never skip a category.
- Flag blocking issues (any check that scores 0 in Uniqueness or Integration) separately.
- Suggest the correct plugin placement even if verdict is SKIP.

**Never:**
- Issue ABSORB verdict when any blocking issue exists.
- Score a partial overlap as full overlap — distinguish "same task" from "related area".
- Treat a SKIP verdict as permanent — note when to revisit.

## Workflow

### 1. Parse Input

```
If $ARGUMENTS is a file path and the file exists:
  mode = File
  Read the file → skill_content

Else:
  mode = Description
  skill_content = null
  Work from the description in $ARGUMENTS
```

If blank: AskUserQuestion — "Provide a skill file path or a one-sentence description of the proposed skill."

### 2. Load Context

```bash
# Existing skill list for overlap checks
find plugins/*/skills -name "SKILL.md" 2>/dev/null
```

Grep description fields of existing skills:
```bash
grep -r "^description:" plugins/*/skills/*/SKILL.md 2>/dev/null
```

Read `docs/concept/tcs-vision.md` if it exists (authoritative criteria source).

### 3. Run Checks

Evaluate each check. Score YES=1, PARTIAL=0.5, NO=0.

#### Uniqueness (3 checks)

| ID | Question |
|----|----------|
| U1 | Does TCS already have a skill/agent that covers this? (YES = overlap exists → score 0) |
| U2 | If overlap exists — is the new skill significantly better, not just different? (N/A if no overlap) |
| U3 | Does this fill a real gap in the spec-to-ship workflow? |

For U1: grep existing descriptions for semantic overlap. "Covers" means >50% of the same responsibility.
For U2: only evaluated if U1=YES. Score YES if new skill is meaningfully superior, NO if merely different style.

#### Fit (4 checks)

| ID | Question |
|----|----------|
| F1 | Does it follow progressive disclosure (SKILL.md + reference/ pattern)? |
| F2 | Does it respect YAGNI (no speculative or unused features)? |
| F3 | Is it workflow-agnostic enough to work with the TCS pipeline? |
| F4 | Does it belong clearly in one of: tcs-workflow / tcs-team / tcs-helper / tcs-patterns? |

For F4: decide placement based on these rules:
- `tcs-workflow`: user-facing workflow steps (spec, implement, review, test)
- `tcs-team`: specialist agent activities (architect, developer, designer, etc.)
- `tcs-helper`: development utilities not in the core pipeline
- `tcs-patterns`: domain/stack-specific knowledge (DDD, React, TypeScript, etc.)
- `external`: skill designed for a different framework — does not fit TCS

#### Integration (3 checks)

| ID | Question |
|----|----------|
| I1 | Does it conflict with any existing skill's stated responsibility? |
| I2 | Can it be merged into an existing skill rather than added standalone? (YES = prefer merge) |
| I3 | Does it have clear, specific trigger conditions that prevent accidental activation? |

For I1: look for responsibility boundary violations (e.g. two skills that both "review code quality").
For I2: a skill that adds 1-2 steps to an existing workflow is a merge candidate, not a new skill.

#### Quality (3 checks)

| ID | Question |
|----|----------|
| Q1 | Is SKILL.md under ~25 KB (or clearly scoped to stay there)? |
| Q2 | Are constraints listed as Always/Never? |
| Q3 | Does it have an Interface section defining its state? |

For Description mode: score Q checks based on the description's implied design (PARTIAL if unclear).

### 4. Score and Verdict

```
score = sum of all check scores (max 13)
```

```
match (score) {
  >= 12 => verdict = ABSORB        "Adopt as-is"
  >= 8  => verdict = ABSORB_ADAPT  "Adopt with stated adaptations"
  >= 5  => verdict = MERGE         "Merge into [existing skill name]"
  < 5   => verdict = SKIP          "Park for later — revisit if [condition]"
}
```

**Blocking issues override score:**
- U1=YES AND U2=NO → downgrade verdict to MERGE or SKIP regardless of score
- I1=YES (conflict exists) → blocking issue, cannot ABSORB until resolved

### 5. Output Report

```
## TCS Skill Evaluation: [target name]

**Verdict: [ABSORB | ABSORB_ADAPT | MERGE | SKIP]**
**Score: [X]/13**
**Placement: [plugin]**

### Checks

| # | Category | Check | Result | Note |
|---|----------|-------|--------|------|
| U1 | Uniqueness | Existing coverage? | YES/NO/PARTIAL | ... |
| U2 | Uniqueness | Significantly better? | YES/NO/NA | ... |
| U3 | Uniqueness | Fills real gap? | YES/NO/PARTIAL | ... |
| F1 | Fit | Progressive disclosure? | YES/NO/PARTIAL | ... |
| F2 | Fit | YAGNI? | YES/NO/PARTIAL | ... |
| F3 | Fit | Pipeline-agnostic? | YES/NO/PARTIAL | ... |
| F4 | Fit | Clear placement? | YES/NO/PARTIAL | [plugin] |
| I1 | Integration | No conflicts? | YES/NO/PARTIAL | ... |
| I2 | Integration | Merge candidate? | YES/NO | [target if yes] |
| I3 | Integration | Clear triggers? | YES/NO/PARTIAL | ... |
| Q1 | Quality | Size OK? | YES/NO/PARTIAL | ... |
| Q2 | Quality | Always/Never format? | YES/NO/PARTIAL | ... |
| Q3 | Quality | Interface section? | YES/NO/PARTIAL | ... |

### Blocking Issues
[List or "None"]

### Recommendations
[Advisory suggestions — do not block verdict]

### Next Step
[ABSORB: "Ready to install." | ABSORB_ADAPT: "Apply [X] before installing." | MERGE: "Merge into [skill] — see [check] for reasoning." | SKIP: "Revisit when [condition]."]
```
