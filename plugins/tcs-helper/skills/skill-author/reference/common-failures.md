# Common Skill Failures

Failure patterns to watch for when creating, auditing, or converting skills.

---

## Failure: Declarative Instead of Imperative

**Symptom:** Agent reads skill but doesn't execute workflow

**Bad (declarative):**
```markdown
The security review should check for SQL injection vulnerabilities.
```

**Good (imperative):**
```markdown
### 3. Security Review

Search for database queries using Grep.
Check each query for string interpolation (vulnerability).
Report findings in Finding format.
```

---

## Failure: Missing Tool Instructions

**Symptom:** Agent has tools listed but doesn't use them

**Bad:** `allowed-tools: Task, Bash, Read` with no mention of tools in body.

**Good:** Workflow steps reference tools explicitly:
```markdown
### 1. Gather Context

match (target) {
  /^\d+$/  => gh pr diff $target    // uses Bash
  "staged" => git diff --cached     // uses Bash
}
```

---

## Failure: Description Summarizes Workflow

**Symptom:** Agent follows description shortcut, skips skill body

**Bad:**
```yaml
description: Coordinates code review by launching four specialized subagents then synthesizing findings
```

**Good:**
```yaml
description: Use when reviewing code changes, PRs, or staged files. Handles security, performance, quality, and test analysis.
```

---

## Failure: No Clear Starting Point

**Symptom:** Skill is comprehensive reference but agent doesn't know where to start

**Fix for linear workflows:** Use numbered `### N. Step Name` headings — execution order is implicit.

**Fix for non-linear workflows:** Add `### Entry Point` with a match block:
```markdown
### Entry Point

match (mode) {
  Create  => steps 2, 3, 7
  Audit   => steps 4, 7
  Convert => steps 5, 7
}
```

---

## Failure: Code Fences Around Skill Syntax

**Symptom:** Agent treats Interface, Constraints, or Workflow blocks as inert code rather than following them

**Fix:** Remove all ` ``` ` wrappers around Interface definitions, Constraints, State, and Workflow content. These blocks are instructions, not code samples.

---

## Failure: Documentation in Instructions

**Symptom:** Agent searches for removed files, gets confused by historical context, or wastes tokens on rationale it can't act on

Skills and agents are **imperative instructions for an LLM**, not documentation for humans. Rationale, history, and spec references dilute directives and cause actively harmful behavior — mentioning "file X was removed" triggers the model to search for X.

**Detect these anti-patterns:**

| Pattern | Example | Harm |
|---------|---------|------|
| Historical references | "was removed", "previously used", "no longer exists" | Model searches for the removed thing (Streisand effect) |
| Rationale blocks | "because...", "the reason is...", "this was done to..." | Dilutes the directive; model weighs explanation over instruction |
| Spec/doc refs without action | "see PRD §3.2", "per ADR-5", "as documented in..." | Dead context — model can't read external docs |
| Negative existence claims | "X doesn't exist", "there is no Y" | Model treats as hint that X/Y might exist |
| Past-tense narrative | "we decided to...", "this was introduced when..." | Wrong temporal frame — instructions must be present-tense imperative |
| Inline comments explaining why | `// added for the auth rewrite`, `# workaround for bug #42` | Rot as context changes; model may try to find the referenced bug/rewrite |

**The test:** For each non-imperative line, ask: *"Would removing this line degrade execution?"* If no — it's documentation, not instruction.

**Where stripped content goes:**

| Content type | Destination |
|--------------|-------------|
| Design rationale | `docs/` mirror file or ADR |
| Decision history | Git commit message |
| Recurring pattern | Memory bank |
| Disposable context | Nowhere — delete it |

**Critical:** Strip-first destroys institutional knowledge. Before removing rationale from a runtime file, verify the WHY is captured in its destination. Write to destination first, strip from runtime second.

---

## Failure: Backend Waits for a TTY

**Symptom:** A script the skill runs lists candidates and stops, or hangs, and never acts

Claude's Bash tool gives every subprocess a piped stdin, never a TTY, on host and in containers alike. A backend that confirms with `input()` or gates on `isatty()` cannot be driven by an agent.

**Fix:**
- Give the backend a non-interactive path: `--yes` to act on everything listed, or flags that select items.
- The skill shows the list, takes the user's explicit approval in chat, then re-runs with the flag. That approval replaces the TTY prompt.
- Without a TTY and without the flag, print how to proceed. A silent no-op reads as success.
- Keep the interactive prompt for a human at a real terminal, or the `!` prefix in a Claude prompt.

---

## Failure: Display Label Reused as a Lookup Key

**Symptom:** Routing silently falls through for some answers, with no error

An `AskUserQuestion` option label carries a parenthetical for the user — `Before Claude calls a tool (e.g. block pip installs)` — and the captured answer is later matched exactly against a heading such as `## Q3 = Before Claude calls a tool`. Every answer with a parenthetical misses.

**Fix, one of:**
- **Strip on capture** when the value stays internal: save the bare label, dropping everything from ` (e.g.` onward.
- **Prefix-match on dispatch** when the value is shown to the user again: match `starting with "Before Claude calls a tool"`.

**Detect:** any label that appears both as an option and as a key in a reference file. Search for `(e.g.` in option labels near `## … = ` headings.

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Instead |
|--------------|--------------|---------|
| Create without duplicate check | Fragments knowledge | Search first |
| 400+ line SKILL.md | Agents skim, miss sections | Extract to reference/ |
| Audit without reading file | Miss actual issues | Always read the skill |
| Fix without testing | May not address root cause | Verify fix works |
| Declarative-only workflow | Agents don't execute | Use imperative ### step headings |
| Description with workflow | Agents skip body | Triggers only in description |
| `type` aliases for enums | Extra indirection | Inline values into interface fields |
| Mirrored Always/Never rules | Wastes tokens | Each rule once, most natural framing |
