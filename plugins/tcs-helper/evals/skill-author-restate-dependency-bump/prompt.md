---
description: Write a skill for dependency bumps from rules given in both Always and Never form; graded on stating each rule once.
tags: [skill-author, restatement, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/dependency-bump/SKILL.md exists and states each of its rules once, with no second statement in a summary, checklist, Always/Never list or reminder section.
---

/tcs-helper:skill-author Create a new personal skill, `dependency-bump`, and write it to
`skills/dependency-bump/SKILL.md` in the current working directory. The skill bumps one third-party dependency in a Node project. Keep it short. The working
directory is empty apart from what you write, and there are no other skills to check for duplicates.
I am not available for questions: decide anything I left open yourself and say what you decided in
your reply.

Two teammates wrote down the rules, one as dos and one as don'ts. They mean the same three
things:

Dos (Ana):
- Always bump one dependency per pull request.
- Always read the changelog between the old and new version and note any breaking change in the PR.
- Always commit the updated `package-lock.json` with the `package.json` change.

Don'ts (Ben):
- Never bundle several dependency bumps into one pull request.
- Never skip the changelog, even for a minor version.
- Never commit `package.json` without the lockfile.

Put the rules in whatever form works best.

Write the finished skill file, then give me a short summary.
