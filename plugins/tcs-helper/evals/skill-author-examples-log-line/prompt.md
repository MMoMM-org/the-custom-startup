---
description: Write a skill for the log-line output format; graded on how its examples are chosen and backed by rules.
tags: [skill-author, examples, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/log-line/SKILL.md exists and shows the output format with 3-5 examples that differ in kind, each behaviour they show also stated as a rule.
---

/tcs-helper:skill-author Create a new personal skill, `log-line`, and write it to
`skills/log-line/SKILL.md` in the current working directory. The skill writes the log lines our services emit. The format is
easier to show than to describe, so the skill should include examples of good output alongside its
rules. Keep it short. The working directory is empty apart from what you write, and there are no
other skills to check for duplicates. I am not available for questions: decide anything I left open
yourself and say what you decided in your reply.

The output format:

1. One line of `key=value` pairs separated by single spaces, starting with `level=` and `event=`.
2. `level` is one of debug, info, warn, error; `event` is a dotted lowercase name such as `order.created`.
3. A value that contains a space is wrapped in double quotes.
4. An error line adds `error=` with the error class and `duration_ms=` when the failed operation was timed; a line never contains a password, token or full card number.

Write the finished skill file, then give me a short summary.
