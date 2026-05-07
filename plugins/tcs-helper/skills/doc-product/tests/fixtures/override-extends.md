# Override Extends Fixture
# Has extends: defaults directive — merges with built-in defaults.
# 1 new persona + 1 override of "migrator" (changes required: false -> true).

```yaml
extends: defaults

personas:
  - id: migrator
    required: true
    description: |
      Coming from a similar tool. Wants to find equivalents.
      This version marks migrator as required (override of the default).
    questions:
      - id: migration-path
        required: true
        text: "If the document references migrating from another tool, summarise how the migration works. If no migration is described, answer 'no migration documented'."
        pages: [README.md, claude-docs/migration.md]

  - id: api-consumer
    required: false
    description: |
      Developer integrating with this tool's API or extension points.
    questions:
      - id: api-entry
        required: false
        text: "What APIs or extension points does this tool expose?"
        pages: [claude-docs/api.md]
```
