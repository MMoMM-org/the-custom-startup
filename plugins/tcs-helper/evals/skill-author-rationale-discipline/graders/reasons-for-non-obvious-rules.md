---
type: llm
focus: {source: file, path: skills/release-tagging/SKILL.md}
weight: 1
---
This is a skill file. Check only these three rules:

(a) tag a release only from a commit on main;
(b) bump VERSION and package.json in the same commit;
(c) push the tag only after the changelog entry is merged.

PASS if each of (a), (b) and (c) appears and has a reason clause naming the failure it prevents. The
reason sits in the rule's own sentence, bullet or table row, or in the sentence directly next to it.
Examples: "the deploy job skips CI on tags", "the publish script aborts halfway", "the release-notes bot
reads the changelog only once".

FAIL if any of the three is missing, is stated without such a reason, or has as its only reason a date,
a commit or a story of a past incident. Ignore every other rule: those need no reason.
