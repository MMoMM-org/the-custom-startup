# Specification: 019-observability-rollout-across-active-repos

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-08 |
| **Current Phase** | PLAN |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-08 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 26 acceptance criteria, 0 clarification markers, 1 open question carried (collection-period end date) |
| solution.md | completed | 4 components, 8 ADRs all confirmed, 24 acceptance criteria |
| plan/ | completed | Incremental tier: 4 phases, 18 tasks, 2 parallel, 71 spec references |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-08 | Spec opened | spec-018 shipped a working instrument and left it pointed at a repository where little work happens. Its own Won't-Have deferred distribution with the condition "revisit once the record has answered a real question" — but that condition can never be met from here, because the premise underneath it ("#147 needs the evidence *here*") is false. The maintainer works actively in four other repositories. This is a corrected premise, not an override of the decision |
| 2026-09-08 | Branched from the spec-018 branch, not `main` | spec-018 is unmerged and `main` ends at spec-017. `scripts/observability/report.py` — which this spec extends — does not exist on `main` at all, so a spec written from there could not reference its own starting point |
| 2026-09-08 | **No real repository names or paths in any COMMITTED artifact** — spec documents, commit messages, code. Targets are `repo1`–`repo4` there. **The report's own output is the opposite case: it names repositories, deliberately.** | Maintainer instruction, refined 2026-09-08 after an over-broad first reading by the author of this row. The two contexts have nothing in common. A spec document is committed to a PUBLIC repository (`gh repo view` → `visibility: PUBLIC`) and travels wherever the repository travels; the names of the repositories someone works in are exactly the context this spec exists to keep separate, so publishing them in the document arguing for that separation would be self-defeating. A report is generated locally, on the maintainer's own machine, from records that never leave it. There, the repository name is not an exposure but **the payload**: "does skill A fire in both repositories where it is supposed to?" is the actionable question, and it is unanswerable from a pooled total. Anonymising the report would delete its usefulness to protect against a disclosure that is not happening |
| 2026-09-08 | **Per-repository detail is the reporting default; a union figure is added only where it answers something a per-repository view cannot** | Follows from the row above, and independently from the research: merging is *misleading* for recording status and for the hook `installed` flag, because one live repository would make the whole report read fresh and hide stale logs — inverting spec-018's SDD-AC-15 honesty rule. Firing coverage is the one analysis that genuinely gains from merging, and notably the one that needs no repository identity at all: it unions numerators against a single shipped-inventory denominator. So the split is not a compromise between usefulness and honesty — the same line satisfies both |
| 2026-09-08 | ~~**Registration follows the satori pattern: an absolute path resolved at setup time.**~~ **SUPERSEDED TWICE the same day** — by the row below on *which file*, and by ADR-2 in `solution.md` on *the mechanism*. What survives of this row is only its negative half: the plugin `hooks.json` route was rejected, and the reasons below still hold. The absolute path did **not** survive: ADR-2 replaced it with a `$HOME`-relative bundle, because an absolute path cannot express the container and host shapes from one command string, and has no upgrade path. A first attempt to amend this row scoped the amendment to "which file" and explicitly claimed the mechanism still stood — which left the contradiction in place and a validator caught it. | Chosen over a plugin `hooks.json` registration. The plugin route resolves paths more cleanly via `${CLAUDE_PLUGIN_ROOT}`, but registers the hooks in *every* repository with the plugin enabled, each paying ~3-5 ms per matching event whether or not recording is on — a floor set by the macOS per-exec code-signature check, with script size and early-exit position both measured and refuted as causes. spec-018's Won't-Have list already rejected a permanently installed timing layer on exactly that reasoning. It is also unproven: no manifest in this repository registers `InstructionsLoaded` or `SubagentStart`, and the first of those is the event that carries the instruction data. The satori pattern touches only the repositories named, needs no plugin publish, and its merge half is proven in-repo |
| 2026-09-08 | **Setup writes into each target's `.claude/settings.local.json`, never `.claude/settings.json`** | Found while checking a residual risk rather than by design intent, and it inverted the obvious choice. In three of the four targets `.claude/settings.json` is **tracked in git**, and all four have remotes. Writing the registration there would put it in the maintainer's diffs, let it be committed by accident, and — once pushed — start recording for anyone who clones the repository and opens a session, with no reason to look for it. That is precisely the breach spec-018's PRD Feature 3 names, arriving one clone away rather than through a plugin update. `settings.local.json` is untracked in all four. It is also proven to carry hooks: one of the four already has a `hooks` block there, which is empirical evidence that the harness honours them at that layer rather than a claim from documentation. The satori precedent supplies the merge mechanism, not the choice of file — that choice is ours, and the evidence settles it |
| 2026-09-08 | **Success is defined as "#147 becomes decidable", not "records exist"** | Maintainer choice. The criterion is that after a stated collection period the report can say, for every shipped skill and agent, in which target repositories it fired and in which it did not — reliably enough to decide keep, drop or rework. A criterion phrased as "recording works" would be met on day one and would leave the feature in exactly the state spec-018 left it: built, correct, and answering nothing |
| 2026-09-08 | **The setup command is general and reversible, not a four-repository script** | Maintainer choice. It accepts any target, detects the host or container shape itself, merges without damaging foreign entries, reports honestly when it finds entries it does not own, and can uninstall. The incremental cost over a hard-coded script is small because the merge logic is required either way — and a setup path with no uninstall path is a trap, leaving entries to be pulled out of several files by hand later |
| 2026-09-08 | **Decomposition tier: Incremental.** Classifier recommended Incremental; maintainer confirmed | Rule 1 fired twice over: `component_count` 3 (bundle installer, registration editor, locations config are new surface; the report aggregation modifies existing code and so does not increment) and `feature_count` 4. `ac_count` 26, `change_type` feature, `parallel_markers` **false** — the two "concurrent" mentions in the SDD are a requirement that concurrent setup runs must serialize, which is a safety property of the lock rather than a parallel work stream, so a naive grep would have set this signal wrongly. Not a borderline case: breadth vetoes Direct regardless of change type, and both breadth signals cleared the threshold independently |

## Context

### What spec-018 delivered, and what it did not

spec-018 built and proved the recorder: instruction loads with reason and parent, byte cost split
between the always-loaded and conditional layers, skill and agent firings joined against the shipped
inventory, structurally unreachable skills, and per-hook durations under a temporarily installed
wrapper. Every acceptance criterion carries evidence.

What it did not deliver is data. The record has run in one repository for one session. Two figures
from that session are sound at any sample size — the always-loaded layer costs 7038 bytes, and 15
skills in one plugin are structurally unreachable, nested too deep to be discoverable at all. One is
not a finding: "82 of 83 never fired" over a single session describes the sample, not the inventory.

### The four target repositories, verified 2026-09-08

Named `repo1`–`repo4` deliberately; see the Decisions Log. What matters here is not which they are
but that they fall into **two kinds**, because the two kinds put the record in different places.

| Target | Runs in | Record location shape |
|---|---|---|
| repo1 | container | `<repo>/claude-docker-home/.claude/plugins/data/observability-<repo>/observability/events.jsonl` |
| repo2 | **host** | `$HOME/.claude/plugins/data/observability-<repo>/observability/events.jsonl` |
| repo3 | container | container shape, as repo1 |
| repo4 | container | container shape, as repo1 |

Three of the four run Claude in a per-repository container whose home is bind-mounted from
`<repo>/claude-docker-home`; the fourth runs on the host. (Where a target repository contains Docker
configuration of its own, that belongs to the application it ships and has nothing to do with how
Claude runs there — the two were easy to confuse and are not the same thing.)

All four are git repositories. **Corrected 2026-09-08 after a consistency audit:** an earlier
version of this paragraph concluded from "all four already have a `.claude/settings.json`" that
setup only ever extends an existing file. That conclusion was drawn about the wrong file. Setup
writes to `.claude/settings.local.json` (see the Decisions Log), and while that file happens to
exist in all four targets today, nothing guarantees it in general — so **setup must handle an absent
file by creating it**, which is a tested criterion (SDD-AC-2) and a fixture in the phase-2 matrix.
An implementer trusting the old wording would have dropped that path. No record exists in any of the
four yet.

### The three constraints this spec has to satisfy

1. **Two path shapes, not one.** A container repository's record lands inside the repository
   directory under `claude-docker-home/`; a host repository's lands under the user's real `$HOME`.
   Any location config must express both. Note that `claude-docker-home/` is gitignored, so
   spec-018's SDD-AC-10 *intent* (the record cannot be committed) survives even though its literal
   wording, "outside the repository working tree", does not hold inside a container.
2. **`report.py` reads exactly one record.** Its `--events` flag takes a single path. Reading N
   records as one logical set is new work — though the same shape as the rotated-chain merge it
   already performs.
3. **Aggregating at report time is not the same as pooling at rest.** spec-018 deliberately rejected
   a single cross-repository record because it would "mix client contexts into one file". Keeping
   the records separate and merging them for a report does not violate that decision — but the
   report's *output* would still place four contexts side by side, and that needs a deliberate
   answer rather than an accident. Skill and agent usage aggregates harmlessly; file paths from four
   contexts are a different question, and so are the repository names themselves.

### Enabling must never become automatic

spec-018's PRD Feature 3 names the persona as an "ordinary Claude Code user; may not know the
plugins ship hooks at all", whose pain point is that "a plugin update that silently starts recording
their Bash command lines would be a breach of trust, and they would have no reason to look for it".
A setup command is invoked by a person. It is not a prompt at session start, and it is not something
a plugin update performs.

Note also the mechanical limit, which settles the question independently of whether it were
desirable: a hook is a child process and cannot set an environment variable in the session that
spawned it. "Enable itself on demand" is not available in that form at all. The most a hook could do
is write into a configuration file, which takes effect for the *next* session — a different act, and
one that needs a person behind it.

---
*This file is managed by the xdd-meta skill.*
