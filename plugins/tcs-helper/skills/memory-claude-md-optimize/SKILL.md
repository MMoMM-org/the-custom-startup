---
name: memory-claude-md-optimize
description: "Optimize and migrate CLAUDE.md files into Memory Bank structure. Use when auditing CLAUDE.md quality, scoring content, migrating flat files to categorized memory, replacing @-imports with descriptive references, reducing context window token consumption, or cleaning up bloated CLAUDE.md files."
user-invocable: true
argument-hint: "[--dry-run] [--scope global|project|repo]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:memory-claude-md-optimize**

Act as a CLAUDE.md optimization specialist that audits, scores, categorizes, and migrates content from flat CLAUDE.md files into the structured Memory Bank system.

## Interface

```
DiscoveredFile {
  path: string           // Absolute path to the file
  scope: global | project | repo
  type: claude_md | memory_category | memory_index | agents_md | include_file
  line_count: number
  token_estimate: number // chars / 4 approximation
  import_chain: string[] // Which @-import led to this file's discovery
  loading: always | lazy // always = @-imported; lazy = referenced
}

QualityScore {
  file: DiscoveredFile
  commands_workflows: number    // 0-20
  architecture_clarity: number  // 0-20
  non_obvious_patterns: number  // 0-15
  conciseness: number           // 0-15
  currency: number              // 0-15
  actionability: number         // 0-15
  total: number                 // 0-100
  grade: A | B | C | D | F
  issues: string[]              // Specific improvement suggestions
  warnings: string[]            // Line count warnings, etc.
}

CategorizedItem {
  content: string               // The actual text (bullet, section, code block)
  source_file: string           // Where it came from
  source_line: number           // Line number in source
  category: general | tools | domain | decisions | context | troubleshooting
  scope_fit: generic | specific
  current_scope: global | project | repo
  recommended_scope: global | project | repo
  move_reason: string           // Why relocation is recommended (empty if staying)
}

ImportReplacement {
  file: string                  // File containing the @-import
  line: number                  // Line number of the @-import
  original: string              // e.g., "@docs/ai/memory/memory.md"
  replacement: string           // Descriptive reference text
  target_file: string           // The file being imported
  token_savings: number         // Estimated tokens saved by lazy-loading
}

SecretDetection {
  file: string
  line: number
  type: string                  // "API key", "GitHub token", "Password", etc.
  redacted_preview: string      // Line with secret replaced by [REDACTED]
}

SnapshotEntry {
  path: string
  scope: global | project | repo
  lines: number
  tokens: number
  loading: always | lazy
}

OptimizationSnapshot {
  timestamp: string             // ISO8601
  files: SnapshotEntry[]
  total_lines: number
  total_tokens: number
  always_loaded_tokens: number  // Tokens from @-imported files
  lazy_loaded_tokens: number    // Tokens from referenced-only files
}

State {
  target: string                // Repo root (cwd)
  scope: global | project | repo | null
  dry_run: boolean
  discovered_files: DiscoveredFile[]
  scores: QualityScore[]
  categorized_items: CategorizedItem[]
  import_replacements: ImportReplacement[]
  secrets: SecretDetection[]
  before_snapshot: OptimizationSnapshot | null
  after_snapshot: OptimizationSnapshot | null
}
```

## Constraints

**Always:**
- Create backups before modifying any file (in-place with `.backup-YYYYMMDD-HHMMSS` suffix).
- Get user confirmation via AskUserQuestion before applying changes.
- Load reference docs only when the workflow reaches that phase (not upfront).
- Treat existing Memory Bank content as already-categorized — propose additions, not overwrites.
- Discover project directories dynamically via @-import chains — never hardcode paths.
- Follow `<!-- YYYY-MM-DD -->` date format for new memory entries.
- Scan for credential patterns during analysis and flag in report (non-blocking).
- Preserve AGENTS.md for cross-tool compatibility — only optimize the @-import.

**Never:**
- Modify files without explicit user confirmation.
- Hardcode project directory paths (e.g., `~/.claude/projects/` is session storage, not project CLAUDE.md).
- Overwrite existing Memory Bank entries — always append below existing content.
- Delete @-import targets — only replace the import line with a descriptive reference.
- Block operations on credential detection — warn in report only.
- Create @-imports in memory.md — it is an index only.
- Propose replacing **protected @-imports** (see Protected @-Imports below).
- Flag "skill overlap" when a CLAUDE.md section says "use /skill-name" and points to a reference file — the reference file supplements the skill, it does not duplicate it.
- Mechanize enforceable directives (always/never/must rules) — detecting them is in scope, but classification and hook/CI authoring belong to `rule-enforcer`. Emit a pointer only.

### Protected @-Imports

Some @-imports are structural and must **never** be proposed for replacement:

| Pattern | Reason |
|---------|--------|
| `@docs/ai/memory/memory.md` | Memory bank index — routing hub for the memory system |
| `@~/*/projects/*/` (project-level team/config) | Critical project context loaded for every session in that project |
| `@AGENTS.md` | Cross-tool compatibility file (handled separately in Step 4) |

**Detection rule**: Before adding an @-import to `ImportReplacement[]`, check:
1. Is the target a memory index file (`memory.md` in a `memory/` directory)? → **Skip**
2. Is the target a project-level config outside the repo (resolved path matches `~/*/projects/`)? → **Skip**
3. Is the target `AGENTS.md`? → **Skip** (handled in Step 4)

Only propose replacement for @-imports that are genuinely candidates for lazy-loading (architecture docs, large reference files, supplementary context).

## Reference Materials

- [Categorization](reference/categorization.md) — Category definitions, signal keywords, edge case rules, scope-fit assessment
- [Scoring Rubric](reference/scoring-rubric.md) — 6 quality criteria, grade scale, line count warnings, low-score guidance
- [Scope Rules](reference/scope-rules.md) — Scope definitions, cascade behavior, @-import resolution, scope-fit decision tree

## Workflow

### 1. Discover

Parse arguments: extract `--dry-run` flag and `--scope` option from invocation.

match (scope argument) {
  provided => set State.scope to argument value
  missing  => AskUserQuestion:
    Global (g+p+r) — analyze all scopes, starting from ~/.claude/CLAUDE.md
    Project (p+r) — analyze project and repo scopes
    Repo (r only) — analyze repo CLAUDE.md and Memory Bank files only
}

Read reference/scope-rules.md for scope definitions, cascade behavior, and @-import resolution.

Execute cascade discovery per scope-rules.md:
- Start at the scope entry point (global: `~/.claude/CLAUDE.md`; project: project CLAUDE.md from @-import chain; repo: `./CLAUDE.md`)
- For each file discovered, scan for two types of references:
  1. **@-imports** (eager): lines matching `^@(.+\.md)\s*$` — these are always-loaded
  2. **Descriptive references** (lazy): prose lines containing file paths matching `[a-zA-Z0-9_./-]+\.md` that point to existing files — these are already-optimized lazy-loaded references (e.g., "For routing rules, see docs/ai/memory/memory.md — consult when...")
- Resolve each path (expand `~`, resolve relative to containing file, use absolute if starts with `/`)
- Classify scope of resolved path: under `~/.claude/` → global; outside repo but not `~/.claude/` → project; inside repo → repo
- Mark @-imports as `loading: always`; descriptive references as `loading: lazy`
- Track a `visited` set of absolute paths — skip with warning if already visited (circular import detection)
- If resolved path does not exist: log warning "Broken reference: {path} in {source_file}" and continue
- For repo scope: also Glob `**/CLAUDE.md`, find `AGENTS.md`, and Glob `docs/ai/memory/*.md`
- Cascade downward through included scopes (global → project → repo); never cascade upward

For each discovered file: compute line_count (via `wc -l` or Read), token_estimate (chars / 4), classify loading type (always vs lazy per scope-rules.md file type table).

Compute BEFORE snapshot: sum all file metrics into OptimizationSnapshot.

Display discovery summary table:
| File | Scope | Lines | ~Tokens | Loading |

---

### 2. Score

Read reference/scoring-rubric.md.

Read the repository README and skim the code layout first: the rubric credits only what they do not
already give.

For each discovered file where type is `claude_md` or `agents_md`:
1. Read the file content
2. Apply all 6 scoring criteria from the rubric:
   - commands_workflows (0-20): scan for runnable commands, CLI invocations, workflow steps
   - architecture_clarity (0-20): scan for structural constraints and design reasons the README and code lack
   - non_obvious_patterns (0-15): scan for gotchas, workarounds, "note:", "important:", edge cases
   - conciseness (0-15): measure line count, redundancy, ratio of actionable to filler content
   - currency (0-15): scan for stale references, deprecated tools, outdated versions
   - actionability (0-15): scan for directive vs descriptive statements
3. Compute total score and assign grade: A (85-100) | B (70-84) | C (50-69) | D (30-49) | F (0-29)
4. If total < 50: add concrete improvement suggestions to issues[] per rubric Low Score Guidance
5. If line_count > 150: add warning "File exceeds the 150-line optimization threshold."
6. If line_count > 200: add warning "File significantly exceeds recommended length (200+ lines). Context window cost is high."

Display quality scores table:
| File | Scope | Lines | Score | Grade | Key Issue |

---

### 3. Categorize

Read reference/categorization.md and reference/scope-rules.md.

For each discovered file:
1. Parse content into discrete items (bullet points, sections with content, code blocks, paragraphs)
   - If the README or code already gives an item (an overview, directory tour, tech-stack list or
     setup steps), mark it for removal instead of categorizing it, and list it in Content Migration
     with To: `removed (in README)` or `removed (in code)` ([PA-31](../prompt-author/reference/catalog/instruction-files.md#pa-31-overview-the-readme-or-code-already-gives)).
2. For each remaining item: classify by category using categorization.md signal keywords and edge case rules:
   - general: naming, convention, style, format, always/never/prefer directives
   - tools: CLI commands, build/CI references, API/SDK knowledge, tool quirks
   - domain: business rules, entity definitions, data model constraints, domain vocabulary
   - decisions: "chose", "decided", "because", architecture rationale, trade-off records
   - context: "working on", "this sprint", "current", "blocker", time-bound active state
   - troubleshooting: "if X fails", workarounds, known bugs, proven fixes
   - If multiple categories match: prefer the more specific category
3. Assess scope fit using scope-rules.md decision tree:
   - generic (applies everywhere) → recommended_scope: global
   - project-wide (applies across repos in this project) → recommended_scope: project
   - repo-specific → recommended_scope: repo
4. If recommended_scope != current_scope: flag for relocation with reason
5–7. Read `reference/categorize-checks.md` now and run its three checks on every discovered file: credential patterns (non-blocking warning), skill overlap, and the enforceable-directive count for the Step 4 report.

For each @-import found during discovery:
1. Check against Protected @-Imports rules (see Constraints) — if protected, skip with note "Protected: [reason]"
2. Analyze the imported file's content
3. Generate a descriptive reference: "For [topic], see [path] — [description of contents and when to use]"
4. Record in ImportReplacement[] with estimated token savings (file token_estimate)

Display categorization summary:
- Items per category table: | Category | Count | Files |
- Scope mismatch recommendations: list items with current_scope → recommended_scope
- @-import replacement proposals: | File | Import | Proposed Reference | ~Token Savings |
- Credential warnings (if any): | File | Line | Type | Preview |
- Skill-overlap detections (if any): | Section | Skill | Overlap | Recommendation |

---

### 4. Propose

match (dry_run flag) {
  true =>
    Display full report to console: quality scores table, content migration table,
    @-import replacement proposals, sensitive content warnings, before/after comparison
    (computed as if apply had run — project from categorization data, no actual write).
    STOP. Do not create any files.
  false => continue to proposal generation below
}

Check if `claude-md-optimization/` already exists at repo root:

match (existing temp dir) {
  exists =>
    AskUserQuestion:
      Overwrite existing claude-md-optimization/ directory
      Use a different directory name (enter name)
      Cancel
  missing => use `claude-md-optimization/` as proposal dir
}

Read `reference/proposal-format.md` now. It gives the proposal directory layout, how each optimized CLAUDE.md is built, the seven sections of `OPTIMIZATION-REPORT.md`, and the `@AGENTS.md` handling. Create every file it lists before going on.

Display: "Proposal ready at claude-md-optimization/ — review files and OPTIMIZATION-REPORT.md."

AskUserQuestion:
  Apply — proceed with backing up originals and placing new files
  Edit files first, then come back to apply
  Cancel — discard proposal, no changes made

match (response) {
  Apply   => continue to Step 5
  Edit    => STOP — user edits temp dir, re-invokes skill when ready
  Cancel  => STOP — inform user no changes were made
}

---

### 5. Apply

For each original file that will be modified:

1. Compute backup path: original path + `.backup-` + current date-time (format: `YYYYMMDD-HHMMSS`)
2. Run: `Bash("cp /abs/path/to/original /abs/path/to/original.backup-YYYYMMDD-HHMMSS")`
3. If backup write fails: ABORT apply. Report: "Backup failed for {path} — apply aborted.
   Check file permissions." Do not modify any originals.

After all backups succeed: write proposed files from temp dir to original locations.

Memory Bank handling:

match (docs/ai/memory/ exists) {
  missing =>
    Create docs/ai/memory/ directory.
    For each category file: Read corresponding template from
    `plugins/tcs-helper/templates/memory-{category}.md` as format reference, then Write
    the proposed category file (with proposed content appended in `<!-- YYYY-MM-DD -->` format).
    Create docs/ai/memory/memory.md index from template.
  exists =>
    For each proposed category file with new content:
      Read existing docs/ai/memory/{category}.md.
      Append new entries below existing content with `<!-- YYYY-MM-DD -->` date comment.
      Do NOT overwrite existing entries.
    Update docs/ai/memory/memory.md: add `[updated: YYYY-MM-DD]` next to modified files.
    If stale or duplicate content detected in existing memory files: display recommendation:
      "Run /memory-cleanup to deduplicate and prune stale entries in the existing memory files."
}

Display apply summary:

```
Apply complete:
  Backed up:  ~/.claude/CLAUDE.md → ~/.claude/CLAUDE.md.backup-20260329-143022
              ./CLAUDE.md → ./CLAUDE.md.backup-20260329-143022
  Created:    docs/ai/memory/ (new Memory Bank structure)
  Modified:   docs/ai/memory/domain.md (2 entries appended)
              docs/ai/memory/tools.md (3 entries appended)
  Replaced:   ~/.claude/CLAUDE.md
              ./CLAUDE.md

Recommendation: Run /memory-sync --fix to verify Memory Bank structural integrity.
```

---

### 6. Verify

Compute AFTER snapshot: re-scan all files at their final locations (originals have been replaced).
For each file: compute line_count and token_estimate. Classify loading type.
Sum into after_snapshot (same structure as before_snapshot from Step 1).

Display Before/After comparison table:

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total files | {before.files count} | {after.files count} | {delta} |
| Total lines | {before.total_lines} | {after.total_lines} | {delta} ({pct}%) |
| Always-loaded tokens | {before.always_loaded_tokens} | {after.always_loaded_tokens} | {delta} ({pct}%) |
| Lazy-loaded tokens | {before.lazy_loaded_tokens} | {after.lazy_loaded_tokens} | {delta} |
| Net context savings | — | — | **{net savings} tokens ({pct}% always-loaded)** |

Display the verification prompt from the end of `reference/proposal-format.md` as a blockquote, with the before and after numbers filled in.

AskUserQuestion:
  Delete temp directory (`rm -rf claude-md-optimization/`)
  Archive — keep claude-md-optimization/ in place as an archive record
  Keep as-is — leave unchanged

match (response) {
  Delete  => Bash("rm -rf {repo_root}/claude-md-optimization/")
             Display: "Temp directory deleted."
  Archive => Display: "claude-md-optimization/ kept as archive. You may commit or
             remove it later."
  Keep    => Display: "Temp directory left unchanged at claude-md-optimization/."
}
