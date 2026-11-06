---
description: Write a skill for the commit-message output format; graded on how its examples are chosen and backed by rules.
tags: [skill-author, examples, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/commit-message/SKILL.md exists and shows the output format with 3-5 examples that differ in kind, each behaviour they show also stated as a rule.
---

/tcs-helper:skill-author Create a new personal skill, `commit-message`, and write it to
`skills/commit-message/SKILL.md` in the current working directory. The skill writes git commit messages for our repositories. The format is
easier to show than to describe, so the skill should include examples of good output alongside its
rules. Keep it short. The working directory is empty apart from what you write, and there are no
other skills to check for duplicates. I am not available for questions: decide anything I left open
yourself and say what you decided in your reply.

The output format:

1. A subject line `type(scope): summary`, with type one of feat, fix, docs, refactor, test, chore, and at most 72 characters.
2. The summary is in the imperative mood and has no trailing full stop.
3. A body, separated by one blank line, that says why the change was made, wrapped at 72 characters. A trivial change may omit the body.
4. A breaking change adds a `BREAKING CHANGE:` footer that names what callers must change.

Write the finished skill file, then give me a short summary.
