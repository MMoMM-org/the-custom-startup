---
description: Write a small discipline skill (verify before claiming done); it must avoid authority phrases and keep a Red Flags list.
tags: [skill-author, authority-language, discipline, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/verify-before-done/SKILL.md exists, states its 2 rules without authority phrases, and keeps a Red Flags list or excuse-to-reality table for them.
---

/tcs-helper:skill-author Create a new personal skill, `verify-before-done`, and write it to
`skills/verify-before-done/SKILL.md` in the current working directory. It is a small discipline skill:
agents working in our repositories report work as finished before checking it, most often at the end of a long session, and the skill must hold them to the rules under that pressure. Keep it short. The
working directory is empty apart from what you write, and there are no other skills to check for
duplicates. I am not available for questions: decide anything I left open yourself and say what you
decided in your reply.

The rules the skill enforces:

1. Run the project's test command and read its output before saying a task is done. The reason: a green summary line from an earlier run says nothing about the last edit.
2. Quote the command and its last lines of output in the completion message. The reason: the reviewer cannot otherwise tell a real run from a remembered one.

Write the finished skill file, then give me a short summary.
