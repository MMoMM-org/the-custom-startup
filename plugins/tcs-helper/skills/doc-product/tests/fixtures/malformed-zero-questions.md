# Malformed Fixture — Zero Questions
# Persona has an empty questions list (no entries).
# validate_personas_file should exit non-zero naming this persona.

```yaml
personas:
  - id: empty-persona
    required: true
    description: |
      A persona with no questions — this is invalid per the schema.
    questions:
```
