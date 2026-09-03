# Changelog

All notable changes to `tcs-patterns` are documented here.

Patch versions are bumped automatically when a merge touches this plugin
(`.github/workflows/auto-bump-versions.yml`), so not every version has an entry.
Add one when a change is worth a reader's attention. The top entry must never
name a version `plugin.json` does not carry — `scripts/ci/check-changelog-version-sync.sh`
enforces that on every merge.

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
