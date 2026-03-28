---
title: "TCS v2 Documentation Rewrite"
status: complete
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

A documentation set that accurately represents TCS v2's 4-plugin architecture, XDD workflow, and 20 skills — structured so a new user can install, understand, and use TCS without any prior knowledge of v1.

### Problem Statement

The current docs are factually broken for v2:
- All plugin references use the old name `tcs-start` (renamed to `tcs-workflow`)
- Docs describe "3 plugins" — v2 ships 4 (`tcs-patterns` is undocumented entirely)
- Skill count is listed as "10" — v2 has 20 skills in `tcs-workflow`
- The XDD workflow (6 new skills) is not documented anywhere
- Install commands reference `start@the-custom-startup` (wrong namespace)
- Flat file structure with duplicate content (`PHILOSOPHY.md` vs `the-custom-philosophy.md`) creates confusion
- `docs/concept/` and `docs/concept/v2/` contain internal design notes mixed with user-facing docs

A new user following the current docs will get wrong install commands and an incomplete picture of what TCS does.

### Value Proposition

Accurate, structured v2 docs give new users:
1. Working install commands on first attempt
2. A clear mental model of the 4-plugin system and when to use each
3. A complete XDD workflow reference they can follow from day one
4. The tcs-patterns catalogue so they can discover and select relevant skills
5. Transparent attribution so the open-source lineage is clear

---

## User Personas

### Primary Persona: New Developer

- **Role:** Software developer who has never used TCS; found it through the marketplace or a recommendation
- **Technical level:** Comfortable with CLI tools, Claude Code user, not familiar with TCS conventions
- **Goals:** Install TCS, understand what it does, run the first workflow (specify → implement) on a real project
- **Pain Points:** Wrong install commands cause immediate failure; undocumented plugins mean missed capability; flat doc structure makes it hard to find the right starting point

### Secondary Persona: v1 Upgrader

- **Role:** Existing TCS user migrating from `tcs-start` to `tcs-workflow`
- **Goals:** Find what changed, update their saved commands and aliases, discover new capabilities (XDD, tcs-patterns)
- **Pain Points:** Commands that used to work (`tcs-start:...`) now fail; no migration notes; can't tell if their workflow is still supported

---

## User Journey Maps

### Primary User Journey: First Install and First Feature

1. **Discovery:** Developer finds TCS via marketplace listing or a colleague's recommendation; reads README.md to understand what it is
2. **Installation:** Follows `getting-started/installation.md`; runs install script; confirms plugins are active
3. **Orientation:** Reads `getting-started/workflow.md`; understands the BUILD loop (specify → validate → implement → review)
4. **First feature:** Runs `/specify` on a real task; follows the XDD workflow through PRD → SDD → PLAN; reads `reference/xdd.md` when they hit an unfamiliar step
5. **Exploration:** Discovers `tcs-patterns` in `guides/tcs-patterns.md`; installs skills relevant to their stack
6. **Retention:** Bookmarks `reference/skills.md` and `reference/agents.md` as ongoing references

### Secondary User Journey: v1 Upgrader

1. **Awareness:** Runs a familiar command (e.g., `/output-style tcs-start:The Startup`); it fails with an unknown plugin error
2. **Investigation:** Reads README.md or `getting-started/installation.md`; sees `tcs-workflow` is the new name
3. **Re-orientation:** Checks `reference/skills.md` to confirm their workflows are still supported under new names
4. **Exploration:** Reads `about/sources.md` to understand what changed and what's new in v2

---

## Feature Requirements

### Must Have Features

#### Feature 1: Accurate v2 Plugin References

- **User Story:** As a new user, I want all install commands and plugin names to be correct so that I can install TCS without failure
- **Acceptance Criteria:**
  - [ ] Given a user follows `getting-started/installation.md`, When they run the install commands, Then all 4 plugins install successfully with no name errors
  - [ ] Given a user reads `reference/plugins.md`, When they look up any plugin, Then the install command shown matches the actual marketplace identifier
  - [ ] Given a user reads any doc file, When they see a skill invocation like `/output-style X:Y`, Then the namespace X matches an installed plugin name

#### Feature 2: tcs-patterns Plugin Documented

- **User Story:** As a new user, I want to understand what tcs-patterns offers so that I can decide which pattern skills are relevant to my stack
- **Acceptance Criteria:**
  - [ ] Given a user reads `guides/tcs-patterns.md`, When they look for their technology stack (Node.js, Python, Go, React, etc.), Then they find at least one relevant skill with a description of what it does and when to use it
  - [ ] Given a user reads `reference/plugins.md`, When they read the tcs-patterns section, Then they see the full list of 17 skills and the install command
  - [ ] Given a user reads `getting-started/installation.md`, When they reach the optional plugins section, Then tcs-patterns is listed as an optional install with a link to `guides/tcs-patterns.md`

#### Feature 3: XDD Workflow Documented

- **User Story:** As a new user, I want to understand the XDD workflow so that I can use the 6 XDD skills (xdd, xdd-meta, xdd-prd, xdd-sdd, xdd-plan, xdd-tdd) effectively
- **Acceptance Criteria:**
  - [ ] Given a user reads `reference/xdd.md`, When they need to understand what xdd-prd/xdd-sdd/xdd-plan each produce, Then each skill's purpose, inputs, and outputs are clearly described
  - [ ] Given a user reads `getting-started/workflow.md`, When they look at the BUILD loop, Then the XDD path is presented as the primary way to specify a feature
  - [ ] Given a user reads `reference/skills.md`, When they scan the skill list, Then all 20 tcs-workflow skills are listed with descriptions

#### Feature 4: Restructured Information Architecture

- **User Story:** As a new user, I want a logical docs structure so that I know where to look for what I need
- **Acceptance Criteria:**
  - [ ] Given a user lands on `docs/`, When they navigate to get started, Then `getting-started/index.md` is the clear entry point
  - [ ] Given a user needs a reference, When they look in `reference/`, Then they find skills, agents, plugins, and output-styles — not installation steps or guides
  - [ ] Given a user needs a deep guide, When they look in `guides/`, Then they find tcs-patterns, multi-ai-workflow, and statusline setup
  - [ ] Given a user reads `about/sources.md`, When they want to understand TCS origins, Then attribution to rsmdt/the-startup and citypaul skills is explicit and accurate

#### Feature 5: Attribution and Sources Document

- **User Story:** As a contributor or curious user, I want to understand where TCS content originates so that proper credit is maintained
- **Acceptance Criteria:**
  - [ ] Given a user reads `about/sources.md`, When they look for the base fork attribution, Then they find a link to rsmdt/the-startup with description of what was derived
  - [ ] Given a user reads `about/sources.md`, When they look for skill origins, Then citypaul-derived skills (10) are listed separately from TCS-native skills (5) and integration skills (2)
  - [ ] Given a user reads `README.md`, When they look for the fork attribution, Then the "What's different" section still appears with a link to sources.md

### Should Have Features

- **Quick-start walkthrough** (`getting-started/quick-start.md`): Step-by-step first-project guide: constitution → specify → implement. Gives new users a concrete success experience in under 30 minutes.
- **Merged statusline guide** (`guides/statusline.md`): Consolidates `statusline.md`, `statusline-starship.md`, and `statusline-starship-reddit.md` into a single doc. Reduces navigation confusion.
- **CHANGELOG.md update**: Add a v2.0 entry to `CHANGELOG.md` (create if absent) documenting the plugin rename (`tcs-start` → `tcs-workflow`), new tcs-patterns plugin, XDD workflow addition, and doc restructure. Gives upgraders a single place to see what changed.

### Could Have Features

- Comparison table between The Startup and The ScaleUp output styles with example outputs
- "Which skills do I need?" decision tree in `guides/tcs-patterns.md`

### Won't Have (This Phase)

- Auto-generated API reference from skill frontmatter
- Video tutorials or interactive examples
- Versioned docs (v1 / v2 toggle)
- Migration guide from tcs-start to tcs-workflow (v1 upgraders are secondary audience; git history serves this need)

---

## Detailed Feature Specifications

### Feature: Restructured Information Architecture

**Description:** The flat `docs/` directory is replaced by a 4-level hierarchy: `getting-started/`, `reference/`, `guides/`, `about/`. All 14 new/rewritten files live in these directories. Six existing files are deleted; two directories (`docs/concept/`, `docs/concept/v2/`) are removed after their content is promoted.

**File inventory by destination:**

| Destination | Work type | Source |
|-------------|-----------|--------|
| `getting-started/index.md` | New | — |
| `getting-started/installation.md` | Rewrite | `docs/installation.md` |
| `getting-started/quick-start.md` | New | — |
| `getting-started/workflow.md` | Rewrite | `docs/workflow.md` |
| `reference/plugins.md` | Rewrite | `docs/plugins.md` |
| `reference/skills.md` | Rewrite | `docs/skills.md` |
| `reference/agents.md` | Minor update | `docs/agents.md` |
| `reference/output-styles.md` | Minor update | `docs/output-styles.md` |
| `reference/xdd.md` | New | concept/v2/ insights |
| `guides/tcs-patterns.md` | New | skill SKILL.md files |
| `guides/multi-ai-workflow.md` | Move | `docs/multi-ai-workflow.md` |
| `guides/statusline.md` | Merge | 3 statusline files → 1 |
| `about/the-custom-philosophy.md` | Update | `docs/the-custom-philosophy.md` + concept/ |
| `about/sources.md` | New | — |
| `about/principles.md` | Move | `docs/PRINCIPLES.md` |
| `README.md` | Rewrite | `README.md` |

**Files to delete:**
`docs/index.md`, `docs/concepts.md`, `docs/PHILOSOPHY.md`, `docs/the-custom-philosophy.md` (moved), `docs/statusline-starship.md`, `docs/statusline-starship-reddit.md`, `docs/concept/` (directory), `docs/concept/v2/` (directory)

**Business Rules:**
- All internal cross-links in docs must be updated to reflect the new paths
- README.md must link to `docs/getting-started/index.md` as the entry point
- `about/sources.md` must explicitly list: rsmdt/the-startup (base fork), citypaul-derived skills (10), TCS-native skills (5), integration skills (2)
- `the-custom-philosophy.md` replaces `PHILOSOPHY.md` as the canonical philosophy document
- All skill invocation examples must use `tcs-workflow:` namespace (not `tcs-start:`)

**Edge Cases:**
- If a user has bookmarked `docs/workflow.md` — the old path will 404. Acceptable: clean break for v2, no redirects needed for a local docs folder.
- `docs/XDD/`, `docs/ai/`, `docs/templates/` are NOT touched — they are spec artifacts, not user-facing docs.

---

## Success Metrics

### Key Performance Indicators

- **Accuracy:** 0 broken install commands across all doc files
- **Completeness:** 0 pages referencing `tcs-start`, `start@the-custom-startup`, or "3 plugins"
- **Coverage:** All 20 tcs-workflow skills listed in `reference/skills.md`; all 17 tcs-patterns skills listed in `guides/tcs-patterns.md`
- **Attribution:** `about/sources.md` exists with correct counts and links

### Tracking Requirements

| Check | What to verify | Purpose |
|-------|---------------|---------|
| Plugin name scan | `grep -r "tcs-start" docs/` returns 0 results | Confirms no stale plugin references |
| Skill count | `reference/skills.md` lists exactly 20 tcs-workflow skills | Confirms completeness |
| Install command test | Each plugin install command matches marketplace identifier | Confirms accuracy |
| Attribution check | `about/sources.md` names rsmdt, citypaul, TCS-native counts | Confirms attribution intact |
| Dead link check | All `docs/` internal links resolve to existing files | Confirms IA integrity |

---

## Constraints and Assumptions

### Constraints

- `docs/XDD/`, `docs/ai/`, `docs/templates/` are out of scope — spec artifacts, not user docs
- The `README.md` at the repo root must retain the ASCII art header and the "What's different" fork attribution section — these are identity markers
- No versioned docs (this is a single-version project)

### Assumptions

- New users are installing TCS from scratch — no migration path needed in this phase
- The install script (`install.sh`) is already updated for v2 plugin names — docs just need to match
- The XDD skill frontmatter and SKILL.md files are the source of truth for `reference/xdd.md` content
- `docs/concept/` content is safe to delete once extracted — it's working notes, not referenced externally

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Cross-links between docs break after restructure | Medium | High | Validate all internal links after writing; update README links explicitly |
| concept/ deletion removes something still needed | Low | Low | Read all concept/ files before deleting; promote any valuable content first |
| tcs-patterns skill count or names drift during writing | Low | Medium | Read actual SKILL.md files when writing guides/tcs-patterns.md, not from memory |
| XDD skill descriptions become outdated | Low | Low | Write reference/xdd.md from the actual SKILL.md files in tcs-workflow/skills/ |

---

## Open Questions

- [x] Should `getting-started/quick-start.md` use a real example project or a generic placeholder? **Decision: generic placeholder** — avoids scope creep and keeps the walkthrough universally applicable.
- [x] Does `about/sources.md` need to list individual skill names or just categories? **Decision: categories with counts** — e.g., "10 citypaul-derived skills", "5 TCS-native skills", "2 integration skills" — with individual names only where attribution is relevant to a specific skill.
