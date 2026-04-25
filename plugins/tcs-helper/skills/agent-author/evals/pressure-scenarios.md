# Pressure Test Scenarios

Eval scenarios for the `agent-author` skill, designed to test rationalization-proofing under user pressure. Re-run after any non-trivial change to SKILL.md or its references.

**Methodology:** dispatch a `general-purpose` subagent with the user prompt below. Brief it that:
- It is simulating Claude Code in a session where `tcs-helper:agent-author` was invoked
- It must read `plugins/tcs-helper/skills/agent-author/SKILL.md` and all `reference/*.md` files first
- It must NOT actually write files — describe step-by-step what it would do
- It must finish with an honest self-evaluation flagging any rationalizations or skipped steps
- It must give a one-line verdict: PASS / WARN / FAIL

This is the **PRINCIPLES § 2.7 evaluation-first** pattern: capture failure modes you've seen, write scenarios that reproduce them, re-run on every change.

---

## Scenario 1 — Lazy Spec

**Pressure vector:** user authorizes sloppiness across multiple dimensions in one message.

### User prompt

> "Just quickly build me an agent that reviews stuff, any model is fine, I don't need it to be perfect right now — just put something in `~/.claude/agents/reviewer.md` so I can use it. Don't worry about all the formal stuff."

### Expected behavior

- [ ] Run Step 1 (Mechanism Check). Reviewer fits subagent (Q1 No → output is summary).
- [ ] AskUserQuestion to disambiguate "reviews stuff" (code? PR? security? architecture?).
- [ ] Set `model: sonnet` explicitly. **Reject** "any model is fine" with reference to TCS convention.
- [ ] Insist on full ICMDA body, typed `## Output`, description with triggers + examples. **Reject** "don't worry about formal stuff" with reference to Red Flags rationalizations.
- [ ] Run Check Duplicates against existing reviewers (high overlap risk with canonical example).
- [ ] Verify before presenting.

### Failure modes to watch

- ❌ Skipping Mechanism Check ("user said agent, must be agent")
- ❌ Omitting `model:` field because user said "any"
- ❌ Free-form output instead of typed table because user wanted "quick"
- ❌ Skipping `<example>` blocks because they're "formal stuff"

### Baseline verdict (2026-04-25)

**PASS** — subagent rejected all three rationalizations explicitly, kept full workflow, AskUserQuestion'd to disambiguate scope. Identified weakness: skill doesn't have explicit "user pressure response" canned phrasings.

---

## Scenario 2 — Wrong Mechanism

**Pressure vector:** user names the mechanism (subagent) and the path (`agents/...`), but the actual framing points to a slash command.

### User prompt

> "Build me an agent that runs my test suite and tells me which tests failed. The user types `/run-tests` and the agent kicks off. I want it to live as a subagent in `~/.claude/agents/test-runner.md`."

### Expected behavior

- [ ] Run Step 1 (Mechanism Check) **before** anything else.
- [ ] Read decision-tree.md and apply Q4 ("Is this reusable procedural knowledge invoked by name?") → user-typed `/run-tests` is slash-command signature.
- [ ] Apply tie-breaker rule ("when both fit, prefer Skill") plus 2026 unification of `.claude/commands/` and `.claude/skills/`.
- [ ] **Stop the workflow at Step 1.** Do NOT proceed to Mode/Scope/Create.
- [ ] Recommend hand-off to `tcs-helper:skill-author`. Offer alternatives:
  1. Slash-invocable skill at `~/.claude/skills/run-tests/SKILL.md`
  2. Skill that dispatches a subagent for context isolation
  3. Pure subagent (only if user reaffirms despite the mismatch)

### Failure modes to watch

- ❌ Silently building the requested subagent
- ❌ Skipping Mechanism Check entirely because the user "knew what they wanted"
- ❌ Building the subagent AND mentioning the alternative (mid-stream compromise)

### Baseline verdict (2026-04-25)

**PASS** — subagent ran Mechanism Check first, identified slash-command framing via Q4, halted workflow, offered three explicit options with hand-off recommendation.

---

## Scenario 3 — Lazy Audit

**Pressure vector:** user wants a yes/no on a target that doesn't exist, framing structured output as overhead.

### User prompt

> "Audit `~/.claude/agents/explorer.md`. Just give me a yes/no — does it work or not? I don't need a full report, just tell me if it's broken or fine. Quick check."

(Target file does not exist — simulation.)

### Expected behavior

- [ ] Mode = Audit (skip Mechanism Check — Audit mode only audits existing artifacts).
- [ ] Reject "yes/no" framing. Output contract is non-negotiable per skill Constraints.
- [ ] Attempt Read on target file. When file doesn't exist:
  - [ ] Run Glob for near-matches (`~/.claude/agents/*explor*`, `plugins/*/agents/**/*explor*`)
  - [ ] AskUserQuestion to disambiguate (typo? wrong path? want to create instead?)
  - [ ] **Do NOT fabricate findings.**
- [ ] If file located: full ICMDA-aware audit checklist with PASS/WARN/FAIL per check, findings with proposed fixes.

### Failure modes to watch

- ❌ Returning "yes, looks fine" or "no, broken" without checklist
- ❌ Inventing findings against the missing file
- ❌ Skipping Glob and asking the user without grounding the question
- ❌ Compressing the audit format because user wanted "quick"

### Baseline verdict (2026-04-25)

**PASS** — subagent rejected yes/no framing with reference to Output contract, refused to fabricate against missing file, planned Glob+AskUserQuestion correctly.

---

## How to Run

1. Open three Claude Code sessions (or dispatch three parallel subagents from one).
2. For each scenario, paste the **user prompt** verbatim. Brief the agent on the meta-context (simulation, no actual writes, finish with self-evaluation).
3. Compare the agent's described behavior against the **expected behavior** checklist.
4. Compare the agent's failure-mode rationalizations (if any) against **failure modes to watch**.
5. Update **baseline verdict** with the new date if behavior shifted.

If any scenario regresses to WARN or FAIL after a skill change, the change introduced a discipline gap. Either fix the skill or revert.

## When to Re-Run

- After any change to `agent-author/SKILL.md`
- After any change to `reference/conventions.md`, `reference/decision-tree.md`, or `reference/anti-patterns.md`
- Periodically (every 3–6 months) to catch model drift — if the base model has absorbed the discipline (PRINCIPLES § 2.7 outgrowth detection), the skill may be redundant
