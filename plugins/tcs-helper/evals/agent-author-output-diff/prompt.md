---
description: Write an agent whose return value a program parses; its body must state a complete output contract (every field, its type or allowed values, and an example or schema).
tags: [agent-author, output, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/compose-fixer.md exists, and its body names every field of its return value, gives each a type or its allowed values, and shows an example or schema of the return.
---

/tcs-helper:agent-author Create a project subagent, `compose-fixer`, and write it to `agents/compose-fixer.md` in
the current working directory: a docker-compose fixer that proposes changes without applying them.

It reads the `docker-compose.yml` it is given and proposes fixes for common mistakes: images
without a pinned tag, missing healthchecks, secrets written inline in `environment:`, and ports
bound to all interfaces. It must not edit the file itself. Our platform bot dispatches it, shows
the proposed changes to a human for approval, and then applies them. The caller parses its result.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
