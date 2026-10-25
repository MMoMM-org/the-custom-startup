# tcs-workflow evals

`claude plugin eval` cases for tcs-workflow skills. They run locally only: every run calls the
model on your own credential. How to write a case: `tcs-helper:skill-author`,
`reference/plugin-evals.md`.

## Run

From the repository root:

```bash
claude plugin eval plugins/tcs-workflow --runs 3 -j 4 --allow-tools Write Edit \
  --trust-plugin --no-publish --max-cost-usd 10
```

One case: add `--case <name>`. Against a deliberately weakened skill: add `--ablation none` to skip
the no-plugin arm. Results go to `evals/results/`, which is gitignored.

## Cases

| Case | Measures | With plugin | Without | Rule weakened |
|---|---|---|---|---|
| `xdd-tdd-plain` | xdd-tdd triggers unprompted on a plain implementation request | 1.0 | — | 0 (old description) |
| `xdd-tdd-no-trigger` | xdd-tdd stays out of a documentation-only request | 1.0 | — | — |
| `xdd-tdd-pressure` | xdd-tdd triggers unprompted when the user explicitly postpones tests | 0 | 0 | — |
| `xdd-tdd-pressure-invoked` | xdd-tdd, typed, holds test-first under the same pressure | 1.0 | 0 | 0.08 |
| `review-breaking-change` | removing a parameter from a published function leads the report as breaking, verdict REQUEST CHANGES | 1.0 | 0.2 | 0.73 |
| `review-breaking-rename` | a behaviour-preserving rename of a published function, the same | 1.0 | 0.2 | 0.53 |

Scores from 3 runs per arm on Claude Code 2.1.309 with Opus 5.5, judge Haiku.

- The trigger cases were measured with `--ablation none`: without the plugin there is no skill to
  fire. `xdd-tdd-plain` scored 0 with the earlier description ("Use at the start of each
  implementation task") and 1.0 with the current one.
- `xdd-tdd-pressure` still scores 0: when the user says "tests after the demo", the model follows
  that instruction and never invokes the skill, whatever the description says. Typed, the skill
  holds (`xdd-tdd-pressure-invoked`).
- The review cases' "rule weakened" score comes from removing the breaking-changes section and the
  breaking-forces-REQUEST-CHANGES rule. The section grader catches it. The verdict mostly stays
  REQUEST CHANGES anyway, because the model rates breaking a published API as severe on its own.

## Cost

| Case | Per run, with plugin | Per run, without |
|---|---|---|
| xdd-tdd cases | about $0.10–0.25 | about $0.10 |
| review cases | about $0.65 (reviewer subagents) | about $0.08 |

The full suite at 3 runs per arm costs about $5 and takes 2–3 minutes with `-j 4`.
