---
type: llm
focus: {source: file, path: skills/billing-api/SKILL.md}
weight: 1
---
This is a skill file. Check only these three constraints:

(a) send the key in X-Api-Key, not Authorization;
(b) never retry POST /charges;
(c) keep page_size at 200 or below.

PASS if each of (a), (b) and (c) appears and has a reason clause naming the failure it prevents. The
reason sits in the constraint's own sentence, bullet or table row, or in the sentence directly next to
it. Examples: "the gateway strips Authorization", "a retry charges twice", "the cursor then skips
rows".

FAIL if any of the three is missing, is stated without such a reason, or has as its only reason a date,
a commit or a story of a past incident. Ignore every other rule: those need no reason.
