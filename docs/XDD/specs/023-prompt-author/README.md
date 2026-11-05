# Specification: 023-prompt-author

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-04 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-05 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | approved 2026-11-05 |
| solution.md | in_progress | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-04 | Spec created; external research (outside TCS) required before PRD | User request: prompt quality failures recur outside skills/agents; research must not be limited to TCS sources |
| 2026-11-04 | Baseline compares Opus- vs Sonnet-authored prompts | User asked whether Sonnet writes better prompts; no evidence either way, so measure it |
| 2026-11-04 | Start with PRD; research mode Agent Team, run as 3 resumable background researchers (inventory, prompt corpus, lint/eval mechanics) | User chose Agent Team; team tools are unavailable in this session, so researchers stay addressable via SendMessage instead |
| 2026-11-04 | External research saved to research-external.md | Feeds PRD; key finding: "strip rationale" and authority-language rules contradict current Anthropic/OpenAI/Google guidance |
| 2026-11-04 | Internal, technical and corpus research saved (research-internal.md, research-technical.md, research-corpus.md) | Three resumable researchers; orchestrator spot-checked key claims |
| 2026-11-04 | Scope: prompt-author + shared failure catalog with corrected rules; skill-author, agent-author, memory-claude-md-optimize migrate to it. `MUST BE USED` in descriptions excluded | User choice. ADR-4 depends on description authority language; changing it needs a measured follow-up and a superseding ADR |
| 2026-11-04 | Run the full Opus-vs-Sonnet experiment (5 tasks) BEFORE the PRD | User choice over the recommended small pilot; PRD targets measured differences. Est. $100-400, 1-2 days, via `claude -p` on subscription |
| 2026-11-04 | Non-Claude targets: per-vendor porting profiles + lint; live eval only on local Ollama (reachable at host.docker.internal:11434); otherwise emit eval kit labelled "not evaluated on target". GEMINI_API_KEY must not be used | User: the Gemini key has little budget behind it; Ollama is available locally |
| 2026-11-04 | Defects found by corpus research filed as separate GitHub issues, fixed outside spec 023 | User choice; they double as audit test cases for the skill |
| 2026-11-04 | Defects filed as #250-#253, no project board | User: only org board is MiYo Tomo/Hashi, not TCS |
| 2026-11-04 | Experiment plan approved (experiment/PLAN.md): pilot first, $400 hard ceiling, judge validated on ~20 user labels per semantic criterion | User approval |
| 2026-11-04 | T4 status quo = no CLAUDE.md (empty Q.md), not an experimenter-written baseline | A hand-written baseline would be a third, unblinded author |
| 2026-11-04 | Pilot done (45 runs, $1.45); five grader defects fixed and regraded; criteria frozen (PLAN.md § Pilot outcome) | The pilot exists to catch instrument errors before the full run |
| 2026-11-04 | Judge labels collected from a stratified sample of the full run, not from the pilot | The pilot yields only 9 outputs per semantic criterion, all judged PASS; ~20 labels need the full run's spread |
| 2026-11-04 | Gravity agent-prompt article added to research-external.md; its agent rules (stopping conditions, behaviour when unclear, goal over script, refusal with alternative) go into the shared catalog, reaching agent-author via the migration | User-supplied source; agent-author has none of these rules today; a direct edit would bypass the catalog that is meant to be the single source |
| 2026-11-05 | Full experiment run (385 runs, $7.97): no measurable Opus-vs-Sonnet difference; explicit authoring beats the repo's subagent briefs (T2/T3 Q 0%); see experiment/results.md | Answers the user's question 'would Sonnet write better prompts' — no; the gap is in the missing contracts, not the author model |
| 2026-11-05 | Judge validation from 28 user labels: T5 no_implementation_detail validated (9/10); T1 no_unsupported_fact invalid (3/10, all 7 judge FAILs overturned) and dropped from the T1 headline; T3 planted_bug_identified supported but not validated (4/4 decided, 4 UNSURE) | Below the 85% threshold a criterion is reported unvalidated; the T1 judge demands per-claim hedges the rubric does not ask for. Dropping it changes no conclusion (T1 O 98% / S 100% / Q 95%). Lesson for the catalog: an LLM judge passing hand-built controls is not calibrated |
| 2026-11-05 | PRD scope: lint = low-false-alarm checks as errors, rest warn/review; eval = kit + local runs (Claude CLI, Ollama), other vendors kit only; rule corrections applied in migration, measured per skill, reverted on regression | User choices; matches measured FP rates (research-technical.md) and the cheap local harness ($7.97 for 385 runs) |
| 2026-11-05 | PRD approved; phase → SDD. CLAUDE.md stays owned by memory-claude-md-optimize (catalog consumer); prompt-author owns AGENTS.md/GEMINI.md and all non-skill, non-agent prompt kinds | User approval; avoids a second CLAUDE.md owner (skill-evaluate U1 overlap) |
| 2026-11-05 | SDD ADR-1–4 confirmed: catalog inside prompt-author skill with ../ links; IDs + fingerprint test; two eval routes (plugin eval at two git states + standalone runner) with one kit format; eval case first, then each rule correction | User choices; model-ladder precedent shows cross-skill links survive install (whole plugin dir is installed) |

## Context

A skill for writing, auditing and porting LLM prompts beyond Claude Code skills/agents: API system prompts, subagent briefs, CLAUDE.md/AGENTS.md, non-Claude target models. Candidate: extract the portable part of skill-author/agent-author failure catalogs as a single source of truth. Open tension: existing "strip rationale" and "authority language" rules may contradict current vendor guidance.

---
*This file is managed by the xdd-meta skill.*
