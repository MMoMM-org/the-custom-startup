# TCS v2 — Sources & Attribution

This document lists all external sources analyzed and drawn from in the TCS v2 design.
Maintained for reference and attribution when publishing changes.

---

## claude-reflect (marketplace plugin)

**Plugin:** `claude-reflect` (installed via Claude Code marketplace)
**Repository:** https://github.com/claude-reflect-marketplace/claude-reflect
**Version used:** 3.0.1

**What we use:**
- `/reflect` — two-stage self-learning: hooks capture corrections → user processes queue → routed to correct CLAUDE.md destination. Foundation for `tcs-helper:memory` capture layer.
- `/reflect-skills` — AI-powered session analysis that identifies repeating patterns and generates skill files. **This is the promotion mechanism** for Conneely's staging→promotion→pointer lifecycle. Used as the organic growth engine for `tcs-patterns`.
- Learning destinations model (global CLAUDE.md / project CLAUDE.md / CLAUDE.local.md / rules/*.md / auto-memory) — directly informs TCS g/p/r routing table.
- `/miyo-reflect` extension pattern — proof that reflect can be extended with repo-specific routing. TCS follows the same pattern with `/tcs-reflect` for `.claude/memory/` category routing.

**Key insight:** `tcs-helper:memory` does NOT build a new capture system. It extends claude-reflect with category-aware and layer-aware routing, the same way `/miyo-reflect` extended it for MiYo.

---

## obra/superpowers

**Repository:** https://github.com/obra/superpowers
**Author:** Jesse Vincent (obra)
**License:** Check repo for current license

**What we use:**
- TDD skill (RED-GREEN-REFACTOR iron law, rejected-rationalizations table) → `tcs-workflow:xdd-tdd`
- Verification-before-completion discipline → `tcs-workflow:verify`
- Receiving-code-review rigor pattern → `tcs-workflow:receive-review`
- Git worktree workflow → `tcs-helper:git-worktree`
- Finishing-a-development-branch workflow → `tcs-helper:finish-branch`
- Dispatching-parallel-agents patterns → `tcs-workflow:parallel-agents`
- Spec-review subagent loop (from brainstorming) → merged into `tcs-workflow:brainstorm`
- Anti-shortcut iron law (from systematic-debugging) → merged into `tcs-workflow:debug`
- Subagent dispatch with BASE_SHA/HEAD_SHA context (from requesting-code-review) → merged into `tcs-workflow:review`
- Fresh-subagent-per-task + two-stage review pattern (from subagent-driven-development) → merged into `tcs-workflow:implement`
- `writing-skills` PICS structure and verification steps → merged into `tcs-helper:skill-author`

**Deprecated by TCS equivalents:** `writing-plans`, `executing-plans`, `brainstorming`

---

## citypaul/.dotfiles

**Repository:** https://github.com/citypaul/.dotfiles
**Author:** Paul Dobbins (citypaul)
**License:** Check repo for current license

**What we use:**
- Domain skill library → `tcs-patterns` plugin (17 skills total):
  - Architecture: `ddd`, `hexagonal-architecture`, `functional`, `event-driven` (skill exists, no citypaul source)
  - API & Types: `api-design` (no citypaul source), `typescript-strict`
  - Testing: `testing`, `mutation-testing`, `frontend-testing`, `react-testing`, `twelve-factor` (via testing angle)
  - `test-design-reviewer` — originally by Andrea Laforgia (andlaf-ak/claude-code-agents), adapted by citypaul, re-adapted for TCS; evaluates tests against Dave Farley's 8 properties
  - `tdd` skill from citypaul — **dropped**; TCS already has `tcs-workflow:xdd-tdd` (from obra/superpowers). MUTATE step from citypaul `tdd` merged into `tcs-workflow:xdd-tdd` as an optional checkpoint.
- All reference/ stub files in `tcs-patterns` skills populated with content from this repo (progressive disclosure pattern)
- Philosophy-first CLAUDE.md approach (v3.0.0: ~100 lines core, skills on demand) → informs TCS modular CLAUDE.md design
- ADR agent pattern → `tcs-team:the-architect/record-decision.md`
- `/setup` command concept (stack detection → generate CLAUDE.md + hooks + agents) → `tcs-helper:setup`
- TDD plan task format (explicit RED/GREEN/REFACTOR/MUTATE per step) → merged into `tcs-workflow:specify-plan`; MUTATE checkpoint also added to `tcs-workflow:xdd-tdd`
- PR reviewer with TDD compliance dimension → informs `tcs-team` code-reviewer enhancements
- Progress-guardian plan tracking concept → merged into `tcs-workflow:specify-meta` and `implement`

**Attribution note:** `test-design-reviewer` skill originates from Andrea Laforgia (https://github.com/andlaf-ak/claude-code-agents/blob/main/test-design-reviewer.md), adopted via citypaul's adaptation. Attribution preserved in the skill file.

---

## centminmod/my-claude-code-setup

**Repository:** https://github.com/centminmod/my-claude-code-setup
**Author:** centminmod
**License:** Check repo for current license

**What we use:**
- Memory bank architecture (per-concern CLAUDE-*.md files: activeContext, patterns, decisions, troubleshooting) → `tcs-helper:memory` (layer 3 of unified memory system)
- Cleanup-context workflow (token reduction, archive resolved issues) → part of `tcs-helper:memory`
- `claude-docs-consultant` pattern (on-demand docs fetching, never front-loaded) → `tcs-helper:docs`
- CLAUDE.md tech-stack templates (Cloudflare Workers, Convex) → `docs/templates/`, consumed by `tcs-helper:setup`
- Memory bank synchronizer agent (preservation rules: never delete todos/roadmaps, only update technical accuracy) → informs `tcs-helper:memory` design
- Chain of Draft (CoD) token-efficient search notation concept → optional mode in `tcs-workflow:analyze`

---

## youngleaders.tech: How I Finally Sorted My Claude Code Memory

**Article:** https://www.youngleaders.tech/p/how-i-finally-sorted-my-claude-code-memory
**Author:** John Conneely

**What we use:**
- Memory category taxonomy: **general** (conventions), **tools** (integrations), **domain** (topic knowledge) — applied across g/p/r scope layers rather than all-global as the article does
- Domain knowledge lifecycle: staging (in repo memory) → promotion (extracted to skill) → pointer (memory entry references skill) — informs organic growth path for `tcs-patterns`
- 200-line budget rule for project MEMORY.md
- Routing rules belong in CLAUDE.md (always loaded), not in MEMORY.md (budgeted)
- PreToolUse hook pattern for injecting memory before tool calls (to evaluate in memory system session)
- MEMORY.md as index only — topic files loaded on demand, not front-loaded
- Practical result: reduced CLAUDE.md from ~189 to 63 lines by moving content to typed memory files

**Key divergence from article:** Author puts all categories in global scope. TCS distributes them: general/tools at global level, domain at repo level, project domain at project level.

---

## Reddit: Managing Large CLAUDE.md Files with Document References

**Post:** https://www.reddit.com/r/ClaudeAI/comments/1lr6occ/tip_managing_large_claudemd_files_with_document/
**Author:** unknown Reddit user

**What we use:**
- Document-reference approach for modular CLAUDE.md: split large files into focused sub-documents, import by reference
- Informs `tcs-helper:memory` sync design and `tcs-helper:setup` CLAUDE.md generation

---

## TCS Upstream (MMoMM-org fork baseline)

**Repository:** https://github.com/MMoMM-org/the-custom-startup
**Upstream:** (original the-startup framework)

**Foundation everything builds on:**
- Full spec pipeline (PRD → SDD → PLAN via `/specify`)
- Agent team library (tcs-team, 15 agents)
- Phase orchestration with drift detection (`/implement`)
- Constitution enforcement (`/validate`, `CONSTITUTION.md`)
- `tcs-helper:skill-author` (existing)
- Statusline scripts and configuration
