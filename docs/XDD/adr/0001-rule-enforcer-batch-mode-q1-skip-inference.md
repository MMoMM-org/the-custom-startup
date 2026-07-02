# ADR 0001 — rule-enforcer batch mode skips Q1 and infers Q2/Q3/Q4 non-interactively

## Status

Accepted

## Context

The interactive `tcs-helper:rule-enforcer` skill walks a user through four
structured questions (Q1–Q4) to route a single recurrence rule to the right
enforcement mechanism. Its `Constraints → Never` block
(`plugins/tcs-helper/skills/rule-enforcer/SKILL.md`, ~L47–51) hard-codes two
invariants that assume an interactive, one-rule-at-a-time session:

- **Never skip the Q1 short-circuit** — if the rule has only happened once,
  defer to `memory-add` (Step 2, L63–74).
- **Never infer Q2** — a `No-judgment` Q2 answer must short-circuit to a
  per-rule `memory-add` hand-off with strong-language wording (Step 3, L76–86;
  Step 8, L170–172).

Spec 016 adds a **BATCH mode** that scans a *file of already-codified rules*
(e.g. `CLAUDE.md`, memory files) and proposes mechanisms for many candidates at
once. In that source, both interactive invariants become nonsensical or hostile
at N-scale:

- **Q1 (recurrence)** is meaningless — a rule that is *already written down* is,
  by construction, recurring/established. Asking "how many times have you
  violated this?" for a rule the user already codified adds no signal.
- **Per-rule Q2 → memory-add** would fire N interactive hand-offs (one per
  judgment-only candidate) against rules that already live in memory/guidance —
  an O(N) prompt storm that re-adds what is already recorded.

Batch mode is reachable only via the Step 0 mode dispatch
(`--scan` / `--from-file` / empty args → BATCH), so the interactive path is
never entered by the batch pipeline and vice versa.

## Decision

In **BATCH mode only**:

1. **Skip Q1 entirely.** Recurrence is presumed because the rule is already
   written down; there is no first-time case to short-circuit.
2. **Infer Q2/Q3/Q4 non-interactively** from the rule text (directive strength,
   detectability signals, intervention point, enforcement style) instead of
   asking the user per candidate.
3. **Treat `Q2 = No` (judgment-only) as a FILTER, not a hand-off.** Such
   candidates are dropped to a "left as guidance" list in the consolidated
   proposal, rather than triggering a per-line `memory-add` — they already exist
   as guidance in the scanned file.

The `mechanism-matrix.md` file remains the **single source of truth** for the
`(Q3, Q4) → mechanism` mapping. Batch mode emits bare-label Q3 strings and looks
them up in the matrix exactly as the interactive path does, then feeds each
accepted candidate into the *unchanged* Step 8 hand-off dispatch (slug gates and
templates inherited verbatim).

## Consequences

### Positive

- **O(1) confirmation instead of O(N×4) prompts.** One consolidated review gate
  replaces four questions per candidate across the whole file.
- **Matches the source.** A file of already-codified rules does not need Q1
  recurrence proof or N memory re-adds; inference + a single confirm fits the
  input shape.
- **No matrix divergence.** Reusing `mechanism-matrix.md` and the Step 8
  dispatch keeps batch and interactive routing behaviourally identical.

### Negative / trade-offs

- **Inference can misjudge without the human Q2 answer.** A candidate the human
  would have called "judgment-only" (or vice versa) may be mis-routed.
  - *Mitigation 1:* low-confidence inferences are flagged **needs-review** and
    default-off, so uncertain candidates are not silently actioned.
  - *Mitigation 2:* the single batch **confirm gate** is the review point — the
    human approves the consolidated proposal (and the "left as guidance" list)
    before any hand-off runs.

### Scope

This exception is **batch-mode-only** and gated by the Step 0 dispatch. The
interactive mode is unchanged: its `Never skip Q1` and `Never infer Q2`
constraints still hold in full for single-rule, interactive triage. No new
persistence is introduced (inherits ADR-3: rule-enforcer v1 has no scan-state
persistence).

## References

- Spec 016 — rule-enforcer batch/extraction mode:
  `docs/XDD/specs/016-rule-enforcer-claude-md-sweep/` (this decision is the
  spec-internal "ADR-2").
- Interactive skill under exception:
  `plugins/tcs-helper/skills/rule-enforcer/SKILL.md`
  (Constraints `Never` block; Step 2 Q1 short-circuit; Step 3 Q2 short-circuit;
  Step 8 hand-off).
- Mechanism SSOT:
  `plugins/tcs-helper/skills/rule-enforcer/reference/mechanism-matrix.md`.
