# Scope Rules Reference

## How to Use This Document

Load this document during the **Discover** and **Categorize** phases of the optimization workflow.

- **Discover phase**: Use the Scope Definitions, Cascade Behavior, and @-Import Resolution sections to find all files that belong to the selected scope.
- **Categorize phase**: Use the File Type Classification and Scope-Fit Decision Tree to determine whether each content item is at the correct scope or should be moved.

---

## Scope Definitions

### Global Scope

- **Primary file**: `~/.claude/CLAUDE.md`
- **Also includes**: `~/.claude/includes/*.md`
- **Loading**: Always loaded at the start of every Claude Code session
- **Purpose**: Personal preferences, workflow habits, universal conventions, and tool knowledge that applies across every project and repo
- **Discovery**: Fixed path — always starts here when starting scope is `global`
- **Writes**: Use `~/.claude/includes/memory-<category>.md` for categorized global memory

### Project Scope

- **Primary file**: Discovered via @-imports — the path is user-defined (e.g., `~/Kouzou/projects/{name}/CLAUDE.md`)
- **NOT at**: `~/.claude/projects/{encoded}/` — that path is Claude Code's session storage (learnings queue), not project CLAUDE.md files
- **Loading**: Loaded when Claude Code is run inside any repo belonging to that project
- **Purpose**: Conventions, architecture decisions, and domain rules that apply to all repos in a multi-repo project
- **Discovery**: Follow @-imports from `~/.claude/CLAUDE.md`. Any @-import that points outside the current repo (e.g., to `~/Kouzou/...`) is classified as a PROJECT scope file. The path varies per user — never hardcode it.

### Repo Scope

- **Primary file**: `./CLAUDE.md` (repo root)
- **Also includes**:
  - Subdirectory variants: `src/CLAUDE.md`, `test/CLAUDE.md`, `docs/CLAUDE.md`, and any other `**/CLAUDE.md`
  - `AGENTS.md` (if present — kept for cross-tool compatibility with Codex, Cursor, Aider, etc.)
  - Memory Bank files: `docs/ai/memory/*.md` — **always analyzed**, even if starting scope is repo only
- **Loading**: Loaded when Claude Code is run in this specific repo
- **Purpose**: Repo-specific conventions, architecture, build commands, toolchain knowledge, and Memory Bank content
- **Discovery**: Glob `**/CLAUDE.md` from repo root; find `AGENTS.md`; Glob `docs/ai/memory/*.md`

---

## Cascade Behavior

The cascade always moves downward — from broader scope to narrower. It never cascades upward.

### Starting scope: `global`

1. Discover `~/.claude/CLAUDE.md` → add to list
2. Follow all @-imports from global CLAUDE.md (recursive, with visited-set to prevent loops)
   - @-imports pointing to `~/.claude/includes/*.md` → GLOBAL scope
   - @-imports pointing outside the repo (e.g., `~/Kouzou/projects/...`) → PROJECT scope
   - @-imports pointing inside the repo → REPO scope
3. Discover all `~/.claude/includes/*.md` → add to list (GLOBAL scope)
4. Cascade to PROJECT scope (step below)
5. Cascade to REPO scope (step below)

### Starting scope: `project`

1. Identify the project CLAUDE.md path from the @-import chain discovered in global scope (or ask user if starting here without global context)
2. Discover project CLAUDE.md → add to list
3. Follow @-imports from project CLAUDE.md (recursive)
4. Cascade to REPO scope (step below)

### Starting scope: `repo`

1. Discover `./CLAUDE.md` → add to list
2. Glob `**/CLAUDE.md` in src/, test/, docs/ and other subdirectories → add to list
3. Discover `AGENTS.md` if present → add to list
4. Glob `docs/ai/memory/*.md` → add to list (Memory Bank files, always included)
5. Follow @-imports from all discovered repo files (recursive, with visited-set)

---

## @-Import Resolution

@-imports appear as lines matching `^@(.+\.md)\s*$` in a CLAUDE.md file.

Resolve the path using these rules in order:

| Prefix | Resolution rule | Example |
|--------|----------------|---------|
| Starts with `~` | Expand `~` to the user's home directory | `@~/.claude/includes/memory-preferences.md` → `/Users/marcus/.claude/includes/memory-preferences.md` |
| Starts with `/` | Use as absolute path | `@/absolute/path/to/file.md` → `/absolute/path/to/file.md` |
| No prefix | Resolve relative to the **directory containing the current file** | `@docs/ai/memory/memory.md` in `~/project/CLAUDE.md` → `~/project/docs/ai/memory/memory.md` |

### Scope classification of resolved @-imports

After resolving the path, classify the target file's scope:

- Path is under `~/.claude/` → GLOBAL scope
- Path is outside the current repo but not under `~/.claude/` → PROJECT scope
- Path is inside the current repo → REPO scope

### Circular import detection

Track a `visited` set of resolved absolute paths. Before recursing into a file, check if it is already in `visited`. If it is, skip it and log a warning: `"Circular @-import detected: {path} already visited"`.

### Broken import handling

If a resolved path does not exist, log a warning: `"Broken @-import: {original_path} in {source_file}"` and continue discovery. Do not abort.

---

## File Type Classification

Each discovered file has a type that determines how it is treated during analysis.

| File pattern | Type | Scope | Always-loaded? |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | primary-config | global | Yes — at every session start |
| `~/.claude/includes/*.md` | global-includes | global | Yes — via @-import from global CLAUDE.md |
| `{project-dir}/CLAUDE.md` | project-config | project | Yes — when inside any repo of that project |
| `./CLAUDE.md` | repo-config | repo | Yes — when inside this repo |
| `{subdir}/CLAUDE.md` | subdir-config | repo | Conditional — when Claude Code discovers it |
| `AGENTS.md` | cross-tool-compat | repo | Only if @-imported by CLAUDE.md |
| `docs/ai/memory/memory.md` | memory-index | repo | Lazy — Claude reads when routing learnings |
| `docs/ai/memory/general.md` | memory-category | repo | Lazy — loaded on demand |
| `docs/ai/memory/tools.md` | memory-category | repo | Lazy — loaded on demand |
| `docs/ai/memory/domain.md` | memory-category | repo | Lazy — loaded on demand |
| `docs/ai/memory/decisions.md` | memory-category | repo | Lazy — loaded on demand |
| `docs/ai/memory/context.md` | memory-category | repo | Lazy — loaded on demand |
| `docs/ai/memory/troubleshooting.md` | memory-category | repo | Lazy — loaded on demand |

**Always-loaded** files are the primary optimization target. Reducing their size directly reduces context window consumption.

**Lazy-loaded** (memory category files) are not @-imported — Claude reads them by choice when relevant. They do not consume context at session start.

---

## Scope-Fit Decision Tree

Use this decision tree for each content item found during categorization. The goal is to recommend the most appropriate scope for the content.

```
Is the content relevant across ALL projects and repos (not specific to this project or codebase)?
  YES → Recommended scope: GLOBAL
       Examples: personal workflow preferences, universal Claude behavior rules,
                 cross-project tool knowledge (e.g., git conventions, shell preferences)
  NO → continue ↓

Is the content relevant across MULTIPLE REPOS in this project, but not globally?
  YES → Recommended scope: PROJECT
       Examples: shared architecture patterns, cross-repo naming conventions,
                 team conventions that apply project-wide but not to other projects
  NO → continue ↓

Is the content specific to THIS REPO only?
  YES → Recommended scope: REPO
       Examples: build commands, repo-specific toolchain, this codebase's architecture,
                 domain rules for this service, troubleshooting notes for this repo's issues
```

### Mismatch Detection Rules

After determining the recommended scope, compare it to the file's current scope:

| Content specificity | Currently in | Action |
|---|---|---|
| Generic (applies everywhere) | global | Correct — no move needed |
| Generic (applies everywhere) | project | Suggest moving to global |
| Generic (applies everywhere) | repo | Suggest moving to global |
| Project-wide | project | Correct — no move needed |
| Project-wide | global | Suggest moving to project |
| Project-wide | repo | Suggest moving to project |
| Repo-specific | repo | Correct — no move needed |
| Repo-specific | global | Suggest moving to repo |
| Repo-specific | project | Suggest moving to repo |

### Specificity Signal Keywords

Use these signals to determine whether content is generic or specific:

**Generic signals** (suggests global or project scope):
- Model names: `gpt-*`, `claude-*`, `o1`, `sonnet`, `opus`
- Universal patterns: "always", "never", "prefer", "avoid" without repo-specific context
- Standard tools: `git`, `curl`, `jq`, common CLI tools
- Personal workflow phrases: "my workflow", "I prefer", "I always"

**Specific signals** (suggests repo scope):
- Specific file paths: references to paths that only exist in this repo
- Project names: mentions of this project or service by name
- Repo-specific tooling: `nx`, `turbo`, custom scripts unique to this repo
- Current-state context: "working on", "this sprint", "blocked by"
- Repo-local commands: build scripts, test commands, deploy pipelines unique to this repo

### Edge Cases

- Content that fits both generic and specific signals → use the more specific classification (repo > project > global)
- Content about a tool that is universally installed vs. one only used in this repo → if only used in this repo, treat as repo-specific
- @-imports that load project or repo content from global CLAUDE.md → the @-import line itself should be replaced with a descriptive reference; the loaded content's scope is determined by the target file's scope
