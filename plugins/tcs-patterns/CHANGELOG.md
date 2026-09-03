# Changelog

All notable changes to `tcs-patterns` are documented here.

Patch versions are bumped automatically when a merge touches this plugin
(`.github/workflows/auto-bump-versions.yml`), so not every version has an entry.
Add one when a change is worth a reader's attention. The top entry must never
name a version `plugin.json` does not carry — `scripts/ci/check-changelog-version-sync.sh`
enforces that on every merge.

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
