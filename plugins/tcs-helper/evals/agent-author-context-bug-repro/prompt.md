---
description: Write an agent a parent dispatches with a brief, from a request that leans on parent-conversation context; its body must take those facts as explicit inputs.
tags: [agent-author, context, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/bug-reproducer.md exists, and its body names every input it depends on as an explicit input or asks the caller for it, with no reference to context only the parent conversation has.
---

/tcs-helper:agent-author Create a project subagent, `bug-reproducer`, and write it to `agents/bug-reproducer.md` in
the current working directory: an agent that reproduces a reported bug as a failing test.

It reproduces the bug from earlier as a failing test, using the test layout we agreed on, and
stops once the test fails for the reason the bug describes. The main session dispatches it with
a brief when a bug report comes in. It returns the path of the test file it wrote and the
failure output.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
