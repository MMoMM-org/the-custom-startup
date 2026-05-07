# Override Replace Fixture
# No extends: directive — entirely replaces defaults.
# 3 personas.

```yaml
personas:
  - id: new-user
    required: true
    description: |
      Brand new user seeing the product for the first time.
    questions:
      - id: what-is-it
        required: true
        text: "What does this product do?"
        pages: [README.md]

  - id: power-user
    required: true
    description: |
      Experienced user who wants to customise the tool deeply.
    questions:
      - id: advanced-config
        required: true
        text: "What advanced configuration options are available?"
        pages: [claude-docs/configuration.md]
      - id: scripting
        required: false
        text: "Can I script or automate this tool?"
        pages: [claude-docs/scripting.md]

  - id: contributor
    required: false
    description: |
      Developer who wants to contribute code or fix bugs.
    questions:
      - id: dev-setup
        required: false
        text: "How do I set up a development environment?"
        pages: [CONTRIBUTING.md]
```
