# Run-Review Test Personas Fixture
# 2 personas × 3 questions for run-review.sh pressure tests.
# p1 (required): 2 required questions (q1 on docs/installation.md, q2 on docs/configuration.md)
# p2 (non-required): 1 non-required question (q3 on docs/installation.md)

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
        pages: [docs/installation.md]
      - id: q2
        required: true
        text: "What is the main configuration option?"
        pages: [docs/configuration.md]

  - id: p2
    required: false
    description: |
      An optional reader interested in installation details.
    questions:
      - id: q3
        required: false
        text: "Are there any prerequisites for installation?"
        pages: [docs/installation.md]
```
