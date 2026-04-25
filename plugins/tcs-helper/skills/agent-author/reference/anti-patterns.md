# Subagent Anti-Patterns

Failure modes from the official Anthropic guidance, the `the-startup` PRINCIPLES.md (April 2026), and community experience. Reject any agent that exhibits these patterns; modernize existing agents to remove them.

**Sources:**
- [Anthropic — Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [rsmdt/the-startup PRINCIPLES.md § 4.5](https://github.com/rsmdt/the-startup/blob/main/docs/PRINCIPLES.md)
- [Steve Kinney — Common Sub-Agent Anti-Patterns and Pitfalls](https://stevekinney.com/courses/ai-development/subagent-anti-patterns)

---

## Tool & Permission Anti-Patterns

### `tools: *`

Grants Bash, Write, everything. Loses parent's approval history → every call re-prompts. Highest-severity reject-on-sight.

**Fix:** explicit whitelist per archetype. See `conventions.md` § Tool Scoping.

### `tools: inherit` without justification

Inheriting parent tools loses dangerous-tool approvals. Use `inherit` only when the agent genuinely needs the parent's full toolset AND the user has explicitly opted in.

**Fix:** explicit `tools: Read, Grep, Glob` (or whatever's actually needed).

### Headless write-capable agent with no review gate

Agent has `Write` and `Edit` and runs autonomously without `permissionMode: plan` or human review between read and write phases.

**Fix:** add `permissionMode: plan` or split into a read-only audit agent + a separate apply step that requires user confirmation.

### Permission-mode confusion

Setting `permissionMode: auto` on a subagent assuming it loosens the parent's stricter mode. Parent mode wins when stricter; subagent mode is honored only if as-strict-or-stricter.

**Fix:** test in the actual permission context the agent will run in. Document the expected mode.

---

## Scope & Identity Anti-Patterns

### The Mega-Generalist (PRINCIPLES § 4.5)

Single agent with 50+ KB prompt and ten responsibilities. Examples: *"You are a senior 10x rockstar who reviews, debugs, designs, and writes tests."*

**Why it fails:**
- Description too broad to trigger reliably
- High overlap with main agent → Claude defaults to handling inline
- No distillation benefit — output reads like main-agent output
- Un-parallelizable, hard to audit

**Fix:** split into focused activity-scoped archetypes. See PRINCIPLES § 2.4 — *"Many small activity-scoped agents beat single role-agents."*

### The Persona Cosplay

*"You are a 10x rockstar engineer with 20 years of experience at FAANG..."*

**Why it fails:**
- Persona prose adds zero routing or verification value
- Wastes tokens on every invocation
- Distracts from operational instructions

**Fix:** open with a single sentence: `You are a focused <archetype> subagent specializing in <domain>.` All enforcement → Constraints, Activities.

### The Chat Buddy

Agent designed for back-and-forth dialogue, brainstorming, *"let's iterate together."*

**Why it fails:**
- Subagents have isolated context — they don't see the conversation history
- Iterative chat belongs in the main thread
- Each round wastes context-isolation benefit

**Fix:** subagents deliver **focused artifacts** (reports, plans, diffs, findings). Move interactive work to main thread or a slash command.

---

## Description Anti-Patterns

### Generic Role Description

`description: An expert software architect.`

**Why it fails:** no action verb, no triggers, overlaps with main agent.

**Fix:** see `description-patterns.md` for the action + trigger + examples pattern.

### Workflow Summary in Description (PRINCIPLES § 3.4 documented bug)

`description: Reads files, analyzes diff, runs tests, writes report.`

**Why it fails:** Claude may follow the description as a shortcut and skip reading the system prompt body. **Documented failure mode** — caused real production behavior breaks (one review instead of two when description summarized "two-stage review").

**Fix:** description = triggering conditions only. Workflow stays in body.

### Stale Description

Agent's description was written when the feature launched, never updated. Misses current trigger phrases users say.

**Fix:** modernize descriptions periodically. When auditing, check description against current user vocabulary.

---

## Context & Communication Anti-Patterns

### Assuming Parent Context Is Visible

Agent system prompt references *"the file we just discussed"* or *"the user's earlier point about X"*. **Subagents do not see parent conversation.** They get only: their system prompt, the Agent-tool task prompt, project `CLAUDE.md`, and their tool catalog.

**Fix:** the Agent-tool dispatch prompt is the **only** parent → child channel. Pass everything explicitly: file paths, decisions, constraints.

### The Repo-Vacuum

Agent reads the whole codebase and returns a 5000-line report. Defeats context-isolation purpose.

**Fix:** add explicit filtering in workflow ("Identify only files relevant to the change") and aggregation in output ("Return only findings that matter — no exhaustive lists").

### Parallel Agents With Implicit Inter-Dependencies

Spawning 3 sibling agents that assume they can see each other's outputs. Siblings return to parent independently — they cannot communicate.

**Fix:** either sequence them (run A, pass result to B), or escalate to Agent Teams for genuine peer coordination.

### Context Bloat From Verbose Returns

Agent returns full transcripts, exhaustive file lists, raw test output. Pollutes parent context, kills isolation benefit.

**Fix:** require key findings only in `Output` section. *"Filtered one-line failure summaries cross barriers; raw transcripts do not."* (PRINCIPLES § 5.6)

---

## Structural Anti-Patterns

### No Output Format

Agent returns free-form prose. No rubrics, no named fields, no typed table.

**Why it fails:** hard to parse for orchestration, important findings buried in prose, inconsistent across invocations.

**Fix:** every agent gets a fixed `## Output` section with typed table or named rubrics. See `output-formats.md`.

### Wrong Mechanism Choice

Building a subagent for what should be a skill (or vice versa). Symptoms:
- "Subagent" runs every interaction with no real isolation benefit
- User constantly re-explains context the agent should already have
- Agent's output is incremental dialogue, not a distilled artifact

**Fix:** run through `decision-tree.md` Q1 ("Should output remain visible in parent conversation?"). If you find yourself building a subagent for an inherently inline task, switch to a skill.

### Plan-Mode Replacement (PRINCIPLES § 4.5 implicit)

Building a "research" or "architect" subagent to do what `Plan Mode` already handles cleanly.

**Why it fails:**
- Plan Mode + main-thread Explore handles most "investigate this" cases
- The subagent adds context-switching cost without unique benefit

**Fix:** before authoring, ask: "would Plan Mode + main-thread Explore handle this?" If yes, skip the subagent.

---

## Model & Cost Anti-Patterns

### Over-Specced Model

Using `model: opus` for a reviewer that does straightforward code reading.

**Why it fails:** 5× the input cost, 5× the output cost vs sonnet. Compounds across many invocations.

**Fix:** sonnet is the default. Opus only with explicit rationale (deep architecture, hard root-cause, critical security).

### Under-Specced Model

Using `model: haiku` for substantive reasoning work (architecture decisions, complex debugging).

**Why it fails:** Haiku is for read-heavy, narrow tasks. Substantive reasoning produces shallow output and may require retries.

**Fix:** if the agent's activities involve trade-off analysis, multi-file reasoning, or judgment calls, use sonnet.

### Implicit Inheritance When Session = Opus

Omitting `model:` field on activity agents. When user runs Opus, every dispatch costs Opus tokens.

**Fix:** TCS convention — explicitly set `model: sonnet` for team-style activity agents. Predictable cost, no inheritance surprises.

---

## Reject-on-Sight Checklist

When auditing an agent, immediately reject if:

- [ ] Description has no `Use PROACTIVELY` / `MUST BE USED`
- [ ] Description summarizes the workflow
- [ ] `tools: *` or unjustifiably broad list
- [ ] `tools: inherit` without explicit justification
- [ ] Model is `inherit` (with no documented reason)
- [ ] No `## Output` section with explicit format
- [ ] Persona prose dominates the system prompt
- [ ] Scope overlaps significantly with main agent or another existing agent
- [ ] Designed for interactive chat instead of artifact delivery
- [ ] Body exceeds 25 KB without progressive disclosure to references
