# Brainstorm: Rule-Enforcer Skill + Phrase Intercept Hook

**Date:** 2026-05-21
**Author:** Marcus + Claude (Opus 4.7)
**Status:** Brainstorm complete — ready for PRD
**Source conversation:** session that produced PR #27 (Finalize step), PR #28 (catch-up bump), PR #29 (auto-bumper CI), PR #30 (stale-spec cleanup)

## Problem Statement

This conversation surfaced a recurring anti-pattern: **memory rules that don't stick.**

Concrete example: `feedback_no-manual-marketplace-sync.md` was written 10 days ago with explicit guidance ("every behavior-changing PR must also bump `plugin.json` (and `marketplace.json` metadata version) before merge"). Today it was violated immediately (PR #27 shipped without bumps), requiring a catch-up PR #28, which finally led to mechanizing the rule via PR #29 (auto-bump CI).

The memory was not the bug-preventer — the **CI workflow** was. Memories rely on Claude re-reading and applying them; mechanization makes the rule load-bearing on a system that can't forget.

This pattern likely repeats across many memories. Other candidates already visible in the memory bank:
- `feedback_skill-author-on-creation.md` — partially mechanized via authoring.md PostToolUse reminder hook, but still relies on Claude noticing
- `feedback_python_venv.md` — could be a PreToolUse hook that detects `pip install` on macOS and intercepts
- `feedback_test-stubs-mirror-real-wire-format.md` — could be a skill, but trigger conditions are too judgment-based
- `feedback_archive-source-docs.md` — pure judgment, memory is right place

The friction: when a new "remember to X" rule appears, the user (and Claude) defaults to writing it as memory. There's no structured prompt to ask: *should this be mechanized instead?*

## Goal

Build a **rule-enforcer skill** that:

1. **Auto-triggers** when phrases or patterns suggest a recurring rule (via UserPromptSubmit hook that watches for trigger phrases — "vergessen", "remember to", "wieder vergessen", "I keep…", "next time")
2. **User-invokes** via `/enforce-rule "<description>"` for explicit triage
3. **Triages** the rule against a mechanism matrix
4. **Routes** to the appropriate author-skill (skill-author, hook-development, ci-author-TBD) to scaffold the chosen mechanism
5. **Falls back to memory-add** only when no mechanization fits

## Design — Triage Framework

Four questions, applied in order:

### Q1: Frequency / ROI

How often has this failed?
- **1 time** → Likely premature; suggest writing a Memory rule first, revisit if violated again
- **2+ times** → Mechanization candidate; proceed to Q2
- **Cross-cutting (would affect everyone using TCS)** → Mechanize regardless of frequency

### Q2: Mechanical Detectability

Can the violation be detected programmatically?
- **No (subjective/judgment)** → Memory rule with strong language (Persuasion-principles); STOP
- **Yes** → Proceed to Q3

Examples:
- "Forgot to bump marketplace.json" — YES (diff-based)
- "Wrote code without a failing test first" — PARTIALLY (TDD guardian heuristics)
- "Mocked the database in integration tests" — YES (grep `jest.mock.*db`)
- "Communicated too verbosely" — NO (judgment)

### Q3: Earliest Point of Intervention

Where in the workflow can the violation be caught earliest?

| Where | Mechanism | Examples this repo |
|-------|-----------|-------------------|
| Before Claude calls a tool | Claude PreToolUse hook | tcs-git-helpers `DESTRUCTIVE_CHECKOUT`, `FORCE_PUSH` |
| After Claude calls a tool | Claude PostToolUse hook | authoring.md skill-author reminder |
| User submits a prompt | Claude UserPromptSubmit hook | (none yet; this skill would be one) |
| Session start | Claude SessionStart hook | context-bridge restore |
| Session end | Claude SessionEnd hook | — |
| Local git operation | Git hook (`.githooks/`) | pre-commit format check |
| PR / merge to main | CI workflow (`.github/workflows/`) | spec-012 hook-bundle gate, PR #29 auto-bumper |
| In repeated coding patterns | Skill with discipline-enforcing prompt | tdd-guardian, spec-compliance-reviewer |
| Genuine judgment call | Memory rule (last resort) | `feedback_archive-source-docs` |

### Q4: Block, Auto-Fix, or Nudge?

Once detected, what response?
- **Block** — refuse the action, force the user to fix (destructive ops)
- **Auto-fix** — silently correct (auto-bump)
- **Nudge** — proceed but emit a warning/reminder (skill-author hook)

Trade-offs:
- Block = highest assurance, highest friction
- Auto-fix = zero friction, but requires CI to fix what dev forgot (delayed feedback)
- Nudge = low friction, easily ignored

## Design — Intercept Hook

Companion piece: a Claude UserPromptSubmit hook that watches for trigger phrases in user prompts and prepends a system message recommending `/enforce-rule`.

**Trigger phrases (initial set):**
- DE: "vergessen", "schon wieder", "wieder vergessen", "nicht daran denken"
- EN: "keep forgetting", "remember to", "next time", "I always forget"
- Pattern: "I should/shouldn't…", "we need to remember…"

**False-positive mitigation:**
- Only trigger if phrase appears in a context that suggests recurrence (not e.g. "I forget the syntax for X")
- Possibly require 2+ trigger phrases in same prompt
- Soft suggestion ("Consider /enforce-rule …"), not interruption

**Output of intercept:** a single-line system reminder injected into the prompt: `[rule-enforcer] Detected recurrence signal — consider running /enforce-rule to triage if this can be mechanized.`

## Open Design Questions for PRD

1. **Slash command name** — `/enforce-rule`, `/automate-rule`, `/triage-rule`, `/mechanize`? Marcus's preference?
2. **Hook placement** — `tcs-helper/hooks/rule-enforcer-intercept.json` or `tcs-helper/hooks/user-prompt-watch.json`?
3. **Trigger-phrase config** — hard-coded in hook, or pulled from a `reference/trigger-phrases.md` so users can extend?
4. **Routing UI** — AskUserQuestion picker for mechanism, or direct hand-off based on Q3 answer?
5. **Mechanism-matrix as reference or inline** — reference/mechanism-matrix.md (token-cheap, lazy-loaded) vs inline (always available)?
6. **Memory fallback** — should the skill itself invoke `memory-add`, or just recommend?
7. **Scaffolding scope** — pure routing (hand off to skill-author etc.), or include built-in templates for common cases (CI patch-bump, post-tool nudge)?
8. **Auto-trigger vs user-only** — should the hook fire automatically, or only as a `/`-command response?
9. **CI-workflow author** — there's no existing skill for "author a GitHub Actions workflow". Should this skill include lightweight CI scaffolding, or punt to TBD `ci-workflow-author`?

## Anti-patterns to avoid

- Skill becomes a noisy interruption ("did you mean to mechanize this?") on every minor user prompt
- Routing logic that's too greedy — recommends a hook for one-off issues
- Duplicates `tcs-helper:skill-author` / `plugin-dev:hook-development` capabilities instead of routing
- Becomes a meta-skill that requires its own enforcer to remember to use

## Memories that would be informed by this skill

- `feedback_no-manual-marketplace-sync.md` — would have proposed CI patch-bump immediately
- `feedback_skill-author-on-creation.md` — would have proposed PostToolUse hook (which now exists)
- `feedback_bash_dir_persistence.md` — would have proposed making the Bash tool's wrapper script auto-cd
- `feedback_validate-fixtures-in-target-tools.md` — would have proposed adding a fixture-validation step to the implementer subagent's prompt

## Related work in this repo

- `tcs-helper:skill-author` — for skill scaffolding
- `tcs-helper:agent-author` — for agent scaffolding
- `tcs-helper:memory-add` — for memory entries
- `plugin-dev:hook-development` — for Claude hook scaffolding
- `tcs-git-helpers` — for git-hook scaffolding (less explicit author tool)
- `.github/workflows/` — for CI workflows (no author tool yet)

This skill sits ONE LEVEL above all of those — it routes to them.

## Estimated scope

- `SKILL.md` ~200 lines (triage workflow + routing)
- `reference/mechanism-matrix.md` ~80 lines
- `reference/trigger-phrases.md` ~40 lines
- `reference/examples.md` ~120 lines (10 worked examples from memory bank)
- `hooks/rule-enforcer-intercept.json` — Claude UserPromptSubmit hook config
- `scripts/intercept-watch.sh` — trigger phrase detector (~50 lines bash)

Total: ~500 lines new content + hook config.

---

## Next step

PRD via xdd-prd skill. This brainstorm artifact is the input.
