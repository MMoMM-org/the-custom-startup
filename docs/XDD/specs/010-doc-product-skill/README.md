# Specification: 010-doc-product-skill

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-06 |
| **Current Phase** | Initialization |
| **Last Updated** | 2026-05-06 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | Awaiting PRD authoring |
| solution.md | pending | Awaiting SDD authoring |
| plan/ | pending | Awaiting PLAN authoring |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-06 | Spec scaffolded as 010-doc-product-skill | Brainstorm chose all-four-modes scope, all repo targets, lives in tcs-helper |
| 2026-05-06 | XDD workflow over ad-hoc build | Per `feedback_spec_first` memo: previous M3 work without spec caused rework |
| 2026-05-06 | Skill vs agent architecture deferred to PRD/SDD | Open question raised in brainstorm: one skill with mode router vs agent + sibling skills — needs explicit analysis against `docs/about/skill-and-agent-design.md` |

## Context

**Goal:** Create a Claude Code skill `doc-product` that helps authors produce high-quality user-facing documentation (READMEs, configuration references, troubleshooting guides) for TCS plugins and other projects — not internal/code documentation.

**Four modes:**
- `plan` — analyse repo, propose `docs/` skeleton based on repo type
- `write` — draft a single doc page section-by-section with iterative refinement
- `extract` — generate Configuration Reference automatically from TS interfaces / JSON Schema / Pydantic models
- `review` — automated reader testing via `claude -p` headless invocations against persona-based questions

**Killer feature:** Reader-test automation. Spawn fresh Claude instances (no context bleed) with persona prompts, capture structured JSON output, aggregate into a gap report. This converts Anthropic's manual reader-test pattern into a CI-able quality gate.

**Reference inputs:**
- Anthropic's `doc-coauthoring` skill — three-stage workflow (context → structure → reader test)
- `miyo-kado` — reference for good `docs/` layout (separate `installation.md`, `configuration.md`, `troubleshooting.md`, etc.)
- `miyo-tomo` — anti-pattern benchmark (198-line single README)
- Perplexity proposal — four sub-agent decomposition (architect/writer/reviewer/extractor)
- `docs/about/skill-and-agent-design.md` — TCS heuristics for skill vs subagent vs slash command

**Constraints decided in brainstorm:**
- Scope: all four modes in v1 (plan/write/extract/review)
- Targets: Obsidian TS plugins, Python tools, TCS plugins themselves, repo-agnostic fallback
- Location: `plugins/tcs-helper/skills/doc-product/`

**Open architectural question (for PRD/SDD):**
- One skill with mode router (`SKILL.md` + `modes/{plan,write,extract,review}.md`) vs agent-with-skills vs four sibling skills
- Reader-test parallelism: `claude -p &` from Bash vs Agent-tool subagent dispatch
- Whether design heuristics should be woven back into `skill-author` conventions and root CLAUDE.md as a result of this spec

**Open questions for PRD:**
- Definition of done for a "passing" reader test (per-persona thresholds?)
- Persona override / customisation contract (per-project file?)
- Settings-source detection across the four target repo types
- Output of `plan` mode — does it create files or only propose?
- Integration with existing TCS skills (xdd, validate, skill-author)?

---
*This file is managed by the xdd-meta skill.*
