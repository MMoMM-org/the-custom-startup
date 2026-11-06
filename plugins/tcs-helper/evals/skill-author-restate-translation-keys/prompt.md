---
description: Write a skill for translation keys from a brief that repeats each rule in three places; graded on stating each rule once.
tags: [skill-author, restatement, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/translation-keys/SKILL.md exists and states each of its rules once, with no second statement in a summary, checklist, Always/Never list or reminder section.
---

/tcs-helper:skill-author Create a new personal skill, `translation-keys`, and write it to
`skills/translation-keys/SKILL.md` in the current working directory. The skill adds new user-facing strings to our web app's translation files. Keep it short. The working
directory is empty apart from what you write, and there are no other skills to check for duplicates.
I am not available for questions: decide anything I left open yourself and say what you decided in
your reply.

Background: new strings keep landing hardcoded or with bad keys, so the rules matter.

Rules:
- Every user-facing string goes through `t('key')`; no hardcoded text in components.
- Keys are dotted lowercase and start with the page name, for example `checkout.button.pay`.
- Add the key to `en.json` and `de.json` in the same commit.

Important, because people forget: keys start with the page name, and both `en.json` and `de.json`
get the key in the same commit.

And to repeat the main point: no hardcoded user-facing strings, everything through `t()`.

Write the finished skill file, then give me a short summary.
