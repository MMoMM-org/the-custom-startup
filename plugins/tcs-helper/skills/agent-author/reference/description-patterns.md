# Description Patterns

The `description` field is **the activation contract** between Claude's router and your agent. Get it wrong and the agent never triggers; get it right and auto-delegation works reliably.

**Source:** rsmdt/the-startup PRINCIPLES.md § 2.1, grounded in [Anthropic Engineering, Equipping agents for the real world with Agent Skills (Dec 2025)](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) and [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

---

## How Auto-Delegation Actually Works

Claude selects skills and subagents by performing **text reasoning over the description field** — not embedding retrieval, not keyword matching, not a classifier. This means:

- Words you write in the description are the only routing signal
- Phrasing matters more than synonym coverage
- "Slightly pushy" imperatives outperform neutral descriptions

Anthropic explicitly notes that Claude tends to **under-trigger** — it errs toward not invoking when it should. Compensate with imperative phrasing.

---

## Hard Rules

### 1. Front-load the trigger in the first ~50 characters

The `/skills` UI truncates at 250 chars. The field hard-caps at 1,024. Combined `description + when_to_use` caps at 1,536. Anything past those limits is invisible to part of the routing path.

```yaml
# ✅ GOOD — trigger scenario in first 50 chars
description: |
  Reviews PRs for security and compliance issues. Use PROACTIVELY when the task mentions auth, permissions, or injection.

# ❌ BAD — trigger buried after generic preamble
description: |
  This is a comprehensive code review specialist that brings deep expertise in many areas of software engineering. It can help with security, performance, and other concerns.
```

### 2. Third-person, scenario-anchored

```yaml
# ✅ GOOD — third-person, scenario
description: Reviews changes for security issues. Use when the user mentions auth, permissions, or injection-related concerns.

# ❌ BAD — second-person, abstract
description: You are a security expert that helps with various security tasks.
```

### 3. Use imperative phrasing — `Use PROACTIVELY when…` and `MUST BE USED when…`

These phrases are explicitly recommended by Anthropic to counteract Claude's under-triggering bias.

### 4. Include 2–3 `<example>` blocks (PRINCIPLES § 4.3)

For subagents specifically, `<example>` blocks dramatically improve parent-side delegation accuracy. Format:

```yaml
description: |
  Use PROACTIVELY to review code changes for correctness and missing tests.
  MUST BE USED after non-trivial code changes before commit.
  Examples:

  <example>
  Context: User just finished implementing a feature.
  user: "Done with the auth refactor"
  assistant: "I'll use the code-reviewer agent to check for correctness and test coverage."
  <commentary>Post-implementation review is exactly the trigger.</commentary>
  </example>

  <example>
  Context: User explicitly asks for review.
  user: "Can you review my PR?"
  assistant: "I'll use the code-reviewer agent for that."
  <commentary>Explicit review request.</commentary>
  </example>
```

---

## Pattern: Action + Trigger + Examples

Every description should layer three things:

1. **Action segment** with `Use PROACTIVELY` or `MUST BE USED`
2. **Trigger segment** with concrete user-language phrases
3. **Example blocks** for high-value agents (PRINCIPLES § 4.3 recommends 2–3)

---

## Good Examples by Archetype

### Reviewer

```yaml
description: |
  Use PROACTIVELY to review code changes for correctness, regressions, and missing tests before merging.
  MUST BE USED after any non-trivial code change before commit.
  Triggers: code review, PR review, "looks good?", "ready to merge", post-implementation check.
```

### Debugger

```yaml
description: |
  MUST BE USED to investigate failing tests and identify root causes when the task mentions failing tests, broken CI, or "tests are red".
  Triggers: failing tests, broken CI, intermittent failures, flaky test, debugging request.
```

### Explorer

```yaml
description: |
  Use proactively to scan the codebase and locate relevant files when the task involves "where is X implemented", "how does Y work", or "find all callers of Z".
```

### Performance Optimizer

```yaml
description: |
  Use PROACTIVELY whenever the user requests performance analysis, profiling, or optimization of existing code.
  Triggers: slow queries, memory leaks, latency issues, "make this faster".
```

### Security Reviewer

```yaml
description: |
  MUST BE USED when the user asks for security, permission, or injection-related review of code or configuration.
  Triggers: "is this safe", "security review", "auth check", "SQL injection", "XSS", "permissions audit".
```

### Test Runner

```yaml
description: |
  Use proactively to run tests and surface failures when the task mentions broken tests, failing CI, or "tests are red".
```

---

## Reject-on-Sight Bad Examples

### Generic Role

```yaml
description: An expert code reviewer for all kinds of code.
```
Problems: no action verb, no trigger phrases, overlaps with main agent ("for all kinds"), passive ("an expert ... for ...").

### Helpful-Assistant

```yaml
description: A helpful debugging assistant.
```
Problems: "helpful" / "assistant" carry zero routing signal. No domain specifics.

### Buzzword Soup

```yaml
description: A powerful AI assistant that can do many things.
```
Problems: maximally overlapping with main agent, no trigger phrases.

### Workflow Summary (PRINCIPLES § 3.4 — known anti-pattern)

```yaml
description: Reads files, analyzes diff, runs tests, writes report.
```
Problems: describes the workflow, not when to use the agent. **Claude may follow the description as a shortcut and skip reading the system prompt body** — confirmed failure mode in real use.

---

## Trigger Phrase Library

Use phrases users actually type. Verbatim user-language outperforms paraphrases.

### Code Review
"review this", "ready to merge", "PR review", "before commit", "look over this change", "looks good?"

### Debugging
"tests are failing", "broken", "doesn't work", "intermittent", "flaky", "race condition", "memory leak", "tests are red"

### Exploration
"where is X", "how does Y work", "find all callers", "what uses this", "trace through"

### Performance
"slow", "latency", "memory", "profile", "optimize", "make this faster"

### Security
"is this safe", "vulnerability", "auth", "injection", "XSS", "CSRF", "permissions", "leak", "secure?"

### Architecture
"should we", "trade-offs", "design", "approach", "pattern", "boundary", "scale this"

### Testing
"add tests", "test coverage", "missing tests", "verify", "validation"

---

## Verification Checklist

Before shipping a description:

- [ ] Trigger scenario appears in the first ~50 characters
- [ ] Contains `Use PROACTIVELY` OR `MUST BE USED`
- [ ] Has at least 2 concrete trigger phrases (verbatim user-language)
- [ ] Third-person, scenario-anchored
- [ ] Does NOT summarize the workflow (Claude will skip the body)
- [ ] Distinguishable from main-agent scope (not "for all X")
- [ ] For high-value agents: includes 2–3 `<example>` blocks
- [ ] Total length ≤ 1,024 chars (hard cap); UI-safe portion ≤ 250 chars
