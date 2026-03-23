# Gold-Standard Skill Conventions

The definitive reference for skill structure. Apply when creating, converting, or auditing skills.

---

## Skill Anatomy

skills/[skill-name]/
├── SKILL.md           # Core logic (always loaded, <500 lines, <25 KB)
├── reference/         # Advanced protocols (loaded on demand)
├── templates/         # Document templates
├── examples/          # Real-world scenarios
└── validation.md      # Quality checklists

**Progressive disclosure**: Only `SKILL.md` is loaded into context. Reference files, templates, and examples are loaded when the skill explicitly requests them — keeping context lean for simple invocations.

---

## Frontmatter

Required fields:

name: kebab-case-name                        // Lowercase, numbers, hyphens (max 64 chars)
description: What it does and when to use it  // Max 1024 chars

Optional fields:

allowed-tools: Task, Bash, Read              // Tools without permission prompts
user-invocable: true                         // false = hides from / menu
argument-hint: "description of arguments"    // Shown in / menu
disable-model-invocation: false              // true = only user can invoke
context: fork                                // Run in subagent
agent: Explore                               // Subagent type when context: fork
model: haiku | sonnet | opus                 // Pin to specific model (omit for default)

### Model Selection

```yaml
model: haiku | sonnet | opus
```

Use to pin a skill to a specific Claude model:

| Model | When to use |
|-------|-------------|
| `haiku` | Fast, cheap tasks: lookup, formatting, simple transforms |
| `sonnet` | Default for most skills — balanced speed and quality |
| `opus` | Complex reasoning, multi-step analysis, judgment calls |

Most skills should not set `model` — let the user's configured model handle it. Only set it when the skill's task has a clear cost/quality tradeoff that benefits from pinning.

### Agent Forking

```yaml
context: fork        # Run this skill in a subagent context
agent: Explore       # Subagent type: Explore, general-purpose, or any registered agent type
```

Use `context: fork` when the skill's work is genuinely independent and benefits from a clean context. Use `agent:` to specify which subagent type handles the forked execution.

For skills that need to delegate to a domain specialist, use the `find-agents.sh` script (see `skills/skill-author/find-agents.sh`) to discover available agents rather than hardcoding agent names.

### Description Guidelines

- Explain WHAT the skill does AND WHEN to use it
- Include keywords users would naturally say
- Keep it focused on triggers, not implementation details
- Write in third person (injected into system prompt)
- NEVER describe the workflow in the description — agents will follow it as a shortcut and skip the body

### String Substitutions

$ARGUMENTS              // All arguments passed when invoking
$ARGUMENTS[0]           // First argument
${CLAUDE_SESSION_ID}    // Current session ID
!`shell command`        // Execute command, insert output (preprocessing)

### Security Note
Never combine `!`shell command`` preprocessing with `$ARGUMENTS` — this executes user input as a shell command at skill load time. Use `Bash()` in the Workflow section instead, where the AI mediates the execution.

---

## Claude Search Optimization (CSO)

Skills are discovered by Claude reading their description. The description field is the primary discovery mechanism — get it wrong and the skill never loads.

### Description: When to Use, NOT What the Skill Does

**Critical rule:** Description must describe triggering conditions only. Never summarize the skill's workflow.

**Why this matters:** When a description summarizes the workflow, Claude may follow the description as a shortcut and skip reading the full skill body. A description saying "dispatches subagent per task with code review between tasks" caused Claude to do ONE review even though the skill's flowchart showed TWO. Changing the description to just triggering conditions fixed the behavior.

```yaml
# ❌ BAD: summarizes workflow — Claude skips the body
description: Use when creating skills — search for duplicates, write SKILL.md, test with subagents

# ✅ GOOD: triggering conditions only
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
```

### Keyword Coverage

Use words Claude would search for:
- Error messages verbatim: `"Hook timed out"`, `"ENOTEMPTY"`
- Symptoms: `"flaky"`, `"hanging"`, `"not working"`
- Synonyms: timeout/hang/freeze, cleanup/teardown
- Tool names and library names

### Token Efficiency Targets

Skills are loaded into context on every invocation. Every token costs money and attention.

| Skill type | SKILL.md target |
|------------|----------------|
| Frequently loaded (orchestrators) | < 200 lines |
| Standard skills | < 500 lines |
| Reference files | No hard limit — only loaded on demand |

**Techniques:**
- Move educational content, examples, and verbose checklists to `reference/` files
- Reference `--help` instead of documenting all flags inline
- Cross-reference other skills instead of repeating their content
- One excellent example beats five mediocre ones

---

## Skill Body: PICS + Workflow

Section order — each section is a `## ` heading:

## Persona               // Role and expertise frame
## Interface             // Data shapes + State
## Constraints           // Always / Never markdown lists
## Reference Materials   // Optional — links to progressive disclosure files
## Workflow              // Numbered ### headings + entry point

### Persona

Sets the AI's role and expertise frame. Keep enforcement rules out — those go in Constraints.

### Interface

Data shapes using TypeScript-like syntax. Inline enum values directly — no `type` aliases. Include State and optional Scope blocks here.

Finding {
  severity: CRITICAL | HIGH | MEDIUM | LOW
  title: String
  fix: String
}

State {
  target = $ARGUMENTS
  perspectives = []              // populated from reference/perspectives.md
  findings: [Finding]
}

**In scope:** What this skill acts on.
**Out of scope:** What is off-limits.

**Why TypeScript-like syntax**: LLMs have extensive training on TypeScript interfaces. This format has near-zero parsing overhead and unambiguously communicates output contracts.

No forward declarations — the Workflow headings serve as the function index.

### Constraints

Use markdown **Always:** and **Never:** lists. Each rule appears once, in whichever framing is most natural. Move enforcement-worthy rules from Persona into **Never:**.

**Always:**
- Every finding must have a specific, implementable fix.
- Provide full file context to reviewers, not just diffs.

**Never:**
- Review code yourself — always delegate to specialist agents.
- Present findings without actionable fix recommendations.

**Why markdown over `Constraints {}`**: The words "Always" and "Never" carry the full semantic weight. Curly braces add no structural value the LLM uses — markdown headers and bold labels provide the same grouping with better training-data alignment.

### Reference Materials

Links to progressive disclosure files. Keep descriptions minimal — the LLM reads the file content. Only include when the skill has a `reference/` directory.

- reference/perspectives.md — review perspectives
- reference/output-format.md — output guidelines

### Workflow

Define each step as a numbered `###` heading. Use natural language for procedures. Use `match` blocks only for 3+ branch routing decisions. Use numbered sub-steps for data processing pipelines.

### 1. Gather Context

Determine the review target from $ARGUMENTS.

match (target) {
  PR number     => gh pr diff $target
  "staged"      => git diff --cached
  default       => git diff main...$target
}

### 2. Synthesize Findings

Process findings:
1. Deduplicate overlapping findings.
2. Sort by severity (descending).
3. Build summary table.

### Entry Point (Non-Linear Workflows Only)

Include an `### Entry Point` section only when the workflow has non-linear execution — branching, looping, or step-skipping based on input. For sequential workflows, the numbered headings already communicate execution order.

Examples of non-linear entry points:
- Mode-based routing: `match (mode) { Create => steps 2, 3, 7 | Audit => steps 4, 7 }`
- Argument-based routing: `match (target) { new => step 1 | existing => step 3 }`
- Loop patterns: `Repeat steps 2-4 for each section`

**What to use where**:

| Construct | Use for | Don't use for |
|-----------|---------|---------------|
| `match (x) { a => b }` | 3+ branch routing decisions | Binary if/else (use prose) |
| Numbered sub-steps | Data processing, multi-step operations | — |
| Markdown `### N. Step Name` | Workflow steps | — |
| `AskUserQuestion:` | User choice points | — |
| `Read reference/X.md` | Loading progressive disclosure files | — |

**Why markdown headings over `fn` definitions**: LLMs process markdown headers as their strongest structural signal. `fn` definitions trigger code-interpretation patterns and require the LLM to learn the novel `fn`/no-`fn` entry-point convention. Numbered headings are immediately parseable.

---

## Skill Types

| Type | Purpose | Structure |
|------|---------|-----------|
| **Technique** | How-to guide with steps | Workflow + examples |
| **Pattern** | Mental model or approach | Principles + when to apply |
| **Reference** | API/syntax documentation | Tables + code samples |
| **Coordination** | Orchestrate multiple agents | Perspectives + synthesis |

---

## The Iron Law: Test Before You Ship

**No skill ships without a failing test first.** This applies to new skills AND edits to existing skills.

The process:
1. **RED** — Run a pressure scenario WITHOUT the skill. Document what the agent does wrong (exact rationalizations verbatim).
2. **GREEN** — Write the skill addressing those specific failures. Run the same scenario WITH the skill.
3. **REFACTOR** — Find new rationalizations, add counters, re-test until bulletproof.

See `reference/testing-with-subagents.md` for pressure scenario methodology.

### Discipline-Enforcing Skills Need Extra Work

Skills that enforce rules (TDD, verification-before-completion) need rationalization-proofing:
- Use strong language: "YOU MUST", "No exceptions"
- Add a **Red Flags** section listing thoughts that signal the agent is about to rationalize
- Build an excuse → reality table from actual baseline test output
- See `reference/persuasion-principles.md` for language patterns backed by research

---

## Discipline-Enforcing Skills

Skills that enforce rules (TDD, verification) need special attention:
- Use strong language: "YOU MUST", "No exceptions", "Never"
- Add rationalization counters (excuse → reality table)
- Add Red Flags section listing rationalizations that indicate violation
- Test with 3+ combined pressure scenarios (see testing-with-subagents.md)
- See persuasion-principles.md for research on language patterns

---

## Token Optimization

Skills are loaded into context on every invocation. Every token costs money, context space, and LLM attention.

### Constraint Deduplication

Each rule appears once, in whichever framing (**Always** or **Never**) is most natural. Never mirror the same rule in both lists.

Bad — same rule stated twice:
```
**Always:** Run tests after every change.
**Never:** Skip test verification after a change.
```

Good — one rule, one location:
```
**Never:** Skip test verification after a change.
```

### Progressive Disclosure Enforcement

Content belongs in `reference/` (not SKILL.md) when it is:
- **Educational** — examples, catalogs, before/after patterns
- **Conditional** — only needed for specific target types
- **Verbose** — tables, checklists, detailed output format specs

SKILL.md should contain only **behavioral instructions** — what to do, when, and how to route.

### State Comments

Only comment State fields when the origin is non-obvious:

Bad: `mode: Standard | Team  // chosen by user in selectMode`
Good: `perspectives = []  // from reference/perspectives.md`

---

## Transformation Checklist

When converting an existing skill to these conventions:

**Structure:**
- [ ] Restructure body into PICS + Workflow sections
- [ ] Inline enum values into interface fields; remove `type` aliases
- [ ] Merge State into Interface section
- [ ] Replace `Constraints { require {} never {} }` with markdown **Always:** / **Never:** lists
- [ ] Replace `fn` workflow definitions with numbered `### N. Step Name` headings
- [ ] Replace entry-point pipe chain with `### Entry Point` section (only if workflow is non-linear)
- [ ] Replace novel syntax blocks (prefer/avoid) with **In scope:** / **Out of scope:**

**Token efficiency:**
- [ ] Deduplicate Always/Never — no mirrored rules
- [ ] Move enforcement-worthy Persona rules into **Never:**
- [ ] Remove forward declarations from Interface
- [ ] Remove self-evident State comments
- [ ] Use explicit reference loading (`Read reference/X.md`) not implicit (`per reference/X`)
- [ ] Trim Reference Materials descriptions to path + short label
- [ ] Externalize educational/verbose content to reference/

**Validation:**
- [ ] `match` blocks used only for 3+ branch routing
- [ ] No `|>` pipe chains — use numbered sub-steps instead
- [ ] No content/logic lost in transformation

---

## Canonical Example

See `../examples/canonical-skill.md` for a fully annotated skill demonstrating all conventions.
