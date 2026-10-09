# Decisions — the-custom-startup
<!-- Architecture choices and rationale. Updated: 2026-10-09 -->
<!-- What goes here: why we chose X over Y, ADR links, significant tradeoff choices -->
<!-- Format: ADR-N: [decision]. → [rationale]. No spec refs — git blame has the origin. -->

<!-- 2026-03-30 -->
- ADR-1: Removed `merge_hooks.py`. → Claude Code natively loads `hooks/hooks.json` from enabled plugins with runtime `${CLAUDE_PLUGIN_ROOT}` resolution; the script added fragile absolute paths that broke on version bumps.
- ADR-2: `semantic_detector.py` lives in `scripts/lib/`. → Co-located with `reflect_utils.py` for a consistent import pattern.
- ADR-3: Ported pattern detection from claude-reflect v3.1.0 — 13 CJK patterns, false-positive filtering, confidence tuning. → Adapted for Memory Bank routing instead of CLAUDE.md tiers.

<!-- 2026-04-25 -->
- ADR-4: Three-layer enforcement for skill auto-invocation, because descriptions alone do not reliably trigger the matching authoring skill. → (1) PostToolUse hook on `**/skills/**` and `**/agents/**` injecting `additionalContext`, (2) path-scoped rule at `~/.claude/rules/authoring.md`, (3) `MUST BE USED` in descriptions. Each layer covers the others' failure modes.

<!-- 2026-05-22 -->
- ADR-5: Keep the two-stage review chain (spec-compliance → code-quality) rather than collapsing it. → The passes are additive: spec-compliance catches routing and labeling bugs, code-quality catches correctness and safety bugs. Reviewers stay specialized and the second pass finds the first's blind spots.

<!-- 2026-10-07 -->
- ADR-6 (Marcus): A plugin major/minor release is requested by writing exactly the next-major/minor heading in its CHANGELOG; auto-bump sets plugin.json to it. → CI could only patch-bump, so a breaking release could not ship.

<!-- 2026-10-09 -->
- ADR-7 (Marcus): Auto-bump derives what is owed from main's history (one bump per commit touching a plugin since its last version raise), not from the push range. → A lost push event otherwise drops its bump for good and reddens every later run.
