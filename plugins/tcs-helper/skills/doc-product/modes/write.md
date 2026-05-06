# `write` Mode — Section-by-Section Page Drafting

**Invocation:** `/doc-product write <page>`

Examples: `/doc-product write installation`, `/doc-product write configuration`,
`/doc-product write usage`, `/doc-product write troubleshooting`

This mode guides the author through drafting a single documentation page one section at a
time, using the section structure defined in `reference/conventions.md` as the source of
truth. It follows a **discover → document → review** cycle per section: read what exists,
draft the next unwritten section through targeted questions, present the draft for author
approval, then commit only that section before moving on.

> **No-fabrication contract:** this mode NEVER fabricates content. If a fact is not
> available from the repository or from the author's explicit answers, the mode asks
> AskUserQuestion to surface the gap. Writing invented details — command flags, URLs,
> default values, error messages — is forbidden even when they seem plausible.

---

## Prerequisites

Before starting, verify the following. Stop and report any failure; do not proceed.

1. **Git installed and in a git repository.**

   ```bash
   git rev-parse --show-toplevel >/dev/null 2>&1
   ```

   If this fails: `write mode must be run from within a git repository.`

2. **Not on `main` or `master`.** Section edits should land on a feature branch so
   the author can review before merging. If on the default branch, print:

   ```
   Advisory: you are on the default branch. Consider switching to a feature branch
   before write mode edits any file.
   ```

   This is informational — do not block.

3. **`reference/conventions.md` is readable.** The section-structure map lives here.
   Use the Read tool to verify it loads before proceeding.

   If the file is missing: `write mode requires reference/conventions.md — re-install
   the doc-product skill or check the reference/ directory.`

---

## Step 1: Parse Argument

Read `$ARGUMENTS`. The leading token after the mode keyword (`write`) is the page name.

```
page_name = second token of $ARGUMENTS (e.g. "installation", "configuration", "usage", "troubleshooting")
```

If no page name is provided, use AskUserQuestion:

```
Which page do you want to draft? Common choices:
  installation       — install steps, prerequisites, verification
  configuration      — settings reference
  usage              — invocation, common patterns, output
  troubleshooting    — common errors, diagnostics, escalation

Or enter any other page name.
```

---

## Step 2: Locate the Target File

Resolve the target path:

```
target_file = docs/<page_name>.md  (relative to repo root)
```

Use the Read tool to check whether `docs/<page_name>.md` exists.

### If the file does NOT exist

When the placeholder is missing, route to plan mode and stop.

```
docs/<page_name>.md does not exist.

write mode requires a placeholder file to be present before drafting can begin.
Run `/doc-product plan` first to create the docs/ skeleton, which will produce
the placeholder for <page_name>.md. Then return to `/doc-product write <page_name>`.
```

Stop. Do not proceed to Step 3.

### If the file exists

Read its full current contents. Identify which sections are:
- **Approved** — have substantive prose (not a `<!-- TODO -->` or empty body).
- **Unwritten** — have only a `<!-- TODO -->` marker or an empty body after the heading.

This distinction drives the discover step.

---

## Step 3: Detect Page Type and Load Section Structure

Match `<page_name>` to the corresponding `##` section in `reference/conventions.md`.
The matching is case-insensitive on the leading word (e.g. `installation` matches
`## installation`).

Use the Read tool to load `reference/conventions.md`. Extract the recommended section
list for the matched page type. This gives:

- An ordered list of section headings.
- A one-sentence purpose for each section.
- The "must include" checklist for this page type.

If `<page_name>` does not match any `## <type>` in `reference/conventions.md`, use
AskUserQuestion to ask the author which page type is closest, or whether they want to
provide a custom section list.

---

## Step 4: Discover — Assess Current State

With the target file contents (from Step 2) and the section structure (from Step 3):

1. **List approved sections** — sections with substantive content. These will be
   preserved verbatim throughout this mode session.

2. **List unwritten sections** — sections with only `<!-- TODO -->` or no body.
   These are candidates for drafting in this session.

3. **Identify missing sections** — headings from `reference/conventions.md` that do
   not appear at all in the current file (common in hand-edited stubs).

Report the discovery to the author:

```
Current state of docs/<page_name>.md:

  Approved (will be preserved):
    ## Prerequisites       ← already has content
  
  Unwritten (ready to draft):
    ## Install             ← TODO placeholder
    ## Verify              ← TODO placeholder
  
  Missing from conventions (not yet in file):
    ## Next steps          ← not present

Will draft unwritten sections in order, starting with the first unwritten section.
```

---

## Step 5: Propose Section Structure and Confirm

Render the full section list for unwritten and missing sections — the order from
`reference/conventions.md` is the proposed order.

Present it to the author and AskUserQuestion to confirm before drafting:

```
Proposed section structure for the unwritten portions of docs/<page_name>.md
(from reference/conventions.md — <page_name> type):

  ## Install
    Draft this section — command or UI steps to install the software.

  ## Verify
    Draft this section — how the reader confirms installation succeeded.

  ## Next steps
    Draft this section — where to go after a successful install.

Proceed with this structure? (yes / adjust / skip to a specific section)
```

Wait for the author's response.

- **yes** — proceed to Step 6.
- **adjust** — AskUserQuestion to collect changes (reorder, add, remove headings),
  then re-render and confirm again.
- **skip to <section>** — begin at the named section, preserving all earlier sections.

Do not draft any content until the author confirms.

---

## Step 6: Document — Draft One Section at a Time

Work through the confirmed unwritten sections in order, one section at a time.

For each section, run the **discover → document → review** sub-cycle:

### 6a: Discover — Read the section's conventions entry

Re-read the conventions entry for this section type (loaded in Step 3). Note:
- What this section must answer (the "must include" checklist items that apply).
- What facts are required but not yet in the file or obvious from the repo.

### 6b: Document — Surface gaps before drafting

Before writing a single word of prose, identify every fact required to write this
section accurately:

- Commands, flags, file paths — check the repo (use Read, Glob, Grep).
- Version numbers, defaults, prerequisites — check package manifests, settings files.
- Any fact not found in the repo: do NOT fabricate. Use AskUserQuestion.

Example question to author when source-of-truth is missing:

```
To draft the Install section I need:
  1. The exact install command (e.g. npm install, pip install, community plugin search)
  2. The minimum supported OS or runtime version

Neither was found in the repository. Please provide them.
```

Wait for the author's answers before drafting. Record the answers for use in the
draft.

### 6c: Document — Draft the section body

Draft the section body using only:
- Facts found in the repository.
- Facts the author provided in 6b.

Do not fabricate. If a required fact remains unknown after asking, write a
`[NEEDS: <description of missing fact>]` marker in its place and note it in the
final report.

### 6d: Review — Present draft to author

Present the drafted section and AskUserQuestion with three choices:

```
Draft of ## <Section Heading>:

---
<drafted content>
---

What would you like to do?
  Approve   — commit this section to the file; move to the next section
  Iterate   — give feedback; redraft this section
  Remove    — delete this section from the file entirely
```

---

## Step 7: Iteration Counter and "Can Anything Be Removed?" Gate

Track the iteration count per section. The count starts at 0 and increments on each
**Iterate** response.

**After 3 iterations on the same section without substantive change:**

"Substantive change" means the author's feedback produced a meaningfully different
draft (not just punctuation or whitespace). Read both drafts and judge whether the
content changed materially.

If 3 iterations have passed and the draft is not substantively different from the
first-shown draft, use AskUserQuestion before offering another Iterate option:

```
This section has been iterated 3 times without a substantive change.

Can anything be removed from this section to make it clearer or shorter?

  Trim        — yes, let's remove something; tell me what to cut
  Keep-as-is  — the section is correct; approve it as-is and move on
```

On **Trim**: capture what to cut, apply the cut, present the trimmed draft for one
final Approve / Iterate / Remove round.

On **Keep-as-is**: treat as Approve — commit the section and move on.

---

## Step 8: Commit Approved Sections to File

When the author approves a section (via Approve or Keep-as-is):

Use the **Edit tool** to perform a surgical replacement of only the approved section's
content in `docs/<page_name>.md`. Do NOT use the Write tool to rewrite the whole file
— that would clobber other sections.

The Edit operation replaces:
- The `<!-- TODO -->` marker (or the existing draft body) for this section heading
  with the approved prose.

All other sections — approved in earlier rounds, TODO placeholders for later sections,
and the file's H1 and front matter — are preserved verbatim.

**Preservation contract:** prior approved sections are never touched by subsequent
section drafts. Each Edit call is scoped to one section's body only.

After each Edit, confirm the write succeeded by checking the Edit tool's result.

---

## Step 9: Loop — Next Unwritten Section

After committing an approved section, move to the next unwritten section in the
confirmed order (from Step 5).

Repeat Steps 6–8 for each unwritten section.

If the author responds **Remove** in Step 6d:
- Use the Edit tool to delete the section heading and its body from the file.
- Leave the rest of the file intact.
- Move to the next unwritten section.

The loop ends when:
- All confirmed sections have been approved or removed, OR
- The author explicitly asks to pause (type "stop" or "pause" at any AskUserQuestion).

---

## Step 10: Final Report

After the loop ends, print a summary:

```
write mode complete — docs/<page_name>.md

Sections drafted and approved:
  ## Install           ← approved; written to file
  ## Verify            ← approved; written to file

Sections removed:
  ## Next steps        ← removed by author

Sections still unwritten (session paused):
  (none)

Sections with [NEEDS] markers (facts outstanding):
  ## Verify — [NEEDS: minimum runtime version]

Next steps:
  - Fill in [NEEDS] markers before running /doc-product review.
  - Run /doc-product review to test this page against reader personas.
```

Adjust to reflect what was actually drafted, approved, removed, and left outstanding.

---

## Quality and Safety Contract

- This mode NEVER fabricates content. Every fact in a drafted section comes from the
  repository or from an explicit author answer obtained via AskUserQuestion.
- This mode NEVER loses prior approved sections. Every Edit call is surgical — one
  section body at a time. No Write-tool whole-file rewrites.
- AskUserQuestion is used at every author decision point: section structure confirm
  (Step 5), gap surfacing (Step 6b), section review (Step 6d), iteration gate (Step 7),
  and non-existent-page handling (Step 2).
- No backup or recovery mechanisms are introduced. Surgical edits and the author's git
  history are the recovery path.
- No CLI flags beyond the page name are supported. Do NOT add `--type`, `--page`,
  `--persona`, or any other flag not specified here.

---

## Error Handling Reference

| Situation | Behaviour |
|---|---|
| No page name provided | AskUserQuestion for page name before proceeding |
| `docs/<page_name>.md` does not exist | Route to plan mode; stop |
| `docs/<page_name>.md` is missing a section heading from conventions | Surface as "missing" in Step 4; include in proposal |
| Page type not in `reference/conventions.md` | AskUserQuestion: closest type or custom list |
| Required fact missing from repo | AskUserQuestion (Step 6b); no fabrication |
| Author pauses the session | Stop loop; report what is drafted and what remains |
| 3 iterations without substantive change | "Can anything be removed?" gate (Step 7) |
| Edit tool failure | Report the error; do not proceed to next section without author acknowledgment |

---

## Examples

### Example 1: Empty installation placeholder

**Invocation:** `/doc-product write installation`

```
Current state of docs/installation.md:

  Approved (will be preserved):
    (none — file is a full placeholder)

  Unwritten (ready to draft):
    ## Prerequisites     ← TODO placeholder
    ## Install           ← TODO placeholder
    ## Verify            ← TODO placeholder
    ## Next steps        ← TODO placeholder

Proposed section structure (from reference/conventions.md — installation type):

  ## Prerequisites
    Lists software, OS, and account requirements the reader must have.

  ## Install
    The exact command or UI steps to put the software on the machine.

  ## Verify
    How to confirm the installation succeeded without contacting the author.

  ## Next steps
    Points to configuration or a quickstart.

Proceed with this structure? (yes / adjust / skip to a specific section)
```

Author answers **yes**. Mode begins Step 6 with the first section (Prerequisites).

Before drafting Prerequisites, mode checks the repo for prerequisite information.
If not found:

```
To draft the Prerequisites section I need:
  1. What runtime or tool must be installed before this software (e.g. Node.js 18+, Python 3.11+)?
  2. Any OS restriction (macOS only? Linux supported?)?

These were not found in the repository. Please provide them.
```

Author provides answers. Mode drafts Prerequisites using only those answers.

### Example 2: Iterated section triggers the removal gate

**Invocation:** `/doc-product write troubleshooting`

After 3 iterations on `## Common errors` without substantive change:

```
This section has been iterated 3 times without a substantive change.

Can anything be removed from this section to make it clearer or shorter?

  Trim        — yes, let's remove something; tell me what to cut
  Keep-as-is  — the section is correct; approve it and move on
```

### Example 3: Non-existent page

**Invocation:** `/doc-product write migration`

```
docs/migration.md does not exist.

write mode requires a placeholder file to be present before drafting can begin.
Run `/doc-product plan` first to create the docs/ skeleton, which will produce
the placeholder for migration.md. Then return to `/doc-product write migration`.
```

Mode stops. No files are written.
