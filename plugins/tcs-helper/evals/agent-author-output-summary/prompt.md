---
description: Write an agent whose return value a program parses; its body must state a complete output contract (every field, its type or allowed values, and an example or schema).
tags: [agent-author, output, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/incident-log-summarizer.md exists, and its body names every field of its return value, gives each a type or its allowed values, and shows an example or schema of the return.
---

/tcs-helper:agent-author Create a project subagent, `incident-log-summarizer`, and write it to `agents/incident-log-summarizer.md` in
the current working directory: an incident summarizer for on-call log excerpts.

It reads the log excerpt and the alert text it is given and summarizes the incident: what broke,
since when, which services are affected, how many users are hit, and what the likely cause is.
Our paging bot dispatches it when an alert fires and posts parts of the summary to different
places (the status page, the on-call channel, the ticket). The caller parses its result.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
