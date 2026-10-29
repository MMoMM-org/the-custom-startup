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

**What counts as a component.** A unit with its own interface and responsibility — a module, skill, agent, hook, service or script. A single function or helper is part of the component that contains it, not a component of its own: counting functions makes the `>= 2` threshold fire on changes that are one unit wide. When the Building Block View lists functions, group them by the unit they live in and count the units.

**New surface named only outside the Building Block View** — in an implementation example, say — is not counted. Name it in the rationale ("`foo` appears only in an example; not counted"), so the user can see that the solution.md is incomplete there and override if it matters (#161).

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
3. **The spec README Documents table**, `plan/` row. On **Direct**, set it to `skipped` with the tier as the note — a Direct spec has no plan *by decision*, and a row left at `pending` reads as work outstanding. On **Incremental**, it follows the plan as usual.

```
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-03 | Decomposition tier: Incremental | Classifier recommended Incremental (2 features, 3 components). Accepted. |
| 2026-09-03 | Decomposition tier: Incremental (override) | Classifier recommended Direct (change_type=fix, 1 component). User chose Incremental because the change touches the release path. |
```

```
| Document | Status | Notes |
|----------|--------|-------|
| plan/ | skipped | Direct tier writes no decomposition artifact |
```

The log makes the choice auditable; the Status row makes it executable. A tier recorded only in the log is a tier the dispatcher cannot see.

---

## Model Tier

A second recommendation, computed in the **same step-6 pass** from the same two documents and confirmed in the **same round** as the decomposition tier. It picks how strong a model the implement loops start with: **routine**, **hard** or **frontier**.

The classifier **recommends** a model tier. It never applies one: the user sees the rationale and confirms or overrides before anything is recorded.

What each tier means is owned by [model-ladder.md](model-ladder.md) — routine is the existing selection, hard starts at a stronger model, frontier at the strongest. Rungs, dispatch parameters and the cost sentence live there and nowhere else; the confirmation question takes the cost sentence from that file.

### Inputs

Four signals. `change_type` is shared with the decomposition tier; the others come from the same two documents.

| Signal | Source | How to compute |
|--------|--------|----------------|
| `change_type` | as for the decomposition tier | Shared; computed once. |
| `high_risks` | requirements.md, Risks and Mitigations table | Rows whose Impact cell is `High`. |
| `novel_pattern` | solution.md, Pattern Documentation | True when "New patterns created" lists at least one entry; an entry reading "None" or "N/A" counts as empty. |
| `adr_count` | solution.md, Architecture Decisions | Number of ADR entries. |

**When a signal cannot be determined**, lower it: `high_risks = 0`, `novel_pattern = false`, `adr_count = 0`. Name each lowered signal in the rationale and continue. Never block on a missing signal.

### Classification

Apply top to bottom, **first match wins**:

```
1. routine   if change_type == doc
2. frontier  if novel_pattern AND high_risks >= 2
3. hard      if novel_pattern OR high_risks >= 1 OR adr_count >= 3
4. routine   otherwise
```

**Why rule 1 comes first.** A doc change cannot break behaviour, so risk and novelty in its subject matter do not make the work harder to execute. **Why rule 2 comes before rule 3.** The frontier test is the strict case of the hard test; ordering it first keeps rule 3 from absorbing it.

### Edge cases

| Situation | Tier | Why |
|---|---|---|
| Doc rewrite, one High risk, a new doc pattern | routine | Rule 1 fires first |
| Spec with 7 ADRs, no High risk, no new pattern | hard | Rule 3: `adr_count >= 3` |
| Novel pattern, two High risks | frontier | Rule 2 |
| Two High risks, no new pattern | hard | Rule 2 needs both conditions; rule 3 catches the risks |
| Small fix, only Medium risks | routine | Rule 4 |
| No Pattern Documentation section, one High risk | hard | `novel_pattern = false` (undeterminable), rule 3 on `high_risks >= 1` |

### Rationale examples

> Model tier **hard** — adr_count=7 (>= 3); no High risks; no new patterns.

> Model tier **frontier** — novel_pattern=true (consensus protocol); high_risks=2.

> Model tier **routine** — change_type=fix; no High risks; no new patterns; adr_count=0.

> Model tier **hard** — novel_pattern=false (no Pattern Documentation section; undeterminable); high_risks=1.

### Decision Logging

Whatever tier is chosen — accepted or overridden — record it in **both** places, as for the decomposition tier:

1. **The spec README Status table**, `Model tier` row.
2. **The spec README Decisions Log**, one row with the date, the chosen tier, the recommendation and the rationale.

On an override, the reason is the user's **free-text** answer; without one, log `no reason given`.

```
| 2026-10-29 | Model tier: hard | Classifier recommended hard (adr_count=7). Accepted. |
| 2026-10-29 | Model tier: frontier (override) | Classifier recommended hard (adr_count=7). User chose frontier because the protocol is novel to the team. |
| 2026-10-29 | Model tier: routine (override) | Classifier recommended hard (adr_count=7). User chose routine (no reason given). |
```
