# tcs-issues

GitHub issue lifecycle and native sub-issue (parent/child) management for Claude Code.

Complements `tcs-workflow:/pickup` — which *reads* the GitHub Projects (v2) board to orient a
session — by *writing* to it: creating issues onto the board and linking the issue graph.

## Skills

| Skill | What it does |
|-------|--------------|
| `/tcs-issues:issue` | Create, list, close, and comment on issues. New issues are placed on the repo's Project (v2) board with a status and labels. Confirms before every write. |
| `/tcs-issues:link-issue` | Link / unlink native sub-issues (parent ↔ child) and list an issue's children and parent epic, via the GitHub GraphQL sub-issue API. |

## Requirements

- [`gh`](https://cli.github.com/) installed and authenticated (`gh auth login`).
- Run from inside a git repository — `owner/repo` is auto-detected via `gh repo view`.
- Board placement (`/issue create`) resolves the Project number from `$ARGUMENTS`, the
  `[tcs] project` key in `startup.toml`, or auto-detection — the same order as `/pickup`.

## Install

```
/plugin install tcs-issues@the-custom-startup
```

## Notes

Sub-issue relationships have no first-class `gh` subcommand; `/link-issue` drives the GraphQL
`addSubIssue` / `removeSubIssue` mutations directly. The verified recipes live in
[`skills/link-issue/reference/graphql.md`](skills/link-issue/reference/graphql.md).
