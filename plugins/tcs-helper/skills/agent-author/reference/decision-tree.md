# Agent vs Skill vs Slash Command — Decision Tree

Claude Code offers three primary mechanisms to extend behavior. Picking the wrong one is the most common failure mode for new contributors. Use this tree to decide before authoring anything.

---

## Quick Decision

```
Does the work need ISOLATED CONTEXT (separate window) and produce a DISTILLED RESULT?
├─ YES → Subagent
└─ NO ↓

Is this a REUSABLE WORKFLOW with templates/examples that should AUTO-TRIGGER on relevant tasks?
├─ YES → Skill
└─ NO ↓

Is this a USER-INVOKED SHORTCUT triggered by typing /name in the terminal?
├─ YES → Slash Command
└─ NO → reconsider scope
```

---

## Subagent — When to Use

A subagent runs in its own context window with its own model, tools, and system prompt. Choose this when:

- **The task is research-heavy** and would pollute the main context with logs, search results, or large file dumps.
- **The output is a distilled artifact** (findings, plan, report) — not an ongoing dialogue.
- **The task is a closed sub-process** with clear inputs and outputs (Explore, Review, Debug, Audit).
- **A different model would help** (e.g., Opus for deep architecture; Haiku for fast lookups).
- **A different tool set is appropriate** (read-only reviewer, write-capable implementer).

### Strong signals for subagent

- "explore the codebase and find …"
- "review this PR and report findings"
- "debug this failing test"
- "audit our security configuration"
- "run all tests and tell me what failed"

### Weak signals (probably wrong choice)

- "let's brainstorm an approach" → main thread
- "edit this file to add X" → main thread (or implementer agent if pattern is recurring)
- "show me the contents of this file" → main thread

---

## Skill — When to Use

A skill is a directory with a `SKILL.md` and supporting files. It loads into the main context when Claude detects a matching task. Choose this when:

- **The work is a reusable workflow** that benefits from templates, examples, or step-by-step guidance.
- **You want auto-discovery** based on task keywords (Claude reads the description and decides to invoke).
- **The skill should run in main context** (not isolated) so the user can iterate on the same files and history.
- **The work involves multiple files or a richer scaffold** — references, templates, examples.

### Strong signals for skill

- "always when X, do Y" (recurring pattern)
- "we have a standard procedure for Z"
- "I want a guided workflow for setting up …"
- "auto-apply when Claude detects this kind of task"

### Weak signals (probably wrong choice)

- "I want a one-off shortcut I type" → slash command
- "I want isolated context and a focused result" → subagent

---

## Slash Command — When to Use

A slash command is a single `.md` file invoked by typing `/<name>` in the terminal. Choose this when:

- **The user wants a manual entry point** — explicit invocation, not auto-triggering.
- **The action is a one-shot operation** with predictable steps.
- **The command may orchestrate other things** (call subagents, read skills) but the entry point is a typed shortcut.
- **The user wants a discoverable, repeatable command** in their terminal workflow.

### Strong signals for slash command

- "I want to type /generate-spec to start a process"
- "give me a quick way to /run-migration-plan"
- "I'll trigger this when I'm ready, not auto"

### Weak signals (probably wrong choice)

- "auto-trigger when Claude sees X" → skill
- "isolated context with distilled result" → subagent

---

## Heuristic Cheatsheet

| User says... | Mechanism |
|---|---|
| "always when …" / "every time …" | Skill |
| "I want a separate specialist for …" | Subagent |
| "I want to type /xyz" | Slash command |
| "investigate / review / audit / debug" | Subagent |
| "guided workflow / standard procedure" | Skill |
| "manual shortcut / explicit trigger" | Slash command |

---

## Common Confusions

### "I want this to run automatically when relevant"

This describes both **skills** and **subagents**. Disambiguate:

- If the work is a procedure/workflow that runs in main context with the same conversation history → **Skill**.
- If the work needs isolated context, separate model, or distilled output → **Subagent**.

### "I want a specialist for this domain"

Domain specialization can be either:

- **Subagent** if it produces a focused artifact and benefits from context isolation.
- **Skill** if it's a procedure that uses the main context with templates and references.

Prefer subagent when the output is a report or artifact. Prefer skill when the output is incremental work in the same conversation.

### "I want this command available in the terminal"

That's a **slash command**. Slash commands are about user-invoked entry points. They can call subagents or trigger skills internally — those are implementation details.

---

## Anti-Pattern: Building a Subagent for Everything

Many users build subagents for tasks that should be skills or simply remain in the main thread. Symptoms:

- The "subagent" runs every interaction (no real isolation benefit).
- The user has to constantly explain context the agent should already have.
- The agent's output is incremental dialogue, not a distilled artifact.

If you find yourself building a subagent that takes constant back-and-forth — that's a skill or main-thread work, not a subagent.

---

## Cross-Reference

- For skill authoring: invoke `tcs-helper:skill-author`
- For slash command development: see `plugin-dev:command-development` (if available) or the official Claude Code documentation
- For subagent authoring: this skill (`agent-author`)
