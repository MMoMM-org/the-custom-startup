# Output Format — Direct Tier

Two reports. Keep both short: this tier exists because the work is small, and a
summary longer than the change defeats the point.

---

## Decomposition Summary

Presented before any work is dispatched, as the thing the user approves.

```
Direct tier — 2 delivery units

  1. Tier row in the spec README template          [docs]
     refs: SDD/Data Storage Changes
     done: a scaffolded spec carries the row and reads back as untiered

  2. spec.py reports decomposition_tier            [script]
     refs: SDD/Interface Specifications, ADR-6
     done: --read emits the key; the 16 existing specs still exit 0

Nothing dispatched yet.
```

If the decomposition needs more than three units, say so plainly instead of
presenting it:

```
Direct tier is the wrong fit — this decomposes into 5 units.

Re-run /xdd on this spec and choose Incremental; the work wants phase
boundaries. Nothing has been dispatched.
```

---

## Unit Result

One block per delivery unit, as it lands. Extract, do not paste the agent's reply.

```
Unit 1/2 — Tier row in the spec README template ✓
  files:  plugins/tcs-workflow/skills/xdd-meta/template.md
  tests:  32 passing
  notes:  placeholder reads back as absent, as required
```

Report a blocker in the same shape, with what it needs:

```
Unit 2/2 — spec.py reports decomposition_tier ✗ BLOCKED
  reason: --read has no README parsing to extend
  needs:  a decision on whether to add one or derive the tier elsewhere
```

---

## Completion Summary

```
Direct implementation complete — spec 018

  units:   2/2
  files:   3 changed
  tests:   230 passing
  drift:   none
  constitution: n/a (no CONSTITUTION.md)
  spec:    018 finalized → Implemented

Next: Commit + PR | Commit only | Skip
```

**Always include the finalize line.** A completion summary that does not say the
spec was closed is how specs end up sitting on `Ready` after they shipped — the
failure this repository has already recorded once.

State drift findings even when they are empty. "drift: none" is evidence the
check ran; omitting the line is indistinguishable from skipping it.
