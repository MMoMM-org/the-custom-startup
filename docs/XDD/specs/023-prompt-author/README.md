# Specification: 023-prompt-author

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-04 |
| **Current Phase** | PRD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-04 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | |
| solution.md | pending | |
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

## Context

A skill for writing, auditing and porting LLM prompts beyond Claude Code skills/agents: API system prompts, subagent briefs, CLAUDE.md/AGENTS.md, non-Claude target models. Candidate: extract the portable part of skill-author/agent-author failure catalogs as a single source of truth. Open tension: existing "strip rationale" and "authority language" rules may contradict current vendor guidance.

---
*This file is managed by the xdd-meta skill.*
