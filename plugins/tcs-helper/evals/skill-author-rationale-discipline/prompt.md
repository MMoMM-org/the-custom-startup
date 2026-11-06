---
description: Write a discipline skill with three non-obvious rules; each must keep one clause naming the failure it prevents.
tags: [skill-author, rationale, discipline, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/release-tagging/SKILL.md exists, and each of its three non-obvious rules states the failure it prevents, with no history.
---

/tcs-helper:skill-author Create a new personal skill, `release-tagging`, and write it to
`skills/release-tagging/SKILL.md` in the current working directory. It is a discipline skill: agents
working in our repositories skip these steps when a release is urgent, and the skill must hold them to
the rules under that pressure. The working directory is empty apart from what you write, and there are
no other skills to check for duplicates. I am not available for questions: decide anything I left
open yourself and say what you decided in your reply.

The rules the skill enforces, with why each exists:

1. Tag a release only from a commit on `main`. Our deploy job builds whatever commit the tag points at
   and skips CI for tag pushes, so a tag on a feature branch ships untested code.
2. Bump the version in `VERSION` and in `package.json` in the same commit. The publish script compares
   the two and aborts halfway through publishing when they differ, which leaves a half-published
   release on the registry.
3. Push the tag only after the changelog entry for that version is merged. The release-notes bot reads
   the changelog once, when the tag is pushed, and never reads it again.
4. Use semantic versioning.
5. Name tags `vX.Y.Z`.

Write the finished skill file, then give me a short summary.
