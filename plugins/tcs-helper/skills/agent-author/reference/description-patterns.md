# Description Patterns

The `description` field drives Claude's auto-delegation. This is the highest-leverage field in the entire agent definition. A good description triggers reliably; a passive one means the agent rarely gets called even when ideal.

---

## Anthropic's Official Recommendation

Anthropic explicitly recommends including these phrases in the description to encourage proactive delegation:

- `Use PROACTIVELY ...`
- `MUST BE USED ...`

These imperative phrases signal to Claude's router that the agent should be auto-invoked, not just listed.

---

## Pattern: Action + Trigger Phrases

Every description should contain two elements:

1. **Action segment** with `Use PROACTIVELY` or `MUST BE USED`
2. **Trigger segment** with 2–5 concrete phrases the user might say or contexts that should match

### Template

```yaml
description: |
  Use PROACTIVELY to <action> when the task involves <context>.
  MUST BE USED when <specific condition or trigger phrase>.
```

---

## Good Examples (Strong Triggering)

### Reviewer

```yaml
description: |
  Use PROACTIVELY to review code changes for correctness, regressions, and missing tests before merging.
  MUST BE USED after any non-trivial code change before commit.
```

**Why it works:** action verb (`review`), specific scope (`correctness, regressions, missing tests`), explicit trigger context (`after any non-trivial code change before commit`).

### Debugger

```yaml
description: |
  Use PROACTIVELY to investigate failing tests and identify likely root causes before making code edits.
  MUST BE USED when the task mentions failing tests, broken CI, or "tests are red".
```

**Why it works:** clear domain (`failing tests`), explicit user-language triggers (`tests are red`, `broken CI`).

### Explorer

```yaml
description: |
  Use proactively to scan the codebase and locate relevant files and patterns when the task involves "where is X implemented", "how does Y work", or "find all callers of Z".
```

**Why it works:** quotes user language verbatim — Claude's router matches against literal phrases users say.

### Performance Optimizer

```yaml
description: |
  Use PROACTIVELY whenever the user requests performance analysis, profiling, or optimization of existing code.
  Triggers include: slow queries, memory leaks, latency issues, "make this faster".
```

**Why it works:** explicit trigger list with verbatim user phrases.

### Security Reviewer

```yaml
description: |
  MUST BE USED when the user asks for security, permission, or injection-related review of code or configuration.
  Triggers include: "is this safe", "security review", "auth check", "SQL injection", "XSS", "permissions audit".
```

**Why it works:** strong imperative (`MUST BE USED`), domain-specific trigger keywords.

### Test Runner

```yaml
description: |
  Use proactively to run tests and surface failures when the task mentions broken tests, failing CI, or "tests are red".
```

**Why it works:** action-oriented, single-purpose, clear user-language triggers.

---

## Bad Examples (Weak / No Triggering)

### Generic Role Description

```yaml
description: An expert code reviewer for all kinds of code.
```

**Problems:**
- No action verb (no `Use PROACTIVELY` / `MUST BE USED`)
- No trigger phrases
- Overlaps with main agent ("for all kinds of code")
- Passive ("an expert ... for ...")

### Helpful-Assistant Pattern

```yaml
description: A helpful debugging assistant.
```

**Problems:**
- "helpful" / "assistant" carry zero routing signal
- No domain specifics
- No trigger conditions
- Could match almost anything → matches almost nothing reliably

### Buzzword Soup

```yaml
description: A powerful AI assistant that can do many things.
```

**Problems:**
- Anti-pattern: overlap with main agent maximized
- No trigger phrases
- Buzzwords ("powerful", "many things") don't match user language

### Workflow Summary

```yaml
description: |
  Reads files, analyzes diff, runs tests, writes report.
```

**Problems:**
- Describes the workflow, not when to use the agent
- Claude may follow the description as a shortcut and skip the system prompt body
- No trigger phrases

---

## Trigger Phrase Library

Use phrases that match what the user actually types. Ideas by domain:

### Code Review
- "review this", "ready to merge", "PR review", "before commit", "look over this change"

### Debugging
- "tests are failing", "broken", "doesn't work", "intermittent", "flaky", "race condition", "memory leak"

### Exploration
- "where is X", "how does Y work", "find all callers", "what uses this", "trace through"

### Performance
- "slow", "latency", "memory", "profile", "optimize", "make this faster"

### Security
- "secure?", "vulnerability", "auth", "injection", "XSS", "CSRF", "permissions", "leak"

### Architecture
- "should we", "trade-offs", "design", "approach", "pattern", "boundary"

---

## Verification Checklist

Before shipping a description, confirm:

- [ ] Contains `Use PROACTIVELY` OR `MUST BE USED`
- [ ] Has at least 2 concrete trigger phrases
- [ ] Uses words the user actually types (not buzzwords)
- [ ] Does NOT summarize the workflow
- [ ] Distinguishable from main-agent scope (not "for all X")
- [ ] Action-oriented, not role-descriptive
