# Subagent Anti-Patterns

Community-validated failure modes from real-world Claude Code subagent usage. Reject any agent that exhibits these patterns; modernize existing agents to remove them.

---

## 1. The Mega-Generalist

**Symptom:** "An expert senior engineer who can review, debug, architect, and write tests."

**Why it fails:**
- Description is too broad to trigger reliably — Claude's router can't distinguish from main-agent scope.
- High overlap with main agent → Claude defaults to handling it inline.
- No distillation benefit — agent's output reads like main-agent output.

**Fix:** split into focused archetypes (Reviewer, Debugger, Architect). Each gets one job, one trigger pattern, one output format.

---

## 2. The Persona Cosplay

**Symptom:** "You are a 10x rockstar engineer with 20 years of experience at FAANG..."

**Why it fails:**
- Persona prose adds zero routing or verification value.
- Wastes tokens on every invocation.
- Distracts from the operational instructions.

**Fix:** open with a single sentence: `You are a focused <archetype> subagent specializing in <domain>.` Move all enforcement to **Responsibilities**, **Do not**, and **Workflow** sections.

---

## 3. The All-Tools-Just-in-Case

**Symptom:** `tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, Task, ...`

**Why it fails:**
- Reviewer/Explorer agents shouldn't have `Write` — risk of accidental edits.
- Security agents shouldn't have `Write` — could leak findings into the repo.
- Bash without scope can run anything → unsafe and unauditable.
- More tools = more surface for the agent to drift off task.

**Fix:** strip to archetype default. Add a tool only with explicit reason in a comment.

---

## 4. The Inherit-Model Trap

**Symptom:** `model: inherit` (or no `model` set, with the user running Opus)

**Why it fails:**
- Inherits the session model — usually Opus.
- Spends Opus tokens on tasks that Sonnet handles fine.
- Compounds across many invocations.

**Fix:** explicit `model: sonnet` for nearly everything. Escalate to `opus` only for deep architecture, hardest debugging, or critical security audits — and document the reason.

---

## 5. The Free-Prose Output

**Symptom:** "Here's what I found: ..." — followed by paragraphs of unstructured text.

**Why it fails:**
- Hard to parse for orchestration (commands, other skills, the main agent).
- Important findings buried in prose.
- Inconsistent across invocations.

**Fix:** every agent gets a fixed format with named rubrics (Critical/Warning/Suggestion, Symptom/Root Cause/Evidence, etc.). See `output-formats.md`.

---

## 6. The Chat Buddy

**Symptom:** Agent designed for back-and-forth dialogue, brainstorming, "let's iterate together".

**Why it fails:**
- Subagents run with their own context — they don't see the conversation history naturally.
- Iterative chat belongs in the main thread.
- Each round wastes context-isolation benefit.

**Fix:** subagents deliver **focused artifacts** (reports, plans, diffs, findings). Move interactive work to the main thread or a slash command.

---

## 7. The Repo-Vacuum

**Symptom:** Agent reads "the whole codebase" and returns a 5000-line report.

**Why it fails:**
- Pollutes both the agent's context and the main agent's response.
- Defeats the context-isolation purpose.
- Findings get lost in the noise.

**Fix:** the agent must filter aggressively. Add to **Workflow**: "Identify only files relevant to the change/task. Read those fully. Do not load the entire repo." Add to **Output format**: "Return only findings that matter — no exhaustive lists."

---

## 8. The Plan-Mode Replacement

**Symptom:** A "research" or "architect" subagent that does what `Plan Mode` already does.

**Why it fails:**
- Plan Mode + main-thread exploration handles most "investigate this" cases cleanly.
- The subagent adds context-switching cost without unique benefit.
- User has to constantly re-explain the task.

**Fix:** before authoring a research/architect subagent, ask: "would Plan Mode + main-thread Explore handle this?" If yes, skip the subagent.

---

## 9. The Stale Description

**Symptom:** Agent's description was written when the feature launched, never updated. Doesn't include current trigger phrases users actually say.

**Why it fails:**
- User language evolves; trigger phrases drift.
- Old descriptions miss new failure modes the agent could handle.
- Auto-delegation rate decays silently over time.

**Fix:** modernize descriptions periodically. When auditing, check description against current user vocabulary. Update trigger phrases.

---

## 10. The Over-Reliance on Auto-Delegation

**Symptom:** Agents designed assuming Claude will always auto-invoke them when relevant.

**Why it fails:**
- Auto-delegation is non-deterministic — even a perfect description doesn't guarantee invocation.
- Users may need to invoke explicitly: "Use the code-reviewer agent to ..."
- Without a manual fallback, the agent is unreliable.

**Fix:**
- Make descriptions strong (see `description-patterns.md`) but don't rely on them alone.
- Document explicit invocation in the agent's README or in the main repo's CLAUDE.md.
- Consider a slash command (`/review-change`) that explicitly invokes the subagent.

---

## Reject-on-Sight Checklist

When auditing, immediately reject the agent if:

- [ ] Description has no `Use PROACTIVELY` / `MUST BE USED`
- [ ] Description summarizes the workflow
- [ ] Tools list is "all tools" or unjustifiably broad
- [ ] Model is `inherit` (with no explicit reason)
- [ ] No fixed output format
- [ ] Persona prose dominates the system prompt
- [ ] Scope overlaps significantly with another existing agent
- [ ] Agent designed for interactive chat
