# `review` Mode — Persona-Driven Reader Test Orchestrator

**Invocation:** `/doc-product review [--page <name>] [--since <ref>]`

This mode runs parallel headless `claude -p` subprocesses against the project's documentation,
aggregates findings per persona, and renders a Reader-Test Gap Report inline in this conversation.
No files are written to disk (ADR-6).

---

## Step 1: Prerequisites

Before any subprocess call, verify the following. On any failure, stop and print the message below.
Do not proceed to Step 2.

**Check `claude` CLI:**

```bash
command -v claude >/dev/null 2>&1
```

If missing, output exactly:

```
review mode requires the `claude` CLI; install via `npm install -g @anthropic-ai/claude-code` and authenticate with `claude /login`
```

**Check `jq`:**

```bash
command -v jq >/dev/null 2>&1
```

If missing, output: `review mode requires jq; install with: brew install jq`

**Check git repo:**

```bash
git rev-parse --show-toplevel >/dev/null 2>&1
```

If not in a git repo, output: `review mode must be run from within a git repository`

---

## Step 2: Invoke the review helper

Invoke `bash scripts/run-review.sh` with any flags the user passed:

```bash
# No scope restriction
bash scripts/run-review.sh

# Page scope
bash scripts/run-review.sh --page claude-docs/installation.md

# Git-diff scope
bash scripts/run-review.sh --since <ref>

# Save merged persona file for inspection
bash scripts/run-review.sh --save-active-persona-file /tmp/active-personas.md
```

Capture both stdout (aggregate JSON) and exit code. The helper:

- Resolves the active persona set via `scripts/lib-personas.sh:resolve_active_persona_set`
- Builds the work plan (persona × question tuples filtered by scope)
- Runs each tuple via `scripts/reader-test.sh` in parallel (bounded by `READER_TEST_PARALLEL`, default 4)
- Writes per-tuple JSON output files to a tempdir
- Aggregates all results and emits a single JSON object to stdout
- Exits 0 on PASS, 1 on FAIL

**Aggregate JSON shape:**

```json
{
  "outcome": "PASS" | "FAIL",
  "persona_source": "defaults" | "project override at `.claude/doc-personas.md`",
  "pages_tested": ["claude-docs/foo.md", "..."],
  "tuples": [
    {
      "persona_id": "first-time-installer",
      "question_id": "install",
      "page_used": "claude-docs/installation.md",
      "found": "yes" | "partial" | "no",
      "answer": "...",
      "unclear": [],
      "guessed": [],
      "error": "<type string or absent>"
    }
  ]
}
```

---

## Step 3: Handle helper failure (prerequisites)

If `run-review.sh` exits with a message containing "requires the \`claude\` CLI" or any
prerequisite error (exit code non-zero, no JSON on stdout), forward the error message directly
to the user and stop. Do not attempt to render a gap report.

---

## Step 4: Parse the aggregate JSON

From the aggregate JSON produced by `run-review.sh`, extract:

- `outcome`: `"PASS"` or `"FAIL"`
- `persona_source`: label string
- `pages_tested`: array of path strings
- `tuples`: array of finding objects

Apply the aggregate algorithm from SDD §722-748:

1. Partition tuples: `infra_errors` = tuples where `.error` is set; `clean` = the rest.
2. Group `clean` tuples by `persona_id`.
3. For each persona group:
   - `required_questions` = tuples where the question's `required` field is `true` (from the personas file)
   - `pass_count` = count where `found == "yes"`
   - `fail_count` = count where `found` is `"partial"` or `"no"`
   - If `persona.required == true` AND `fail_count > 0`: `persona_status = "FAIL"`
   - Else: `persona_status = "PASS"` or `"(informational)"` (non-required)
4. `overall_outcome = "FAIL"` if any required persona has status `"FAIL"`; else `"PASS"`.
   - Infrastructure errors alone do NOT produce FAIL (Fixture-4 rule).

The `run-review.sh` helper already emits `outcome` per this algorithm. Trust its `outcome` field
unless you need to re-derive it for rendering.

---

## Step 5: Render the Gap Report inline

Render the gap report using the canonical schema in `templates/gap-report-template.md`.
Output Markdown **directly into this conversation** — do not use the `Write` tool.

Substitute all `{{placeholder}}` tokens:

| Placeholder | Source |
|---|---|
| `{{run_timestamp}}` | Current UTC time when the run started (ISO 8601) |
| `{{pages_tested}}` | `aggregate.pages_tested` joined with `, ` |
| `{{persona_count}}` | Number of distinct persona IDs in the tuples |
| `{{persona_source_label}}` | `aggregate.persona_source` |
| `{{outcome}}` | `aggregate.outcome` |
| `{{summary_rows}}` | One row per persona — see below |
| `{{failing_required_items}}` | Required-fail finding blocks — see below |
| `{{optional_items}}` | Informational finding blocks — see below |
| `{{infra_error_items}}` | Infrastructure error blocks — see below |

**Summary row format** (one row per persona, in source order from the personas file):

```markdown
| {{persona_id}} | {{required_flag}} | {{pass_count}} / {{total_required_questions}} | {{status_cell}} |
```

- `required_flag`: `yes` if `persona.required == true`; `no` otherwise
- `pass_count`: clean findings where `found == "yes"` for required questions
- `total_required_questions`: count of required questions (infra errors excluded)
- `status_cell`: `**FAIL**` (required persona with any fail), `PASS` (required persona, no fails), or `(informational)` (non-required persona)

**Failing required findings** — one block per `clean` tuple where `persona.required == true`
AND `question.required == true` AND `found` is `"partial"` or `"no"`. Sorted: `persona_id` ASC,
then `question_id` ASC.

**Optional findings** — one block per `clean` tuple where `persona.required == false`
OR `question.required == false`, AND `found` is not `"yes"`. Sorted same way.

**Infrastructure errors** — one block per tuple where `.error` is set. Sorted same way.

Collapse (omit heading + body) any section with zero items.

---

## Step 6: Emit non-interactive failure signal

If `outcome == "FAIL"`, the first line of the rendered gap report MUST be:

```markdown
<!-- DOC-PRODUCT-REVIEW: FAIL -->
```

This marker allows non-interactive callers (CI scripts, outer agents) to grep the output
for failure detection without parsing the full Markdown. The `run-review.sh` helper also
exits 1 on FAIL for Bash-level callers.

If `outcome == "PASS"`:

```markdown
<!-- DOC-PRODUCT-REVIEW: PASS -->
```

---

## Examples

### Example 1: PASS run

**Invocation:** `/doc-product review`

**Expected output (abridged):**

```markdown
<!-- DOC-PRODUCT-REVIEW: PASS -->

# Reader-Test Gap Report

**Run:** 2026-05-06T14:32:00Z
**Pages tested:** README.md, claude-docs/installation.md, claude-docs/configuration.md, claude-docs/troubleshooting.md
**Personas active:** 4 (defaults)
**Outcome:** PASS

## Summary

| Persona | Required | Pass / Total | Status |
|---------|----------|--------------|--------|
| first-time-installer | yes | 2 / 2 | PASS |
| config-explorer | yes | 1 / 1 | PASS |
| troubleshooter | yes | 1 / 1 | PASS |
| migrator | no | 0 / 0 | (informational) |
```

No `## Failing required findings` section (zero fails).

### Example 2: FAIL run

**Invocation:** `/doc-product review`

**Expected output (abridged):**

```markdown
<!-- DOC-PRODUCT-REVIEW: FAIL -->

# Reader-Test Gap Report

**Run:** 2026-05-06T14:35:00Z
**Pages tested:** README.md, claude-docs/installation.md, claude-docs/troubleshooting.md
**Personas active:** 4 (defaults)
**Outcome:** FAIL

## Summary

| Persona | Required | Pass / Total | Status |
|---------|----------|--------------|--------|
| first-time-installer | yes | 2 / 2 | PASS |
| config-explorer | yes | 1 / 1 | PASS |
| troubleshooter | yes | 0 / 1 | **FAIL** |
| migrator | no | 0 / 0 | (informational) |

## Failing required findings

### troubleshooter — `common-error`
**Page:** `claude-docs/troubleshooting.md`
**Question:** "Pick the first error message or failure scenario described in the document. What does it mean and how do I fix it?"
**Found:** `no`
**Reader's answer (verbatim):** "The document does not describe any error messages."
**Unclear:** ["what errors can occur", "how to recover"]
**Guessed:** []

**Suggested fix (author):** Add a section answering this question to `claude-docs/troubleshooting.md`. Re-run `/doc-product review`.
```

---

## Error Handling Reference

| Situation | Behaviour |
|---|---|
| `claude` CLI missing | Stop at Step 1; print setup message; no subprocess called |
| `jq` missing | Stop at Step 1; print install message |
| Not in a git repo | Stop at Step 1; print message |
| Persona file malformed | `run-review.sh` exits non-zero with validation error; forward to user |
| All tuples are infra errors | outcome = PASS (Fixture-4 rule); infra section populated |
| `--page` path not in any question's pages | Zero tuples run; outcome = PASS; empty summary |
| `run-review.sh` exits 1 with JSON on stdout | Render the gap report normally; outcome is FAIL |
