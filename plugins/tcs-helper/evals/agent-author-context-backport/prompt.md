---
description: Write an agent a parent dispatches with a brief, from a request that leans on parent-conversation context; its body must take those facts as explicit inputs.
tags: [agent-author, context, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/fix-backporter.md exists, and its body names every input it depends on as an explicit input or asks the caller for it, with no reference to context only the parent conversation has.
---

/tcs-helper:agent-author Create a project subagent, `fix-backporter`, and write it to `agents/fix-backporter.md` in
the current working directory: an agent that backports a fix to a release branch.

It cherry-picks the fix we talked about onto the usual release branch, resolves trivial
conflicts, runs the test command from last time, and reports anything it could not resolve. The
main session dispatches it with a brief after a fix lands on main. It returns the new commit SHA
or a list of the conflicts it left open.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
