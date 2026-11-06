# Persuasion Principles for Skill Design

**Load this reference when:** designing discipline-enforcing skills, understanding why certain language patterns work better, or making skills more effective under pressure.

## Overview

LLMs respond to the same persuasion principles as humans. Understanding this psychology helps you design more effective skills - not to manipulate, but to ensure critical practices are followed even under pressure.

**Research foundation:** Meincke et al. (2025) tested 7 persuasion principles with N=28,000 AI conversations. Persuasion techniques more than doubled compliance rates (33% → 72%, p < .001). That compliance is reported to be with requests the model would otherwise refuse (scope not re-checked), not with following a skill's rules, so treat the principles below as untested for skills unless a section says otherwise.

---

## Principles That Work for Skills

### 1. Authority — unverified for current models

**What it is:** Deference to expertise and non-negotiable rules.

**Status:** unverified for current models. Current vendor guides advise against the emphasis it relies on ([PA-03](../../prompt-author/reference/catalog/core.md#pa-03-emphasis-and-authority-language)):
- Anthropic, Prompting best practices: "soften any aggressive language"; where you might have said "CRITICAL: You MUST use this tool when...", use "Use this tool when...". "If in doubt, use [tool]" causes overtriggering.
- OpenAI, GPT-4.1 prompting guide: all-caps and similar incentives are "generally not necessary".
- OpenAI, GPT-5 prompting guide: Cursor's "Be THOROUGH" was "counterproductive with GPT-5"; the fix was softening the language.
- "Attention is Case-Sensitive" (13 models): uppercase concentrates attention, but "increased concentration does not inherently improve task accuracy".

**How to use instead:**
- State the rule in sentence case with the failure it prevents (PA-01).
- Close loopholes with a Red Flags list and an excuse → reality table, not with capitals or "no exceptions".
- A hard terminal constraint may be restated once, plainly, at the end of the skill.

**Example:**
```markdown
✅ Wrote code before its test? Delete it and start over: code written first shapes the test to fit it.
❌ Consider writing tests first when feasible.
```

### 2. Commitment

**What it is:** Consistency with prior statements and explicit choices.

**How to use:**
- Force explicit choices: "Choose A, B, or C"
- Require announcements: "First, state what you will do"
- Use tracking: Checklists that must be completed

**Example:**
```markdown
✅ Before proceeding, confirm: "I have checked for duplicates: [Yes/No]"
❌ You might want to check for duplicates.
```

### 3. Scarcity / Urgency

**What it is:** Time-bound requirements that prevent procrastination.

**How to use:**
- "Before proceeding" requirements
- "Immediately after X" sequences
- Sequential dependencies

**Example:**
```markdown
✅ After completing a task, run verification immediately, before proceeding.
❌ You can verify when convenient.
```

### 4. Social Proof

**What it is:** Establishing what's normal and expected.

**How to use:**
- Universal patterns: "Every time", "Always"
- Failure modes: "X without Y = failure"
- "All skills follow this pattern"

**Example:**
```markdown
✅ Skills without testing = skills that fail in production. Every time.
❌ Some people find testing helpful.
```

---

## Principles to Avoid

### Liking
Don't use "be friendly" to get compliance. Creates sycophancy and conflicts with honest feedback.

### Reciprocity
Rarely needed and can feel manipulative.

---

## Principle Combinations by Skill Type

| Skill Type | Use | Avoid |
|------------|-----|-------|
| **Discipline-enforcing** | Commitment + Social Proof, plain rules with reasons | Liking, capitalised or absolute directives |
| **Technique/guidance** | Plain rules with reasons | Heavy authority |
| **Reference** | Clarity only | All persuasion |

---

## Why This Works

**Bright-line rules reduce rationalization:**
- A rule stated once, plainly, with its reason, leaves no "is this an exception?" question
- Explicit anti-rationalization counters close specific loopholes

**LLMs are parahuman:**
- Trained on human text containing these patterns
- Commitment sequences (statement → action) frequently modeled

---

## Ethical Use

**Legitimate:**
- Ensuring critical practices are followed
- Creating effective documentation
- Preventing predictable failures

**Test:** Would this technique serve the user's genuine interests if they fully understood it?

---

## Quick Reference

When designing a discipline skill:

1. **State rules plainly** - sentence case, imperative, with the failure each prevents (Authority is unverified, see above)
2. **Use Commitment** - Force explicit choices, require announcements
3. **Use Social Proof** - "Every time", "All skills do X"
4. **Use Scarcity** - "Before proceeding", "Immediately"
5. **Avoid Liking** - Don't use friendliness for compliance

## Research Citations

- Cialdini, R. B. (2021). *Influence: The Psychology of Persuasion.* Harper Business.
- Meincke, L., et al. (2025). Call Me A Jerk: Persuading AI to Comply. University of Pennsylvania.
