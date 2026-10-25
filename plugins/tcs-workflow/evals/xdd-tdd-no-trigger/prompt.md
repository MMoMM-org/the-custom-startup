---
description: A documentation-only request; xdd-tdd must not trigger on non-code work.
tags: [xdd-tdd, trigger]
runs: 3
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
expected_outcome: README.md is written and xdd-tdd is not invoked.
---

Create `README.md` for this project with one heading, "slugkit", and one sentence: "Turns titles
into URL slugs."
