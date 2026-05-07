# Configuration Page Template

This file is the **canonical template and renderer contract** for the Configuration page
produced by `modes/extract.md`. It is a reference document consumed by the extract-mode
renderer at render time — never executed by Bash, never written to disk.

The renderer reads a TSV produced by one of the three parser scripts
(`parse-ts-settings.sh`, `parse-jsonschema.sh`, `parse-pydantic.sh`) and transforms it
into a Markdown configuration page for the target repository.

---

## Renderer Contract

### Input format

The TSV emitted by all three parsers shares a common header and four columns:

```
name<TAB>type<TAB>default<TAB>description
```

- **name** — the field or property name as it appears in source code.
- **type** — the declared type (e.g. `string`, `number`, `'small' | 'large'`).
- **default** — the default value as a literal, or a marker (see Markers section below).
- **description** — the JSDoc comment / docstring for the field, or a marker.

### Output format

The renderer produces a single Markdown file (`docs/configuration.md`) with the
following structure:

1. **H1 title** — `# Configuration`
2. **Intro paragraph** — describes the purpose of the page, when a user should consult it,
   and that the source of truth is the settings file (not this page). See the intro
   paragraph template below.
3. **Markdown table** — one row per setting, four columns: `Name`, `Type`, `Default`,
   `Description` (in that order).

The renderer MUST NOT add extra prose, invent defaults, or invent descriptions.
Its only job is to transform the TSV faithfully into the table structure.

---

## Markers — Verbatim Preservation Rule

The parsers emit three sentinel markers when source information is missing or ambiguous.
The renderer **MUST preserve every marker verbatim** — it must never replace, paraphrase,
or fabricate content in place of a marker. Authors use these markers as a checklist to
complete the documentation manually after extraction.

| Marker | Meaning | Which column |
|--------|---------|--------------|
| `[NEEDS DESCRIPTION]` | The field has no JSDoc / docstring. Author must write one. | `description` |
| `[NEEDS REVIEW]` | The type expression is too complex to parse reliably (generics, mapped types, intersections). Author must verify the emitted type. | `type` |
| `[NEEDS DEFAULT]` | No default value was found in the paired const / schema. Author must confirm the actual default. | `default` |

**Rule:** if a marker appears in the input TSV, it must appear identically in the output
Markdown. The renderer never fabricates replacement content for a marker cell.

---

## Configuration Page Structure

### H1 Title

```markdown
# Configuration
```

### Intro Paragraph Template

The intro paragraph is a standard block. The renderer emits it verbatim (substituting
the plugin name if available, otherwise leaving the placeholder):

```markdown
This page documents every configuration setting available in {{plugin_name}}. Each row
describes a single field: its name, expected type, default value, and what it controls.
Fields marked `[NEEDS DESCRIPTION]` or `[NEEDS REVIEW]` require author attention before
the documentation is complete. Fields marked `[NEEDS DEFAULT]` have no recorded default
and should be confirmed against the source code.
```

If `{{plugin_name}}` cannot be determined from context, the renderer substitutes
`the plugin` as a neutral fallback.

### Table Header

```markdown
| Name | Type | Default | Description |
|------|------|---------|-------------|
```

Column order is fixed: `Name`, `Type`, `Default`, `Description`.

### Table Row Format

```markdown
| `{{name}}` | `{{type}}` | `{{default}}` | {{description}} |
```

- **Name cell** — always wrapped in backticks.
- **Type cell** — always wrapped in backticks. The marker `[NEEDS REVIEW]` is no
  exception — the type cell always gets backtick wrapping, so emit: `| \`[NEEDS REVIEW]\` |`.
- **Default cell** — wrapped in backticks when it is a literal value. If the default is
  `[NEEDS DEFAULT]`, emit the marker as-is without backtick wrapping: `| [NEEDS DEFAULT] |`.
- **Description cell** — plain text (no backtick wrapping). If the description is
  `[NEEDS DESCRIPTION]`, emit the marker as-is: `| [NEEDS DESCRIPTION] |`.

Pipe characters (`|`) inside a Type cell (e.g. union types like `'a' | 'b'`) MUST be
escaped as `\|` to prevent Markdown table breakage.

---

## Example Value Column — v1 Behaviour and v2 Deferral

### PRD F3 AC1 requirement

PRD Feature 3 AC1 specifies the configuration page should contain: name, type, default
value, JSDoc comment as description, **and example value**.

### v1 behaviour (current)

The parsers (T3.1/T3.2/T3.3) emit only four columns: `name`, `type`, `default`,
`description`. No fifth `example` column is produced in v1.

The v1 renderer therefore uses four columns only. The `default` value serves as the
implicit example in most cases (it is the representative starting point for the field).
There is no separate "Example" column in v1 output.

**Rationale:** Extracting a meaningful example distinct from the default requires either:
(a) an `@example` JSDoc tag that the parsers do not currently capture, or
(b) heuristic inference that risks fabricating misleading examples — violating the
    no-fabrication contract.

The four-column table is a correct, complete v1 output. The PRD F3 AC1 "example value"
gap is a known, accepted v1 limitation, not a defect.

### v2 enhancement path

A future T3.1 parser update may capture `@example` JSDoc tags and emit them as a fifth
`example` column. When that column is present, the renderer adds it as a fifth column
after `Description`.

Until the parsers emit `example` data, the renderer MUST NOT add an Example column or
populate it with guesses. Adding a column with fabricated examples would be worse than
omitting it.

**Open question (v2):** Should the `@example` extraction be per-tag (one row per
`@example` block) or collapsed to a single representative string? Defer to v2 design.

---

## Inline Fixture Example

This section shows the exact transformation the renderer performs, using the T3.4 test
fixture. Authors reading this template can verify their renderer implementation against it.

### Input TSV (`tests/fixtures/configuration/sample-settings.tsv`)

```
name	type	default	description
apiKey	string	''	The API key used to authenticate requests to the remote service.
timeout	number	[NEEDS DEFAULT]	[NEEDS DESCRIPTION]
retryPolicy	[NEEDS REVIEW]	'exponential'	The retry strategy applied on transient failures.
logLevel	'debug' | 'info' | 'warn' | 'error'	'info'	Controls the verbosity of log output.
```

### Expected output (`tests/fixtures/configuration/expected-configuration.md`)

```markdown
# Configuration

This page documents every configuration setting available in the plugin. Each row
describes a single field: its name, expected type, default value, and what it controls.
Fields marked `[NEEDS DESCRIPTION]` or `[NEEDS REVIEW]` require author attention before
the documentation is complete. Fields marked `[NEEDS DEFAULT]` have no recorded default
and should be confirmed against the source code.

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `apiKey` | `string` | `''` | The API key used to authenticate requests to the remote service. |
| `timeout` | `number` | `[NEEDS DEFAULT]` | [NEEDS DESCRIPTION] |
| `retryPolicy` | `[NEEDS REVIEW]` | `'exponential'` | The retry strategy applied on transient failures. |
| `logLevel` | `'debug' \| 'info' \| 'warn' \| 'error'` | `'info'` | Controls the verbosity of log output. |
```

Key points illustrated by this example:

- `apiKey` — fully populated row; all four cells have real values.
- `timeout` — both `[NEEDS DEFAULT]` and `[NEEDS DESCRIPTION]` appear verbatim; no fabrication.
- `retryPolicy` — `[NEEDS REVIEW]` appears verbatim in the Type cell; other cells are normal.
- `logLevel` — union type pipes escaped as `\|`; description and default are normal.

---

## Re-run Behaviour

When `extract` mode is run against a repo that already has `docs/configuration.md`, the
renderer MUST NOT overwrite silently. It produces the new Markdown, diffs it against the
existing file, and surfaces the diff for author review. Only the author explicitly
approves an overwrite. (Implementation: `modes/extract.md` T3.5.)

---

## Notes for `modes/extract.md` Implementation

When the extract mode renderer (T3.5) consumes this template:

1. Read the TSV from the parser script's stdout.
2. Skip the header row (`name<TAB>type<TAB>default<TAB>description`).
3. For each data row, split on TAB to get `(name, type, default, description)`.
4. Apply the per-cell escaping rules above (especially `|` → `\|` in the Type cell).
5. Emit the intro paragraph with plugin name substituted (or `the plugin` fallback).
6. Emit the table header.
7. Emit one table row per data row.
8. Check for existing `docs/configuration.md` — diff if present, write if absent.
