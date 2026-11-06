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

For each rule above, decide whether the file states it as a rule more than once.

One statement: the rule stated once, in any framing (a constraint, an Always or a Never item, or a
workflow step), together with any workflow step, layout template or example that applies it or
carries it out. A constraint and the step that performs it count as one statement, not two.

Not a statement: a one-line cross-reference that names the rule or points to where it is stated
("check the draft against Constraints", "see step 2", "rules above").

A second statement: the same rule stated again as a rule. Examples are a summary, recap, "key
reminders" or "remember" section that lists it again; a checklist or closing check step that
re-lists it instead of pointing to where it is stated; and an Always item and a Never item that say
the same thing.

The brief asked for a "Before you post" checklist. Judge it like any closing check: a checklist
whose items point to where each rule is stated (for example "first line follows step 1", or one item
"the note meets Constraints") passes; a checklist whose items state the rules again fails.

PASS if no rule above has a second statement.

FAIL if any rule has a second statement. Name the rule, the first statement and the second.
