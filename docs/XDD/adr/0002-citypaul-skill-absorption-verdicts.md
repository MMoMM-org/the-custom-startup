# ADR 0002 — Absorption verdicts for nine upstream citypaul skills

## Status

Accepted — 2026-08-31

## Context

`citypaul/.dotfiles` shipped roughly ten skills when TCS ported its `tcs-patterns`
set in March 2026. It now ships around fifty. The 2026-08-31 upstream sweep
(epic #73) shortlisted nine of the new ones as plausible additions and issue #80
asked for an accept/decline verdict on each.

The evaluation used `tcs-helper:skill-evaluate`'s criteria. Its first check is
decisive:

> **U1** — Does TCS already have a skill/agent that covers this? YES = overlap
> exists → score 0.

and its integration check prefers absorption over addition:

> **I2** — Can it be merged into an existing skill rather than added standalone?
> YES = prefer merge.

So the work was an overlap analysis against the current inventory (17
`tcs-patterns` skills, 21 `tcs-workflow`, 17 `tcs-helper`, 15 `tcs-team` agents)
before any quality judgement.

## Decision

Four accepted, four declined, one declined-with-merge.

### Accepted — port to PICS format

| Skill | Gap it fills | Boundary to watch |
|---|---|---|
| `observability` | We have nothing on instrumentation *placement* — wide events, OpenTelemetry traces/metrics, context propagation, sampling. `twelve-factor` covers logs in one line. | `tcs-team:the-devops:monitor-production` owns SLOs, alerting and dashboards. The skill must teach placement, not re-review production readiness. |
| `event-sourcing` | Append-only log as source of truth, Decider write model, projections, event versioning. | `tcs-patterns:event-driven` (TCS-native) owns messaging discipline — schemas, idempotency, correlation IDs, ordering. Different concern: persistence model vs. message contract. Keep separate; cross-link. |
| `secure-oauth-oidc` | We have **no auth pattern skill at all**. RFC 9700 / BCP 240 depth. | `tcs-team:the-architect:review-security` reviews; it does not teach. |
| `bff-entry-points` | Browser-facing route protection — public/protected classification, session, Origin and Fetch Metadata checks, CSRF. Nothing in TCS covers this. | `tcs-patterns:api-design` (TCS-native) owns REST semantics and error shapes, not entry-point hardening. |

### Declined with merge — `ubiquitous-language`

Direct U1 overlap. `ddd` already owns ubiquitous language in three places: its
`description`, an Always constraint, and workflow step 3, plus glossary handling
in `reference/bounded-contexts.md` and `reference/ddd-patterns.md`.

Upstream's version is nonetheless stronger in one respect — it makes a
repository-declared glossary the *naming authority* with an explicit
propose → decide → record → rename protocol, where our step 3 only greps for
divergent terms and flags them LOW.

**Merged that mechanism into `ddd` rather than adding a skill.** A second skill
owning the same concern would split the audit and dilute both trigger surfaces.

### Declined

| Skill | Reason |
|---|---|
| `specification` | U1 overlap with `tcs-workflow:brainstorm` (intent and requirements through dialogue) and `xdd-prd` (requirements, acceptance criteria). The XDD chain owns turning fuzzy intent into acceptance criteria; a competing entry point would fragment it. |
| `react-performance` | U1 overlap with `tcs-team:the-developer:optimize-performance`. It is also a *router* into `vercel-react-best-practices` and `vercel-composition-patterns` — catalogues we do not have — so porting it yields a skill whose main job is to point at nothing. |
| `bff-design` | The "do we need a BFF, how many, who owns each" question is an architecture decision, which is `tcs-team:the-architect:design-system`'s remit. Adding a skill for one architectural style invites a skill per style. |
| `xstate` | Scoped to a single library. Fails U3 — it does not fill a gap in the spec-to-ship workflow, and TCS pattern skills are deliberately library-agnostic (`react-testing` is the closest, and it targets a testing *approach*, not one library's API). |

## Consequences

- Four ports are tracked as their own issues. Each needs PICS conversion
  (progressive-disclosure sections, frontmatter trigger terms), a `skill-author`
  audit before commit, and a `sources.md` entry with the upstream revision.
- `tcs-patterns` grows from 17 to 21 skills once all four land. That is
  deliberate: each fills a named gap rather than adding a variant of something
  we have.
- The declines are recorded here so the next sweep does not re-evaluate them
  from zero. Re-open a decline only if the overlapping TCS component changes
  scope, or if upstream's version diverges enough to change the U2 answer.
- We accepted none of the *agent-behaviour* skills spotted alongside these
  (`double-check`, `find-gaps`, `panel-review`, `wtf`,
  `production-parity-skill-builder`). They belong to `tcs-helper` rather than
  `tcs-patterns` and were out of #80's scope; they remain unevaluated.

## References

- Issue #80, epic #73
- `docs/about/sources.md` — provenance and sync status
- `plugins/tcs-helper/skills/skill-evaluate/SKILL.md` — the criteria applied
