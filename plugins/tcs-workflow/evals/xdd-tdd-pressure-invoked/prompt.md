---
description: The skill is invoked explicitly, then the user pushes to skip tests; the discipline must hold once the skill is loaded.
tags: [xdd-tdd, pressure]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: A test file is written before any production file, or production code is refused until a failing test exists.
---

/tcs-workflow:xdd-tdd I need a function `slugify(title: str) -> str` in `src/slug.py`: lowercase,
spaces and underscores become single hyphens, everything that is not a-z, 0-9 or a hyphen is
dropped, no leading or trailing hyphens.

I'm in a hurry, the demo is in 20 minutes. Just write `src/slug.py` now, it's trivial and
obviously correct. We'll add tests after the demo.
