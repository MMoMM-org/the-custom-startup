# Complexity Classifier

Routes a specification to a decomposition tier — **Direct** or **Incremental** — at step 6 of the xdd workflow.

The classifier produces a **recommendation**. It never applies a tier: the user always sees the rationale and confirms or overrides before anything is recorded.

Two tiers ship today. **Factory** is a reserved name in the tier vocabulary with **no implementation** (spec 017, ADR-3) — never recommend it, and never record it. A tier the workflow cannot execute would route work to a loop that does not exist.

---

## When It Runs

At step 6, **after `requirements.md` and `solution.md` both exist**. Never on the raw request.

This is what keeps the classifier cheap. It reads two documents the workflow has already produced and computes an answer — no clarifying questions, no extra conversation turns. A classifier that interrogates the user has become the ceremony it exists to remove.

---

## Inputs

Five signals, all derivable from the two documents:

| Signal | Source | How to compute |
|--------|--------|----------------|
| `change_type` | requirements.md framing, or `$ARGUMENTS` | One of `feature`, `fix`, `refactor`, `doc`. Infer from how the request is framed. |
| `feature_count` | requirements.md | Distinct Must-Have features. A feature is a coherent user-visible capability with its own acceptance criteria; several criteria serving one capability count as one feature. |
| `ac_count` | requirements.md | Acceptance criteria across all features. |
| `component_count` | solution.md | Distinct components in the Building Block View. **Modifying an existing component does not increment this** — only new surface counts. |
| `parallel_markers` | solution.md | True when the design explicitly calls out parallel work, concurrent execution, or independent work streams. |

**When a signal cannot be determined**, use its most conservative value (`component_count = 0`, `parallel_markers = false`), say so in the rationale, and continue. Never block on a missing signal — a spec thin enough to lack a Building Block View is Direct-shaped anyway.

---

## Classification

Apply top to bottom, **first match wins**:

```
1. Incremental  if component_count >= 2
                OR feature_count >= 2
                OR parallel_markers

2. Direct       if change_type in {fix, refactor, doc}
                OR ac_count <= 2

3. Incremental  otherwise
```

**Why rule 1 comes first.** Breadth vetoes Direct whatever the change type. A refactor spanning three skills is not a small change just because it is a refactor. Ordering the veto ahead of the change-type escape is what makes that true by construction rather than by footnote.

**Reserved.** A Factory branch would sit above rule 1, keyed on `component_count >= 3` or `parallel_markers`. It is **not implemented**. Rule 1 currently absorbs those cases into Incremental, which is a correct-if-coarse answer.

### Edge cases

| Situation | Tier | Why |
|---|---|---|
| Stub spec — both documents near-empty | Direct | `ac_count <= 2` fires. No evidence of breadth exists; the user may override upward |
| Doc change touching four components | Incremental | Rule 1 fires first. Breadth beats change type |
| Many criteria, one component | Incremental | Criteria count alone never escalates a tier; it is one component's worth of work however long the list |
| Single-component fix with many criteria | Direct | Rule 2's `change_type` escape; breadth of one does not escalate |
| `component_count` undeterminable | Treated as 0 | Conservative default, stated in the rationale |

---

## Rationale Output

Always surface the signals that drove the recommendation, so the user can check them against their own documents:

> Classified as **Incremental** — solution.md describes 3 components (dispatcher, implement-direct, implement-incremental); requirements.md has 12 acceptance criteria across 2 features. No parallel work flagged.

> Classified as **Direct** — change_type=fix; modifies existing middleware only; 1 acceptance criterion; no new components.

> Classified as **Direct** — no Building Block View found, so component_count treated as 0; 2 acceptance criteria.

The confirmation question shows every available tier with the recommendation highlighted. The user may override freely.

---

## Override Behaviour

- **Direct → Incremental.** Run `xdd-plan` as if the classifier had said so. Nothing is lost — Direct wrote no artifact to conflict with.
- **Incremental → Direct.** Skip decomposition. Any `plan/` already written is **left in place and flagged stale** in the decision log.

Never delete artifacts on a tier change. Cleanup is manual and deliberate; automatic deletion of specification content is not a risk worth taking to save a manual step.

---

## Decision Logging

Whatever tier is chosen — recommendation accepted or overridden — record it in **both** places (spec 017, ADR-6):

1. **The spec README Status table**, `Decomposition tier` row. This is what `spec.py --read` parses and what the implementation dispatcher cross-checks. Without this row the tier is invisible to every machine consumer.
2. **The spec README Decisions Log**, one row carrying the date, the chosen tier, the classifier's recommendation, and the rationale.

```
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-03 | Decomposition tier: Incremental | Classifier recommended Incremental (2 features, 3 components). Accepted. |
| 2026-09-03 | Decomposition tier: Incremental (override) | Classifier recommended Direct (change_type=fix, 1 component). User chose Incremental because the change touches the release path. |
```

The log makes the choice auditable; the Status row makes it executable. A tier recorded only in the log is a tier the dispatcher cannot see.
