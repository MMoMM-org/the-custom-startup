# Hypothesis Hygiene

Vocabulary and ledger discipline for investigation. Load when an investigation is running long, when hypotheses are accumulating, or when the user pushes back on a finding.

---

## Epistemic prefixes

Every claim carries a prefix naming what it is actually worth. The prefix is for you as much as the reader — an untagged claim drifts from guess to fact through repetition alone.

| Prefix | Means | Earned by |
|---|---|---|
| `[hypothesis]` | A guess that fits what we know | Reading code, reading an error |
| `[evidence: X]` | An observation, with its source | Running something, reading a specific line, a log entry |
| `[ruled out: X because Y]` | A hypothesis actively falsified | A test that would have shown X, and did not |
| `[demonstrated]` | Toggling the condition makes the bug appear and disappear | Doing exactly that, both directions |

Only `[demonstrated]` may be reported as a root cause.

## The hypothesis ledger

Keep every hypothesis visible with its current state — `pending`, `supported`, `ruled out`, `demonstrated`. The ledger is the artefact that makes silent abandonment impossible.

**Never move from hypothesis A to hypothesis B without resolving A.** Either falsify it (`[ruled out: … because …]`) or park it explicitly (`unresolved — deferred because …`). Quietly moving on is speculation laundering: it looks like progress, it produces a list of untested guesses, and the one you dropped is often the right one.

A hypothesis that "no longer feels likely" is still `pending`. Feelings are not falsification.

## When you are stuck

Two untested hypotheses is the signal to **instrument, not theorise**. Generating a third costs nothing and buys nothing.

Descend in this order — each step buys a real observation:

1. **Read the path end-to-end.** Not the error site. The whole path.
2. **Add a probe.** Log the value you are guessing about, at the boundary where you are guessing.
3. **Write a failing test** that captures the symptom.
4. **Bisect.** Over commits, over inputs, over configuration — whatever varies.
5. **Assert the invariant** where you believe it holds. If it fires, you have your answer; if not, that region is clean.

The rule of thumb: if you cannot name the observation that would change your mind, you are not investigating, you are narrating.

## Root cause

A root cause is not the most plausible explanation. It is the one where you can **make the bug appear and disappear on demand** by toggling the suspected condition.

Both directions matter. Turning something off and seeing the bug vanish is one data point; turning it back on and seeing the bug return is what separates cause from coincidence.

If you cannot toggle it, say so: `[supported, not demonstrated]`. That is an honest state to report and stop at.

## Handling pushback

When the user disagrees, evaluate the substance before the tone.

- **They named evidence or reasoning you did not address** — acknowledge that specifically, and reformulate. Not "you're right, let me reconsider", but "you're right that the timestamp in the log predates the deploy; that rules out A".
- **They did not** — defend the position with the reasoning and evidence behind it. Folding to social pressure produces an agreeable investigation and an unfixed bug.

Changing position is fine. Changing position without a reason you can name is the failure mode.

## Never say

| Phrase | Why it is not a finding |
|---|---|
| "It's transient" | Restates the symptom; explains nothing |
| "It's a flake" | A hypothesis with no evidence, phrased as a conclusion |
| "It didn't recur in N attempts" | Insufficient instrumentation, not proof of absence |
| "Probably a race" | `[hypothesis]` wearing a conclusion's clothes |
| "That should fix it" | If it is fixed, demonstrate it; if not, say so |
