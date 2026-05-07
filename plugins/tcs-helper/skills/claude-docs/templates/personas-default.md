# Default Personas — claude-docs Skill

This file defines the built-in reader personas used by the `claude-docs review` mode.
Each persona drives a set of questions that are tested against the project's documentation
via headless `claude -p` instances (one invocation per persona × question × pages set).

## Relation to Project Overrides

Projects may override these defaults by creating `.claude/doc-personas.md` at their repo root.
The override file **replaces** this file entirely (clean override). To extend rather than replace,
add `extends: defaults` as the first line of the override file's YAML body.

See ADR-4 in the claude-docs SDD (spec 010-doc-product-skill) for the full override mechanism rationale.

## Usage Notes

- `pages:` paths are resolved relative to the repo root (`git rev-parse --show-toplevel`).
- Pages that do not exist in the target repo are silently skipped at runtime.
- Generic language is intentional: the reader (`claude -p`) extracts project-specific framing
  from the document content itself. No persona text refers to a specific technology, OS, or
  project type (e.g. "Obsidian plugin", "Python CLI", "macOS"). Project-local overrides exist
  for edge cases where these defaults are too vague.

## Canonical Persona Definitions

```yaml
personas:
  - id: first-time-installer
    required: true
    description: |
      Has never used this software. Wants to install it and verify it
      works. Knows their operating system but is not the project's developer.
    questions:
      - id: install
        required: true
        text: "How do I install this, step by step?"
        pages: [README.md, docs/installation.md]
      - id: verify-install
        required: true
        text: "After installing, how do I verify it is running correctly?"
        pages: [README.md, docs/installation.md]

  - id: config-explorer
    required: true
    description: |
      Has the software installed and is configuring it for their use case.
      Wants to understand a setting before changing it.
    questions:
      - id: setting-purpose
        required: true
        text: "Pick the most prominent configuration option in the document. What does it do, and what is its default?"
        pages: [docs/configuration.md]
      - id: setting-impact
        required: false
        text: "For that same setting, what happens if I leave it at its default?"
        pages: [docs/configuration.md]

  - id: troubleshooter
    required: true
    description: |
      Hit an error. Has the software installed and roughly configured.
      Wants to recover without contacting the author.
    questions:
      - id: common-error
        required: true
        text: "Pick the first error message or failure scenario described in the document. What does it mean and how do I fix it?"
        pages: [docs/troubleshooting.md]

  - id: migrator
    required: false
    description: |
      Coming from a similar tool. Wants to find equivalents.
    questions:
      - id: migration-path
        required: false
        text: "If the document references migrating from another tool, summarise how the migration works. If no migration is described, answer 'no migration documented'."
        pages: [README.md, docs/migration.md]
```

## Schema Notes

- `personas[].id` — unique identifier, kebab-case. Referenced in review output and CI gate filtering.
- `personas[].required` — when `true`, the review fails if this persona's required questions score below threshold.
- `personas[].description` — fed verbatim to `claude -p` as the PERSONA field. Generic language only.
- `questions[].id` — unique within the persona. Appears in the structured report.
- `questions[].required` — when `true`, a `"found": "no"` result on this question is a blocking gap.
- `questions[].text` — the question fed to `claude -p`. Generic language only; no technology-specific terms.
- `questions[].pages` — list of doc paths (relative to repo root) concatenated as the document corpus
  for this question. Includes `README.md` for navigation-style questions and the topic page for
  content-specific questions. Authors can override per-question in `.claude/doc-personas.md` for
  projects with non-standard layouts.
