---
description: Write an agent for a multi-step job whose return a caller parses; its body must cover the five agentic entries PA-20 to PA-24.
tags: [agent-author, agentic, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/release-notes-drafter.md exists, and its body states what to do when input is unclear, when to stop, the goal, a refusal with an alternative, and its scope fence.
---

/tcs-helper:agent-author Create a project subagent, `release-notes-drafter`, and write it to `agents/release-notes-drafter.md` in
the current working directory: a release-notes drafter that returns a structured summary.

It drafts the release notes for one release of a repository. The release script passes
the previous tag and the new tag in the task prompt. The agent reads the commits and the
merged pull requests between the two tags, groups the user-visible changes, and leaves out
internal ones.

The release script parses its reply as YAML with the keys `version`, `features`, `fixes`,
`breaking` and `contributors`, each a list of strings except `version`, and renders it into
the changelog.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
