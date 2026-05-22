# Decisions — the-custom-startup
<!-- Architecture choices and rationale. Updated: 2026-05-22 -->
<!-- What goes here: why we chose X over Y, ADR links, significant tradeoff choices -->
<!-- Format: YYYY-MM-DD — Decision: [what] — Rationale: [why] -->

<!-- 2026-03-30 -->
- ADR-1: Removed merge_hooks.py — Claude Code natively loads hooks/hooks.json from enabled plugins with runtime ${CLAUDE_PLUGIN_ROOT} resolution. The merge script was unnecessary and introduced fragile absolute paths that broke on plugin version bumps.
- ADR-2: semantic_detector.py placed in scripts/lib/ — co-located with reflect_utils.py for consistent import pattern.
- ADR-3: Ported pattern detection from claude-reflect v3.1.0 — 13 CJK patterns, false positive filtering, confidence tuning. Adapted for Memory Bank routing instead of CLAUDE.md tiers.

<!-- 2026-04-25 -->
- ADR-4: Three-layer enforcement stack for skill auto-invocation — when Claude self-decides to write skill/agent files, skill descriptions alone don't reliably trigger the matching authoring skill (skill-author/agent-author), even with TCS skills installed. Stack: (1) PostToolUse hook on `**/skills/**` and `**/agents/**` paths injecting `additionalContext` system-reminders (deterministic, fires on every Write/Edit), (2) path-scoped Rule at `~/.claude/rules/authoring.md` (loads on file-read in matching dirs), (3) hardened skill descriptions with `Use PROACTIVELY`/`MUST BE USED` (auto-routing baseline). Each layer compensates for the others' failure modes. Apply when a TCS skill exists but Claude routinely bypasses it. Files: `~/.claude/hooks/authoring-reminder.sh`, `~/.claude/rules/authoring.md`, settings.json PostToolUse chain.

<!-- 2026-05-22 -->
- ADR-5: Two-stage review chain (spec-compliance → code-quality) is additive, not redundant — spec-013 implementation confirmed each reviewer catches issues the other misses. Spec-compliance found routing/labeling bugs (parenthetical drift T2.3, exact-match → prefix-match T2.4, missing test assertions T2.5). Code-quality found correctness/safety bugs (fence state T1.1, UnicodeDecodeError T1.1, sys.exit-inside-try T1.2, perf-test methodology T1.2, malformed-file assertion strength T2.2, new-branch push bypass T3.2). Keep the two-pass workflow in `tcs-workflow:implement` rather than collapsing into one; reviewers stay specialized and the second pass finds blind spots from the first.
