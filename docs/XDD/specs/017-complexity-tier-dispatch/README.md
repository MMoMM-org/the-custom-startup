# Specification: 017-complexity-tier-dispatch

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-03 |
| **Current Phase** | SDD |
| **Last Updated** | 2026-09-03 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 5 Must / 2 Should / 2 Could / 5 Won't; 24 acceptance criteria; 0 clarification markers |
| solution.md | in_progress | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-03 | Spec opened from issue #83 | Issue explicitly asks for `/xdd` rather than a PR: the change alters the core workflow contract that `xdd-meta`, `implement`, `xdd-plan` and the repo's own spec-first rule all depend on. |
| 2026-09-03 | Research done inline, no research-agent fan-out | Issue #83 named the exact inputs to read (upstream `rsmdt/the-startup` tier sub-skills and classifier, `obra/superpowers` v6.3.0 ceremony scaling, the four local skills in scope). All were read directly. Fanning out research agents over ground already covered would add cost without adding findings. |
| 2026-09-03 | Tier the PLAN only, not the documents | The two upstreams disagree: `rsmdt` keeps requirements+solution at every tier and scales only decomposition; `superpowers` scales the documents themselves. Chose `rsmdt`. Keeps the repo's spec-first rule literally true, lets the classifier read real documents instead of guessing from a raw request, and preserves the artifact that the whole feature exists to produce. Accepted cost: a one-line fix still writes two short documents. |
| 2026-09-03 | Direct tier keeps TDD, approval and drift gates; drops the per-task reviewer chain | Issue #83 required an explicit answer rather than an omission, since dropping the TDD gate would contradict `xdd-tdd`'s iron law. The per-task spec-compliance and code-quality reviewers are the cost driver; the test-first and approval gates are the guarantees. Matches what upstream's `implement-direct` actually kept. |
| 2026-09-03 | PRD complete | 24 acceptance criteria across 5 must-have features. 3 open questions, none blocking SDD. |

## Context

Tracks issue [#83](https://github.com/MMoMM-org/the-custom-startup/issues/83), a child of the upstream drift sweep epic [#73](https://github.com/MMoMM-org/the-custom-startup/issues/73).

**Problem in one line:** TCS applies the same three-document ceremony to a one-line fix as to a new subsystem, so for small work the ceremony gets skipped entirely — which yields no artifact at all, strictly worse than a smaller artifact.

**Research inputs read before drafting:**

| Source | Revision | What it contributes |
|---|---|---|
| `rsmdt/the-startup` `plugins/start/skills/implement/SKILL.md` | main @ 2026-09-03 | Dispatch by **artifact detection**, not re-classification |
| `rsmdt/the-startup` `.../specify/SKILL.md` + `reference/classifier.md` | main | Classifier runs *after* requirements+solution exist; five signals; user may override; overrides logged |
| `rsmdt/the-startup` `.../implement-direct/SKILL.md` | main | Phase-less orchestrator; 1–3 delivery units; >3 units ⇒ escalate tier |
| `rsmdt/the-startup` `.../specify-meta/SKILL.md` | main | `decomposition_tier` as a first-class lifecycle field |
| `obra/superpowers` v6.3.0 release notes | v6.3.0 | Spike / bounded / architectural; small tasks skip the two-document ritual; approval gate survives every tier |
| Local: `xdd`, `implement`, `xdd-meta`, `xdd-plan` | this repo | The contract being changed |

**The load-bearing finding, and the open question it creates.** The two upstreams do *not* agree on what scales:

- `rsmdt` keeps **requirements + solution at every tier** and tiers only the third artifact (decomposition): Direct writes no plan, Incremental writes `plan/`, Factory writes `manifest.md` + `units/` + `scenarios/`.
- `superpowers` scales the **documents themselves** — small tasks skip the two-document ritual.

TCS must pick one. This is the first question the PRD has to answer, because everything else (classifier placement, `xdd-meta` fields, migration) follows from it. It is recorded here so the decision is visible rather than implied by whichever upstream got copied.

---
*This file is managed by the xdd-meta skill.*
