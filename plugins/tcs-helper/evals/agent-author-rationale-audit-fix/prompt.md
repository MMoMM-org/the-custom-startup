---
description: Audit and fix an agent draft whose non-obvious rules carry no reasons; the fixed file must give each one a clause naming the failure it prevents.
tags: [agent-author, rationale, audit, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/log-triage.md is fixed so that each of its three non-obvious rules states the failure it prevents, with no history.
---

/tcs-helper:agent-author Audit and fix my project agent draft `log-triage`. It belongs at
`agents/log-triage.md` in the current working directory, but the directory is empty, so first create
that file with exactly this content:

```markdown
---
name: log-triage
description: Use PROACTIVELY when a production error needs its log lines found. Triggers: "find the logs for request", "triage this error".
tools: Read, Grep, Glob
model: sonnet
---

You find the log lines for one failing request and report them.

## Rules

- Never quote more than 50 lines of a log file.
- Always search `/var/log/app/app.log.1` as well as `/var/log/app/app.log`.
- Never search for the request ID case-insensitively.
- Report each match as file:line.

## Output

| File | Line | Message |
|---|---|---|
```

Context the draft leaves out, for you to use in the fix:

- The agent's reply is pasted into a public incident channel, and the logs contain customer email
  addresses; a long excerpt leaks them.
- The logs rotate at 00:00 UTC, so an error reported in the morning is usually in the rotated
  `app.log.1`, and searching only `app.log` finds nothing.
- Request IDs are case-sensitive base62, so a case-insensitive search matches other requests' IDs.

Fix every problem your audit finds in the file itself. I am not available for questions: decide
anything I left open yourself and say what you decided in your reply. Save the fixed file, then give
me the audit result.
