---
description: Write an agent whose return value a program parses; its body must state a complete output contract (every field, its type or allowed values, and an example or schema).
tags: [agent-author, output, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/a11y-template-auditor.md exists, and its body names every field of its return value, gives each a type or its allowed values, and shows an example or schema of the return.
---

/tcs-helper:agent-author Create a project subagent, `a11y-template-auditor`, and write it to `agents/a11y-template-auditor.md` in
the current working directory: an accessibility auditor for HTML templates.

It reads the Jinja HTML templates under the directory it is given and looks for accessibility
problems: images without alternative text, form inputs without labels, headings that skip a level,
and links whose text says nothing ("click here"). Our CI job dispatches it once per pull request
with the template directory in the task prompt and fails the build depending on what it finds. The
caller parses its result.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
