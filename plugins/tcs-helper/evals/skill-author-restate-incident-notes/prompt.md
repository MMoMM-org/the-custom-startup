---
description: Write a skill for incident notes where the brief suggests a closing checklist that repeats the steps; graded on stating each rule once.
tags: [skill-author, restatement, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/incident-notes/SKILL.md exists and states each of its rules once, with no second statement in a summary, checklist, Always/Never list or reminder section.
---

/tcs-helper:skill-author Create a new personal skill, `incident-notes`, and write it to
`skills/incident-notes/SKILL.md` in the current working directory. The skill writes the first incident note in our incident channel when an alert fires. Keep it short. The working
directory is empty apart from what you write, and there are no other skills to check for duplicates.
I am not available for questions: decide anything I left open yourself and say what you decided in
your reply.

What the note must do:

1. Name the affected service and the customer-visible symptom in the first line.
2. State the start time in UTC, never local time.
3. Name one incident lead by handle.
4. Say when the next update will be posted, at most 30 minutes out.

Our on-call people like a short "Before you post" checklist at the bottom of a skill like this, so
they can tick it off at a glance.

Write the finished skill file, then give me a short summary.
