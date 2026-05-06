# Malformed Fixture — No questions: key
# Persona has NO "questions:" key at all (distinct from malformed-zero-questions.md
# which has "questions:" with an empty body).
# validate_personas_file should exit non-zero with "no questions list" error only;
# it must NOT also emit "zero questions" (that error is redundant / misleading here).

```yaml
personas:
  - id: no-questions-key-persona
    required: true
    description: |
      A persona that omits the questions key entirely — invalid per the schema.
```
