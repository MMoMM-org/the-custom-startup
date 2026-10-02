# Specification: 020-tcs-patterns-selective-install

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-02 |
| **Current Phase** | PRD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-10-02 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | in_progress | |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-02 | Rebuild tcs-patterns as an installer rather than flag its skills off | `disable-model-invocation` works on plugin skills (measured: -628 tokens, entry gone) but costs the user auto-routing -- a flagged skill must be typed. A skill installed into `<repo>/.claude/skills/` stays in the model-facing listing (+620 tokens vs absent) so routing keeps working only where the pattern applies. |
| 2026-10-02 | Per-skill versions in one manifest, not a single bundle marker | `.claude/skills/.tcs-patterns-manifest` carries `bundle:` plus one line per installed pattern, so drift reports per skill (`ddd v3 -> v4`) and a change to one pattern only flags repos that actually installed it. A single marker would flag every repo for any change. |
| 2026-10-02 | patterns-setup offers to commit the installed files, never forces it | Same stance as `install_files.sh`, which deliberately does not auto-commit (spec-012 PRD M10 AC5). The selection is a project decision worth sharing and reviewing, but the install must not write to someone's history unasked. |
| 2026-10-02 | Full PRD -> SDD -> PLAN before implementation | Breaking change to a published plugin, a new CI gate and a new bundle distribution. Marcus's standing rule after M3 was built ad-hoc and its spec never completed. |

## Context

Claude Code rations the skill listing, which nothing in TCS accounted for. Measured in a live
session on CLI 2.1.286 (2026-10-02):

```
[WARN] Skill listing over budget: 115 skills, 42086 chars > 8000 budget
       -- descriptions will be truncated.
```

Defaults read out of the CLI binary: `skillListingBudgetFraction` = 0.01 of the context window
(in characters, so 8000 chars at 200k and 40000 at 1M), `skillListingMaxDescChars` = 1536 per
description.

tcs-patterns is the largest single contributor: 5918 of the 21128 characters the six TCS plugins
put into that listing (28%), roughly 14% of the whole 42086. Its own manifest has promised
selective installation since it shipped -- `plugins/tcs-patterns/.claude-plugin/plugin.json:4`
and `.claude-plugin/marketplace.json:30` both say "install only the patterns relevant to your
stack" -- and no mechanism has ever delivered it.

Consumer-side selection is impossible for plugin skills. `skillOverrides` (`on` | `name-only` |
`user-invocable-only` | `off`) is the per-skill knob, but its resolver returns early:

```js
if (e.type !== "prompt" || e.source === "plugin") return "on";
```

Measured as zero effect across all three plausible key formats. The only consumer lever for a
plugin skill is `enabledPlugins`, which is all-or-nothing.

**The win is description quality, not tokens.** Disabling tcs-patterns outright saves ~220 tokens
today (median of eight interleaved runs) because the listing is already clipped to budget --
freed space is immediately taken by other descriptions. Raising the budget from 0.01 to 0.1 adds
7127 tokens, which is the amount of listing being discarded today. So the 21 descriptions are not
mainly a token cost; they are 5918 characters of pressure that truncates every other skill's
description, including the routing contracts written into tcs-team on 2026-10-01.

**Scope limit, stated up front:** this does not get the listing under budget. 42086 -> ~36200
characters against 8000. tcs-patterns is the biggest single item, but tcs-team (4924),
tcs-helper (4460) and tcs-workflow (4401) are each comparable. Getting under budget needs the
same treatment across all four, or a raised `skillListingBudgetFraction`. That is a follow-on,
not this spec.

---
*This file is managed by the xdd-meta skill.*
