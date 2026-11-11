# Suite Gate

Used by `implement-incremental` and `implement-direct`. "The suite is green" means this
comparison, not a count of passing tests (#271).

## The command

The full suite is the one command a contributor runs before a merge. Take it from, in order:

1. The project instructions file (CLAUDE.md, AGENTS.md) or CONTRIBUTING.md.
2. The CI workflow's test step.
3. The README's testing section.

If none names one, ask the user. Do not guess a command or stitch one together per area. Use the
same command, with the same arguments, for the baseline and for every gate run.

## The baseline

Run the command once **before the first dispatch** and record:

- the command and the commit it ran on;
- the **set** of failing tests, each by its identifier as the runner prints it (a pytest node id, a
  bats test name, a file and test title); a test that errors counts as failing;
- whether the run completed. A run that could not start or crashed part-way is no baseline:
  that is an environment problem, so stop and report it before dispatching anything.

A baseline with failures is fine. Show it to the user before work starts.

## The gate

At each gate (the phase checkpoint, or the end of the direct run), run the same command and
compare the failure **sets**:

| Result | Meaning | Action |
|---|---|---|
| failing ⊆ baseline | nothing broke | pass; name any baseline test that now passes |
| a test fails that is not in the baseline | a regression | block; list each new failure by id |
| the run did not complete | environment problem | block; report the command and its error |

Compare identifiers, not a count. "3 failing before, 3 failing after" passes a gate that two
fixed tests and two new failures should block. A test renamed or removed by the work is a change
to report, not a pass.
