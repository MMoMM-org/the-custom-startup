# Declined Decisions

> The memory bank stores what is true **now**. This file stores what we decided **not** to do, and
> why — the half plain memory lacks. Without it a rejected idea resurfaces weeks later as if fresh,
> and gets re-argued from zero by a session that never saw the original conversation.

**Before proposing anything structural** — a new layer, a tool swap, a restructure, an automation,
adopting something from an upstream source — read this file. If the idea is here, do not re-pitch
it unless its `Revisit if` condition now holds, or you reopen it *explicitly* as a trade-off that
quotes the original decline.

**When something is rejected or deferred**, append the entry in the same session. Capturing it a
week later does not happen.

**When a decline is overturned**, do not delete the entry. Mark it `⚡ OVERTURNED <date>` with a
pointer to what replaced it, and keep the original text. A parallel session must never cite a dead
verdict as live.

Entry form:

```
### YYYY-MM-DD — <short title>
- **Proposed:** what was suggested
- **Decision:** rejected | deferred
- **Why:** the reason, in the decider's own words where possible
- **Revisit if:** the condition that reopens it, or —
```

Only structural things belong here. An ordinary implementation choice is not a decline; if nobody
would plausibly re-propose it, leave it out.

---

### 2026-09-05 — `@`-import the memory category files into every prompt

- **Proposed:** make `memory.md` `@`-import `general.md`, `tools.md`, `domain.md`, `decisions.md`,
  `context.md`, `troubleshooting.md`, so the bank actually reaches subagents instead of being
  opt-in reading they mostly skip.
- **Decision:** rejected
- **Why:** Marcus — "ich will weiterhin nicht den context der agenten und der main session so voll
  haben". Six files into every agent prompt *and* the main session is the wrong trade for a bank
  that is reference material most of the time.
- **Revisit if:** an agent is measurably failing for want of a category file's content, or the bank
  shrinks enough that the cost is negligible. The cheaper alternative — a per-rule index line
  instead of a per-file pointer — is #147, and does not require importing any bodies.

### 2026-09-05 — a PAT to bypass the `main` ruleset for the auto-bump push

- **Proposed:** give `auto-bump-versions.yml` a personal access token and add a bypass actor, so
  required status checks can stay on while the bot still pushes to `main`.
- **Decision:** rejected
- **Why:** a PAT acts as its owner, who is a repository admin, so the only accepted bypass
  (`RepositoryRole: admin`) would cover **every merge that owner makes**. The checks would stop
  applying to the case they exist for, and auto-merge would again have nothing to wait for — the
  bug the ruleset was built to fix.
- **Revisit if:** a GitHub App is created and installed; an `Integration` bypass exempts the bump
  push alone and leaves human merges gated.

### 2026-09-05 — re-enable the `main` ruleset as it stands

- **Proposed:** switch ruleset `22331008` back to `active` with its six required checks.
- **Decision:** deferred
- **Why:** required status checks in a ruleset apply to **direct pushes**, not only merges. A fresh
  bot commit has no check runs, so `auto-bump-versions.yml` was rejected with `GH013` on every
  merge and left `tcs-git-helpers` version-inconsistent on `main`.
- **Revisit if:** a bypass actor exists that exempts the bot and nothing else — see the entry above.

### 2026-09-05 — pilot `memory:` on a TCS agent

- **Proposed:** enable subagent persistent memory on one agent and judge whether recall improves
  the output (#85, criterion 4).
- **Decision:** deferred
- **Why:** the criterion demands a measured before/after, and the instrument is `claude plugin
  eval`, which this account is not enabled for. A pilot without measurement is an opinion with
  frontmatter, and would leave the criterion just as open. The remaining candidates are also on the
  list only because they are *not* read-only — a constraint, not a recommendation.
- **Revisit if:** `plugin eval` is enabled (#84), or #144 reports that the unscoped `Write`/`Edit`
  grant has been confined, which puts the reviewer agents back in play.

### 2026-09-05 — adopt upstream's `evals.json` layout for eval suites

- **Proposed:** follow `rsmdt/the-startup`'s per-skill `evals/evals.json` + `fixtures/` convention.
- **Decision:** rejected
- **Why:** the first-party runner expects `<eval dir>/**/case.yaml`, or `prompt.md` plus
  `graders/*.md`. Upstream's format predates it and would not run at all — this is not a style
  preference.
- **Revisit if:** —

### 2026-09-05 — put `README.md` in `.github/docs-map`

- **Proposed:** require a README change whenever user-facing code changes, enforced by `docs-sync`.
- **Decision:** rejected
- **Why:** almost no code change needs the README, so the rule would be wrong far more often than
  right, and a check that is usually wrong gets switched off within a week — at which point it
  protects nothing. It lives in the pull request template instead, where it costs a glance rather
  than a red build.
- **Revisit if:** README staleness recurs despite the template checklist.

### 2026-09-05 — adopt `claude-bible`'s frontmatter precedence for the memory bank

- **Proposed:** `origin: owner`, `date_established`, `status: superseded` and supersede-never-delete
  on memory entries, from [`tonydzi/claude-bible`](https://github.com/tonydzi/claude-bible).
- **Decision:** rejected
- **Why:** supersede-don't-delete fills a 24 KB bank with dead rules, which is what
  `/memory-cleanup` exists to remove. It is the right design for their setting — a large vault,
  several machines, human assistants alongside agents — and the wrong one for a single-writer bank
  under a hard budget. Our ADRs already supersede properly, which is where that discipline belongs.
- **Revisit if:** more than one person or machine writes to the bank.

### 2026-09-04 — resolve the statusline OAuth token from the environment only

- **Proposed:** read `CLAUDE_CODE_OAUTH_TOKEN` and nothing else, so the shipped script carries no
  credential-file or keychain reading code for anyone who installs TCS.
- **Decision:** rejected (by Marcus, over the recommendation)
- **Why:** enabling the feature should not also require an `export`. The fuller resolution — env,
  then `~/.claude/.credentials.json`, then the system keychain — was chosen for convenience, with
  the cost accepted knowingly.
- **Revisit if:** —

### 2026-09-06 — turn `tdd-guardian` into an observer, and run Gate 1 to decide it

- **Proposed:** re-shape `tdd-guardian` from a pre-dispatch gate into an in-flight observer on the
  implementer (#99), and first run Gate 1 — an observer attached to ~5 real `implement` dispatches,
  reports logged not acted on, to measure detection value.
- **Decision:** rejected (the re-shaping), deferred (Gate 1)
- **Why:** the spike measured the blocker as structural, not one of signal quality. A report to the
  observed agent is advisory — a worker refused one, calling it "not user consent" — and on a
  fan-out the report goes to the *coordinator* instead, which is only delivered while that
  coordinator is **running**. An orchestrator awaiting an implementer is parked by definition: the
  probe lost 5 of 7 reports parked, against 2 of 8 when the same coordinator was kept busy. So the
  escalation path is closed in exactly our topology, and Gate 1's number — how often an observer
  has something useful to say — cannot change that in either direction. Gate 1 also is not free
  the way the plan assumed: it attaches a write-capable agent to real implementation runs.
- **Revisit if:** the fields leave experimental and the liveness behaviour changes so a parked
  target still receives reports; or we want an observer for a topology where the target stays awake
  — an agent doing long work *itself* rather than waiting on a subagent, where delivery measured
  5 of 5. In that case run Gate 1 restricted to that shape, with an explicit `tools:` line on the
  observer. Full evidence: #99 and its two Gate 0 comments.
