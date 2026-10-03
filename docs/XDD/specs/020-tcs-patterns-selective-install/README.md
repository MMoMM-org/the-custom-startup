# Specification: 020-tcs-patterns-selective-install

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-02 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-10-03 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 36 acceptance criteria across 10 Must features, 0 clarification markers |
| solution.md | completed | 10 ADRs confirmed, 18 acceptance criteria, 0 markers |
| plan/ | completed | 5 phases, 25 tasks, 139 spec references, all resolvable |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-02 | Rebuild tcs-patterns as an installer rather than flag its skills off | `disable-model-invocation` works on plugin skills (measured: -628 tokens, entry gone) but costs the user auto-routing -- a flagged skill must be typed. A skill installed into `<repo>/.claude/skills/` stays in the model-facing listing (+620 tokens vs absent) so routing keeps working only where the pattern applies. |
| 2026-10-02 | Per-skill versions in one manifest, not a single bundle marker | `.claude/skills/.tcs-patterns-manifest` carries `bundle:` plus one line per installed pattern, so drift reports per skill (`ddd v3 -> v4`) and a change to one pattern only flags repos that actually installed it. A single marker would flag every repo for any change. |
| 2026-10-02 | patterns-setup offers to commit the installed files, never forces it | Same stance as `install_files.sh`, which deliberately does not auto-commit (spec-012 PRD M10 AC5). The selection is a project decision worth sharing and reviewing, but the install must not write to someone's history unasked. |
| 2026-10-02 | Full PRD -> SDD -> PLAN before implementation | Breaking change to a published plugin, a new CI gate and a new bundle distribution. Marcus's standing rule after M3 was built ad-hoc and its spec never completed. |
| 2026-10-02 | Catalogue access demoted from Must to Should | Nothing in the Must set depends on it: the relocation, the scan, the install, the collision refusal, the record, the advisory and the gate all stand without it. It is the strongest Should because it preserves what the all-21 install made possible at one description's cost, but shipping the Must set without it still solves the stated problem. |
| 2026-10-02 | ADR-1: installed patterns always carry a `tcs-` prefix | Zero exact collisions exist today, so plain names would have worked now and been fragile later: a repo may create `testing` or `observability` at any time and could then never install that pattern. The prefix makes collision structurally impossible and provenance visible. Accepted cost: the user types a name they did not choose, in the slash menu and in every `skillOverrides` key, and it does nothing for the four near-misses. |
| 2026-10-02 | ADR-2: scanner and installer in Python, only the advisory in bash | Two of the seven traps are structural-parsing problems — runtime vs development dependencies inside JSON, and walking nested manifests — which in bash means a hand-rolled JSON reader or an unavailable `jq`. Python also steps around the whole BSD/GNU constraint list for new code and puts the detector where pytest can call it against fixtures. |
| 2026-10-02 | ADR-3: one `VERSION` integer per pattern, no central catalogue file | Per-pattern versions are required by F7. Given that, per-directory beats a central file on the CI gate: "every changed pattern directory contains a changed VERSION" needs no parsing, and a pattern added later is covered by the rule that already exists. An integer rather than semver because prose has no API for "breaking" to describe. |
| 2026-10-02 | ADR-4: content hash at install, unified diff on conflict | Without a hash the installer cannot tell "never touched" from "deliberately adapted", and its only safe behaviour would be to never overwrite — leaving a diverged pattern permanently stale and the advisory repeating forever. The machinery bought is the hash; given Python the diff is three lines of difflib. Limit accepted: the hash covers SKILL.md only. |
| 2026-10-02 | ADR-5: an unrecognised stack gets nothing, but still reaches the architecture question | The validated set included a desktop app in an uncovered language, where the right answer was nothing. But architectural intent is language-independent, so gating that question on a recognised language would deny patterns to exactly the repos whose architecture is deliberate. "Nothing detected" and "nothing applicable" are separate states. |
| 2026-10-02 | ADR-7: the Obsidian rule stays duplicated, kept honest by a test | The write-time hook must work standalone; making it depend on a file outside itself is the failure mode #163 already records twice. Two implementations plus a test that fails when they disagree buys the safety without the coupling, and needs no new abstraction — only the fixtures the detection suite builds anyway. |
| 2026-10-02 | ADR-9: the existing multi-bundle CI gate gains a per-pattern rule | The gate was already generalized to a table in spec-019 and already runs on every PR. The table's shape does not fit: it asks whether a bundle's single marker changed, which for 21 independently versioned patterns passes when the wrong one was bumped — the precise failure it exists to prevent. Per-directory rule instead, no new script, no new workflow. |
| 2026-10-02 | SDD validation added AC-16 and AC-17 | Mechanical traceability found three PRD criteria with no counterpart: the per-entry listing cost and the baseline-not-surfaced rule from F2, and "a second party can determine currency" from F6. Found by checking rather than by eye, which is the reason the check is run. |
| 2026-10-02 | Decomposition tier: Incremental | Classifier recommended Incremental and rule 1 fired twice: 8 new components (C1-C8; C9 only modifies the existing CI gate script and does not count) and 9 Must features, with 36 acceptance criteria. No parallel work flagged in the design. Accepted. |
| 2026-10-02 | Plan: 5 phases, 25 tasks | Ordering is forced by dependency, not preference: the catalogue first because everything reads it and because its verification needs a fresh session; detection second and alone, because fixtures written before the rules are the PRD's answer to its own top risk and there is nothing to run them against but fixtures; then the write path, then drift, then the user-facing surface. Validation found the spec reference count stated as 68 against 139 actual; corrected. |
| 2026-10-03 | The catalogue reader is promoted to Must as Feature 10 | Flagged at the end of planning rather than discovered: nothing in the Must set depends on it, so MoSCoW put it in Should, but that reading ignores what the relocation takes away. Today 21 pattern names are typable in every repository; afterwards none are, and the only route to a body is to install it. Marcus ruled it Must. The criteria count is unchanged at 36 — the two were already counted; Should drops from 3 entries to 2, and SDD AC-15 now traces to F10 instead of to a Should-have. T5.2 stays in Phase 5, since C8 depends only on C1 and nothing in Phase 5 can now be cut. |
| 2026-10-03 | `skills/REFERENCES.md` does not exist, and never did | T1.1's Prime step said to verify rather than assume, and verification refuted the premise: no such file in the working tree and none in history (`git log --diff-filter=ADR --all` returns nothing). So T1.1's second `git mv` had no source and would have aborted the task, and T1.3's "confirm the two citations resolve post-move" was unachievable — they never resolved. A fourth site was also unlisted (`hexagonal/reference/hexagonal-layers.md:17`, `../REFERENCES.md`). Repair chosen: keep the attribution, drop the dead pointer, invent no source notes. A catalogue-level file was rejected because C5 copies one pattern directory, so a catalogue-relative link is dead again in the consumer repository. T1.3's containment test was tightened from per-catalogue to per-pattern-directory for the same reason. |
| 2026-10-03 | AC-1 restated against what the instrument can measure | `report.py` globs `plugins/*/skills/*/SKILL.md` one level deep and has no notion of a catalogue, so "21 catalogue entries" was unobtainable. The second half was worse: the unreachable list is already empty, so "0 unreachable skill files" is identical before and after the move and cannot distinguish success from doing nothing. Replaced with the figures that do move -- inventory 98 to 77, no `tcs-patterns:` skill left, and the catalogue's 21 `SKILL.md` asserted directly against the tree. Extending `report.py` to see the catalogue was considered and declined as unplanned work on spec-019's artifact inside Phase 1. |
| 2026-10-03 | Rename purity is migration evidence, not a standing test | T1.1's rename assertion ran `git diff --name-status -M HEAD`, which compares the working tree to HEAD. It read 80 while the move was pending and 0 once committed, so it passed at the one moment the task was unfinished and was red forever after -- on a fresh clone and in CI alike. Pinning it to the parent commit or a SHA dies on the squash merge. Removed from the suite in 3a01f59 and recorded in the test module's docstring instead: commit 2a5f192, 80 files at R100, 0 insertions and 0 deletions across all of them. The six genuine invariants stayed. T1.1's validate command was also wrong -- `--summary` prints `rename a/b (100%)` and never the token `R100`, which only `--name-status` emits -- and both phase tasks now require a clean committed tree for every leg. |
| 2026-10-03 | T1.3's "no source note was invented" restated as a structural claim | The criterion asserted a fact about authorship, which no test, diff or later reviewer can settle -- seeing an attribution in the file does not distinguish "already there" from "added to fill the gap". tdd-guardian blocked the task on it. Replaced with the consequence that is checkable: exactly two patterns carry a `reference/references.md` (`observability`, `event-sourcing`), that set must be unchanged, and no existing one may gain a line. The prohibition also moved into the Implement step as an instruction rather than living only as a criterion the implementer reads last. |
| 2026-10-03 | T1.3 needs two link checks, not one, and "contains ../" is not the escape rule | Only one of the four broken references is a markdown link; the other three are bare paths inside inline code spans, which the existing `tests/test_docs_links.py` blanks on purpose to avoid false-positives on quoted examples. So the check must inspect exactly what that test discards. Separately, my proposed rule "contains `../`" was wrong: `../REFERENCES.md` from `hexagonal/reference/` resolves to `hexagonal/REFERENCES.md` and stays inside the pattern, so it breaks the resolve rule and not the escape rule -- the path must be resolved and compared against the pattern root. A fourth control was added for the same reason: a `../` path that resolves inside the pattern must PASS, or a check that blanket-rejects `../` satisfies every other control while being wrong. |
| 2026-10-03 | T1.3's resolve criterion narrowed to what the check can actually enforce | "Every remaining relative link resolves to an existing file" claimed more than any check can deliver here. Measured over the catalogue: 188 file-like paths sit inside code spans -- 80 resolve from the containing file, 39 from the pattern root, 69 from neither, the last group holding MIME types (`application/json`), URL schemes, GitHub slugs and illustrative consumer paths. The same syntax also carries cross-pattern references: `ddd`'s testing doc cites `reference/testing-hex-arch.md`, which lives in `hexagonal/`. One syntax, six meanings, nothing mechanical to separate them -- so the check treats a code span as a path only when it begins `../`, and the criterion now states that scope instead of implying full coverage. Third criterion added requiring the exclusion and its measurement to be recorded in the test module, so the next reader does not mistake the narrowing for an oversight. |
| 2026-10-03 | Cross-pattern references become co-recommendations (new T2.4, AC-18) | Measured while repairing T1.3: 14 cross-pattern code-span references, nine distinct pairs, forming a cycle (`ddd`/`hexagonal` and `event-driven`/`event-sourcing` are mutual). C5 copies one pattern directory, so installing `ddd` alone leaves its citation of `reference/testing-hex-arch.md` dangling in the consumer repo, and Q2 being multiSelect makes that selection reachable. Invisible before this spec, because shipping all 21 made every citation resolve. Marcus chose co-recommendation in Phase 2 over an installer warning or a documented limitation: cheapest real fix, and the user still decides. Encoded as a map DERIVED from the catalogue with a test asserting the nine pairs, not a hardcoded table that would go stale on the first reference change. Companions join the proposal before the outcome partition, so AC-6's three sets stay disjoint and still sum to 21. |

## Context

Claude Code rations the skill listing, which nothing in TCS accounted for. Measured in a live
session on CLI 2.1.286 (2026-10-02):

```
[WARN] Skill listing over budget: 112 skills, 40191 chars > 30000 budget
       -- descriptions will be truncated.
```

Defaults read out of the CLI binary: `skillListingBudgetFraction` = 0.01 of the context window
(in characters, which is 8000 on a 200k-class model and 30000 in this 1M-context session --
both observed, not derived), `skillListingMaxDescChars` = 1536 per
description.

tcs-patterns is the largest single contributor: 5918 of the 21128 characters the six TCS plugins
put into that listing (28%), roughly 15% of the whole 40191. Its own manifest has promised
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

**Scope limit, stated up front:** this does not get the listing under budget. 40191 -> ~34300
characters against a budget of 8000 to 30000 depending on the model. tcs-patterns is the
biggest single item, but tcs-team (4924),
tcs-helper (4460) and tcs-workflow (4401) are each comparable. Getting under budget needs the
same treatment across all four, or a raised `skillListingBudgetFraction`. That is a follow-on,
not this spec.

---
*This file is managed by the xdd-meta skill.*
