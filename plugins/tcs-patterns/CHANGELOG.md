# Changelog

All notable changes to `tcs-patterns` are documented here.

Patch versions are bumped automatically when a merge touches this plugin
(`.github/workflows/auto-bump-versions.yml`), so not every version has an entry.
Add one when a change is worth a reader's attention. The top entry must never
name a version `plugin.json` does not carry — `scripts/ci/check-changelog-version-sync.sh`
enforces that on every merge.

## [2.0.0] - 2026-10-06

### Changed (breaking)

- **The 21 pattern skills are no longer plugin skills.** They moved from `skills/<name>/` to
  `templates/patterns/<name>/` and are now a catalogue the plugin carries, not skills it registers.
  After updating, `/tcs-patterns:ddd`, `/tcs-patterns:hexagonal` and the other nineteen no longer
  exist. Each pattern's `SKILL.md` and `reference/` moved unchanged, and each gained a `VERSION`
  file that drift detection compares against.
- **What you do now.** In each repository that used a pattern, run
  `/tcs-patterns:patterns-setup install` and choose from the proposal. Installed patterns live in
  `<repo>/.claude/skills/tcs-<pattern>/`, so the name gains a `tcs-` prefix: `/tcs-patterns:ddd`
  becomes `tcs-ddd`. To read a pattern without installing it, run `/tcs-patterns:pattern ddd`.
  A user on `1.x` keeps the 21 plugin skills until the plugin updates; after updating they have
  none until the setup is run.
- **Why.** Claude Code budgets the skill listing, and 5918 of the 21128 characters the six TCS
  plugins put into it went on 21 pattern descriptions that most repositories never use. Space
  freed by one description is consumed by another, so the cost shows up as shortened descriptions
  for every other skill, not as tokens. A pattern is now in a session's listing only when a
  repository chose it.

### Added

- **`/tcs-patterns:patterns-setup <install|update|remove|status> [path]`.** `install` scans the
  repository, proposes patterns from what it finds, asks at most three questions, and writes the
  selection to `<repo>/.claude/skills/tcs-<pattern>/` together with a `.tcs-patterns-manifest`
  recording what was installed at which version. `update` refreshes patterns the catalogue has
  moved past and, for a pattern edited locally, shows the diff instead of overwriting it.
  `remove` deletes a pattern and its manifest entry; a locally edited one needs `--discard-edits`
  and the diff is shown first. `status` reports installed, drifted and unaccounted-for patterns.
- **`/tcs-patterns:pattern <name>`.** Shows one catalogue pattern in the session without installing
  it.
- **The manifest carries `schema = 1`.** A manifest written by a later tcs-patterns with a
  higher `schema` can still be read by `status` and the drift advisory. `install`, `update`
  and `remove` refuse to rewrite it and ask for a plugin update instead, so newer fields are
  never dropped. Each entry's `installed_as` must be `tcs-<name>`: a hand-edited entry naming
  another directory makes the manifest unparseable rather than letting `update` overwrite that
  directory.
- **Drift advisory.** The `tcs-git-helpers` session brief names installed patterns that are behind
  the catalogue, and patterns the catalogue can no longer account for (see its changelog).

### Fixed

- **The plugin description's promise is now kept.** `plugin.json` has said "Install only the
  patterns relevant to your stack" since the plugin began, but installing the plugin registered
  all 21. Now only the selected ones reach a repository.

## [1.4.4] - 2026-09-04

### Changed

- **`testing` and `test-design-reviewer` converted to PICS (#120)** — the last two skills in the plugin that predated the convention. Both now carry a Persona section opening with the active-skill announcement, an Interface, `Always:`/`Never:` constraints, and a numbered Workflow, plus the `argument-hint` and `allowed-tools` frontmatter their nineteen siblings already declared. `test-design-reviewer` had no active-skill line at all, so a user could not tell from the terminal that it had activated.
- **Educational content moved behind progressive disclosure.** `testing` keeps its examples in `reference/public-api-testing.md`, `reference/test-factories.md` and `reference/coverage-theater.md` (218 → 102 lines); `test-design-reviewer` keeps the eight scoring bands in `reference/farley-properties.md` and the report template in `reference/output-format.md` (151 → 89 lines). The `## Test Design Review: [File/Suite Name]` template artifact no longer sits in the skill's own heading hierarchy.
- **`testing`'s audit step names the test framework before grepping.** Its smell patterns were Jest-shaped with nothing said about it, so a Python or Go suite would grep clean and read as passing.

## [1.4.3] - 2026-09-03

### Added

- **`bff-entry-points` skill (#98)** — browser-facing HTTP entry-point hardening: an explicit public/protected classification for every production route, a composition-prepared registrar that installs the chain by construction, the session cookie profile, Origin/Fetch Metadata/CSRF/content-type policy, no-oracle failure semantics, protected SSE and WebSocket upgrades, a single browser-side authentication coordinator, and twelve automated gates. Six references. The workflow leads with enumeration and classification, because the vulnerability is the missing check (CWE-306), not the broken one.

### Changed

- **`secure-oauth-oidc` no longer declares the browser session layer unguided.** Its Boundaries section said to stop at "token obtained" and "name it as unguided rather than improvising past it"; that boundary now has an owner on the other side, and both skills say so in the same words.

## [1.4.2] - 2026-09-03

### Added

- **`event-sourcing` skill (#97)** — the append-only log as source of truth: the Decider write model, rehydration as a left fold, the event store port with optimistic concurrency, projections and read models, event versioning and upcasters, snapshots, crypto-shredding. Nine references. The workflow leads with the complexity ladder, because the most common defect is adopting the pattern at all.

### Changed

- **`event-driven` no longer teaches event sourcing.** Its reference carried a class-based, mutable `rehydrate` and an `EventStore` interface that contradicted the new skill's pure fold. Both are replaced by a boundary pointer, and the skill gained a Boundaries table: it owns events as *messages* (schema, naming, correlation, idempotency, ordering), `event-sourcing` owns events as *persistence*. The projection example moved for the same reason.
- **`ddd` and `hexagonal` name the new owner.** `ddd` states that how an aggregate is persisted is out of scope; `hexagonal`'s `cqrs-lite.md` points at `event-sourcing` as the full form of the read/write split. Without these, the new skill claimed a boundary the other side did not acknowledge — the same defect the `twelve-factor` edit fixed in 1.4.1.
- **Fat events are no longer flatly an anti-pattern** in `event-driven`'s catalogue. A *deliberate* fat event is a consumer-isolation trade-off; only the accidental one — the whole aggregate state — is the defect.

## [1.4.1] - 2026-09-03

### Added

- **`secure-oauth-oidc` skill (#95)** — OAuth 2.0 and OpenID Connect against the RFC 9700 / BCP 240 baseline. Transaction ledger, the four control boundaries, ID Token validation as an ordered protocol check, and five references including a 55-control catalog with section provenance. TCS had no auth pattern skill before this.
- **`observability` skill (#96)** — wide events and canonical log lines, OpenTelemetry traces and metrics, context propagation, sampling, metric cardinality, and the four-tier placement model. SLOs, error budgets and alerting deliberately stay with `tcs-team:the-devops:monitor-production`.

### Changed

- **`twelve-factor` Factor XI now owns log transport *and* shape** — machine-parseable output, recognized severity levels, structured context, ISO 8601 timestamps — and names `observability` as the owner of what goes into the stream. Without this the new skill claimed a boundary the other side did not acknowledge.

### Note on this version

Both skills above shipped on `main` while `plugin.json` still read `1.4.0`. Each
of their pull requests added keywords to the manifest, and the auto-bump script
read "this manifest is in the diff" as "the author bumped it deliberately", so
it skipped the plugin and bumped only the marketplace. The classification now
compares the version field itself. This entry carries the version the two ports
should have produced.

## [1.4.0] - 2026-09-03

Changelog started at the version the plugin already carried. Nothing is
reconstructed here — earlier history is in the repository's git log and in the
root `CHANGELOG.md`.
