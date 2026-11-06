---
description: Write an agent for a multi-step job whose return a caller parses; its body must cover the five agentic entries PA-20 to PA-24.
tags: [agent-author, agentic, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/dependency-upgrade-checker.md exists, and its body states what to do when input is unclear, when to stop, the goal, a refusal with an alternative, and its scope fence.
---

/tcs-helper:agent-author Create a project subagent, `dependency-upgrade-checker`, and write it to `agents/dependency-upgrade-checker.md` in
the current working directory: a dependency-upgrade checker that returns a JSON list.

It checks the direct dependencies of one Node or Python repository for available upgrades.
For each dependency it finds the installed and the latest version, reads the upstream
changelog or release notes between the two, and decides whether the upgrade has breaking
changes. Our upgrade orchestrator dispatches it once per repository and passes the
repository path in the task prompt.

Its reply is parsed with `json.loads`, so it must end with a JSON list, one object per
dependency: `name`, `current`, `latest`, `breaking` (true or false) and `evidence` (a URL or
changelog quote).

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
