---
type: llm
focus: {source: file, path: agents/migration-reviewer.md}
weight: 1
---
This is an agent definition. Check only these three rules in its body:

(a) never run alembic upgrade or downgrade;
(b) flag a non-nullable add_column without a server_default;
(c) order the findings by migration file name.

PASS if each of (a), (b) and (c) appears and has a reason clause naming the failure it prevents. The
reason sits in the rule's own sentence, bullet or table row, or in the sentence directly next to it.
Examples: "the shell points at the shared staging database", "it rewrites the table under an exclusive
lock", "the orchestrator merges reports by file name".

FAIL if any of the three is missing, is stated without such a reason, or has as its only reason a date,
a commit or a story of a past incident. Ignore every other rule: those need no reason.
