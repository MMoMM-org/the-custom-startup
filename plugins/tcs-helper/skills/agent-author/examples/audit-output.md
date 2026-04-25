# Audit Output Example

Concrete example of what an Audit-mode response looks like, against the ICMDA-aware audit checklist. Use this as the target shape when reporting findings to the user.

---

## Scenario

User asks: *"Audit my `~/.claude/agents/architect.md` agent — it never seems to get auto-invoked."*

The agent file currently looks like:

```markdown
---
name: architect
description: An expert software architect who can help design systems.
tools: Read, Write, Edit, Bash, Grep, Glob, WebFetch
---

You are a brilliant software architect with 20 years of experience designing scalable systems at top tech companies. You have deep expertise in distributed systems, microservices, and cloud architecture.

When asked about architecture, provide thoughtful analysis and recommendations.
```

---

## Audit Response

# Agent Audit: `architect`

**File:** `~/.claude/agents/architect.md`
**Archetype:** Architect (intended) — currently misconfigured
**Verdict:** Multiple FAILs across description, tools, model, and ICMDA structure. Will not auto-trigger reliably and has unsafe tool grant.

## Audit Checklist

| Category | Check | Status | Note |
|---|---|---|---|
| Frontmatter | Valid YAML, `name` + `description` present | PASS | |
| Frontmatter | `name` matches filename stem | PASS | |
| Frontmatter | `model` set explicitly | **FAIL** | Missing → inherits session model (Opus → wasteful) |
| Frontmatter | `tools` minimal per archetype | **FAIL** | 7 tools incl. `Write`/`Edit` — Architect should be read-only |
| Frontmatter | `color` matches archetype | WARN | Not set; Architect should be `blue` |
| Description | Trigger in first ~50 chars | **FAIL** | Generic "expert ... who can help" |
| Description | Contains `Use PROACTIVELY` or `MUST BE USED` | **FAIL** | Neither |
| Description | At least 2 trigger phrases | **FAIL** | Zero |
| Description | Third-person, scenario-anchored | **FAIL** | "An expert ... who can help" — vague role description |
| Description | Does NOT summarize the workflow | PASS | |
| Description | High-value agent has 2–3 `<example>` blocks | **FAIL** | None |
| Active-agent announcement | First non-blank line after frontmatter | **FAIL** | Missing |
| ICMDA | `## Identity` (1–2 sentences) | **FAIL** | Persona prose, not Identity section |
| ICMDA | `## Constraints` | **FAIL** | Missing |
| ICMDA | `## Mission` | **FAIL** | Missing |
| ICMDA | `## Decision: <Topic>` if routing decisions | **FAIL** | Missing |
| ICMDA | `## Activities` numbered list | **FAIL** | Missing |
| ICMDA | `## Output` typed table or rubrics | **FAIL** | Missing — free prose only |
| Size | Body ≤ 25 KB | PASS | Way under |

## Findings

### FAIL #1 — Description won't trigger auto-delegation

**Current:** *"An expert software architect who can help design systems."*

**Problem:** No imperative phrase, no trigger words, trigger scenario not in first 50 chars. Per PRINCIPLES § 2.1, descriptions are read by Claude's text-reasoning router; phrasing without `Use PROACTIVELY` / `MUST BE USED` and concrete user-language triggers reliably under-trigger. This is the root cause of "never gets auto-invoked".

**Fix:**

```yaml
description: |
  Use PROACTIVELY when the task involves system architecture decisions, service boundaries, scaling trade-offs, or technology selection.
  MUST BE USED when the user asks "how should we design X", evaluates microservices vs monolith, or plans for 10x growth.
  Examples:

  <example>
  Context: New service planning.
  user: "We need to design the architecture for our new payment service"
  assistant: "I'll use the architect agent to evaluate boundaries, scaling, and integration patterns."
  <commentary>System design from scratch is the canonical trigger.</commentary>
  </example>

  <example>
  Context: Architectural trade-off question.
  user: "Should we go microservices or stick with the monolith?"
  assistant: "I'll use the architect agent for that trade-off analysis."
  <commentary>Architecture trade-off question.</commentary>
  </example>
```

### FAIL #2 — Unsafe tool grant

**Current:** `Read, Write, Edit, Bash, Grep, Glob, WebFetch`

**Problem:** Architect agents review and recommend; they don't edit code. `Write`/`Edit` enable accidental changes during exploration. Per PRINCIPLES § 2.5, default to `Read, Grep, Glob` for research/analysis agents.

**Fix:**

```yaml
tools: Read, Grep, Glob
```

(Add `WebFetch` only with explicit comment if the agent needs to look up external architecture references.)

### FAIL #3 — Model not set

**Current:** No `model` field.

**Problem:** Inherits session model. Per TCS convention (and to avoid Opus-cost surprises), explicitly set `sonnet` for activity agents.

**Fix:**

```yaml
model: sonnet
```

Escalate to `opus` only with explicit rationale (e.g., this agent handles the hardest cross-system architecture decisions). Document the reason in a comment near the frontmatter.

### FAIL #4 — System prompt has no ICMDA structure

**Current:** Persona prose + "provide thoughtful analysis."

**Problem:** Missing all six required sections (Identity / Constraints / Mission / Decision / Activities / Output). The agent has no reliable behavior — different shapes of output every invocation. Persona prose adds zero routing or operational value.

**Fix:** rewrite the body using the ICMDA skeleton (see `examples/canonical-agent.md`):

```markdown
**Active agent: architect**

## Identity

You are a focused architecture review subagent specializing in system boundaries, scaling risks, and technology trade-offs.

## Constraints

```
Constraints {
  require {
    Cite specific files / interfaces for every finding
    Reference existing patterns or established conventions
    Distinguish observed risks from speculative concerns
  }
  never {
    Edit files or write code
    Re-implement features
    Speculate beyond what is observable in the code or docs
  }
}
```

## Mission

Surface architectural risks and trade-offs early so technology choices are made with eyes open.

## Decision: Review Scope

| IF target involves | THEN start with | Rationale |
|---|---|---|
| New service/system | Existing similar services in repo | Match local conventions first |
| Refactor of existing | Current implementation + callers | Understand status quo before redesigning |
| Trade-off question | Both options' implications in this codebase context | Concrete analysis, not generic advice |

## Activities

1. Identify relevant modules, interfaces, and architectural seams.
2. Read existing patterns in similar areas of the codebase.
3. Evaluate the proposal against those patterns.
4. Identify scaling, coupling, and ownership risks.
5. Format findings using the output template.

## Output

| Field | Type | Required | Description |
|---|---|---|---|
| criticalRisks | string[] | Yes | Boundary violations, scaling failures, coupling |
| designWeaknesses | string[] | Yes | Weak abstractions, unclear ownership |
| positiveSignals | string[] | No | Patterns aligned with existing design |
| filesReviewed | string[] | Yes | |
| recommendedNextStep | string | Yes | |
```

## Modernize Recommendation

Apply all four fixes together. The agent will then:
- Auto-trigger on architecture-related tasks (Fix #1)
- Run safely without accidental edits (Fix #2)
- Use predictable model cost (Fix #3)
- Produce consistent, parseable output (Fix #4)

## Recommended Next Step

Run `agent-author` in **Modernize mode** to apply these fixes:
> "Modernize ~/.claude/agents/architect.md per the audit findings"

Or apply manually using the patches above. Re-run audit afterwards to confirm all checks PASS.

---

## Notes on this report shape

- **Verdict line up top** — user knows immediately whether the agent is OK or broken.
- **Checklist table** — every check from `output-formats.md` Audit Checklist, with status.
- **Findings grouped by severity** — FAILs first, with root cause + specific fix code shown inline.
- **Modernize recommendation** — explicit next-step invocation the user can run.
- **References to canonical-agent.md** — for the full ICMDA template.

This shape works for both "audit this agent" requests and post-Modernize verification reports.
