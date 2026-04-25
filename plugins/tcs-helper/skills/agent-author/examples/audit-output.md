# Audit Output Example

Concrete example of what an Audit-mode response looks like. Use this as the target shape when reporting findings to the user.

---

## Scenario

User asks: "Audit my `~/.claude/agents/architect.md` agent — it never seems to get auto-invoked."

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
**Verdict:** Multiple FAILs — agent will not auto-trigger reliably and has unsafe tool grant.

## Audit Checklist

| Check | Status | Note |
|---|---|---|
| Frontmatter — valid YAML | PASS | |
| Frontmatter — `name` present | PASS | |
| Frontmatter — `description` present | PASS | |
| Frontmatter — `model` present | **FAIL** | Missing — will inherit session model (likely Opus, wasteful) |
| Frontmatter — `tools` minimal | **FAIL** | 7 tools including `Write`/`Edit` — Architect should be read-only |
| Description — action verb | **FAIL** | No `Use PROACTIVELY` or `MUST BE USED` |
| Description — trigger phrases | **FAIL** | Zero concrete triggers |
| Description — scope distinct | **FAIL** | "expert ... who can help" overlaps with main agent |
| Description — workflow leak | PASS | Doesn't summarize workflow |
| System prompt — Role | WARN | Persona prose ("brilliant ... 20 years ...") instead of single-sentence identity |
| System prompt — Responsibilities | **FAIL** | None — body is generic "provide thoughtful analysis" |
| System prompt — Do not | **FAIL** | No boundaries defined |
| System prompt — Workflow | **FAIL** | No numbered steps |
| System prompt — Verification | **FAIL** | No evidence-grounding instructions |
| System prompt — Output format | **FAIL** | No fixed structure — free prose |
| Color | WARN | Not set — Architect should be `cyan` or `blue` |
| Size | PASS | Under 200 lines (way under) |

## Findings

### FAIL #1 — Description won't trigger auto-delegation

**Current:** "An expert software architect who can help design systems."

**Problem:** No imperative phrase, no trigger words. Claude's router has nothing to match against. This is the root cause of "never gets auto-invoked."

**Fix:**

```yaml
description: |
  Use PROACTIVELY when the task involves system architecture decisions, service boundaries, scaling trade-offs, or technology selection.
  MUST BE USED when the user asks "how should we design X", evaluates microservices vs monolith, or plans for 10x growth.
  Triggers: architecture review, system design, "should we use X", scaling, service boundaries, design trade-offs.
```

### FAIL #2 — Unsafe tool grant

**Current:** `Read, Write, Edit, Bash, Grep, Glob, WebFetch`

**Problem:** Architect agents review and recommend; they don't edit code. `Write`/`Edit` enable accidental changes during exploration.

**Fix:**

```yaml
tools: Read, Grep, Glob
```

(Add `WebFetch` only if the agent needs to look up external architecture references — and explain why in a comment.)

### FAIL #3 — Model not set

**Current:** No `model` field.

**Problem:** Inherits session model. If the user runs Opus, every architect invocation costs Opus tokens — overkill for most architecture reviews.

**Fix:**

```yaml
model: sonnet
```

Escalate to `opus` only with explicit rationale (e.g., the agent is intended specifically for the hardest cross-system architecture decisions). Document the reason in a comment.

### FAIL #4 — System prompt has no operational structure

**Current:** Persona prose + "provide thoughtful analysis".

**Problem:** No Responsibilities, no Do-not, no Workflow, no Verification, no Output Format. The agent has no reliable behavior — it will produce different shapes of output every invocation.

**Fix:** rewrite the system prompt using the canonical skeleton (see `examples/canonical-agent.md`). Skeleton:

```markdown
You are a focused architecture review subagent specializing in system boundaries, scaling risks, and technology trade-offs.

## Responsibilities
1. Review proposed or existing architecture for boundary violations and coupling.
2. Evaluate scaling and operational risks.
3. Compare against established patterns in the codebase.

## Do not
- Edit files or write code.
- Re-implement features.
- Speculate beyond what is observable in the code or docs.

## Workflow
1. Identify the relevant modules, interfaces, and architectural seams.
2. Read existing patterns in similar areas of the codebase.
3. Evaluate the proposal against those patterns.
4. Identify scaling, coupling, and ownership risks.
5. Format findings using the output template.

## Verification Behavior
For each finding:
- Cite specific files / interfaces.
- Reference existing patterns or established conventions.
- Distinguish observed risks from speculative concerns.

## Output Format
- **Critical risks** — boundary violations, scaling failures, coupling
- **Design weaknesses** — weak abstractions, unclear ownership
- **Positive signals** — patterns aligned with existing design
- **Files reviewed**
- **Recommended next step**
```

## Modernize Recommendation

Apply all four fixes together. The agent will then:
- Auto-trigger on architecture-related tasks (description fixes #1)
- Run safely without accidental edits (tools fix #2)
- Use appropriate model cost (#3)
- Produce consistent, useful output (#4)

## Recommended Next Step

Run `agent-author` in **Modernize mode** to apply these fixes:
> "Modernize ~/.claude/agents/architect.md per the audit findings"

Or apply manually using the patches above. Re-run audit afterwards to confirm all checks PASS.

---

## Notes on this report shape

- **Verdict line up top** — user knows immediately whether the agent is OK or broken.
- **Checklist table** — every check from `output-formats.md` audit checklist, with status.
- **Findings grouped by severity** — FAILs first, with root cause + specific fix code shown inline.
- **Modernize recommendation** — explicit next-step invocation the user can run.

This shape works for both "audit this agent" requests and post-Modernize verification reports.
