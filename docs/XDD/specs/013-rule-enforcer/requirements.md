---
title: "Rule Enforcer Skill + Phrase Intercept Hook"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain (12 open questions: 8 resolved/defaulted in PRD, 3 deferred to SDD with explicit decision criteria)
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (3 live violation patterns from this session)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events (where applicable)
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

A meta-skill that converts repeated *"I keep forgetting X"* moments into structured automation decisions — so mechanizable rules become hooks/CI/skills instead of accumulating as ignored memory entries.

### Problem Statement

**Memory rules for "remember to X" do not reliably prevent the X violation.**

Concrete proof from this session (2026-05-21):
1. `feedback_no-manual-marketplace-sync.md` was written 2026-05-11 with explicit "always bump plugin.json AND marketplace.json" guidance.
2. **10 days later**, the same Claude that wrote the memory violated it (PR #27 shipped Finalize step without bumps → PR #28 catch-up required).
3. The bug class only got eliminated by **mechanization** (PR #29 auto-bump CI workflow), not by the memory.
4. Within the same session, **3 mechanizable rules were violated** — marketplace bump, the memory itself, and post-feature docs updates (CHANGELOG/README missed when Finalize shipped — fixed in commit `5834976`).

Memory's failure mode is **recall-and-apply-at-action-time**, which depends on Claude reading the memory, recognizing relevance, and choosing to comply. Each step is fallible. Mechanization removes the choice from the loop — the system enforces, the rule cannot be ignored.

**Cost of the status quo:** every violated memory becomes a reactive catch-up commit or PR. This session alone produced PR #28 (catch-up bump) and commit `5834976` (catch-up docs) — both preventable.

### Value Proposition

Triages new "I keep forgetting X" moments against a 5-mechanism matrix:

| Mechanism | Catches | Response style |
|-----------|---------|----------------|
| Claude PreToolUse/PostToolUse hook | violations at tool-call boundary | block / nudge |
| Git hook (.githooks/) | local git operation issues | block / warn |
| CI workflow (.github/workflows/) | violations visible at PR/merge | auto-fix / block / warn |
| Skill with discipline language | recurring coding patterns | nudge through prompt |
| Memory rule | genuine judgment calls | rely on recall (last resort) |

For each candidate rule, the skill walks 4 triage questions (frequency, mechanical detectability, earliest intervention point, response style) and **routes to the right author skill** (skill-author, hook-development, etc.). When mechanization doesn't fit, it falls back to `memory-add` with strong-language templates.

**Outcome:** fewer ignored memories, more enforced automation, fewer reactive catch-up PRs.

---

## User Personas

### Primary Persona: TCS Plugin Author (Marcus)

- **Demographics:** Solo developer, deep TCS plugin expertise, also operator of MiYo-related repos
- **Goals:** Ship plugin changes without forgetting mechanical follow-ups (version bumps, docs updates, hook scaffolding). Keep cognitive load on design decisions, not bookkeeping.
- **Pain Points:** Memory entries pile up faster than they get followed. Same mistakes recur. Reactive catch-up PRs interrupt flow.

### Secondary Persona: Claude Instance (in TCS-hosted sessions)

- **Demographics:** LLM agent operating across TCS plugin development sessions
- **Goals:** Apply project conventions reliably without depending on every memory file being loaded into every context window
- **Pain Points:** Memory entries are observational; when prompts get long or context compresses, recall degrades. Mechanical signals from hooks/CI never degrade.

---

## User Journey Maps

### Primary User Journey: Recurring Rule Detection

1. **Awareness:** Marcus says *"I keep forgetting…"* / *"wieder vergessen"* / *"remember to…"* in a prompt. The `UserPromptSubmit` hook detects the trigger phrase and **prepends a single-line system reminder**: `[rule-enforcer] Detected recurrence signal — consider running /enforce-rule to triage if this can be mechanized.`
2. **Consideration:** Marcus runs `/enforce-rule "<description of the recurring rule>"` (suggested or manual). The skill greets with the 4-question triage.
3. **Adoption:** Marcus answers Q1–Q4 via AskUserQuestion. Skill computes the recommended mechanism and presents it with rationale. Marcus confirms or overrides.
4. **Usage:** Skill hands off to the matching author skill (e.g., `Skill(plugin-dev:hook-development)` for a Claude hook, `Skill(tcs-helper:skill-author)` for a discipline skill, inline CI/pre-push scaffolding for the two established templates). Author skill walks Marcus through the actual file creation.
5. **Retention:** The new mechanism catches the next violation. Marcus's memory bank stops growing with "I should…" entries that never get followed. The skill itself is invoked organically every time a recurrence signal appears.

### Secondary User Journey: Manual Triage (No Intercept)

Marcus has a half-formed thought *"I wonder if we should automate the way we tag commits"* — not a "I keep forgetting" phrase. He runs `/enforce-rule "tag commits by phase"` directly. Skill performs triage as in the primary journey, may recommend Memory (Q2 = judgment-only) or a git commit-msg hook (Q2 = mechanical).

---

## Feature Requirements

### Must Have Features

#### Feature M1: UserPromptSubmit Intercept Hook

- **User Story:** As Marcus, I want the system to notice when I say "I keep forgetting" so that I don't have to remember to triage every potential automation opportunity myself.
- **Acceptance Criteria:**
  - [ ] Given user submits a prompt containing any trigger phrase from `reference/trigger-phrases.md`, When `UserPromptSubmit` hook fires, Then a single-line system reminder is prepended suggesting `/enforce-rule`
  - [ ] Given user submits a prompt with no trigger phrase, When the hook fires, Then no reminder is injected (no noise)
  - [ ] Given hook execution duration is measured, When 100 invocations are sampled, Then the p95 latency is ≤ 50ms (UserPromptSubmit runs on every prompt — must be cheap)
  - [ ] Given the trigger-phrase file is missing or empty, When the hook fires, Then it exits silently with non-zero only on actual errors (graceful degradation)

#### Feature M2: `/enforce-rule` Slash Command (Skill Entry Point)

- **User Story:** As Marcus, I want a single slash command to start triage so that I don't have to remember which author skill to invoke.
- **Acceptance Criteria:**
  - [ ] Given user runs `/enforce-rule "<description>"`, When the skill loads, Then it begins the 4-question triage with the description as starting context
  - [ ] Given user runs `/enforce-rule` with no description, When the skill loads, Then it asks for a description via AskUserQuestion (or accepts free-text follow-up)
  - [ ] Given the skill is invoked, When the active-skill announcement fires, Then it announces `tcs-helper:rule-enforcer`

#### Feature M3: 4-Question Triage Logic

- **User Story:** As Marcus, I want a deterministic triage workflow so that the same rule always gets the same mechanism recommendation.
- **Acceptance Criteria:**
  - [ ] Given triage begins, When Q1 (frequency) is asked, Then options are {1×, 2+×, Cross-cutting}
  - [ ] Given Q1 answer is `1×`, When the skill proceeds, Then Memory fallback is recommended without asking Q2–Q4 (skill suggests revisiting if rule is violated again)
  - [ ] Given Q1 answer is `2+×` or `Cross-cutting`, When the skill proceeds, Then Q2 (mechanical detectability) is asked
  - [ ] Given Q2 answer is `No — judgment only`, When the skill proceeds, Then Memory fallback is recommended (skip Q3, Q4)
  - [ ] Given Q2 answer is `Yes`, When the skill proceeds, Then Q3 (earliest intervention) and Q4 (block/auto-fix/nudge) are asked in sequence

#### Feature M4: Mechanism Matrix Routing

- **User Story:** As Marcus, I want the triage answers mapped to a concrete mechanism so that I know exactly what to build next.
- **Acceptance Criteria:**
  - [ ] Given Q3 = `Before Claude calls a tool` AND Q4 = `Block`, When the mechanism is computed, Then result is `Claude PreToolUse hook`
  - [ ] Given Q3 = `After Claude calls a tool` AND Q4 = `Nudge`, When the mechanism is computed, Then result is `Claude PostToolUse hook`
  - [ ] Given Q3 = `PR/merge to main` AND Q4 = `Auto-fix`, When the mechanism is computed, Then result is `CI workflow` (e.g., auto-bump pattern)
  - [ ] Given Q3 = `PR/merge to main` AND Q4 = `Block`, When the mechanism is computed, Then result is `CI workflow with required check`
  - [ ] Given Q3 = `Local git operation` AND Q4 = `Block`, When the mechanism is computed, Then result is `git pre-push hook` (in `.githooks/`)
  - [ ] Given Q3 = `In repeated coding patterns`, When the mechanism is computed, Then result is `Skill with discipline-enforcing language`
  - [ ] Given Q3 = `Genuine judgment call`, When the mechanism is computed, Then result is `Memory rule` (last resort)
  - [ ] Given any mechanism is computed, When presented to the user, Then it is shown via AskUserQuestion with `Accept | Override | Explain rationale` options

#### Feature M5: Hand-off to Existing Author Skills

- **User Story:** As Marcus, I want the enforcer to hand off cleanly so that file creation is done by the specialized author skill, not duplicated here.
- **Acceptance Criteria:**
  - [ ] Given mechanism = `Skill with discipline-enforcing language`, When hand-off begins, Then `Skill(tcs-helper:skill-author)` is invoked with the rule description as context
  - [ ] Given mechanism = `Claude * hook`, When hand-off begins, Then `Skill(plugin-dev:hook-development)` is invoked with the hook event type pre-selected
  - [ ] Given mechanism = `Memory rule`, When hand-off begins, Then `Skill(tcs-helper:memory-add)` is invoked with a strong-language template hint
  - [ ] Given hand-off completes, When user returns to the enforcer flow, Then the enforcer logs the chosen mechanism + hand-off target to the session for later observability (optional)

#### Feature M6: Inline Scaffolding for Two Established Templates

- **User Story:** As Marcus, I want the two patterns we already proved this session (auto-bump CI, pre-push docs gate) to be inline-scaffoldable, not hand-off-only — they're common enough to template.
- **Acceptance Criteria:**
  - [ ] Given mechanism = `CI workflow` AND template hint = `auto-bump-style patch`, When the skill scaffolds, Then it produces `.github/workflows/<name>.yml` + `scripts/ci/<name>.sh` based on the PR #29 pattern with the new rule's detection logic
  - [ ] Given mechanism = `git pre-push hook` AND template hint = `docs-gate-style`, When the skill scaffolds, Then it proposes a `.githooks/pre-push` snippet that detects the violation pattern and prints a block message
  - [ ] Given the user wants neither template, When asked, Then the skill falls back to hand-off (Feature M5)

#### Feature M7: Skill Self-Test Against This Session's Violations

- **User Story:** As Marcus, I want proof that the triage logic produces the right answer on the 3 rules I actually violated this session so that I trust the skill on future rules.
- **Acceptance Criteria:**
  - [ ] Given the rule `I keep forgetting to bump marketplace.json after plugin changes`, When triaged, Then the recommended mechanism is `CI workflow` (matches the PR #29 auto-bumper that solved it)
  - [ ] Given the rule `I keep forgetting to update CHANGELOG/README after shipping a feature`, When triaged, Then the recommended mechanism is `git pre-push hook` (per user's session-time refinement: catch before PR creation)
  - [ ] Given the rule `I keep forgetting to run skill-author after editing skills/`, When triaged, Then the recommended mechanism is `Claude PostToolUse hook` (matches the existing `authoring.md` reminder pattern)
  - [ ] Given the self-test fixtures, When the test suite runs, Then all 3 cases produce the expected mechanism without manual intervention

### Should Have Features

#### Feature S1: Externalized Trigger-Phrase Config

- **User Story:** As Marcus, I want trigger phrases to live in a readable reference file so that I can extend them without editing the hook script.
- **Acceptance Criteria:**
  - [ ] Given `reference/trigger-phrases.md` exists, When the intercept hook fires, Then trigger phrases are loaded from that file
  - [ ] Given the file is edited, When the next prompt is submitted, Then the new phrases take effect (no plugin reinstall required)

#### Feature S2: Worked Examples in Reference

- **User Story:** As Marcus, I want a library of worked triage examples so that the matrix decisions are concrete, not abstract.
- **Acceptance Criteria:**
  - [ ] Given the skill is reviewed, When `reference/examples.md` is opened, Then at least 5 real cases (including the 3 from this session) are documented with Q1–Q4 answers and final mechanism

### Could Have Features

#### Feature C1: Memory-Bank Audit Mode

- **User Story:** As Marcus, I might want a one-time pass over my existing memory to identify mechanization candidates.
- **Acceptance Criteria:**
  - [ ] Given `/enforce-rule --audit-memory` is invoked, When the skill scans all `feedback_*.md` files in the memory bank, Then it produces a ranked list of "mechanization candidates" with proposed mechanisms

#### Feature C2: Recurrence Detection from Git Log

- **User Story:** As Marcus, I might want the skill to detect recurrence by scanning git for "fix:" commits that revert recent work (a proxy for "we keep doing the same thing wrong").
- **Acceptance Criteria:**
  - [ ] Given `/enforce-rule --scan-git` is invoked, When the skill greps the last 30 days of `fix:` commits, Then it surfaces patterns of repeated bug categories

### Won't Have (This Phase)

- **W1:** Automatic hook installation — every scaffold proposal requires user confirmation before writing files
- **W2:** Cross-repo enforcement — TCS-internal only; downstream consumers can adopt the resulting hooks/CI but the enforcer skill itself stays here
- **W3:** ML-based phrase detection — keyword/regex on `reference/trigger-phrases.md` is sufficient
- **W4:** Rewriting or removing existing memory entries — the enforcer only ADDS mechanisms; memory cleanup is `tcs-helper:memory-cleanup`'s job
- **W5:** Per-repo trigger phrase customization in v1 — single global config in the plugin; per-repo override deferred

---

## Detailed Feature Specifications

### Feature: M3 — 4-Question Triage Workflow

**Description:** Deterministic triage that maps a free-text rule description to one of 5 mechanisms via 4 sequential questions. Designed to short-circuit cleanly when the answer is obviously "Memory" (Q1 = 1× or Q2 = judgment-only).

**User Flow:**

1. User invokes `/enforce-rule "<rule description>"` OR is prompted by the intercept hook.
2. Skill announces active state, echoes the rule description, then asks Q1 via AskUserQuestion.
3. Based on Q1, either short-circuits to Memory fallback OR proceeds to Q2.
4. Based on Q2, either short-circuits to Memory fallback OR proceeds to Q3.
5. Q3 (earliest intervention) is asked with 7 options matching the mechanism matrix.
6. Q4 (response style: block / auto-fix / nudge) is asked.
7. Skill computes the mechanism and presents the recommendation with rationale.
8. User picks `Accept | Override | Explain rationale` via AskUserQuestion.
9. On Accept, skill hands off to the matching author skill (M5) or inline scaffolder (M6).

**Business Rules:**

- **BR-1:** Q1 short-circuit at `1×` always recommends Memory (single occurrences don't justify mechanism overhead; revisit on recurrence).
- **BR-2:** Q2 short-circuit at `Judgment-only` always recommends Memory with strong-language template.
- **BR-3:** Q4 = `Block` raises the bar — the recommendation includes a warning that `--no-verify` or equivalent bypass exists; if the rule is critical, recommend CI gate as backup.
- **BR-4:** Cross-cutting frequency (Q1) overrides the Q1 = 1× short-circuit — even one occurrence justifies mechanization if it affects everyone using TCS.

**Edge Cases:**

- **EC-1:** Rule description is too vague to triage → Skill asks user to refine before Q1.
- **EC-2:** User picks `Override` at the mechanism step → Skill records the override reason in session log and proceeds with the user's chosen mechanism.
- **EC-3:** User's chosen mechanism has no matching author skill → Skill explains the gap and recommends `Memory rule` as a documented workaround until the author skill exists.
- **EC-4:** Two reasonable mechanisms could fit (e.g., Q3 = `local git operation` AND Q4 = `auto-fix` could be either git hook with patch logic or post-commit hook) → Skill presents BOTH and asks user to pick.

---

## Success Metrics

### Key Performance Indicators

- **Adoption:** Every "I keep forgetting" / "wieder vergessen" recurrence signal in a TCS session within 30 days post-launch results in either (a) skill invocation OR (b) explicit user-noted "no automation possible" — measured by intercept-hook trigger count vs. follow-up skill invocations
- **Engagement:** Skill invoked organically (auto + manual) ≥5 times per month after first month
- **Quality:** ≥80% of completed triage sessions result in `mechanism != Memory` (proxy for "we're catching real automation opportunities, not just adding more memories")
- **Business Impact:** Decrease in reactive catch-up PRs per month (baseline = PR #28 + commit `5834976` in the 2026-05-21 session = 2 catch-ups in one day; target = ≤1 per month after 60 days)

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `intercept-hook-fired` | trigger_phrase, prompt_length, suggestion_injected (bool) | Measure intercept volume + signal-to-noise |
| `enforce-rule-invoked` | invocation_source (intercept \| manual), rule_description_hash | Measure adoption + organic vs prompted use |
| `triage-completed` | q1_answer, q2_answer, q3_answer, q4_answer, recommended_mechanism, user_override (bool) | Measure triage distribution + override rate |
| `handoff-invoked` | mechanism, target_skill | Measure hand-off success vs Memory fallback |

Tracking is optional in v1 (per `Won't Have W2-equivalent assumption: no telemetry pipeline yet`). Could be added as Could Have via a local JSONL append.

---

## Constraints and Assumptions

### Constraints

- **C1:** Lives in `plugins/tcs-helper/skills/rule-enforcer/` (consistent with skill-author / agent-author / memory-add — the "Meta-Tools" cluster)
- **C2:** Hook overhead ≤ 50ms p95 (UserPromptSubmit runs on every prompt — strict budget)
- **C3:** Pure bash 3.2 + tools already available in tcs-helper (no new runtime dependencies)
- **C4:** Must not block prompts on hook errors — graceful degradation only
- **C5:** Trigger-phrase config must be data-driven (not code-baked) so user can extend without re-installing

### Assumptions

- **A1:** Trigger phrases reliably indicate recurrence intent (initial set tuned from this session; will need iteration)
- **A2:** User WANTS to be reminded; the skill suggests, never blocks the user's actual prompt
- **A3:** Existing author skills (`skill-author`, `hook-development`, `agent-author`, `memory-add`) are the right hand-off destinations — this skill stays a router, not a duplicator
- **A4:** Pre-push hooks via `.githooks/` are the right place for "block before PR exists" rules in TCS repos (consistent with tcs-git-helpers bundle layout)
- **A5:** Marcus is the only operator initially; multi-user collaboration patterns deferred

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hook becomes noisy (too many false positives) → user disables it | High | Med | Conservative trigger phrase set; soft "Consider" wording not interruption; easy `enabled: false` toggle in `.claude/settings.json` |
| Triage routing leads to over-mechanization (every minor friction gets a hook) | Med | Med | Q1 frequency filter; Memory is a valid recommendation (not "failure"); user-override always available |
| Skill duplicates `skill-author` / `hook-development` / `memory-add` capabilities instead of routing to them | Med | Low | Architecturally a router; documented contract; explicit hand-off lines in SKILL.md |
| Pre-push hook can be bypassed via `--no-verify` → critical rule slips through | Med | Med | Document the limitation; if rule is critical, recommend CI gate as backup (matrix already covers this) |
| Inline CI/pre-push scaffolding (M6) drifts from the proven templates → produces broken workflows | High | Low | Reference auto-bump-versions.yml as gold standard; require manual review of generated YAML before commit |
| Skill itself becomes the new "I forgot to invoke it" problem | Med | Low | Intercept hook is the safety net; if user forgets `/enforce-rule`, hook reminds on next "vergessen" phrase |

---

## Open Questions

### Resolved (PRD phase)

- [x] **Q1 — Slash command name:** `/enforce-rule` (Marcus 2026-05-21). Action-verb + object, consistent with tcs-helper naming.
- [x] **Q8 — Intercept hook default:** Opt-out (on by default). Nutzer kann via `.claude/settings.json` ausschalten. Forgetting to enable the hook would itself be the bug we're solving.
- [x] **Q9 — Inline scaffolding scope:** Hybrid — inline for the 2 established templates (CI auto-bump-style + pre-push docs-gate-style per Feature M6); hand-off via Feature M5 for all other mechanisms.
- [x] **Q12 — False-positive mitigation:** 1 trigger phrase suffices in v1. If noise becomes a problem, upgrade to 2-phrase threshold or smarter heuristic in v2.

### Defaulted in PRD (revisit in SDD if user disagrees)

- [x] **Q2 — Hook config filename:** `plugins/tcs-helper/hooks/rule-enforcer-intercept.json` (matches skill name; PRD-default).
- [x] **Q3 — Trigger-phrase config:** Externalized to `reference/trigger-phrases.md` (per Feature S1; user-extensible without reinstall).
- [x] **Q4 — Routing UI:** Sequential drill-down Q1→Q2→Q3→Q4 (per Feature M3; deterministic, traceable).
- [x] **Q6 — Memory fallback:** Skill invokes `Skill(tcs-helper:memory-add)` directly with strong-language template hint (per Feature M5; lower friction).

### Deferred to SDD

- [ ] **Q5 — Mechanism-matrix location:** `reference/mechanism-matrix.md` (token-cheap lazy load) vs inline in SKILL.md. **Decision criterion:** SKILL.md token budget after Workflow section is sized.
- [ ] **Q10 — Pre-push hook integration:** Produce snippet directly for repo's `.githooks/`, vs integrate with `tcs-git-helpers` bundle (which has version-controlled hook templates + bundle versioning gates). **Decision criterion:** does the rule-enforcer-produced hook need bundle-style upgrades?
- [ ] **Q11 — Override memory:** When user overrides recommended mechanism, remember it per-rule-class for next time, or always re-ask. **Decision criterion:** session-log persistence model in SDD.

---

## Supporting Research

### Competitive Analysis

No directly competing skills in the Claude Code / TCS ecosystem. Adjacent patterns:

- **`tdd-guardian` (tcs-workflow)** — discipline-enforcing skill in the same spirit (blocks implementer subagents from writing code without a test plan). Validates that "skill with discipline language" (mechanism option 4 in the matrix) is a proven TCS pattern.
- **`tcs-git-helpers` PreToolUse hooks** — proven precedent for hook-based enforcement (DESTRUCTIVE_CHECKOUT, FORCE_PUSH). Validates the Claude-hook mechanism.
- **PR #29 auto-bump CI** — proven precedent for CI auto-fix mechanism (built this session).
- **`authoring.md` PostToolUse reminder** — proven precedent for nudge-style hook (also from `tcs-helper`).

### User Research

- **Internal observation (this session, 2026-05-21):** 3 violation patterns of mechanizable rules in a single day, all by the same Claude agent operating in the same repo. Concrete evidence of the problem.
- **Memory bank analysis:** At least 4 entries in `~/.claude/projects/<repo>/memory/` are mechanization candidates (`feedback_no-manual-marketplace-sync`, `feedback_skill-author-on-creation`, `feedback_python_venv`, `feedback_bash_dir_persistence`).

### Market Data

N/A — internal TCS skill. ROI measured by reduction in reactive catch-up commits.
