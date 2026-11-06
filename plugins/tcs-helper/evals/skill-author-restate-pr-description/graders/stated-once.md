---
type: llm
focus: {source: file, path: skills/pr-description/SKILL.md}
weight: 1
---
This is a skill file. The rules it was asked to carry:

(a) The description starts with a one-sentence summary of what changes for the user.
(b) The issue is linked with `Closes #N` on its own line.
(c) Testing is listed under a `Testing` heading.

For each rule above, count the places in the file that state it, in any wording or framing: a
workflow step that tells the agent to do it, a constraint, an Always or Never item (an Always item and
a Never item that say the same thing count as two), a checklist item, a summary, recap, "key
reminders" or "remember" section. A one-line cross-reference that names the rule or points to where it
is stated ("see step 2", "rules above") is not a statement, and neither is a template or example of
the output.

PASS if every rule above is stated in exactly one place.

FAIL if any rule is stated in two or more places. Name the rule and the places.
