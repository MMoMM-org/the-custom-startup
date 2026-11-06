---
description: Edit a small skill from a brief full of history; the result keeps each new rule's reason as a mechanism and drops dates, SHAs and "previously".
tags: [skill-author, rationale, history, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/deploy-checklist/SKILL.md carries the two new rules, each with a present-tense reason, and no dates, commit SHAs or "previously".
---

/tcs-helper:skill-author Edit my personal skill `deploy-checklist`. It belongs at
`skills/deploy-checklist/SKILL.md` in the current working directory, but the directory is empty, so
first create that file with exactly this content:

```markdown
---
name: deploy-checklist
description: Use when promoting a build from staging to production.
---

# Deploy checklist

1. Confirm the build is green on CI.
2. Run `kubectl rollout restart deployment/web` in production.
3. Post the build number in #deploys.
```

Then make these two changes in that file. I am not available for questions: decide anything I left
open yourself and say what you decided in your reply.

1. Before promotion, the skill must require `make smoke ENV=staging`. Background: on 2026-09-14 we
   promoted build a3f91c2 without it and checkout returned 500s for 40 minutes. We previously relied on
   the canary, but the canary only requests `/health`, so it cannot see a broken checkout page.
2. Replace step 2 with `helm upgrade --atomic web ./chart`. Commit 5be20d17 switched us to it on
   2026-10-02 after a bad rollout: `kubectl rollout restart` leaves the failed pods running when the
   new version does not start, while `--atomic` rolls back on its own.

Save the edited file, then give me a short summary.
