# Setting Up Your Claude Project

Create one Claude project for all external workflow phases (brainstorm, PRD, constitution).
You do not need separate projects per phase — reuse the same project.

---

## Steps

1. Go to [claude.ai](https://claude.ai) and sign in.
2. In the left sidebar, click **Projects**, then **New project**.
3. Name it something like `[Your Project Name] — Dev Workflow`.
4. Open **Project instructions** (gear icon or "Edit project instructions").
5. Paste the system prompt below into the instructions field.
6. Save the project.

---

## System Prompt

```
You are helping with a software project that follows The Custom Startup development framework.
This framework uses spec-driven development with three documents per feature:
requirements.md (PRD), solution.md (SDD), and a plan/ directory.

When I paste a template at the start of a conversation, follow its instructions exactly.
The template defines your persona, constraints, and workflow for that session.

General rules that apply in all sessions:
- Ask one question at a time.
- Wait for my approval before finalizing anything.
- Never include technical implementation details in PRD work.
- Apply YAGNI — strip unnecessary features from all designs.
```

---

## How to Use It

For each workflow phase, start a **new conversation** inside the project:

1. Click **New chat** (inside the project, not from the sidebar).
2. Paste the relevant template as your first message:
   - Brainstorm → `brainstorm-prompt.md`
   - PRD → `prd-prompt.md`
   - Constitution → `constitution-prompt.md`
3. Replace all `{{PLACEHOLDER}}` values in the template before sending.
4. The project context is pre-loaded; the template activates the skill.

The project remembers the framework. Each new conversation gets a fresh context for the specific phase.

---

## Tips

- Keep conversations single-phase. Do not mix brainstorm and PRD in one conversation — start a new chat for each phase.
- Copy the final output before closing a conversation. Claude.ai does not export automatically.
- Templates also work standalone — you can paste them into any Claude.ai conversation without a project, or into ChatGPT. The system prompt just saves you from explaining the framework each time.
