# Output Format Templates

Every agent MUST define an explicit `## Output` section in its body. Free-form prose is reject-on-sight — it makes orchestration brittle and hides important findings.

This file provides:
1. **Typed-table templates per archetype** for the agent's own `## Output` section
2. **Audit checklist** for the agent-author skill itself (Audit/Modernize mode)

---

## Output Section — TCS Convention

The TCS-team convention is a **typed table** with `| Field | Type | Required | Description |` columns. Example:

```markdown
## Output

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| findings | Finding[] | Yes | Audit findings list (Critical/Warning/Suggestion) |
| filesReviewed | string[] | Yes | Paths examined |
| testsRun | string | No | Test command + summary if applicable |
| recommendedNextStep | string | Yes | Single-sentence next action |
```

For nested types, define them inline with their own table:

```markdown
### Finding

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| severity | enum: Critical \| Warning \| Suggestion | Yes | Severity bucket |
| location | string | Yes | file:line citation |
| description | string | Yes | What the issue is |
| fix | string | Yes | Proposed remediation |
```

Use rubric-style markdown lists (`- **Critical**`, `- **Warning**`) instead of typed tables only when the agent's output is purely human-facing and won't be consumed by orchestration.

---

## Per-Archetype Output Templates

### Reviewer (Code / PR / Spec)

| Field | Type | Required | Description |
|---|---|---|---|
| critical | Finding[] | Yes | Correctness, security, data-loss issues — blocks merge |
| warning | Finding[] | Yes | Regression risk, edge cases, missing tests |
| suggestion | Finding[] | No | Maintainability, naming, optional improvements |
| filesChecked | string[] | Yes | Paths reviewed |
| testsRun | string | No | Command + pass/fail summary |
| recommendedNextStep | string | Yes | Single-sentence next action |

### Debugger

| Field | Type | Required | Description |
|---|---|---|---|
| symptom | string | Yes | What the user sees / what's failing |
| likelyRootCause | string | Yes | Single best hypothesis |
| evidence | string[] | Yes | file:line, command output, log excerpts |
| fixOptions | FixOption[] | Yes | Ranked by impact and risk |
| verificationSteps | string[] | Yes | How to confirm the fix |

### Explorer

| Field | Type | Required | Description |
|---|---|---|---|
| relevantFiles | string[] | Yes | file:line citations |
| patternsFound | string[] | Yes | Observed conventions and structures |
| constraintsOrRisks | string[] | No | Non-obvious gotchas |
| openQuestions | string[] | No | What couldn't be answered from the code |
| suggestedNextStep | string | Yes | |

### Implementer

| Field | Type | Required | Description |
|---|---|---|---|
| changesMade | Change[] | Yes | file:line edits with one-line summary each |
| testsRun | string | Yes | Command + result |
| verification | string | Yes | How the change was confirmed working |
| followUps | string[] | No | Anything left for the user |

### Architect

| Field | Type | Required | Description |
|---|---|---|---|
| criticalRisks | string[] | Yes | Boundary violations, scaling concerns, coupling |
| designWeaknesses | string[] | Yes | Weak abstractions, unclear ownership |
| positiveSignals | string[] | No | Patterns aligned with existing design |
| filesReviewed | string[] | Yes | |
| recommendedNextStep | string | Yes | |

### Security Reviewer

| Field | Type | Required | Description |
|---|---|---|---|
| critical | Finding[] | Yes | Exploitable issues (injection, auth bypass, data leak) |
| highRisk | Finding[] | Yes | Exposed surfaces, missing validation |
| mediumLow | Finding[] | No | Hardening recommendations |
| filesReviewed | string[] | Yes | |
| remediationPriority | string | Yes | Ranked priority order |

### Test Runner

| Field | Type | Required | Description |
|---|---|---|---|
| testSummary | string | Yes | N passed / M failed / K skipped |
| failures | Failure[] | If any | Name, file:line, error excerpt |
| flakyCandidates | string[] | If any | Tests that passed on retry |
| recommendedNextStep | string | Yes | |

### Docs Writer

| Field | Type | Required | Description |
|---|---|---|---|
| filesWritten | string[] | Yes | |
| keySectionsCovered | string[] | Yes | |
| openQuestions | string[] | No | What couldn't be documented from available code |
| crossReferences | string[] | No | Linked docs, ADRs, runbooks |

---

## Audit Checklist (used by agent-author Audit/Modernize mode)

| Category | Check | Pass criteria |
|---|---|---|
| **Frontmatter** | Valid YAML between `---` fences? | `name`, `description` present |
| | `name` matches filename stem | Yes |
| | `model` set explicitly (TCS convention) | `sonnet` default; `haiku`/`opus` with rationale; not `inherit` without justification |
| | `tools` minimal per archetype | No `*`; security/reviewer no `Write` |
| | `color` matches archetype semantic | Per conventions.md table |
| **Description** | Trigger in first ~50 chars | Yes |
| | Contains `Use PROACTIVELY` or `MUST BE USED` | Yes |
| | At least 2 concrete trigger phrases | Verbatim user-language |
| | Third-person, scenario-anchored | Yes |
| | Does NOT summarize the workflow | Yes |
| | Distinguishable from main-agent scope | Not "for all X" |
| | High-value agents have 2–3 `<example>` blocks | Yes |
| **Active-agent announcement** | First non-blank line after frontmatter | `**Active agent: <plugin>:<role>:<activity>**` |
| **ICMDA Body** | `## Identity` present, 1–2 sentences | Yes |
| | `## Constraints` present (block or markdown) | Yes |
| | `## Mission` present, single sentence | Yes |
| | At least one `## Decision: <Topic>` for routing decisions | If agent makes routing choices |
| | `## Activities` numbered list of concrete actions | Yes |
| | `## Output` typed table or named rubrics | Yes — never free prose |
| **Size** | Body ≤ 25 KB | Yes; if larger, externalize to reference/ |

---

## Issue Categories (for reporting findings)

| Symptom | Category | Fix Approach |
|---|---|---|
| "Agent doesn't get auto-invoked" | Description weakness | Add `Use PROACTIVELY` + concrete triggers + examples |
| "Agent does the wrong thing" | Scope drift | Tighten Activities + add explicit boundaries in Constraints `never {}` |
| "Agent uses too many tokens" | Model over-spec | Switch from `inherit`/`opus` to `sonnet`/`haiku` |
| "Agent edits files it shouldn't" | Tool over-grant | Strip `Write`/`Edit`/`Bash` per archetype |
| "Output is hard to parse" | Format weakness | Replace free prose with typed table |
| "Agent overlaps with another" | Duplicate scope | Modernize one, deprecate other, or merge |
| "Agent reads whole repo" | Context hygiene | Add filtering in Activities + size limits in Output |
| "Agent assumes parent context" | Channel violation | Move context-passing into the dispatch prompt; remove "we discussed" references |

---

## Severity Mapping

| Severity | Meaning | Example |
|---|---|---|
| **FAIL** | Agent broken — won't trigger or produces unsafe output | Description has no action verb; security agent has `Write` tool; `tools: *` |
| **WARN** | Agent works but suboptimal — wastes tokens or matches loosely | Model `inherit`; description has only one trigger phrase; missing `<example>` blocks |
| **PASS** | Meets all conventions | — |

Always propose a specific fix for FAIL and WARN. Never report symptoms without remediation.
