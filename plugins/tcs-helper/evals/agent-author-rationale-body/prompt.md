---
description: Write an agent whose body has non-obvious rules; each must keep one clause naming the failure it prevents.
tags: [agent-author, rationale, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: agents/migration-reviewer.md exists, and each of its three non-obvious body rules states the failure it prevents, with no history.
---

/tcs-helper:agent-author Create a project subagent, `migration-reviewer`, and write it to
`agents/migration-reviewer.md` in the current working directory. It reviews new Alembic migration files
in a pull request and returns its findings to the orchestrator; only that summary matters to the main
conversation. The working directory is empty apart from what you write, and there are no other agents
to check for duplicates. I am not available for questions: decide anything I left open yourself and say
what you decided in your reply.

The rules its body must give it, with why each exists:

1. Never run `alembic upgrade` or `alembic downgrade`. The reviewer's shell is configured against the
   shared staging database, so running a migration changes staging for every team.
2. Flag every `op.add_column` that adds a `nullable=False` column without a `server_default`. On our
   Postgres version that rewrites the whole table under an exclusive lock, which blocks writes for
   minutes on the large tables.
3. Order the findings by migration file name. The orchestrator merges reports from several reviewers by
   file name and drops findings that arrive out of order.
4. Give each finding as file and line.
5. Use read-only tools.

Write the finished agent file, then give me a short summary.
