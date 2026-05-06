# Reader-Test Personas Fixture
# Minimal 1-persona × 1-question fixture for reader-test.sh tests.
# Multi-page question: README.md (exists) + missing.md (absent from fixture repo).

```yaml
personas:
  - id: test-reader
    required: true
    description: |
      A reader who wants to understand what this software does.
    questions:
      - id: what-is-it
        required: true
        text: "What does this software do?"
        pages: [README.md, missing.md]
```
