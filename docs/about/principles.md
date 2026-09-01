# Design Principles

Design principles for TCS skills, subagents, and plugins.

This document answers **why** we build agentic capability the way we do. It deliberately does not answer two adjacent questions, because we already have better homes for them:

| Question | Where it lives |
|---|---|
| *Which mechanism* should this capability be — skill, subagent, or slash command? | [skill-and-agent-design.md](skill-and-agent-design.md) |
| *How* is a skill or agent file structured — frontmatter, conventions, anti-patterns? | `plugins/tcs-helper/skills/{skill,agent}-author/reference/conventions.md` |

Everything here is grounded in the sources listed under [§ Sources](#sources), predominantly Anthropic documentation. Where a claim comes from general software engineering rather than a Claude Code-specific source, that is stated.

> **Provenance.** This document replaced a pre-2026 version inherited from [rsmdt/the-startup](https://github.com/rsmdt/the-startup), which framed agent design through CrewAI / AutoGen / LangGraph research, framework-detection templates, and multiplier metrics ("10× planning", "3× fewer bugs") that do not survive citation-checking. Those claims were dropped rather than relabeled. The rewrite follows upstream's own 2026 re-grounding, adapted to TCS and corrected where upstream had itself gone stale. See [sources.md](sources.md) for the synced revision.

---

## 1. Positioning

TCS ships four plugins to the Claude Code marketplace:

- **`tcs-workflow`** — spec-driven development: XDD, analysis, review, implementation
- **`tcs-team`** — activity-scoped subagents for research, design, implementation, review
- **`tcs-patterns`** — domain pattern skills
- **`tcs-helper`** / **`tcs-git-helpers`** / **`tcs-issues`** — authoring, memory, and repo tooling

Every design decision maps to one of the mechanisms Claude Code exposes: **skills**, **subagents**, **agent teams**, and **hooks**. This document is organized around their runtime contracts, not around analogies to human team structures.

---

## 2. Core Design Principles

Seven principles that apply to skills and subagents alike. They are the load-bearing rules; the rest of TCS's conventions are downstream of them.

### 2.1 Description is the activation contract

Skills and subagents are selected by Claude reasoning over their `description` frontmatter — not embedding retrieval, not keyword matching, not a classifier.

Consequences:

- **Front-load the trigger scenario.** The first ~50 characters carry most of the routing weight. The `/skills` UI truncates around 250 characters.
- **Write third-person and scenario-anchored.** "Extracts text and tables from PDF files. Use when the user mentions PDFs, forms, or document extraction" — not "Helps with documents."
- **Expect under-triggering by default.** Anthropic notes that Claude tends not to invoke skills when it probably should, and recommends slightly pushy phrasing — the `Use PROACTIVELY when…` and `MUST BE USED when…` patterns visible across `tcs-team`'s agent descriptions.

Description quality is the single highest-leverage field in an agent file. A perfect body behind a vague description never runs.

### 2.2 Progressive disclosure is the enforced context-economy pattern

Skills load in three tiers, not as one monolithic prompt:

| Tier | Content | When loaded | Cost |
|---|---|---|---|
| L1 Metadata | `name` + `description` | Always, at session start | ~100 tokens per skill |
| L2 Body | Full `SKILL.md` | When the skill triggers | Budget ≤5,000 tokens |
| L3 Resources | `reference/`, `scripts/`, `templates/` | Read on demand via the filesystem | Zero until referenced |

The boundary is enforced by the runtime — L3 files are read with ordinary Read/Bash calls, so anything bundled costs nothing until explicitly referenced.

Implications:

- Keep `SKILL.md` bodies **≤500 lines**; split longer content into `reference/`.
- Keep references **one level deep**. Nested chains (SKILL.md → advanced.md → details.md) make Claude fall back on `head -N` preview reads, yielding incomplete information.
- Reference files over ~100 lines should lead with a table of contents, so a preview read still surfaces scope.

### 2.3 Subagent context isolation is the feature, not a side effect

A non-fork subagent starts with a **fresh, isolated context window**. Verified against the current subagents documentation (2026-08-31), its initial context contains exactly:

1. Its own system prompt, plus environment details Claude Code appends — *not* the full Claude Code system prompt
2. The delegation message the parent writes
3. The **complete `CLAUDE.md` hierarchy** the main conversation loads (the built-in `Explore` and `Plan` agents skip this)
4. A **git status snapshot** taken at the start of the parent session
5. The full body of any skill named in its `skills:` frontmatter
6. A sibling roster, when the agent has `SendMessage` and other named agents exist

What does **not** reach it: the parent's conversation history, previously invoked skills, the output style, and — importantly for us — **the main conversation's auto memory**.

Implications for TCS:

- **Write the delegation prompt like a brief for a colleague who just walked in.** Targets, decisions, and constraints must be inline; the prompt string is the only parent→child channel.
- **Never write a subagent that assumes it can "see what we discussed."** It cannot.
- **Our Memory Bank reaches agents in two layers, deliberately.** `CLAUDE.md` `@`-imports `docs/ai/memory/active.md` — a budgeted file of rules whose violation is silent and whose trigger is broad — so those reach every subagent by the hierarchy. It also imports `docs/ai/memory/memory.md`, an index that *links* its category files, so the rest is available but costs nothing until an agent chooses to read it. The split exists because an import is paid for on every dispatch, not once per session.
- Use isolation deliberately: dispatch a subagent when the exploration output should stay out of the parent; invoke a skill inline when the result must remain visible. This is the load-bearing question in [skill-and-agent-design.md](skill-and-agent-design.md).

### 2.4 Activity specialization beats role mega-agents

Many small activity-scoped agents (`review-security`, `design-system`, `optimize-performance`) outperform single role-agents that do everything. This is why `tcs-team` organizes by activity under a role namespace rather than one agent per job title.

Rationale:

- Focused system prompts raise accuracy; bloated prompts lower it.
- Activity agents are parallel-dispatchable when independent — wall-clock time drops roughly with parallelism on independent work.
- Smaller tool allowlists are easier to audit and produce fewer permission prompts.
- Failure in one activity does not halt the others.

Single Responsibility is inherited from general software engineering. Its specific application to Claude Code subagents is supported by the structure of Anthropic's shipped examples and by the isolation mechanism in § 2.3.

The counter-pressure — when *not* to split — is covered in [skill-and-agent-design.md § When to Keep Specialists as Agents](skill-and-agent-design.md).

### 2.5 Least-privilege tool scoping is enforced at dispatch

For subagents, `tools` in frontmatter is a **whitelist applied before the first turn** — tools outside it are stripped from the catalog at dispatch. For skills, `allowed-tools` is a pre-approval list, not a restriction: other tools stay callable under the normal permission flow. These are different mechanisms with similar-looking syntax.

Rules:

- Default to **`Read`, `Grep`, `Glob`** for research and analysis agents. `tcs-workflow`'s `spec-compliance-reviewer` is scoped exactly this way.
- Add `Edit` and `Write` only for implementer agents.
- Add `Bash` sparingly; when needed, pair it with a `PreToolUse` hook that validates commands.
- Never `tools: *`. Never `tools: inherit` without justification — a subagent loses the parent's approval history, so inherited dangerous tools re-prompt on every call.

**Watch for features that widen the grant implicitly.** Enabling the `memory:` field auto-enables Read, Write, and Edit so the agent can manage its memory files — which silently un-scopes a deliberately read-only reviewer. Check the side effects of any frontmatter field before adding it to a scoped agent.

### 2.6 Model selection is a tactical cost and latency lever

Subagent `model:` accepts `haiku` / `sonnet` / `opus`, a specific model ID, or `inherit`.

Current models, **verified 2026-08-31** — re-verify rather than trusting this table, via the `claude-api` skill or the [models overview][models]:

| Alias | Model | Context | Input $/MTok | Output $/MTok |
|---|---|---|---|---|
| `haiku` | Claude Haiku 4.5 | 200K | $1.00 | $5.00 |
| `sonnet` | Claude Sonnet 5 | 1M | $2.00 | $10.00 |
| `opus` | Claude Opus 5 | 1M | $5.00 | $25.00 |

Guidance:

- **Haiku** for high-volume read-heavy work — codebase search, file discovery, pattern matching. Anthropic's built-in `Explore` agent uses Haiku for exactly this.
- **Sonnet** for general coding and implementation. This is `tcs-team`'s prevailing default.
- **Opus** for complex reasoning — architectural review, security analysis, hard refactors.
- **Omit `model`** to inherit the parent when there is no tactical reason to override.

> A pricing table is a stale claim waiting to happen — the version this document replaced quoted Opus at $15/$75 per MTok, three times the current rate. Treat the numbers as a snapshot with a date on it, and the *ordering* as the durable part.

### 2.7 Evaluation-first authoring

The authoring flow that produces skills which measurably change behavior:

1. Run Claude on representative tasks **without** the skill or agent; record the specific failures.
2. Write three or more eval scenarios capturing those failures as input / expected-behavior pairs.
3. Write the minimal body needed to pass them.
4. Benchmark against the unprompted baseline to confirm improvement.
5. Re-run periodically. If the base model has absorbed the behavior, **retire the skill** — Anthropic calls this outgrowth detection.

The discipline matters most for the changes that feel obviously right. A prose rule that reads as strong can change nothing, and a section deleted for brevity can quietly degrade behavior — both are only visible with an eval.

**TCS does not meet this bar yet.** No plugin ships eval coverage. Until that changes, treat every claim that an authoring change "improved" a skill as unverified.

---

## 3. Quality and Evaluation

**Skills.** Anthropic's `skill-creator` supports evals (input prompts plus what-good-looks-like, run pass/fail), benchmarks (pass rate, elapsed time, token usage), blind A/B comparison, and outgrowth detection. `claude plugin eval` is the first-party runner for plugin-shipped suites.

**Subagents.** No official eval framework. Practical techniques:

- **Trigger testing** — invoke with natural language matching the description; verify delegation actually happens.
- **Transcript inspection** — read `~/.claude/projects/{project}/{session}/subagents/agent-{id}.jsonl`.
- **Tool enforcement** — attempt a non-allowlisted tool; verify a clean failure rather than a permission prompt.
- **Cost tracking** — confirm custom-model agents actually run on the declared model.

---

## 4. Known Gaps and Open Questions

Verified 2026-08-31 unless noted.

- **`disable-model-invocation` on plugin skills** — plugin skills do not support the field the way user skills do ([anthropics/claude-code#22345][gh-issues], open, last updated 2026-08-30).
- **Cross-surface skill portability** — skills uploaded to claude.ai, the API, and Claude Code do not sync.
- **Agent Teams maturity** — experimental; real-world patterns still emerging.
- **Subagent eval tooling** — no official framework for agents specifically; each team reinvents it.
- **Size-limit empiricism** — Anthropic publishes ≤500 lines for `SKILL.md`; community reports run considerably higher with good progressive disclosure. No public benchmarks settle it.
- **Subagent memory routing** — the `memory:` field adds a per-agent store that the main session and sibling agents cannot see. How that composes with the TCS Memory Bank is undecided.

> Upstream's version of this list also carried `#26251` (`disable-model-invocation: true` blocking user invocation). That issue is **closed** as of 2026-02-27 and has been dropped.

---

## 5. Validation Checklist

Apply to every skill, subagent, and plugin change.

**Skills**

- [ ] `SKILL.md` ≤ 500 lines; references one level deep
- [ ] `description` front-loads the trigger in the first ~50 characters; third-person; safe under ~250
- [ ] Eval scenarios exist, or their absence is a conscious decision
- [ ] `allowed-tools` lists only what is needed, or is omitted
- [ ] No time-sensitive phrasing, no absolute paths
- [ ] Any claim with a date or a price carries the date it was verified

**Subagents**

- [ ] Activity-scoped, not role-scoped
- [ ] `description` contains trigger scenarios and 2–3 examples
- [ ] `tools` is an explicit least-privilege list, never `*`
- [ ] No frontmatter field silently widens the tool grant (see § 2.5)
- [ ] `model` chosen tactically — Haiku for read-only research, Sonnet default, Opus for hard reasoning
- [ ] Body ≤ 25 KB; bulk reference deferred to `skills:` or reference files
- [ ] Does not assume visibility of parent context
- [ ] Golden-path trigger test performed; transcript reviewed

**Composition**

- [ ] Each behavior sits in the right mechanism — see [skill-and-agent-design.md](skill-and-agent-design.md)
- [ ] Independent work is parallelized; only dependent phases are sequential
- [ ] Information barriers intact where relied upon (evaluator ≠ code-writer)

---

## Sources

Preferential weight to Anthropic official documentation.

- [Extend Claude with skills][skills-doc] — skill structure, discovery, frontmatter, invocation control
- [Agent Skills overview][skills-overview] — architecture, progressive disclosure, limitations
- [Skill authoring best practices][skill-best] — naming, descriptions, content guidelines, evaluation-first workflow
- [Equipping agents for the real world with Agent Skills][eng-skills] — rationale for progressive disclosure
- [Improving skill-creator][skill-creator] — evals, benchmarking, A/B, outgrowth detection
- [Create custom subagents][subagents] — frontmatter schema, tool gating, context loading, persistent memory
- [Subagents in the SDK][sdk-subagents] — programmatic definition, tool restriction enforcement
- [Orchestrate teams of Claude Code sessions][agent-teams] — Agent Teams
- [Model configuration][model-config] — per-session and per-subagent model selection
- [Models overview][models] — current pricing and capability
- [anthropics/claude-code issues][gh-issues] — open defects affecting skill and plugin behavior

[skills-doc]: https://code.claude.com/docs/en/skills
[skills-overview]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
[skill-best]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
[eng-skills]: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
[skill-creator]: https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills
[subagents]: https://code.claude.com/docs/en/sub-agents
[sdk-subagents]: https://code.claude.com/docs/en/agent-sdk/subagents
[agent-teams]: https://code.claude.com/docs/en/agent-teams
[model-config]: https://code.claude.com/docs/en/model-config
[models]: https://platform.claude.com/docs/en/about-claude/models/overview
[gh-issues]: https://github.com/anthropics/claude-code/issues

---

## See Also

- [skill-and-agent-design.md](skill-and-agent-design.md) — which mechanism a capability belongs in, with worked TCS decisions
- [concepts.md](concepts.md) — the XDD workflow and the philosophy behind it
- [sources.md](sources.md) — provenance and upstream sync state
- `plugins/tcs-helper/skills/skill-author/reference/conventions.md` — skill structure and frontmatter
- `plugins/tcs-helper/skills/agent-author/reference/conventions.md` — agent structure and frontmatter

---

*Grounded in the primary sources above. When they are updated or contradicted by newer Anthropic guidance, update this document rather than preserving stale claims — and record the verification date.*
