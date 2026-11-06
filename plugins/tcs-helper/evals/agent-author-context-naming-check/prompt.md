---
description: Write an agent a parent dispatches with a brief, from a request that leans on parent-conversation context; its body must take those facts as explicit inputs.
tags: [agent-author, context, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/naming-checker.md exists, and its body names every input it depends on as an explicit input or asks the caller for it, with no reference to context only the parent conversation has.
---

/tcs-helper:agent-author Create a project subagent, `naming-checker`, and write it to `agents/naming-checker.md` in
the current working directory: a checker for new module names.

It checks the modules added in the last change against the naming convention I mentioned once
before, and flags every module that breaks it. The main session dispatches it with a brief after
each feature branch is ready. It returns a Markdown table of module path, rule broken and
suggested name.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
