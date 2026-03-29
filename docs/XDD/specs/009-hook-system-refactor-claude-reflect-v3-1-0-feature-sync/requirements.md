---
title: "Hook System Refactor + claude-reflect v3.1.0 Feature Sync"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

TCS-helper's learning capture and memory management system operates reliably across all installation scopes, detects user corrections with high precision, and routes learnings to the right Memory Bank category — automatically and without manual hook management.

### Problem Statement

The tcs-helper plugin has five concrete problems with its hook installation system and significant feature gaps compared to its upstream (claude-reflect v3.1.0):

**Hook System (measured):**
1. **Double-fire risk**: Hooks exist in both the plugin's native `hooks/hooks.json` AND merged into `settings.json`, likely causing each hook to execute twice per event.
2. **Fragile paths**: `merge_hooks.py` resolves `${CLAUDE_PLUGIN_ROOT}` to absolute paths at install time. Plugin version bumps or cache changes silently break all hooks.
3. **Scope mismatch**: The `/setup` skill hardcodes `--scope r` (repo), ignoring the user's installation choice (global). Users who chose global installation get hooks in the wrong location.
4. **Duplicate accumulation**: Re-running setup after a path change adds duplicate hook entries (comparison is by exact resolved path string).
5. **Unnecessary complexity**: `merge_hooks.py` (172 LOC) exists solely to merge hooks into `settings.json` — but Claude Code natively loads `hooks/hooks.json` from enabled plugins, making the entire script redundant.

**Feature Gaps (measured against claude-reflect v3.1.0):**
- Pattern detection: 4 categories / ~12 patterns (original: 8 categories / 50+ patterns including CJK)
- False positive filtering: none (original: non-correction phrases, structural filters, length-based confidence)
- Semantic AI validation: none (original: `claude -p` powered intent classification)
- Tool error capture: none (original: PostToolUse error extraction with categorization)
- Cross-category deduplication: none (original: cross-tier dedup + contradiction detection)
- Test coverage: 31 tests (original: 160 tests); `detect_learning()` has zero direct unit tests

**Consequences of not solving:** Hooks may silently break on plugin updates. False positives pollute the learning queue. Duplicate learnings accumulate across Memory Bank categories. Users cannot trust the system to work unattended.

### Value Proposition

Compared to the current state, this delivers:
- **Zero-maintenance hooks**: Native plugin hook loading eliminates merge scripts, path fragility, and scope confusion.
- **Higher-precision learning capture**: Fewer false positives and better multilingual support mean less noise in the memory system.
- **Automated quality control**: Cross-category dedup and optional semantic validation prevent memory pollution without manual review.
- **Confidence through testing**: 80+ tests provide a safety net for ongoing development.

Compared to using claude-reflect directly: TCS adapts the original's detection and validation capabilities to the structured Memory Bank architecture (6 categorized files) instead of flat CLAUDE.md files (9 tiers), which provides better organization and routing for long-term knowledge management.

## User Personas

### Primary Persona: Plugin User (Marcus)
- **Demographics:** Senior developer, daily Claude Code user, manages multiple repos with TCS plugins installed globally
- **Goals:** Learning capture works silently and correctly. Memory Bank stays organized without manual curation. Plugin updates don't break hooks.
- **Pain Points:** Hooks break silently after plugin updates (swallowed exceptions). False positives in queue require manual filtering during `/memory-add`. No visibility into whether hooks are actually firing or double-firing.

### Secondary Persona: Plugin Maintainer
- **Demographics:** Developer contributing to the tcs-helper plugin codebase
- **Goals:** Confident refactoring with good test coverage. Clear separation between hook scripts and skill workflows. Simple onboarding for new contributors.
- **Pain Points:** `detect_learning()` has no direct tests — changes risk silent regressions. `merge_hooks.py` is complex code solving a problem that doesn't need solving. Low test coverage (31 tests) makes refactoring risky.

## User Journey Maps

### Primary User Journey: Learning Capture (Plugin User)

1. **Awareness:** User types a correction ("no, don't use that approach") or explicit instruction ("remember: always use venv") during a Claude Code session.
2. **Consideration:** The hook system must correctly identify this as a learning (not a false positive) and classify it with appropriate confidence.
3. **Adoption:** The learning appears in the queue silently. At session start, user sees "N pending learnings" and runs `/memory-add`.
4. **Usage:** `/memory-add` presents classified learnings routed to the correct Memory Bank category. User reviews, approves, or skips.
5. **Retention:** Over time, the Memory Bank accumulates accurate, deduplicated learnings. Claude Code sessions improve because context is richer.

### Secondary User Journey: Plugin Maintenance

1. **Awareness:** Maintainer needs to add new detection patterns or fix a bug in learning capture.
2. **Consideration:** Reads existing tests to understand current behavior. Runs test suite as safety net.
3. **Adoption:** Writes new tests for the change (TDD). Implements the change. All tests pass.
4. **Usage:** Bumps plugin version. Pushes update. No manual hook re-installation needed by users.
5. **Retention:** Test suite catches regressions. Native hooks survive version bumps automatically.

## Feature Requirements

### Must Have Features

#### Feature M1: Eliminate merge_hooks.py — Use Native Plugin Hooks
- **User Story:** As a plugin user, I want hooks to load automatically from the plugin so that I never need to run a merge script or worry about stale paths after updates.
- **Acceptance Criteria:**
  - [ ] Given the tcs-helper plugin is enabled in `settings.json` `enabledPlugins`, When Claude Code starts a session, Then all 4 hooks from `hooks/hooks.json` fire correctly using runtime-resolved `${CLAUDE_PLUGIN_ROOT}`
  - [ ] Given `merge_hooks.py` is deleted, When the full test suite runs, Then all remaining tests pass (the 11 merge_hooks tests are also deleted)
  - [ ] Given hooks are loaded natively, When the plugin version is bumped, Then hooks continue to work without re-running setup
  - [ ] Given the setup skill, When Step 5 (hook installation) executes, Then it no longer calls `merge_hooks.py`

#### Feature M2: Fix Hook Script Input Contract (cwd from JSON)
- **User Story:** As a hook script, I want to read the project path from the JSON stdin `cwd` field so that I follow Claude Code's hook contract instead of relying on shell variable expansion.
- **Acceptance Criteria:**
  - [ ] Given a hook receives JSON stdin with a `cwd` field, When the script needs the project path, Then it reads `cwd` from the parsed JSON
  - [ ] Given a hook receives JSON stdin without a `cwd` field, When the script needs the project path, Then it falls back to `os.getcwd()`
  - [ ] Given the `hooks.json` template, When commands are defined, Then no command passes `"${PWD}"` as a CLI argument
  - [ ] Given the `TCS_QUEUE_OVERRIDE` env var is set, When tests run, Then queue path override still works correctly

#### Feature M3: Expanded Pattern Detection
- **User Story:** As a plugin user, I want corrections in any language and format to be detected accurately so that the system captures real learnings and ignores noise.
- **Acceptance Criteria:**
  - [ ] Given a prompt containing a CJK correction (e.g., Japanese "違う", Chinese "不对"), When `detect_learning()` runs, Then it returns a match with appropriate confidence
  - [ ] Given a prompt containing a false positive phrase (e.g., "no problem", "don't worry about it"), When `detect_learning()` runs, Then it returns no match
  - [ ] Given a prompt with a correction keyword inside a code block, When `detect_learning()` runs, Then it ignores code-block content
  - [ ] Given a short ambiguous prompt (e.g., "no"), When `detect_learning()` runs, Then confidence is below the capture threshold
  - [ ] Given multiple patterns match in one prompt, When confidence is calculated, Then it increases (multi-pattern boost)

#### Feature M4: Test Suite Expansion to 80+ Tests
- **User Story:** As a plugin maintainer, I want comprehensive test coverage so that I can refactor with confidence and catch regressions early.
- **Acceptance Criteria:**
  - [ ] Given the test suite, When `pytest tests/tcs-helper/` runs, Then at least 80 tests pass
  - [ ] Given `detect_learning()`, When tested directly, Then at least 30 tests cover all pattern categories, false positives, CJK, edge cases, and confidence thresholds
  - [ ] Given each hook script, When tested, Then error paths, malformed JSON, and missing fields are covered
  - [ ] Given queue I/O operations, When tested, Then roundtrip, corruption recovery, and concurrent access are covered
  - [ ] Given no test depends on `~/.claude/`, When tests run on CI, Then all tests use `tmp_path` or mocks

### Should Have Features

#### Feature S1: Tool Error Extraction
- **User Story:** As a plugin user, I want recurring tool errors captured automatically so that common issues are routed to `troubleshooting.md` without manual tracking.
- **Acceptance Criteria:**
  - [ ] Given a PostToolUse event where the tool output contains an error, When the hook processes it, Then the error is queued with `item_type: 'tool_error'`
  - [ ] Given a transient error (network timeout), When compared to a persistent error (wrong path), Then only persistent errors (repeated 2+ times in session) are captured
  - [ ] Given `/memory-add` processes tool errors, When routing, Then they are directed to `troubleshooting.md`
  - [ ] Given the same error pattern occurs multiple times, When queued, Then only one entry exists (deduplicated by error pattern)

#### Feature S2: Cross-Category Deduplication
- **User Story:** As a plugin user, I want the system to prevent duplicate learnings across Memory Bank categories so that the same knowledge doesn't appear in both `tools.md` and `general.md`.
- **Acceptance Criteria:**
  - [ ] Given a new learning matches an existing entry in any of the 6 category files, When `/memory-add` processes it, Then it flags the duplicate and asks the user to skip or replace
  - [ ] Given an exact duplicate (identical text), When detected, Then it is silently skipped
  - [ ] Given a near-duplicate (same meaning, different wording), When detected, Then user is shown both entries and asked to decide
  - [ ] Given dedup runs during `/memory-add`, When the queue has 20 items, Then dedup completes within 5 seconds (no AI calls for basic dedup)

### Could Have Features

#### Feature C1: Semantic AI Validation
- **User Story:** As a plugin user, I want low-confidence detections validated by Claude so that borderline cases are correctly classified.
- **Acceptance Criteria:**
  - [ ] Given a learning with confidence below 0.7, When semantic validation is enabled, Then `claude -p` is called to confirm intent
  - [ ] Given `claude` CLI is unavailable, When validation would run, Then it falls back to regex-only with no error
  - [ ] Given validation is disabled via `TCS_SEMANTIC_VALIDATION=false`, When a learning is detected, Then no AI call is made
  - [ ] Given semantic validation runs, When it takes longer than 5 seconds, Then it times out and keeps the original confidence

#### Feature C2: Contradiction Detection
- **User Story:** As a plugin user, I want conflicting learnings flagged so that my Memory Bank doesn't contain contradictory instructions.
- **Acceptance Criteria:**
  - [ ] Given a new learning "always use tabs" and an existing entry "always use spaces", When `/memory-add` processes, Then the contradiction is flagged with both entries shown
  - [ ] Given a time-based contradiction (old vs new), When user is asked, Then the newer entry is recommended as the default resolution
  - [ ] Given contradiction detection uses keyword matching, When no AI is available, Then basic keyword overlap still catches obvious conflicts

### Won't Have (This Phase)

- **Full /reflect port**: The 750-line, 10-phase `/reflect` command stays in the original. Our `/memory-add` covers the core workflow; we enhance it incrementally.
- **9-tier routing**: We do not adopt the original's `find_claude_files()` or `suggest_claude_file()`. Memory Bank's 6 categories + global scope is our architecture.
- **/reflect-skills (skill discovery from sessions)**: Valuable but out of scope. Our `/memory-promote` covers a subset of this.
- **Tool rejection extraction**: Lower priority than tool error extraction. Can be added later.
- **compare_detection.py diagnostic**: Developer-only tool, not needed for MVP.
- **Marketplace distribution**: No changes to plugin marketplace packaging.

## Detailed Feature Specifications

### Feature: M1 — Eliminate merge_hooks.py

**Description:** Remove the `merge_hooks.py` script and all related code. Claude Code natively loads `hooks/hooks.json` from enabled plugins, resolving `${CLAUDE_PLUGIN_ROOT}` at runtime. The merge step is unnecessary and introduces fragility.

**User Flow:**
1. User installs/enables tcs-helper plugin (existing flow, no change)
2. Claude Code reads `hooks/hooks.json` from the plugin directory at session start
3. Claude Code resolves `${CLAUDE_PLUGIN_ROOT}` to the actual plugin path at runtime
4. Hooks fire correctly — no setup step needed for hooks

**Business Rules:**
- Rule 1: When `/setup` runs, it skips hook installation entirely (hooks are native).
- Rule 2: The `merge_hooks.py` script and its test file are deleted.
- Rule 3: The setup skill Step 5 is replaced with a note that hooks are natively loaded.

**Edge Cases:**
- Manually cleaned up: stale merged hooks in settings.json have already been handled outside this spec

### Feature: M3 — Expanded Pattern Detection

**Description:** Extend `detect_learning()` with CJK support, false positive filtering, non-correction phrase exclusion, and context-aware confidence scoring.

**User Flow:**
1. User types a correction in any supported language
2. Hook fires `capture_learning.py`
3. `detect_learning()` matches against expanded pattern set
4. False positive filter removes non-corrections
5. Confidence is calculated with length/context adjustments
6. If above threshold, learning is queued

**Business Rules:**
- Rule 1: When a prompt matches a false positive pattern (question starting with "no", "don't worry", "no problem"), it is excluded regardless of correction pattern match.
- Rule 2: When a prompt contains code blocks (``` delimited), correction keywords inside code blocks are ignored.
- Rule 3: When multiple patterns match, confidence increases by 0.05 per additional match (capped at 0.95).
- Rule 4: When a prompt is shorter than 5 characters, it is never captured (too ambiguous).
- Rule 5: When a CJK pattern matches, confidence starts at 0.60-0.90 depending on pattern strength.

**Edge Cases:**
- Mixed-language prompt (English + Japanese) → both pattern sets apply, highest confidence wins
- "Actually, that's exactly right" → "actually" matches correction but context is positive → false positive filter catches this
- Pasted error message containing "no" → structural filter (long text with code-like patterns) reduces confidence
- `remember:` prefix always captures at 0.90 confidence regardless of other filters

## Success Metrics

### Key Performance Indicators

- **Adoption:** 100% of repos with tcs-helper enabled use native hooks (no merged hooks in settings.json) within 2 weeks of update
- **Engagement:** Learning queue captures at least 1 valid learning per 10 correction-containing prompts (10% recall floor)
- **Quality:** False positive rate below 15% (measured: learnings rejected during `/memory-add` / total learnings queued)
- **Business Impact:** Test suite at 80+ tests with all passing; zero hook-related bug reports after migration

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `learning_captured` | type, confidence, patterns, tcs_category | Measure detection precision |
| `learning_rejected` | reason (false_positive, duplicate, user_skip) | Track false positive rate |
| `hook_migration` | hooks_removed, hooks_kept, scope | Track migration rollout |
| `dedup_detected` | type (exact, near, contradiction), categories | Measure memory hygiene |

Note: "Tracking" means queue metadata and `/memory-add` output — not analytics infrastructure. These are observable via queue file inspection and skill output.

---

## Constraints and Assumptions

### Constraints
- **Python 3.8+ compatibility**: Hook scripts must work on Python 3.8 (some CI environments) through 3.14 (current dev)
- **Hook execution budget**: Hook scripts must complete within Claude Code's implicit timeout (~10 seconds). No AI calls in hooks.
- **No pip dependencies**: Hook scripts use stdlib only. Semantic detection (C1) may call `claude` CLI but not import external packages.
- **macOS primary**: Development and testing on macOS. CI on Linux. No Windows requirement.
- **venv for testing**: All pytest runs use the repo's `venv/` — never system Python.

### Assumptions
- Claude Code natively loads `hooks/hooks.json` from enabled plugins and resolves `${CLAUDE_PLUGIN_ROOT}` at runtime. (Needs verification in Phase 1 of implementation.)
- The `claude` CLI is available in environments where semantic validation (C1) is enabled.
- Queue file format (`learnings-queue.json`) is stable and won't change upstream.
- Users running `/setup` after the update will get the migration automatically.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claude Code does NOT auto-register plugin hooks | High | Low | Verify in Phase 1. Fallback: keep merge_hooks.py but fix resolution + scope bugs. |
| CJK patterns increase false positives | Medium | Medium | Start with high-confidence patterns only (0.80+). Add lower-confidence patterns after validation with real usage data. |
| Semantic validation (C1) adds latency to /memory-add | Low | Medium | Make it opt-in. Default off. Only validate items below confidence threshold. |

## Open Questions

- [x] Does Claude Code natively load hooks/hooks.json from enabled plugins? (Assumption: yes, based on plugin-dev documentation. Must verify in Phase 1.)
- [ ] What is the exact hook execution timeout in Claude Code? (Affects whether tool error extraction can run in PostToolUse hook.)
- [ ] Should the version bump be 2.2.0 (incremental) or 3.0.0 (breaking)? Depends on whether merge_hooks.py removal is considered a breaking change.

---

## Supporting Research

### Competitive Analysis

**claude-reflect v3.1.0** (upstream, BayramAnnakov/claude-reflect):
- 160 tests, 3-OS CI, Python 3.8+3.11
- Semantic AI detection via `claude -p`
- 50+ regex patterns including 13 CJK patterns
- 10-phase /reflect workflow with cross-tier routing
- Tool error and rejection extraction
- Routes to CLAUDE.md (9 tiers, flat hierarchy)

**TCS tcs-helper v2.1.1** (our fork):
- 31 tests, no CI for scripts
- Regex-only detection, 12 patterns, no CJK
- `/memory-add` skill (simpler, 6-step)
- Routes to Memory Bank (6 categories, structured)
- Additional: `/memory-sync`, `/memory-cleanup`, `/memory-promote`, `/setup`

### User Research

Based on direct experience (Marcus as primary user):
- Hooks broke silently after plugin cache changes — discovered only when learnings stopped appearing
- False positives in queue ("no problem" detected as correction) waste time during `/memory-add`
- No confidence in hook system reliability due to path fragility and lack of tests

### Market Data

Claude Code plugin ecosystem is early-stage. claude-reflect is one of the most mature learning-capture plugins with 160 tests and multi-platform CI. TCS extends the concept with Memory Bank architecture but lags on detection quality and test coverage.
