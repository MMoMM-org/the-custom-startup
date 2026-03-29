# Decisions — the-custom-startup
<!-- Architecture choices and rationale. Updated: YYYY-MM-DD -->
<!-- What goes here: why we chose X over Y, ADR links, significant tradeoff choices -->
<!-- Format: YYYY-MM-DD — Decision: [what] — Rationale: [why] -->

<!-- 2026-03-30 -->
- ADR-1: Removed merge_hooks.py — Claude Code natively loads hooks/hooks.json from enabled plugins with runtime ${CLAUDE_PLUGIN_ROOT} resolution. The merge script was unnecessary and introduced fragile absolute paths that broke on plugin version bumps.
- ADR-2: semantic_detector.py placed in scripts/lib/ — co-located with reflect_utils.py for consistent import pattern.
- ADR-3: Ported pattern detection from claude-reflect v3.1.0 — 13 CJK patterns, false positive filtering, confidence tuning. Adapted for Memory Bank routing instead of CLAUDE.md tiers.
