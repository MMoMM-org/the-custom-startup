# Output Format Templates

Every agent MUST define a fixed output format in its system prompt. Free-form prose is reject-on-sight — it makes orchestration brittle and hides important findings.

This file provides:
1. **Templates per archetype** for the agent's own output format
2. **Audit checklist** for the agent-author skill itself

---

## Per-Archetype Templates

### Reviewer (Code / PR / Spec)

```
- **Critical** (correctness, security, data loss)
- **Warning** (regression risk, edge cases, missing tests)
- **Suggestion** (maintainability, style, naming)
- **Files checked**
- **Recommended next step**
```

### Debugger

```
- **Symptom** — what the user sees / what's failing
- **Likely root cause** — single best hypothesis
- **Evidence** — file:line, command output, log excerpts
- **Fix options** — ranked by impact and risk
- **Verification steps** — how to confirm the fix
```

### Explorer

```
- **Relevant files** — file:line citations
- **Patterns found** — observed conventions and structures
- **Constraints or risks** — non-obvious gotchas
- **Open questions** — what couldn't be answered from the code
- **Suggested next step**
```

### Implementer

```
- **Changes made** — list of file:line edits with one-line summary each
- **Tests run** — command + result
- **Verification** — how the change was confirmed working
- **Follow-ups** — anything left for the user to handle
```

### Architect

```
- **Critical risks** — boundary violations, scaling concerns, coupling
- **Design weaknesses** — weak abstractions, unclear ownership
- **Positive signals** — patterns that align with existing design
- **Files reviewed**
- **Recommended next step**
```

### Security Reviewer

```
- **Critical findings** — exploitable issues (injection, auth bypass, data leak)
- **High-risk findings** — exposed surfaces, missing validation
- **Medium / Low** — hardening recommendations
- **Files reviewed**
- **Remediation priority**
```

### Test Runner

```
- **Test summary** — N passed / M failed / K skipped
- **Failures** — name, file:line, error excerpt
- **Flaky candidates** — tests that passed on retry
- **Recommended next step**
```

### Docs Writer

```
- **Files written / updated**
- **Key sections covered**
- **Open questions** — what couldn't be documented from available code
- **Cross-references** — linked docs, ADRs, runbooks
```

---

## Audit Checklist (used by agent-author Audit/Modernize mode)

| Check | Question | Pass criteria |
|---|---|---|
| **Frontmatter** | Valid YAML between `---` fences? | `name`, `description`, `model`, `tools` present |
| **Description — action** | Contains `Use PROACTIVELY` or `MUST BE USED`? | Yes |
| **Description — triggers** | At least 2 concrete trigger phrases? | Yes |
| **Description — scope** | Distinguishable from main-agent scope? | Not "expert in X" / "for all Y" |
| **Description — workflow leak** | Does NOT summarize the workflow? | Description focuses on *when*, not *how* |
| **Model** | `sonnet` (default) or `opus`/`haiku` with rationale? | Not `inherit` |
| **Tools** | Minimal set per archetype? | No "all tools just in case" |
| **Tools — security** | If security/reviewer agent: no `Write`? | Yes |
| **System prompt — Role** | One-sentence identity present? | Yes |
| **System prompt — Responsibilities** | Numbered, concrete? | Yes |
| **System prompt — Do not** | Explicit boundaries? | Yes |
| **System prompt — Workflow** | Numbered steps? | Yes |
| **System prompt — Verification** | How findings are grounded in evidence? | Yes |
| **System prompt — Output format** | Fixed structure (rubrics or named fields)? | Not free prose |
| **Color** | Matches archetype semantic? | Per conventions.md table |
| **Size** | System prompt under 200 lines? | Yes |

---

## Issue Categories (for reporting audit findings)

| Symptom | Category | Fix Approach |
|---|---|---|
| "Agent doesn't get auto-invoked" | Description weakness | Add `Use PROACTIVELY` + concrete triggers |
| "Agent does the wrong thing" | Scope drift | Tighten Responsibilities + add Do-not boundaries |
| "Agent uses too much tokens" | Model over-spec | Switch from `inherit`/`opus` to `sonnet`/`haiku` |
| "Agent edits files it shouldn't" | Tool over-grant | Strip `Write`/`Edit`/`Bash` per archetype |
| "Output is hard to parse" | Format weakness | Replace free prose with fixed rubrics |
| "Agent overlaps with another" | Duplicate scope | Modernize one, deprecate other, or merge |
| "Agent reads whole repo" | Context hygiene | Add filtering steps in Workflow + size limits in Verification |

---

## Severity Mapping

When presenting audit findings, use these severities:

| Severity | Meaning | Example |
|---|---|---|
| **FAIL** | Agent broken — won't trigger or produces unsafe output | Description has no action verb; security agent has `Write` tool |
| **WARN** | Agent works but suboptimal — wastes tokens or matches loosely | Model is `inherit`; description has only one trigger phrase |
| **PASS** | Meets all conventions | — |

Always propose a specific fix for FAIL and WARN. Never report symptoms without remediation.
