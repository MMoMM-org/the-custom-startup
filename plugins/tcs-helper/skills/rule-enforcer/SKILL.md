---
name: rule-enforcer
description: "Use PROACTIVELY when the user describes a recurrence rule they keep violating, wants to enforce a personal workflow rule, or uses phrases like 'I keep forgetting', 'remind me to always', 'enforce that I', or 'make sure I never'."
user-invocable: true
argument-hint: "[rule description]"
allowed-tools: Read, AskUserQuestion, Task
---

## Persona

**Active skill: tcs-helper:rule-enforcer**

Act as a rule-triage specialist that walks the user through 4 structured questions to identify the right enforcement mechanism for a recurrence rule, then hands off to the appropriate author skill.

**Request**: $ARGUMENTS

## Interface

```
TriageState {
  rule: string
  q1: First | Recurring | Cross-cutting | undefined
  q2: Yes | No-judgment | undefined
  q3: PreToolUse | PostToolUse | UserPromptSubmit | SessionStart | LocalGitPush | PRMerge | CodingPattern | undefined
  q4: Block | Auto-fix | Nudge | undefined
  mechanism: string | undefined
}

State {
  rule = $ARGUMENTS
  triage: TriageState
}
```

**In scope:** Recurrence rules the user wants mechanically enforced via hooks, CI, skills, or memory.

**Out of scope:** One-off tasks, general advice, or rules that require human judgment on every occurrence.

## Constraints

**Always:**
- Use AskUserQuestion for Q1–Q4 — never present questions as plain-text prompts.
- Read reference/mechanism-matrix.md lazily at Step 6 (not upfront).
- Hand off to existing author skills via Skill() — do not re-implement their authoring logic.
- Echo the rule back at Step 1 before asking any questions.

**Never:**
- Persist triage state to disk — v1 has no persistence (ADR-3).
- Mirror constraints across PICS sections — each rule appears once.
- Skip the Q1 short-circuit — if the rule has only happened once, defer to memory-add.
- Ask Q2–Q4 when Q1 = First (those steps are irrelevant for first-time occurrences).

## Workflow

### 1. Echo rule + confirm

Quote back the rule exactly as the user stated it:

> "You want to enforce: _[rule from $ARGUMENTS]_. Is this description accurate, or would you like to revise it before we begin triage?"

Use AskUserQuestion with options `{Looks right — continue, Let me revise the rule}`. If the user revises, update `State.rule` and echo again before proceeding.

### 2. Q1 — Recurrence check

AskUserQuestion — Q1: How many times have you violated this rule?

Options (each includes a short example to aid recognition):
- `First time — no memory yet (e.g., "I haven't seen this in any prior session")`
- `Recurring — memory exists but was ignored (e.g., "I have a memory entry for this and broke it again")`
- `Cross-cutting — applies broadly across areas (e.g., "This pattern occurs in many different contexts")`

Branch on Q1:
- `First time` → Defer to memory-add skill via `Skill(tcs-helper:memory-add)` and exit triage (Q2–Q4 are irrelevant for first-time occurrences — skip them entirely).
- `Recurring` or `Cross-cutting` → Set `triage.q1` and proceed to Step 3.

### 3. Q2 — Mechanical detectability

AskUserQuestion — Q2: Can a script or tool reliably detect this violation without human judgment?

Options (each includes a concrete example per PRD M3 design constraint):
- `Yes — concrete signal (e.g., "missing CHANGELOG line, detectable by grep")`
- `No — judgment only (e.g., "is this code too verbose — requires a human eye")`

Branch on Q2:
- `No-judgment` → Short-circuit to Memory with strong-language template: defer to memory-add skill via `Skill(tcs-helper:memory-add)` with a hint to use strong wording (e.g., "MUST", "NEVER", "ALWAYS") since mechanical enforcement is not applicable. Exit triage.
- `Yes` → Set `triage.q2` and proceed to Step 4.

### 4. Q3 — Intervention point

AskUserQuestion — Q3: At which point should enforcement trigger?

Options — each label includes a concrete example (verify labels match `reference/mechanism-matrix.md` section headings):
- `Before Claude calls a tool (e.g. block --break-system-packages)`
- `After Claude calls a tool (e.g. nudge after editing skills/)`
- `User submits a prompt (e.g. recurrence-signal injection)`
- `Session start (e.g. restore context or validate env)`
- `Local git push (e.g. block before pushing if CHANGELOG missing)`
- `PR/merge to main (e.g. CI auto-bump versions)`
- `In repeated coding patterns (e.g. TDD discipline)`

Set `triage.q3` to the **bare label** of the chosen option — strip the parenthetical suffix starting at ` (e.g.`. For example, `Before Claude calls a tool (e.g. block --break-system-packages)` becomes `Before Claude calls a tool`. This ensures Step 6's matrix lookup finds the correct section heading in `reference/mechanism-matrix.md`.

Then proceed to Step 5.

### 5. Q4 — Enforcement style

AskUserQuestion — Q4: How strong should the enforcement be?

Options (each includes a behavior preview):
- `Block — refuse the action until the violation is resolved`
- `Auto-fix — silently correct or generate the missing artifact`
- `Nudge — warn but allow the action to continue`

Set `triage.q4` and proceed to Step 6.

### 6. Matrix lookup

Read `reference/mechanism-matrix.md` now (lazy load per ADR-1 — do not read earlier).

Find the section `## Q3 = [triage.q3]` and look up the row where `Q4 = [triage.q4]`. Extract the mechanism name from the `Mechanism` column. Set `triage.mechanism`.

**Lookup key format**: `## Q3 = {triage.q3}` where `triage.q3` is the bare label from Step 4. For example, if the user chose `Before Claude calls a tool (e.g. block --break-system-packages)` in Step 4, the lookup key is `## Q3 = Before Claude calls a tool` (the normalized bare label from that option).

Do not hard-code any (Q3, Q4) → mechanism mapping in this workflow — the mechanism-matrix file is the single source of truth.

### 7. Recommendation

Present the result via AskUserQuestion — show mechanism name + one-line rationale (drawn from the matrix section note if present):

> "Based on your answers, the recommended enforcement mechanism is: **[triage.mechanism]**
> Rationale: [one-line note from matrix section]"

Options:
- `Accept — proceed to hand-off`
- `Override — let me pick a different mechanism`
- `Explain — show full rationale and alternative mechanisms`

If `Override`: re-prompt Q3 and Q4 and repeat Steps 5–7.
If `Explain`: display the full matrix section for the chosen Q3, then re-offer Accept / Override.
If `Accept`: proceed to Step 8.

### 8. Hand-off

Match on `triage.mechanism` (set in Step 6). Invoke the target skill with the
rule context formatted as `$ARGUMENTS` so the target skill receives it as its
`**Request**: $ARGUMENTS` input.

**Mechanism match:**

- Any mechanism starting with `Skill with discipline language` →
  `Skill(tcs-helper:skill-author)` with `$ARGUMENTS` =
  `"Create or update a skill that enforces: [State.rule]. Q4 style: [triage.q4]."`

- Any mechanism starting with `Claude PreToolUse hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `PreToolUse` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- Any mechanism starting with `Claude PostToolUse hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `PostToolUse` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- Any mechanism starting with `Claude UserPromptSubmit hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `UserPromptSubmit` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- Any mechanism starting with `Claude SessionStart hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `SessionStart` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- `Memory rule` →
  `Skill(tcs-helper:memory-add)` with `type=feedback` and a strong-language hint:
  prepend the rule with `MUST`, `NEVER`, or `ALWAYS` to maximise enforcement weight.

- Any mechanism starting with `CI workflow` →
  1. Read both template files:
     `plugins/tcs-helper/skills/rule-enforcer/templates/ci-auto-bump-style.yml.j2`
     `plugins/tcs-helper/skills/rule-enforcer/templates/ci-auto-bump-style.sh.j2`
  2. Compute `workflow_name` and `script_name` as kebab-case slugs derived from the rule
     (e.g., "CHANGELOG must be touched when feat: commits land" → `enforce-changelog`).

  **Slug validation gate**: Before any Write, assert both computed slugs match the regex
  `^[a-z0-9][a-z0-9-]{0,62}$`. If either does not (contains `/`, `.`, `..`, special chars, or
  exceeds 63 chars): abort the hand-off via AskUserQuestion `{Edit slug manually / Cancel}`.
  This prevents path-traversal via crafted rule descriptions.

  3. Generate the `detection_logic` bash block and `remediation_logic` bash block
     for the specific rule — Claude authors these from the rule description and Q4 style.
  4. Render both templates via string substitution, replacing all five placeholders:
     `{{rule_description}}`, `{{workflow_name}}`, `{{script_name}}`,
     `{{detection_logic}}`, `{{remediation_logic}}`.
  5. Present the rendered YAML and rendered .sh as a PREVIEW to the user — do not
     write any files yet.
  6. AskUserQuestion `{Write — commit the workflow + script, Refine — show changes I want to make, Cancel — abort}`:
     - `Write` → Write the rendered YAML to `.github/workflows/{{workflow_name}}.yml`
       AND the rendered .sh to `scripts/ci/{{script_name}}.sh`
     - `Refine` → prompt the user for specific changes, regenerate, and return to step 5
     - `Cancel` → exit with no files written

- Any mechanism starting with `git pre-push hook` →
    1. Read template file:
       `plugins/tcs-helper/templates/githooks/pre-push-rule-enforcer.sh.j2`
    2. Determine `response_style` from `triage.q4`:
       - `Block` → response_style = `Block`
       - `Nudge` or `Auto-fix` → response_style = `Nudge`
    3. Author `detection_pattern` (bash conditional using `$commits_file` / `$diff_file`) and
       `warning_message` from the rule description and Q4 style.
    4. Render the template via string substitution, replacing all four placeholders:
       `{{rule_description}}`, `{{detection_pattern}}`, `{{response_style}}`, `{{warning_message}}`.
    5. Compute target filename: `.githooks/pre-push-rule-enforcer-<slug>.sh`
       where slug = kebab-case derived from the rule description.

  **Slug validation gate**: Before any Write, assert the computed slug matches the regex
  `^[a-z0-9][a-z0-9-]{0,62}$`. If it does not (contains `/`, `.`, `..`, special chars, or
  exceeds 63 chars): abort the hand-off via AskUserQuestion `{Edit slug manually / Cancel}`.
  This prevents path-traversal via crafted rule descriptions.

    6. **Collision check**: read `.githooks/tcs-helper-rule-enforcer-version` if it exists;
       compare to the plugin's current marker (read from
       `plugins/tcs-helper/templates/githooks/tcs-helper-rule-enforcer-version`).
       - Marker missing → fresh install: proceed.
       - Marker matches → AskUserQuestion: append a new hook vs replace existing.
       - Marker differs → AskUserQuestion: suggest re-install
         (offer `Skill(tcs-git-helpers:git-setup)` hand-off for full bundle refresh).
    7. Present the rendered `.sh` as a PREVIEW — do not write any files yet.
    8. AskUserQuestion `{Write — install hook, Refine — show changes I want to make, Cancel — abort}`:
       - `Write` →
         - Write rendered script to `.githooks/pre-push-rule-enforcer-<slug>.sh`
         - Copy `plugins/tcs-helper/templates/githooks/tcs-helper-rule-enforcer-version`
           to `.githooks/tcs-helper-rule-enforcer-version` (sibling marker)
         - `chmod +x .githooks/pre-push-rule-enforcer-<slug>.sh`
         - Remind user to run `git config core.hooksPath .githooks` if not already configured
       - `Refine` → prompt user for specific changes, regenerate, return to step 7
       - `Cancel` → exit with no files written

**Fallback (target plugin not installed):**

AskUserQuestion with options:
- `Install plugin first — I will install plugin-dev and retry`
  → Instruct user to install the plugin, then abort triage (do not attempt hand-off).
- `Use Memory rule instead — add to memory with strong wording`
  → `Skill(tcs-helper:memory-add)` with `type=feedback` + strong-language hint.
- `Cancel — exit triage, no action taken`
  → Exit skill immediately with no further action.

### Entry Point

Non-linear routing summary:
- Step 2 (Q1 = `First time`) → invoke memory-add and exit; skip Steps 3–8.
- Step 3 (Q2 = `No-judgment`) → invoke memory-add with strong-language hint and exit; skip Steps 4–8.
- Step 7 (`Override`) → loop back to Step 4 (re-ask Q3 and Q4).
- All other paths → proceed sequentially Steps 1 → 8.
