# Proposal Format (step 4)

Loaded at step 4 of `SKILL.md`, once the proposal directory name is settled.

Create the proposal directory structure:

```
claude-md-optimization/
  global/
    CLAUDE.md          # Optimized global CLAUDE.md (if global scope included)
  project/
    CLAUDE.md          # Optimized project CLAUDE.md (if project scope included)
  repo/
    CLAUDE.md          # Optimized repo CLAUDE.md
    memory/
      memory.md        # Proposed memory index
      general.md       # Proposed general category
      tools.md         # Proposed tools category
      domain.md        # Proposed domain category
      decisions.md     # Proposed decisions category
      context.md       # Proposed context category
      troubleshooting.md
OPTIMIZATION-REPORT.md
```

For each optimized CLAUDE.md file: replace @-imports with descriptive references from
ImportReplacement[]; drop items marked for removal; move categorized content to the appropriate
memory category file under `repo/memory/`; keep routing rules, guardrails, and essentials in
CLAUDE.md.

Write `claude-md-optimization/OPTIMIZATION-REPORT.md` with these sections:

1. **Quality Scores** — table: | File | Scope | Lines | Score | Grade | Key Issue |
2. **Content Migration** — table: | Item | From | To | Category | Reason |
3. **@-Import Replacements** — table: | File | Import | Action | Token Savings |
4. **Sensitive Content Detected** — table: | File | Line | Type | (if any; else omit section)
   Note: "The proposed optimized files have these lines removed."
5. **Enforceable-directive candidates (N found)** — using the Step 3 count. Emit this pointer:
   these always/never/must rules may be mechanically enforceable rather than left as memory
   guidance; this skill relocates them into the Memory Bank as-is; to convert them into hooks,
   CI checks, or git pre-push guards, run `/rule-enforcer --scan` AFTER this optimization
   applies (so directives land in the canonical Memory Bank first, then the scan reads canonical
   files). Optionally list up to 3 example candidate quotes. (Omit section if N is 0.)
6. **Before/After Comparison** — table: | Metric | Before | After | Delta |
   Rows: Total files, Total lines, Always-loaded tokens, Lazy-loaded tokens, Net context savings
   Note: always-loaded = CLAUDE.md + @-imported files; lazy-loaded = memory category files
7. **Verification Prompt** — blockquote (exact format under "Verification prompt" below; displayed in Step 6)

AGENTS.md handling (Feature 11):

match (AGENTS.md exists AND @AGENTS.md found in any CLAUDE.md) {
  true =>
    Calculate token cost of @AGENTS.md import (AGENTS.md token_estimate).
    Check whether AGENTS.md content duplicates content in CLAUDE.md or memory files.
    AskUserQuestion:
      (a) Replace `@AGENTS.md` with a descriptive reference (stops eager loading, keeps AGENTS.md for other tools)
      (b) Slim down AGENTS.md to brief project description only (reduce import token cost)
      (c) Remove `@AGENTS.md` import entirely (AGENTS.md stays for other tools, ignored by Claude Code)
      (d) Keep as-is
    Apply user choice to the proposed CLAUDE.md in the temp directory.
  false => skip AGENTS.md handling
}

## Verification prompt (step 6)

Display self-contained verification prompt as a blockquote:

> **Why a new session?** The current session still has the old CLAUDE.md files
> cached. Claude Code loads CLAUDE.md and memory files at session start,
> so the current session reflects the old structure — not the optimized one.
>
> After applying the optimization, start a **new Claude Code session**, then run:
>
> 1. `/context` — check total memory token usage; always-loaded tokens should
>    be approximately {after.always_loaded_tokens} (was {before.always_loaded_tokens})
> 2. `/memory` — verify Memory Bank structure is intact; you should see
>    {count} category files under `docs/ai/memory/`
>
> **What to look for:**
> - CLAUDE.md files should be shorter and free of raw `@`-imports
> - Memory category files should be present and contain the migrated content
> - No API keys or tokens visible in any CLAUDE.md file
> - The verification confirms the optimization applied correctly and Claude is
>   operating with the reduced always-loaded footprint
