# tcs-issues

GitHub issue lifecycle and native sub-issue (parent/child) management for Claude Code.

Complements `tcs-workflow:/pickup` — which *reads* the GitHub Projects (v2) board to orient a
session — by *writing* to it: creating issues onto the board and linking the issue graph.

## Skills

| Skill | What it does |
|-------|--------------|
| `/tcs-issues:issue` | Create, list, close, and comment on issues. New issues are placed on the repo's Project (v2) board with a status and labels. Confirms before every write. |
| `/tcs-issues:link-issue` | Link / unlink native sub-issues (parent ↔ child) and list an issue's children and parent epic, via the GitHub GraphQL sub-issue API. |

## Hooks

Active in every repository where the plugin is installed.

| Event | Script | What it does |
|-------|--------|--------------|
| PreToolUse (Bash) | `scripts/require-issue-comments.sh` | Denies `gh issue view` when it reads an issue's text without its comments: a plain view, or `--json` with `body` but not `comments`. Add `--comments`, or `comments` to the field list. `--web` and status-only reads such as `--json state` pass. |
| PostToolUse (Bash) | `scripts/nudge-issue-list.sh` | After `gh issue list`, adds a note that titles alone are no basis for a recommendation, and that each issue should be read with `--comments` first. Never blocks. |

An issue's title and body go stale; its comments record what was already done or decided.
Both hooks fail open: malformed input or a missing `jq` lets the command run.

## Requirements

- [`gh`](https://cli.github.com/) installed and authenticated (`gh auth login`).
- `jq` for the hooks; without it they let every command through.
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
