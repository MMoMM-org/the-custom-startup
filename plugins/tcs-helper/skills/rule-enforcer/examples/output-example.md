# Rule Enforcer — Output Examples

Documented triage paths exercising each major branch. Each scenario records the
4-question answers and expected mechanism so the workflow can be validated
manually in a fresh Claude Code session.

---

## Scenario A: First-time occurrence (Q1 short-circuit)

**Rule**: "I keep forgetting to add a test for new utility functions"

| Question | Answer | Notes |
|----------|--------|-------|
| Step 1 — confirm rule | Looks right — continue | Rule echoed back correctly |
| Q1 — recurrence | `First time — no memory yet` | Never seen before in any session |
| Q2–Q4 | skipped | Short-circuit fires at Q1 |

**Expected outcome**: Defer to `Skill(tcs-helper:memory-add)` and exit triage immediately. Q2–Q4 are never asked.

**Rationale**: A first-time occurrence is not an enforcement escalation scenario — it is a new rule that belongs in memory. The enforcer is for escalation when memory has empirically failed.

---

## Scenario B: Recurring + judgment-only (Q2 short-circuit)

**Rule**: "My code tends to get too verbose — I should write more concisely"

| Question | Answer | Notes |
|----------|--------|-------|
| Step 1 — confirm rule | Looks right — continue | Rule echoed back correctly |
| Q1 — recurrence | `Recurring — memory exists but was ignored` | Memory entry exists, was broken again |
| Q2 — detectable? | `No — judgment only` | "Too verbose" requires human judgment; no grep can catch this |
| Q3–Q4 | skipped | Short-circuit fires at Q2 |

**Expected outcome**: Short-circuit to Memory rule with strong-language template. Defer to `Skill(tcs-helper:memory-add)` with hint to use strong wording (MUST / NEVER / ALWAYS). Q3–Q4 are never asked.

**Rationale**: Mechanical enforcement requires a detectable signal. Judgment calls cannot be automated; the only escalation from plain memory is stronger memory wording.

---

## Scenario C: Recurring + detectable + PR/merge + Auto-fix → CI workflow

**Rule**: "I keep forgetting to bump plugin version numbers before merging"

| Question | Answer | Notes |
|----------|--------|-------|
| Step 1 — confirm rule | Looks right — continue | Rule echoed back correctly |
| Q1 — recurrence | `Recurring — memory exists but was ignored` | Memory entry exists; PR #29 case |
| Q2 — detectable? | `Yes — concrete signal` | "marketplace.json version unchanged" is grep-detectable |
| Q3 — intervention point | `PR/merge to main (e.g. CI auto-bump versions)` | Violation is only meaningful at merge time |
| Q4 — enforcement style | `Auto-fix — silently correct or generate the missing artifact` | Prefer hands-off automation |

**Expected mechanism**: `CI workflow (auto-PR or commit: detects and patches the violation automatically)`

**Rationale**: Matrix section `## Q3 = PR/merge to main`, row `Auto-fix` → CI workflow (auto-commit/auto-PR). Matches the PR #29 auto-bumper origin case.

---

## Scenario D: Recurring + detectable + Local git push + Block → git pre-push hook

**Rule**: "I keep forgetting to add a CHANGELOG entry before pushing"

| Question | Answer | Notes |
|----------|--------|-------|
| Step 1 — confirm rule | Looks right — continue | Rule echoed back correctly |
| Q1 — recurrence | `Recurring — memory exists but was ignored` | Memory entry exists; broken multiple times |
| Q2 — detectable? | `Yes — concrete signal` | "Missing CHANGELOG line" is grep-detectable |
| Q3 — intervention point | `Local git push (e.g. block before pushing if CHANGELOG missing)` | Enforce before remote receives the commit |
| Q4 — enforcement style | `Block — refuse the action until the violation is resolved` | Hard block: push must not succeed if rule is violated |

**Expected mechanism**: `git pre-push hook (exit 1, refuses push until violation resolved)`

**Rationale**: Matrix section `## Q3 = Local git push`, row `Block` → git pre-push hook (exit 1). Bundle-versioning pattern (ADR-2) applies: template lives in `plugins/tcs-helper/templates/githooks/`.

---

## Scenario E: Coding pattern + Block → Skill hand-off

**Rule**: "I keep skipping TDD — I start writing code before writing the test"

| Question | Answer | Notes |
|----------|--------|-------|
| Step 1 — confirm rule | Looks right — continue | Rule echoed back correctly |
| Q1 — recurrence | `Recurring — memory exists but was ignored` | Memory entry exists; pattern repeated across sessions |
| Q2 — detectable? | `Yes — concrete signal` | Can detect Write/Edit calls before any test file is modified |
| Q3 — intervention point | `In repeated coding patterns (e.g. TDD discipline)` | No discrete hook boundary — rule is about coding approach |
| Q4 — enforcement style | `Block — refuse the action until the violation is resolved` | Must-style: enforce TDD strictly |

**Expected mechanism**: `Skill with discipline language (MUST-style constraints, refuses to proceed)`

**Step 8 hand-off**: Dispatches `Skill(tcs-helper:skill-author)` with `$ARGUMENTS` = `"Create or update a skill that enforces: I keep skipping TDD — I start writing code before writing the test. Q4 style: Block."`

**Rationale**: Matrix section `## Q3 = In repeated coding patterns`, row `Block` → Skill with discipline language (MUST-style). No hook boundary exists for coding patterns; prompt-level guidance is the only lever.

---

## Scenario F: Hook path + PreToolUse + Block → hook-development hand-off

**Rule**: "I keep using --break-system-packages when installing Python packages on macOS"

| Question | Answer | Notes |
|----------|--------|-------|
| Step 1 — confirm rule | Looks right — continue | Rule echoed back correctly |
| Q1 — recurrence | `Recurring — memory exists but was ignored` | Memory entry `feedback_python_venv.md` exists; broken again |
| Q2 — detectable? | `Yes — concrete signal` | `--break-system-packages` flag is grep-detectable in pip/pip3 commands |
| Q3 — intervention point | `Before Claude calls a tool (e.g. block --break-system-packages)` | Intercept before the Bash tool runs the pip command |
| Q4 — enforcement style | `Block — refuse the action until the violation is resolved` | Hard block: command must not execute with that flag |

**Expected mechanism**: `Claude PreToolUse hook`

**Step 8 hand-off**: Dispatches `Skill(plugin-dev:hook-development)` with hook event = `PreToolUse` and rule context `"Block pip/pip3 commands that include --break-system-packages on macOS"`.

**Rationale**: Matrix section `## Q3 = Before Claude calls a tool`, row `Block` → Claude PreToolUse hook. The flag is detectable in the tool-call arguments before execution.

---

## Scenario G: Hook path — plugin-dev NOT installed → fallback AskUserQuestion

**Rule**: Same as Scenario F — `--break-system-packages` block.

**Trigger**: At Step 8, `plugin-dev:hook-development` plugin is not installed in the current session.

**Step 8 behaviour**: Instead of invoking hook-development, presents AskUserQuestion fallback:

> "The `plugin-dev` plugin (required for hook authoring) is not installed. How would you like to proceed?"

Options offered:
- `Install plugin first — I will install plugin-dev and retry` → instructs user to install the plugin, aborts triage
- `Use Memory rule instead — add to memory with strong wording` → dispatches `Skill(tcs-helper:memory-add)` with `type=feedback` and hint: prepend rule with `NEVER`
- `Cancel — exit triage, no action taken` → exits skill, no further action

**User picks**: `Use Memory rule instead`

**Final hand-off**: `Skill(tcs-helper:memory-add)` invoked with `type=feedback` and strong-language hint. Rule stored as: `"NEVER use --break-system-packages when installing Python packages on macOS — always use a venv (PEP 668)."`

**Rationale**: Fallback path prevents a hard crash when the target plugin is absent. Memory rule is the recommended interim since it is always available.
