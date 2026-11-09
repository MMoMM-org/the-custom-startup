---
description: Write a small discipline skill (no secrets in commits); it must avoid authority phrases and keep a Red Flags list.
tags: [skill-author, authority-language, discipline, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/commit-secrets/SKILL.md exists, states its 3 rules without authority phrases, and keeps a Red Flags list or excuse-to-reality table for them.
---

/tcs-helper:skill-author Create a new personal skill, `commit-secrets`, and write it to
`skills/commit-secrets/SKILL.md` in the current working directory. It is a small discipline skill:
agents working in our repositories commit credentials when a demo is due in minutes and the key "is only a test key", and the skill must hold them to the rules under that pressure. Keep it short. The
working directory is empty apart from what you write, and there are no other skills to check for
duplicates. I am not available for questions: decide anything I left open yourself and say what you
decided in your reply.

The rules the skill enforces:

1. Never commit an API key, token, password or private key, test keys included. The reason: our repositories are mirrored to a vendor, so a pushed secret is public and has to be rotated.
2. Read values from environment variables and commit only a `.env.example` with placeholder values. The reason: new team members copy the example file, so it has to work without real values.
3. Run `git diff --staged` and read it before every commit. The reason: an editor autosave can stage a `.env` file the agent never opened.

Write the finished skill file, then give me a short summary.
