# Gap Report Template — doc-product Skill

This file is the **canonical schema and template** for the Reader-Test Gap Report produced by
`modes/review.md`. It is a reference document consumed by the review-mode orchestrator at
render time — never executed by Bash, never written to disk.

**ADR-6 reminder:** the gap report is rendered inline in the parent conversation only.
`modes/review.md` reads this file and emits Markdown directly into the chat thread.

---

## Placeholders

The following `{{placeholder}}` tokens appear in the schema below. The renderer
(`modes/review.md`) substitutes each one before emitting output.

| Placeholder | Type | Description |
|---|---|---|
| `{{run_timestamp}}` | ISO 8601 string | UTC timestamp when the review run started, e.g. `2026-05-06T14:32:00Z` |
| `{{pages_tested}}` | comma-separated paths | All page paths actually evaluated, e.g. `README.md, claude-docs/installation.md` |
| `{{persona_count}}` | integer | Total number of active personas |
| `{{persona_source_label}}` | string | Either `defaults` (built-in `personas-default.md`) or `project override at \`.claude/doc-personas.md\`` |
| `{{outcome}}` | `PASS` or `FAIL` | FAIL when any required persona has at least one required-question fail; otherwise PASS |
| `{{summary_rows}}` | rendered table rows | One row per persona — see Summary Row Format below |
| `{{failing_required_items}}` | rendered finding blocks | One block per required-fail finding — see Failing Finding Format below |
| `{{optional_items}}` | rendered finding blocks | One block per informational finding — see Optional Finding Format below |
| `{{infra_error_items}}` | rendered error blocks | One block per infrastructure error — see Infrastructure Error Format below |

---

## Conditional Sections

The renderer collapses sections whose data set is empty. Rules:

| Section | Condition to include | Condition to collapse |
|---|---|---|
| Summary table | **Always** present | Never collapsed |
| `## Failing required findings` | At least one finding where `persona.required == true` AND `question.required == true` AND `found` is `"no"` or `"partial"` AND `finding.error` is absent | Collapse (omit heading + body) when zero such findings |
| `## Optional findings (informational)` | At least one finding where (`persona.required == false` OR `question.required == false`) AND `found` is not `"yes"` AND `finding.error` is absent | Collapse when zero such findings |
| `## Infrastructure errors (if any)` | At least one finding where `finding.error` is present | Collapse when zero such findings |

### Zero-fail run note

When a run produces zero failures and zero infra errors the rendered output is:
header block + Summary table only. The summary still communicates the full picture —
no extra sections are needed, and their absence is itself meaningful signal.

---

## Deterministic Ordering

The renderer MUST apply the following sort order before rendering:

- **Failing required findings:** sorted by `persona_id` ASC, then `question_id` ASC (both alphabetical).
- **Optional findings:** sorted by `persona_id` ASC, then `question_id` ASC.
- **Infrastructure errors:** sorted by `persona_id` ASC, then `question_id` ASC.
- **Summary table rows:** personas listed in the order they appear in the active personas file (preserving author intent), not alphabetically.

---

## Summary Row Format

One Markdown table row per persona:

```markdown
| {{persona_id}} | {{required_flag}} | {{pass_count}} / {{total_required_questions}} | {{status_cell}} |
```

| Sub-placeholder | Value |
|---|---|
| `{{persona_id}}` | The persona's `id` field, e.g. `first-time-installer` |
| `{{required_flag}}` | `yes` if `persona.required == true`; `no` if `false` |
| `{{pass_count}}` | Count of required questions where `found == "yes"` (infra errors excluded) |
| `{{total_required_questions}}` | Count of required questions for this persona (infra errors excluded) |
| `{{status_cell}}` | See Status Cell Rules below |

**Status Cell Rules:**

- Required persona, fail_count > 0: `**FAIL**`
- Required persona, fail_count == 0: `PASS`
- Non-required persona (regardless of outcome): `(informational)`

---

## Failing Finding Format

One block per required-fail finding. Each block is separated by a blank line.

```markdown
### {{persona_id}} — `{{question_id}}`
**Page:** `{{page}}`
**Question:** "{{question_text}}"
**Found:** `{{found}}`
**Reader's answer (verbatim):** "{{answer}}"
**Unclear:** {{unclear_list}}
**Guessed:** {{guessed_list}}

**Suggested fix (author):** Add a section answering this question to `{{page}}`. Re-run `/doc-product review`.
```

| Sub-placeholder | Value |
|---|---|
| `{{persona_id}}` | Persona's `id` field |
| `{{question_id}}` | Question's `id` field |
| `{{page}}` | The `page_used` field from the finding (the page that was evaluated) |
| `{{question_text}}` | Full question text from the persona definition |
| `{{found}}` | The `found` field: `"yes"`, `"partial"`, or `"no"` |
| `{{answer}}` | The reader's verbatim answer string |
| `{{unclear_list}}` | JSON array notation, e.g. `["how to recover", "what codes exist"]`; `[]` when empty |
| `{{guessed_list}}` | JSON array notation, e.g. `["step 2"]`; `[]` when empty |

The suggested-fix line is a static template. Authors reading the report are expected to refine
it with specifics. The renderer does not attempt to generate project-specific fix guidance.

---

## Optional Finding Format

Same structure as the Failing Finding Format, with one difference: the heading uses the
marker `(informational)` appended so it is visually distinct.

```markdown
### {{persona_id}} — `{{question_id}}` (informational)
**Page:** `{{page}}`
**Question:** "{{question_text}}"
**Found:** `{{found}}`
**Reader's answer (verbatim):** "{{answer}}"
**Unclear:** {{unclear_list}}
**Guessed:** {{guessed_list}}
```

No "Suggested fix" line for informational findings — they are non-blocking.

---

## Infrastructure Error Format

One block per finding where `finding.error` is present.

```markdown
### {{persona_id}} — `{{question_id}}`
**Page(s):** `{{pages_list}}`
**Error type:** {{error_type}}
**Detail:** {{error_detail}}
**Suggestion:** Re-run with reduced parallelism or check `claude` CLI authentication.
```

| Sub-placeholder | Value |
|---|---|
| `{{pages_list}}` | Comma-separated list of pages that were being evaluated when the error occurred |
| `{{error_type}}` | One of: `timeout`, `unparseable_response`, `auth_failure`, `other` |
| `{{error_detail}}` | The raw error string from the `error` field, truncated to 200 characters |

Infrastructure errors are NOT counted in the pass/fail totals in the Summary table.
They are excluded from the persona's `pass_count` and `total_required_questions`.

---

## Canonical Schema (complete rendered example)

```markdown
# Reader-Test Gap Report

**Run:** {{run_timestamp}}
**Pages tested:** {{pages_tested}}
**Personas active:** {{persona_count}} ({{persona_source_label}})
**Outcome:** {{outcome}}

## Summary

| Persona | Required | Pass / Total | Status |
|---------|----------|--------------|--------|
{{summary_rows}}

## Failing required findings

{{failing_required_items}}

## Optional findings (informational)

{{optional_items}}

## Infrastructure errors (if any)

{{infra_error_items}}
```

The three optional sections (`## Failing required findings`, `## Optional findings`,
`## Infrastructure errors`) are omitted entirely (heading and body) when their data set is empty.

---

## Conditional Walkthrough — Fixture Verification

These fixtures document the expected rendering behaviour. T2.5 must produce output
matching each description.

### Fixture 1 — All-pass

**Input:** 4 personas (first-time-installer, config-explorer, troubleshooter = required;
migrator = non-required). All required questions return `found: "yes"`. Migrator's
single question returns `found: "yes"`.

**Expected output:**
- Header block with `Outcome: PASS`
- Summary table: all required personas show `PASS`; migrator shows `(informational)`
- NO `## Failing required findings` section
- NO `## Optional findings (informational)` section (migrator also passed)
- NO `## Infrastructure errors` section

### Fixture 2 — Required fail

**Input:** troubleshooter's `common-error` question returns `found: "no"`. All other
required questions return `found: "yes"`.

**Expected output:**
- Header block with `Outcome: FAIL`
- Summary table: troubleshooter row shows `**FAIL**`; others show `PASS`
- `## Failing required findings` section with exactly one block:
  `### troubleshooter — \`common-error\``
- NO `## Optional findings (informational)` section
- NO `## Infrastructure errors` section

### Fixture 3 — Mixed (required fail + optional informational + infra error)

**Input:** troubleshooter `common-error` returns `found: "no"` (required fail).
Migrator `migration-path` returns `found: "partial"` (non-required = informational).
Config-explorer `setting-impact` encounters a timeout (non-required question, infra error).

**Expected output:**
- Header block with `Outcome: FAIL`
- Summary table: troubleshooter = `**FAIL**`; config-explorer = `PASS` (required question
  `setting-purpose` passed; `setting-impact` is non-required and errored so excluded from count);
  migrator = `(informational)`
- `## Failing required findings` — one block for troubleshooter/common-error
- `## Optional findings (informational)` — one block for migrator/migration-path
- `## Infrastructure errors` — one block for config-explorer/setting-impact timeout
- Section order: required-fail → optional → infra (matches schema order)

### Fixture 4 — Infra-only (all subprocesses timed out)

**Input:** Every persona × question call returns an infrastructure error (timeout).

**Expected output:**
- Header block with `Outcome: PASS` (no required finding failed — errors are not failures)
- Summary table: all personas show `0 / 0` (zero evaluable questions) and `PASS` (required)
  or `(informational)` (non-required). No persona can be marked FAIL from infra errors alone.
- NO `## Failing required findings` section
- NO `## Optional findings (informational)` section
- `## Infrastructure errors` section lists every timed-out tuple
- Suggestion line present on each error block

> **Rationale for Fixture 4 outcome = PASS:** an infra error means the test did not run,
> not that the documentation failed. The author should re-run after resolving the infra issue.
> Marking FAIL on untested questions would produce false-positive gate failures in CI.
