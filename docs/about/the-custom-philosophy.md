# Why The Custom Startup Exists

The original framework by Rudolf Schmidt ([the-startup](https://github.com/rsmdt/the-startup)) is genuinely good. The core idea — write a specification before writing code, then execute it with parallel specialist agents — reflects how senior engineers actually think, and it works. What the framework lacked was everything around the edges: how you get it running, how you stay oriented while it runs, how you use it away from a terminal, how it fits into the directory structure of a real project, and how it keeps context usage manageable across long sessions.

What started as a fork to close those gaps has grown into an opinionated, standalone framework — a curated collection of 4 plugins, 20+ skills, 15 specialist agents, and supporting infrastructure that does not depend on external plugins for its core functionality.

---

## The install experience

The original installation was: either clone the repo, run `claude plugin install ./plugins/start` or install via curl command, done. Functional, but it assumed familiarity with Claude Code's plugin system, didn't account for existing installation or configuration changes. In general it lacked flexibility and safety measures.

A tool that claims to reduce friction should not require you to take it or leave it. The install wizard asks where to install, which plugins to include, which output style to activate, where your specs should live, and whether you want a statusline — and then writes everything in one pass. Running it a second time is safe.

---

## Statusline as a feedback loop

A statusline might seem cosmetic. It is not. When you can see the context window filling up at a glance, you context-reset before it becomes a problem. When you see the session cost in real time, you make different decisions about how much you parallelize. When you see the model name and output style, you know immediately whether Claude is in the mode you expect.

The three variants cover different setups: Standard for anyone who wants something lightweight with no dependencies (and which was included in the original), Enhanced for power users who want token budget bars and git context (which was "developed" by me), and the Starship bridge for people who have already invested in a custom prompt and do not want two separate status displays (which I found on Reddit and found intriguing).

The `statusline.toml` config and the calibrated plan limits (Pro: ~28,450 tokens per 5h window, measured rather than assumed) came from iterating on actual usage.

---

## Multi-AI workflow

The spec-driven workflow implicitly assumes you are always in a terminal with Claude Code open. Most of the time, that is not true. You might be thinking through a feature on your phone, in a browser, or in a meeting. Perplexity is better for current research. Claude.ai is more conversational for brainstorming and PRD writing.

The multi-AI workflow fills the gap with prompt templates and two shell scripts. The templates are the same intellectual work as the Claude Code skills, adapted for external tools. The export script packages a spec for external review; the import script brings the result back. The loop closes back in Claude Code when it is time to write code.

This is not about replacing Claude Code. It is about using the right tool for each phase and keeping the handoff clean.

---

## Configurable paths

`.start/specs/` is an implementation detail from the original framework, not a natural place to put your specifications. A project that uses this framework should be able to decide where its specs live — whether that is `docs/specs/`, `the-custom-startup/specs/`, or something entirely different.

The `.claude/startup.toml` config file solves this once. Set `specs_dir` once and every skill, script, and command reads it automatically. The fallback chain preserves backward compatibility for projects already using `.start/specs/`.

---

## What I kept

Everything that works. The spec-driven workflow is correct. The output styles are genuinely useful. The slash commands cover the right lifecycle phases.

The activity-based agent architecture is sound — and worth explaining, because it is not obvious why it is designed that way.

### Activity-based agents

Traditional engineering boundaries map to job titles: backend engineer, QA engineer, frontend engineer. The team plugin rejects this. Its agents are organized by what they do, not who they are:

```
Traditional role-based:
├── the-backend-engineer   (too broad)
└── the-qa-engineer        (multiple responsibilities)

Activity-based:
├── the-developer/build-feature    (specific activity)
└── the-tester/test-strategy       (specific activity)
```

There are four reasons this works better for LLMs:

1. **LLMs do not have job titles** — They have capabilities that map to activities, not to org chart positions
2. **Reduced context switching** — Each agent receives only the context relevant to its specific activity
3. **Better parallelization** — Activities decompose naturally into parallel workflows
4. **Stack agnostic** — `the-developer/build-feature` builds features regardless of whether the stack is React, Vue, or plain HTML

The research backs this up. Task specialization consistently outperforms role-based organization: a 2.86%–21.88% accuracy improvement with specialized agents versus single broad agents, and a 60% time savings in QA processes from agent specialization. Leading multi-agent frameworks (CrewAI, Microsoft AutoGen, LangGraph) all organize agents by capability rather than job title for the same reasons.

The naming convention — `the-[human-role]/[activity]` — keeps it navigable. The human role part (`the-architect`, `the-developer`) tells you where to look. The activity part (`review-security`, `build-feature`) tells you what it actually does.

---

## TDD + SDD integration

The original framework had SDD (Solution Design Documents) as the bridge between requirements and code. This fork adds TDD (Test-Driven Development) as a hard gate between design and implementation.

The insight: SDD defines contracts (interfaces, data models, behavior expectations). TDD verifies them (each contract becomes a failing test before any implementation). Neither works well alone — SDD without TDD produces designs that may never be correctly implemented; TDD without SDD produces tests that may be testing the wrong things.

The `xdd-tdd` skill enforces the RED-GREEN-REFACTOR iron law. The `tdd-guardian` agent (dispatched automatically by `/implement`) blocks production code until a failing test exists. The plan tasks produced by `/xdd-plan` are structured as TDD cycles anchored to SDD contracts. This is not advisory — it is a hard gate.

See [concepts.md](concepts.md) for the full TDD + SDD integration design.

---

## Memory Bank

Long Claude Code sessions accumulate context. Eventually the window fills up, context compaction loses detail, and the AI forgets what it learned earlier. The Memory Bank is a layered knowledge system that moves durable learnings out of the context window and into structured files.

Three scopes (global, project, repo) with six categories (general, tools, domain, decisions, context, troubleshooting) store knowledge where Claude Code's own file discovery rules will find it — but only when working in the relevant directory. This is context minimization through file structure: knowledge is available when relevant without consuming budget upfront.

Python hooks passively capture corrections and learnings during sessions. Five maintenance skills (`/memory-add`, `/memory-sync`, `/memory-cleanup`, `/memory-promote`, `/setup`) keep the bank lean. The promotion lifecycle — patterns that recur across sessions are elevated from memory files into reusable skills — means the bank gets leaner over time, not larger.

See [concepts.md](concepts.md) for the full Memory Bank design.

---

## Satori — optional context reduction

Even with the Memory Bank, some sessions generate more context than the window can hold. Satori is an MCP gateway that sits between Claude Code and your MCP servers, capturing session activity into a local database and serving compact summaries instead of replaying full tool outputs. The install script offers Satori setup as an optional step.

Satori and the Memory Bank operate at different time scales: Satori handles ephemeral session context, the Memory Bank holds durable knowledge. Together they form a two-tier system that keeps context usage low while maintaining both session continuity and cross-session learning.

---

## Spec-driven development

The primary workflow enforces spec-first development. This is not bureaucracy — it is how you avoid the most expensive mistakes.

Writing requirements before implementation locks scope before the cost of changing direction rises. Design decisions made on paper are cheaper than design decisions discovered in code. A completed spec lets multiple specialists work in parallel from the same source of truth. And the `/validate` step acts as a quality gate: it checks completeness, consistency, and correctness before any implementation investment is made.

The PRD → SDD → PLAN sequence mirrors how effective engineering teams actually work: understand the problem, design the solution, plan the execution. **Think twice, ship once.**

The principle underneath all of it: **humans decide, AI executes.** The framework keeps critical decisions with you and hands off implementation details to the agents. The specs are your decisions made explicit.

---

What started as infrastructure around a solid core has become a complete development framework. The spec-driven workflow, TDD discipline, Memory Bank, and optional Satori integration work together to make Claude Code sessions predictable, reviewable, and context-efficient.

Any behavioral changes from upstream are noted in the [What's different](../../README.md#whats-different) section of the main README. Full attribution is in [sources.md](sources.md).

Thanks to Rudolf Schmidt ([@rsmdt](https://github.com/rsmdt)) for creating [the-startup](https://github.com/rsmdt/the-startup) — the foundation this framework builds on.
