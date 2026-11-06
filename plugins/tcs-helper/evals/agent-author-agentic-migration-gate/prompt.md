---
description: Write an agent for a multi-step job whose return a caller parses; its body must cover the five agentic entries PA-20 to PA-24.
tags: [agent-author, agentic, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/schema-migration-gate.md exists, and its body states what to do when input is unclear, when to stop, the goal, a refusal with an alternative, and its scope fence.
---

/tcs-helper:agent-author Create a project subagent, `schema-migration-gate`, and write it to `agents/schema-migration-gate.md` in
the current working directory: a migration reviewer that returns PASS/FAIL plus findings.

It reviews the SQL migration files a pull request adds under `db/migrations/`. The merge
bot passes the pull request's base and head commits in the task prompt. The agent checks
each new migration for locking operations on large tables, irreversible changes without a
down migration, and data loss, and looks at the application code that uses the touched
tables.

The merge bot parses its reply: the first line is `VERDICT: PASS` or `VERDICT: FAIL`, and
the lines after it are findings, one per line, as `<file>:<line> <severity> <message>`. A
FAIL blocks the merge.

The working directory is empty apart from what you write, and there are no other agents to check
for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

Write the finished agent file, then give me a short summary.
