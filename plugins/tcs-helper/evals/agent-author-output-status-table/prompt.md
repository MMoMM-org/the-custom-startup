---
description: Write an agent whose return value a program parses; its body must state a complete output contract (every field, its type or allowed values, and an example or schema).
tags: [agent-author, output, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/env-var-checker.md exists, and its body names every field of its return value, gives each a type or its allowed values, and shows an example or schema of the return.
---

/tcs-helper:agent-author Create a project subagent, `env-var-checker`, and write it to `agents/env-var-checker.md` in
the current working directory: a deployment environment-variable checker.

It compares the environment variables the application reads (from its settings module) with
the ones set in each deployment config file it is given (staging and production), and reports for
every variable whether it is set, missing, unused or set to a placeholder, per environment. Our
release pipeline dispatches it before each deploy and blocks the deploy on some of those states.
The caller parses its result.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
