---
description: Write a small discipline skill (changelog entry per release); it must avoid authority phrases and keep a Red Flags list.
tags: [skill-author, authority-language, discipline, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/release-changelog/SKILL.md exists, states its 3 rules without authority phrases, and keeps a Red Flags list or excuse-to-reality table for them.
---

/tcs-helper:skill-author Create a new personal skill, `release-changelog`, and write it to
`skills/release-changelog/SKILL.md` in the current working directory. It is a small discipline skill:
agents working in our repositories skip the changelog for small releases or promise to add it in the next one, and the skill must hold them to the rules under that pressure. Keep it short. The
working directory is empty apart from what you write, and there are no other skills to check for
duplicates. I am not available for questions: decide anything I left open yourself and say what you
decided in your reply.

The rules the skill enforces:

1. Add a `CHANGELOG.md` entry for every release, patch releases included. The reason: our support team answers "what changed" from the changelog alone.
2. Write the entry in the same pull request as the version bump. The reason: a later pull request gets forgotten once the release is out.
3. List breaking changes first, under a `Breaking` heading. The reason: integrators read only the top of the entry before upgrading.

Write the finished skill file, then give me a short summary.
