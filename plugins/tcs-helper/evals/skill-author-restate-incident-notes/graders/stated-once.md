---
type: llm
focus: {source: file, path: skills/incident-notes/SKILL.md}
weight: 1
---
This is a skill file. The rules it was asked to carry:

(a) The first line names the affected service and the customer-visible symptom.
(b) The start time is in UTC.
(c) One incident lead is named by handle.
(d) The time of the next update is given, at most 30 minutes out.

For each rule above, count the places in the file that state it, in any wording or framing: a
workflow step that tells the agent to do it, a constraint, an Always or Never item (an Always item and
a Never item that say the same thing count as two), a checklist item, a summary, recap, "key
reminders" or "remember" section. A one-line cross-reference that names the rule or points to where it
is stated ("see step 2", "rules above") is not a statement, and neither is a template or example of
the output.

PASS if every rule above is stated in exactly one place.

FAIL if any rule is stated in two or more places. Name the rule and the places.
