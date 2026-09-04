# Skill and Agent Design

This document captures the practical reasoning behind TCS's choice between **skills**, **subagents**, and **slash commands**. It complements [principles.md](principles.md) (which establishes *why* we specialize agents at all) by answering *which mechanism* a given piece of capability should live in.

The short version:

- **Skill** when the work and its output should remain visible in the parent conversation, or when the same procedure is reused by multiple consumers.
- **Subagent** when the work needs an isolated context, parallel dispatch, an information barrier, or produces verbose intermediate output that would bloat the parent.
- **Slash command** when the user must explicitly trigger a side-effect operation.

The cost of getting this wrong is not catastrophic — both skills and agents *work* in either role — but it is real: misplaced capability bloats context windows, dilutes auto-trigger accuracy, or duplicates maintenance.

---

## The Three Mechanisms

| Mechanism | Runtime Contract | Best At |
|---|---|---|
| **Skill** | Loaded into the parent context on description match (or explicit `/name`). Body and produced content live alongside the conversation. | Reusable procedures, domain references, deterministic decision logic, slash-invocable workflows |
| **Subagent** | Dispatched via the Agent tool. Runs in an isolated context window. Only the final message returns to the parent. | Verbose research, parallel review, information-barrier evaluations, focused output schemas |
| **Slash command** | Same as a user-invocable skill, but typically frames itself as an explicit user-triggered entry point (e.g. `/implement`, `/review`). | Side-effect operations, workflow entry points, anything the user must explicitly authorize |

Practically, skills and slash commands are the same artifact in TCS — a skill with `user-invocable: true` is reachable from the `/` menu, and that is what we call a slash command in conversation. Subagents are the categorically different mechanism, because the runtime contract (isolated context, summary-only return) is fundamentally different.

For the full decision tree with seven sequential gates, see [`tcs-helper:skill-author`'s `reference/decision-tree.md`](../../plugins/tcs-helper/skills/skill-author/reference/decision-tree.md). The remainder of this document is about the *design heuristics* that sit on top of that tree.

---

## The Load-Bearing Question

Before any other decision criterion, ask:

> **Should the output remain visible in the parent conversation after the work is done?**

| Answer | Choice |
|---|---|
| **Yes** — content stays in conversation, user/Claude reference it later | **Skill** |
| **No** — a summary suffices; intermediate work should be walled off | **Subagent** |

This single question resolves most apparent overlap. If an agent produces a final verdict that the parent acts on (e.g. a security review's findings list), the rest is noise — that's a subagent. If an agent produces an artifact the user iterates on (e.g. a designed schema, a draft document), the body of the work has to stay visible — that's a skill.

When this is decisive, stop. The remaining sections are tie-breakers.

---

## When to Extract a Skill

Pulling instructions out of an agent body and into a separate skill is only ROI-positive if **at least one** of these is true:

1. **Multi-consumer**: Two or more agents (or workflows) genuinely need the same procedure.
2. **Progressive-disclosure benefit**: The content is large enough (a useful threshold is roughly **>200 lines including reference files**) that pre-loading it into every agent invocation would waste context — even with a single consumer.
3. **User-invocable need**: The user should be able to invoke the procedure explicitly via `/name`.
4. **Slash-command identity**: The capability *is* a workflow entry point (all `tcs-workflow/*` skills).

If **none** of these hold — single consumer, small body, no user-invocation use case, not a workflow — the content belongs **inline** in the consuming agent. Extracting it produces a skill file, a frontmatter, a `skills:` list entry, a README row, and ongoing maintenance for zero gain.

### Concrete TCS examples

| Skill | Consumers | Size (LOC) | Why extracted |
|---|---|---|---|
| `project-discovery` | 16 agents | 926 | Universal reuse + size — strongest case |
| `pattern-detection` | 15 agents | 288 | Universal reuse |
| `platform-operations` | 4 agents | 948 | Multi-consumer + size |
| `architecture-selection` | 1 agent (`design-system`) | 533 | Single consumer, but size justifies progressive disclosure |
| `obsidian-plugin` | auto-trigger by domain | 1680 | Domain pattern, public-invocable, large |

And one example we **un-extracted**:

- **`agentic-patterns`** — was 57 lines, single consumer (`build-feature`), no reference files, no slash-command identity. Inlined into the consuming agent and the skill deleted. Small + single-consumer + no slash use case = pure overhead.

### Audit signal

A periodic check that surfaces extraction-without-ROI cases:

```bash
# For each skill, count which agents reference it via skills: frontmatter
for skill in plugins/tcs-team/skills/*/*/; do
  name=$(basename "$skill")
  count=$(grep -lE "skills:.*\\b$name\\b" plugins/*/agents/**/*.md 2>/dev/null | wc -l)
  echo "$count $name"
done | sort -n
```

A skill with `count=1`, no `reference/*.md` files, and a `SKILL.md` under ~150 lines is the candidate to inline.

---

## When to Keep Specialists as Agents

The opposite mistake is consolidating distinct specialists into one agent + skills "to be more skill-driven." Three properties make a specialist worth keeping as its own agent:

1. **Distinct trigger surface.** Auto-triggering depends on description match. Two specialists with overlapping but non-identical trigger surfaces (e.g. *security review of dependencies* vs *compatibility review of public APIs*) need distinct descriptions to route accurately. Merging them produces a description that is either too generic ("review for issues") or too long (three paragraphs of triggers) — both hurt routing.

2. **Distinct output schema.** When findings need different fields (e.g. `affectedConsumers` and `migrationPath` for compatibility findings; `CVE` and `severity` for security findings; `trigger` for robustness findings), a unified schema either bloats with optional fields or loses information.

3. **Parallel dispatch is the value.** If the workflow's purpose is "run these reviews concurrently," each parallel slot needs its own dispatchable agent. Skills run inline and serialize.

When all three hold and each specialist is already lean (~70–150 lines), consolidating saves little and costs trigger accuracy.

### Concrete TCS examples

| Specialists | Why kept distinct |
|---|---|
| `the-architect:review-security` / `review-robustness` / `review-compatibility` | All three properties hold: distinct trigger domains (auth/deps vs async/concurrency vs API/schema/migration), distinct output schemas (`SEC-NNN` / `ROB-NNN` / `COMPAT-NNN` with domain-specific fields), parallel dispatch from `/implement` workflow. Average ~90 LOC each — already lean. |
| `the-developer:build-feature` / `optimize-performance` | Distinct triggers (build vs profiling), distinct mental modes, parallel dispatch when both apply. |

The rule of thumb: **before merging two specialists, look at the descriptions side-by-side**. If there's no single description that auto-triggers reliably for both use cases without overlap with adjacent specialists, the merge will hurt routing more than it helps maintenance.

---

## The Receptionist Pattern

A single front-door routes incoming work to the right specialist. TCS implements this with **two routing layers**:

```
                              ┌──────────────────────────┐
User request ─────────►       │  Main Conversation       │
                              │  (Claude Code itself)    │  ← First receptionist:
                              │                          │     auto-triggers skills,
                              │                          │     dispatches subagents
                              └────────────┬─────────────┘
                                           │
                  ┌────────────────────────┼────────────────────────┐
                  │                        │                        │
                  ▼                        ▼                        ▼
        Single-domain task         Cross-domain task        Side-effect task
        → Skill or specialist      → the-chief              → Slash command
                                   (Second receptionist:
                                   complexity scoring,
                                   activity decomposition,
                                   parallel routing)
```

**First layer — the main conversation agent.** Auto-triggers skills via description match, dispatches subagents via the Agent tool. Handles single-domain requests directly. This is the "lightweight router" that the agent design literature consistently advocates.

**Second layer — `the-chief`.** Invoked when work is ambiguous, spans multiple domains, or benefits from explicit complexity scoring before dispatch. Returns a structured routing plan (activities, parallel flags, dependencies). Lives as an agent because most invocations involve reading project context (CLAUDE.md, specs, constitution) — isolation prevents that from bloating the parent conversation.

The two-layer design has a real tradeoff: you could compress it into one layer by making complexity assessment a skill rather than an agent. The second layer is justified when:

- Project context is large enough that reading it inline would dominate parent context.
- The routing decision benefits from being walled off (a separate "decision artifact" rather than a conversation turn).
- Explicit complexity scoring is itself worth doing as a discrete artifact.

For small projects with thin CLAUDE.md / constitution files, a single-layer router (skill-only) would be lighter. TCS keeps both because the projects we target tend to have substantial spec context.

---

## When to Use a Slash Command

A slash command in TCS is just a user-invocable skill — but the framing matters. Use the slash-command framing when:

1. **The user must explicitly authorize the action.** Side effects (deploy, send-message, commit) should never auto-trigger from a description match.
2. **The capability is a named workflow entry point.** `/xdd`, `/implement`, `/review`, `/brainstorm` — these are workflows the user enters deliberately.
3. **Discoverability matters.** If the user might forget the capability exists, putting it in the `/` menu is a feature.

For pattern references (e.g. `/obsidian-plugin`), being user-invocable AND auto-triggering is reasonable — the user can invoke it explicitly to "audit my plugin," and it can auto-trigger when the conversation is clearly about Obsidian.

For agent-internal skills (e.g. `project-discovery`, `code-quality-review`), set `user-invocable: false`. They appear in agents' `skills:` frontmatter and auto-load when the agent runs; surfacing them in the `/` menu adds noise without giving the user a meaningful affordance.

---

## Worked Examples

Four recent decisions, with the criterion that drove each.

### Inline `agentic-patterns` into `build-feature`

**Inputs:** 57-line skill, 1 consumer (`build-feature`), no `reference/*.md` files, no public/slash use case.

**Criterion:** Extraction requires ≥1 of {multi-consumer, progressive-disclosure, user-invocable, slash-command}. None held.

**Action:** Moved framework guidance (LangChain / Vercel AI SDK / assistant-ui llms.txt URLs) into `build-feature.md` as a "Decision: Agentic AI Features" table. Removed from the agent's `skills:` list. Deleted the skill directory.

**Trade-off:** Pre-loading three llms.txt URLs into every `build-feature` invocation is acceptable (small content). Lost: ability to invoke `/agentic-patterns` directly — never used.

### Keep `the-architect:review-{security,robustness,compatibility}` as three agents

**Inputs:** 71 / 75 / 123 LOC each, distinct trigger surfaces, distinct output schemas (`SEC-NNN` / `ROB-NNN` / `COMPAT-NNN`), all three dispatched in parallel by `/implement` and `/review`.

**Criterion:** Specialist consolidation should preserve distinct triggers, output schemas, and parallel dispatch. All three are violated by a merge.

**Action:** No change.

**Trade-off:** Three agents to maintain instead of one + three skills. Mitigated by each agent being already lean — there's little duplication to deduplicate.

### Keep `tcs-patterns:test-design-reviewer` as a forked skill (not convert to a subagent)

**Inputs:** Its whole job is to produce a review report and hand it back — the Load-Bearing Question answers "No, a summary suffices", which points at a subagent. But it already carries `context: fork` + `agent: Explore`, it is reachable as `/test-design-reviewer`, and three other skills route to it by name.

**Criterion:** `context: fork` resolves the Load-Bearing Question's "No" branch without leaving the skill mechanism. The skill body runs in an isolated context and only its report returns — the subagent runtime contract — while the `/` entry point and the `tcs-patterns:<name>` address that other skills cite both survive. A subagent has neither.

**Action:** No change to the mechanism. Converted to PICS in place (#120).

**Trade-off:** It cannot be dispatched in parallel from a workflow the way an agent can. Nothing dispatches it that way today; `tcs-workflow:xdd-tdd` and the sibling pattern skills all reference it by name for a human or the parent to invoke.

**Generalises to:** a reviewer that must stay addressable by name and by `/` belongs in the plugin that owns its domain as a forked skill. Move it to an agent when parallel dispatch becomes the point — that is the property `context: fork` cannot supply.

### Keep `the-chief` as an agent (not convert to a `/triage` skill)

**Inputs:** 118-LOC orchestrator. Workload mixes deterministic decision tables (skill-friendly) and project-context reading (parent-bloat risk if inlined).

**Criterion:** Conversion is ROI-positive only if context-isolation savings are small AND the inline visibility is genuinely valuable to the user. For typical TCS projects with substantial spec context, isolation matters more.

**Action:** No change. Cascading rename across four documentation files plus the agent-author conventions example would also have been a real cost.

**Trade-off:** Routing decisions remain summary-only rather than visible in the parent conversation. Acceptable because the user mostly cares about the resulting dispatch, not the scoring rubric's intermediate steps.

---

## Anti-Patterns

| Anti-pattern | Why it hurts | Fix |
|---|---|---|
| Skill extracted with single consumer + small body + no slash use case | Adds frontmatter, file, README row, `skills:` entry to maintain — for nothing | Inline into the consuming agent |
| Two specialists merged into one agent + two skills "to be more skill-driven" | Trigger description either bloats or generalizes; output schemas collide | Keep specialists distinct when triggers and outputs are genuinely different |
| Agent created for what is essentially deterministic decision logic over small inputs | Subagent overhead (round-trip, isolated context) for work that could happen inline | Convert to a skill if inline visibility is fine and project context is small |
| Agent-internal skill with `user-invocable: true` | Pollutes the `/` menu without giving the user a meaningful affordance | Set `user-invocable: false`; auto-trigger via description still works |
| Skill body that summarizes the workflow instead of stating triggers | Claude follows the description as a shortcut and skips the body | Description states *when* to use; body states *how* |
| Subagent that returns a body the user wants to iterate on | Iteration requires the body in the parent — subagents only return summaries | Convert to a skill |

---

## See Also

- [principles.md](principles.md) — the design principles this document sits on: activation contract, progressive disclosure, context isolation, tool scoping, model selection, evaluation-first
- [concepts.md](concepts.md) — XDD workflow and the design philosophy behind it
- [`reference/skills.md`](../reference/skills.md) — skill inventory and decision tree for the `tcs-workflow` plugin
- [`reference/agents.md`](../reference/agents.md) — agent inventory across `tcs-team`
- `plugins/tcs-helper/skills/skill-author/reference/decision-tree.md` — the seven-question sequential decision tree (skill / subagent / slash / hook / agent team)
- `plugins/tcs-helper/skills/skill-author/reference/conventions.md` — gold-standard skill structure and frontmatter
- `plugins/tcs-helper/skills/agent-author/reference/conventions.md` — agent file structure and naming
