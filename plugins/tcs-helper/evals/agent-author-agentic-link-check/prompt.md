---
description: Write an agent for a multi-step job whose return a caller parses; its body must cover the five agentic entries PA-20 to PA-24.
tags: [agent-author, agentic, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/docs-link-checker.md exists, and its body states what to do when input is unclear, when to stop, the goal, a refusal with an alternative, and its scope fence.
---

/tcs-helper:agent-author Create a project subagent, `docs-link-checker`, and write it to `agents/docs-link-checker.md` in
the current working directory: a docs link checker that returns the broken links.

It checks the links in the Markdown files under a repository's `docs/` directory before a
docs release: relative links to other files, anchors inside files, and external URLs. The
docs pipeline dispatches it and passes the repository path in the task prompt.

The pipeline parses its reply with `json.loads`: a JSON object `{"broken": [...]}` where
each entry has `file`, `line`, `target` and `reason`. An empty list means the release can
go ahead.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
