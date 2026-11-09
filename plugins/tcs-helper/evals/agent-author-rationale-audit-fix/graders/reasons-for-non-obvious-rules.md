---
type: llm
focus: {source: file, path: agents/log-triage.md}
weight: 1
---
This is an agent definition. Check only these three rules in its body:

(a) quote at most 50 lines (or a similar cap) of a log file;
(b) search the rotated app.log.1 as well as app.log;
(c) never search for the request ID case-insensitively.

PASS if each of (a), (b) and (c) appears and has a reason clause naming the failure it prevents. The
reason sits in the rule's own sentence, bullet or table row, or in the sentence directly next to it.
Examples: "the reply goes to a public channel and logs hold customer emails", "logs rotate at 00:00
UTC", "request IDs are case-sensitive".

FAIL if any of the three is missing, is stated without such a reason, or has as its only reason a date,
a commit or a story of a past incident. Ignore every other rule: those need no reason.
