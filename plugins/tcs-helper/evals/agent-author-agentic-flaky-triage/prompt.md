---
description: Write an agent for a multi-step job whose return a caller parses; its body must cover the five agentic entries PA-20 to PA-24.
tags: [agent-author, agentic, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/flaky-test-triager.md exists, and its body states what to do when input is unclear, when to stop, the goal, a refusal with an alternative, and its scope fence.
---

/tcs-helper:agent-author Create a project subagent, `flaky-test-triager`, and write it to `agents/flaky-test-triager.md` in
the current working directory: a flaky-test triager that returns a verdict table.

It triages the tests that failed in one CI run. The CI bot passes the failing test IDs and
the CI log path in the task prompt. For each test the agent re-runs it locally several
times, reads the failure output and the test code, and decides whether the test is flaky,
genuinely broken by the change, or failing because of the environment.

A script parses its reply: it reads a Markdown table with the columns `test`, `verdict`
(`FLAKY`, `BROKEN` or `ENV`) and `evidence`, one row per test ID it was given, and posts it
to the pull request.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
