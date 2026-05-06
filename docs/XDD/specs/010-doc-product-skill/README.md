# Specification: 010-doc-product-skill

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-06 |
| **Current Phase** | SDD |
| **Last Updated** | 2026-05-06 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 22 Gherkin ACs; 0 markers; PRD reviewed and approved by Marcus |
| solution.md | in_progress | 7/7 ADRs confirmed; multi-page corpus design + generic personas resolved per Marcus's inline notes; awaiting final approval before PLAN |
| plan/ | pending | Awaiting PLAN authoring |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-06 | Spec scaffolded as 010-doc-product-skill | Brainstorm chose all-four-modes scope, all repo targets, lives in tcs-helper |
| 2026-05-06 | XDD workflow over ad-hoc build | Per `feedback_spec_first` memo: previous M3 work without spec caused rework |
| 2026-05-06 | Skill vs agent architecture: ONE skill with mode router | Heuristics from `docs/about/skill-and-agent-design.md` (now wired into decision-tree) confirm: progressive disclosure + user-invocable + slash-identity all hold; modes are sequential not parallel; reader-test isolation via `claude -p` (OS process) beats Agent-tool isolation. No separate front-door agent needed. |
| 2026-05-06 | Reader-test pass threshold: strict 100% on required questions | Marcus's choice in PRD clarification round: clean binary pass/fail beats configurable thresholds that erode over time |
| 2026-05-06 | No telemetry in v1 | Marcus's choice: KPIs verified from git artifacts and `docs/.reader-test/` reports; no event pipeline. v2 may revisit via `tcs-helper:doc-stats` |
| 2026-05-06 | extract scope: settings only (TS / JSON Schema / Pydantic) in v1 | Manifest-derived "Plugin Metadata" deferred to v2 to keep parser surface area focused |
| 2026-05-06 | User research scope: solo-author n=1 (Marcus) for v1 | Recruiting other TCS plugin authors deferred to v2; v1 dogfood on MiYo + TCS plugins owned by Marcus |
| 2026-05-06 | ADR-1..7 confirmed in SDD | Mode router (1), claude -p subprocess (2), stateless review (3), persona override = replace+opt-in extends (4), separate parser scripts with explicit dependency reporting (5), gap report inline only (6), single /doc-product slash with mode arg (7) |
| 2026-05-06 | Persona language: generic + LLM extracts specifics from doc | Default personas avoid project-type and OS hardcoding; reader resolves "Obsidian Plugin"/"macOS"/etc. from the doc itself; project override for edge cases |
| 2026-05-06 | Multi-page corpus per question | Each persona question declares `pages: [...]`; skill concatenates listed pages into a single corpus per `claude -p` call. Tests both navigation and content in one shot. Default for built-ins: README.md + topic page |

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
