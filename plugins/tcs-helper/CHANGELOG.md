# Changelog

## [3.4.1] - 2026-05-07

### Fixed

- **`doc-product` output directory renamed `docs/` → `claude-docs/`** — initial dogfood revealed that writing into `docs/` collides with target repos' existing `docs/` trees (used for ADRs, XDD specs, and internal dev notes in TCS / MiYo repos). The skill now writes user-facing docs into `claude-docs/` instead. All four modes (plan, write, extract, review), templates (4 skeletons + configuration + gap-report), reference/conventions.md, SKILL.md description, the `run-review.sh` page-scope scanner, and the test suite (13 files, 369 assertions, all green) updated. Repo-internal `docs/` references that are not the skill's output (e.g. `docs/about/skill-and-agent-design.md`) are preserved. See `docs/XDD/specs/010-doc-product-skill/plan/phase-5.md` Deviation 1 for full record.

## [3.4.0] - 2026-05-07

### Added

- **`doc-product` skill — Phases 1–4 functional** — Mode-router skill (`/doc-product {plan|write|extract|review}`) for authoring and reviewing user-facing documentation. Implements all four modes per spec-010: `plan` (repo analysis + `docs/` skeleton), `write` (section-by-section drafting via discover → document → review), `extract` (settings → configuration page from TS / JSON Schema / Pydantic sources), `review` (persona-driven reader testing via `claude -p` subprocess). Includes built-in persona library, four skeleton templates, configuration + gap-report templates, and Bash parsers per source type. Phase 5 (dogfood) outstanding.

## [3.3.0] - 2026-05-06

### Added

- **`doc-product` skill scaffold (Phase 1 of spec-010)** — Skill skeleton with mode-router SKILL.md and TODO stubs for the four mode files. Routes `/doc-product {plan|write|extract|review}` via case-insensitive leading-token match with AskUserQuestion fallback. Mode bodies progressively disclosed.

## [3.2.0] - 2026-04-25

### Changed

- **`agent-author` conventions overhauled** — re-grounded in `rsmdt/the-startup` `docs/PRINCIPLES.md` (April 2026) and the actual ICMDA layout used by all `tcs-team` agents. Replaces the earlier Perplexity-based PICS draft. Updates: conventions.md (ICMDA + frontmatter schema + tool/model/color tables), description-patterns.md (first-50-char rule, third-person, `<example>` blocks), output-formats.md (typed-table per archetype), anti-patterns.md (PRINCIPLES § 4.5 list), canonical-agent.md (full ICMDA reviewer example), audit-output.md (ICMDA-aware audit checklist), SKILL.md (Mechanism Check as Step 1).
- **`skill-author` Mechanism Check** — symmetric Step 1 added before mode selection. Walks the load-bearing question from PRINCIPLES § 5.2 ("should output remain visible in parent conversation?"). Recommends handoff to `agent-author` if a subagent is the right mechanism instead of a skill.

### Added

- **Shared `decision-tree.md`** — identical content in both `agent-author/reference/` and `skill-author/reference/`. Sourced from PRINCIPLES § 5.2 sequential decision tree + worked examples + common confusions. Sync header in both files.
- **`agent-author/evals/pressure-scenarios.md`** — three persisted pressure-test scenarios (lazy spec, wrong mechanism, lazy audit) with expected behaviors, failure modes to watch, and 2026-04-25 baseline PASS verdicts. Per PRINCIPLES § 2.7 evaluation-first authoring; re-run after any non-trivial skill change.

## [3.1.0] - 2026-04-25

### Added

- **`agent-author` skill** — Authoring assistant for Claude Code subagents (mirrors `skill-author` for skills). Supports Create / Audit / Modernize modes. Enforces TCS opinions: `sonnet` as default model (rejects `inherit`), action-oriented descriptions with `Use PROACTIVELY`/`MUST BE USED` triggers, minimum tool sets per archetype, and fixed output formats. Includes reference docs (conventions, description-patterns, decision-tree, output-formats, anti-patterns) and annotated examples.

## [3.0.3] - 2026-04-11

### Fixed

- **`post_commit_reminder.py` JSON schema** — The PostToolUse(Bash) hook was emitting `{"hookSpecificOutput": "text"}` (string), which Claude Code rejects with "JSON validation failed". Fixed to emit the required object shape `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "text"}}`. Triggered after every `git commit` (non-amend). Tests updated accordingly (17/17 pass).

## [3.0.0] - 2026-03-30

### Breaking Changes

- **Removed `merge_hooks.py`** — Claude Code natively loads `hooks/hooks.json` from enabled plugins. The merge script and its 13 tests are deleted. The `/setup` skill no longer calls it.

### Added

- **CJK correction patterns** — 13 patterns ported from claude-reflect v3.1.0 (Japanese 8, Chinese 3, Korean 2)
- **False positive filtering** — Non-correction phrases ("no problem", "don't worry") are filtered out
- **Code block exclusion** — Correction keywords inside ``` code blocks are ignored
- **Confidence tuning** — Context-aware scoring: short text boost, long text penalty, multi-pattern boost (cap 0.95)
- **Tool error detection** — PostToolUse hook captures persistent tool errors (seen 2+ times), categorized by type (module_not_found, connection_refused, etc.)
- **Cross-category deduplication** — `find_duplicates()` checks all 6 Memory Bank files using Jaccard similarity
- **Semantic AI validation** (optional) — `semantic_detector.py` validates low-confidence items via `claude -p`. Disabled by default; enable by ensuring `TCS_SEMANTIC_VALIDATION` is not `false`.
- **Contradiction detection** — Flags conflicting entries during `/memory-add`, with keyword-based fallback when claude CLI unavailable
- **Test suite expansion** — 31 → 160 tests (5x increase)
- **conftest.py** — Shared pytest fixtures for all test files

### Changed

- **Hook input contract** — Scripts now read `cwd` from JSON stdin instead of `${PWD}` CLI argument. Fallback to `os.getcwd()` when `cwd` absent.
- **hooks.json** — Removed `"${PWD}"` from all hook commands
- **detect_learning()** — Refactored into 8-step pipeline with CJK-aware length calculation
- **`/memory-add` skill** — Added tool error auto-routing to troubleshooting.md, cross-category dedup, optional semantic validation, contradiction detection

## [2.1.1] - Previous

- Initial TCS fork of claude-reflect with Memory Bank integration
