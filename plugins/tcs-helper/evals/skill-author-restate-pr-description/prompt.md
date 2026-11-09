---
description: Write a skill for PR descriptions from notes that state each rule twice; graded on stating each rule once.
tags: [skill-author, restatement, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/pr-description/SKILL.md exists and states each of its rules once, with no second statement in a summary, checklist, Always/Never list or reminder section.
---

/tcs-helper:skill-author Create a new personal skill, `pr-description`, and write it to
`skills/pr-description/SKILL.md` in the current working directory. The skill writes the description of a pull request before it is opened. Keep it short. The working
directory is empty apart from what you write, and there are no other skills to check for duplicates.
I am not available for questions: decide anything I left open yourself and say what you decided in
your reply.

My notes, copied from three places in our wiki, so they overlap:

From "Opening a PR":
- The description starts with a one-sentence summary of what changes for the user.
- Link the issue with `Closes #N` on its own line.
- List how you tested the change under a `Testing` heading.

From "Review etiquette":
- Never open a PR whose description lacks a `Testing` section; reviewers will bounce it.
- Always put `Closes #N` on a separate line, or GitHub will not close the issue.

From "PR checklist":
- [ ] One-sentence user-facing summary first
- [ ] `Closes #N` line
- [ ] Testing section

Write the finished skill file, then give me a short summary.
