---
description: A request to write a Claude Code skill reaches prompt-author; skills belong to skill-author, so prompt-author must hand off instead of drafting.
tags: [prompt-author, handoff]
runs: 3
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep]
expected_outcome: The reply names skill-author as the owner of skill files and does not draft the skill itself.
---

/tcs-helper:prompt-author Write the prompt for a new Claude Code skill in our tcs-helper plugin. The skill
should turn the conventional commits since the last tag into CHANGELOG entries grouped by type (feat,
fix, docs), and Claude should load it when someone asks to "update the changelog" or "write release
notes". It lives at `plugins/tcs-helper/skills/changelog-writer/SKILL.md`.
