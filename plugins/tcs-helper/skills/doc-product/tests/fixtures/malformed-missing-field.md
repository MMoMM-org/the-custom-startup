# Malformed Fixture — Missing Required Field
# Persona is missing the "description" field.
# validate_personas_file should exit non-zero naming the persona and field.

```yaml
personas:
  - id: no-description-persona
    required: true
    questions:
      - id: some-question
        required: true
        text: "What does this do?"
        pages: [README.md]
```
