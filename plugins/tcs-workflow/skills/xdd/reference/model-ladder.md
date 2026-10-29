# Model Ladder

The one definition of "a stronger model" for the workflow. The classifier (xdd step 6) and both implement loops link this file and never restate a rung.

Everything here degrades instead of stopping: no model problem halts a run. A rung that cannot be used is skipped or capped, and the step is logged.

---

## Ladder

Five rungs, lowest to highest:

| Rung | Dispatch parameters |
|------|---------------------|
| `haiku` | `model: haiku` |
| `sonnet` | `model: sonnet` |
| `opus` | `model: opus` |
| `opus@max` | `model: opus`, `effort: max` |
| `fable` | `model: fable` |

- Pass **aliases only** (`haiku`, `sonnet`, `opus`, `fable`). Never write a full model ID: IDs change, aliases follow them.
- `opus@max` is not a model. It is `opus` with per-dispatch `effort: max`, and needs Claude Code 2.1.292 or later.
- If the Agent tool rejects `effort` (older Claude Code), re-dispatch at `opus` without effort and log a substitution with the reason "effort unsupported".
- A `CLAUDE_CODE_EFFORT_LEVEL` in the user's environment overrides the per-dispatch effort. `opus@max` then runs at that level.
- Escalation never goes down and never skips a rung.

---

## Starting Rung

The task's tier is its `[model: …]` tag when the value is recognised (`routine`, `hard`, `frontier`), otherwise the spec's model tier. An unknown tag value falls back to the spec tier; report the unknown value once for that task.

| Tier | Incremental spec | Direct spec |
|------|------------------|-------------|
| absent, placeholder or unknown | step 4b as today | no `model` parameter (inherits the session model); the first escalation goes to `opus`, then follows the ladder |
| `routine` | step 4b as today | `sonnet` |
| `hard` | `opus` | `opus` |
| `frontier` | `fable` | `fable` |

A `frontier` tag in a spec whose tier is not `frontier` needs consent first (see Consent). Yes: start on `fable`, and the task counts as planned. No, a dismissed prompt, or nobody to ask: run at the `hard` rung.

A spec whose tier is `frontier` and was confirmed by the user needs no further consent for its planned tasks.

---

## Escalation

Exactly two triggers move a task up:

1. The implementer reports **BLOCKED** for reason **complexity**.
2. The task fails review **twice in a row at the same rung**. Spec-compliance and code-quality reviews count together as one counter per task.

Three BLOCKED reasons never escalate: **missing context**, **task too large**, **wrong plan**. Handle them as the loop handles them today.

```
on implementer result for task T at rung R:
  BLOCKED(complexity)        -> escalate(T)
  BLOCKED(other reason)      -> today's handling, no escalation
on reviewer PASS for task T:  T.failures_at_rung = 0
on reviewer FAIL for task T:
  T.failures_at_rung += 1
  if T.failures_at_rung == 2 -> escalate(T) and re-dispatch with the fix list
  else                       -> re-dispatch at R with the fix list

escalate(T):
  T.failures_at_rung = 0
  next = rung after T.rung
  if T.rung == fable or (T.rung == opus@max and run.fable_unavailable)
                             -> report BLOCKED to the user; stop
  if next != fable           -> T.rung = next; log escalation; re-dispatch
  if nobody can be asked     -> log "fable not reached: no one to ask"; report BLOCKED at opus@max
  ask the user (Consent):
    yes -> T.rung = fable; T.fable_consent = true; log consent and escalation; re-dispatch
    no  -> log declined; report BLOCKED at opus@max
```

Rules the pseudocode encodes:

- **One rung at a time.** The count starts again at 0 after every escalation; a PASS also resets it. A FAIL, a PASS, then a FAIL is not two in a row.
- **Automatic up to `opus@max`.** No question is asked for any rung below `fable`.
- **The cap.** At the highest rung a task may reach, the same triggers report **BLOCKED** to the user instead of retrying. This bounds every review loop. The highest reachable rung is `fable` after consent, and `opus@max` when fable is unavailable, declined, or nobody can be asked.
- **Log every escalation** (see Decisions Log).

---

## Consent

Every dispatch to `fable` needs a person's consent, except a planned task in a spec whose `frontier` tier the user confirmed. Consent is asked:

- at escalation from `opus@max` to `fable`;
- for a `frontier` task tag in a spec whose tier is not `frontier`.

Ask in one question that carries the cost sentence (see Cost Sentence). Answer yes: dispatch on `fable`, log the consent. Answer no: log the decline and stay at the capped rung.

**Nobody can be asked** means: `YOLO=true`, or the question returns no answer or an error (`claude -p`, Agent SDK). Then fable is never dispatched: an escalation is reported BLOCKED at `opus@max` with a log row, and a `frontier` tag runs at the `hard` rung.

---

## Fable Failure

A fable dispatch fails when it returns an error (not entitled, refused), when its Claude Code consent prompt is dismissed or unanswered, or when it is served by another model (see Served Model). Then:

- fable is **off for the rest of the run**; never try it again;
- a **planned** task (frontier tier confirmed, or consent given for a frontier tag): re-dispatch at `opus@max`, log the substitution, continue;
- an **escalated** task: log the substitution as refused and report BLOCKED. `opus@max` has already failed it.

A spec classified `frontier` on a machine without fable still starts; the first fable dispatch takes this path.

---

## Served Model

After every dispatch, check which model answered. The Agent tool returns the subagent transcript as `output_file`. Read **only** the `message.model` field:

```bash
jq -r 'select(.type == "assistant") | .message.model' <output_file> | sort -u
```

The dispatch matches when every served model belongs to the family of the requested alias. Compare by the alias name (`opus` within the served ID), never against a hard-coded full model ID. A mismatch is logged as a substitution naming the served model. A `fable` dispatch served by another model is a fable failure.

Read no other part of the transcript. If the file cannot be read, skip the check; a missing check never blocks a dispatch.

---

## Cost Sentence

Shown wherever fable is offered: the `frontier` option in the classifier's confirmation round, and every runtime consent question.

> Fable costs about 2.5× Opus per token and can bill usage credits instead of your plan's limits.

The sentence states the ratio and the billing route, never prices: prices change.

---

## Decisions Log

Escalations, consents and substitutions are Decisions Log rows, written through xdd-meta step 4. Four formats:

```
| <date> | Model escalation: T2.1 opus → opus@max | Trigger: second review FAIL |
| <date> | Fable consent: T2.1 | Asked at escalation; user agreed |
| <date> | Model substitution: T2.1 | Requested fable, ran opus@max: dispatch error <reason> |
| <date> | Model substitution: T2.1 | Requested fable, served <model> (message.model) |
```

The escalation row names the task, the rung before and after, and the trigger (`second review FAIL` or `complexity BLOCKED`). A decline, "fable not reached: no one to ask", and a refused substitution use the same two-cell shape: what happened for the task, then why.

The spec's own `Model tier` row is written by the classifier step, not here.
