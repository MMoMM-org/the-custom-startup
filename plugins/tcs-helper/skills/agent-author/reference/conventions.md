# Agent Authoring Conventions

The definitive reference for Claude Code subagent structure. Apply when creating, modernizing, or auditing agents.

---

## Agent Anatomy

agents/[agent-name].md      # Single flat file (NOT a directory)

Unlike skills, agents are **flat .md files** with YAML frontmatter. There is no `agents/foo/AGENT.md` convention — `agents/foo.md` is the only valid form.

Locations by scope:

| Scope | Path | Loaded by |
|---|---|---|
| User-global | `~/.claude/agents/<name>.md` | Every session on the machine |
| Plugin | `plugins/<plugin>/agents/<name>.md` | Sessions where plugin is enabled |
| Project | `<repo>/.claude/agents/<name>.md` | Sessions in that repo (team-shared via git) |

---

## Frontmatter

Required fields:

```yaml
---
name: kebab-case-name        # lowercase, hyphens, 3–50 chars
description: |               # action-oriented trigger description
  Use PROACTIVELY ... when ...
  MUST BE USED when ...
model: sonnet                # sonnet | opus | haiku — see Model Selection
tools: Read, Grep, Glob      # minimum set per archetype
---
```

Optional fields:

```yaml
color: blue                  # blue | cyan | green | yellow | red | magenta
```

### Description Field — The #1 Delegation Lever

Claude's auto-delegation router reads the `description` field. A passive description means the agent rarely triggers, even when relevant. See `description-patterns.md` for full templates and good/bad examples.

**Minimum requirements:**
- Contains `Use PROACTIVELY` or `MUST BE USED`
- 2–5 concrete trigger phrases (`when the task mentions X`, `when the user asks for Y`)
- Action-oriented, not role-descriptive
- Distinguishable from main-agent scope

**NEVER summarize the agent's workflow in the description** — Claude may follow the description as a shortcut and skip reading the system prompt.

### Model Selection

| Model | When to use | Examples |
|---|---|---|
| `sonnet` | **Default for almost all agents** | Reviewer, Explorer, Debugger, Implementer, Docs writer |
| `opus` | Only with explicit rationale | Deep architecture decisions, critical security audits, hardest root-cause debugging |
| `haiku` | Trivial, fast, narrow tasks | Simple file inspection, single-string lookups, basic config checks |
| `inherit` | **Reject this** | Inherits session model — usually Opus → wastes tokens for simple agents |

**Rule:** if the task could be handled in <30 seconds of reasoning, use `haiku`. If it needs systematic work over multiple files but no novel reasoning, use `sonnet`. Use `opus` only when stakes or complexity genuinely require it, and document the reason in a comment near the frontmatter.

### Tools — Minimum Per Archetype

| Archetype | Default tools | Rationale |
|---|---|---|
| Reviewer | `Read, Grep, Glob` | Read-only, no risk of accidental edits |
| Explorer | `Read, Grep, Glob` | Read-only, finds files and patterns |
| Debugger | `Read, Edit, Write, Bash` | Needs to fix code and run verification |
| Implementer | `Read, Edit, Write, Bash` | Writes and tests changes |
| Architect | `Read, Grep, Glob` | Reviews structure, doesn't edit |
| Security Reviewer | `Read, Grep, Glob` | NEVER `Write` — risk of leaking changes |
| Test Runner | `Read, Bash` | Runs tests, reads output, no edits |
| Docs Writer | `Read, Write` | Writes docs without code execution |

**Rule:** start from the archetype's default. Add tools only with stated reason. Strip anything not justified.

### Color Mapping

| Color | Semantic |
|---|---|
| blue / cyan | Analysis, exploration, review |
| green | Generation, creation, building |
| yellow | Validation, caution, warning |
| red | Security, critical, dangerous |
| magenta | Transformation, refactoring, creative |

Color is optional but useful — it lets users visually identify which agent is running in the terminal status line.

---

## System Prompt Structure

Every agent system prompt should follow this skeleton. Each section is a `## ` heading.

### 1. Role

One sentence stating the agent's identity and primary expertise frame. No long persona prose.

> You are a focused code review subagent specializing in correctness, regression risk, and missing test coverage.

### 2. Responsibilities

Numbered list. Concrete and scoped. Avoid abstract words like "ensure quality" — say what the agent actually checks.

### 3. Do not

Explicit boundaries. What the agent must NEVER do. This prevents scope creep and overlap with the main agent.

> Do not:
> - Edit files directly.
> - Re-implement features.
> - Speculate beyond what is observable in the code.

### 4. Workflow

Numbered steps describing how the agent works. Be specific — vague workflows produce vague results.

### 5. Verification Behavior

How the agent grounds its findings in evidence. Force the agent to cite file:line, quote relevant code, or run commands rather than speculate.

> For each finding:
> - Cite the exact file path and line number.
> - Quote the relevant code snippet.
> - Explain why it is a problem with reference to the codebase.

### 6. Output Format

The fixed structure for the agent's return value. See `output-formats.md` for archetype-specific templates. Free-form prose is reject-on-sight.

---

## Size Targets

| Component | Target |
|---|---|
| Frontmatter | 5–15 lines |
| System prompt | <200 lines |
| Total file | <250 lines |

If the system prompt exceeds 200 lines, externalize verbose checklists or examples to a sibling reference file (rare for agents — usually the prompt should be tight).

---

## Anatomy Example — Skeleton

```markdown
---
name: code-reviewer
description: |
  Use PROACTIVELY to review code changes for correctness, regression risk, and missing test coverage when the task mentions code review, PR review, "ready to merge", or completed implementation work.
  MUST BE USED after any non-trivial code change before the change is committed.
model: sonnet
color: blue
tools: Read, Grep, Glob, Bash
---

You are a focused code review subagent specializing in correctness, regression risk, and missing test coverage.

## Responsibilities
1. Review only files relevant to the requested change (use git diff if applicable).
2. Identify correctness issues, edge cases, and missing tests.
3. Flag regression risks tied to the change.

## Do not
- Edit files directly.
- Re-implement features or refactor unrelated code.
- Speculate beyond what is observable in the code.

## Workflow
1. Identify the change scope from $ARGUMENTS or `git diff`.
2. Read each changed file fully (not just the diff).
3. Cross-reference callers and tests for impacted symbols.
4. Run existing tests via Bash if a test command is provided.
5. Synthesize findings using the output format below.

## Verification Behavior
For each finding:
- Cite the exact file path and line number.
- Quote the relevant code snippet.
- Explain why it is a problem and propose a specific fix.

## Output Format
- **Critical** (correctness, security, data loss)
- **Warning** (regression risk, edge cases, missing tests)
- **Suggestion** (maintainability, style, naming)
- **Files checked**
- **Recommended next step**
```

This skeleton is the gold standard. See `examples/canonical-agent.md` for the fully annotated version.
