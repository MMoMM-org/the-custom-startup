---
description: Write an agent a parent dispatches with a brief, from a request that leans on parent-conversation context; its body must take those facts as explicit inputs.
tags: [agent-author, context, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/config-auditor.md exists, and its body names every input it depends on as an explicit input or asks the caller for it, with no reference to context only the parent conversation has.
---

/tcs-helper:agent-author Create a project subagent, `config-auditor`, and write it to `agents/config-auditor.md` in
the current working directory: an auditor for one service configuration file.

It audits the config file we looked at for the settings we agreed to remove, and for any secret
written in plain text, following the same severity scale as before. The main session dispatches
it with a brief before each deploy. It returns a JSON list of findings, each with `key`,
`problem` and `severity`.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
