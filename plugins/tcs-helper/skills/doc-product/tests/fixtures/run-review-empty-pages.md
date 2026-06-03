# Run-Review Empty-Pages Fixture
# Valid personas whose questions carry an empty pages list.
# Passes validate_personas_file (the `pages:` key is present) yet yields zero
# (persona, question, page) tuples, so the work plan comes out empty.
# Used by S8 to exercise the zero-coverage guard: an unfiltered run that tests
# nothing must fail loudly, never report a vacuous PASS. This is the same
# observable condition the mawk interval-regex bug produced in the wild.

```yaml
personas:
  - id: p1
    required: true
    description: |
      A first-time reader who wants basic setup instructions.
    questions:
      - id: q1
        required: true
        text: "How do I install this software?"
        pages: []
```
