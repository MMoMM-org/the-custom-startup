# Rule Enforcer — Mechanism Matrix

Maps Q3 (earliest intervention point) × Q4 (response style) to the concrete
enforcement mechanism. Consumed by the `/enforce-rule` skill at workflow step 6.

Each section uses a parenthetical example so the user can recognize their own
rule — matching against a real case is more reliable than judging an abstract
property (PRD M3 design constraint).

---

## Q3 = Before Claude calls a tool

*(e.g., block bad git ops before they run, guard against --break-system-packages pip)*

| Q4 | Mechanism |
|----|-----------|
| Block | Claude PreToolUse hook |
| Auto-fix | Claude PreToolUse hook (rewrites args before execution) |
| Nudge | Claude PreToolUse hook (warn-only, prints reminder then allows) |

---

## Q3 = After Claude calls a tool

*(e.g., run skill-author after editing skills/, check for missing test after Write)*

Note: blocking is not useful here — the tool call already executed. The matrix
uses PostToolUse hook (warn-only) for the Block cell; if a hard block is truly
needed, choose "Before Claude calls a tool" instead, or add a CI gate.

| Q4 | Mechanism |
|----|-----------|
| Block | Claude PostToolUse hook (warn-only — tool already ran; use PreToolUse for true blocks) |
| Auto-fix | Claude PostToolUse hook (runs a follow-up corrective action) |
| Nudge | Claude PostToolUse hook |

---

## Q3 = User submits a prompt

*(e.g., inject context when recurrence-signal phrases detected, restore session state)*

| Q4 | Mechanism |
|----|-----------|
| Block | Claude UserPromptSubmit hook (rare — rejects or redirects the prompt) |
| Auto-fix | Claude UserPromptSubmit hook (rewrites or appends to prompt before processing) |
| Nudge | Claude UserPromptSubmit hook (prepends suggestion line, does not block) |

---

## Q3 = Session start

*(e.g., restore important context at session open, validate env or tool versions)*

| Q4 | Mechanism |
|----|-----------|
| Block | Claude SessionStart hook (exits session if preconditions unmet) |
| Auto-fix | Claude SessionStart hook (runs setup/repair steps automatically) |
| Nudge | Claude SessionStart hook (prints reminders at session open) |

---

## Q3 = Local git push

*(e.g., block push if CHANGELOG missing, warn if docs out of date before PR creation)*

Uses bundle-versioning pattern (ADR-2): template lives in
`plugins/tcs-helper/templates/githooks/`, installed hook ships a sibling
`tcs-helper-rule-enforcer-version` marker for drift detection.

| Q4 | Mechanism |
|----|-----------|
| Block | git pre-push hook (exit 1, refuses push until violation resolved) |
| Auto-fix | git pre-push hook (auto-patches file then re-stages; rare — prefer nudge) |
| Nudge | git pre-push hook (prints warning, exits 0, lets push through) |

---

## Q3 = PR/merge to main

*(e.g., auto-bump marketplace.json on merge, block PR if required file missing)*

| Q4 | Mechanism |
|----|-----------|
| Block | CI workflow (required check — PR cannot merge if check fails) |
| Auto-fix | CI workflow (auto-PR or commit: detects and patches the violation automatically) |
| Nudge | CI workflow (posts a comment on PR, check passes, merge not blocked) |

---

## Q3 = In repeated coding patterns

*(e.g., TDD discipline, always run skill-author before committing a new skill)*

Coding-pattern rules are enforced through prompt-level guidance — there is no
discrete tool call or git boundary to hook. All three response styles use a
Skill with discipline language; the Q4 choice shapes how strongly the skill
is worded (Block → must, Auto-fix → will-do-it-for-you, Nudge → should).

| Q4 | Mechanism |
|----|-----------|
| Block | Skill with discipline language (MUST-style constraints, refuses to proceed) |
| Auto-fix | Skill with discipline language (performs the corrective action automatically) |
| Nudge | Skill with discipline language (recommends, does not block) |

---

## Fallback: Genuine judgment call

When the rule cannot be captured by any of the 7 Q3 options above (Q2 = "No —
judgment only"), or when the rule has only occurred once (Q1 = "First time"):

**Mechanism: Memory rule** — add to memory via `tcs-helper:memory-add` with
strong-language template. Memory is the layer-1 defense; the enforcer is for
escalation when memory has empirically failed.
