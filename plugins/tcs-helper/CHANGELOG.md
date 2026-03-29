# Changelog

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
