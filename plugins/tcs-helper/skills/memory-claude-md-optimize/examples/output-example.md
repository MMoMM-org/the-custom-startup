# /memory-claude-md-optimize — Example Output

## Input

Running optimization on a repo where:

1. `~/.claude/CLAUDE.md` (global) is 187 lines, verbose, contains stale tool references and one embedded API key
2. `./CLAUDE.md` (repo) is 95 lines, mostly clean but has two raw `@`-imports and some content duplicated from global
3. `docs/ai/memory/domain.md` contains a business rule that should be in the memory bank, not inline in CLAUDE.md
4. Several memory bank files exist but are not referenced via descriptive imports

---

## Output

The skill writes an `OPTIMIZATION-REPORT.md` to the proposal temp directory. Its contents:

```markdown
# OPTIMIZATION REPORT
Generated: 2026-03-29 14:30:22

## Quality Scores

| File | Scope | Lines | Score | Grade | Key Issue |
|------|-------|-------|-------|-------|-----------|
| ~/.claude/CLAUDE.md | global | 187 | 42 | D | Verbose, stale tool refs, embedded credential |
| ./CLAUDE.md | repo | 95 | 71 | B | Raw @-imports reduce lazy-loading benefit |
| docs/ai/memory/domain.md | repo | 38 | 85 | A | Clean; one item miscategorized |
| docs/ai/memory/tools.md | repo | 22 | 90 | A | Well-scoped tool preferences |
| docs/ai/memory/context.md | repo | 14 | 88 | A | Current and concise |

Grading scale: A = 80-100, B = 65-79, C = 50-64, D = 30-49, F = 0-29

## Content Migration

| Item | From | To | Category | Reason |
|------|------|-----|----------|--------|
| "Always use fd for file search" | global CLAUDE.md:31 | global memory-tools.md | tools | Tool preference belongs in tools category, not always-loaded CLAUDE.md |
| "OrderProcessor validates before..." | repo CLAUDE.md:52 | repo memory-domain.md | domain | Business invariant — load on demand, not every session |
| "Prefer Zod schemas at API boundaries" | global CLAUDE.md:67 | global memory-preferences.md | preferences | Coding style preference — lazy-loadable |
| "Auth spike in progress, paused on..." | global CLAUDE.md:144 | repo memory-context.md | context | Active context item belongs in repo scope, not global |
| "Never use --force-push on main" | global CLAUDE.md:18 | global CLAUDE.md:18 | guardrails | Already correctly placed — no migration needed |

## @-Import Replacements

| File | Import | Action | Token Savings |
|------|--------|--------|---------------|
| ./CLAUDE.md | `@docs/ai/memory/domain.md` | Replace with: "Business rules and domain invariants are in `docs/ai/memory/domain.md` — consult when implementing OrderProcessor, PaymentService, or related domain logic." | ~220 tokens |
| ./CLAUDE.md | `@AGENTS.md` | Replace with: "Project structure and agent guidance is in `AGENTS.md` — consult when working on agent definitions, understanding repo layout, or onboarding to the codebase." | ~420 tokens |
| ~/.claude/CLAUDE.md | `@~/.claude/includes/skills-reference.md` | Replace with: "Skill authoring rules and frontmatter reference are in `~/.claude/includes/skills-reference.md` — consult when creating or editing Claude Code skills." | ~310 tokens |

## Sensitive Content Detected

| File | Line | Type |
|------|------|------|
| ~/.claude/CLAUDE.md | 42 | API key (`sk-ant-api03-[REDACTED]`) |
| ~/.claude/CLAUDE.md | 98 | GitHub token (`ghp_[REDACTED]`) |

**Recommendation:** Remove these credentials before applying optimization.
They should not be stored in CLAUDE.md files — use environment variables or a secrets manager instead.
The proposed optimized files have these lines removed.

## Before/After Comparison

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total files | 5 | 9 | +4 (new memory category files) |
| Total lines | 356 | 248 | -108 (-30%) |
| Always-loaded tokens | 2,450 | 980 | -1,470 (-60%) |
| Lazy-loaded tokens | 0 | 1,200 | +1,200 |
| Net context savings | — | — | **-1,470 tokens (-60% always-loaded)** |

*Always-loaded tokens* = tokens Claude reads at session start from CLAUDE.md and direct @-imports.
*Lazy-loaded tokens* = tokens in memory category files, read only when relevant context is requested.

## Verification Prompt

> **Why a new session?** The current session still has the old CLAUDE.md files
> cached. Claude Code loads CLAUDE.md and memory files at session start,
> so the current session reflects the old structure — not the optimized one.
>
> After applying the optimization, start a **new Claude Code session**, then run:
>
> 1. `/context` — check total memory token usage; always-loaded tokens should
>    be approximately 980 (was 2,450)
> 2. `/memory` — verify Memory Bank structure is intact; you should see
>    4 category files under `docs/ai/memory/`
>
> **What to look for:**
> - `~/.claude/CLAUDE.md` and `./CLAUDE.md` should be shorter and free of raw `@`-imports
> - Memory category files (`domain.md`, `tools.md`, `preferences.md`, `context.md`) should
>   be present and contain the migrated content
> - No API keys or tokens visible in any CLAUDE.md file
> - The verification confirms the optimization applied correctly and Claude is
>   operating with the reduced always-loaded footprint
```
