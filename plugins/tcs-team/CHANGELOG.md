# Changelog

All notable changes to `tcs-team` are documented here.

Patch versions are bumped automatically when a merge touches this plugin
(`.github/workflows/auto-bump-versions.yml`), so not every version has an entry.
Add one when a change is worth a reader's attention. The top entry must never
name a version `plugin.json` does not carry — `scripts/ci/check-changelog-version-sync.sh`
enforces that on every merge.

## [3.4.5] - 2026-10-07

### Changed

- **Cross-plugin routing contracts name the installed pattern, `tcs-<name>`.** After tcs-patterns 2.0
  the address `tcs-patterns:<name>` resolves to nothing; a pattern is a repo skill `tcs-<name>`,
  installed with `/tcs-patterns:patterns-setup`. The "Do NOT use ... `tcs-<name>` owns that"
  clauses in six skill descriptions and the skills README now say so.

## [3.4.4] - 2026-10-01

### Fixed

- **Every skill was undiscoverable, so every agent's `skills:` preload silently resolved to
  nothing.** The 15 skills sat at `skills/<category>/<name>/SKILL.md`. Claude Code discovers a
  plugin skill only at `skills/<name>/SKILL.md` — exactly one level — so none of them existed as
  far as the harness was concerned, and `claude plugin details tcs-team` reported `Skills (0)`.

  That mattered more than a missing slash command, because these skills were never meant to be
  typed: all 15 are `user-invocable: false` and exist to be **preloaded** into this plugin's
  agents, every one of which carries a `skills:` line. `skills:` resolves by name against the
  discovered registry, and an unresolvable name is skipped with only a debug-log warning. So all
  15 agents have been running without the context they declare, silently, for as long as they
  have existed. `build-feature` was dispatched 10 times in a target repository during spec-019's
  three-week collection period.

  Flattened to one level: 14 pure directory renames at 100 % similarity, no content touched, no
  internal path edited — every skill already referenced its own `reference/`, `examples/`,
  `templates/` and `checklists/` relative to itself.

### Changed

- **`testing` is now `test-practices`.** Making the skills discoverable put tcs-team's `testing`
  alongside the long-reachable `tcs-patterns:testing`. Two skills answering to one name make
  preload resolution undefined, so `build-feature` and `test-strategy` could have been handed the
  wrong body. tcs-team's was renamed rather than tcs-patterns': the latter is live and
  user-invocable, the former was inert by construction. The new name also describes the content
  better — mocking rules by layer, failing-test debugging, flaky-test management.

- **11 of 15 descriptions rewritten as routing contracts.** They were written while nothing could
  compete with them; they now sit in a registry with tcs-patterns' 21 and tcs-workflow's 23
  skills. Each rewritten one states the situation it is for and names the reachable skill that
  owns the neighbouring ground. `feature-prioritization`, `user-research`, `frontend-patterns` and
  `performance-analysis` were left alone — read beside their nearest neighbour, they do not clash.

  Ten descriptions are double-quoted now. The rewrites introduced a clause ending in a colon,
  which YAML reads as a key, and ten frontmatter blocks stopped parsing. `claude plugin validate`
  passed cleanly over all ten, so it is not a safety net for skill frontmatter — parse it yourself.

- `skills/README.md` and this plugin's README no longer present category directories as the
  layout, and the skills table's count is corrected from 16 to the 15 rows it always had.

## [3.4.1] - 2026-09-03

Changelog started at the version the plugin already carried. Nothing is
reconstructed here — earlier history is in the repository's git log and in the
root `CHANGELOG.md`.
