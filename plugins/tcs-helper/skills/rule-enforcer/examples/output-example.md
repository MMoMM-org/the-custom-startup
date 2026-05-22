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
