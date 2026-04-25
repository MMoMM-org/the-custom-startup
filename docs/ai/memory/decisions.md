# Decisions — the-custom-startup
<!-- Architecture choices and rationale. Updated: YYYY-MM-DD -->
<!-- What goes here: why we chose X over Y, ADR links, significant tradeoff choices -->
<!-- Format: YYYY-MM-DD — Decision: [what] — Rationale: [why] -->

<!-- 2026-03-30 -->
- ADR-1: Removed merge_hooks.py — Claude Code natively loads hooks/hooks.json from enabled plugins with runtime ${CLAUDE_PLUGIN_ROOT} resolution. The merge script was unnecessary and introduced fragile absolute paths that broke on plugin version bumps.
- ADR-2: semantic_detector.py placed in scripts/lib/ — co-located with reflect_utils.py for consistent import pattern.
- ADR-3: Ported pattern detection from claude-reflect v3.1.0 — 13 CJK patterns, false positive filtering, confidence tuning. Adapted for Memory Bank routing instead of CLAUDE.md tiers.

<!-- 2026-04-25 -->
- ADR-4: Three-layer enforcement stack for skill auto-invocation — when Claude self-decides to write skill/agent files, skill descriptions alone don't reliably trigger the matching authoring skill (skill-author/agent-author), even with TCS skills installed. Stack: (1) PostToolUse hook on `**/skills/**` and `**/agents/**` paths injecting `additionalContext` system-reminders (deterministic, fires on every Write/Edit), (2) path-scoped Rule at `~/.claude/rules/authoring.md` (loads on file-read in matching dirs), (3) hardened skill descriptions with `Use PROACTIVELY`/`MUST BE USED` (auto-routing baseline). Each layer compensates for the others' failure modes. Apply when a TCS skill exists but Claude routinely bypasses it. Files: `~/.claude/hooks/authoring-reminder.sh`, `~/.claude/rules/authoring.md`, settings.json PostToolUse chain.
