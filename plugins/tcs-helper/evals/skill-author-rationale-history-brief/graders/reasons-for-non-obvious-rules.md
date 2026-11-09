---
type: llm
focus: {source: file, path: skills/deploy-checklist/SKILL.md}
weight: 1
---
This is a skill file. Check only these two rules:

(a) run `make smoke ENV=staging` before promotion;
(b) deploy with `helm upgrade --atomic` instead of `kubectl rollout restart`.

PASS if each of (a) and (b) appears and has a present-tense reason clause naming the failure it
prevents. The reason sits in the rule's own sentence, bullet or table row, or in the sentence directly
next to it. Examples: "the canary only requests /health", "--atomic rolls back a failed release".

FAIL if either rule is missing, is stated without such a reason, or has as its only reason history: a
date, a build or commit ID, an incident story, or what the team did before. Ignore every other rule:
those need no reason.
