---
title: "memory-claude-md-optimize: CLAUDE.md Optimization and Memory Bank Migration"
status: COMPLETE
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
- [x] Context -> Problem -> Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

A single skill that transforms bloated, flat CLAUDE.md files into an optimized, layered Memory Bank structure — scoring quality, categorizing content, replacing eager @-imports with lazy descriptive references, and ensuring every line earns its place in the context window.

### Problem Statement

Claude Code users accumulate CLAUDE.md content over time — conventions, tool knowledge, domain rules, troubleshooting notes — all in flat files. This creates three problems:

1. **Context bloat**: Large CLAUDE.md files and @-imports consume context window budget even when most content is irrelevant to the current task.
2. **No structure**: Mixing general preferences, tool-specific knowledge, domain rules, and troubleshooting in one file makes it hard to maintain and impossible to lazy-load selectively.
3. **Wrong scope**: Content meant for one project ends up in global CLAUDE.md, or global conventions are duplicated across repos.

The TCS Memory Bank system (docs/ai/memory/ with typed category files) solves the structural problem, but users have no migration path from their existing flat CLAUDE.md files.

### Value Proposition

Instead of manually restructuring CLAUDE.md files (tedious, error-prone, often deferred indefinitely), users run one skill that:
- Audits and scores their CLAUDE.md quality across all scopes
- Proposes an optimized structure with content correctly categorized and scoped
- Replaces @-imports with descriptive references that let Claude decide when to load
- Generates everything in a temp directory for review before touching any originals
- Creates backups and offers archival of originals

The result is leaner CLAUDE.md files, properly categorized memory, and lower context usage.

## User Personas

### Primary Persona: TCS Power User

- **Demographics:** Developer using Claude Code daily with TCS plugins installed. Has accumulated CLAUDE.md content over weeks/months. Familiar with the Memory Bank concept but hasn't migrated.
- **Goals:** Reduce context window consumption. Get structured memory that loads only when relevant. Clean up accumulated cruft.
- **Pain Points:** CLAUDE.md files are large and growing. Context window fills faster than expected. @-imports load everything even when working in a narrow area. Knows Memory Bank exists but migration feels like too much manual work.

### Secondary Persona: New TCS Adopter

- **Demographics:** Developer who just installed TCS. May have existing CLAUDE.md files from previous Claude Code usage (pre-TCS). May not have Memory Bank structure yet.
- **Goals:** Get the Memory Bank set up with their existing knowledge preserved. Understand the g/p/r scope model.
- **Pain Points:** Doesn't know what goes where. Existing CLAUDE.md has useful content they don't want to lose. /setup creates empty structure but doesn't populate it from existing files.

## User Journey Maps

### Primary User Journey: Optimize Existing CLAUDE.md

1. **Awareness:** User notices context window filling quickly, or runs /context and sees memory files consuming significant tokens. Or they hear about Memory Bank and want to adopt it.
2. **Consideration:** User looks at their CLAUDE.md files and realizes restructuring manually would take significant effort. They see the skill exists.
3. **Adoption:** User runs `/memory-claude-md-optimize`. The skill asks which scopes to include and creates a proposal.
4. **Usage:** User reviews the temp directory structure, edits files if needed, triggers apply. Originals are backed up, new structure is in place.
5. **Retention:** User sees lower context usage. Runs the skill periodically (e.g., monthly) to re-optimize as content accumulates.

### Secondary User Journey: First-Time Memory Bank Setup

1. **Awareness:** User installs TCS with tcs-helper. Runs /setup which creates empty Memory Bank structure.
2. **Discovery:** User has existing CLAUDE.md content and wonders how to populate the Memory Bank from it.
3. **Migration:** User runs `/memory-claude-md-optimize`. The skill detects both existing CLAUDE.md content and empty Memory Bank files, proposes populating memory from CLAUDE.md content.
4. **Result:** Memory Bank is populated, CLAUDE.md is slimmed down to routing and essentials.

## Feature Requirements

### Must Have Features

#### Feature 1: Multi-Scope Discovery with Cascade

- **User Story:** As a TCS user, I want the skill to discover all my CLAUDE.md files across scopes so that nothing is missed during optimization.
- **Acceptance Criteria:**
  - [x] Given the user invokes the skill, When it starts, Then it asks which starting scope to include: global (includes g+p+r), project (includes p+r), or repo (r only)
  - [x] Given scope "global" is selected, When discovery runs, Then it cascades: finds ~/.claude/CLAUDE.md, follows @-imports to discover project-level files, then discovers repo-level files
  - [x] Given scope "project" is selected, When discovery runs, Then it cascades: finds project-level CLAUDE.md (from @-import references), then discovers repo-level files
  - [x] Given scope "repo" is selected, When discovery runs, Then it finds CLAUDE.md at repo root, all subdirectory CLAUDE.md files (src/CLAUDE.md, test/CLAUDE.md, docs/CLAUDE.md, etc.), AND any existing Memory Bank files (docs/ai/memory/*.md)
  - [x] Given any scope is selected, When discovery runs, Then existing Memory Bank files are always included in the analysis (they are part of the repo scope)
  - [x] Given an @-import is encountered at any scope, When it is followed, Then the referenced file and any further @-imports it contains are recursively discovered
  - [x] Given discovery completes, When results are shown, Then the user sees a list of all discovered files with their scope, line count, and path

#### Feature 2: Quality Scoring

- **User Story:** As a TCS user, I want each CLAUDE.md file scored for quality so I know what needs the most attention.
- **Acceptance Criteria:**
  - [x] Given a discovered CLAUDE.md file, When it is analyzed, Then it receives scores on 6 criteria: commands/workflows (20pts), architecture clarity (20pts), non-obvious patterns (15pts), conciseness (15pts), currency (15pts), actionability (15pts)
  - [x] Given scoring completes, When the report is shown, Then each file has a total score (0-100) and grade (A/B/C/D/F)
  - [x] Given a file scores below 50 (grade D/F), When the report is shown, Then specific issues are highlighted with concrete improvement suggestions
  - [x] Given files over 150 lines, When the report is shown, Then a warning is displayed recommending optimization

#### Feature 3: Content Categorization

- **User Story:** As a TCS user, I want each piece of content categorized into Memory Bank categories so I can see where everything should go.
- **Acceptance Criteria:**
  - [x] Given a CLAUDE.md file is analyzed, When content is extracted, Then each bullet point or section is assigned to exactly one Memory Bank category: general, tools, domain, decisions, context, or troubleshooting
  - [x] Given content is categorized, When results are shown, Then each item is also flagged as "probably generic" (applies broadly) or "probably specific" (project/repo-specific)
  - [x] Given "probably generic" content found in a repo-level file, When results are shown, Then it suggests moving to global or project scope
  - [x] Given "probably specific" content found in global CLAUDE.md, When results are shown, Then it suggests moving to the relevant repo scope

#### Feature 4: @-Import Replacement

- **User Story:** As a TCS user, I want @-imports replaced with descriptive references so that Claude loads files on demand rather than eagerly loading everything.
- **Acceptance Criteria:**
  - [x] Given a CLAUDE.md contains `@path/to/file.md`, When optimization runs, Then the @-import is replaced with a descriptive reference explaining what the file contains and when to consult it
  - [x] Given an @-import points to a file, When the import is followed, Then the referenced file's content is analyzed and categorized alongside the importing file
  - [x] Given a descriptive reference is generated, When shown in the proposal, Then it follows the pattern: "For [topic], see [path] — [brief description of what it contains and when to use it]" — this tells Claude WHAT the file is about so it can decide whether to load it, rather than eagerly loading everything via @
  - [x] Given a CLAUDE.md currently has `@path/to/file.md` and nothing else, When replaced, Then the descriptive reference explains the file's purpose so that Claude knows when to Read it (e.g., "Memory routing rules and category definitions are documented in docs/ai/memory/memory.md — consult when routing learnings to the correct scope and category")

#### Feature 5: Proposal Generation

- **User Story:** As a TCS user, I want to review the proposed changes before anything is modified so I can adjust the optimization.
- **Acceptance Criteria:**
  - [x] Given analysis completes, When the proposal is generated, Then a temp directory is created at the user's chosen location (default: `<repo>/claude-md-optimization/`)
  - [x] Given the temp directory, When populated, Then it mirrors the full g/p/r structure: `global/`, `project/`, `repo/` subdirectories each containing proposed CLAUDE.md and memory files
  - [x] Given the temp directory, When populated, Then it contains an OPTIMIZATION-REPORT.md explaining: what was moved, why (category + scope reasoning), quality scores, and a before/after summary
  - [x] Given the proposal is presented, When the user is prompted, Then they can: edit files in the temp directory, then come back and trigger apply

#### Feature 6: Apply with Backups

- **User Story:** As a TCS user, I want originals backed up before any changes are applied so I can roll back if needed.
- **Acceptance Criteria:**
  - [x] Given the user triggers apply, When backup runs, Then each original file is copied with a `.backup-YYYYMMDD-HHMMSS` suffix in the same directory
  - [x] Given backups are created, When new files are placed, Then the new CLAUDE.md versions replace the originals
  - [x] Given Memory Bank structure doesn't exist, When apply runs, Then it creates `docs/ai/memory/` with category files (reusing setup skill's template approach)
  - [x] Given all files are placed, When apply completes, Then a summary shows which files were backed up, created, and modified

#### Feature 7: Archive or Delete Temp Directory

- **User Story:** As a TCS user, I want to choose what happens to the temp directory after applying so I can keep a record or clean up.
- **Acceptance Criteria:**
  - [x] Given apply completes, When the user is prompted, Then they can choose: delete temp directory, archive it, or keep it as-is
  - [x] Given the user chooses archive, When prompted for location, Then the default is `<repo>/claude-md-optimization/` (same as proposal dir, kept as archive) and the user can override
  - [x] Given archive is chosen, When files are moved, Then backup copies of originals are moved alongside the proposal files with `-archived` appended to filenames

#### Feature 8: Before/After Verification

- **User Story:** As a TCS user, I want to see the impact of the optimization in terms of context usage so I can verify the improvement.
- **Acceptance Criteria:**
  - [x] Given the skill starts, When discovery and scoring complete, Then a "BEFORE" snapshot is captured: per-file line counts, total token estimate, and a note to run `/context` and `/memory` for live baseline
  - [x] Given apply completes, When the summary is shown, Then an "AFTER" section shows: new per-file line counts, estimated token savings, and instructions to reload the session (start a new conversation) and run `/context` and `/memory` to see the actual difference
  - [x] Given the OPTIMIZATION-REPORT.md, When it is generated, Then it includes both the BEFORE and AFTER snapshots plus instructions for manual verification

### Should Have Features

#### Feature 9: Dry Run Mode

- **User Story:** As a TCS user, I want to see what changes would be made without generating files so I can quickly assess whether optimization is needed.
- **Acceptance Criteria:**
  - [x] Given the user passes `--dry-run`, When the skill runs, Then it performs discovery, scoring, and categorization but only prints the report without creating any files

#### Feature 10: Incremental Re-Optimization (delegates to memory-cleanup)

- **User Story:** As a TCS user running the skill again after initial migration, I want it to detect existing Memory Bank structure and handle it appropriately.
- **Acceptance Criteria:**
  - [x] Given Memory Bank structure already exists at `docs/ai/memory/`, When the skill runs, Then it analyzes both CLAUDE.md files AND existing memory files as part of its discovery — existing memory content is treated as already-categorized and new CLAUDE.md content is proposed as additions/moves
  - [x] Given existing memory files contain stale or duplicate content, When the skill detects this, Then it recommends running `/memory-cleanup` for maintenance (deduplication, archiving resolved items, pruning stale context) rather than handling cleanup itself — memory-cleanup is the dedicated tool for ongoing maintenance
  - [x] Given the distinction: memory-claude-md-optimize handles structural migration and quality optimization of CLAUDE.md files; memory-cleanup handles ongoing maintenance of Memory Bank content that is already in place

### Could Have Features

#### Feature 11: AGENTS.md Context Reduction

- **User Story:** As a TCS user, I want the optimization to address AGENTS.md context duplication so that the same content isn't loaded twice (once via CLAUDE.md, once via AGENTS.md).
- **Acceptance Criteria:**
  - [x] Given AGENTS.md exists and contains content that overlaps with CLAUDE.md, When the optimization runs, Then it flags the duplication and the context cost
  - [x] Given duplication is found, When the user is prompted, Then they can choose: (a) make AGENTS.md a thin pointer that references CLAUDE.md for details, (b) rename AGENTS.md to remove it from auto-loading (Claude Code auto-loads AGENTS.md but has no setting to exclude it), or (c) keep both as-is
  - [x] Given the user chooses to make AGENTS.md a pointer, When apply runs, Then AGENTS.md is rewritten to contain only a brief project description and a reference to CLAUDE.md for full context
  - [x] Given the user chooses to rename, When prompted, Then the default new name is `FOR-AGENTS.md` (not auto-loaded) and the user can override

### Won't Have (This Phase)

- **Automated periodic re-optimization** — Users run the skill manually when needed
- **Cross-repo analysis** — Each repo is optimized independently; no cross-repo content deduplication
- **Undo/rollback command** — Backups exist for manual rollback; no automated undo
- **Ongoing memory file maintenance** — Handled by `/memory-cleanup` (archive resolved issues, prune stale context, consolidate duplicates within memory files)

## Detailed Feature Specifications

### Feature: Content Categorization (most complex)

**Description:** The skill reads each line/section of a CLAUDE.md file, classifies it into a Memory Bank category, and determines whether it belongs at the current scope or should be moved.

**User Flow:**
1. User invokes `/memory-claude-md-optimize`
2. Skill asks which scopes to include
3. Skill discovers and reads all CLAUDE.md files
4. For each file, content is parsed into discrete items (bullet points, sections, code blocks)
5. Each item is classified by category (general/tools/domain/decisions/context/troubleshooting) and scope (generic/specific)
6. Items flagged as "wrong scope" are proposed for relocation
7. Results are presented in the OPTIMIZATION-REPORT.md

**Business Rules:**
- Rule 1: Content mentioning specific tools, APIs, CLI commands, or integrations maps to "tools" category
- Rule 2: Content with "always", "never", "prefer" patterns maps to "general" category (conventions)
- Rule 3: Content about data models, business logic, or domain concepts maps to "domain" category
- Rule 4: Content about architecture choices, trade-offs, or "why we chose X" maps to "decisions" category
- Rule 5: Content about current goals, active work, or sprint context maps to "context" category
- Rule 6: Content about known bugs, workarounds, or "if X fails, do Y" maps to "troubleshooting" category
- Rule 7: Content mentioning model names (gpt-*, claude-*), global tools, or universal patterns is "probably generic"
- Rule 8: Content mentioning specific file paths, project names, or repo-specific tools is "probably specific"

**Edge Cases:**
- Scenario 1: Content that fits multiple categories -> Use primary intent; if ambiguous, prefer the more specific category
- Scenario 2: Entire CLAUDE.md is a single paragraph with no bullets -> Parse into sentences, categorize each
- Scenario 3: CLAUDE.md contains code blocks (e.g., shell snippets) -> Keep code blocks with their surrounding context, categorize the block as a unit
- Scenario 4: @-import chain (A imports B which imports C) -> Follow the full chain, analyze all files, report the chain in the OPTIMIZATION-REPORT
- Scenario 5: Empty CLAUDE.md file -> Report as "empty", suggest populating from Memory Bank or removing

## Success Metrics

### Key Performance Indicators

- **Adoption:** 80% of tcs-helper users run the skill at least once within first month
- **Quality Improvement:** Average CLAUDE.md quality score increases by 20+ points after optimization
- **Context Reduction:** Token usage for memory files decreases by 30%+ after optimization (measured via /context)
- **Retention:** 50% of users who run it once run it again within 3 months

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| skill_invoked | scopes_selected, dry_run, file_count | Usage patterns |
| optimization_proposed | files_analyzed, items_categorized, items_moved, quality_delta | Measure effectiveness |
| optimization_applied | files_modified, backups_created, memory_files_created | Track actual changes |
| optimization_archived | archive_location | Archive behavior |

---

## Constraints and Assumptions

### Constraints
- Must run on bash 3.2 (macOS default) — no associative arrays
- Must work with Python 3.x for any helper scripts (using repo venv if needed)
- Must not modify files without explicit user confirmation
- CLAUDE.md files may be arbitrarily large (some users have 500+ lines)
- @-import paths may be absolute or relative, may use ~ expansion

### Assumptions
- Users have tcs-helper installed (skill lives in that plugin)
- Memory Bank structure may or may not already exist (skill handles both cases)
- Users understand the g/p/r scope model (or will learn from the OPTIMIZATION-REPORT)
- Claude Code's file discovery rules won't change drastically (CLAUDE.md loaded from parent directories)

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Miscategorization places content in wrong memory file | Medium | Medium | User review step before apply; easy to move content manually |
| @-import replacement changes behavior (Claude loads less context) | High | Low | Descriptive references guide Claude to load when needed; backups allow rollback |
| Large CLAUDE.md files cause slow analysis | Low | Low | Progressive output; dry-run mode for quick assessment |
| User doesn't review temp directory carefully | Medium | Medium | OPTIMIZATION-REPORT highlights key changes; diff view shows before/after |

## Open Questions

- (none — all clarified during brainstorming)

---

## Supporting Research

### Competitive Analysis

**Anthropic claude-md-management plugin:** Provides quality scoring (6 criteria, A-F grades) and session learning capture. Focuses on audit and incremental improvement, not structural migration. Our skill extends this with Memory Bank migration, scope analysis, and @-import optimization.

**centminmod/my-claude-code-setup:** Demonstrates per-concern memory files (activeContext, patterns, decisions, troubleshooting). Our Memory Bank categories are directly inspired by this approach.

**John Conneely memory system:** Establishes the ~200-line MEMORY.md index pattern and the principle that routing rules belong in CLAUDE.md, not in memory files. Our optimization preserves this: CLAUDE.md keeps routing + essentials, memory files hold the categorized content.

### User Research

Based on TCS development experience:
- Global CLAUDE.md files commonly reach 150-300 lines
- @-imports are the primary cause of context bloat (loading entire project trees)
- Users consistently defer CLAUDE.md cleanup because it's tedious
- The memory-add and memory-promote skills work well for incremental additions but don't address the initial bulk migration

### Market Data

Claude Code's context window (200K tokens) makes context efficiency critical. Memory files consuming 5-10% of context budget is common. Optimization can reclaim 30-50% of that by moving content to lazy-loaded category files.
