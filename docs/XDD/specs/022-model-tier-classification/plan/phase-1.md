---
title: "Phase 1: Spike and metadata foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Spike and metadata foundation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-6]` — spike first; amended after it: the served model is read from the subagent transcript
- `[ref: SDD/Risks and Technical Debt; Known Technical Issues]` — what the spike must answer
- `[ref: SDD/Architecture Decisions; ADR-7]` and `[ref: SDD/Interface Specifications; Internal API Changes]` — `read_status_row`, `KNOWN_MODEL_TIERS`, `model_tier`
- `[ref: SDD/Constraints; CON-3]` — every existing spec must still read cleanly

**Key Decisions**:
- The spike's answer changes only how substitutions are recorded (ADR-6), never whether a run continues.
- The reader stays fail open: absent, placeholder or unknown → `""`, exit 0.

**Dependencies**:
- None. Phase 2 and 3 depend on this phase.

---

## Tasks

Establishes what Claude Code lets the orchestrator observe about a subagent's model, and makes the model tier a readable spec field.

- [x] **T1.1 Spike: observe the model a subagent actually ran on** `[activity: research]`

  1. Prime: Read the unconfirmed items `[ref: SDD/Risks and Technical Debt; Known Technical Issues]` and the error table `[ref: SDD/Runtime View; Error Handling]`.
  2. Test: Define the questions before probing — (a) does the Agent tool result, or the subagent transcript under `~/.claude/projects/<repo>/…/subagents/`, carry the model that served it; (b) what the orchestrator sees when `model: fable` is dispatched on an account without consent or entitlement, and when the consent prompt is dismissed (error vs. silent substitution); (c) whether `effort: max` is accepted on `opus` in Claude Code 2.1.309; (d) what the orchestrator sees when a `fable` subagent is dispatched in a Remote Control session — the Remote Control docs state the Fable usage-credits consent prompt is shown only in the local terminal, never forwarded, and an unanswered prompt ends the turn without sending the request — and whether that matches the dismissed-consent row (planned → opus@max, escalated → BLOCKED).
  3. Implement: Dispatch minimal subagents (`haiku`; `opus` with `effort: max`; `fable` only with the maintainer at the local terminal to answer any consent prompt; for (d), once more with the session driven from a Remote Control device and nobody at the terminal) and record observations in `docs/XDD/specs/022-model-tier-classification/research/spike-model-observation.md`.
  4. Validate: Each question has an answer with evidence (quoted output or transcript excerpt) or is marked "not observable".
  5. Success: Findings recorded in `research/`; where they contradict the SDD Error Handling rows, the SDD is amended and a Decisions Log row records the amendment `[ref: SDD/ADR-6]`. (The README-limit branch was not triggered: the served model is observable.)

- [x] **T1.2 `spec.py` reports the model tier** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `read_decomposition_tier` and `read_spec` in `plugins/tcs-workflow/skills/xdd-meta/spec.py` `[ref: SDD/Interface Specifications; Internal API Changes]`; read `tests/test_spec_tier.py`, whose `_make_spec` takes only `tier=` and must gain `model_tier=` `[ref: SDD/Risks and Technical Debt; Implementation Gotchas]`.
  2. Test: Extend `tests/test_spec_tier.py` — `Model tier | Hard` emits `model_tier = "hard"` (case-insensitive for all three values); no row emits `""` with exit 0; `Bananas` and the `{{MODEL_TIER}}` placeholder emit `""`; `model_tier` is printed directly after `decomposition_tier`; `decomposition_tier` output is unchanged for every case; `test_every_existing_spec_reads_cleanly` still passes.
  3. Implement: Add `read_status_row(spec_dir, label, known)`; make `read_decomposition_tier` delegate to it; add `KNOWN_MODEL_TIERS = ("routine", "hard", "frontier")`, `read_model_tier`, and the `model_tier` print.
  4. Validate: `rm -rf tests/__pycache__ && .venv/bin/python -m pytest -q tests/test_spec_tier.py tests/test_dispatch_detection.py` passes; full suite passes.
  5. Success: `[ref: PRD/AC-2.2]`; `[ref: PRD/AC-2.3]`; `[ref: SDD/Constraints; CON-3]`

- [x] **T1.3 Spec template and xdd-meta carry the model tier** `[activity: backend-api]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd-meta/template.md` (the `Decomposition tier` row and its legend) and `SKILL.md` (the `SpecStatus` and `State` interfaces; the "both places" rule) `[ref: SDD/Interface Specifications; Data Storage Changes]`. Keep the literal that `tests/test_spec_tier.py:225` checks intact.
  2. Test: Add tests — the template carries `| **Model tier** | {{MODEL_TIER}} |` and a legend line naming the three values; a scaffolded spec reads `model_tier = ""`; xdd-meta SKILL declares `model_tier` in its interface and requires both Status row and Decisions Log for a model-tier decision.
  3. Implement: Add the row and legend to `template.md`; add the model tier to xdd-meta's `SpecStatus` interface and to its "write a tier decision to both places" rule.
  4. Validate: Tests pass; skill-author audit of `xdd-meta/SKILL.md` clean.
  5. Success: `[ref: PRD/AC-2.1]`; `[ref: SDD/Architecture Decisions; ADR-7]`

- [x] **T1.4 Phase Validation** `[activity: validate]`

  - Gate task (no TDD cycle of its own). Run the full Python suite. Confirm `spec.py --read` on every spec under `docs/XDD/specs/` prints `model_tier = ""` and an unchanged `decomposition_tier`. T1.1's findings are in `research/`, and any SDD amendment they caused is logged.
