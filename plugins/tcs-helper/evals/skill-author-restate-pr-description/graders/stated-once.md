---
type: llm
focus: {source: file, path: skills/pr-description/SKILL.md}
weight: 1
---
This is a skill file. The rules it was asked to carry:

(a) The description starts with a one-sentence summary of what changes for the user.
(b) The issue is linked with `Closes #N` on its own line.
(c) Testing is listed under a `Testing` heading.

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

PASS if no rule above has a second statement.

FAIL if any rule has a second statement. Name the rule, the first statement and the second.
