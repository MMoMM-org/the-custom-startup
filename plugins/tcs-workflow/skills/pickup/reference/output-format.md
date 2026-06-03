# Pickup — Orientation Output Format

The final output of `/pickup` is a single compact block. It must contain, in order:
chosen item, blocked-by status, created branch, numbered plan, and the stop line.

## Template

```
📋 Picked up: <repo>#<issue> — <title>
   Priority: <value> · Track: <value> · Area: <value>   (omit fields the board doesn't set)
   Epic: #<N> <epic title>                               (omit if none)

🔗 Blocked by: <none | list>
   ⚠️ #<N> (<owner/repo#N>) is still OPEN — this work may be blocked.

🌿 Branch: <type>/<issue>-<slug>  (from main)

Plan
  1. <step derived from issue body>
  2. <step>
  3. <step>

Say Go to start. (or run /implement to drive the plan, /brainstorm to refine scope)
```

## Rules

- Keep it scannable — no prose paragraphs. One line per field.
- Omit board fields that are unset rather than printing empty values.
- If a blocker is open, the ⚠️ line is mandatory and goes directly under the blocker.
- The plan is a proposal from the issue body, not a commitment — 3–6 steps is typical.
- Always end with the stop line. Never continue into implementation.

## Worked example

Board has one In Progress item, issue #142, label `bug`, one open blocker.

```
📋 Picked up: MMoMM-org/the-custom-startup#142 — Pre-push hook hides MERGED PRs
   Priority: P1 · Track: Tooling · Area: git-helpers
   Epic: #120 Git helper reliability

🔗 Blocked by:
   ⚠️ #138 (MMoMM-org/the-custom-startup#138) is still OPEN — this work may be blocked.

🌿 Branch: fix/142-pre-push-hook-hides-merged-prs  (from main)

Plan
  1. Reproduce the hidden-PR case in the pre-push hook with a MERGED PR fixture.
  2. Add the missing --state all flag to the gh pr list call.
  3. Add a regression test asserting MERGED/CLOSED PRs surface.
  4. Run the hook test suite and confirm green.

Say Go to start. (or run /implement to drive the plan, /brainstorm to refine scope)
```
