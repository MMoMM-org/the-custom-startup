---
name: rule-enforcer
description: "Use PROACTIVELY when the user describes a recurrence rule they keep violating, wants to enforce a personal workflow rule, or uses phrases like 'I keep forgetting', 'remind me to always', 'enforce that I', or 'make sure I never'. Also use to bulk-convert already-written rules into enforcement — when the user says 'scan my rules', 'turn my CLAUDE.md into hooks', 'enforce all my rules', 'mechanize my memory rules', or invokes it with --scan / --from-file."
user-invocable: true
argument-hint: "[rule description] | --scan | --from-file <path>"
allowed-tools: Read, AskUserQuestion, Skill, Write, Bash, Glob, Grep
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

**Batch mode only (see `## Batch mode` + ADR-1..ADR-5):**

```
BatchState { scope, sourceFiles: string[], candidates: Candidate[] }

Candidate {                # mirrors TriageState field-for-field so B9 feeds
  sourceFile, line         # each straight into the unchanged Step 8 hand-off
  rawText                  # scrubbed if personal
  q2, q3, q4, mechanism    # q1 is skipped (ADR-2); q3 = BARE-LABEL (ADR-4)
  confidence: high | low   # low => needs-review, default OFF
  dedupStatus: new | already-enforced
  target
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

## Reference Materials

Load lazily — read a file only at the step that needs it.

- `reference/mechanism-matrix.md` — (Q3 × Q4) → mechanism mapping. Single source of truth for both the interactive Step 6 lookup and batch B5.
- `reference/examples.md` — worked (rule → Q2/Q3/Q4 → mechanism) cases; the analogy training set for classification.
- `reference/trigger-phrases.md` — phrases that should fire the skill.
- `reference/scan-sources.md` — batch B1 default source set, `@`-import policy, and structural exclusions.
- `reference/extraction-heuristics.md` — batch B3/B4 enforceable-vs-judgment filter, Q3 bucket cues, Q4 defaults, and the canonical Q3 bare labels.
- `reference/installed-enforcement-catalog.md` — batch B6 dedup hint layer (live `.githooks/` + `hooks.json` inspection is authoritative).

## Workflow

### 0. Mode dispatch

Inspect `$ARGUMENTS` and route (ADR-1 — explicit argument shape, no path-vs-sentence sniffing):

- empty **OR** starts with `--scan` → **BATCH mode**. Scope from an optional
  `--scope repo|project|global`; default is **repo + project** (global is opt-in
  only, because `~/.claude/` holds personal content). Go to `## Batch mode`.
- starts with `--from-file <path>` → **BATCH mode** over that one explicit file.
  **Validate the path before any read**: reject `..`, and reject absolute paths
  outside the repo and outside the known `~/.claude/` set. On rejection, report and exit.
- otherwise (a rule sentence) → **INTERACTIVE mode**: proceed to Step 1 (unchanged).

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

Read `reference/hand-off.md` now and follow it. It maps `triage.mechanism` to the author skill or template to invoke, holds the slug validation gates, and covers a target plugin that is not installed. The rule it hands off is `State.rule`.

### Entry Point

Non-linear routing summary:
- Step 0 (`$ARGUMENTS` empty / `--scan` / `--from-file`) → BATCH branch: skip Steps 1–7, run `## Batch mode` (B1–B9), which reuses Step 8 for hand-off.
- Step 2 (Q1 = `First time`) → invoke memory-add and exit; skip Steps 3–8.
- Step 3 (Q2 = `No-judgment`) → invoke memory-add with strong-language hint and exit; skip Steps 4–8.
- Step 7 (`Override`) → loop back to Step 4 (re-ask Q3 and Q4).
- All other paths → proceed sequentially Steps 1 → 8.

## Batch mode

Thin orchestration over a set of already-codified rule files (CLAUDE.md sweep).
Skips Q1 and turns Q2 into a filter (ADR-2); reuses the matrix (CON-1) and the
Step 8 hand-off verbatim (ADR-3). Read-only until the single confirm at B8.
Procedural detail lives in the lazy-loaded `reference/` files — load them here,
do not inline their content.

- **B1 Enumerate** — load `reference/scan-sources.md`; resolve the source set for
  the chosen scope. Reuse `memory-claude-md-optimize`'s @-import / scope-discovery
  model (do not reimplement traversal); apply that file's protected/structural exclusions.
- **B2 Parse** — read each resolved file; split into candidate instructions,
  recording provenance (`file:line`) per candidate.
- **B3 Filter (Q2 gate)** — apply `reference/extraction-heuristics.md` §1: keep
  deterministically-enforceable candidates; drop judgment-only ones to a "left as
  guidance" list. Do **not** fire a per-line memory-add (ADR-2).
- **B4 Infer** — per kept candidate infer Q2/Q3/Q4 via `reference/extraction-heuristics.md`
  (Q1 skipped, ADR-2). Emit Q3 as the exact **bare-label** matrix heading string
  (ADR-4). Mark low-confidence rows `needs-review` (default OFF).
- **B5 Matrix lookup** — resolve the mechanism via `reference/mechanism-matrix.md`
  using the same `## Q3 = <bare-label>` × Q4-row lookup as interactive Step 6 (SSOT, CON-1).
- **B6 Dedup** — mark `already-enforced` by matching mechanism + target-pattern
  against the **live** `.githooks/` + `hooks.json` + per-rule slug files + the
  `tcs-helper-rule-enforcer-version` marker; use `reference/installed-enforcement-catalog.md`
  as a hint layer only (ADR-5). Default already-enforced rows OFF.
- **B7 Render table** — one consolidated proposal table (columns: `#`,
  `Source file:line`, `Quote`, `Q2`, `Mechanism`, `Style`, `Status`, `Target`)
  plus a "Left as guidance" sub-table for the judgment-only lines. If zero
  enforceable rules: report counts and skip the confirm.
- **B8 Single confirm** — two-tier AskUserQuestion. Tier 1
  `{Apply all enforceable, Select a subset, Cancel}`; Tier 2 (if subset) a
  `multiSelect` over the rows, **paged when > 4** (AskUserQuestion caps at 4
  options). `already-enforced` and `needs-review` rows default OFF.
- **B9 Hand-off** — for each accepted row build a
  `TriageState{ q1: skipped, q2, q3, q4, mechanism }` and feed it into the
  **existing Step 8 "Mechanism match" dispatch verbatim** (inherits slug-validation
  gates, templates, collision check, and Fallback). Group by mechanism bucket; if a
  target plugin is absent, degrade that whole bucket to memory-add (with confirm)
  and continue (skip-and-report). Show one grouped artifact preview, then a single
  `{Write all / Refine one / Cancel}`. Personal `~/.claude/` content must be
  **paraphrased**, never pasted into generated artifacts or hand-off `$ARGUMENTS` (CON-5).
