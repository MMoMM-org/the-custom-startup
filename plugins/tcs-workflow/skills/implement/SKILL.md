---
name: implement
description: "Implementation entry point. Use to execute a completed specification — 'implement spec 017', 'run the plan', 'build what we specified' — at whichever decomposition tier it was written for."
user-invocable: true
argument-hint: "spec ID to implement (e.g., 001), or file path"
allowed-tools: Bash, Read, LS, Glob, Grep, AskUserQuestion, Skill
---

## Persona

**Active skill: tcs-workflow:implement**

Act as the implementation entry-point dispatcher: resolve the spec, see which decomposition artifacts exist, hand off to the loop that implements them. You orchestrate nothing yourself — every loop body lives in a sub-skill.

**Implementation Target**: $ARGUMENTS

## Interface

DispatchTarget {
  tier: Direct | Incremental
  skill: implement-direct | implement-incremental
  artifact: string           // what triggered the dispatch, shown to the user
}

State {
  target = $ARGUMENTS
  specDirectory: string
  recordedTier: Direct | Incremental | None   // from spec.py --read; None for pre-tier specs
  dispatch: DispatchTarget
}

## Constraints

**Always:**
- Detect from the artifacts on disk. They are ground truth; a recorded tier can be stale.
- Cross-check the detected route against the recorded tier, and report a mismatch before dispatching anything.
- Pass `$ARGUMENTS` to the sub-skill unchanged.
- Show which route was selected and which artifact triggered it, before handing off.
- Invoke exactly one sub-skill per invocation.

**Never:**
- Implement, orchestrate, or review anything. The sub-skills own all execution.
- Guess a route. An artifact this workflow does not implement stops the dispatch.
- Modify spec artifacts. Each sub-skill owns its own updates and its own completion summary.
- Post-process a sub-skill's output. It reports directly to the user.

## Reference Materials

A dispatcher owns no references; each sub-skill owns its own:

- [implement-direct](../implement-direct/SKILL.md) — phase-less loop, for a spec with no decomposition artifact
- [implement-incremental](../implement-incremental/SKILL.md) — phase loop with the per-task review chain

## Workflow

### 1. Resolve

Invoke `Skill(tcs-workflow:xdd-meta)` with `$ARGUMENTS` to resolve the spec directory and read its status. The `--read` output carries `decomposition_tier`, empty for every spec written before tiers existed. When `$ARGUMENTS` is a file path or freeform brief rather than a spec ID, skip resolution and route to `implement-direct`.

### 2. Detect

Inspect the resolved directory, top to bottom, first match wins:

```
manifest.md or units/ present      => STOP. Report the artifact found; this
                                      workflow implements no tier that produces
                                      it. Do not route.
plan/README.md present             => Incremental, triggered by "plan/README.md"
implementation-plan.md present     => Incremental, triggered by the legacy plan
requirements.md or solution.md      => Direct, triggered by "requirements.md + solution.md"
nothing of the above               => ERROR. No specification artifacts found.
                                      Run /xdd first, or pass a brief.
```

The unknown-artifact branch is checked first on purpose. A spec carrying both a plan and an unrecognised artifact is ambiguous, not incremental, and routing it would send work to the wrong loop.

### 3. Cross-check

Compare the detected route against `recordedTier`:

match (recordedTier) {
  None                  => proceed silently. Pre-tier specs are the normal case.
  agrees with detection => proceed.
  disagrees             => report both — what was recorded, what was found, and
                           what each implies — then ask before proceeding. This
                           usually means an interrupted /xdd run, for example a
                           tier recorded as Incremental with no plan written yet.
}

### 4. Hand off

Show one line, then invoke the sub-skill with `$ARGUMENTS` unchanged:

```
Detected: plan/README.md → routing to implement-incremental
Detected: no decomposition artifact → routing to implement-direct
```

Each sub-skill reads its own artifacts, runs its own loop, and presents its own completion summary — nothing returns here.
