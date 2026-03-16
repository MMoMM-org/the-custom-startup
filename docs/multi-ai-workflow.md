# Multi-AI Workflow

This guide explains how to use external AI tools (Claude.ai, Perplexity, ChatGPT) alongside Claude Code to complete the full spec-driven development workflow when you are not inside a Claude Code session.

---

## Why Multiple Tools?

Claude Code has codebase access, tool execution, and the full plugin suite. External tools don't. But external tools are available anywhere — mobile, browser, a colleague's machine — and each has different strengths.

| | Perplexity | Claude.ai | Claude Code |
|---|---|---|---|
| **Web search** | Native, always on | Available (Pro/Team plans) | Via agents (WebSearch) |
| **Best for** | Research, current data, citations | Brainstorm, PRD, constitution design | SDD, PLAN, implement, review |
| **Codebase access** | No | No | Yes |
| **Cost** | Separate subscription | Claude subscription | Claude subscription |
| **Persistent context** | Spaces (shared prompt) | Projects (shared prompt) | Working directory + CLAUDE.md |

---

## Phase Mapping

The spec-driven workflow has five phases. Here is which tool to use for each:

| Phase | Slash Command | Best External Tool | Notes |
|---|---|---|---|
| Constitution (optional) | `/start:constitution` | Claude.ai | Use `constitution-prompt.md`; run once per project |
| Research | `/start:analyze` | Perplexity | Use `research-prompt.md` |
| Brainstorm | `/start:brainstorm` | Claude.ai | Use `brainstorm-prompt.md` |
| Requirements (PRD) | `/start:specify` | Claude.ai | Use `prd-prompt.md` |
| Solution + Plan + Implement | `/start:implement` | Claude Code only | Requires codebase access |

The final phase (SDD, PLAN, implementation) requires reading and writing code. Use Claude Code for that.

---

## Claude Only (No Perplexity)

If you do not have Perplexity, you have two options for research:

**Option A — Claude.ai with web search:** The same `research-prompt.md` templates work. Enable web search in Claude.ai (requires Pro or Team plan). Results are slightly less reliable for current data but reasoning quality is higher.

**Option B — Claude Code analyze:** Run `/start:analyze` directly in Claude Code. The analyze skill launches parallel specialist agents with WebSearch access. Best option when the research target is your own codebase or technology stack.

Trade-off: Perplexity is optimized for citation-heavy retrieval. Claude (all versions) is better at reasoning about what the findings mean. Use whichever fits your need.

---

## The Project and Space Architecture

The key insight: **template = skill, adapted for external use.**

The Claude project or Perplexity space provides only minimal framework context. When you want to invoke a "skill" externally, you paste the corresponding template as your first message. The template carries the full persona, constraints, and workflow — identical quality to running the slash command in Claude Code.

**Two usage modes for every template:**

1. **With project/space** — The project system prompt is pre-loaded. Paste the template as the first message of a new conversation. The project remembers the framework; the template activates the skill.

2. **Standalone** — Paste the template into any Claude.ai conversation (or ChatGPT, or any LLM). It is fully self-contained. No project needed.

**One project, one space.** Do not create a separate Claude project for brainstorm and another for PRD. Use a single project for all Claude.ai workflow phases. Reuse the same Perplexity space for all research queries. See `setup-claude-project.md` and `setup-perplexity-space.md` for setup instructions.

---

## Template Files

| Template | Use For | Mirrors Skill |
|---|---|---|
| `constitution-prompt.md` | Project governance rules | `start:constitution` |
| `research-prompt.md` | Market, technology, and problem research | `start:analyze` |
| `brainstorm-prompt.md` | Idea exploration and design | `start:brainstorm` |
| `prd-prompt.md` | Product requirements document | `start:specify-requirements` |
| `setup-claude-project.md` | One-time Claude.ai project setup | — |
| `setup-perplexity-space.md` | One-time Perplexity space setup | — |

---

## Spec Paths Note

The export/import scripts (`export-spec.sh`, `import-spec.sh`) currently hardcode `.start/specs/` as the spec directory. If your project uses a different path, edit the scripts directly. A configurable `SPECS_DIR` variable will be added in a future installer update.

---

## Typical Session Flow

```
0. Constitution (Claude.ai, optional, once per project)
   → new conversation in your Claude project
   → paste constitution-prompt.md with your project description
   → iterate through discovery questions
   → copy the final CONSTITUTION.md content into your repo

1. Research (Perplexity or Claude.ai)
   → paste research-prompt.md with your question
   → copy findings to clipboard or a scratch file

2. Brainstorm (Claude.ai)
   → new conversation in your Claude project
   → paste brainstorm-prompt.md with your idea
   → iterate until design is approved

3. PRD (Claude.ai)
   → new conversation in your Claude project
   → paste prd-prompt.md with your feature description
   → iterate section by section until complete
   → copy the final Markdown output

4. SDD + PLAN + Implement (Claude Code)
   → open your project in Claude Code
   → paste or import the PRD
   → run /start:specify to generate SDD and PLAN
   → run /start:implement to execute the plan
```

### Step-by-step: using the output from each phase

**Step 0 — Constitution**

1. Open `docs/templates/constitution-prompt.md` and copy the full contents.
2. Fill in `{{PROJECT_DESCRIPTION}}`, `{{TECH_STACK}}`, and `{{FOCUS_AREAS_OR_LEAVE_BLANK}}`.
3. Start a new conversation in your Claude project and paste the filled-in template.
4. Answer the discovery questions one by one. Claude will propose rules after each area.
5. When all rules are approved, Claude outputs a complete `CONSTITUTION.md`. Copy it.
6. Save it as `CONSTITUTION.md` in your project root. No script needed — it is a plain file.

**Step 1 — Research**

1. Open `docs/templates/research-prompt.md` and pick the query that fits your need (market, tech evaluation, best practices, or problem validation).
2. Copy that query block and fill in the `{{PLACEHOLDER}}` values.
3. Paste into a new Perplexity thread (or Claude.ai conversation) and send.
4. When the response is complete, copy the Markdown output and save it as a local file, for example `research-notes.md`. This file is for your own reference only — it does not go into the spec.
5. Keep the file open while you brainstorm. Paste the Summary and Recommendations sections into the brainstorm or PRD template as additional context.

**Step 2 — Brainstorm**

1. Open `docs/templates/brainstorm-prompt.md` and copy the full contents.
2. Fill in `{{IDEA_DESCRIPTION}}`. Optionally paste relevant research findings below it as extra context.
3. Start a new conversation in your Claude project and paste the filled-in template.
4. Work through the dialogue — probe, approaches, design sections — until you reach the Conclude step.
5. When Claude presents the final design summary, copy it and save it as a local file, for example `brainstorm-notes.md`.
6. You do not need to import this file with a script. Paste the design summary into the PRD template in the next step as the `{{OPTIONAL_CONTEXT}}` input.

**Step 3 — PRD**

1. Open `docs/templates/prd-prompt.md` and copy the full contents.
2. Fill in `{{FEATURE_DESCRIPTION}}`. Paste your brainstorm design summary (and any research notes) into `{{OPTIONAL_CONTEXT}}`.
3. Start a new conversation in your Claude project and paste the filled-in template.
4. Work through the eight sections one by one, approving each before moving on.
5. When validation passes, Claude outputs the complete PRD as a Markdown code block. Copy it and save it as a local file, for example `prd-output.md`.
6. Import it into your project with the import script:

```bash
./scripts/import-spec.sh --type prd --input prd-output.md
# or, to create a new spec directory at the same time:
./scripts/import-spec.sh --type prd --new my-feature --input prd-output.md
```

The script places the PRD at `.start/specs/NNN-my-feature/requirements.md`, ready for `/start:specify` in Claude Code.
