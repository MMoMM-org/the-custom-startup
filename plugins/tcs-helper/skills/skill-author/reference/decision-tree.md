<!-- SYNC: identical content lives in plugins/tcs-helper/skills/skill-author/reference/decision-tree.md — update both together. Source: rsmdt/the-startup PRINCIPLES.md §5.2 (April 2026) -->

# Mechanism Decision Tree

Before authoring a skill or subagent, confirm you're picking the right mechanism. Skills, subagents, slash commands, and hooks have **distinct runtime contracts** — picking the wrong one produces a thing that works in isolation but fails to integrate.

This tree is grounded in [Anthropic's official docs](https://code.claude.com/docs/en/skills) and the upstream `the-startup` PRINCIPLES.md § 5.2.

---

## The Load-Bearing Question

Ask this **first**. It resolves most apparent overlap.

> **Should the output remain visible in the parent conversation after the work is done?**

| Answer | Mechanism | Why |
|---|---|---|
| **Yes** — content stays in conversation, user/Claude reference it later | **Skill** | Skill body and produced content live in parent context |
| **No** — a summary suffices; intermediate work should be walled off | **Subagent** | Subagent context is isolated; only final message returns |

If this single question gives a decisive answer, stop here.

---

## Sequential Tree — Stop at the First Decisive Answer

### Q1. Should the output remain visible in the parent conversation?

→ See above. If decisive, you're done.

### Q2. Does this work need to run in parallel with other independent work?

| Answer | Mechanism |
|---|---|
| Yes | **Subagent** — skills execute inline and block; subagents dispatch concurrently |
| No | Either viable, continue |

### Q3. Would verbose intermediate output bloat the parent context?

(e.g. scanning a large codebase, running a test suite, reading dozens of files)

| Answer | Mechanism |
|---|---|
| Yes | **Subagent**, with `model: haiku` for read-heavy passes |
| No | Skill is lighter weight |

### Q4. Is this reusable procedural or domain knowledge invoked by name?

| Answer | Mechanism |
|---|---|
| Yes — slash-invocable, discoverable via `/skills`, versioned | **Skill** |
| No — opportunistic delegation triggered by description match | **Subagent** |

### Q5. Do you need an enforced information barrier?

(e.g. an evaluator that must not see the source it's grading)

| Answer | Mechanism |
|---|---|
| Yes | **Subagent** — context isolation is enforced at dispatch |
| No | Skill may suffice |

### Q6. Is this a side-effect operation requiring explicit user authorization?

(deploy, commit, send-message)

| Answer | Mechanism |
|---|---|
| Yes | **Skill** with `disable-model-invocation: true` (note: bug #26251 currently also blocks user invocation) |
| No | Continue with earlier answers |

### Q7. Is this peer-to-peer coordination between multiple in-flight agents?

| Answer | Mechanism |
|---|---|
| Yes | **Agent Team** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), not a skill or plain subagent |
| No | Answer is skill or subagent per Q1–Q6 |

---

## Tie-Breaker

When both Skill and Subagent genuinely fit: **prefer Skill**.

Reasons:
- Cheaper to author
- Easier to test (`skill-creator` benchmarks)
- Visible output, user-invocable
- First-class versioning artifact

Escalate to Subagent only when context economy, parallelism, or information isolation **demands** it.

---

## Worked Examples

| Situation | Choice | Primary reason |
|---|---|---|
| "Review this PR for security issues" | Subagent (`review-security`) | Read-heavy; findings return as summary; runs in parallel with other reviewers |
| "How should we structure a REST API?" | Skill (`designing-apis`) | Domain knowledge; output must stay visible for follow-up design work |
| "Deploy to staging" | Skill, `disable-model-invocation: true` | User-authorized side-effect; not a research task |
| "Find all uses of feature flag X across the repo" | Subagent (`Explore`, Haiku) | Verbose output; summary suffices |
| "Run the test suite and fix any failures" | Subagent with `tools: Bash, Read, Edit`, `isolation: worktree` | Multi-turn side task; parent doesn't need transcript |
| "Explain the auth flow in this repo" | Skill (`reading-codebase`) | Inline walk-through; user wants to see it unfold |
| "Three researchers investigate competing hypotheses about this bug" | Agent Team | Peer coordination required |
| "Onboarding checklist for the auth module" | Skill | Reusable reference; must remain visible inline |
| "Evaluate candidate implementations against scenarios without seeing the source" | Subagent | Information barrier required — only subagents enforce isolation |
| "Design a database schema for multi-tenant billing" | Skill (`designing-schemas`) | Produces an artifact the user reads, critiques, and iterates on |
| "Lint, type-check, and run tests before marking done" | Subagent (or hook chain) | Verbose output; deterministic gate |

---

## Common Confusions

**"The code-reviewer does such-a-specific job — shouldn't it be a skill?"**
No. A reviewer produces a summary verdict; intermediate reads should not clutter the parent, and it benefits from parallel dispatch alongside other reviewers. **Subagent.**

**"Our deploy workflow has many steps — isn't that a subagent?"**
No. The user must explicitly trigger it, and the outcome (success, failure, which environment) must remain visible in the parent. **Skill** with model-invocation disabled.

**"API design conventions are just knowledge — why not a subagent?"**
A subagent would isolate the knowledge to its fork and return a summary, losing the point. The user wants the conventions in their conversation to reason against. **Skill.**

**"Exploratory codebase search sounds like a skill."**
Exploration produces tens of reads and grep calls most of which are noise to the parent. **Subagent** (the built-in `Explore` agent on Haiku is the reference pattern).

**"The onboarding playbook is invoked once, then never again."**
Frequency is the wrong axis. If the output should stay in context and be user-invocable, it's a skill regardless of how often you invoke it.

---

## How the Author Skills Use This Tree

When invoking `tcs-helper:skill-author` or `tcs-helper:agent-author`, the **first workflow step** is a Mechanism Check that walks the user through Q1 above. If the wrong author was invoked (e.g. user called `skill-author` for something that should be a subagent), the skill recommends switching to the other author and offers to hand off.

This is intentional friction. Picking the wrong mechanism is the highest-cost, hardest-to-fix authoring mistake — far more expensive than a few seconds of mechanism reflection.

---

## Other Mechanisms (Reference)

| Mechanism | When | Context | Communication |
|---|---|---|---|
| **Skill** | Reusable workflow, domain knowledge, checklist, slash command | Parent's own (unless `context: fork`) | Inline — content joins conversation |
| **Subagent** | Isolated exploration, parallel work, summary-returning research | Fresh fork; parent unseen | One-way: parent → task prompt → summary |
| **Slash Command** | Explicit terminal entry point | Whatever it invokes | User-typed `/cmd` |
| **Agent Team** | Sustained peer coordination, competing hypotheses | Persistent per-teammate contexts | Bidirectional mailbox; peer-to-peer |
| **Hook** | Deterministic gate on a tool call (block writes, validate queries) | Shell process | Exit code / stdout / stderr |

In 2026, slash commands and skills have been **unified** — `.claude/commands/` and `.claude/skills/` both work. Skill frontmatter (`argument-hint`, `disable-model-invocation`, `user-invocable`) subsumes what used to require separate command definitions.
