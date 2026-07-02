# Rule Enforcer — Extraction Heuristics

Examples-driven heuristics for **batch mode**: sweeping a CLAUDE.md (or memory
bank) and triaging every candidate rule without a per-rule dialogue. Where the
interactive `/enforce-rule` skill asks the 4 questions one rule at a time, batch
mode applies these heuristics to (a) filter enforceable vs judgment (the Q2
gate), (b) infer the Q3 bucket, and (c) pick a Q4 default — then hands the
survivors to the mechanism matrix.

These heuristics recognize a rule **by analogy** to the 5 worked cases in
[examples.md](examples.md), which is the training set. Match against a real case,
not an abstract property (PRD M3 design constraint).

> **SSOT boundary**: the `(Q3, Q4) → mechanism` mapping lives **only** in
> [mechanism-matrix.md](mechanism-matrix.md). This file infers the Q3 and Q4
> *inputs*; it never restates the mechanism table. After Q3/Q4 are inferred,
> look the mechanism up there.

---

## 1. Enforceable vs judgment (the batch Q2 gate)

Every candidate is first classified. Only **enforceable** rules become
mechanisms; the rest drop to a guidance list and are **not** fired as per-line
memory-add.

**Enforceable** — the violation is detectable by machine, no per-occurrence
human judgment. Signals:

- **Concrete tool / flag / command** — names a specific invocation, e.g.
  `--break-system-packages`, `git push`, `--no-verify`, `pip install`.
  (cf. examples.md #4)
- **File / path predicate** — a check on which files changed, e.g. `CHANGELOG`
  present, `README` updated, `marketplace.json` unchanged while `plugin.json`
  changed. (cf. examples.md #1, #2)
- **Git boundary** — anchored to push / merge / branch, e.g. "block push if
  CHANGELOG missing", "bump on merge". (cf. examples.md #1, #2)
- **Structural check** — a missing line, a missing version bump, an absent test
  file — countable presence/absence. (cf. examples.md #3)

**Not enforceable → guidance list** (do NOT emit a per-line memory-add):

- **Subjective quality** — "keep code clean", "be concise", "use good names".
  No machine can rule on satisfaction per occurrence.
- **Knowledge recall** — "remember the syntax for jq `--arg`". Nothing to
  intercept; there is no wrong *action*. (cf. examples.md #5)
- **Anything needing human judgment per occurrence** — "use the right
  abstraction", "prefer the simpler design".

When in doubt, a rule is enforceable only if you can name the exact string,
path, or boundary a script would test.

---

## 2. Q3 bucket inference cues

For each enforceable rule, infer the earliest intervention point by matching the
cue below to one of the 7 canonical buckets. The bucket names here are
**byte-identical** to the `## Q3 = <label>` headings in mechanism-matrix.md.

<!-- Q3-LABELS-START -->
Before Claude calls a tool
After Claude calls a tool
User submits a prompt
Session start
Local git push
PR/merge to main
In repeated coding patterns
<!-- Q3-LABELS-END -->

Cues (one per canonical label):

- **Before Claude calls a tool** — the rule constrains a shell command or flag
  Claude is about to run (block/rewrite it before execution). e.g.
  `--break-system-packages` guard.
- **After Claude calls a tool** — the rule is a post-action review that fires
  once an edit/action already happened. e.g. run skill-author after editing
  `skills/`.
- **User submits a prompt** — prompt-time context injection or redirect. e.g.
  inject context when a recurrence-signal phrase is detected.
- **Session start** — session/startup/env-restore or tool-version validation.
  e.g. restore context or check versions at session open.
- **Local git push** — push / pre-push time, or a docs gate that must hold
  *before PR creation*. e.g. CHANGELOG-before-PR.
- **PR/merge to main** — merge / PR / CI, or an auto-bump that runs on merge.
  e.g. bump `marketplace.json` on merge.
- **In repeated coding patterns** — a discipline or workflow habit with **no
  discrete tool call or git boundary** to hook. e.g. TDD discipline.

If two cues seem to fit, prefer the **earliest** boundary (the interactive skill
defines Q3 as the *earliest* intervention point).

---

## 3. Q4 default selection

Pick the response strength by the rule's failure cost:

- **Destructive / env-corrupting → Block.** If letting it through leaves the
  system broken (env pollution, data loss) and the correct alternative is
  unambiguous. e.g. `--break-system-packages`. (cf. examples.md #4)
- **Docs gate → Nudge.** Nudge (warn + exit 0) is the *honest* default for docs
  gates: a hard block with `--no-verify` available just trains bypassing.
  (cf. examples.md #2, PRD M6 refinement)
- **Pure-mechanical fill → Auto-fix.** If the fix is a deterministic edit with
  no human decision (bump a number, restage a file). e.g. marketplace bump.
  (cf. examples.md #1)

Confidence guards:

- **Low-confidence inference → mark `needs-review`** (default OFF). If the Q3 or
  Q4 inference is a guess, emit the candidate flagged for human confirmation
  rather than shipping an active hook.
- **High-false-positive-but-plausible → demote.** If a rule is plausible but
  would misfire often (e.g. a rule about a literal `!` in shell commands), route
  it to nudge/memory or a warning — **never** a silent block hook.

---

## Training set

The five worked cases in [examples.md](examples.md) map real rules through
Q2/Q3/Q4 to a mechanism. Use them as the analogy set when a candidate is
ambiguous: find the closest worked case and follow its classification. The
mechanism itself is then read from [mechanism-matrix.md](mechanism-matrix.md).
