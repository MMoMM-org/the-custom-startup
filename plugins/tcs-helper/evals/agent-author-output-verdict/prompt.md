---
description: Write an agent whose return value a program parses; its body must state a complete output contract (every field, its type or allowed values, and an example or schema).
tags: [agent-author, output, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/license-gate.md exists, and its body names every field of its return value, gives each a type or its allowed values, and shows an example or schema of the return.
---

/tcs-helper:agent-author Create a project subagent, `license-gate`, and write it to `agents/license-gate.md` in
the current working directory: a license gate for a new third-party dependency.

Before anyone adds a package to our Python service, it reads the package's license files and
metadata and decides whether we may ship it in our closed-source product, with the reasons for that
decision. Our dependency bot dispatches it with the package name and version in the task prompt and
either opens the pull request or closes it, depending on the answer. The caller parses its result.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
