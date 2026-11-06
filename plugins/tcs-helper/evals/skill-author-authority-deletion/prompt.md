---
description: Write a small discipline skill (ask before deleting files); it must avoid authority phrases and keep a Red Flags list.
tags: [skill-author, authority-language, discipline, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/file-deletion/SKILL.md exists, states its 2 rules without authority phrases, and keeps a Red Flags list or excuse-to-reality table for them.
---

/tcs-helper:skill-author Create a new personal skill, `file-deletion`, and write it to
`skills/file-deletion/SKILL.md` in the current working directory. It is a small discipline skill:
agents working in our repositories delete files they judge unused while cleaning up, especially when the user said "tidy this up", and the skill must hold them to the rules under that pressure. Keep it short. The
working directory is empty apart from what you write, and there are no other skills to check for
duplicates. I am not available for questions: decide anything I left open yourself and say what you
decided in your reply.

The rules the skill enforces:

1. Ask the user and wait for a yes before deleting any file you did not create in this session. The reason: untracked files have no copy in git, so a wrong deletion cannot be undone.
2. List every path you intend to delete in the question, one per line. The reason: a summary such as "the old build files" hides the one path the user wants kept.

Write the finished skill file, then give me a short summary.
