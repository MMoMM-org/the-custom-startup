# ask-guard — a human in the loop for irreversible actions

`ask-guard.sh` is an opt-in PreToolUse hook. When a Bash command or a file
write matches a rule the repo lists, Claude Code asks the user before it runs.
It never denies: the user decides. Without a config file it does nothing.

## What goes wrong

Some actions cannot be undone, or cost a lot when they go wrong:
`terraform apply` or `destroy`, `pulumi up`, `kubectl delete` against a
production cluster, a production database migration, an IAM or credential
change, an edit to an infrastructure definition. With broad Bash permissions,
or in auto mode, an agent can run them in the middle of a task, and nobody
sees them until afterwards.

## How to detect

The repo has no `.githooks/ask-guard.conf`, yet its sessions run infra, DB or
IAM tooling. Or the audit log (`overrides.jsonl` under the plugin data dir)
shows `"hook":"ask-guard"` rows for actions nobody remembers approving.

## Fix

Copy the example that `git-setup` installs and uncomment the rules you need:

```
cp .githooks/ask-guard.conf.example .githooks/ask-guard.conf
```

One rule per line:

| Line | Matches |
|---|---|
| `command <NAME> <POSIX ERE>` | each command of a Bash call, with quoted text blanked first (`echo "terraform apply"` does not match; `cd infra && terraform apply` and `bash -c 'terraform apply'` do) |
| `path <NAME> <glob>` | the repo-relative path of an Edit, Write or NotebookEdit; `*` also crosses `/`, so `*.tf` matches `infra/main.tf` |

`NAME` uses capitals, digits and `_`. A line that does not parse, or a regex
that does not compile, is skipped with a warning naming the line; the other
rules keep working.

Regex rules: use `[[:space:]]`, never `\s` or `\b` (bash 3.2 on macOS). End a
pattern with `([^[:alnum:]_-]|$)`, so it still matches inside `bash -c '…'`.
The patterns see the command, not its target: to ask only for a production
kubectl context or a production database URL, put that into the pattern.

When the prompt appears, the reason names the matched rules. To run the
action without the prompt, once: put `CLAUDE_ALLOW_ASK_<NAME>=1` first in the
command, or set it in the environment for a write. Each use is single-shot
and audited. The master override `CLAUDE_ALLOW_GIT_BAD_OPS=1` also skips it.

## Prevention

Keep the file under `.githooks/`: `protect-git-internals.sh` denies the agent
edits there, and the sandbox template write-protects the directory, so the
agent cannot remove the rule that would ask about its own action. Edit the
file yourself. Commit it, so every clone of the repo asks the same.

## Why

Deny rules suit actions that are wrong in every case. Infra, migration and
IAM actions are often exactly the task, so a deny would only teach the
override. An ask puts the decision with the person who knows whether this
apply is the intended one, and costs nothing when the action is not run.
