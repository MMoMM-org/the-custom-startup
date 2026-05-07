# Changelog

## [3.4.2] - 2026-05-07

### Fixed

- **`doc-product` review mode: `claude -p --output-format json` wrapper unwrapping** — `scripts/reader-test.sh` ran `jq -e '.found'` against the outer wrapper object instead of the nested model payload. `claude -p --output-format json` returns `{"type":"result","subtype":"success","result":"<inner-JSON-as-string>",...}` where the model's `.found`/`.answer`/etc. live inside `.result` as a stringified payload. The pre-fix script saw `.found` missing on the wrapper and routed every tuple through the `unparseable_response` branch — a uniform failure across every `/doc-product review` run against real `claude`. Fix: unwrap via `try (.result | fromjson) catch empty`, validate the inner has `.found`, and emit the inner JSON. The existing test stubs were also updated to emit the realistic wrapper shape (they previously emitted flat JSON, which masked the bug). New scenario S8 covers the wrapper-without-`.result` subtype path (e.g. `error_max_turns`).

### Changed (breaking — slash command rename)

- **3.4.1 rename reverted; `docs` skill renamed to `claude-docs` instead** — the 3.4.1 rename targeted the wrong skill. The `claude-docs` name belongs on the Claude-Code-documentation fetcher (formerly `/docs`), not on the user-facing-doc-authoring skill. Two corrective renames:
  1. **`claude-docs` (the doc-authoring skill from 3.4.1) → `doc-product`** — restores the spec-010 name. The skill directory, `name:` frontmatter, active-skill announcement (`tcs-helper:claude-docs` → `tcs-helper:doc-product`), all `/claude-docs {plan|write|extract|review}` invocations across mode files, gap-report template, personas-default header, `lib-personas.sh` comment, and `write-mode.test.sh` assertions are reverted to `doc-product`.
  2. **`docs` (the doc fetcher) → `claude-docs`** — the slot is now occupied by the skill that actually fetches Claude Code documentation. Updates: skill directory (`plugins/tcs-helper/skills/docs/` → `plugins/tcs-helper/skills/claude-docs/`), `name:` frontmatter, `tcs-helper:docs` → `tcs-helper:claude-docs`, and the `/docs {topic} --refresh` example in the cache header → `/claude-docs {topic} --refresh`.

  The cache output directory `docs/ai/external/claude/` is **unchanged**. Spec ID `010-doc-product-skill` remains as a historical reference. Previous `/claude-docs {plan|write|extract|review}` invocation is gone — use `/doc-product {plan|write|extract|review}`. Previous `/docs` is gone — use `/claude-docs`.

## [3.4.1] - 2026-05-07

### Changed (breaking — slash command rename)

- **Skill renamed `doc-product` → `claude-docs`** — initial dogfood feedback from Marcus: the v1 slash command `/doc-product` was unintuitive in TCS / MiYo contexts. Renamed throughout: skill directory (`plugins/tcs-helper/skills/doc-product/` → `plugins/tcs-helper/skills/claude-docs/`), `name:` frontmatter field, active-skill announcement (`tcs-helper:doc-product` → `tcs-helper:claude-docs`), all `/doc-product {plan|write|extract|review}` slash command invocations across the four mode files, the gap-report template, the personas-default header, the `lib-personas.sh` reference, the `write-mode.test.sh` test assertions, and "the doc-product skill" prose in error messages and template intros. Spec ID `010-doc-product-skill` preserved as a historical reference (the spec name is stable; only the skill identity changed). The output directory `docs/` is **unchanged** — the skill still writes user-facing documentation to a target repo's `docs/` tree.

  All 369 test assertions across 13 test files green. The previous `/doc-product` invocation is no longer available; users invoke `/claude-docs {plan|write|extract|review}` instead.

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
