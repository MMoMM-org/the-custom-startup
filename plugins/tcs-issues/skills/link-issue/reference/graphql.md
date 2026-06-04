# Sub-Issue GraphQL Recipes

GitHub sub-issues key on **node-IDs**, not issue numbers. Resolve numbers first:

```bash
gh issue view <number> --repo "<owner>/<repo>" --json id -q .id   # -> "I_kw..."
```

Node-IDs are inlined directly into each query below — no `$var: ID!` variable declarations.
This keeps the queries free of the `!` non-null marker, which zsh mangles to `\!` when the
query is passed through the shell. Node-IDs are opaque gh-issued tokens, so inlining is safe.
A default authenticated `gh` token is sufficient for all four operations.

## Link a child under a parent

```bash
gh api graphql -f query='
mutation {
  addSubIssue(input: { issueId: "<parentNodeId>", subIssueId: "<childNodeId>" }) {
    issue    { number title }
    subIssue { number title }
  }
}'
```

## Unlink a child from its parent

```bash
gh api graphql -f query='
mutation {
  removeSubIssue(input: { issueId: "<parentNodeId>", subIssueId: "<childNodeId>" }) {
    issue    { number title }
    subIssue { number title }
  }
}'
```

## List children and parent of an issue

```bash
gh api graphql -f query='
query {
  node(id: "<issueNodeId>") {
    ... on Issue {
      number
      title
      parent { number title state }
      subIssues(first: 50) { nodes { number title state } }
    }
  }
}'
```

`parent` is `null` when the issue has no parent. `subIssues.nodes` is empty when it has no
children. Raise `first` only if an issue is expected to have more than 50 children.

## Reorder a child (optional)

```bash
gh api graphql -f query='
mutation {
  reprioritizeSubIssue(input: { issueId: "<parentNodeId>", subIssueId: "<childNodeId>", afterId: "<afterChildNodeId>" }) {
    issue { number }
  }
}'
```

Drop the `afterId` field to move the child to the top of the list.
