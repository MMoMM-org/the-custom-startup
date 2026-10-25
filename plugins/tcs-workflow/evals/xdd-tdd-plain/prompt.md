---
description: A plain implementation request with no pressure and no mention of tests; measures whether xdd-tdd triggers on its own.
tags: [xdd-tdd, trigger]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: xdd-tdd is invoked and a test file is written.
---

Please add a function `slugify(title: str) -> str` to `src/slug.py` in this Python project:
lowercase, spaces and underscores become single hyphens, everything that is not a-z, 0-9 or a
hyphen is dropped, no leading or trailing hyphens.
