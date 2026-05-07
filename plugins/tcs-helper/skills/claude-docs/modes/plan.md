# `plan` Mode — Repo Detection, Skeleton Proposal, and `docs/` Placeholder Writes

**Invocation:** `/claude-docs plan`

This mode analyses the current repository to determine its type, selects the matching
skeleton from `templates/`, proposes the resulting `docs/` tree to the author, diffs
against any existing `docs/` pages, requests explicit confirmation, then writes empty
placeholder files — one per approved page. No content is ever fabricated; every written
file contains only a page-name H1, a `> TODO:` callout, and empty H2 section headings.

> **No-fabrication contract:** this mode NEVER writes prose content. Every file it creates
> is a placeholder skeleton. Authors fill in the content using `write` mode. If you are
> tempted to fill in a section with example values or concrete prose, stop — write a
> `<!-- TODO -->` marker instead.

---

## Prerequisites

Before starting, verify the following. Stop and report any failure; do not proceed.

1. **Git installed and in a git repository.**
   Diff logic and repo-root resolution depend on `git`.

   ```bash
   git rev-parse --show-toplevel >/dev/null 2>&1
   ```

   If this fails: `plan mode must be run from within a git repository.`

2. **Not on `main` or `master`.** Placeholder writes should land on a feature branch so
   the author can review before merging.

   ```bash
   current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
   ```

   If `current_branch` is `main` or `master`, print an advisory:

   ```
   Advisory: you are on the default branch. Consider switching to a feature branch
   before plan mode writes placeholder files.
   ```

   This is informational — do not block.

3. **Skeleton templates present.** The four skeleton files must exist in `templates/`:

   - `templates/skeleton-obsidian.md`
   - `templates/skeleton-python.md`
   - `templates/skeleton-tcs-plugin.md`
   - `templates/skeleton-generic.md`

   These files live in the `claude-docs` skill's own `templates/` directory (not the
   target repo). If any template is missing, stop:

   ```
   plan mode requires templates/<name> — re-install the claude-docs skill or check
   the templates/ directory.
   ```

---

## Step 1: Repo-Type Detection

Use the Glob tool to look for known manifest files at the repo root. Detection priority
order (first match wins):

| Check | Glob pattern | Detected type |
|---|---|---|
| 1 | `manifest.json` present | `obsidian` — Obsidian plugin |
| 2 | `plugin.json` present | `tcs-plugin` — TCS plugin |
| 3 | `pyproject.toml` present | `python` — Python tool |
| 4 | none of the above | `unknown` — user prompted below |

**Detection logic:**

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"

if Glob "$REPO_ROOT/manifest.json" returns a result; then
  REPO_TYPE="obsidian"
elif Glob "$REPO_ROOT/plugin.json" returns a result; then
  REPO_TYPE="tcs-plugin"
elif Glob "$REPO_ROOT/pyproject.toml" returns a result; then
  REPO_TYPE="python"
else
  REPO_TYPE="unknown"
fi
```

**Detection priority rationale:** `manifest.json` is checked first because it is the most
specific Obsidian identifier (unlikely to appear in Python or TCS repos). `plugin.json` is
checked before `pyproject.toml` to distinguish TCS plugins (which use `plugin.json`) from
Python tools that happen to have a `pyproject.toml` but no `plugin.json`.

### Unknown manifest

If `REPO_TYPE` is `"unknown"` — no recognised manifest was found — do NOT guess.

Use AskUserQuestion to ask the author for the project type before proposing anything:

```
No recognised manifest file was found in this repository
(checked: manifest.json, plugin.json, pyproject.toml).

What type of project is this? Choose one:
  obsidian    — Obsidian plugin (manifest.json-based)
  python      — Python tool or CLI (pyproject.toml-based)
  tcs-plugin  — TCS Claude Code plugin (plugin.json-based)
  generic     — any other project type
```

Wait for the author's response. Set `REPO_TYPE` to the chosen value, then continue.

---

## Step 2: Select and Load Skeleton Template

Map `REPO_TYPE` to the matching skeleton file in the `claude-docs` skill's `templates/`
directory:

| `REPO_TYPE` | Template |
|---|---|
| `obsidian` | `templates/skeleton-obsidian.md` |
| `python` | `templates/skeleton-python.md` |
| `tcs-plugin` | `templates/skeleton-tcs-plugin.md` |
| `generic` | `templates/skeleton-generic.md` |

Use the Read tool to load the selected skeleton. The skeleton defines:
- The proposed `docs/` tree (page filenames).
- Per-page purpose and suggested section structure.

Parse the skeleton to produce a list of proposed pages. Each entry records:
- Page path relative to repo root (e.g. `docs/installation.md`)
- Purpose sentence
- Suggested section headings (H2 list)

---

## Step 3: Render the Proposal

Present the proposed `docs/` tree to the author in a clear, readable format before asking
anything. Example format:

```
Proposed docs/ tree for this obsidian repo:

  docs/
  ├── README.md               — index page linking to all other pages
  ├── installation.md         — install from Community Plugins; verify
  ├── configuration.md        — settings reference (generated by extract mode)
  ├── usage.md                — first use; common workflows
  ├── troubleshooting.md      — common issues; debug info; getting help
  ├── settings-reference.md   — per-setting deep reference
  └── commands-reference.md   — command palette entries
```

Adjust the list and descriptions to match the skeleton selected in Step 2.

---

## Step 4: Diff Against Existing `docs/`

Check whether the repo already has a `docs/` directory:

```bash
docs_dir="$REPO_ROOT/docs"
```

If `docs/` does not exist: all proposed pages are new. Skip to Step 5.

If `docs/` exists: for each proposed page, check whether the file already exists.
For each page that already exists, use AskUserQuestion to ask the author for a per-page
choice:

```
docs/installation.md already exists. What would you like to do with it?
  Keep    — leave the existing file untouched; skip creating a placeholder
  Replace — overwrite the existing file with a fresh placeholder
  Merge   — keep the existing file untouched; you will manually incorporate
             any proposed sections afterwards

(Keep / Replace / Merge)
```

Record the author's choice for each existing page. Pages not yet present always receive
a fresh placeholder (no question needed).

**NEVER overwrite an existing file silently.** The mode will never write to an existing
file unless the author explicitly chose Replace in the per-page question and confirmed
in Step 5. Any page the author chose `Keep` must remain exactly as-is after this mode
completes. This is a hard contract.

---

## Step 5: Propose-Then-Confirm

After all per-page choices have been collected, present the full intended-write list to
the author and ask for confirmation before writing any file:

```
Here is what plan mode will write:

  CREATE  docs/README.md
  CREATE  docs/installation.md
  KEEP    docs/configuration.md  (existing — not touched)
  REPLACE docs/usage.md          (existing — placeholder replaces content)
  MERGE   docs/usage-advanced.md (existing — not written; you will merge sections manually)
  CREATE  docs/troubleshooting.md

Confirm? (yes / no / edit the list)
```

Wait for the author's response.

- **yes** — proceed to Step 6.
- **no** — abort without writing any file. Inform the author: "No files written."
- **edit** — use AskUserQuestion to let the author add, remove, or change choices before
  confirming again.

Do not write a single file before receiving explicit confirmation.

---

## Step 6: Write Placeholder Files

For each page approved for writing (CREATE or REPLACE), use the Write tool to create the
placeholder file.

**Placeholder format (required for all four skeleton types):**

```markdown
# <Page Name>

> TODO: <one sentence describing what this page should contain, drawn from the
> skeleton's per-page purpose statement — paraphrased, not copied verbatim>

## <Section Heading 1>

<!-- TODO -->

## <Section Heading 2>

<!-- TODO -->

(one H2 per section heading listed in the skeleton for this page type)
```

Rules for placeholder content:

- The H1 is the page name (e.g. `Installation`, `Configuration`, `Usage`).
- The `> TODO:` callout describes what to fill in, using the skeleton's purpose
  sentence as the source — paraphrase it; do not copy-paste the skeleton text.
- Each H2 heading matches the skeleton's suggested section list for this page type.
- Each H2 body is empty except for a `<!-- TODO -->` marker.
- No concrete tool names, example values, URLs, or command invocations beyond what
  the skeleton already lists generically.
- No fabricated content of any kind.

**REPLACE behaviour:** The author has already given explicit consent by choosing Replace in
Step 4. Use the Write tool to overwrite the existing file directly with the placeholder
content.

**MERGE behaviour:** Pages the author chose Merge are NOT written by this mode — they are
treated identically to Keep for write purposes; the author handles section incorporation
manually after the mode exits.

**README.md placeholder format:** `docs/README.md` is always part of the proposed skeleton
and is subject to Keep / Replace / Merge like any other page. When writing it, use the
following index placeholder format — the link list must reflect only the pages actually
created or kept in this run:

```markdown
# Documentation

> TODO: Add a one-paragraph overview of this project and who it is for.

## Overview

<!-- TODO -->

## Documentation map

- [Installation](installation.md)
- [Configuration](configuration.md)
- [Usage](usage.md)
- [Troubleshooting](troubleshooting.md)
(add or remove lines to match the pages actually created)

## Quick links

<!-- TODO -->
```

Use relative links (e.g. `[Installation](installation.md)`) — not absolute paths.

---

## Step 7: Final Report

After all writes complete, print a summary:

```
plan mode complete.

Files written:
  CREATE  docs/README.md
  CREATE  docs/installation.md
  REPLACE docs/usage.md
  CREATE  docs/troubleshooting.md

Files kept (not touched):
  KEEP    docs/configuration.md

Files flagged for manual merge:
  MERGE   docs/usage-advanced.md

Files skipped (not in approved list):
  (none)

Next steps:
  - Run `/claude-docs write <page>` to draft content for each placeholder page.
  - Run `/claude-docs extract` to auto-generate docs/configuration.md from your
    settings source.
  - Run `/claude-docs review` when the pages have content to test them against
    reader personas.
```

Adjust the output to reflect what was actually written, kept, replaced, merged, and skipped.

---

## Quality and Safety Contract

- This mode NEVER overwrites an existing file silently. Every existing file that is
  touched requires an explicit Replace choice from the author in Step 4, followed by
  confirmation in Step 5.
- This mode NEVER fabricates content. Every written file is a placeholder with a TODO
  callout and empty H2 sections. No example values, no concrete commands, no invented
  prose.
- AskUserQuestion is used at every decision point: unknown repo type (Step 1), per-page
  Keep / Replace / Merge (Step 4), and final confirmation (Step 5).
- If the author answers "no" at the confirmation step, zero files are written.

---

## Error Handling Reference

| Situation | Behaviour |
|---|---|
| Not in a git repo | Stop at Prerequisites; print message |
| On `main`/`master` | Advisory only; do not block |
| Skeleton template missing | Stop at Prerequisites; print which file is missing |
| No recognised manifest | AskUserQuestion in Step 1; wait for author |
| Existing `docs/` page | AskUserQuestion per page (Keep / Replace / Merge) |
| Author declines confirmation | Abort; zero files written |
| Replace: existing file present | Overwrite directly (explicit consent given in Step 4) |

---

## Examples

### Example 1: Obsidian plugin — no existing `docs/`

**Invocation:** `/claude-docs plan` (repo contains `manifest.json`)

```
Detected: obsidian repo (manifest.json present).

Proposed docs/ tree for this obsidian repo:

  docs/
  ├── README.md               — index page linking to all other pages
  ├── installation.md         — install from Community Plugins; verify
  ├── configuration.md        — settings reference (generated by extract mode)
  ├── usage.md                — first use; common workflows
  ├── troubleshooting.md      — common issues; debug info; getting help
  ├── settings-reference.md   — per-setting deep reference
  └── commands-reference.md   — command palette entries

No existing docs/ directory found. All pages will be created fresh.

Here is what plan mode will write:

  CREATE  docs/README.md
  CREATE  docs/installation.md
  CREATE  docs/configuration.md
  CREATE  docs/usage.md
  CREATE  docs/troubleshooting.md
  CREATE  docs/settings-reference.md
  CREATE  docs/commands-reference.md

Confirm? (yes / no / edit the list)
```

### Example 2: Python repo — existing `docs/installation.md`

**Invocation:** `/claude-docs plan` (repo contains `pyproject.toml`; `docs/installation.md`
already exists)

```
Detected: python repo (pyproject.toml present).

docs/installation.md already exists. What would you like to do with it?
  Keep    — leave the existing file untouched
  Replace — overwrite with a fresh placeholder
  Merge   — keep the existing file; merge new sections manually

(Keep / Replace / Merge)
```

### Example 3: Unknown repo type

**Invocation:** `/claude-docs plan` (no manifest.json, plugin.json, or pyproject.toml)

```
No recognised manifest file was found in this repository
(checked: manifest.json, plugin.json, pyproject.toml).

What type of project is this? Choose one:
  obsidian    — Obsidian plugin
  python      — Python tool or CLI
  tcs-plugin  — TCS Claude Code plugin
  generic     — any other project type
```

Author selects `generic`. Mode loads `templates/skeleton-generic.md` and continues.

